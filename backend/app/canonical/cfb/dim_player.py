"""dim_player — college football player dimension."""

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
    cfb_player_resolution_key,
    mint_cfb_player_id,
)
from app.canonical.cfb.schema import (
    COLLEGE_SCHEMA,
    ensure_college_schema,
)
from app.database import engine


_DIM_PLAYER_CACHE: pd.DataFrame | None = None
_DIM_PLAYER_CACHE_WITH_KEYS: pd.DataFrame | None = None

DIM_PLAYER_COLUMNS = [
    "player_id",
    "name",
    "first_name",
    "last_name",
    "position",
    "birth_date",
    "class_year",
    "current_team_id",
    "status",
    "source_ids",
]


def _load_source_frames(
    seasons: list[int],
) -> dict[str, pd.DataFrame]:
    from sportsdataverse.cfb import load_cfb_rosters

    try:
        rosters = to_pandas(
            load_cfb_rosters(
                seasons=seasons,
                return_as_pandas=True,
            )
        )
    except TypeError:
        rosters = to_pandas(load_cfb_rosters(seasons=seasons))
    return {"rosters": rosters}


def build_dim_player(
    seasons: list[int] | None = None,
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if source_frames is None:
        if not seasons:
            from app.sources import sportsdataverse as sdv_source

            seasons = [sdv_source.get_current_season()]
        raw = _load_source_frames(seasons)
    else:
        raw = source_frames

    rosters = raw.get("rosters", pd.DataFrame()).copy()
    if rosters.empty:
        raise ValueError(
            "Unable to build CFB dim_player: no rosters "
            "available from sportsdataverse."
        )

    # Prefer latest season row per athlete.
    if "season" in rosters.columns:
        rosters["_season_num"] = pd.to_numeric(
            rosters["season"],
            errors="coerce",
        )
        rosters = rosters.sort_values(
            "_season_num",
            ascending=True,
        )

    team_lookup = team_id_lookup_from_dim(
        get_dim_team(force_refresh=False, persist=False)
    )

    records: list[dict[str, Any]] = []
    for row in rosters.to_dict(orient="records"):
        athlete_id = normalize_text(
            first_present(
                row,
                "athlete_id",
                "player_id",
                "id",
                "espn_id",
                "athleteId",
            )
        )
        first_name = normalize_text(
            first_present(row, "first_name", "firstName")
        )
        last_name = normalize_text(
            first_present(row, "last_name", "lastName")
        )
        name = normalize_text(
            first_present(
                row,
                "full_name",
                "athlete_display_name",
                "name",
                "display_name",
            )
        )
        if not name and (first_name or last_name):
            name = " ".join(
                part
                for part in (first_name, last_name)
                if part
            )

        birth_date = normalize_text(
            first_present(row, "birth_date", "date_of_birth")
        )
        try:
            resolution_key = cfb_player_resolution_key(
                athlete_id=athlete_id,
                name=name,
                birth_date=birth_date,
            )
        except ValueError:
            continue

        team_id = resolve_team_id(
            espn_team_id=first_present(
                row,
                "team_id",
                "espn_team_id",
                "school_id",
            ),
            team_abbreviation=first_present(
                row,
                "team_abbreviation",
                "team_abbr",
                "team",
                "abbreviation",
            ),
            team_name=first_present(
                row,
                "team_name",
                "school",
                "team",
            ),
            team_id_lookup=team_lookup,
        )

        source_ids: dict[str, str] = {}
        if athlete_id:
            source_ids["athlete_id"] = athlete_id
        season_val = coerce_int(row.get("season"))
        if season_val is not None:
            source_ids["roster_season"] = str(season_val)

        records.append(
            {
                "player_id": mint_cfb_player_id(
                    resolution_key=resolution_key,
                ),
                "name": name,
                "first_name": first_name,
                "last_name": last_name,
                "position": normalize_text(
                    first_present(
                        row,
                        "position",
                        "pos",
                        "position_abbreviation",
                    )
                ),
                "birth_date": birth_date,
                "class_year": normalize_text(
                    first_present(
                        row,
                        "class",
                        "year",
                        "experience",
                        "class_year",
                    )
                ),
                "current_team_id": team_id,
                "status": normalize_text(
                    first_present(row, "status", "active")
                ),
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build CFB dim_player: no resolvable players."
        )

    dim = pd.DataFrame.from_records(records)
    dim = dim.drop_duplicates(
        subset=["player_id"],
        keep="last",
    ).reset_index(drop=True)

    global _DIM_PLAYER_CACHE, _DIM_PLAYER_CACHE_WITH_KEYS
    _DIM_PLAYER_CACHE_WITH_KEYS = dim.copy()

    if persist:
        upsert_dim_player(dim)

    output = dim[DIM_PLAYER_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    _DIM_PLAYER_CACHE = output.copy()
    return output


def dim_player_count() -> int:
    try:
        ensure_college_schema()
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {COLLEGE_SCHEMA}.dim_player"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def load_dim_player_from_db() -> pd.DataFrame:
    ensure_college_schema()
    query = text(
        f"""
        SELECT
            player_id,
            name,
            first_name,
            last_name,
            position,
            birth_date,
            class_year,
            current_team_id,
            status,
            source_ids::text AS source_ids
        FROM {COLLEGE_SCHEMA}.dim_player
        """
    )
    with engine.connect() as connection:
        return pd.read_sql(query, connection)


def get_dim_player(
    *,
    force_refresh: bool = False,
    persist: bool = False,
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    global _DIM_PLAYER_CACHE

    if (
        not force_refresh
        and _DIM_PLAYER_CACHE is not None
        and not _DIM_PLAYER_CACHE.empty
    ):
        return _DIM_PLAYER_CACHE.copy()

    if not force_refresh and dim_player_count() > 0:
        frame = load_dim_player_from_db()
        if not frame.empty:
            _DIM_PLAYER_CACHE = frame.copy()
            return frame

    return build_dim_player(
        seasons,
        persist=persist,
    )


def upsert_dim_player(dim: pd.DataFrame) -> None:
    if dim.empty:
        return

    ensure_college_schema()
    statement = text(
        f"""
        INSERT INTO {COLLEGE_SCHEMA}.dim_player (
            player_id,
            name,
            first_name,
            last_name,
            position,
            birth_date,
            class_year,
            current_team_id,
            status,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :player_id,
            :name,
            :first_name,
            :last_name,
            :position,
            CAST(:birth_date AS DATE),
            :class_year,
            :current_team_id,
            :status,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            player_id = EXCLUDED.player_id,
            name = EXCLUDED.name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            position = EXCLUDED.position,
            birth_date = EXCLUDED.birth_date,
            class_year = EXCLUDED.class_year,
            current_team_id = EXCLUDED.current_team_id,
            status = EXCLUDED.status,
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
                "player_id": record["player_id"],
                "name": sql_null_if_missing(record.get("name")),
                "first_name": sql_null_if_missing(
                    record.get("first_name")
                ),
                "last_name": sql_null_if_missing(
                    record.get("last_name")
                ),
                "position": sql_null_if_missing(
                    record.get("position")
                ),
                "birth_date": sql_null_if_missing(
                    record.get("birth_date")
                ),
                "class_year": sql_null_if_missing(
                    record.get("class_year")
                ),
                "current_team_id": sql_null_if_missing(
                    record.get("current_team_id")
                ),
                "status": sql_null_if_missing(
                    record.get("status")
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


def player_id_lookup_from_dim(
    dim: pd.DataFrame | None = None,
) -> dict[str, str]:
    frame = dim
    if frame is None:
        frame = get_dim_player(force_refresh=False, persist=False)
    if frame is None or frame.empty:
        return {}

    lookup: dict[str, str] = {}
    for row in frame.to_dict(orient="records"):
        player_id = normalize_text(row.get("player_id"))
        if not player_id:
            continue
        source_ids = row.get("source_ids") or {}
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except json.JSONDecodeError:
                source_ids = {}
        athlete = None
        if isinstance(source_ids, dict):
            athlete = normalize_text(source_ids.get("athlete_id"))
        if athlete:
            lookup[athlete] = player_id
    return lookup


def clear_dim_player_cache() -> None:
    global _DIM_PLAYER_CACHE, _DIM_PLAYER_CACHE_WITH_KEYS
    _DIM_PLAYER_CACHE = None
    _DIM_PLAYER_CACHE_WITH_KEYS = None
