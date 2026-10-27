"""fact_game_market — multi-sport betting lines (sports_odds schema)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.sports_odds.schema import (
    SPORTS_ODDS_SCHEMA,
    ensure_sports_odds_schema,
)
from app.database import engine

_CACHE: pd.DataFrame | None = None

FACT_COLUMNS = [
    "league",
    "game_id",
    "game_date",
    "timestamp",
    "source",
    "spread",
    "over_under",
    "home_implied_total",
    "away_implied_total",
    "home_moneyline",
    "away_moneyline",
    "opening_spread",
    "opening_over_under",
    "opening_home_implied_total",
    "opening_away_implied_total",
    "opening_captured_at",
    "season",
    "week",
    "season_type",
    "home_abbr",
    "away_abbr",
    "home_name",
    "away_name",
    "start_time",
    "status",
    "source_ids",
]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _sql_null_if_missing(value: Any) -> Any:
    if _is_missing(value):
        return None
    return value


def upsert_fact_game_market(fact: pd.DataFrame) -> None:
    if fact.empty:
        return

    ensure_sports_odds_schema()
    statement = text(
        f"""
        INSERT INTO {SPORTS_ODDS_SCHEMA}.fact_game_market (
            league, game_id, game_date, timestamp, source,
            spread, over_under,
            home_implied_total, away_implied_total,
            home_moneyline, away_moneyline,
            opening_spread, opening_over_under,
            opening_home_implied_total, opening_away_implied_total,
            opening_captured_at,
            season, week, season_type,
            home_abbr, away_abbr, home_name, away_name,
            start_time, status,
            source_ids, resolution_key, updated_at
        ) VALUES (
            :league, :game_id, CAST(:game_date AS DATE),
            CAST(:timestamp AS TIMESTAMP), :source,
            :spread, :over_under,
            :home_implied_total, :away_implied_total,
            :home_moneyline, :away_moneyline,
            :opening_spread, :opening_over_under,
            :opening_home_implied_total, :opening_away_implied_total,
            CAST(NULLIF(:opening_captured_at, '') AS TIMESTAMP),
            :season, :week, :season_type,
            :home_abbr, :away_abbr, :home_name, :away_name,
            CAST(:start_time AS TIMESTAMP), :status,
            CAST(:source_ids AS JSONB), :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            league = EXCLUDED.league,
            game_id = EXCLUDED.game_id,
            game_date = EXCLUDED.game_date,
            timestamp = EXCLUDED.timestamp,
            source = EXCLUDED.source,
            spread = EXCLUDED.spread,
            over_under = EXCLUDED.over_under,
            home_implied_total = EXCLUDED.home_implied_total,
            away_implied_total = EXCLUDED.away_implied_total,
            home_moneyline = EXCLUDED.home_moneyline,
            away_moneyline = EXCLUDED.away_moneyline,
            opening_spread = COALESCE(
                EXCLUDED.opening_spread,
                {SPORTS_ODDS_SCHEMA}.fact_game_market.opening_spread
            ),
            opening_over_under = COALESCE(
                EXCLUDED.opening_over_under,
                {SPORTS_ODDS_SCHEMA}.fact_game_market.opening_over_under
            ),
            opening_home_implied_total = COALESCE(
                EXCLUDED.opening_home_implied_total,
                {SPORTS_ODDS_SCHEMA}.fact_game_market.opening_home_implied_total
            ),
            opening_away_implied_total = COALESCE(
                EXCLUDED.opening_away_implied_total,
                {SPORTS_ODDS_SCHEMA}.fact_game_market.opening_away_implied_total
            ),
            opening_captured_at = COALESCE(
                EXCLUDED.opening_captured_at,
                {SPORTS_ODDS_SCHEMA}.fact_game_market.opening_captured_at
            ),
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            home_abbr = EXCLUDED.home_abbr,
            away_abbr = EXCLUDED.away_abbr,
            home_name = EXCLUDED.home_name,
            away_name = EXCLUDED.away_name,
            start_time = EXCLUDED.start_time,
            status = EXCLUDED.status,
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
                key: _sql_null_if_missing(record.get(key))
                for key in (
                    "league",
                    "game_id",
                    "game_date",
                    "timestamp",
                    "source",
                    "spread",
                    "over_under",
                    "home_implied_total",
                    "away_implied_total",
                    "home_moneyline",
                    "away_moneyline",
                    "opening_spread",
                    "opening_over_under",
                    "opening_home_implied_total",
                    "opening_away_implied_total",
                    "opening_captured_at",
                    "season",
                    "week",
                    "season_type",
                    "home_abbr",
                    "away_abbr",
                    "home_name",
                    "away_name",
                    "start_time",
                    "status",
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
                rows[start : start + batch_size],
            )


def load_fact_game_market_from_db(
    *,
    leagues: list[str] | None = None,
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    ensure_sports_odds_schema()
    cols = (
        ", ".join(FACT_COLUMNS[:-1])
        + ", source_ids::text AS source_ids"
    )
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if leagues:
        clauses.append("league = ANY(:leagues)")
        params["leagues"] = [str(league).lower() for league in leagues]
    if seasons:
        clauses.append("season = ANY(:seasons)")
        params["seasons"] = [int(season) for season in seasons]
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = text(
        f"""
        SELECT {cols}
        FROM {SPORTS_ODDS_SCHEMA}.fact_game_market
        {where}
        """
    )
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params=params)


def clear_fact_game_market_cache() -> None:
    global _CACHE
    _CACHE = None
