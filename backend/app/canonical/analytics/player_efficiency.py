"""
player_efficiency — weekly efficiency intelligence scores.

Distinct from fact_player_efficiency (raw per-game rates).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import (
    clip,
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

TABLE_NAME = "player_efficiency"

PLAYER_EFFICIENCY_COLUMNS = [
    "player_id",
    "season",
    "week",
    "efficiency_score",
    "receiving_efficiency",
    "rushing_efficiency",
    "source_ids",
]


def _ypc_score(value: Any) -> float | None:
    yards = normalize_float(value)
    if yards is None:
        return None
    # ~2.5 ypc → 25, 4.0 → 40, 5.5 → 55, clip 0–100
    return clip(yards * 10.0)


def _ypt_score(value: Any) -> float | None:
    yards = normalize_float(value)
    if yards is None:
        return None
    return clip(yards * 8.0)


def _yprr_score(value: Any) -> float | None:
    yards = normalize_float(value)
    if yards is None:
        return None
    return clip(yards * 25.0)


def _epa_score(value: Any) -> float | None:
    epa = normalize_float(value)
    if epa is None:
        return None
    # Center near 0 EPA/attempt around 50.
    return clip(50.0 + (epa * 25.0))


def build_player_efficiency(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    efficiency = raw.get("efficiency")
    if efficiency is None:
        from app.canonical.fact_player_efficiency import (
            get_fact_player_efficiency,
        )

        efficiency = get_fact_player_efficiency(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        efficiency = efficiency.copy()

    if efficiency.empty:
        raise ValueError(
            "Unable to build player_efficiency: no efficiency rows."
        )

    records: list[dict[str, Any]] = []
    for row in efficiency.to_dict(orient="records"):
        player_id = row.get("player_id")
        season = row.get("season")
        week = row.get("week")
        if not player_id or season is None or week is None:
            continue

        receiving = weighted_mean(
            [
                _ypt_score(row.get("yards_per_target")),
                _yprr_score(row.get("yards_per_route_run")),
                score_from_rate(row.get("catch_rate")),
            ],
            weights=[0.4, 0.35, 0.25],
        )
        rushing = weighted_mean(
            [
                _ypc_score(row.get("yards_per_carry")),
                _epa_score(row.get("rush_epa_per_attempt")),
            ],
            weights=[0.55, 0.45],
        )
        overall = weighted_mean(
            [
                receiving,
                rushing,
                _epa_score(row.get("pass_epa_per_dropback")),
                score_from_rate(row.get("td_rate"), scale=200.0),
            ],
            weights=[0.35, 0.35, 0.2, 0.1],
        )

        records.append(
            {
                "player_id": player_id,
                "season": int(season),
                "week": int(week),
                "efficiency_score": overall,
                "receiving_efficiency": receiving,
                "rushing_efficiency": rushing,
                "source_ids": {
                    "derived_from": "fact_player_efficiency",
                },
                "resolution_key": (
                    f"{player_id}:{int(season)}:{int(week)}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build player_efficiency: no resolvable rows."
        )

    model = pd.DataFrame.from_records(records)
    model = nullify_object_frame(
        model,
        PLAYER_EFFICIENCY_COLUMNS + ["resolution_key"],
    )
    model = model.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _CACHE, _CACHE_WITH_KEYS, _CACHE_SEASONS
    _CACHE_WITH_KEYS = model.copy()
    _CACHE_SEASONS = tuple(resolved)

    if persist:
        upsert_player_efficiency(model)

    output = finalize_output(
        model,
        PLAYER_EFFICIENCY_COLUMNS,
        sort_cols=["season", "week", "player_id"],
    )
    _CACHE = output.copy()
    return output


def player_efficiency_count() -> int:
    return count_rows(TABLE_NAME)


def load_player_efficiency_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    return load_rows(
        TABLE_NAME,
        PLAYER_EFFICIENCY_COLUMNS,
        seasons=seasons,
        order_by="season, week, player_id",
    )


def upsert_player_efficiency(frame: pd.DataFrame) -> None:
    upsert_rows(TABLE_NAME, PLAYER_EFFICIENCY_COLUMNS, frame)


def get_player_efficiency(
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
        count_fn=player_efficiency_count,
        load_fn=load_player_efficiency_from_db,
        build_fn=build_player_efficiency,
    )
