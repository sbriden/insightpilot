"""fact_team_game — CFB team box-score offense."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.cfb._common import (
    coerce_float,
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
    "team_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "offensive_plays",
    "pass_attempts",
    "rush_attempts",
    "pass_rate",
    "points",
    "yards",
    "turnovers",
    "source_ids",
]


def _load_source_frames(
    seasons: list[int],
) -> dict[str, pd.DataFrame]:
    from sportsdataverse.cfb import load_cfb_team_box

    try:
        box = to_pandas(
            load_cfb_team_box(
                seasons=seasons,
                return_as_pandas=True,
            )
        )
    except TypeError:
        box = to_pandas(load_cfb_team_box(seasons=seasons))
    except Exception:
        from sportsdataverse import cfb as cfb_mod

        loader = getattr(cfb_mod, "load_cfb_team_boxscore", None)
        if loader is None:
            raise
        try:
            box = to_pandas(
                loader(seasons=seasons, return_as_pandas=True)
            )
        except TypeError:
            box = to_pandas(loader(seasons=seasons))
    return {"team_box": box}


def build_fact_team_game(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    raw = source_frames or _load_source_frames(seasons)
    box = raw.get("team_box", pd.DataFrame()).copy()
    if box.empty:
        raise ValueError(
            "Unable to build CFB fact_team_game: empty team box."
        )

    games = get_dim_game(
        seasons=seasons,
        force_refresh=False,
        persist=False,
    )
    game_lookup = game_id_lookup_from_dim(games)
    game_meta = {
        str(row["game_id"]): row
        for row in games.to_dict(orient="records")
    }
    team_lookup = team_id_lookup_from_dim(
        get_dim_team(force_refresh=False, persist=False)
    )

    records: list[dict[str, Any]] = []
    for row in box.to_dict(orient="records"):
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
        meta = game_meta.get(str(game_id)) or {}

        team_id = resolve_team_id(
            espn_team_id=first_present(
                row, "team_id", "espn_team_id", "id"
            ),
            team_abbreviation=first_present(
                row,
                "team_abbreviation",
                "team",
                "abbreviation",
                "team_abbr",
            ),
            team_name=first_present(
                row, "team_name", "school", "team"
            ),
            team_id_lookup=team_lookup,
        )
        if not team_id:
            continue

        pass_att = coerce_int(
            first_present(
                row,
                "pass_attempts",
                "passing_attempts",
            )
        )
        if pass_att is None:
            # sportsdataverse uses "21/32" completionAttempts.
            comp_att = normalize_text(
                first_present(
                    row,
                    "completionAttempts",
                    "completions_attempts",
                    "completion_attempts",
                )
            )
            if comp_att and "/" in comp_att:
                try:
                    pass_att = int(comp_att.split("/")[-1].strip())
                except ValueError:
                    pass_att = None

        rush_att = coerce_int(
            first_present(
                row,
                "rush_attempts",
                "rushingAttempts",
                "rushing_attempts",
                "carries",
            )
        )
        plays = coerce_int(
            first_present(
                row,
                "offensive_plays",
                "plays",
                "total_plays",
            )
        )
        if plays is None and pass_att is not None and rush_att is not None:
            plays = pass_att + rush_att

        pass_rate = coerce_float(
            first_present(row, "pass_rate", "pass_pct")
        )
        if (
            pass_rate is None
            and plays
            and pass_att is not None
            and plays > 0
        ):
            pass_rate = float(pass_att) / float(plays)

        season = coerce_int(
            first_present(row, "season", "year")
        ) or coerce_int(meta.get("season"))
        week = coerce_int(first_present(row, "week")) or coerce_int(
            meta.get("week")
        )

        points = coerce_int(
            first_present(
                row,
                "points",
                "score",
                "total_points",
                "points_scored",
            )
        )
        if points is None:
            home_away = normalize_text(
                first_present(row, "home_away", "homeAway")
            )
            if home_away == "home":
                points = coerce_int(meta.get("home_score"))
            elif home_away == "away":
                points = coerce_int(meta.get("away_score"))
            elif team_id == meta.get("home_team_id"):
                points = coerce_int(meta.get("home_score"))
            elif team_id == meta.get("away_team_id"):
                points = coerce_int(meta.get("away_score"))

        resolution_key = f"{team_id}:{game_id}"

        records.append(
            {
                "team_id": team_id,
                "game_id": game_id,
                "season": season,
                "week": week,
                "season_type": normalize_text(
                    first_present(row, "season_type", "game_type")
                ) or normalize_text(meta.get("season_type")),
                "offensive_plays": plays,
                "pass_attempts": pass_att,
                "rush_attempts": rush_att,
                "pass_rate": pass_rate,
                "points": points,
                "yards": coerce_float(
                    first_present(
                        row,
                        "yards",
                        "totalYards",
                        "total_yards",
                        "net_yards",
                    )
                ),
                "turnovers": coerce_int(
                    first_present(
                        row,
                        "turnovers",
                        "turnover",
                        "giveaways",
                    )
                ),
                "source_ids": {
                    "cfb_game_id": external_game,
                },
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build CFB fact_team_game: no joined rows."
        )

    fact = pd.DataFrame.from_records(records)
    fact = fact.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    if persist:
        upsert_fact_team_game(fact)

    output = fact[FACT_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    global _CACHE
    _CACHE = output.copy()
    return output


def get_fact_team_game(
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
        frame = load_fact_team_game_from_db(seasons)
        if not frame.empty:
            return frame

    return build_fact_team_game(seasons, persist=persist)


def load_fact_team_game_from_db(
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
        FROM {COLLEGE_SCHEMA}.fact_team_game
        WHERE season = ANY(:seasons)
        """
    )
    with engine.connect() as connection:
        return pd.read_sql(
            query,
            connection,
            params={"seasons": [int(s) for s in seasons]},
        )


def upsert_fact_team_game(fact: pd.DataFrame) -> None:
    if fact.empty:
        return

    ensure_college_schema()
    statement = text(
        f"""
        INSERT INTO {COLLEGE_SCHEMA}.fact_team_game (
            team_id, game_id, season, week, season_type,
            offensive_plays, pass_attempts, rush_attempts,
            pass_rate, points, yards, turnovers,
            source_ids, resolution_key, updated_at
        ) VALUES (
            :team_id, :game_id, :season, :week, :season_type,
            :offensive_plays, :pass_attempts, :rush_attempts,
            :pass_rate, :points, :yards, :turnovers,
            CAST(:source_ids AS JSONB), :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            offensive_plays = EXCLUDED.offensive_plays,
            pass_attempts = EXCLUDED.pass_attempts,
            rush_attempts = EXCLUDED.rush_attempts,
            pass_rate = EXCLUDED.pass_rate,
            points = EXCLUDED.points,
            yards = EXCLUDED.yards,
            turnovers = EXCLUDED.turnovers,
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
                    "team_id",
                    "game_id",
                    "season",
                    "week",
                    "season_type",
                    "offensive_plays",
                    "pass_attempts",
                    "rush_attempts",
                    "pass_rate",
                    "points",
                    "yards",
                    "turnovers",
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


def clear_fact_team_game_cache() -> None:
    global _CACHE
    _CACHE = None
