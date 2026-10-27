"""
Postgres schema for multi-sport odds (non-football leagues).

Stores ScoresAndOdds / Action Network consensus lines keyed by
provider game id until league-specific dim_game tables exist.
"""

from __future__ import annotations

from sqlalchemy import text

from app.database import engine

SPORTS_ODDS_SCHEMA = "sports_odds"

_SCHEMA_STATEMENTS = (
    f"CREATE SCHEMA IF NOT EXISTS {SPORTS_ODDS_SCHEMA}",
    f"""
    CREATE TABLE IF NOT EXISTS {SPORTS_ODDS_SCHEMA}.fact_game_market (
        league TEXT NOT NULL,
        game_id TEXT NOT NULL,
        game_date DATE,
        timestamp TIMESTAMP,
        source TEXT NOT NULL,
        spread DOUBLE PRECISION,
        over_under DOUBLE PRECISION,
        home_implied_total DOUBLE PRECISION,
        away_implied_total DOUBLE PRECISION,
        home_moneyline DOUBLE PRECISION,
        away_moneyline DOUBLE PRECISION,
        opening_spread DOUBLE PRECISION,
        opening_over_under DOUBLE PRECISION,
        opening_home_implied_total DOUBLE PRECISION,
        opening_away_implied_total DOUBLE PRECISION,
        opening_captured_at TIMESTAMP,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        home_abbr TEXT,
        away_abbr TEXT,
        home_name TEXT,
        away_name TEXT,
        start_time TIMESTAMP,
        status TEXT,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (resolution_key)
    )
    """,
    f"""
    CREATE INDEX IF NOT EXISTS
    idx_sports_odds_fact_game_market_league_season
    ON {SPORTS_ODDS_SCHEMA}.fact_game_market (league, season)
    """,
    f"""
    CREATE INDEX IF NOT EXISTS
    idx_sports_odds_fact_game_market_game
    ON {SPORTS_ODDS_SCHEMA}.fact_game_market (game_id)
    """,
    f"""
    CREATE INDEX IF NOT EXISTS
    idx_sports_odds_fact_game_market_game_date
    ON {SPORTS_ODDS_SCHEMA}.fact_game_market (league, game_date)
    """,
)


def ensure_sports_odds_schema() -> None:
    with engine.begin() as connection:
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(text(statement))
