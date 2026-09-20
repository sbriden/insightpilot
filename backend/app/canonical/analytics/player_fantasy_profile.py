"""
player_fantasy_profile — InsightPilot proprietary weekly profile.

Composes analytical-layer scores into a single player×week
intelligence row. This is where InsightPilot gets proprietary.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import (
    clip,
    normalize_float,
    nullify_object_frame,
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

TABLE_NAME = "player_fantasy_profile"

PLAYER_FANTASY_PROFILE_COLUMNS = [
    "player_id",
    "season",
    "week",
    "production_score",
    "opportunity_score",
    "efficiency_score",
    "trend_score",
    "matchup_score",
    "environment_score",
    "risk_score",
    "fantasy_value_score",
    "source_ids",
]


def _key(
    player_id: Any,
    season: Any,
    week: Any,
) -> tuple[str, int, int] | None:
    if not player_id or season is None or week is None:
        return None
    try:
        return (str(player_id), int(season), int(week))
    except (TypeError, ValueError):
        return None


def _index_by_player_week(
    frame: pd.DataFrame,
) -> dict[tuple[str, int, int], dict[str, Any]]:
    if frame is None or frame.empty:
        return {}
    lookup: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in frame.to_dict(orient="records"):
        key = _key(
            row.get("player_id"),
            row.get("season"),
            row.get("week"),
        )
        if key:
            lookup[key] = row
    return lookup


def _ppr_points(row: dict[str, Any]) -> float | None:
    from app.analysis.insights.fantasy_scoring import (
        fantasy_points_from_row,
    )

    return fantasy_points_from_row(row, scoring="ppr")


def _production_score(row: dict[str, Any]) -> float | None:
    points = _ppr_points(row)
    if points is None:
        return None

    # Kickers typically land in the 6–12 FPTS band. Skill-position
    # scaling (×3) leaves even strong kickers near "Weak".
    kicking = any(
        normalize_float(row.get(column)) not in (None, 0.0)
        for column in (
            "fg_made",
            "pat_made",
            "fg_made_0_19",
            "fg_made_20_29",
            "fg_made_30_39",
            "fg_made_40_49",
            "fg_made_50_59",
            "fg_made_60_",
        )
    )
    skill = any(
        normalize_float(row.get(column)) not in (None, 0.0)
        for column in (
            "pass_yards",
            "rush_yards",
            "receiving_yards",
            "receptions",
            "pass_tds",
            "rush_tds",
            "receiving_tds",
        )
    )
    multiplier = 6.0 if kicking and not skill else 3.0
    # Kicker: ~10 FPTS → 60; skill: ~20 PPR → 60
    return clip(points * multiplier)


def _trend_score(opportunity_trend: Any) -> float | None:
    change = normalize_float(opportunity_trend)
    if change is None:
        return None
    # ±0.10 share change → ±20 around 50
    return clip(50.0 + (change * 200.0))


def _injury_risk(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    status = str(row.get("game_status") or "").strip().lower()
    expected = row.get("is_expected_to_play")

    if status in {"out"}:
        return 95.0
    if status in {"doubtful"}:
        return 85.0
    if status in {"questionable"}:
        return 55.0
    if expected is False:
        return 80.0
    if expected is True:
        return 15.0
    if status:
        return 25.0
    return None


def _usage_volatility_risk(
    trends: dict[str, Any] | None,
) -> float | None:
    if not trends:
        return None
    snap_change = normalize_float(trends.get("snap_share_change"))
    target_change = normalize_float(
        trends.get("target_share_change")
    )
    magnitudes: list[float] = []
    if snap_change is not None:
        magnitudes.append(abs(snap_change))
    if target_change is not None:
        magnitudes.append(abs(target_change))
    if not magnitudes:
        return None
    # 0.05 abs change → ~25 risk, 0.20 → 100
    return clip(sum(magnitudes) / len(magnitudes) * 500.0)


def _risk_score(
    injury: dict[str, Any] | None,
    trends: dict[str, Any] | None,
) -> float | None:
    return weighted_mean(
        [
            _injury_risk(injury),
            _usage_volatility_risk(trends),
        ],
        weights=[0.7, 0.3],
    )


def _fantasy_value_score(
    *,
    production: float | None,
    opportunity: float | None,
    efficiency: float | None,
    trend: float | None,
    matchup: float | None,
    environment: float | None,
    risk: float | None,
) -> float | None:
    safety = None if risk is None else clip(100.0 - risk)
    return weighted_mean(
        [
            production,
            opportunity,
            efficiency,
            trend,
            matchup,
            environment,
            safety,
        ],
        weights=[0.20, 0.22, 0.15, 0.10, 0.13, 0.10, 0.10],
    )


def _load_component(
    raw: dict[str, pd.DataFrame],
    key: str,
    getter_path: tuple[str, str],
    seasons: list[int],
) -> pd.DataFrame:
    if key in raw and raw[key] is not None:
        return raw[key].copy()

    module_name, getter_name = getter_path
    module = __import__(module_name, fromlist=[getter_name])
    getter = getattr(module, getter_name)
    return getter(
        seasons,
        force_refresh=False,
        persist=False,
    )


def build_player_fantasy_profile(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    production = _load_component(
        raw,
        "production",
        (
            "app.canonical.fact_player_game",
            "get_fact_player_game",
        ),
        resolved,
    )
    opportunity = _load_component(
        raw,
        "opportunity",
        (
            "app.canonical.analytics.player_opportunity",
            "get_player_opportunity",
        ),
        resolved,
    )
    efficiency = _load_component(
        raw,
        "efficiency",
        (
            "app.canonical.analytics.player_efficiency",
            "get_player_efficiency",
        ),
        resolved,
    )
    trends = _load_component(
        raw,
        "trends",
        (
            "app.canonical.analytics.player_usage_trend",
            "get_player_usage_trend",
        ),
        resolved,
    )
    matchups = _load_component(
        raw,
        "matchups",
        (
            "app.canonical.analytics.player_matchup",
            "get_player_matchup",
        ),
        resolved,
    )
    environments = _load_component(
        raw,
        "environments",
        (
            "app.canonical.analytics.player_environment",
            "get_player_environment",
        ),
        resolved,
    )

    injuries = raw.get("injuries")
    if injuries is None:
        try:
            from app.canonical.fact_injury import (
                get_fact_injury,
            )

            injuries = get_fact_injury(
                resolved,
                force_refresh=False,
                persist=False,
            )
        except Exception:
            injuries = pd.DataFrame()
    else:
        injuries = injuries.copy()

    if production.empty and opportunity.empty:
        raise ValueError(
            "Unable to build player_fantasy_profile: no "
            "production or opportunity rows."
        )

    production_lookup = _index_by_player_week(production)
    opportunity_lookup = _index_by_player_week(opportunity)
    efficiency_lookup = _index_by_player_week(efficiency)
    trend_lookup = _index_by_player_week(trends)
    matchup_lookup = _index_by_player_week(matchups)
    environment_lookup = _index_by_player_week(environments)
    injury_lookup = _index_by_player_week(injuries)

    keys = sorted(
        set(production_lookup)
        | set(opportunity_lookup)
        | set(efficiency_lookup)
        | set(trend_lookup)
        | set(matchup_lookup)
        | set(environment_lookup)
    )
    if not keys:
        raise ValueError(
            "Unable to build player_fantasy_profile: no "
            "resolvable player×week keys."
        )

    records: list[dict[str, Any]] = []
    for player_id, season, week in keys:
        key = (player_id, season, week)
        prod_row = production_lookup.get(key, {})
        opp_row = opportunity_lookup.get(key, {})
        eff_row = efficiency_lookup.get(key, {})
        trend_row = trend_lookup.get(key, {})
        match_row = matchup_lookup.get(key, {})
        env_row = environment_lookup.get(key, {})
        injury_row = injury_lookup.get(key)

        production_score = _production_score(prod_row)
        opportunity_score = normalize_float(
            opp_row.get("opportunity_score")
        )
        efficiency_score = normalize_float(
            eff_row.get("efficiency_score")
        )
        trend_score = _trend_score(
            trend_row.get("opportunity_trend")
        )
        matchup_score = normalize_float(
            match_row.get("matchup_score")
        )
        environment_score = normalize_float(
            env_row.get("game_environment_score")
        )
        risk_score = _risk_score(injury_row, trend_row)
        fantasy_value = _fantasy_value_score(
            production=production_score,
            opportunity=opportunity_score,
            efficiency=efficiency_score,
            trend=trend_score,
            matchup=matchup_score,
            environment=environment_score,
            risk=risk_score,
        )

        records.append(
            {
                "player_id": player_id,
                "season": season,
                "week": week,
                "production_score": production_score,
                "opportunity_score": opportunity_score,
                "efficiency_score": efficiency_score,
                "trend_score": trend_score,
                "matchup_score": matchup_score,
                "environment_score": environment_score,
                "risk_score": risk_score,
                "fantasy_value_score": fantasy_value,
                "source_ids": {
                    "derived_from": [
                        "fact_player_game",
                        "player_opportunity",
                        "player_efficiency",
                        "player_usage_trend",
                        "player_matchup",
                        "player_environment",
                        "fact_injury",
                    ],
                },
                "resolution_key": (
                    f"{player_id}:{season}:{week}"
                ),
            }
        )

    model = pd.DataFrame.from_records(records)
    model = nullify_object_frame(
        model,
        PLAYER_FANTASY_PROFILE_COLUMNS + ["resolution_key"],
    )
    model = model.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _CACHE, _CACHE_WITH_KEYS, _CACHE_SEASONS
    _CACHE_WITH_KEYS = model.copy()
    _CACHE_SEASONS = tuple(resolved)

    if persist:
        upsert_player_fantasy_profile(model)

    output = finalize_output(
        model,
        PLAYER_FANTASY_PROFILE_COLUMNS,
        sort_cols=["season", "week", "player_id"],
    )
    _CACHE = output.copy()
    return output


def player_fantasy_profile_count() -> int:
    return count_rows(TABLE_NAME)


def load_player_fantasy_profile_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    return load_rows(
        TABLE_NAME,
        PLAYER_FANTASY_PROFILE_COLUMNS,
        seasons=seasons,
        order_by="season, week, player_id",
    )


def upsert_player_fantasy_profile(frame: pd.DataFrame) -> None:
    upsert_rows(
        TABLE_NAME,
        PLAYER_FANTASY_PROFILE_COLUMNS,
        frame,
    )


def get_player_fantasy_profile(
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
        count_fn=player_fantasy_profile_count,
        load_fn=load_player_fantasy_profile_from_db,
        build_fn=build_player_fantasy_profile,
    )
