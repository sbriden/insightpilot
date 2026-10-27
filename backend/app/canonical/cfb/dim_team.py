"""dim_team — college football team dimension."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.cfb._common import (
    first_present,
    normalize_text,
    sql_null_if_missing,
    to_pandas,
)
from app.canonical.cfb.ids import (
    cfb_team_resolution_key,
    mint_cfb_team_id,
)
from app.canonical.cfb.schema import (
    COLLEGE_SCHEMA,
    ensure_college_schema,
)
from app.database import engine


_DIM_TEAM_CACHE: pd.DataFrame | None = None
_DIM_TEAM_CACHE_WITH_KEYS: pd.DataFrame | None = None

DIM_TEAM_COLUMNS = [
    "team_id",
    "team_name",
    "team_abbreviation",
    "conference",
    "division",
    "subdivision",
    "stadium",
    "source_ids",
]


def _default_team_seasons() -> list[int]:
    try:
        from sportsdataverse.cfb import most_recent_cfb_season

        current = int(most_recent_cfb_season())
    except Exception:
        from datetime import datetime, timezone

        current = datetime.now(timezone.utc).year
    # Team info is season-scoped in sportsdataverse; a short
    # lookback covers conference realignment without a full
    # historical pull for a dimension table.
    start = max(2001, current - 3)
    return list(range(start, current + 1))


def _load_source_frames(
    seasons: list[int] | None = None,
) -> dict[str, pd.DataFrame]:
    from sportsdataverse.cfb import (
        load_cfb_team_info,
        load_cfb_teams,
    )

    resolved = [int(s) for s in (seasons or _default_team_seasons())]
    frames: dict[str, pd.DataFrame] = {}
    try:
        frames["team_info"] = to_pandas(
            load_cfb_team_info(
                seasons=resolved,
                return_as_pandas=True,
            )
        )
    except TypeError:
        try:
            frames["team_info"] = to_pandas(
                load_cfb_team_info(seasons=resolved)
            )
        except Exception:
            frames["team_info"] = pd.DataFrame()
    except Exception:
        frames["team_info"] = pd.DataFrame()

    try:
        frames["teams"] = to_pandas(
            load_cfb_teams(
                seasons=resolved,
                return_as_pandas=True,
            )
        )
    except TypeError:
        try:
            frames["teams"] = to_pandas(
                load_cfb_teams(seasons=resolved)
            )
        except Exception:
            frames["teams"] = pd.DataFrame()
    except Exception:
        frames["teams"] = pd.DataFrame()

    return frames


def team_id_lookup_from_dim(
    dim: pd.DataFrame | None = None,
) -> dict[str, str]:
    """Map espn_team_id / abbreviation → InsightPilot team_id."""

    frame = dim
    if frame is None:
        frame = get_dim_team(force_refresh=False, persist=False)
    if frame is None or frame.empty:
        return {}

    lookup: dict[str, str] = {}
    for row in frame.to_dict(orient="records"):
        team_id = normalize_text(row.get("team_id"))
        if not team_id:
            continue
        source_ids = row.get("source_ids") or {}
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except json.JSONDecodeError:
                source_ids = {}
        espn_id = normalize_text(
            source_ids.get("espn_team_id")
            if isinstance(source_ids, dict)
            else None
        )
        abbr = normalize_text(row.get("team_abbreviation"))
        if espn_id:
            lookup[f"espn:{espn_id}"] = team_id
        if abbr:
            lookup[f"abbr:{abbr.upper()}"] = team_id
        name = normalize_text(row.get("team_name"))
        if name:
            lookup[f"name:{name.lower()}"] = team_id
    return lookup


def resolve_team_id(
    *,
    espn_team_id: Any = None,
    team_abbreviation: Any = None,
    team_name: Any = None,
    team_id_lookup: dict[str, str] | None = None,
) -> str | None:
    lookup = team_id_lookup
    if lookup is None:
        lookup = team_id_lookup_from_dim()

    espn_id = normalize_text(espn_team_id)
    if espn_id and f"espn:{espn_id}" in lookup:
        return lookup[f"espn:{espn_id}"]

    abbr = normalize_text(team_abbreviation)
    if abbr and f"abbr:{abbr.upper()}" in lookup:
        return lookup[f"abbr:{abbr.upper()}"]

    name = normalize_text(team_name)
    if name and f"name:{name.lower()}" in lookup:
        return lookup[f"name:{name.lower()}"]

    return None


def build_dim_team(
    seasons: list[int] | None = None,
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    raw = source_frames or _load_source_frames(seasons)
    teams = raw.get("team_info", pd.DataFrame()).copy()
    if teams.empty:
        teams = raw.get("teams", pd.DataFrame()).copy()

    if teams.empty:
        raise ValueError(
            "Unable to build CFB dim_team: no teams available "
            "from sportsdataverse."
        )

    records: list[dict[str, Any]] = []
    for row in teams.to_dict(orient="records"):
        espn_team_id = normalize_text(
            first_present(
                row,
                "team_id",
                "id",
                "espn_team_id",
                "school_id",
            )
        )
        abbr = normalize_text(
            first_present(
                row,
                "abbreviation",
                "team_abbreviation",
                "abbr",
                "team_abbr",
            )
        )
        name = normalize_text(
            first_present(
                row,
                "school",
                "team_name",
                "display_name",
                "nickname",
                "name",
            )
        )
        if not espn_team_id and not abbr and not name:
            continue

        try:
            resolution_key = cfb_team_resolution_key(
                espn_team_id=espn_team_id,
                team_abbreviation=abbr,
                team_name=name,
            )
        except ValueError:
            continue

        team_id = mint_cfb_team_id(
            resolution_key=resolution_key,
        )
        source_ids: dict[str, str] = {}
        if espn_team_id:
            source_ids["espn_team_id"] = espn_team_id
        if abbr:
            source_ids["team_abbreviation"] = abbr.upper()

        records.append(
            {
                "team_id": team_id,
                "team_name": name,
                "team_abbreviation": (abbr or "UNK").upper(),
                "conference": normalize_text(
                    first_present(
                        row,
                        "conference",
                        "conf",
                        "conference_name",
                    )
                ),
                "division": normalize_text(
                    first_present(
                        row,
                        "division",
                        "div",
                    )
                ),
                "subdivision": normalize_text(
                    first_present(
                        row,
                        "classification",
                        "subdivision",
                        "level",
                    )
                ),
                "stadium": normalize_text(
                    first_present(
                        row,
                        "venue",
                        "stadium",
                        "venue_name",
                    )
                ),
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build CFB dim_team: no resolvable teams."
        )

    dim = pd.DataFrame.from_records(records)
    dim = dim.drop_duplicates(
        subset=["team_id"],
        keep="last",
    ).reset_index(drop=True)

    global _DIM_TEAM_CACHE, _DIM_TEAM_CACHE_WITH_KEYS
    _DIM_TEAM_CACHE_WITH_KEYS = dim.copy()

    if persist:
        upsert_dim_team(dim)

    output = dim[DIM_TEAM_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["conference", "team_abbreviation"],
        kind="mergesort",
    ).reset_index(drop=True)
    _DIM_TEAM_CACHE = output.copy()
    return output


def dim_team_count() -> int:
    try:
        ensure_college_schema()
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {COLLEGE_SCHEMA}.dim_team"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def load_dim_team_from_db() -> pd.DataFrame:
    ensure_college_schema()
    query = text(
        f"""
        SELECT
            team_id,
            team_name,
            team_abbreviation,
            conference,
            division,
            subdivision,
            stadium,
            source_ids::text AS source_ids
        FROM {COLLEGE_SCHEMA}.dim_team
        ORDER BY conference, team_abbreviation
        """
    )
    with engine.connect() as connection:
        return pd.read_sql(query, connection)


def get_dim_team(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _DIM_TEAM_CACHE

    if (
        not force_refresh
        and _DIM_TEAM_CACHE is not None
        and not _DIM_TEAM_CACHE.empty
    ):
        return _DIM_TEAM_CACHE.copy()

    if not force_refresh and dim_team_count() > 0:
        frame = load_dim_team_from_db()
        if not frame.empty:
            _DIM_TEAM_CACHE = frame.copy()
            return frame

    return build_dim_team(seasons, persist=persist)


def upsert_dim_team(dim: pd.DataFrame) -> None:
    if dim.empty:
        return

    ensure_college_schema()
    statement = text(
        f"""
        INSERT INTO {COLLEGE_SCHEMA}.dim_team (
            team_id,
            team_name,
            team_abbreviation,
            conference,
            division,
            subdivision,
            stadium,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :team_id,
            :team_name,
            :team_abbreviation,
            :conference,
            :division,
            :subdivision,
            :stadium,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            team_id = EXCLUDED.team_id,
            team_name = EXCLUDED.team_name,
            team_abbreviation = EXCLUDED.team_abbreviation,
            conference = EXCLUDED.conference,
            division = EXCLUDED.division,
            subdivision = EXCLUDED.subdivision,
            stadium = EXCLUDED.stadium,
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
                "team_id": record["team_id"],
                "team_name": sql_null_if_missing(
                    record.get("team_name")
                ),
                "team_abbreviation": record[
                    "team_abbreviation"
                ],
                "conference": sql_null_if_missing(
                    record.get("conference")
                ),
                "division": sql_null_if_missing(
                    record.get("division")
                ),
                "subdivision": sql_null_if_missing(
                    record.get("subdivision")
                ),
                "stadium": sql_null_if_missing(
                    record.get("stadium")
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


def clear_dim_team_cache() -> None:
    global _DIM_TEAM_CACHE, _DIM_TEAM_CACHE_WITH_KEYS
    _DIM_TEAM_CACHE = None
    _DIM_TEAM_CACHE_WITH_KEYS = None
