"""
player_matchup — opponent-relative fantasy matchup scores.
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

TABLE_NAME = "player_matchup"

PLAYER_MATCHUP_COLUMNS = [
    "player_id",
    "season",
    "week",
    "matchup_score",
    "pass_matchup_score",
    "rush_matchup_score",
    "receiving_matchup_score",
    "source_ids",
]


def _opponent_team_id(
    team_id: Any,
    home_team_id: Any,
    away_team_id: Any,
) -> str | None:
    if not team_id:
        return None
    if team_id == home_team_id:
        return away_team_id or None
    if team_id == away_team_id:
        return home_team_id or None
    return None


def _epa_allowed_score(value: Any) -> float | None:
    epa = normalize_float(value)
    if epa is None:
        return None
    # Higher EPA allowed → easier matchup. Center 0 at 50.
    return clip(50.0 + (epa * 40.0))


def _yards_allowed_score(
    value: Any,
    *,
    scale: float,
) -> float | None:
    yards = normalize_float(value)
    if yards is None:
        return None
    return clip(yards * scale)


def _rate_allowed_score(value: Any) -> float | None:
    rate = normalize_float(value)
    if rate is None:
        return None
    return clip(rate * 100.0)


def _pressure_ease_score(value: Any) -> float | None:
    rate = normalize_float(value)
    if rate is None:
        return None
    # High pressure is harder for passers → invert.
    return clip(100.0 - (rate * 100.0))


def _prior_defensive_averages(
    defense: pd.DataFrame,
) -> pd.DataFrame:
    if defense.empty:
        return pd.DataFrame()

    working = defense.copy()
    working = working.sort_values(
        ["defensive_team_id", "season", "week"],
        kind="mergesort",
    )

    metric_cols = [
        "pass_epa_allowed",
        "rush_epa_allowed",
        "pass_yards_allowed",
        "rush_yards_allowed",
        "receiving_yards_allowed",
        "targets_allowed",
        "pressure_rate",
        "sack_rate",
    ]
    for column in metric_cols:
        if column not in working.columns:
            working[column] = None
        working[column] = pd.to_numeric(
            working[column],
            errors="coerce",
        )

    grouped = working.groupby(
        "defensive_team_id",
        sort=False,
    )
    for column in metric_cols:
        working[f"prior_{column}"] = grouped[column].transform(
            lambda series: series.shift(1).rolling(
                window=3,
                min_periods=1,
            ).mean()
        )

    return working


def build_player_matchup(
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

    defense = raw.get("defense")
    if defense is None:
        from app.canonical.fact_defensive_game import (
            get_fact_defensive_game,
        )

        defense = get_fact_defensive_game(
            resolved,
            force_refresh=False,
            persist=False,
        )
    else:
        defense = defense.copy()

    if players.empty:
        raise ValueError(
            "Unable to build player_matchup: no player rows."
        )
    if games.empty:
        raise ValueError(
            "Unable to build player_matchup: no game rows."
        )

    game_lookup = {
        row["game_id"]: row
        for row in games.to_dict(orient="records")
        if row.get("game_id")
    }
    defense_priors = _prior_defensive_averages(defense)
    defense_lookup: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    for row in defense_priors.to_dict(orient="records"):
        key = (
            row.get("defensive_team_id"),
            row.get("season"),
            row.get("week"),
        )
        defense_lookup[key] = row

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

        opponent_id = _opponent_team_id(
            team_id,
            game.get("home_team_id"),
            game.get("away_team_id"),
        )
        if not opponent_id:
            continue

        defense_row = defense_lookup.get(
            (opponent_id, int(season), int(week)),
            {},
        )

        pass_matchup = weighted_mean(
            [
                _epa_allowed_score(
                    defense_row.get("prior_pass_epa_allowed")
                ),
                _yards_allowed_score(
                    defense_row.get("prior_pass_yards_allowed"),
                    scale=0.25,
                ),
                _pressure_ease_score(
                    defense_row.get("prior_pressure_rate")
                ),
                _pressure_ease_score(
                    defense_row.get("prior_sack_rate")
                ),
            ],
            weights=[0.35, 0.25, 0.2, 0.2],
        )
        rush_matchup = weighted_mean(
            [
                _epa_allowed_score(
                    defense_row.get("prior_rush_epa_allowed")
                ),
                _yards_allowed_score(
                    defense_row.get("prior_rush_yards_allowed"),
                    scale=0.4,
                ),
            ],
            weights=[0.55, 0.45],
        )
        receiving_matchup = weighted_mean(
            [
                _yards_allowed_score(
                    defense_row.get(
                        "prior_receiving_yards_allowed"
                    ),
                    scale=0.3,
                ),
                _rate_allowed_score(
                    # targets_allowed is a count; normalize lightly
                    None
                    if normalize_float(
                        defense_row.get("prior_targets_allowed")
                    )
                    is None
                    else min(
                        1.0,
                        float(
                            defense_row.get(
                                "prior_targets_allowed"
                            )
                        )
                        / 40.0,
                    )
                ),
                _epa_allowed_score(
                    defense_row.get("prior_pass_epa_allowed")
                ),
            ],
            weights=[0.4, 0.3, 0.3],
        )
        matchup = weighted_mean(
            [pass_matchup, rush_matchup, receiving_matchup],
            weights=[0.3, 0.3, 0.4],
        )

        records.append(
            {
                "player_id": player_id,
                "season": int(season),
                "week": int(week),
                "matchup_score": matchup,
                "pass_matchup_score": pass_matchup,
                "rush_matchup_score": rush_matchup,
                "receiving_matchup_score": receiving_matchup,
                "source_ids": {
                    "derived_from": [
                        "fact_player_game",
                        "dim_game",
                        "fact_defensive_game",
                    ],
                    "opponent_team_id": opponent_id,
                    "game_id": game_id,
                },
                "resolution_key": (
                    f"{player_id}:{int(season)}:{int(week)}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build player_matchup: no resolvable rows."
        )

    model = pd.DataFrame.from_records(records)
    model = nullify_object_frame(
        model,
        PLAYER_MATCHUP_COLUMNS + ["resolution_key"],
    )
    model = model.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _CACHE, _CACHE_WITH_KEYS, _CACHE_SEASONS
    _CACHE_WITH_KEYS = model.copy()
    _CACHE_SEASONS = tuple(resolved)

    if persist:
        upsert_player_matchup(model)

    output = finalize_output(
        model,
        PLAYER_MATCHUP_COLUMNS,
        sort_cols=["season", "week", "player_id"],
    )
    _CACHE = output.copy()
    return output


def player_matchup_count() -> int:
    return count_rows(TABLE_NAME)


def load_player_matchup_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    return load_rows(
        TABLE_NAME,
        PLAYER_MATCHUP_COLUMNS,
        seasons=seasons,
        order_by="season, week, player_id",
    )


def upsert_player_matchup(frame: pd.DataFrame) -> None:
    upsert_rows(TABLE_NAME, PLAYER_MATCHUP_COLUMNS, frame)


def get_player_matchup(
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
        count_fn=player_matchup_count,
        load_fn=load_player_matchup_from_db,
        build_fn=build_player_matchup,
    )
