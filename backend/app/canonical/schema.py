"""
Canonical fantasy-model schema helpers.

Fantasy football dimensions live in the dedicated
`fantasy_football` Postgres schema so they stay organized
and leave room for other fantasy products later.
"""

from __future__ import annotations

from sqlalchemy import text

from app.database import engine


FANTASY_SCHEMA = "fantasy_football"
LEGACY_FANTASY_SCHEMA = "fantasy"


SCHEMA_STATEMENTS = [

    f"CREATE SCHEMA IF NOT EXISTS {FANTASY_SCHEMA}",

    # Rename/move tables from the short-lived `fantasy` schema.
    f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = '{LEGACY_FANTASY_SCHEMA}'
        ) THEN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = '{LEGACY_FANTASY_SCHEMA}'
                  AND table_name = 'dim_team'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = '{FANTASY_SCHEMA}'
                  AND table_name = 'dim_team'
            ) THEN
                EXECUTE 'ALTER TABLE {LEGACY_FANTASY_SCHEMA}.dim_team SET SCHEMA {FANTASY_SCHEMA}';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = '{LEGACY_FANTASY_SCHEMA}'
                  AND table_name = 'dim_player'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = '{FANTASY_SCHEMA}'
                  AND table_name = 'dim_player'
            ) THEN
                EXECUTE 'ALTER TABLE {LEGACY_FANTASY_SCHEMA}.dim_player SET SCHEMA {FANTASY_SCHEMA}';
            END IF;
        END IF;
    END $$;
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.dim_team (
        team_id TEXT PRIMARY KEY,
        team_name TEXT,
        team_abbreviation TEXT NOT NULL,
        conference TEXT,
        division TEXT,
        stadium TEXT,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_dim_team_abbreviation
    ON {FANTASY_SCHEMA}.dim_team (team_abbreviation)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.dim_player (
        player_id TEXT PRIMARY KEY,
        name TEXT,
        first_name TEXT,
        last_name TEXT,
        position TEXT,
        birth_date DATE,
        rookie_season INTEGER,
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
    idx_fantasy_football_dim_player_current_team_id
    ON {FANTASY_SCHEMA}.dim_player (current_team_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_dim_player_source_gsis
    ON {FANTASY_SCHEMA}.dim_player ((source_ids ->> 'gsis_id'))
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.dim_game (
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
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_dim_game_season_week
    ON {FANTASY_SCHEMA}.dim_game (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_dim_game_home_team_id
    ON {FANTASY_SCHEMA}.dim_game (home_team_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_dim_game_away_team_id
    ON {FANTASY_SCHEMA}.dim_game (away_team_id)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_player_game (
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
        pass_epa DOUBLE PRECISION,
        pass_cpoe DOUBLE PRECISION,
        rush_attempts INTEGER,
        rush_yards INTEGER,
        rush_tds INTEGER,
        rush_epa DOUBLE PRECISION,
        targets INTEGER,
        receptions INTEGER,
        receiving_yards INTEGER,
        receiving_tds INTEGER,
        receiving_epa DOUBLE PRECISION,
        fg_made INTEGER,
        fg_att INTEGER,
        fg_made_0_19 INTEGER,
        fg_made_20_29 INTEGER,
        fg_made_30_39 INTEGER,
        fg_made_40_49 INTEGER,
        fg_made_50_59 INTEGER,
        fg_made_60_ INTEGER,
        pat_made INTEGER,
        pat_att INTEGER,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, game_id)
    )
    """,

    # Backfill kicker columns on existing installs.
    f"""
    ALTER TABLE {FANTASY_SCHEMA}.fact_player_game
      ADD COLUMN IF NOT EXISTS fg_made INTEGER,
      ADD COLUMN IF NOT EXISTS fg_att INTEGER,
      ADD COLUMN IF NOT EXISTS fg_made_0_19 INTEGER,
      ADD COLUMN IF NOT EXISTS fg_made_20_29 INTEGER,
      ADD COLUMN IF NOT EXISTS fg_made_30_39 INTEGER,
      ADD COLUMN IF NOT EXISTS fg_made_40_49 INTEGER,
      ADD COLUMN IF NOT EXISTS fg_made_50_59 INTEGER,
      ADD COLUMN IF NOT EXISTS fg_made_60_ INTEGER,
      ADD COLUMN IF NOT EXISTS pat_made INTEGER,
      ADD COLUMN IF NOT EXISTS pat_att INTEGER
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_game_game_id
    ON {FANTASY_SCHEMA}.fact_player_game (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_game_season_week
    ON {FANTASY_SCHEMA}.fact_player_game (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_game_team_id
    ON {FANTASY_SCHEMA}.fact_player_game (team_id)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_player_usage (
        player_id TEXT NOT NULL,
        game_id TEXT NOT NULL,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        team_id TEXT,
        position TEXT,
        snap_count INTEGER,
        offensive_snap_share DOUBLE PRECISION,
        routes_run INTEGER,
        route_participation_rate DOUBLE PRECISION,
        rush_share DOUBLE PRECISION,
        touches INTEGER,
        touch_share DOUBLE PRECISION,
        red_zone_touches INTEGER,
        goal_line_carries INTEGER,
        inside_5_carries INTEGER,
        target_share DOUBLE PRECISION,
        air_yards INTEGER,
        air_yard_share DOUBLE PRECISION,
        red_zone_targets INTEGER,
        end_zone_targets INTEGER,
        dropbacks INTEGER,
        designed_rush_attempts INTEGER,
        scrambles INTEGER,
        qb_rush_share DOUBLE PRECISION,
        deep_pass_attempts INTEGER,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, game_id)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_usage_game_id
    ON {FANTASY_SCHEMA}.fact_player_usage (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_usage_season_week
    ON {FANTASY_SCHEMA}.fact_player_usage (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_usage_position
    ON {FANTASY_SCHEMA}.fact_player_usage (position)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_player_efficiency (
        player_id TEXT NOT NULL,
        game_id TEXT NOT NULL,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        team_id TEXT,
        position TEXT,
        yards_per_carry DOUBLE PRECISION,
        yards_per_target DOUBLE PRECISION,
        yards_per_route_run DOUBLE PRECISION,
        catch_rate DOUBLE PRECISION,
        td_rate DOUBLE PRECISION,
        pass_epa_per_dropback DOUBLE PRECISION,
        rush_epa_per_attempt DOUBLE PRECISION,
        fantasy_points_per_touch DOUBLE PRECISION,
        fantasy_points_per_route DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, game_id)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_efficiency_game_id
    ON {FANTASY_SCHEMA}.fact_player_efficiency (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_efficiency_season_week
    ON {FANTASY_SCHEMA}.fact_player_efficiency (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_player_efficiency_position
    ON {FANTASY_SCHEMA}.fact_player_efficiency (position)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_team_game (
        team_id TEXT NOT NULL,
        game_id TEXT NOT NULL,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        offensive_plays INTEGER,
        pass_attempts INTEGER,
        rush_attempts INTEGER,
        pass_rate DOUBLE PRECISION,
        neutral_pass_rate DOUBLE PRECISION,
        pace DOUBLE PRECISION,
        points INTEGER,
        yards DOUBLE PRECISION,
        offensive_epa DOUBLE PRECISION,
        pass_epa DOUBLE PRECISION,
        rush_epa DOUBLE PRECISION,
        red_zone_trips INTEGER,
        red_zone_td_rate DOUBLE PRECISION,
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
    idx_fantasy_football_fact_team_game_game_id
    ON {FANTASY_SCHEMA}.fact_team_game (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_team_game_season_week
    ON {FANTASY_SCHEMA}.fact_team_game (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_defensive_game (
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
        pass_epa_allowed DOUBLE PRECISION,
        rush_epa_allowed DOUBLE PRECISION,
        pressure_rate DOUBLE PRECISION,
        sack_rate DOUBLE PRECISION,
        targets_allowed INTEGER,
        receptions_allowed INTEGER,
        receiving_yards_allowed DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (defensive_team_id, game_id)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_defensive_game_game_id
    ON {FANTASY_SCHEMA}.fact_defensive_game (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_defensive_game_opponent
    ON {FANTASY_SCHEMA}.fact_defensive_game (opponent_team_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_defensive_game_season_week
    ON {FANTASY_SCHEMA}.fact_defensive_game (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_injury (
        player_id TEXT NOT NULL,
        team_id TEXT,
        report_date DATE,
        game_id TEXT,
        season INTEGER,
        week INTEGER,
        season_type TEXT,
        injury_type TEXT,
        practice_status TEXT,
        game_status TEXT,
        is_expected_to_play BOOLEAN,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (resolution_key)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_injury_player_id
    ON {FANTASY_SCHEMA}.fact_injury (player_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_injury_game_id
    ON {FANTASY_SCHEMA}.fact_injury (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_injury_season_week
    ON {FANTASY_SCHEMA}.fact_injury (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_injury_report_date
    ON {FANTASY_SCHEMA}.fact_injury (report_date)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_dfs_salary (
        player_id TEXT NOT NULL,
        site TEXT NOT NULL,
        contest_type TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        team TEXT,
        position TEXT,
        player_name TEXT,
        salary INTEGER NOT NULL,
        match_score DOUBLE PRECISION,
        source_name TEXT,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (resolution_key)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_dfs_salary_lookup
    ON {FANTASY_SCHEMA}.fact_dfs_salary (
        site, contest_type, season, week
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_dfs_salary_player_id
    ON {FANTASY_SCHEMA}.fact_dfs_salary (player_id)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_depth_chart (
        team_id TEXT,
        player_id TEXT NOT NULL,
        position TEXT,
        depth_order INTEGER,
        role TEXT,
        effective_date DATE,
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
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_depth_chart_player_id
    ON {FANTASY_SCHEMA}.fact_depth_chart (player_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_depth_chart_team_id
    ON {FANTASY_SCHEMA}.fact_depth_chart (team_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_depth_chart_season_week
    ON {FANTASY_SCHEMA}.fact_depth_chart (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_depth_chart_role
    ON {FANTASY_SCHEMA}.fact_depth_chart (role)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_market (
        player_id TEXT NOT NULL,
        season INTEGER,
        week INTEGER,
        source TEXT NOT NULL,
        rank DOUBLE PRECISION,
        projection DOUBLE PRECISION,
        adp DOUBLE PRECISION,
        ownership DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (resolution_key)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_market_player_id
    ON {FANTASY_SCHEMA}.fact_market (player_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_market_season_week
    ON {FANTASY_SCHEMA}.fact_market (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_market_source
    ON {FANTASY_SCHEMA}.fact_market (source)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_game_market (
        game_id TEXT NOT NULL,
        timestamp TIMESTAMP,
        source TEXT NOT NULL,
        spread DOUBLE PRECISION,
        over_under DOUBLE PRECISION,
        home_implied_total DOUBLE PRECISION,
        away_implied_total DOUBLE PRECISION,
        opening_spread DOUBLE PRECISION,
        opening_over_under DOUBLE PRECISION,
        opening_home_implied_total DOUBLE PRECISION,
        opening_away_implied_total DOUBLE PRECISION,
        opening_captured_at TIMESTAMP,
        line_moved_at TIMESTAMP,
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

    # Opening / line-move columns on existing installs.
    f"""
    ALTER TABLE {FANTASY_SCHEMA}.fact_game_market
      ADD COLUMN IF NOT EXISTS opening_spread DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_over_under DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_home_implied_total DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_away_implied_total DOUBLE PRECISION,
      ADD COLUMN IF NOT EXISTS opening_captured_at TIMESTAMP,
      ADD COLUMN IF NOT EXISTS line_moved_at TIMESTAMP
    """,

    # Seed opening from the earliest known current line.
    f"""
    UPDATE {FANTASY_SCHEMA}.fact_game_market
    SET
      opening_spread = COALESCE(opening_spread, spread),
      opening_over_under = COALESCE(opening_over_under, over_under),
      opening_home_implied_total = COALESCE(
        opening_home_implied_total, home_implied_total
      ),
      opening_away_implied_total = COALESCE(
        opening_away_implied_total, away_implied_total
      ),
      opening_captured_at = COALESCE(
        opening_captured_at, created_at, CURRENT_TIMESTAMP
      )
    WHERE opening_spread IS NULL
       OR opening_over_under IS NULL
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_game_market_game_id
    ON {FANTASY_SCHEMA}.fact_game_market (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_game_market_season_week
    ON {FANTASY_SCHEMA}.fact_game_market (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fact_game_market_source
    ON {FANTASY_SCHEMA}.fact_game_market (source)
    """,

    # Analytical layer — fantasy intelligence (derived from facts).
    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.player_usage_trend (
        player_id TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        snap_share_3wk DOUBLE PRECISION,
        target_share_3wk DOUBLE PRECISION,
        rush_share_3wk DOUBLE PRECISION,
        route_participation_3wk DOUBLE PRECISION,
        target_share_change DOUBLE PRECISION,
        snap_share_change DOUBLE PRECISION,
        opportunity_trend DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, season, week)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_usage_trend_season_week
    ON {FANTASY_SCHEMA}.player_usage_trend (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.player_opportunity (
        player_id TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        opportunity_score DOUBLE PRECISION,
        receiving_opportunity_score DOUBLE PRECISION,
        rushing_opportunity_score DOUBLE PRECISION,
        red_zone_opportunity_score DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, season, week)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_opportunity_season_week
    ON {FANTASY_SCHEMA}.player_opportunity (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.player_efficiency (
        player_id TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        efficiency_score DOUBLE PRECISION,
        receiving_efficiency DOUBLE PRECISION,
        rushing_efficiency DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, season, week)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_efficiency_season_week
    ON {FANTASY_SCHEMA}.player_efficiency (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.player_matchup (
        player_id TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        matchup_score DOUBLE PRECISION,
        pass_matchup_score DOUBLE PRECISION,
        rush_matchup_score DOUBLE PRECISION,
        receiving_matchup_score DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, season, week)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_matchup_season_week
    ON {FANTASY_SCHEMA}.player_matchup (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.player_environment (
        player_id TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        game_environment_score DOUBLE PRECISION,
        team_total DOUBLE PRECISION,
        pace_expectation DOUBLE PRECISION,
        game_script_expectation DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, season, week)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_environment_season_week
    ON {FANTASY_SCHEMA}.player_environment (season, week)
    """,

    # InsightPilot proprietary intelligence.
    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.player_fantasy_profile (
        player_id TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        production_score DOUBLE PRECISION,
        opportunity_score DOUBLE PRECISION,
        efficiency_score DOUBLE PRECISION,
        trend_score DOUBLE PRECISION,
        matchup_score DOUBLE PRECISION,
        environment_score DOUBLE PRECISION,
        risk_score DOUBLE PRECISION,
        fantasy_value_score DOUBLE PRECISION,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, season, week)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_fantasy_profile_season_week
    ON {FANTASY_SCHEMA}.player_fantasy_profile (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_fantasy_profile_value
    ON {FANTASY_SCHEMA}.player_fantasy_profile (fantasy_value_score)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fantasy_signal (
        signal_id TEXT NOT NULL,
        player_id TEXT NOT NULL,
        season INTEGER NOT NULL,
        week INTEGER NOT NULL,
        signal_type TEXT NOT NULL,
        signal_strength DOUBLE PRECISION,
        direction TEXT,
        confidence DOUBLE PRECISION,
        supporting_metrics JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        resolution_key TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (signal_id)
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fantasy_signal_player_week
    ON {FANTASY_SCHEMA}.fantasy_signal (player_id, season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fantasy_signal_type
    ON {FANTASY_SCHEMA}.fantasy_signal (signal_type)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_fantasy_signal_season_week
    ON {FANTASY_SCHEMA}.fantasy_signal (season, week)
    """,

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.ingestion_state (
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

    f"""
    CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.player_correlation (
        resolution_key TEXT PRIMARY KEY,
        player_id TEXT NOT NULL,
        correlated_player_id TEXT NOT NULL,
        game_id TEXT,
        season INTEGER,
        week INTEGER,
        correlation_type TEXT NOT NULL,
        correlation_score DOUBLE PRECISION NOT NULL,
        correlation_reason TEXT,
        confidence TEXT,
        confidence_score DOUBLE PRECISION,
        source TEXT NOT NULL DEFAULT 'structural',
        rule_id TEXT,
        sport TEXT NOT NULL DEFAULT 'nfl',
        source_ids JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_correlation_season_week
    ON {FANTASY_SCHEMA}.player_correlation (season, week)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_correlation_game_id
    ON {FANTASY_SCHEMA}.player_correlation (game_id)
    """,

    f"""
    CREATE INDEX IF NOT EXISTS
    idx_fantasy_football_player_correlation_type
    ON {FANTASY_SCHEMA}.player_correlation (correlation_type)
    """,

    # Move any legacy public.dim_player rows into fantasy_football.
    f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'dim_player'
        ) THEN
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
                created_at,
                updated_at
            )
            SELECT
                player_id,
                name,
                first_name,
                last_name,
                position,
                birth_date,
                rookie_season,
                NULL,
                status,
                source_ids,
                resolution_key,
                created_at,
                updated_at
            FROM public.dim_player
            ON CONFLICT (resolution_key) DO NOTHING;

            DROP TABLE public.dim_player;
        END IF;
    END $$;
    """,
]


_schema_ready = False


def ensure_canonical_schema() -> None:
    """
    Create canonical tables once per process.

    Slate reads used to replay every CREATE statement on each
    lookup, which dominated Sports Betting load time.
    """

    global _schema_ready
    if _schema_ready:
        return

    with engine.begin() as connection:

        for statement in SCHEMA_STATEMENTS:

            connection.execute(
                text(statement)
            )

    _schema_ready = True
