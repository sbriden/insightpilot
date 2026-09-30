"""Clear in-memory fantasy caches after ingest / rebuild."""

from __future__ import annotations

from typing import Any


_CACHE_ATTRS = (
    "_CACHE",
    "_CACHE_WITH_KEYS",
    "_CACHE_SEASONS",
    "_DIM_TEAM_CACHE",
    "_DIM_TEAM_CACHE_WITH_KEYS",
    "_DIM_PLAYER_CACHE",
    "_DIM_PLAYER_CACHE_WITH_KEYS",
    "_DIM_GAME_CACHE",
    "_DIM_GAME_CACHE_WITH_KEYS",
    "_FACT_PLAYER_GAME_CACHE",
    "_FACT_PLAYER_GAME_CACHE_WITH_KEYS",
    "_FACT_PLAYER_GAME_CACHE_SEASONS",
    "_FACT_PLAYER_USAGE_CACHE",
    "_FACT_PLAYER_USAGE_CACHE_WITH_KEYS",
    "_FACT_PLAYER_USAGE_CACHE_SEASONS",
    "_FACT_PLAYER_EFFICIENCY_CACHE",
    "_FACT_PLAYER_EFFICIENCY_CACHE_WITH_KEYS",
    "_FACT_PLAYER_EFFICIENCY_CACHE_SEASONS",
    "_FACT_TEAM_GAME_CACHE",
    "_FACT_TEAM_GAME_CACHE_WITH_KEYS",
    "_FACT_TEAM_GAME_CACHE_SEASONS",
    "_FACT_DEFENSIVE_GAME_CACHE",
    "_FACT_DEFENSIVE_GAME_CACHE_WITH_KEYS",
    "_FACT_DEFENSIVE_GAME_CACHE_SEASONS",
    "_FACT_INJURY_CACHE",
    "_FACT_INJURY_CACHE_WITH_KEYS",
    "_FACT_INJURY_CACHE_SEASONS",
    "_FACT_DEPTH_CHART_CACHE",
    "_FACT_DEPTH_CHART_CACHE_WITH_KEYS",
    "_FACT_DEPTH_CHART_CACHE_SEASONS",
    "_FACT_MARKET_CACHE",
    "_FACT_MARKET_CACHE_WITH_KEYS",
    "_FACT_MARKET_CACHE_SEASONS",
    "_FACT_GAME_MARKET_CACHE",
    "_FACT_GAME_MARKET_CACHE_WITH_KEYS",
    "_FACT_GAME_MARKET_CACHE_SEASONS",
)


_MODULES = (
    "app.canonical.dim_team",
    "app.canonical.dim_player",
    "app.canonical.dim_game",
    "app.canonical.fact_player_game",
    "app.canonical.fact_player_usage",
    "app.canonical.fact_player_efficiency",
    "app.canonical.fact_team_game",
    "app.canonical.fact_defensive_game",
    "app.canonical.fact_injury",
    "app.canonical.fact_depth_chart",
    "app.canonical.fact_market",
    "app.canonical.fact_game_market",
    "app.canonical.analytics.player_usage_trend",
    "app.canonical.analytics.player_opportunity",
    "app.canonical.analytics.player_efficiency",
    "app.canonical.analytics.player_matchup",
    "app.canonical.analytics.player_environment",
    "app.canonical.analytics.player_fantasy_profile",
    "app.canonical.analytics.fantasy_signal",
)


def clear_all_fantasy_caches() -> int:
    """
    Drop process-local DataFrame caches so subsequent reads
    reload from Postgres after an ingest / reprocess.
    """

    import importlib

    cleared = 0
    for module_path in _MODULES:
        try:
            module = importlib.import_module(module_path)
        except Exception:
            continue
        cleared += _clear_module_caches(module)
    return cleared


def _clear_module_caches(module: Any) -> int:
    cleared = 0
    for attr in _CACHE_ATTRS:
        if not hasattr(module, attr):
            continue
        try:
            setattr(module, attr, None)
            cleared += 1
        except Exception:
            continue
    return cleared
