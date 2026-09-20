"""
player_usage_trend — rolling opportunity signals from usage facts.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import (
    normalize_float,
    nullify_object_frame,
    prior_value_by_player,
    rolling_mean_by_player,
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

TABLE_NAME = "player_usage_trend"

PLAYER_USAGE_TREND_COLUMNS = [
    "player_id",
    "season",
    "week",
    "snap_share_3wk",
    "target_share_3wk",
    "rush_share_3wk",
    "route_participation_3wk",
    "target_share_change",
    "snap_share_change",
    "opportunity_trend",
    "source_ids",
]


def build_player_usage_trend(
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
            "Unable to build player_usage_trend: no usage rows."
        )

    frame = usage.copy()
    for column in (
        "offensive_snap_share",
        "target_share",
        "rush_share",
        "route_participation_rate",
    ):
        if column not in frame.columns:
            frame[column] = None

    frame["snap_share_3wk"] = rolling_mean_by_player(
        frame,
        value_col="offensive_snap_share",
    )
    frame["target_share_3wk"] = rolling_mean_by_player(
        frame,
        value_col="target_share",
    )
    frame["rush_share_3wk"] = rolling_mean_by_player(
        frame,
        value_col="rush_share",
    )
    frame["route_participation_3wk"] = rolling_mean_by_player(
        frame,
        value_col="route_participation_rate",
    )

    prior_target = prior_value_by_player(
        frame,
        value_col="target_share_3wk",
    )
    prior_snap = prior_value_by_player(
        frame,
        value_col="snap_share_3wk",
    )
    frame["target_share_change"] = [
        (
            None
            if normalize_float(current) is None
            or normalize_float(prior) is None
            else float(current) - float(prior)
        )
        for current, prior in zip(
            frame["target_share_3wk"],
            prior_target,
        )
    ]
    frame["snap_share_change"] = [
        (
            None
            if normalize_float(current) is None
            or normalize_float(prior) is None
            else float(current) - float(prior)
        )
        for current, prior in zip(
            frame["snap_share_3wk"],
            prior_snap,
        )
    ]
    frame["opportunity_trend"] = [
        weighted_mean([target_change, snap_change])
        for target_change, snap_change in zip(
            frame["target_share_change"],
            frame["snap_share_change"],
        )
    ]

    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        player_id = row.get("player_id")
        season = row.get("season")
        week = row.get("week")
        if not player_id or season is None or week is None:
            continue
        records.append(
            {
                "player_id": player_id,
                "season": int(season),
                "week": int(week),
                "snap_share_3wk": normalize_float(
                    row.get("snap_share_3wk")
                ),
                "target_share_3wk": normalize_float(
                    row.get("target_share_3wk")
                ),
                "rush_share_3wk": normalize_float(
                    row.get("rush_share_3wk")
                ),
                "route_participation_3wk": normalize_float(
                    row.get("route_participation_3wk")
                ),
                "target_share_change": normalize_float(
                    row.get("target_share_change")
                ),
                "snap_share_change": normalize_float(
                    row.get("snap_share_change")
                ),
                "opportunity_trend": normalize_float(
                    row.get("opportunity_trend")
                ),
                "source_ids": {
                    "derived_from": "fact_player_usage",
                },
                "resolution_key": (
                    f"{player_id}:{int(season)}:{int(week)}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build player_usage_trend: no resolvable rows."
        )

    model = pd.DataFrame.from_records(records)
    model = nullify_object_frame(
        model,
        PLAYER_USAGE_TREND_COLUMNS + ["resolution_key"],
    )
    model = model.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _CACHE, _CACHE_WITH_KEYS, _CACHE_SEASONS
    _CACHE_WITH_KEYS = model.copy()
    _CACHE_SEASONS = tuple(resolved)

    if persist:
        upsert_player_usage_trend(model)

    output = finalize_output(
        model,
        PLAYER_USAGE_TREND_COLUMNS,
        sort_cols=["season", "week", "player_id"],
    )
    _CACHE = output.copy()
    return output


def player_usage_trend_count() -> int:
    return count_rows(TABLE_NAME)


def load_player_usage_trend_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    return load_rows(
        TABLE_NAME,
        PLAYER_USAGE_TREND_COLUMNS,
        seasons=seasons,
        order_by="season, week, player_id",
    )


def upsert_player_usage_trend(frame: pd.DataFrame) -> None:
    upsert_rows(TABLE_NAME, PLAYER_USAGE_TREND_COLUMNS, frame)


def get_player_usage_trend(
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
        count_fn=player_usage_trend_count,
        load_fn=load_player_usage_trend_from_db,
        build_fn=build_player_usage_trend,
    )
