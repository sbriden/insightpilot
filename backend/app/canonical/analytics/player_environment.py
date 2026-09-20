"""
player_environment — game environment / script expectations.
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

TABLE_NAME = "player_environment"

PLAYER_ENVIRONMENT_COLUMNS = [
    "player_id",
    "season",
    "week",
    "game_environment_score",
    "team_total",
    "pace_expectation",
    "game_script_expectation",
    "source_ids",
]


def _team_implied_total(
    team_id: Any,
    home_team_id: Any,
    away_team_id: Any,
    home_implied: Any,
    away_implied: Any,
) -> float | None:
    if not team_id:
        return None
    if team_id == home_team_id:
        return normalize_float(home_implied)
    if team_id == away_team_id:
        return normalize_float(away_implied)
    return None


def _spread_for_team(
    team_id: Any,
    home_team_id: Any,
    away_team_id: Any,
    spread: Any,
) -> float | None:
    """Return spread from the team's perspective (negative = favorite)."""
    line = normalize_float(spread)
    if line is None or not team_id:
        return None
    # nflverse spread_line is typically home-team spread.
    if team_id == home_team_id:
        return line
    if team_id == away_team_id:
        return -line
    return None


def _script_score(team_spread: float | None) -> float | None:
    if team_spread is None:
        return None
    # Favorite (negative spread) → positive script for rushers.
    # Underdog → pass-catching game-script lean.
    # Map -14..+14 onto ~20..80 centered at 50.
    return clip(50.0 - (team_spread * 2.5))


def _pace_score(pace: Any) -> float | None:
    value = normalize_float(pace)
    if value is None:
        return None
    # Pace is often plays/game (~55–75). Map around 65 → 50.
    return clip(50.0 + ((value - 65.0) * 3.0))


def _total_score(team_total: float | None) -> float | None:
    if team_total is None:
        return None
    # ~17 pts → 40, 24 → 55, 30 → 70
    return clip(team_total * 2.2)


def build_player_environment(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    players = raw.get("players")
    if players is None:
        from app.canonical.fact_player_game import (
            get_fact_player_game,
        )

        players = get_fact_player_game(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        players = players.copy()

    games = raw.get("games")
    if games is None:
        from app.canonical.dim_game import get_dim_game

        games = get_dim_game(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        games = games.copy()

    markets = raw.get("markets")
    if markets is None:
        from app.canonical.fact_game_market import (
            get_fact_game_market,
        )

        markets = get_fact_game_market(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        markets = markets.copy()

    team_games = raw.get("team_games")
    if team_games is None:
        from app.canonical.fact_team_game import (
            get_fact_team_game,
        )

        team_games = get_fact_team_game(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        team_games = team_games.copy()

    if players.empty:
        raise ValueError(
            "Unable to build player_environment: no player rows."
        )
    if games.empty:
        raise ValueError(
            "Unable to build player_environment: no game rows."
        )

    game_lookup = {
        row["game_id"]: row
        for row in games.to_dict(orient="records")
        if row.get("game_id")
    }

    market_lookup: dict[str, dict[str, Any]] = {}
    if not markets.empty:
        # Prefer the first source per game_id.
        for row in markets.to_dict(orient="records"):
            game_id = row.get("game_id")
            if game_id and game_id not in market_lookup:
                market_lookup[game_id] = row

    pace_lookup: dict[tuple[Any, Any, Any], float | None] = {}
    if not team_games.empty:
        working = team_games.copy()
        working = working.sort_values(
            ["team_id", "season", "week"],
            kind="mergesort",
        )
        if "pace" not in working.columns:
            working["pace"] = None
        working["pace"] = pd.to_numeric(
            working["pace"],
            errors="coerce",
        )
        working["prior_pace"] = working.groupby(
            "team_id",
            sort=False,
        )["pace"].transform(
            lambda series: series.shift(1).rolling(
                window=3,
                min_periods=1,
            ).mean()
        )
        for row in working.to_dict(orient="records"):
            pace_lookup[
                (row.get("team_id"), row.get("season"), row.get("week"))
            ] = normalize_float(row.get("prior_pace"))

    records: list[dict[str, Any]] = []
    for row in players.to_dict(orient="records"):
        player_id = row.get("player_id")
        season = row.get("season")
        week = row.get("week")
        game_id = row.get("game_id")
        team_id = row.get("team_id")
        if (
            not player_id
            or season is None
            or week is None
            or not game_id
        ):
            continue

        game = game_lookup.get(game_id)
        if not game:
            continue

        market = market_lookup.get(game_id, {})
        team_total = _team_implied_total(
            team_id,
            game.get("home_team_id"),
            game.get("away_team_id"),
            market.get("home_implied_total"),
            market.get("away_implied_total"),
        )
        if team_total is None:
            over_under = normalize_float(market.get("over_under"))
            if over_under is not None:
                team_total = over_under / 2.0

        team_spread = _spread_for_team(
            team_id,
            game.get("home_team_id"),
            game.get("away_team_id"),
            market.get("spread"),
        )
        script = _script_score(team_spread)
        pace = pace_lookup.get(
            (team_id, int(season), int(week))
        )
        pace_expectation = _pace_score(pace)

        environment = weighted_mean(
            [
                _total_score(team_total),
                pace_expectation,
                script,
            ],
            weights=[0.45, 0.25, 0.3],
        )

        records.append(
            {
                "player_id": player_id,
                "season": int(season),
                "week": int(week),
                "game_environment_score": environment,
                "team_total": team_total,
                "pace_expectation": pace_expectation,
                "game_script_expectation": script,
                "source_ids": {
                    "derived_from": [
                        "fact_player_game",
                        "dim_game",
                        "fact_game_market",
                        "fact_team_game",
                    ],
                    "game_id": game_id,
                    "team_id": team_id,
                },
                "resolution_key": (
                    f"{player_id}:{int(season)}:{int(week)}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build player_environment: no resolvable rows."
        )

    model = pd.DataFrame.from_records(records)
    model = nullify_object_frame(
        model,
        PLAYER_ENVIRONMENT_COLUMNS + ["resolution_key"],
    )
    model = model.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _CACHE, _CACHE_WITH_KEYS, _CACHE_SEASONS
    _CACHE_WITH_KEYS = model.copy()
    _CACHE_SEASONS = tuple(resolved)

    if persist:
        upsert_player_environment(model)

    output = finalize_output(
        model,
        PLAYER_ENVIRONMENT_COLUMNS,
        sort_cols=["season", "week", "player_id"],
    )
    _CACHE = output.copy()
    return output


def player_environment_count() -> int:
    return count_rows(TABLE_NAME)


def load_player_environment_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    return load_rows(
        TABLE_NAME,
        PLAYER_ENVIRONMENT_COLUMNS,
        seasons=seasons,
        order_by="season, week, player_id",
    )


def upsert_player_environment(frame: pd.DataFrame) -> None:
    upsert_rows(TABLE_NAME, PLAYER_ENVIRONMENT_COLUMNS, frame)


def get_player_environment(
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
        count_fn=player_environment_count,
        load_fn=load_player_environment_from_db,
        build_fn=build_player_environment,
    )
