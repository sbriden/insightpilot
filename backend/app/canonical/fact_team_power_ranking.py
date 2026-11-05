"""
Persisted team power-ranking snapshots (NFL + CFB).

Historical weeks are append-only for a given calculation_version —
rebuilding the same sport/season/week/version replaces that snapshot only.
NFL rows live in fantasy_football; CFB rows in college_football.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.betting_sport import (
    SPORT_CFB,
    SPORT_NFL,
    resolve_betting_sport,
)
from app.canonical.cfb.schema import ensure_college_schema
from app.canonical.schema import ensure_canonical_schema
from app.database import engine

_schema_ready: set[str] = set()


def _table_sql(schema: str) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {schema}.fact_team_power_ranking (
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    team_id TEXT NOT NULL,
    team_abbreviation TEXT,
    team_name TEXT,
    rank INTEGER NOT NULL,
    previous_rank INTEGER,
    rank_change INTEGER,
    overall_power_rating DOUBLE PRECISION NOT NULL,
    offensive_rating DOUBLE PRECISION NOT NULL,
    defensive_rating DOUBLE PRECISION NOT NULL,
    special_teams_rating DOUBLE PRECISION NOT NULL,
    baseline_power_rating DOUBLE PRECISION NOT NULL,
    current_adjusted_rating DOUBLE PRECISION NOT NULL,
    personnel_adjustment DOUBLE PRECISION NOT NULL DEFAULT 0,
    recent_form DOUBLE PRECISION,
    strength_of_schedule DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    effective_games DOUBLE PRECISION,
    rating_trend DOUBLE PRECISION,
    explanation TEXT,
    calculation_version TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    PRIMARY KEY (season, week, team_id, calculation_version)
)
"""


def _index_sql(schema: str) -> str:
    return f"""
CREATE INDEX IF NOT EXISTS idx_fact_team_power_ranking_season_week
ON {schema}.fact_team_power_ranking (season, week)
"""


def _schema_for_sport(sport: str | None) -> str:
    return resolve_betting_sport(sport or SPORT_NFL).schema


def ensure_power_ranking_tables(sport: str | None = None) -> None:
    sport_id = resolve_betting_sport(sport or SPORT_NFL).id
    if sport_id in _schema_ready:
        return
    if sport_id == SPORT_CFB:
        ensure_college_schema()
    else:
        ensure_canonical_schema()
    schema = _schema_for_sport(sport_id)
    with engine.begin() as connection:
        connection.execute(text(_table_sql(schema)))
        connection.execute(text(_index_sql(schema)))
    _schema_ready.add(sport_id)


def persist_power_ranking_snapshot(payload: dict[str, Any]) -> int:
    sport = str(payload.get("sport") or SPORT_NFL)
    ensure_power_ranking_tables(sport)
    schema = _schema_for_sport(sport)
    season = int(payload["season"])
    week = int(payload["week"])
    version = str(payload.get("calculation_version") or "power_rankings.v1")
    calculated_at = payload.get("calculated_at") or datetime.now(
        timezone.utc
    ).isoformat()
    rankings = list(payload.get("rankings") or [])
    if not rankings:
        return 0

    delete_sql = text(
        f"""
        DELETE FROM {schema}.fact_team_power_ranking
        WHERE season = :season
          AND week = :week
          AND calculation_version = :version
        """
    )
    insert_sql = text(
        f"""
        INSERT INTO {schema}.fact_team_power_ranking (
            season, week, team_id, team_abbreviation, team_name,
            rank, previous_rank, rank_change,
            overall_power_rating, offensive_rating, defensive_rating,
            special_teams_rating, baseline_power_rating,
            current_adjusted_rating, personnel_adjustment,
            recent_form, strength_of_schedule, confidence,
            effective_games, rating_trend, explanation,
            calculation_version, calculated_at, payload
        ) VALUES (
            :season, :week, :team_id, :team_abbreviation, :team_name,
            :rank, :previous_rank, :rank_change,
            :overall_power_rating, :offensive_rating, :defensive_rating,
            :special_teams_rating, :baseline_power_rating,
            :current_adjusted_rating, :personnel_adjustment,
            :recent_form, :strength_of_schedule, :confidence,
            :effective_games, :rating_trend, :explanation,
            :calculation_version, CAST(:calculated_at AS TIMESTAMPTZ),
            CAST(:payload AS JSONB)
        )
        """
    )
    meta = {
        key: payload.get(key)
        for key in (
            "sport",
            "half_life_weeks",
            "prior_k",
            "home_field_advantage",
            "league_avg_ppg",
            "data_limitations",
            "opponent_adjustment_iterations",
        )
    }
    with engine.begin() as connection:
        connection.execute(
            delete_sql,
            {"season": season, "week": week, "version": version},
        )
        for row in rankings:
            connection.execute(
                insert_sql,
                {
                    "season": season,
                    "week": week,
                    "team_id": row["team_id"],
                    "team_abbreviation": row.get("team_abbreviation"),
                    "team_name": row.get("team_name"),
                    "rank": int(row["rank"]),
                    "previous_rank": row.get("previous_rank"),
                    "rank_change": row.get("rank_change"),
                    "overall_power_rating": row["overall_power_rating"],
                    "offensive_rating": row["offensive_rating"],
                    "defensive_rating": row["defensive_rating"],
                    "special_teams_rating": row["special_teams_rating"],
                    "baseline_power_rating": row["baseline_power_rating"],
                    "current_adjusted_rating": row[
                        "current_adjusted_rating"
                    ],
                    "personnel_adjustment": row.get(
                        "personnel_adjustment"
                    )
                    or 0.0,
                    "recent_form": row.get("recent_form"),
                    "strength_of_schedule": row.get(
                        "strength_of_schedule"
                    ),
                    "confidence": row.get("confidence"),
                    "effective_games": row.get("effective_games"),
                    "rating_trend": row.get("rating_trend"),
                    "explanation": row.get("explanation"),
                    "calculation_version": version,
                    "calculated_at": calculated_at,
                    "payload": json.dumps(
                        {**row, "snapshot_meta": meta},
                        sort_keys=True,
                    ),
                },
            )
    return len(rankings)


def load_power_rankings_snapshot(
    *,
    season: int,
    week: int,
    sport: str | None = None,
    calculation_version: str | None = None,
) -> dict[str, Any]:
    sport_id = resolve_betting_sport(sport or SPORT_NFL).id
    ensure_power_ranking_tables(sport_id)
    schema = _schema_for_sport(sport_id)
    version = calculation_version or "power_rankings.v1.6"
    # Fall back through prior versions during transition.
    version_fallbacks = (
        version,
        "power_rankings.v1.5",
        "power_rankings.v1.4",
        "power_rankings.v1.3",
        "power_rankings.v1.2",
        "power_rankings.v1.1",
        "power_rankings.v1",
    )
    sql = text(
        f"""
        SELECT *
        FROM {schema}.fact_team_power_ranking
        WHERE season = :season
          AND week = :week
          AND calculation_version = :version
        ORDER BY rank ASC
        """
    )
    rows: list[dict[str, Any]] = []
    resolved_version = version
    with engine.connect() as connection:
        for candidate in version_fallbacks:
            rows = [
                dict(row)
                for row in connection.execute(
                    sql,
                    {
                        "season": int(season),
                        "week": int(week),
                        "version": candidate,
                    },
                ).mappings()
            ]
            if rows:
                resolved_version = candidate
                break
    return {
        "sport": sport_id,
        "season": int(season),
        "week": int(week),
        "calculation_version": resolved_version,
        "team_count": len(rows),
        "rankings": [_public_row(row) for row in rows],
        "persisted": True,
    }


def load_latest_power_rankings(
    *,
    season: int,
    sport: str | None = None,
    calculation_version: str | None = None,
) -> dict[str, Any]:
    sport_id = resolve_betting_sport(sport or SPORT_NFL).id
    ensure_power_ranking_tables(sport_id)
    schema = _schema_for_sport(sport_id)
    version = calculation_version or "power_rankings.v1.6"
    version_fallbacks = (
        version,
        "power_rankings.v1.5",
        "power_rankings.v1.4",
        "power_rankings.v1.3",
        "power_rankings.v1.2",
        "power_rankings.v1.1",
        "power_rankings.v1",
    )
    sql = text(
        f"""
        SELECT MAX(week) AS week
        FROM {schema}.fact_team_power_ranking
        WHERE season = :season
          AND calculation_version = :version
        """
    )
    week = None
    resolved_version = version
    with engine.connect() as connection:
        for candidate in version_fallbacks:
            week = connection.execute(
                sql,
                {"season": int(season), "version": candidate},
            ).scalar()
            if week is not None:
                resolved_version = candidate
                break
    if week is None:
        return {
            "sport": sport_id,
            "season": int(season),
            "week": None,
            "rankings": [],
            "team_count": 0,
            "persisted": False,
        }
    return load_power_rankings_snapshot(
        season=season,
        week=int(week),
        sport=sport_id,
        calculation_version=resolved_version,
    )


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

    public = {
        "team_id": row.get("team_id"),
        "team_abbreviation": row.get("team_abbreviation"),
        "team_name": row.get("team_name"),
        "season": row.get("season"),
        "week": row.get("week"),
        "rank": row.get("rank"),
        "previous_rank": row.get("previous_rank"),
        "rank_change": row.get("rank_change"),
        "overall_power_rating": row.get("overall_power_rating"),
        "offensive_rating": row.get("offensive_rating"),
        "defensive_rating": row.get("defensive_rating"),
        "special_teams_rating": row.get("special_teams_rating"),
        "baseline_power_rating": row.get("baseline_power_rating"),
        "current_adjusted_rating": row.get("current_adjusted_rating"),
        "personnel_adjustment": row.get("personnel_adjustment"),
        "form_adjustment": payload.get("form_adjustment"),
        "sos_adjustment": payload.get("sos_adjustment"),
        "record_adjustment": payload.get("record_adjustment"),
        "wins": payload.get("wins"),
        "losses": payload.get("losses"),
        "ties": payload.get("ties"),
        "win_pct": payload.get("win_pct"),
        "recent_form": row.get("recent_form"),
        "strength_of_schedule": row.get("strength_of_schedule"),
        "confidence": row.get("confidence"),
        "effective_games": row.get("effective_games"),
        "rating_trend": row.get("rating_trend"),
        "explanation": row.get("explanation"),
        "calculation_version": row.get("calculation_version"),
        "calculated_at": (
            row.get("calculated_at").isoformat()
            if hasattr(row.get("calculated_at"), "isoformat")
            else row.get("calculated_at")
        ),
        "logo_url": payload.get("logo_url"),
        "conference": payload.get("conference"),
        "sport": payload.get("sport")
        or (
            payload.get("snapshot_meta") or {}
        ).get("sport"),
    }
    return {key: value for key, value in public.items() if value is not None}
