"""
dim_game — canonical NFL game dimension.

InsightPilot owns game_id. External provider IDs live only
in source_ids. home_team_id / away_team_id reference dim_team.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.ids import (
    game_resolution_key,
    make_game_id,
    make_team_id,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_DIM_GAME_CACHE: pd.DataFrame | None = None
_DIM_GAME_CACHE_WITH_KEYS: pd.DataFrame | None = None
_DIM_GAME_CACHE_SEASONS: tuple[int, ...] | None = None

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
    "source_ids",
]


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


def _normalize_date(value: Any) -> str | None:
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


def _normalize_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _game_status(
    home_score: Any,
    away_score: Any,
) -> str:
    if _is_missing(home_score) or _is_missing(away_score):
        return "Scheduled"
    return "Final"


def _season_type(game_type: Any) -> str | None:
    raw = _normalize_text(game_type)
    if raw is None:
        return None
    return raw.upper()


def _load_schedules(
    seasons: list[int],
) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(
        nfl.load_schedules(seasons=seasons)
    )


def build_dim_game(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Build canonical dim_game for the requested seasons.
    """

    if not seasons:
        raise ValueError("At least one season is required.")

    resolved_seasons = sorted({int(season) for season in seasons})
    raw = source_frames or {
        "schedules": _load_schedules(resolved_seasons),
    }
    schedules = raw.get("schedules", pd.DataFrame()).copy()
    if schedules.empty:
        raise ValueError(
            "Unable to build dim_game: no schedule rows "
            "were available from nflverse."
        )

    # Ensure teams exist when persisting.
    if persist:
        from app.canonical.dim_team import get_dim_team

        get_dim_team(force_refresh=False, persist=True)

    records: list[dict[str, Any]] = []
    for row in schedules.to_dict(orient="records"):
        nflverse_game_id = _normalize_text(row.get("game_id"))
        home_abbr = (_normalize_text(row.get("home_team")) or "").upper() or None
        away_abbr = (_normalize_text(row.get("away_team")) or "").upper() or None
        season = _normalize_int(row.get("season"))
        week = _normalize_int(row.get("week"))

        try:
            resolution_key = game_resolution_key(
                nflverse_game_id=nflverse_game_id,
                season=season,
                week=week,
                home_team=home_abbr,
                away_team=away_abbr,
            )
        except ValueError:
            continue

        home_score = row.get("home_score")
        away_score = row.get("away_score")
        home_score_int = _normalize_int(home_score)
        away_score_int = _normalize_int(away_score)

        source_ids: dict[str, str] = {}
        if nflverse_game_id:
            source_ids["nflverse_game_id"] = nflverse_game_id
        for target, source in (
            ("gsis", "gsis"),
            ("espn", "espn"),
            ("pfr", "pfr"),
            ("pff", "pff"),
            ("ftn", "ftn"),
            ("old_game_id", "old_game_id"),
        ):
            value = _normalize_text(row.get(source))
            if value is not None:
                source_ids[target] = value

        records.append(
            {
                "game_id": make_game_id(resolution_key),
                "season": season,
                "week": week,
                "season_type": _season_type(
                    row.get("game_type")
                ),
                "game_date": _normalize_date(
                    row.get("gameday")
                ),
                "home_team_id": (
                    make_team_id(home_abbr)
                    if home_abbr
                    else None
                ),
                "away_team_id": (
                    make_team_id(away_abbr)
                    if away_abbr
                    else None
                ),
                "home_score": home_score_int,
                "away_score": away_score_int,
                "game_status": _game_status(
                    home_score,
                    away_score,
                ),
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build dim_game: no resolvable games."
        )

    dim = pd.DataFrame.from_records(records)
    for column in (
        "game_date",
        "home_score",
        "away_score",
        "season",
        "week",
    ):
        if column in dim.columns:
            dim[column] = dim[column].astype("object")
            dim[column] = dim[column].where(
                dim[column].notna(),
                None,
            )
    dim = dim.drop_duplicates(
        subset=["game_id"],
        keep="last",
    ).reset_index(drop=True)

    global _DIM_GAME_CACHE, _DIM_GAME_CACHE_WITH_KEYS, _DIM_GAME_CACHE_SEASONS
    _DIM_GAME_CACHE_WITH_KEYS = dim.copy()
    _DIM_GAME_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_dim_game(dim)

    output = dim[DIM_GAME_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "game_date", "game_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _DIM_GAME_CACHE = output.copy()
    return output


def dim_game_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.dim_game"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_dim_game(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _DIM_GAME_CACHE, _DIM_GAME_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        # Full dim_game: every NFL game since 1999.
        resolved = list(range(1999, current + 1))
    else:
        resolved = sorted(
            {int(season) for season in seasons}
        )

    if (
        not force_refresh
        and _DIM_GAME_CACHE is not None
        and not _DIM_GAME_CACHE.empty
        and _DIM_GAME_CACHE_SEASONS == tuple(resolved)
    ):
        return _DIM_GAME_CACHE.copy()

    if not force_refresh and dim_game_count() > 0:
        frame = load_dim_game_from_db(seasons=resolved)
        if not frame.empty:
            _DIM_GAME_CACHE = frame.copy()
            _DIM_GAME_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_dim_game(
        resolved,
        persist=persist,
    )


def upsert_dim_game(
    dim: pd.DataFrame,
) -> None:
    if dim.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.dim_game (
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
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :game_id,
            :season,
            :week,
            :season_type,
            CAST(NULLIF(:game_date, '') AS DATE),
            :home_team_id,
            :away_team_id,
            :home_score,
            :away_score,
            :game_status,
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
                "game_id": record["game_id"],
                "season": _sql_null_if_missing(
                    record.get("season")
                ),
                "week": _sql_null_if_missing(
                    record.get("week")
                ),
                "season_type": _sql_null_if_missing(
                    record.get("season_type")
                ),
                "game_date": _normalize_date(
                    record.get("game_date")
                ),
                "home_team_id": _sql_null_if_missing(
                    record.get("home_team_id")
                ),
                "away_team_id": _sql_null_if_missing(
                    record.get("away_team_id")
                ),
                "home_score": _sql_null_if_missing(
                    record.get("home_score")
                ),
                "away_score": _sql_null_if_missing(
                    record.get("away_score")
                ),
                "game_status": _sql_null_if_missing(
                    record.get("game_status")
                ),
                "source_ids": source_ids,
                "resolution_key": record["resolution_key"],
            }
        )

    batch_size = 1000
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def load_dim_game_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    query = f"""
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
            source_ids
        FROM {FANTASY_SCHEMA}.dim_game
        ORDER BY season, week, game_date, game_id
    """

    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(query),
            connection,
        )

    if seasons and not frame.empty and "season" in frame.columns:
        allowed = {int(season) for season in seasons}
        frame = frame[
            frame["season"].map(
                lambda value: (
                    int(value) in allowed
                    if not _is_missing(value)
                    else False
                )
            )
        ].reset_index(drop=True)

    if "source_ids" in frame.columns:
        frame["source_ids"] = frame["source_ids"].map(
            lambda value: (
                json.dumps(value, sort_keys=True)
                if isinstance(value, dict)
                else value
            )
        )
    return frame


def game_id_lookup_from_dim(
    dim: pd.DataFrame,
) -> dict[str, str]:
    """
    Map nflverse game_id -> InsightPilot game_id for fact joins.
    """

    lookup: dict[str, str] = {}
    for record in dim.to_dict(orient="records"):
        game_id = record.get("game_id")
        source_ids = record.get("source_ids") or {}
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except json.JSONDecodeError:
                source_ids = {}
        nflverse_game_id = None
        if isinstance(source_ids, dict):
            nflverse_game_id = _normalize_text(
                source_ids.get("nflverse_game_id")
            )
        if game_id and nflverse_game_id:
            lookup[nflverse_game_id] = str(game_id)
    return lookup
