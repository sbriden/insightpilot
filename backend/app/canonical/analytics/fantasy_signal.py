"""
fantasy_signal — actionable InsightPilot fantasy signals.

Emits zero-or-more typed signals per player×week from the
proprietary fantasy profile (and supporting analytical scores).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import (
    clip,
    normalize_float,
    nullify_object_frame,
)
from app.canonical.analytics.persist import (
    count_rows,
    finalize_output,
    get_or_build,
    load_rows,
    upsert_rows,
)
from app.canonical.ids import (
    make_signal_id,
    signal_resolution_key,
)


_CACHE: pd.DataFrame | None = None
_CACHE_WITH_KEYS: pd.DataFrame | None = None
_CACHE_SEASONS: tuple[int, ...] | None = None

TABLE_NAME = "fantasy_signal"

SIGNAL_TYPES = (
    "BREAKOUT_CANDIDATE",
    "BUY_LOW",
    "SELL_HIGH",
    "START",
    "SIT",
    "WAIVER_TARGET",
    "REGRESSION_RISK",
    "OPPORTUNITY_SURGE",
    "OPPORTUNITY_DECLINE",
)

FANTASY_SIGNAL_COLUMNS = [
    "signal_id",
    "player_id",
    "season",
    "week",
    "signal_type",
    "signal_strength",
    "direction",
    "confidence",
    "supporting_metrics",
    "source_ids",
]


def _score(row: dict[str, Any], key: str) -> float | None:
    return normalize_float(row.get(key))


def _present_count(values: list[float | None]) -> int:
    return sum(1 for value in values if value is not None)


def _confidence(
    *values: float | None,
    base: float = 55.0,
) -> float:
    present = _present_count(list(values))
    return float(clip(base + (present * 5.0)) or base)


def _emit(
    *,
    player_id: str,
    season: int,
    week: int,
    signal_type: str,
    signal_strength: float,
    direction: str,
    confidence: float,
    supporting_metrics: dict[str, Any],
) -> dict[str, Any]:
    resolution = signal_resolution_key(
        player_id=player_id,
        season=season,
        week=week,
        signal_type=signal_type,
    )
    return {
        "signal_id": make_signal_id(resolution),
        "player_id": player_id,
        "season": season,
        "week": week,
        "signal_type": signal_type,
        "signal_strength": clip(signal_strength),
        "direction": direction,
        "confidence": clip(confidence),
        "supporting_metrics": supporting_metrics,
        "source_ids": {
            "derived_from": ["player_fantasy_profile"],
        },
        "resolution_key": resolution,
    }


def _signals_for_profile(
    row: dict[str, Any],
) -> list[dict[str, Any]]:
    player_id = str(row.get("player_id") or "").strip()
    season = row.get("season")
    week = row.get("week")
    if not player_id or season is None or week is None:
        return []

    season_i = int(season)
    week_i = int(week)

    production = _score(row, "production_score")
    opportunity = _score(row, "opportunity_score")
    efficiency = _score(row, "efficiency_score")
    trend = _score(row, "trend_score")
    matchup = _score(row, "matchup_score")
    environment = _score(row, "environment_score")
    risk = _score(row, "risk_score")
    value = _score(row, "fantasy_value_score")

    signals: list[dict[str, Any]] = []

    if (
        trend is not None
        and trend >= 65
        and (opportunity is None or opportunity >= 50)
    ):
        strength = 40.0 + ((trend - 65.0) * 1.5)
        if opportunity is not None:
            strength += max(0.0, opportunity - 50.0) * 0.4
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="OPPORTUNITY_SURGE",
                signal_strength=strength,
                direction="bullish",
                confidence=_confidence(
                    trend,
                    opportunity,
                    base=60.0,
                ),
                supporting_metrics={
                    "trend_score": trend,
                    "opportunity_score": opportunity,
                },
            )
        )

    if trend is not None and trend <= 35:
        strength = 40.0 + ((35.0 - trend) * 1.5)
        if opportunity is not None:
            strength += max(0.0, 50.0 - opportunity) * 0.3
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="OPPORTUNITY_DECLINE",
                signal_strength=strength,
                direction="bearish",
                confidence=_confidence(
                    trend,
                    opportunity,
                    base=60.0,
                ),
                supporting_metrics={
                    "trend_score": trend,
                    "opportunity_score": opportunity,
                },
            )
        )

    if (
        opportunity is not None
        and opportunity >= 70
        and trend is not None
        and trend >= 60
        and efficiency is not None
        and efficiency >= 55
        and (production is None or production <= 55)
    ):
        strength = (
            (opportunity - 70.0) * 1.2
            + (trend - 60.0) * 1.0
            + (efficiency - 55.0) * 0.8
            + 45.0
        )
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="BREAKOUT_CANDIDATE",
                signal_strength=strength,
                direction="bullish",
                confidence=_confidence(
                    opportunity,
                    trend,
                    efficiency,
                    production,
                    base=65.0,
                ),
                supporting_metrics={
                    "opportunity_score": opportunity,
                    "trend_score": trend,
                    "efficiency_score": efficiency,
                    "production_score": production,
                },
            )
        )

    if (
        production is not None
        and production <= 45
        and opportunity is not None
        and opportunity >= 60
        and efficiency is not None
        and efficiency >= 55
    ):
        strength = (
            (60.0 - production) * 0.8
            + (opportunity - 60.0) * 0.9
            + (efficiency - 55.0) * 0.6
            + 40.0
        )
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="BUY_LOW",
                signal_strength=strength,
                direction="bullish",
                confidence=_confidence(
                    production,
                    opportunity,
                    efficiency,
                    base=65.0,
                ),
                supporting_metrics={
                    "production_score": production,
                    "opportunity_score": opportunity,
                    "efficiency_score": efficiency,
                },
            )
        )

    if (
        production is not None
        and production >= 70
        and (
            (opportunity is not None and opportunity <= 50)
            or (trend is not None and trend <= 40)
        )
    ):
        opp_gap = (
            0.0
            if opportunity is None
            else max(0.0, 50.0 - opportunity)
        )
        trend_gap = (
            0.0
            if trend is None
            else max(0.0, 40.0 - trend)
        )
        strength = (
            (production - 70.0) * 1.0
            + opp_gap * 0.9
            + trend_gap * 0.8
            + 45.0
        )
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="SELL_HIGH",
                signal_strength=strength,
                direction="bearish",
                confidence=_confidence(
                    production,
                    opportunity,
                    trend,
                    base=65.0,
                ),
                supporting_metrics={
                    "production_score": production,
                    "opportunity_score": opportunity,
                    "trend_score": trend,
                },
            )
        )

    if (
        production is not None
        and production >= 70
        and efficiency is not None
        and efficiency <= 45
    ):
        strength = (
            (production - 70.0) * 1.0
            + (45.0 - efficiency) * 1.2
            + 45.0
        )
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="REGRESSION_RISK",
                signal_strength=strength,
                direction="bearish",
                confidence=_confidence(
                    production,
                    efficiency,
                    base=70.0,
                ),
                supporting_metrics={
                    "production_score": production,
                    "efficiency_score": efficiency,
                },
            )
        )

    if (
        value is not None
        and value >= 65
        and (matchup is None or matchup >= 55)
        and (risk is None or risk <= 40)
    ):
        strength = (value - 65.0) * 1.5 + 50.0
        if matchup is not None:
            strength += max(0.0, matchup - 55.0) * 0.5
        if risk is not None:
            strength += max(0.0, 40.0 - risk) * 0.4
        if environment is not None:
            strength += max(0.0, environment - 50.0) * 0.2
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="START",
                signal_strength=strength,
                direction="bullish",
                confidence=_confidence(
                    value,
                    matchup,
                    risk,
                    environment,
                    base=70.0,
                ),
                supporting_metrics={
                    "fantasy_value_score": value,
                    "matchup_score": matchup,
                    "risk_score": risk,
                    "environment_score": environment,
                },
            )
        )

    if (risk is not None and risk >= 70) or (
        value is not None
        and value <= 40
        and matchup is not None
        and matchup <= 45
    ):
        if risk is not None and risk >= 70:
            strength = 40.0 + (risk - 70.0) * 1.5
        else:
            strength = (
                40.0
                + (40.0 - float(value or 40.0)) * 0.8
                + (45.0 - float(matchup or 45.0)) * 0.8
            )
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="SIT",
                signal_strength=strength,
                direction="bearish",
                confidence=_confidence(
                    risk,
                    value,
                    matchup,
                    base=70.0,
                ),
                supporting_metrics={
                    "risk_score": risk,
                    "fantasy_value_score": value,
                    "matchup_score": matchup,
                },
            )
        )

    if (
        opportunity is not None
        and opportunity >= 65
        and trend is not None
        and trend >= 60
        and (production is None or production <= 50)
        and (value is None or value >= 55)
    ):
        strength = (
            (opportunity - 65.0) * 1.0
            + (trend - 60.0) * 1.0
            + 45.0
        )
        if production is not None:
            strength += max(0.0, 50.0 - production) * 0.5
        signals.append(
            _emit(
                player_id=player_id,
                season=season_i,
                week=week_i,
                signal_type="WAIVER_TARGET",
                signal_strength=strength,
                direction="bullish",
                confidence=_confidence(
                    opportunity,
                    trend,
                    production,
                    value,
                    base=60.0,
                ),
                supporting_metrics={
                    "opportunity_score": opportunity,
                    "trend_score": trend,
                    "production_score": production,
                    "fantasy_value_score": value,
                },
            )
        )

    return signals


def build_fantasy_signal(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    profiles = raw.get("profiles")
    if profiles is None:
        from app.canonical.analytics.player_fantasy_profile import (
            get_player_fantasy_profile,
        )

        profiles = get_player_fantasy_profile(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        profiles = profiles.copy()

    if profiles.empty:
        raise ValueError(
            "Unable to build fantasy_signal: no profile rows."
        )

    records: list[dict[str, Any]] = []
    for row in profiles.to_dict(orient="records"):
        records.extend(_signals_for_profile(row))

    if not records:
        raise ValueError(
            "Unable to build fantasy_signal: no signals "
            "triggered for the provided profiles."
        )

    model = pd.DataFrame.from_records(records)
    model = nullify_object_frame(
        model,
        [
            column
            for column in FANTASY_SIGNAL_COLUMNS
            + ["resolution_key"]
            if column
            not in {"supporting_metrics", "source_ids"}
        ],
    )
    model = model.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    )
    # Guard rare hash collisions within a batch.
    model = model.drop_duplicates(
        subset=["signal_id"],
        keep="last",
    ).reset_index(drop=True)

    global _CACHE, _CACHE_WITH_KEYS, _CACHE_SEASONS
    _CACHE_WITH_KEYS = model.copy()
    _CACHE_SEASONS = tuple(resolved)

    if persist:
        upsert_fantasy_signal(model)

    output = finalize_output(
        model,
        FANTASY_SIGNAL_COLUMNS,
        sort_cols=[
            "season",
            "week",
            "player_id",
            "signal_type",
        ],
    )
    _CACHE = output.copy()
    return output


def fantasy_signal_count() -> int:
    return count_rows(TABLE_NAME)


def load_fantasy_signal_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    return load_rows(
        TABLE_NAME,
        FANTASY_SIGNAL_COLUMNS,
        seasons=seasons,
        order_by="season, week, player_id, signal_type",
    )


def upsert_fantasy_signal(frame: pd.DataFrame) -> None:
    # Keep existing signal_id on resolution_key match so refreshes
    # do not rewrite the primary key into a colliding value.
    upsert_rows(
        TABLE_NAME,
        FANTASY_SIGNAL_COLUMNS,
        frame,
        immutable_on_conflict=["signal_id"],
    )


def get_fantasy_signal(
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
        count_fn=fantasy_signal_count,
        load_fn=load_fantasy_signal_from_db,
        build_fn=build_fantasy_signal,
    )
