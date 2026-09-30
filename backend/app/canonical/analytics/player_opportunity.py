"""
player_opportunity — weekly opportunity scores from usage facts.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import (
    normalize_float,
    nullify_object_frame,
    score_from_rate,
    weighted_mean,
)
from app.canonical.analytics.persist import (
    count_rows,
    finalize_output,
    get_or_build,
    load_rows,
    upsert_rows,
)


_CACHE: pd.DataFrame | None = None
_CACHE_WITH_KEYS: pd.DataFrame | None = None
_CACHE_SEASONS: tuple[int, ...] | None = None

TABLE_NAME = "player_opportunity"

PLAYER_OPPORTUNITY_COLUMNS = [
    "player_id",
    "season",
    "week",
    "opportunity_score",
    "receiving_opportunity_score",
    "rushing_opportunity_score",
    "red_zone_opportunity_score",
    "source_ids",
]


def _score_volume(
    count: Any,
    *,
    per_unit: float,
) -> float | None:
    """Map an absolute count into a capped 0–100 score."""

    value = normalize_float(count)
    if value is None:
        return None
    return min(100.0, float(value) * float(per_unit))


def _receiving_opportunity(row: dict[str, Any]) -> float | None:
    rate_score = weighted_mean(
        [
            score_from_rate(row.get("target_share")),
            score_from_rate(row.get("route_participation_rate")),
            score_from_rate(row.get("air_yard_share")),
        ],
        weights=[0.45, 0.35, 0.20],
    )
    if rate_score is not None:
        return rate_score
    # Rates can lag early in a week; fall back to volume.
    return weighted_mean(
        [
            _score_volume(row.get("routes_run"), per_unit=2.5),
            _score_volume(
                row.get("red_zone_targets"),
                per_unit=25.0,
            ),
        ],
        weights=[0.75, 0.25],
    )


def _rushing_opportunity(row: dict[str, Any]) -> float | None:
    rate_score = weighted_mean(
        [
            score_from_rate(row.get("rush_share")),
            score_from_rate(row.get("touch_share")),
        ],
        weights=[0.6, 0.4],
    )
    if rate_score is not None:
        return rate_score
    return weighted_mean(
        [
            _score_volume(row.get("touches"), per_unit=5.0),
            _score_volume(
                row.get("goal_line_carries"),
                per_unit=30.0,
            ),
            _score_volume(
                row.get("inside_5_carries"),
                per_unit=25.0,
            ),
        ],
        weights=[0.70, 0.20, 0.10],
    )


def _qb_rushing_opportunity(row: dict[str, Any]) -> float | None:
    rush_rate = row.get("qb_rush_share")
    if rush_rate is None:
        rush_rate = row.get("rush_share")
    return weighted_mean(
        [
            score_from_rate(rush_rate),
            _score_volume(
                row.get("designed_rush_attempts"),
                per_unit=12.5,
            ),
            _score_volume(row.get("scrambles"), per_unit=12.5),
        ],
        weights=[0.50, 0.30, 0.20],
    )


def _qb_passing_opportunity(row: dict[str, Any]) -> float | None:
    # ~40 dropbacks / ~10 deep attempts ≈ full credit.
    return weighted_mean(
        [
            _score_volume(row.get("dropbacks"), per_unit=2.5),
            _score_volume(
                row.get("deep_pass_attempts"),
                per_unit=10.0,
            ),
        ],
        weights=[0.75, 0.25],
    )


def _red_zone_opportunity(row: dict[str, Any]) -> float | None:
    # Red-zone volume is absolute; map lightly into 0–100.
    rz_touches = normalize_float(row.get("red_zone_touches"))
    rz_targets = normalize_float(row.get("red_zone_targets"))
    rz_goal = normalize_float(row.get("goal_line_carries"))
    return weighted_mean(
        [
            None if rz_touches is None else min(100.0, rz_touches * 20.0),
            None if rz_targets is None else min(100.0, rz_targets * 25.0),
            None if rz_goal is None else min(100.0, rz_goal * 30.0),
        ]
    )


def _skill_opportunity_score(
    row: dict[str, Any],
    *,
    receiving: float | None,
    rushing: float | None,
    red_zone: float | None,
) -> float | None:
    score = weighted_mean(
        [
            score_from_rate(row.get("offensive_snap_share")),
            receiving,
            rushing,
            red_zone,
        ],
        weights=[0.25, 0.35, 0.25, 0.15],
    )
    if score is not None:
        return score
    # Incomplete share denominators → null rates; use snaps/touches.
    return weighted_mean(
        [
            _score_volume(row.get("snap_count"), per_unit=1.5),
            _score_volume(row.get("touches"), per_unit=5.0),
            _score_volume(row.get("routes_run"), per_unit=2.5),
        ],
        weights=[0.40, 0.35, 0.25],
    )


def _qb_opportunity_score(
    row: dict[str, Any],
    *,
    rushing: float | None,
    red_zone: float | None,
) -> float | None:
    """
    QB opportunity ignores receiving rates (usually zero) and
    emphasizes dropbacks, designed rushes / scrambles, and snaps.
    """

    score = weighted_mean(
        [
            score_from_rate(row.get("offensive_snap_share")),
            _qb_passing_opportunity(row),
            rushing,
            red_zone,
        ],
        weights=[0.15, 0.45, 0.25, 0.15],
    )
    if score is not None:
        return score
    return weighted_mean(
        [
            _score_volume(row.get("dropbacks"), per_unit=2.5),
            _score_volume(row.get("snap_count"), per_unit=1.5),
            _score_volume(
                row.get("designed_rush_attempts"),
                per_unit=12.5,
            ),
        ],
        weights=[0.55, 0.30, 0.15],
    )


def build_player_opportunity(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    usage = raw.get("usage")
    if usage is None:
        from app.canonical.fact_player_usage import (
            get_fact_player_usage,
        )

        usage = get_fact_player_usage(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        usage = usage.copy()

    if usage.empty:
        raise ValueError(
            "Unable to build player_opportunity: no usage rows."
        )

    records: list[dict[str, Any]] = []
    for row in usage.to_dict(orient="records"):
        player_id = row.get("player_id")
        season = row.get("season")
        week = row.get("week")
        if not player_id or season is None or week is None:
            continue

        position = str(row.get("position") or "").strip().upper()
        red_zone = _red_zone_opportunity(row)

        if position == "QB":
            receiving = None
            rushing = _qb_rushing_opportunity(row)
            opportunity = _qb_opportunity_score(
                row,
                rushing=rushing,
                red_zone=red_zone,
            )
        else:
            receiving = _receiving_opportunity(row)
            rushing = _rushing_opportunity(row)
            opportunity = _skill_opportunity_score(
                row,
                receiving=receiving,
                rushing=rushing,
                red_zone=red_zone,
            )

        records.append(
            {
                "player_id": player_id,
                "season": int(season),
                "week": int(week),
                "opportunity_score": opportunity,
                "receiving_opportunity_score": receiving,
                "rushing_opportunity_score": rushing,
                "red_zone_opportunity_score": red_zone,
                "source_ids": {
                    "derived_from": "fact_player_usage",
                    "score_model": (
                        "qb" if position == "QB" else "skill"
                    ),
                },
                "resolution_key": (
                    f"{player_id}:{int(season)}:{int(week)}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build player_opportunity: no resolvable rows."
        )

    model = pd.DataFrame.from_records(records)
    model = nullify_object_frame(
        model,
        PLAYER_OPPORTUNITY_COLUMNS + ["resolution_key"],
    )
    model = model.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _CACHE, _CACHE_WITH_KEYS, _CACHE_SEASONS
    _CACHE_WITH_KEYS = model.copy()
    _CACHE_SEASONS = tuple(resolved)

    if persist:
        upsert_player_opportunity(model)

    output = finalize_output(
        model,
        PLAYER_OPPORTUNITY_COLUMNS,
        sort_cols=["season", "week", "player_id"],
    )
    _CACHE = output.copy()
    return output


def player_opportunity_count() -> int:
    return count_rows(TABLE_NAME)


def load_player_opportunity_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    return load_rows(
        TABLE_NAME,
        PLAYER_OPPORTUNITY_COLUMNS,
        seasons=seasons,
        order_by="season, week, player_id",
    )


def upsert_player_opportunity(frame: pd.DataFrame) -> None:
    upsert_rows(TABLE_NAME, PLAYER_OPPORTUNITY_COLUMNS, frame)


def get_player_opportunity(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _CACHE, _CACHE_SEASONS

    def _set_cache(frame: pd.DataFrame, key: tuple[int, ...]) -> None:
        global _CACHE, _CACHE_SEASONS
        _CACHE = frame
        _CACHE_SEASONS = key

    return get_or_build(
        seasons=seasons,
        force_refresh=force_refresh,
        persist=persist,
        cache=_CACHE,
        cache_seasons=_CACHE_SEASONS,
        set_cache=_set_cache,
        count_fn=player_opportunity_count,
        load_fn=load_player_opportunity_from_db,
        build_fn=build_player_opportunity,
    )
