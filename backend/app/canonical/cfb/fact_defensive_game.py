"""fact_defensive_game — CFB points/yards allowed (from opponent offense)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.cfb._common import (
    coerce_float,
    coerce_int,
    sql_null_if_missing,
)
from app.canonical.cfb.dim_game import get_dim_game
from app.canonical.cfb.fact_team_game import (
    build_fact_team_game,
    get_fact_team_game,
)
from app.canonical.cfb.schema import (
    COLLEGE_SCHEMA,
    ensure_college_schema,
)
from app.database import engine


_CACHE: pd.DataFrame | None = None

FACT_COLUMNS = [
    "defensive_team_id",
    "opponent_team_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "points_allowed",
    "yards_allowed",
    "pass_yards_allowed",
    "rush_yards_allowed",
    "source_ids",
]


def build_fact_defensive_game(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Derive defensive allowed stats by flipping opponent team_game rows.

    When source_frames provides team_box, build fact_team_game first
    (persist=False) then flip. Otherwise load team facts from cache/DB.
    """

    if source_frames is not None and "team_box" in source_frames:
        offense = build_fact_team_game(
            seasons,
            persist=False,
            source_frames=source_frames,
        )
    else:
        offense = get_fact_team_game(
            seasons,
            force_refresh=False,
            persist=False,
        )
        if offense.empty:
            offense = build_fact_team_game(
                seasons,
                persist=False,
            )

    games = get_dim_game(
        seasons=seasons,
        force_refresh=False,
        persist=False,
    )
    if games.empty:
        raise ValueError(
            "Unable to build CFB fact_defensive_game: dim_game empty."
        )

    game_meta = {
        str(row["game_id"]): row
        for row in games.to_dict(orient="records")
    }

    records: list[dict[str, Any]] = []
    for row in offense.to_dict(orient="records"):
        game_id = str(row.get("game_id") or "")
        offense_team_id = row.get("team_id")
        meta = game_meta.get(game_id)
        if not meta or not offense_team_id:
            continue

        home = meta.get("home_team_id")
        away = meta.get("away_team_id")
        if offense_team_id == home:
            defensive_team_id = away
        elif offense_team_id == away:
            defensive_team_id = home
        else:
            continue

        if not defensive_team_id:
            continue

        # Pass/rush yards not always on team_game; leave null when absent.
        records.append(
            {
                "defensive_team_id": defensive_team_id,
                "opponent_team_id": offense_team_id,
                "game_id": game_id,
                "season": coerce_int(row.get("season")),
                "week": coerce_int(row.get("week")),
                "season_type": row.get("season_type"),
                "points_allowed": coerce_int(row.get("points")),
                "yards_allowed": coerce_float(row.get("yards")),
                "pass_yards_allowed": None,
                "rush_yards_allowed": None,
                "source_ids": {
                    "derived_from": "fact_team_game",
                },
                "resolution_key": f"{defensive_team_id}:{game_id}",
            }
        )

    if not records:
        raise ValueError(
            "Unable to build CFB fact_defensive_game: no paired rows."
        )

    fact = pd.DataFrame.from_records(records)
    fact = fact.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    if persist:
        upsert_fact_defensive_game(fact)

    output = fact[FACT_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    global _CACHE
    _CACHE = output.copy()
    return output


def get_fact_defensive_game(
    seasons: list[int],
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _CACHE
    if (
        not force_refresh
        and _CACHE is not None
        and not _CACHE.empty
    ):
        allowed = {int(s) for s in seasons}
        cached = _CACHE[
            _CACHE["season"].map(
                lambda value: (
                    int(value) in allowed
                    if value is not None
                    else False
                )
            )
        ]
        if not cached.empty:
            return cached.copy()

    if not force_refresh:
        frame = load_fact_defensive_game_from_db(seasons)
        if not frame.empty:
            return frame

    return build_fact_defensive_game(seasons, persist=persist)


def load_fact_defensive_game_from_db(
    seasons: list[int],
) -> pd.DataFrame:
    ensure_college_schema()
    cols = (
        ", ".join(FACT_COLUMNS[:-1])
        + ", source_ids::text AS source_ids"
    )
    query = text(
        f"""
        SELECT {cols}
        FROM {COLLEGE_SCHEMA}.fact_defensive_game
        WHERE season = ANY(:seasons)
        """
    )
    with engine.connect() as connection:
        return pd.read_sql(
            query,
            connection,
            params={"seasons": [int(s) for s in seasons]},
        )


def upsert_fact_defensive_game(fact: pd.DataFrame) -> None:
    if fact.empty:
        return

    ensure_college_schema()
    statement = text(
        f"""
        INSERT INTO {COLLEGE_SCHEMA}.fact_defensive_game (
            defensive_team_id, opponent_team_id, game_id,
            season, week, season_type,
            points_allowed, yards_allowed,
            pass_yards_allowed, rush_yards_allowed,
            source_ids, resolution_key, updated_at
        ) VALUES (
            :defensive_team_id, :opponent_team_id, :game_id,
            :season, :week, :season_type,
            :points_allowed, :yards_allowed,
            :pass_yards_allowed, :rush_yards_allowed,
            CAST(:source_ids AS JSONB), :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            opponent_team_id = EXCLUDED.opponent_team_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            points_allowed = EXCLUDED.points_allowed,
            yards_allowed = EXCLUDED.yards_allowed,
            pass_yards_allowed = EXCLUDED.pass_yards_allowed,
            rush_yards_allowed = EXCLUDED.rush_yards_allowed,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in fact.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(source_ids, sort_keys=True)
        rows.append(
            {
                key: sql_null_if_missing(record.get(key))
                for key in (
                    "defensive_team_id",
                    "opponent_team_id",
                    "game_id",
                    "season",
                    "week",
                    "season_type",
                    "points_allowed",
                    "yards_allowed",
                    "pass_yards_allowed",
                    "rush_yards_allowed",
                )
            }
            | {
                "source_ids": source_ids,
                "resolution_key": record["resolution_key"],
            }
        )

    batch_size = 500
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def clear_fact_defensive_game_cache() -> None:
    global _CACHE
    _CACHE = None
