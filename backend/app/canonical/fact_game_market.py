"""
fact_game_market — betting / environmental market context.

Separate from player market (fact_market) and from on-field
performance. One row per game × source snapshot.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.dim_game import (
    game_id_lookup_from_dim,
    get_dim_game,
)
from app.canonical.ids import (
    game_resolution_key,
    make_game_id,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_FACT_GAME_MARKET_CACHE: pd.DataFrame | None = None
_FACT_GAME_MARKET_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_GAME_MARKET_CACHE_SEASONS: tuple[int, ...] | None = None

FACT_GAME_MARKET_COLUMNS = [
    "game_id",
    "timestamp",
    "source",
    "spread",
    "over_under",
    "home_implied_total",
    "away_implied_total",
    "season",
    "week",
    "season_type",
    "source_ids",
]

MARKET_SOURCE = "nflverse_schedules"


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


def _normalize_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _season_type(value: Any) -> str | None:
    raw = _normalize_text(value)
    if raw is None:
        return None
    return raw.upper()


def _market_timestamp(
    gameday: Any,
    gametime: Any,
) -> str | None:
    day = _normalize_text(gameday)
    if day is None:
        return None
    # Normalize date portion.
    parsed_day = pd.to_datetime(day, errors="coerce")
    if _is_missing(parsed_day):
        return None
    date_part = parsed_day.strftime("%Y-%m-%d")
    time_part = _normalize_text(gametime)
    if time_part:
        # nflverse gametime is typically "HH:MM:SS" or "HH:MM".
        if len(time_part) == 5:
            time_part = f"{time_part}:00"
        return f"{date_part}T{time_part}"
    return f"{date_part}T00:00:00"


def _implied_totals(
    spread: float | None,
    over_under: float | None,
) -> tuple[float | None, float | None]:
    """
    nflverse spread_line: positive means home favored by that
    many points. Implied team totals follow:

      home = (ou / 2) + (spread / 2)
      away = (ou / 2) - (spread / 2)
    """

    if spread is None or over_under is None:
        return None, None
    home = (over_under / 2.0) + (spread / 2.0)
    away = (over_under / 2.0) - (spread / 2.0)
    return home, away


def _load_schedules(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_schedules(seasons=seasons))


def build_fact_game_market(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
    game_id_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved_seasons = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    schedules = raw.get("schedules")
    if schedules is None:
        schedules = _load_schedules(resolved_seasons)
    else:
        schedules = schedules.copy()
    if schedules.empty:
        raise ValueError(
            "Unable to build fact_game_market: no schedule "
            "rows were available."
        )

    if game_id_lookup is None:
        dim_game = get_dim_game(
            seasons=resolved_seasons,
            force_refresh=False,
            persist=persist,
        )
        game_lookup = game_id_lookup_from_dim(dim_game)
    else:
        game_lookup = game_id_lookup

    records: list[dict[str, Any]] = []
    for row in schedules.to_dict(orient="records"):
        nflverse_game_id = _normalize_text(row.get("game_id"))
        if not nflverse_game_id:
            continue

        spread = _normalize_float(row.get("spread_line"))
        over_under = _normalize_float(row.get("total_line"))
        if spread is None and over_under is None:
            continue

        game_id = game_lookup.get(nflverse_game_id)
        if game_id is None:
            try:
                game_id = make_game_id(
                    game_resolution_key(
                        nflverse_game_id=nflverse_game_id,
                    )
                )
            except ValueError:
                continue

        timestamp = _market_timestamp(
            row.get("gameday"),
            row.get("gametime"),
        )
        home_implied, away_implied = _implied_totals(
            spread,
            over_under,
        )

        source_ids: dict[str, str] = {
            "nflverse_game_id": nflverse_game_id,
        }
        home = _normalize_text(row.get("home_team"))
        away = _normalize_text(row.get("away_team"))
        if home:
            source_ids["home_team"] = home.upper()
        if away:
            source_ids["away_team"] = away.upper()

        records.append(
            {
                "game_id": game_id,
                "timestamp": timestamp,
                "source": MARKET_SOURCE,
                "spread": spread,
                "over_under": over_under,
                "home_implied_total": home_implied,
                "away_implied_total": away_implied,
                "season": _normalize_int(row.get("season")),
                "week": _normalize_int(row.get("week")),
                "season_type": _season_type(
                    row.get("game_type")
                    or row.get("season_type")
                ),
                "source_ids": source_ids,
                "resolution_key": (
                    f"{nflverse_game_id}:{MARKET_SOURCE}:"
                    f"{timestamp or 'unknown'}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build fact_game_market: no games with "
            "betting lines were available."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_GAME_MARKET_COLUMNS + ["resolution_key"]:
        if column == "source_ids" or column not in fact.columns:
            continue
        fact[column] = fact[column].astype("object")
        fact[column] = fact[column].where(
            fact[column].notna(),
            None,
        )

    fact = fact.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_GAME_MARKET_CACHE
    global _FACT_GAME_MARKET_CACHE_WITH_KEYS
    global _FACT_GAME_MARKET_CACHE_SEASONS
    _FACT_GAME_MARKET_CACHE_WITH_KEYS = fact.copy()
    _FACT_GAME_MARKET_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_game_market(fact)

    output = fact[FACT_GAME_MARKET_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "timestamp", "game_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_GAME_MARKET_CACHE = output.copy()
    return output


def fact_game_market_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_game_market"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_game_market(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_GAME_MARKET_CACHE
    global _FACT_GAME_MARKET_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_GAME_MARKET_CACHE is not None
        and not _FACT_GAME_MARKET_CACHE.empty
        and _FACT_GAME_MARKET_CACHE_SEASONS == tuple(resolved)
    ):
        return _FACT_GAME_MARKET_CACHE.copy()

    if not force_refresh and fact_game_market_count() > 0:
        frame = load_fact_game_market_from_db(seasons=resolved)
        if not frame.empty:
            _FACT_GAME_MARKET_CACHE = frame.copy()
            _FACT_GAME_MARKET_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_fact_game_market(
        resolved,
        persist=persist,
    )


def upsert_fact_game_market(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_game_market (
            game_id,
            timestamp,
            source,
            spread,
            over_under,
            home_implied_total,
            away_implied_total,
            season,
            week,
            season_type,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :game_id,
            CAST(NULLIF(:timestamp, '') AS TIMESTAMP),
            :source,
            :spread,
            :over_under,
            :home_implied_total,
            :away_implied_total,
            :season,
            :week,
            :season_type,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            game_id = EXCLUDED.game_id,
            timestamp = EXCLUDED.timestamp,
            source = EXCLUDED.source,
            spread = EXCLUDED.spread,
            over_under = EXCLUDED.over_under,
            home_implied_total = EXCLUDED.home_implied_total,
            away_implied_total = EXCLUDED.away_implied_total,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in fact.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(
                source_ids,
                sort_keys=True,
            )
        rows.append(
            {
                "game_id": record["game_id"],
                "timestamp": _sql_null_if_missing(
                    record.get("timestamp")
                ),
                "source": _sql_null_if_missing(
                    record.get("source")
                ),
                "spread": _sql_null_if_missing(
                    record.get("spread")
                ),
                "over_under": _sql_null_if_missing(
                    record.get("over_under")
                ),
                "home_implied_total": _sql_null_if_missing(
                    record.get("home_implied_total")
                ),
                "away_implied_total": _sql_null_if_missing(
                    record.get("away_implied_total")
                ),
                "season": _sql_null_if_missing(
                    record.get("season")
                ),
                "week": _sql_null_if_missing(
                    record.get("week")
                ),
                "season_type": _sql_null_if_missing(
                    record.get("season_type")
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


def load_fact_game_market_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_GAME_MARKET_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_game_market
        ORDER BY season, week, timestamp, game_id
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
