"""
College football canonical schema helpers.

Lives in the dedicated `college_football` Postgres schema so
NFL fantasy_football tables stay isolated.
"""

from __future__ import annotations

from sqlalchemy import text

from app.database import engine


COLLEGE_SCHEMA = "college_football"

SCHEMA_STATEMENTS = [

    f"CREATE SCHEMA IF NOT EXISTS {COLLEGE_SCHEMA}",

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.dim_team (
        team_id TEXT PRIMARY KEY,
        team_name TEXT,
        team_abbreviation TEXT NOT NULL,
        conference TEXT,
        division TEXT,
        subdivision TEXT,
        stadium TEXT,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_dim_team_abbreviation
    ON {COLLEGE_SCHEMA}.dim_team (team_abbreviation)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_dim_team_espn
    ON {COLLEGE_SCHEMA}.dim_team ((source_ids ->> 'espn_team_id'))
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.dim_player (
        player_id TEXT PRIMARY KEY,
        name TEXT,
        first_name TEXT,
        last_name TEXT,
        position TEXT,
        birth_date DATE,
        class_year TEXT,
        current_team_id TEXT,
        status TEXT,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_dim_player_team
    ON {COLLEGE_SCHEMA}.dim_player (current_team_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_dim_player_athlete
    ON {COLLEGE_SCHEMA}.dim_player ((source_ids ->> 'athlete_id'))
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.dim_game (
        game_id TEXT PRIMARY KEY,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        game_date DATE,
        home_team_id TEXT,
        away_team_id TEXT,
        home_score INTEGER,
        away_score INTEGER,
        game_status TEXT,
        neutral_site BOOLEAN,
        conference_game BOOLEAN,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_dim_game_season_week
    ON {COLLEGE_SCHEMA}.dim_game (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_dim_game_home
    ON {COLLEGE_SCHEMA}.dim_game (home_team_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_dim_game_away
    ON {COLLEGE_SCHEMA}.dim_game (away_team_id)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.fact_player_game (
        player_id TEXT NOT NULL,
        game_id TEXT NOT NULL,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        team_id TEXT,
        pass_attempts INTEGER,
        pass_completions INTEGER,
        pass_yards INTEGER,
        pass_tds INTEGER,
        interceptions INTEGER,
        rush_attempts INTEGER,
        rush_yards INTEGER,
        rush_tds INTEGER,
        targets INTEGER,
        receptions INTEGER,
        receiving_yards INTEGER,
        receiving_tds INTEGER,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, game_id)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_player_game_game
    ON {COLLEGE_SCHEMA}.fact_player_game (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_player_game_season_week
    ON {COLLEGE_SCHEMA}.fact_player_game (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.fact_team_game (
        team_id TEXT NOT NULL,
        game_id TEXT NOT NULL,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        offensive_plays INTEGER,
        pass_attempts INTEGER,
        rush_attempts INTEGER,
        pass_rate DOUBLE PRECISION,
        points INTEGER,
        yards DOUBLE PRECISION,
        turnovers INTEGER,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (team_id, game_id)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_team_game_game
    ON {COLLEGE_SCHEMA}.fact_team_game (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_team_game_season_week
    ON {COLLEGE_SCHEMA}.fact_team_game (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.fact_defensive_game (
        defensive_team_id TEXT NOT NULL,
        opponent_team_id TEXT,
        game_id TEXT NOT NULL,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        points_allowed INTEGER,
        yards_allowed DOUBLE PRECISION,
        pass_yards_allowed DOUBLE PRECISION,
        rush_yards_allowed DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (defensive_team_id, game_id)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_defensive_game_game
    ON {COLLEGE_SCHEMA}.fact_defensive_game (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_defensive_game_season_week
    ON {COLLEGE_SCHEMA}.fact_defensive_game (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.fact_game_market (
        game_id TEXT NOT NULL,
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
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (resolution_key)
    )
    """,

    f"""
    ALTER TABLE {COLLEGE_SCHEMA}.fact_game_market
      ADD COLUMN IF NOT EXISTS opening_spread DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_over_under DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_home_implied_total DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_away_implied_total DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_captured_at TIMESTAMP
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_game_market_game
    ON {COLLEGE_SCHEMA}.fact_game_market (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_college_football_fact_game_market_season_week
    ON {COLLEGE_SCHEMA}.fact_game_market (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {COLLEGE_SCHEMA}.ingestion_state (
        job_key TEXT PRIMARY KEY,
        mode TEXT NOT NULL,
        seasons INTEGER[] NOT NULL DEFAULT '{{}}',
        layers TEXT[] NOT NULL DEFAULT '{{}}',
        datasets_completed TEXT[] NOT NULL DEFAULT '{{}}',
        current_season INTEGER,
        status TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL,
        finished_at TIMESTAMP,
        row_count_total INTEGER NOT NULL DEFAULT 0,
        detail JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


_schema_ready = False


def ensure_college_schema() -> None:
    """Create college_football tables once per process."""

    global _schema_ready
    if _schema_ready:
        return

    with engine.begin() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(text(statement))

    _schema_ready = True
