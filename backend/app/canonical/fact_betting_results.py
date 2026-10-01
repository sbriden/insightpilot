"""
Persist betting projection snapshots, settled market results,
and rolling calibration feedback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.canonical.schema import FANTASY_SCHEMA, ensure_canonical_schema
from app.database import engine


_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_projection_snapshot (
    game_id TEXT PRIMARY KEY,
    season INTEGER,
    week INTEGER,
    home_team TEXT,
    away_team TEXT,
    projected_home_score DOUBLE PRECISION,
    projected_away_score DOUBLE PRECISION,
    projected_total DOUBLE PRECISION,
    model_spread DOUBLE PRECISION,
    market_spread DOUBLE PRECISION,
    market_total DOUBLE PRECISION,
    market_home_score DOUBLE PRECISION,
    market_away_score DOUBLE PRECISION,
    captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    frozen BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_market_result (
    market_id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL,
    season INTEGER,
    week INTEGER,
    market_type TEXT,
    selection TEXT,
    line DOUBLE PRECISION,
    price DOUBLE PRECISION,
    model_probability DOUBLE PRECISION,
    market_probability DOUBLE PRECISION,
    edge DOUBLE PRECISION,
    confidence TEXT,
    result TEXT,
    model_correct BOOLEAN,
    home_score INTEGER,
    away_score INTEGER,
    actual_total DOUBLE PRECISION,
    actual_spread DOUBLE PRECISION,
    model_home_score DOUBLE PRECISION,
    model_away_score DOUBLE PRECISION,
    model_total DOUBLE PRECISION,
    model_spread DOUBLE PRECISION,
    market_spread DOUBLE PRECISION,
    market_total DOUBLE PRECISION,
    total_error DOUBLE PRECISION,
    spread_error DOUBLE PRECISION,
    closing_line DOUBLE PRECISION,
    event_label TEXT,
    home_team TEXT,
    away_team TEXT,
    projection_captured_at TIMESTAMP,
    settled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source TEXT,
    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb
);

CREATE INDEX IF NOT EXISTS
idx_fact_betting_market_result_season_week
ON {FANTASY_SCHEMA}.fact_betting_market_result (season, week);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_calibration (
    season INTEGER PRIMARY KEY,
    sample_games INTEGER NOT NULL DEFAULT 0,
    total_bias DOUBLE PRECISION NOT NULL DEFAULT 0,
    spread_bias DOUBLE PRECISION NOT NULL DEFAULT 0,
    raw_mean_total_error DOUBLE PRECISION,
    raw_mean_spread_error DOUBLE PRECISION,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    dampen DOUBLE PRECISION,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_probability_calibration (
    season INTEGER NOT NULL,
    market_type TEXT NOT NULL DEFAULT 'all',
    method TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    sample_size INTEGER NOT NULL DEFAULT 0,
    model_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    brier_raw DOUBLE PRECISION,
    brier_calibrated DOUBLE PRECISION,
    ece_raw DOUBLE PRECISION,
    ece_calibrated DOUBLE PRECISION,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (season, market_type)
);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_edge_confidence (
    season INTEGER NOT NULL PRIMARY KEY,
    method TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    sample_size INTEGER NOT NULL DEFAULT 0,
    high_min DOUBLE PRECISION,
    moderate_min DOUBLE PRECISION,
    model_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS raw_model_probability DOUBLE PRECISION;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS bet_line DOUBLE PRECISION;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS bet_price DOUBLE PRECISION;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS closing_price DOUBLE PRECISION;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS clv DOUBLE PRECISION;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS clv_unit TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS beat_close BOOLEAN;
"""


_betting_tables_ready = False


def ensure_betting_results_tables() -> None:
    """
    Create betting result tables once per process.

    Replaying this DDL on every snapshot read made the slate
    endpoint spend most of its time in schema setup.
    """

    global _betting_tables_ready
    if _betting_tables_ready:
        return
    ensure_canonical_schema()
    with engine.begin() as connection:
        for statement in _TABLE_SQL.split(";"):
            sql = statement.strip()
            if sql:
                connection.execute(text(sql))
    _betting_tables_ready = True


def upsert_projection_snapshot(
    snapshot: dict[str, Any],
    *,
    freeze: bool = False,
) -> None:
    if not snapshot.get("game_id"):
        return
    try:
        ensure_betting_results_tables()
    except Exception:
        return
    # Never overwrite a frozen snapshot with a live recompute.
    existing = get_projection_snapshot(str(snapshot["game_id"]))
    if existing and existing.get("frozen") and not freeze:
        return
    frozen = bool(freeze or (existing or {}).get("frozen"))
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_projection_snapshot (
            game_id, season, week, home_team, away_team,
            projected_home_score, projected_away_score, projected_total,
            model_spread, market_spread, market_total,
            market_home_score, market_away_score,
            captured_at, frozen, updated_at
        ) VALUES (
            :game_id, :season, :week, :home_team, :away_team,
            :projected_home_score, :projected_away_score, :projected_total,
            :model_spread, :market_spread, :market_total,
            :market_home_score, :market_away_score,
            CAST(:captured_at AS TIMESTAMP), :frozen, CURRENT_TIMESTAMP
        )
        ON CONFLICT (game_id) DO UPDATE SET
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            home_team = EXCLUDED.home_team,
            away_team = EXCLUDED.away_team,
            projected_home_score = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.projected_home_score
                ELSE EXCLUDED.projected_home_score
            END,
            projected_away_score = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.projected_away_score
                ELSE EXCLUDED.projected_away_score
            END,
            projected_total = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.projected_total
                ELSE EXCLUDED.projected_total
            END,
            model_spread = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.model_spread
                ELSE EXCLUDED.model_spread
            END,
            market_spread = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.market_spread
                ELSE EXCLUDED.market_spread
            END,
            market_total = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.market_total
                ELSE EXCLUDED.market_total
            END,
            market_home_score = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.market_home_score
                ELSE EXCLUDED.market_home_score
            END,
            market_away_score = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.market_away_score
                ELSE EXCLUDED.market_away_score
            END,
            captured_at = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.captured_at
                ELSE EXCLUDED.captured_at
            END,
            frozen = EXCLUDED.frozen OR
                {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        **snapshot,
        "frozen": frozen,
        "captured_at": snapshot.get("captured_at")
        or datetime.now(timezone.utc).isoformat(),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def freeze_projection_snapshot(game_id: str) -> dict[str, Any] | None:
    snap = get_projection_snapshot(game_id)
    if not snap:
        return None
    snap["frozen"] = True
    upsert_projection_snapshot(snap, freeze=True)
    return get_projection_snapshot(game_id)


def get_projection_snapshot(game_id: str) -> dict[str, Any] | None:
    if not game_id:
        return None
    found = get_projection_snapshots([game_id])
    return found.get(str(game_id))


def get_projection_snapshots(
    game_ids: list[str],
) -> dict[str, dict[str, Any]]:
    ids = [
        str(game_id).strip()
        for game_id in game_ids
        if str(game_id or "").strip()
    ]
    if not ids:
        return {}
    try:
        ensure_betting_results_tables()
        params = {
            f"id_{index}": game_id
            for index, game_id in enumerate(ids)
        }
        placeholders = ", ".join(
            f":id_{index}" for index in range(len(ids))
        )
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_projection_snapshot
            WHERE game_id IN ({placeholders})
        """
        with engine.connect() as connection:
            rows = connection.execute(
                text(sql), params
            ).mappings().all()
            return {
                str(row["game_id"]): dict(row)
                for row in rows
                if row.get("game_id")
            }
    except Exception:
        return {}


def upsert_market_results(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    try:
        ensure_betting_results_tables()
    except Exception:
        return 0
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_market_result (
            market_id, game_id, season, week, market_type, selection,
            line, price, model_probability, raw_model_probability,
            market_probability, edge,
            confidence, result, model_correct, home_score, away_score,
            actual_total, actual_spread, model_home_score, model_away_score,
            model_total, model_spread, market_spread, market_total,
            total_error, spread_error, closing_line, bet_line, bet_price,
            closing_price, clv, clv_unit, beat_close, event_label,
            home_team, away_team, projection_captured_at, settled_at, source
        ) VALUES (
            :market_id, :game_id, :season, :week, :market_type, :selection,
            :line, :price, :model_probability, :raw_model_probability,
            :market_probability, :edge,
            :confidence, :result, :model_correct, :home_score, :away_score,
            :actual_total, :actual_spread, :model_home_score, :model_away_score,
            :model_total, :model_spread, :market_spread, :market_total,
            :total_error, :spread_error, :closing_line, :bet_line, :bet_price,
            :closing_price, :clv, :clv_unit, :beat_close, :event_label,
            :home_team, :away_team,
            CAST(:projection_captured_at AS TIMESTAMP),
            CAST(:settled_at AS TIMESTAMP), :source
        )
        ON CONFLICT (market_id) DO UPDATE SET
            result = EXCLUDED.result,
            model_correct = EXCLUDED.model_correct,
            model_probability = COALESCE(
                EXCLUDED.model_probability,
                {FANTASY_SCHEMA}.fact_betting_market_result.model_probability
            ),
            raw_model_probability = COALESCE(
                EXCLUDED.raw_model_probability,
                {FANTASY_SCHEMA}.fact_betting_market_result.raw_model_probability
            ),
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score,
            actual_total = EXCLUDED.actual_total,
            actual_spread = EXCLUDED.actual_spread,
            total_error = EXCLUDED.total_error,
            spread_error = EXCLUDED.spread_error,
            closing_line = EXCLUDED.closing_line,
            bet_line = EXCLUDED.bet_line,
            bet_price = EXCLUDED.bet_price,
            closing_price = EXCLUDED.closing_price,
            clv = EXCLUDED.clv,
            clv_unit = EXCLUDED.clv_unit,
            beat_close = EXCLUDED.beat_close,
            settled_at = EXCLUDED.settled_at,
            source = EXCLUDED.source
    """
    written = 0
    try:
        with engine.begin() as connection:
            for row in rows:
                params = {
                    "market_id": row.get("market_id"),
                    "game_id": row.get("event_id"),
                    "season": row.get("season"),
                    "week": row.get("week"),
                    "market_type": row.get("market_type"),
                    "selection": row.get("selection"),
                    "line": row.get("line"),
                    "price": row.get("price"),
                    "model_probability": row.get("model_probability"),
                    "raw_model_probability": row.get(
                        "raw_model_probability"
                    ),
                    "market_probability": row.get("market_probability"),
                    "edge": row.get("edge"),
                    "confidence": row.get("confidence"),
                    "result": row.get("result"),
                    "model_correct": row.get("model_correct"),
                    "home_score": row.get("home_score"),
                    "away_score": row.get("away_score"),
                    "actual_total": row.get("actual_total"),
                    "actual_spread": row.get("actual_spread"),
                    "model_home_score": row.get("model_home_score"),
                    "model_away_score": row.get("model_away_score"),
                    "model_total": row.get("model_total"),
                    "model_spread": row.get("model_spread"),
                    "market_spread": row.get("market_spread"),
                    "market_total": row.get("market_total"),
                    "total_error": row.get("total_error"),
                    "spread_error": row.get("spread_error"),
                    "closing_line": row.get("closing_line"),
                    "bet_line": row.get("bet_line"),
                    "bet_price": row.get("bet_price"),
                    "closing_price": row.get("closing_price"),
                    "clv": row.get("clv"),
                    "clv_unit": row.get("clv_unit"),
                    "beat_close": row.get("beat_close"),
                    "event_label": row.get("event_label"),
                    "home_team": row.get("home_team"),
                    "away_team": row.get("away_team"),
                    "projection_captured_at": row.get(
                        "projection_captured_at"
                    ),
                    "settled_at": row.get("settled_at"),
                    "source": row.get("source"),
                }
                if not params["market_id"] or not params["game_id"]:
                    continue
                connection.execute(text(sql), params)
                written += 1
    except Exception:
        return 0
    return written


def load_market_results(
    *,
    season: int | None = None,
    week: int | None = None,
) -> list[dict[str, Any]]:
    try:
        ensure_betting_results_tables()
    except Exception:
        return []
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if season is not None:
        clauses.append("season = :season")
        params["season"] = int(season)
    if week is not None:
        clauses.append("week = :week")
        params["week"] = int(week)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT *
        FROM {FANTASY_SCHEMA}.fact_betting_market_result
        {where}
        ORDER BY week DESC NULLS LAST, settled_at DESC NULLS LAST
    """
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(sql), params).mappings()
            out = []
            for row in rows:
                item = dict(row)
                item["event_id"] = item.get("game_id")
                out.append(item)
            return out
    except Exception:
        return []


def upsert_calibration(feedback: dict[str, Any], *, season: int) -> None:
    try:
        ensure_betting_results_tables()
    except Exception:
        return
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_calibration (
            season, sample_games, total_bias, spread_bias,
            raw_mean_total_error, raw_mean_spread_error,
            active, dampen, note, updated_at
        ) VALUES (
            :season, :sample_games, :total_bias, :spread_bias,
            :raw_mean_total_error, :raw_mean_spread_error,
            :active, :dampen, :note, CURRENT_TIMESTAMP
        )
        ON CONFLICT (season) DO UPDATE SET
            sample_games = EXCLUDED.sample_games,
            total_bias = EXCLUDED.total_bias,
            spread_bias = EXCLUDED.spread_bias,
            raw_mean_total_error = EXCLUDED.raw_mean_total_error,
            raw_mean_spread_error = EXCLUDED.raw_mean_spread_error,
            active = EXCLUDED.active,
            dampen = EXCLUDED.dampen,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "sample_games": int(feedback.get("sample_games") or 0),
        "total_bias": float(feedback.get("total_bias") or 0.0),
        "spread_bias": float(feedback.get("spread_bias") or 0.0),
        "raw_mean_total_error": feedback.get("raw_mean_total_error"),
        "raw_mean_spread_error": feedback.get("raw_mean_spread_error"),
        "active": bool(feedback.get("active")),
        "dampen": feedback.get("dampen"),
        "note": feedback.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_calibration_feedback(season: int) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_calibration
            WHERE season = :season
        """
        with engine.connect() as connection:
            row = connection.execute(
                text(sql), {"season": int(season)}
            ).mappings().first()
            return dict(row) if row else None
    except Exception:
        return None


def upsert_probability_calibration(
    model: dict[str, Any],
    *,
    season: int,
    market_type: str = "all",
) -> None:
    if not model:
        return
    try:
        ensure_betting_results_tables()
    except Exception:
        return
    metrics = model.get("metrics") or {}
    mtype = str(
        market_type or model.get("market_type") or "all"
    ).lower()
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_probability_calibration (
            season, market_type, method, active, sample_size,
            model_json, brier_raw, brier_calibrated,
            ece_raw, ece_calibrated, note, updated_at
        ) VALUES (
            :season, :market_type, :method, :active, :sample_size,
            CAST(:model_json AS JSONB), :brier_raw, :brier_calibrated,
            :ece_raw, :ece_calibrated, :note, CURRENT_TIMESTAMP
        )
        ON CONFLICT (season, market_type) DO UPDATE SET
            method = EXCLUDED.method,
            active = EXCLUDED.active,
            sample_size = EXCLUDED.sample_size,
            model_json = EXCLUDED.model_json,
            brier_raw = EXCLUDED.brier_raw,
            brier_calibrated = EXCLUDED.brier_calibrated,
            ece_raw = EXCLUDED.ece_raw,
            ece_calibrated = EXCLUDED.ece_calibrated,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    import json

    params = {
        "season": int(season),
        "market_type": mtype,
        "method": str(model.get("method") or "identity"),
        "active": bool(model.get("active")),
        "sample_size": int(model.get("sample_size") or 0),
        "model_json": json.dumps(model, sort_keys=True, default=str),
        "brier_raw": metrics.get("brier_raw"),
        "brier_calibrated": metrics.get("brier_calibrated"),
        "ece_raw": metrics.get("ece_raw"),
        "ece_calibrated": metrics.get("ece_calibrated"),
        "note": model.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_probability_calibration(
    season: int,
    *,
    market_type: str = "all",
) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_probability_calibration
            WHERE season = :season
              AND market_type = :market_type
        """
        with engine.connect() as connection:
            row = connection.execute(
                text(sql),
                {
                    "season": int(season),
                    "market_type": str(market_type or "all").lower(),
                },
            ).mappings().first()
            if not row:
                return None
            payload = dict(row)
            model_json = payload.get("model_json")
            if isinstance(model_json, str):
                import json

                try:
                    model_json = json.loads(model_json)
                except json.JSONDecodeError:
                    model_json = {}
            if isinstance(model_json, dict):
                return {
                    **model_json,
                    "season": payload.get("season"),
                    "market_type": payload.get("market_type"),
                    "updated_at": (
                        payload.get("updated_at").isoformat()
                        if hasattr(payload.get("updated_at"), "isoformat")
                        else payload.get("updated_at")
                    ),
                }
            return None
    except Exception:
        return None

def upsert_edge_confidence(
    model: dict[str, Any],
    *,
    season: int,
) -> None:
    if not model:
        return
    try:
        ensure_betting_results_tables()
    except Exception:
        return
    import json

    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_edge_confidence (
            season, method, active, sample_size,
            high_min, moderate_min, model_json, note, updated_at
        ) VALUES (
            :season, :method, :active, :sample_size,
            :high_min, :moderate_min, CAST(:model_json AS JSONB),
            :note, CURRENT_TIMESTAMP
        )
        ON CONFLICT (season) DO UPDATE SET
            method = EXCLUDED.method,
            active = EXCLUDED.active,
            sample_size = EXCLUDED.sample_size,
            high_min = EXCLUDED.high_min,
            moderate_min = EXCLUDED.moderate_min,
            model_json = EXCLUDED.model_json,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "method": str(model.get("method") or "fallback"),
        "active": bool(model.get("active")),
        "sample_size": int(model.get("sample_size") or 0),
        "high_min": model.get("high_min"),
        "moderate_min": model.get("moderate_min"),
        "model_json": json.dumps(model, sort_keys=True, default=str),
        "note": model.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_edge_confidence(season: int) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_edge_confidence
            WHERE season = :season
        """
        with engine.connect() as connection:
            row = connection.execute(
                text(sql), {"season": int(season)}
            ).mappings().first()
            if not row:
                return None
            payload = dict(row)
            model_json = payload.get("model_json")
            if isinstance(model_json, str):
                import json

                try:
                    model_json = json.loads(model_json)
                except json.JSONDecodeError:
                    model_json = {}
            if isinstance(model_json, dict):
                return {
                    **model_json,
                    "season": payload.get("season"),
                    "updated_at": (
                        payload.get("updated_at").isoformat()
                        if hasattr(payload.get("updated_at"), "isoformat")
                        else payload.get("updated_at")
                    ),
                }
            return {
                "active": bool(payload.get("active")),
                "method": payload.get("method"),
                "sample_size": payload.get("sample_size"),
                "high_min": payload.get("high_min"),
                "moderate_min": payload.get("moderate_min"),
                "note": payload.get("note"),
                "season": payload.get("season"),
            }
    except Exception:
        return None
