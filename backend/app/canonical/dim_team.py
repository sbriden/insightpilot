"""
dim_team — canonical team dimension.

InsightPilot owns team_id. External provider IDs live only
in source_ids JSON for resolution and cross-system joins.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.ids import (
    TEAM_ABBREVIATION_ALIASES,
    canonicalize_team_abbreviation,
    legacy_alias_team_id,
    make_team_id,
    team_resolution_key,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_DIM_TEAM_CACHE: pd.DataFrame | None = None
_DIM_TEAM_CACHE_WITH_KEYS: pd.DataFrame | None = None

DIM_TEAM_COLUMNS = [
    "team_id",
    "team_name",
    "team_abbreviation",
    "conference",
    "division",
    "stadium",
    "source_ids",
]

# Roster / provider codes that are not NFL franchises.
NON_TEAM_ABBREVIATIONS = frozenset(
    {
        "FA",
        "FREE",
        "UNA",
        "UNK",
        "XXX",
        "NA",
        "N/A",
        "NONE",
        "RET",
        "RETIRED",
        "UFA",
        "RFA",
        "PRACTICE",
        "PS",
    }
)


def normalize_team_abbreviation(
    value: Any,
) -> str | None:
    text_value = _normalize_text(value)
    if not text_value:
        return None
    abbr = text_value.upper()
    if abbr in NON_TEAM_ABBREVIATIONS:
        return None
    return canonicalize_team_abbreviation(abbr)


def team_id_lookup_from_dim(
    dim: pd.DataFrame | None = None,
) -> dict[str, str]:
    """Map canonical team_abbreviation → InsightPilot team_id."""

    frame = dim
    if frame is None:
        frame = get_dim_team(force_refresh=False, persist=False)
    if frame is None or frame.empty:
        return {}

    lookup: dict[str, str] = {}
    for row in frame.to_dict(orient="records"):
        raw = _normalize_text(row.get("team_abbreviation"))
        abbr = normalize_team_abbreviation(raw)
        team_id = row.get("team_id")
        if not abbr or not team_id:
            continue
        raw_u = (raw or "").upper()
        # Prefer the row already stored under the canonical abbr
        # so historical OAK does not overwrite LV.
        if abbr not in lookup or raw_u == abbr:
            lookup[abbr] = str(team_id)
    return lookup


def resolve_team_id(
    team_abbreviation: Any,
    *,
    team_id_lookup: dict[str, str] | None = None,
) -> str | None:
    """
    Resolve a roster team code to a dim_team team_id.

    Unknown / non-franchise codes return None so dim_player
    never writes orphan foreign keys.
    """

    abbr = normalize_team_abbreviation(team_abbreviation)
    if not abbr:
        return None
    lookup = team_id_lookup
    if lookup is None:
        lookup = team_id_lookup_from_dim()
    return lookup.get(abbr)


def _to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    raise TypeError("Expected a pandas or polars DataFrame.")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _normalize_text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text_value = str(value).strip()
    if not text_value or text_value.lower() in {
        "nan",
        "none",
        "nat",
        "<na>",
    }:
        return None
    return text_value


def _sql_null_if_missing(value: Any) -> Any:
    if _is_missing(value):
        return None
    return value


def _load_source_frames() -> dict[str, pd.DataFrame]:
    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    return {
        "teams": _to_pandas(nfl.load_teams()),
        "schedules": _to_pandas(
            nfl.load_schedules(seasons=[current])
        ),
    }


def _latest_stadiums(schedules: pd.DataFrame) -> pd.DataFrame:
    if schedules.empty or "home_team" not in schedules.columns:
        return pd.DataFrame(
            columns=["team_abbreviation", "stadium"]
        )

    frame = schedules.copy()
    if "stadium" not in frame.columns:
        return pd.DataFrame(
            columns=["team_abbreviation", "stadium"]
        )

    frame["home_team"] = frame["home_team"].map(
        normalize_team_abbreviation
    )
    frame["stadium"] = frame["stadium"].map(_normalize_text)
    frame = frame[
        frame["home_team"].notna()
        & frame["stadium"].notna()
    ].copy()

    if "week" in frame.columns:
        frame["week"] = pd.to_numeric(
            frame["week"],
            errors="coerce",
        )
        frame = frame.sort_values(
            ["home_team", "week"],
            ascending=True,
        )

    frame = frame.drop_duplicates(
        subset=["home_team"],
        keep="last",
    )
    return frame.rename(
        columns={
            "home_team": "team_abbreviation",
        }
    )[["team_abbreviation", "stadium"]]


def build_dim_team(
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Build the canonical dim_team table.

    team_id is always an InsightPilot ID (ip_team_******).
    """

    raw = source_frames or _load_source_frames()
    teams = raw.get("teams", pd.DataFrame()).copy()
    schedules = raw.get("schedules", pd.DataFrame()).copy()

    if teams.empty:
        raise ValueError(
            "Unable to build dim_team: no teams were "
            "available from nflverse."
        )

    stadiums = _latest_stadiums(schedules)
    teams["team_abbr"] = teams["team_abbr"].map(
        normalize_team_abbreviation
    )
    teams = teams[teams["team_abbr"].notna()].copy()
    # After alias collapse (OAK→LV), keep the current franchise row.
    teams = teams.drop_duplicates(
        subset=["team_abbr"],
        keep="last",
    )
    teams = teams.merge(
        stadiums,
        left_on="team_abbr",
        right_on="team_abbreviation",
        how="left",
    )

    records: list[dict[str, Any]] = []
    for row in teams.to_dict(orient="records"):
        abbr = normalize_team_abbreviation(row.get("team_abbr"))
        if not abbr:
            continue

        nflverse_team_id = _normalize_text(row.get("team_id"))
        resolution_key = team_resolution_key(
            team_abbreviation=abbr,
            nflverse_team_id=nflverse_team_id,
        )
        team_id = make_team_id(abbr)

        source_ids: dict[str, str] = {
            "team_abbreviation": abbr,
        }
        if nflverse_team_id:
            source_ids["nflverse_team_id"] = nflverse_team_id

        records.append(
            {
                "team_id": team_id,
                "team_name": _normalize_text(
                    row.get("team_name")
                ),
                "team_abbreviation": abbr,
                "conference": _normalize_text(
                    row.get("team_conf")
                ),
                "division": _normalize_text(
                    row.get("team_division")
                ),
                "stadium": _normalize_text(
                    row.get("stadium")
                ),
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build dim_team: no resolvable teams."
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
        ["conference", "division", "team_abbreviation"],
        kind="mergesort",
    ).reset_index(drop=True)
    _DIM_TEAM_CACHE = output.copy()
    return output


def dim_team_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.dim_team"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_dim_team(
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

    return build_dim_team(persist=persist)


def upsert_dim_team(
    dim: pd.DataFrame,
) -> None:
    if dim.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.dim_team (
            team_id,
            team_name,
            team_abbreviation,
            conference,
            division,
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
            stadium = EXCLUDED.stadium,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in dim.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(
                source_ids,
                sort_keys=True,
            )
        rows.append(
            {
                "team_id": record["team_id"],
                "team_name": _sql_null_if_missing(
                    record.get("team_name")
                ),
                "team_abbreviation": record[
                    "team_abbreviation"
                ],
                "conference": _sql_null_if_missing(
                    record.get("conference")
                ),
                "division": _sql_null_if_missing(
                    record.get("division")
                ),
                "stadium": _sql_null_if_missing(
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
        consolidate_historical_team_aliases(connection)


def consolidate_historical_team_aliases(
    connection: Any | None = None,
) -> int:
    """
    Remap historical alias team_ids (OAK, SD, …) onto the
    canonical franchise id (LV, LAC, …) and drop alias rows.
    """

    updates = [
        ("dim_player", "current_team_id"),
        ("dim_game", "home_team_id"),
        ("dim_game", "away_team_id"),
        ("fact_player_game", "team_id"),
        ("fact_player_usage", "team_id"),
        ("fact_player_efficiency", "team_id"),
        ("fact_team_game", "team_id"),
        ("fact_defensive_game", "defensive_team_id"),
        ("fact_defensive_game", "opponent_team_id"),
        ("fact_injury", "team_id"),
        ("fact_depth_chart", "team_id"),
    ]
    remapped = 0

    def _run(conn: Any) -> int:
        nonlocal remapped
        for alias, canonical in TEAM_ABBREVIATION_ALIASES.items():
            if alias == canonical:
                continue
            from_id = legacy_alias_team_id(alias)
            to_id = make_team_id(canonical)
            if from_id == to_id:
                continue

            # Ensure canonical franchise row exists.
            conn.execute(
                text(
                    f"""
                    INSERT INTO {FANTASY_SCHEMA}.dim_team (
                        team_id,
                        team_name,
                        team_abbreviation,
                        conference,
                        division,
                        stadium,
                        source_ids,
                        resolution_key,
                        updated_at
                    )
                    SELECT
                        :to_id,
                        COALESCE(
                          (
                            SELECT team_name
                            FROM {FANTASY_SCHEMA}.dim_team
                            WHERE team_id = :to_id
                          ),
                          team_name
                        ),
                        :canonical,
                        conference,
                        division,
                        stadium,
                        jsonb_build_object(
                          'team_abbreviation', :canonical,
                          'nflverse_team_id',
                          source_ids->>'nflverse_team_id'
                        ),
                        :resolution_key,
                        CURRENT_TIMESTAMP
                    FROM {FANTASY_SCHEMA}.dim_team
                    WHERE team_id = :from_id
                    ON CONFLICT (team_id) DO NOTHING
                    """
                ),
                {
                    "from_id": from_id,
                    "to_id": to_id,
                    "canonical": canonical,
                    "resolution_key": f"abbr:{canonical}",
                },
            )

            # If canonical was missing, seed from alias then fix label.
            conn.execute(
                text(
                    f"""
                    UPDATE {FANTASY_SCHEMA}.dim_team
                    SET
                      team_abbreviation = :canonical,
                      resolution_key = :resolution_key,
                      source_ids = COALESCE(source_ids, '{{}}'::jsonb)
                        || jsonb_build_object(
                          'team_abbreviation', :canonical
                        ),
                      updated_at = CURRENT_TIMESTAMP
                    WHERE team_id = :to_id
                      AND team_abbreviation IS DISTINCT FROM :canonical
                    """
                ),
                {
                    "to_id": to_id,
                    "canonical": canonical,
                    "resolution_key": f"abbr:{canonical}",
                },
            )

            for table, column in updates:
                # Skip PK collisions by deleting target rows that
                # would conflict, then remap.
                if table in {
                    "fact_team_game",
                    "fact_defensive_game",
                }:
                    if table == "fact_team_game":
                        conn.execute(
                            text(
                                f"""
                                DELETE FROM {FANTASY_SCHEMA}.fact_team_game AS alias_row
                                WHERE alias_row.team_id = :from_id
                                  AND EXISTS (
                                    SELECT 1
                                    FROM {FANTASY_SCHEMA}.fact_team_game AS canon_row
                                    WHERE canon_row.team_id = :to_id
                                      AND canon_row.game_id = alias_row.game_id
                                  )
                                """
                            ),
                            {"from_id": from_id, "to_id": to_id},
                        )
                    else:
                        # defensive_team_id is PK lead; opponent is not.
                        if column == "defensive_team_id":
                            conn.execute(
                                text(
                                    f"""
                                    DELETE FROM {FANTASY_SCHEMA}.fact_defensive_game AS alias_row
                                    WHERE alias_row.defensive_team_id = :from_id
                                      AND EXISTS (
                                        SELECT 1
                                        FROM {FANTASY_SCHEMA}.fact_defensive_game AS canon_row
                                        WHERE canon_row.defensive_team_id = :to_id
                                          AND canon_row.game_id = alias_row.game_id
                                      )
                                    """
                                ),
                                {
                                    "from_id": from_id,
                                    "to_id": to_id,
                                },
                            )

                result = conn.execute(
                    text(
                        f"""
                        UPDATE {FANTASY_SCHEMA}.{table}
                        SET {column} = :to_id
                        WHERE {column} = :from_id
                        """
                    ),
                    {"from_id": from_id, "to_id": to_id},
                )
                remapped += int(result.rowcount or 0)

            conn.execute(
                text(
                    f"""
                    DELETE FROM {FANTASY_SCHEMA}.dim_team
                    WHERE team_id = :from_id
                    """
                ),
                {"from_id": from_id},
            )
        return remapped

    if connection is not None:
        return _run(connection)
    with engine.begin() as conn:
        return _run(conn)


def load_dim_team_from_db() -> pd.DataFrame:
    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(
                f"""
                SELECT
                    team_id,
                    team_name,
                    team_abbreviation,
                    conference,
                    division,
                    stadium,
                    source_ids
                FROM {FANTASY_SCHEMA}.dim_team
                ORDER BY conference, division, team_abbreviation
                """
            ),
            connection,
        )

    if "source_ids" in frame.columns:
        frame["source_ids"] = frame["source_ids"].map(
            lambda value: (
                json.dumps(value, sort_keys=True)
                if isinstance(value, dict)
                else value
            )
        )
    return frame
