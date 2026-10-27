"""fact_player_game — CFB player box-score production."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.cfb._common import (
    coerce_int,
    first_present,
    normalize_text,
    sql_null_if_missing,
    to_pandas,
)
from app.canonical.cfb.dim_game import (
    game_id_lookup_from_dim,
    get_dim_game,
)
from app.canonical.cfb.dim_player import (
    get_dim_player,
    player_id_lookup_from_dim,
)
from app.canonical.cfb.dim_team import (
    get_dim_team,
    resolve_team_id,
    team_id_lookup_from_dim,
)
from app.canonical.cfb.schema import (
    COLLEGE_SCHEMA,
    ensure_college_schema,
)
from app.database import engine


_CACHE: pd.DataFrame | None = None

FACT_COLUMNS = [
    "player_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "team_id",
    "pass_attempts",
    "pass_completions",
    "pass_yards",
    "pass_tds",
    "interceptions",
    "rush_attempts",
    "rush_yards",
    "rush_tds",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "source_ids",
]


def _load_source_frames(
    seasons: list[int],
) -> dict[str, pd.DataFrame]:
    from sportsdataverse.cfb import load_cfb_player_box

    try:
        box = to_pandas(
            load_cfb_player_box(
                seasons=seasons,
                return_as_pandas=True,
            )
        )
    except TypeError:
        box = to_pandas(load_cfb_player_box(seasons=seasons))
    except Exception:
        # Fallback name variants across sportsdataverse versions.
        from sportsdataverse import cfb as cfb_mod

        loader = getattr(cfb_mod, "load_cfb_player_boxscore", None)
        if loader is None:
            raise
        try:
            box = to_pandas(
                loader(seasons=seasons, return_as_pandas=True)
            )
        except TypeError:
            box = to_pandas(loader(seasons=seasons))
    return {"player_box": box}


def build_fact_player_game(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    raw = source_frames or _load_source_frames(seasons)
    box = raw.get("player_box", pd.DataFrame()).copy()
    if box.empty:
        raise ValueError(
            "Unable to build CFB fact_player_game: empty player box."
        )

    player_lookup = player_id_lookup_from_dim(
        get_dim_player(force_refresh=False, persist=False)
    )
    game_lookup = game_id_lookup_from_dim(
        get_dim_game(
            seasons=seasons,
            force_refresh=False,
            persist=False,
        )
    )
    team_lookup = team_id_lookup_from_dim(
        get_dim_team(force_refresh=False, persist=False)
    )

    records: list[dict[str, Any]] = []
    for row in box.to_dict(orient="records"):
        athlete = normalize_text(
            first_present(
                row,
                "athlete_id",
                "player_id",
                "id",
                "espn_id",
            )
        )
        player_id = player_lookup.get(athlete) if athlete else None
        if not player_id:
            continue

        external_game = normalize_text(
            first_present(row, "game_id", "espn_game_id")
        )
        game_id = (
            game_lookup.get(external_game)
            if external_game
            else None
        )
        if not game_id:
            continue

        team_id = resolve_team_id(
            espn_team_id=first_present(
                row, "team_id", "espn_team_id"
            ),
            team_abbreviation=first_present(
                row, "team_abbreviation", "team", "team_abbr"
            ),
            team_name=first_present(
                row, "team_name", "school"
            ),
            team_id_lookup=team_lookup,
        )

        season = coerce_int(first_present(row, "season", "year"))
        week = coerce_int(first_present(row, "week"))
        resolution_key = f"{player_id}:{game_id}"

        records.append(
            {
                "player_id": player_id,
                "game_id": game_id,
                "season": season,
                "week": week,
                "season_type": normalize_text(
                    first_present(row, "season_type", "game_type")
                ),
                "team_id": team_id,
                "pass_attempts": coerce_int(
                    first_present(
                        row,
                        "pass_attempts",
                        "passing_attempts",
                        "completions_attempts",
                    )
                ),
                "pass_completions": coerce_int(
                    first_present(
                        row,
                        "pass_completions",
                        "passing_completions",
                        "completions",
                    )
                ),
                "pass_yards": coerce_int(
                    first_present(
                        row,
                        "pass_yards",
                        "passing_yards",
                        "passYds",
                    )
                ),
                "pass_tds": coerce_int(
                    first_present(
                        row,
                        "pass_tds",
                        "passing_tds",
                        "pass_touchdowns",
                    )
                ),
                "interceptions": coerce_int(
                    first_present(
                        row,
                        "interceptions",
                        "passing_interceptions",
                        "int",
                    )
                ),
                "rush_attempts": coerce_int(
                    first_present(
                        row,
                        "rush_attempts",
                        "rushing_attempts",
                        "carries",
                    )
                ),
                "rush_yards": coerce_int(
                    first_present(
                        row,
                        "rush_yards",
                        "rushing_yards",
                    )
                ),
                "rush_tds": coerce_int(
                    first_present(
                        row,
                        "rush_tds",
                        "rushing_tds",
                        "rush_touchdowns",
                    )
                ),
                "targets": coerce_int(
                    first_present(row, "targets", "receiving_targets")
                ),
                "receptions": coerce_int(
                    first_present(
                        row,
                        "receptions",
                        "rec",
                        "receiving_receptions",
                    )
                ),
                "receiving_yards": coerce_int(
                    first_present(
                        row,
                        "receiving_yards",
                        "rec_yards",
                    )
                ),
                "receiving_tds": coerce_int(
                    first_present(
                        row,
                        "receiving_tds",
                        "rec_tds",
                        "receiving_touchdowns",
                    )
                ),
                "source_ids": {
                    "athlete_id": athlete,
                    "cfb_game_id": external_game,
                },
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build CFB fact_player_game: no joined rows."
        )

    fact = pd.DataFrame.from_records(records)
    fact = fact.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    if persist:
        upsert_fact_player_game(fact)

    output = fact[FACT_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    global _CACHE
    _CACHE = output.copy()
    return output


def get_fact_player_game(
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
        frame = load_fact_player_game_from_db(seasons)
        if not frame.empty:
            return frame

    return build_fact_player_game(
        seasons,
        persist=persist,
    )


def load_fact_player_game_from_db(
    seasons: list[int],
) -> pd.DataFrame:
    ensure_college_schema()
    cols = ", ".join(FACT_COLUMNS[:-1]) + ", source_ids::text AS source_ids"
    query = text(
        f"""
        SELECT {cols}
        FROM {COLLEGE_SCHEMA}.fact_player_game
        WHERE season = ANY(:seasons)
        """
    )
    with engine.connect() as connection:
        return pd.read_sql(
            query,
            connection,
            params={"seasons": [int(s) for s in seasons]},
        )


def upsert_fact_player_game(fact: pd.DataFrame) -> None:
    if fact.empty:
        return

    ensure_college_schema()
    statement = text(
        f"""
        INSERT INTO {COLLEGE_SCHEMA}.fact_player_game (
            player_id, game_id, season, week, season_type, team_id,
            pass_attempts, pass_completions, pass_yards, pass_tds,
            interceptions, rush_attempts, rush_yards, rush_tds,
            targets, receptions, receiving_yards, receiving_tds,
            source_ids, resolution_key, updated_at
        ) VALUES (
            :player_id, :game_id, :season, :week, :season_type, :team_id,
            :pass_attempts, :pass_completions, :pass_yards, :pass_tds,
            :interceptions, :rush_attempts, :rush_yards, :rush_tds,
            :targets, :receptions, :receiving_yards, :receiving_tds,
            CAST(:source_ids AS JSONB), :resolution_key, CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            team_id = EXCLUDED.team_id,
            pass_attempts = EXCLUDED.pass_attempts,
            pass_completions = EXCLUDED.pass_completions,
            pass_yards = EXCLUDED.pass_yards,
            pass_tds = EXCLUDED.pass_tds,
            interceptions = EXCLUDED.interceptions,
            rush_attempts = EXCLUDED.rush_attempts,
            rush_yards = EXCLUDED.rush_yards,
            rush_tds = EXCLUDED.rush_tds,
            targets = EXCLUDED.targets,
            receptions = EXCLUDED.receptions,
            receiving_yards = EXCLUDED.receiving_yards,
            receiving_tds = EXCLUDED.receiving_tds,
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
                    "player_id",
                    "game_id",
                    "season",
                    "week",
                    "season_type",
                    "team_id",
                    "pass_attempts",
                    "pass_completions",
                    "pass_yards",
                    "pass_tds",
                    "interceptions",
                    "rush_attempts",
                    "rush_yards",
                    "rush_tds",
                    "targets",
                    "receptions",
                    "receiving_yards",
                    "receiving_tds",
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


def clear_fact_player_game_cache() -> None:
    global _CACHE
    _CACHE = None
