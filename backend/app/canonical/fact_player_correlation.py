"""
fact_player_correlation — optional persistence of correlation edges.

Grain: one row per directed pair context (resolution_key).
Used to snapshot structural / empirical edges for a slate so
UI and audits can reload explainable relationships without
rebuilding the full engine context.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.analysis.insights.dfs.correlation import (
    CorrelationContext,
    correlation_edges_as_rows,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


FACT_PLAYER_CORRELATION_COLUMNS = [
    "resolution_key",
    "player_id",
    "correlated_player_id",
    "game_id",
    "season",
    "week",
    "correlation_type",
    "correlation_score",
    "correlation_reason",
    "confidence",
    "confidence_score",
    "source",
    "rule_id",
    "sport",
    "source_ids",
]


def correlation_resolution_key(
    *,
    player_id: str,
    correlated_player_id: str,
    season: int | None,
    week: int | None,
    game_id: str | None,
    sport: str = "nfl",
) -> str:
    a, b = sorted(
        [
            str(player_id).strip(),
            str(correlated_player_id).strip(),
        ]
    )
    return (
        f"{str(sport).strip().lower()}:"
        f"{season if season is not None else 'na'}:"
        f"{week if week is not None else 'na'}:"
        f"{str(game_id or 'na').strip()}:"
        f"{a}:{b}"
    )


def upsert_correlation_context(
    context: CorrelationContext,
    *,
    season: int | None = None,
    week: int | None = None,
    game_id: str | None = None,
) -> int:
    """Persist non-neutral edges from a live context. Returns row count."""

    rows = correlation_edges_as_rows(context)
    if not rows:
        return 0
    frame_rows: list[dict[str, Any]] = []
    for row in rows:
        pid = str(row["player_id"])
        cid = str(row["correlated_player_id"])
        frame_rows.append(
            {
                "resolution_key": correlation_resolution_key(
                    player_id=pid,
                    correlated_player_id=cid,
                    season=row.get("season") or season,
                    week=row.get("week") or week,
                    game_id=row.get("game_id") or game_id,
                    sport=context.sport,
                ),
                "player_id": pid,
                "correlated_player_id": cid,
                "game_id": row.get("game_id") or game_id,
                "season": row.get("season") or season,
                "week": row.get("week") or week,
                "correlation_type": row["correlation_type"],
                "correlation_score": float(row["correlation_score"]),
                "correlation_reason": row.get("correlation_reason"),
                "confidence": row.get("confidence"),
                "confidence_score": row.get("confidence_score"),
                "source": row.get("source") or "structural",
                "rule_id": row.get("rule_id"),
                "sport": context.sport,
                "source_ids": json.dumps({}),
            }
        )
    frame = pd.DataFrame(frame_rows)
    return _upsert_frame(frame)


def load_empirical_correlation_rows(
    *,
    season: int | None = None,
    week: int | None = None,
    game_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load stored empirical / blended rows for engine overlays."""

    clauses = ["source IN ('empirical', 'blended')"]
    params: dict[str, Any] = {}
    if season is not None:
        clauses.append("season = :season")
        params["season"] = int(season)
    if week is not None:
        clauses.append("week = :week")
        params["week"] = int(week)
    if game_id:
        clauses.append("game_id = :game_id")
        params["game_id"] = str(game_id)

    where = " AND ".join(clauses)
    query = f"""
        SELECT
            player_id,
            correlated_player_id,
            correlation_score,
            correlation_reason,
            confidence_score,
            source,
            rule_id
        FROM {FANTASY_SCHEMA}.player_correlation
        WHERE {where}
    """
    with engine.connect() as connection:
        frame = pd.read_sql(text(query), connection, params=params)
    if frame.empty:
        return []
    return frame.to_dict(orient="records")


def _upsert_frame(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    columns = FACT_PLAYER_CORRELATION_COLUMNS
    for col in columns:
        if col not in frame.columns:
            frame[col] = None
    frame = frame[columns]
    placeholders = ", ".join(f":{col}" for col in columns)
    col_list = ", ".join(columns)
    updates = ", ".join(
        f"{col} = EXCLUDED.{col}"
        for col in columns
        if col != "resolution_key"
    )
    sql = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.player_correlation (
            {col_list}
        ) VALUES ({placeholders})
        ON CONFLICT (resolution_key) DO UPDATE SET
            {updates},
            updated_at = CURRENT_TIMESTAMP
        """
    )
    records = frame.to_dict(orient="records")
    with engine.begin() as connection:
        connection.execute(sql, records)
    return len(records)
