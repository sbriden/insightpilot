"""
dim_player — canonical player dimension.

InsightPilot owns player_id. External provider IDs live only
in source_ids JSON for resolution and cross-system joins.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.ids import (
    make_player_id,
    player_resolution_key,
)
from app.canonical.schema import FANTASY_SCHEMA
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
    "rookie_season",
    "current_team_id",
    "status",
    "source_ids",
]


SOURCE_ID_FIELDS = (
    ("gsis_id", "gsis_id"),
    ("nflverse_id", "nfl_id"),
    ("pfr_id", "pfr_id"),
    ("fantasypros_id", "fantasypros_id"),
    ("sleeper_id", "sleeper_id"),
    ("espn_id", "espn_id"),
    ("yahoo_id", "yahoo_id"),
    ("mfl_id", "mfl_id"),
    ("rotowire_id", "rotowire_id"),
    ("sportradar_id", "sportradar_id"),
)


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


def _normalize_id(value: Any) -> str | None:
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
    # Drop trailing .0 from numeric-looking IDs.
    if text_value.endswith(".0"):
        stem = text_value[:-2]
        if stem.isdigit():
            return stem
    return text_value


def _normalize_date(value: Any) -> str | None:
    """
    Return YYYY-MM-DD for Postgres DATE, or None.
    Never return NaN/NaT — those cannot CAST to DATE.
    """

    if _is_missing(value):
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    if _is_missing(parsed):
        return None

    return parsed.strftime("%Y-%m-%d")


def _sql_null_if_missing(value: Any) -> Any:
    if _is_missing(value):
        return None
    return value


def _normalize_status(value: Any) -> str | None:
    raw = _normalize_id(value)
    if raw is None:
        return None

    upper = raw.upper()
    mapping = {
        "ACT": "Active",
        "ACTIVE": "Active",
        "INA": "Inactive",
        "INACTIVE": "Inactive",
        "CUT": "Cut",
        "DEV": "Practice Squad",
        "RES": "Reserve",
        "RET": "Retired",
        "PUP": "PUP",
        "SUS": "Suspended",
        "EXE": "Exempt",
    }
    if upper in mapping:
        return mapping[upper]
    return raw.title()


def _build_source_ids(row: Any) -> dict[str, str]:
    getter = row.get if hasattr(row, "get") else None
    payload: dict[str, str] = {}
    for target_key, source_key in SOURCE_ID_FIELDS:
        value = _normalize_id(
            getter(source_key) if getter else getattr(row, source_key, None)
        )
        if value is not None:
            payload[target_key] = value
    return payload


def _load_source_frames() -> dict[str, pd.DataFrame]:
    import nflreadpy as nfl

    return {
        "players": _to_pandas(nfl.load_players()),
        "ff_playerids": _to_pandas(nfl.load_ff_playerids()),
        "rosters": _to_pandas(
            nfl.load_rosters(
                seasons=[int(nfl.get_current_season())]
            )
        ),
    }


def _prepare_identity_frame(
    players: pd.DataFrame,
    ff_ids: pd.DataFrame,
    rosters: pd.DataFrame,
) -> pd.DataFrame:
    players_frame = players.copy()
    if "gsis_id" in players_frame.columns:
        players_frame["gsis_id"] = players_frame[
            "gsis_id"
        ].map(_normalize_id)

    ff_frame = ff_ids.copy()
    if "gsis_id" in ff_frame.columns:
        ff_frame["gsis_id"] = ff_frame["gsis_id"].map(
            _normalize_id
        )
        ff_frame = ff_frame[
            ff_frame["gsis_id"].notna()
        ].drop_duplicates(
            subset=["gsis_id"],
            keep="last",
        )

    roster_frame = rosters.copy()
    if "gsis_id" in roster_frame.columns:
        roster_frame["gsis_id"] = roster_frame[
            "gsis_id"
        ].map(_normalize_id)

    # Latest roster row per gsis for current team/status.
    if (
        not roster_frame.empty
        and "week" in roster_frame.columns
    ):
        roster_frame["week"] = pd.to_numeric(
            roster_frame["week"],
            errors="coerce",
        )
        roster_frame = roster_frame.sort_values(
            ["gsis_id", "week"],
            ascending=True,
        ).drop_duplicates(
            subset=["gsis_id"],
            keep="last",
        )
    elif not roster_frame.empty:
        roster_frame = roster_frame.drop_duplicates(
            subset=["gsis_id"],
            keep="last",
        )

    roster_keep = [
        col
        for col in [
            "gsis_id",
            "team",
            "status",
            "full_name",
            "first_name",
            "last_name",
            "position",
            "birth_date",
            "rookie_year",
        ]
        if col in roster_frame.columns
    ]
    roster_frame = (
        roster_frame[roster_keep]
        if roster_keep
        else pd.DataFrame(columns=["gsis_id"])
    ).rename(
        columns={
            "team": "roster_team",
            "status": "roster_status",
            "full_name": "roster_name",
            "first_name": "roster_first_name",
            "last_name": "roster_last_name",
            "position": "roster_position",
            "birth_date": "roster_birth_date",
            "rookie_year": "roster_rookie_season",
        }
    )

    ff_keep = [
        col
        for col in [
            "gsis_id",
            "pfr_id",
            "fantasypros_id",
            "sleeper_id",
            "espn_id",
            "yahoo_id",
            "mfl_id",
            "rotowire_id",
            "sportradar_id",
            "name",
            "position",
            "team",
            "birthdate",
            "draft_year",
        ]
        if col in ff_frame.columns
    ]
    ff_frame = (
        ff_frame[ff_keep]
        if ff_keep
        else pd.DataFrame(columns=["gsis_id"])
    ).rename(
        columns={
            "name": "ff_name",
            "position": "ff_position",
            "team": "ff_team",
            "birthdate": "ff_birth_date",
            "draft_year": "ff_rookie_season",
            "pfr_id": "ff_pfr_id",
            "fantasypros_id": "ff_fantasypros_id",
            "sleeper_id": "ff_sleeper_id",
            "espn_id": "ff_espn_id",
            "yahoo_id": "ff_yahoo_id",
            "mfl_id": "ff_mfl_id",
            "rotowire_id": "ff_rotowire_id",
            "sportradar_id": "ff_sportradar_id",
        }
    )

    frame = players_frame.merge(
        ff_frame,
        on="gsis_id",
        how="outer",
    )
    frame = frame.merge(
        roster_frame,
        on="gsis_id",
        how="left",
    )

    # Collapse overlapping ID fields onto canonical source names.
    for target, candidates in {
        "pfr_id": ["pfr_id", "ff_pfr_id"],
        "fantasypros_id": [
            "fantasypros_id",
            "ff_fantasypros_id",
        ],
        "sleeper_id": ["sleeper_id", "ff_sleeper_id"],
        "espn_id": ["espn_id", "ff_espn_id"],
        "yahoo_id": ["yahoo_id", "ff_yahoo_id"],
        "mfl_id": ["mfl_id", "ff_mfl_id"],
        "rotowire_id": ["rotowire_id", "ff_rotowire_id"],
        "sportradar_id": [
            "sportradar_id",
            "ff_sportradar_id",
        ],
    }.items():
        series = None
        for candidate in candidates:
            if candidate not in frame.columns:
                continue
            values = frame[candidate].map(_normalize_id)
            series = (
                values
                if series is None
                else series.fillna(values)
            )
        if series is not None:
            frame[target] = series

    frame["name"] = (
        frame.get("display_name")
        if "display_name" in frame.columns
        else pd.Series([pd.NA] * len(frame))
    )
    if "roster_name" in frame.columns:
        frame["name"] = frame["name"].fillna(
            frame["roster_name"]
        )
    if "ff_name" in frame.columns:
        frame["name"] = frame["name"].fillna(
            frame["ff_name"]
        )

    for target, sources in {
        "first_name": ["first_name", "roster_first_name"],
        "last_name": ["last_name", "roster_last_name"],
        "position": [
            "position",
            "roster_position",
            "ff_position",
        ],
        "birth_date": [
            "birth_date",
            "roster_birth_date",
            "ff_birth_date",
        ],
        "rookie_season": [
            "rookie_season",
            "roster_rookie_season",
            "ff_rookie_season",
            "draft_year",
        ],
        "team_code": [
            "latest_team",
            "roster_team",
            "ff_team",
        ],
        "status_raw": [
            "roster_status",
            "status",
            "pff_status",
        ],
    }.items():
        series = None
        for source in sources:
            if source not in frame.columns:
                continue
            values = frame[source]
            series = (
                values
                if series is None
                else series.fillna(values)
            )
        frame[target] = series

    return frame


def build_dim_player(
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Build the canonical dim_player table.

    player_id is always an InsightPilot ID (ip_player_********).
    External IDs are nested under source_ids only.
    current_team_id only references teams present in dim_team.
    """

    from app.canonical.dim_team import (
        get_dim_team,
        resolve_team_id,
        team_id_lookup_from_dim,
    )

    raw = source_frames or _load_source_frames()
    teams = get_dim_team(
        force_refresh=False,
        persist=persist,
    )
    team_lookup = team_id_lookup_from_dim(teams)

    identity = _prepare_identity_frame(
        raw.get("players", pd.DataFrame()),
        raw.get("ff_playerids", pd.DataFrame()),
        raw.get("rosters", pd.DataFrame()),
    )

    if identity.empty:
        raise ValueError(
            "Unable to build dim_player: no player identity "
            "rows were available from nflverse."
        )

    records: list[dict[str, Any]] = []

    # Dict records avoid iterrows overhead on large frames.
    for row_map in identity.to_dict(orient="records"):
        source_ids = _build_source_ids(row_map)
        name = _normalize_id(row_map.get("name"))
        birth_date = _normalize_date(row_map.get("birth_date"))

        try:
            resolution_key = player_resolution_key(
                gsis_id=source_ids.get("gsis_id"),
                pfr_id=source_ids.get("pfr_id"),
                sleeper_id=source_ids.get("sleeper_id"),
                espn_id=source_ids.get("espn_id"),
                fantasypros_id=source_ids.get(
                    "fantasypros_id"
                ),
                name=name,
                birth_date=birth_date,
            )
        except ValueError:
            continue

        team_code = _normalize_id(row_map.get("team_code"))
        rookie_raw = row_map.get("rookie_season")
        rookie_season = None
        if not _is_missing(rookie_raw):
            try:
                rookie_season = int(float(rookie_raw))
            except (TypeError, ValueError):
                rookie_season = None

        records.append(
            {
                "player_id": make_player_id(resolution_key),
                "name": name,
                "first_name": _normalize_id(
                    row_map.get("first_name")
                ),
                "last_name": _normalize_id(
                    row_map.get("last_name")
                ),
                "position": _normalize_id(
                    row_map.get("position")
                ),
                "birth_date": birth_date,
                "rookie_season": rookie_season,
                "current_team_id": resolve_team_id(
                    team_code,
                    team_id_lookup=team_lookup,
                ),
                "status": _normalize_status(
                    row_map.get("status_raw")
                ),
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build dim_player: no resolvable "
            "player identity rows."
        )

    dim = pd.DataFrame.from_records(records)
    if "birth_date" in dim.columns:
        dim["birth_date"] = dim["birth_date"].astype(
            "object"
        )
        dim["birth_date"] = dim["birth_date"].where(
            dim["birth_date"].notna(),
            None,
        )
    if "current_team_id" in dim.columns:
        dim["current_team_id"] = dim["current_team_id"].astype(
            "object"
        )
        dim["current_team_id"] = dim["current_team_id"].where(
            dim["current_team_id"].notna(),
            None,
        )
    dim = dim.drop_duplicates(
        subset=["player_id"],
        keep="last",
    ).reset_index(drop=True)

    global _DIM_PLAYER_CACHE, _DIM_PLAYER_CACHE_WITH_KEYS
    _DIM_PLAYER_CACHE_WITH_KEYS = dim.copy()

    if persist:
        upsert_dim_player(dim)

    # JSON-serialize source_ids for API/preview tables.
    output = dim[DIM_PLAYER_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(
            value,
            sort_keys=True,
        )
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["last_name", "first_name", "player_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _DIM_PLAYER_CACHE = output.copy()
    return output


def dim_player_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.dim_player"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_dim_player(
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    """
    Fast path for UI/API reads.

    Order:
      1. in-memory cache
      2. Postgres dim_player (if populated)
      3. rebuild from nflverse (optional persist)
    """

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

    return build_dim_player(persist=persist)


def upsert_dim_player(
    dim: pd.DataFrame,
) -> None:
    if dim.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.dim_player (
            player_id,
            name,
            first_name,
            last_name,
            position,
            birth_date,
            rookie_season,
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
            CAST(NULLIF(:birth_date, '') AS DATE),
            :rookie_season,
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
            rookie_season = EXCLUDED.rookie_season,
            current_team_id = EXCLUDED.current_team_id,
            status = EXCLUDED.status,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in dim.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if isinstance(source_ids, str):
            source_ids_json = source_ids
        else:
            source_ids_json = json.dumps(
                source_ids,
                sort_keys=True,
            )

        rows.append(
            {
                "player_id": record["player_id"],
                "name": _sql_null_if_missing(
                    record.get("name")
                ),
                "first_name": _sql_null_if_missing(
                    record.get("first_name")
                ),
                "last_name": _sql_null_if_missing(
                    record.get("last_name")
                ),
                "position": _sql_null_if_missing(
                    record.get("position")
                ),
                "birth_date": _normalize_date(
                    record.get("birth_date")
                ),
                "rookie_season": _sql_null_if_missing(
                    record.get("rookie_season")
                ),
                "current_team_id": _sql_null_if_missing(
                    record.get("current_team_id")
                ),
                "status": _sql_null_if_missing(
                    record.get("status")
                ),
                "source_ids": source_ids_json,
                "resolution_key": record["resolution_key"],
            }
        )

    # Batch to keep first-time sync from timing out the UI path
    # when persist is explicitly requested.
    batch_size = 1000
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def load_dim_player_from_db() -> pd.DataFrame:
    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(
                f"""
                SELECT
                    player_id,
                    name,
                    first_name,
                    last_name,
                    position,
                    birth_date,
                    rookie_season,
                    current_team_id,
                    status,
                    source_ids
                FROM {FANTASY_SCHEMA}.dim_player
                ORDER BY last_name, first_name, player_id
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


def player_id_lookup_from_dim(
    dim: pd.DataFrame,
) -> dict[str, str]:
    """
    Map gsis_id -> InsightPilot player_id for fact joins.
    """

    lookup: dict[str, str] = {}
    for record in dim.to_dict(orient="records"):
        player_id = record.get("player_id")
        source_ids = record.get("source_ids") or {}
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except json.JSONDecodeError:
                source_ids = {}
        gsis_id = _normalize_id(
            source_ids.get("gsis_id")
            if isinstance(source_ids, dict)
            else None
        )
        if player_id and gsis_id:
            lookup[gsis_id] = str(player_id)
    return lookup
