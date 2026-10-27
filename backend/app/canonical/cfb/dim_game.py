"""dim_game — college football game dimension."""

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
from app.canonical.cfb.dim_team import (
    get_dim_team,
    resolve_team_id,
    team_id_lookup_from_dim,
)
from app.canonical.cfb.ids import (
    cfb_game_resolution_key,
    mint_cfb_game_id,
)
from app.canonical.cfb.schema import (
    COLLEGE_SCHEMA,
    ensure_college_schema,
)
from app.database import engine


_DIM_GAME_CACHE: pd.DataFrame | None = None
_DIM_GAME_CACHE_WITH_KEYS: pd.DataFrame | None = None

DIM_GAME_COLUMNS = [
    "game_id",
    "season",
    "week",
    "season_type",
    "game_date",
    "home_team_id",
    "away_team_id",
    "home_score",
    "away_score",
    "game_status",
    "neutral_site",
    "conference_game",
    "source_ids",
]


def _load_source_frames(
    seasons: list[int],
) -> dict[str, pd.DataFrame]:
    from sportsdataverse.cfb import load_cfb_schedule

    try:
        schedule = to_pandas(
            load_cfb_schedule(
                seasons=seasons,
                return_as_pandas=True,
            )
        )
    except TypeError:
        schedule = to_pandas(
            load_cfb_schedule(seasons=seasons)
        )
    return {"schedule": schedule}


def build_dim_game(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    raw = source_frames or _load_source_frames(seasons)
    schedule = raw.get("schedule", pd.DataFrame()).copy()
    if schedule.empty:
        raise ValueError(
            "Unable to build CFB dim_game: no schedule rows "
            "from sportsdataverse."
        )

    team_lookup = team_id_lookup_from_dim(
        get_dim_team(force_refresh=False, persist=False)
    )

    records: list[dict[str, Any]] = []
    for row in schedule.to_dict(orient="records"):
        external_game_id = normalize_text(
            first_present(
                row,
                "game_id",
                "id",
                "espn_game_id",
            )
        )
        season = coerce_int(
            first_present(row, "season", "year")
        )
        week = coerce_int(first_present(row, "week"))
        home_abbr = normalize_text(
            first_present(
                row,
                "home_team",
                "home_abbreviation",
                "home_team_abbr",
            )
        )
        away_abbr = normalize_text(
            first_present(
                row,
                "away_team",
                "away_abbreviation",
                "away_team_abbr",
            )
        )
        home_name = normalize_text(
            first_present(
                row,
                "home_team_name",
                "home_school",
                "home_team",
            )
        )
        away_name = normalize_text(
            first_present(
                row,
                "away_team_name",
                "away_school",
                "away_team",
            )
        )

        try:
            resolution_key = cfb_game_resolution_key(
                game_id=external_game_id,
                season=season,
                week=week,
                home_team=home_abbr or home_name,
                away_team=away_abbr or away_name,
            )
        except ValueError:
            continue

        home_team_id = resolve_team_id(
            espn_team_id=first_present(
                row,
                "home_id",
                "home_team_id",
                "homeTeamId",
            ),
            team_abbreviation=home_abbr,
            team_name=home_name,
            team_id_lookup=team_lookup,
        )
        away_team_id = resolve_team_id(
            espn_team_id=first_present(
                row,
                "away_id",
                "away_team_id",
                "awayTeamId",
            ),
            team_abbreviation=away_abbr,
            team_name=away_name,
            team_id_lookup=team_lookup,
        )

        neutral = first_present(
            row,
            "neutral_site",
            "neutralSite",
            "neutral",
        )
        conference_game = first_present(
            row,
            "conference_game",
            "conferenceGame",
        )

        source_ids: dict[str, str] = {}
        if external_game_id:
            source_ids["cfb_game_id"] = external_game_id

        records.append(
            {
                "game_id": mint_cfb_game_id(
                    resolution_key=resolution_key,
                ),
                "season": season,
                "week": week,
                "season_type": normalize_text(
                    first_present(
                        row,
                        "season_type",
                        "game_type",
                        "seasonType",
                    )
                ),
                "game_date": normalize_text(
                    first_present(
                        row,
                        "start_date",
                        "game_date",
                        "date",
                        "startDate",
                    )
                ),
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": coerce_int(
                    first_present(
                        row,
                        "home_points",
                        "home_score",
                        "home_team_score",
                    )
                ),
                "away_score": coerce_int(
                    first_present(
                        row,
                        "away_points",
                        "away_score",
                        "away_team_score",
                    )
                ),
                "game_status": normalize_text(
                    first_present(
                        row,
                        "status",
                        "game_status",
                        "completed",
                    )
                ),
                "neutral_site": (
                    bool(neutral)
                    if neutral is not None
                    else None
                ),
                "conference_game": (
                    bool(conference_game)
                    if conference_game is not None
                    else None
                ),
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build CFB dim_game: no resolvable games."
        )

    dim = pd.DataFrame.from_records(records)
    dim = dim.drop_duplicates(
        subset=["game_id"],
        keep="last",
    ).reset_index(drop=True)

    if seasons:
        allowed = {int(s) for s in seasons}
        dim = dim[
            dim["season"].map(
                lambda value: (
                    int(value) in allowed
                    if value is not None
                    else False
                )
            )
        ].reset_index(drop=True)

    global _DIM_GAME_CACHE, _DIM_GAME_CACHE_WITH_KEYS
    _DIM_GAME_CACHE_WITH_KEYS = dim.copy()

    if persist:
        upsert_dim_game(dim)

    output = dim[DIM_GAME_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    _DIM_GAME_CACHE = output.copy()
    return output


def dim_game_count() -> int:
    try:
        ensure_college_schema()
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {COLLEGE_SCHEMA}.dim_game"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def load_dim_game_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    ensure_college_schema()
    if seasons:
        query = text(
            f"""
            SELECT
                game_id,
                season,
                week,
                season_type,
                game_date,
                home_team_id,
                away_team_id,
                home_score,
                away_score,
                game_status,
                neutral_site,
                conference_game,
                source_ids::text AS source_ids
            FROM {COLLEGE_SCHEMA}.dim_game
            WHERE season = ANY(:seasons)
            """
        )
        params = {"seasons": [int(s) for s in seasons]}
    else:
        query = text(
            f"""
            SELECT
                game_id,
                season,
                week,
                season_type,
                game_date,
                home_team_id,
                away_team_id,
                home_score,
                away_score,
                game_status,
                neutral_site,
                conference_game,
                source_ids::text AS source_ids
            FROM {COLLEGE_SCHEMA}.dim_game
            """
        )
        params = {}

    with engine.connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_dim_game(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _DIM_GAME_CACHE

    if (
        not force_refresh
        and _DIM_GAME_CACHE is not None
        and not _DIM_GAME_CACHE.empty
        and seasons
    ):
        allowed = {int(s) for s in seasons}
        cached = _DIM_GAME_CACHE[
            _DIM_GAME_CACHE["season"].map(
                lambda value: (
                    int(value) in allowed
                    if value is not None
                    else False
                )
            )
        ]
        if not cached.empty:
            return cached.copy()

    if not force_refresh and dim_game_count() > 0:
        frame = load_dim_game_from_db(seasons)
        if not frame.empty:
            if seasons is None:
                _DIM_GAME_CACHE = frame.copy()
            return frame

    if not seasons:
        from app.sources import sportsdataverse as sdv_source

        seasons = [sdv_source.get_current_season()]

    return build_dim_game(
        seasons,
        persist=persist,
    )


def upsert_dim_game(dim: pd.DataFrame) -> None:
    if dim.empty:
        return

    ensure_college_schema()
    statement = text(
        f"""
        INSERT INTO {COLLEGE_SCHEMA}.dim_game (
            game_id,
            season,
            week,
            season_type,
            game_date,
            home_team_id,
            away_team_id,
            home_score,
            away_score,
            game_status,
            neutral_site,
            conference_game,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :game_id,
            :season,
            :week,
            :season_type,
            CAST(:game_date AS DATE),
            :home_team_id,
            :away_team_id,
            :home_score,
            :away_score,
            :game_status,
            :neutral_site,
            :conference_game,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            game_id = EXCLUDED.game_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            game_date = EXCLUDED.game_date,
            home_team_id = EXCLUDED.home_team_id,
            away_team_id = EXCLUDED.away_team_id,
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score,
            game_status = EXCLUDED.game_status,
            neutral_site = EXCLUDED.neutral_site,
            conference_game = EXCLUDED.conference_game,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in dim.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(source_ids, sort_keys=True)
        rows.append(
            {
                "game_id": record["game_id"],
                "season": sql_null_if_missing(
                    record.get("season")
                ),
                "week": sql_null_if_missing(record.get("week")),
                "season_type": sql_null_if_missing(
                    record.get("season_type")
                ),
                "game_date": sql_null_if_missing(
                    record.get("game_date")
                ),
                "home_team_id": sql_null_if_missing(
                    record.get("home_team_id")
                ),
                "away_team_id": sql_null_if_missing(
                    record.get("away_team_id")
                ),
                "home_score": sql_null_if_missing(
                    record.get("home_score")
                ),
                "away_score": sql_null_if_missing(
                    record.get("away_score")
                ),
                "game_status": sql_null_if_missing(
                    record.get("game_status")
                ),
                "neutral_site": sql_null_if_missing(
                    record.get("neutral_site")
                ),
                "conference_game": sql_null_if_missing(
                    record.get("conference_game")
                ),
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


def game_id_lookup_from_dim(
    dim: pd.DataFrame | None = None,
) -> dict[str, str]:
    frame = dim
    if frame is None:
        frame = get_dim_game(force_refresh=False, persist=False)
    if frame is None or frame.empty:
        return {}

    lookup: dict[str, str] = {}
    for row in frame.to_dict(orient="records"):
        game_id = normalize_text(row.get("game_id"))
        if not game_id:
            continue
        source_ids = row.get("source_ids") or {}
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except json.JSONDecodeError:
                source_ids = {}
        external = None
        if isinstance(source_ids, dict):
            external = normalize_text(
                source_ids.get("cfb_game_id")
            )
        if external:
            lookup[external] = game_id
    return lookup


def clear_dim_game_cache() -> None:
    global _DIM_GAME_CACHE, _DIM_GAME_CACHE_WITH_KEYS
    _DIM_GAME_CACHE = None
    _DIM_GAME_CACHE_WITH_KEYS = None
