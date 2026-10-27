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

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS bet_status TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS bet_label TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS tape_source TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS bet_line_source TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS closing_line_source TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS clv_available BOOLEAN;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS market_probability_source TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_market_result
  ADD COLUMN IF NOT EXISTS reference_probability DOUBLE PRECISION;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_projection_snapshot
  ADD COLUMN IF NOT EXISTS tape_source TEXT;

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_residual_challenger (
    season INTEGER NOT NULL PRIMARY KEY,
    method TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    sample_size INTEGER NOT NULL DEFAULT 0,
    model_version TEXT,
    model_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    mae_home DOUBLE PRECISION,
    mae_away DOUBLE PRECISION,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_score_distribution (
    season INTEGER NOT NULL PRIMARY KEY,
    method TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    sample_size INTEGER NOT NULL DEFAULT 0,
    model_version TEXT,
    model_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    sigma_home DOUBLE PRECISION,
    sigma_away DOUBLE PRECISION,
    rho DOUBLE PRECISION,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_context_ablation (
    season INTEGER NOT NULL PRIMARY KEY,
    report_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    best_group TEXT,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_qualification_thresholds (
    season INTEGER NOT NULL PRIMARY KEY,
    method TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    sample_size INTEGER NOT NULL DEFAULT 0,
    model_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    strong_edge_pp DOUBLE PRECISION,
    strong_ev_pct DOUBLE PRECISION,
    lean_edge_pp DOUBLE PRECISION,
    lean_ev_pct DOUBLE PRECISION,
    holdout_strong_roi DOUBLE PRECISION,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_projection_snapshot
  ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{{}}'::jsonb;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_projection_snapshot
  ADD COLUMN IF NOT EXISTS model_version TEXT;

ALTER TABLE {FANTASY_SCHEMA}.fact_betting_projection_snapshot
  ADD COLUMN IF NOT EXISTS decision_at TIMESTAMP;

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_model_promotion (
    season INTEGER NOT NULL,
    component TEXT NOT NULL,
    decision TEXT NOT NULL,
    active_model TEXT NOT NULL DEFAULT 'champion',
    candidate_version TEXT,
    sample_size INTEGER NOT NULL DEFAULT 0,
    champion_mae DOUBLE PRECISION,
    challenger_mae DOUBLE PRECISION,
    relative_improvement DOUBLE PRECISION,
    bootstrap_confidence DOUBLE PRECISION,
    report_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    note TEXT,
    decided_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (season, component)
);

CREATE TABLE IF NOT EXISTS {FANTASY_SCHEMA}.fact_betting_learning_report (
    season INTEGER NOT NULL PRIMARY KEY,
    report_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    n_settled INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
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
    import json

    payload = snapshot.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_projection_snapshot (
            game_id, season, week, home_team, away_team,
            projected_home_score, projected_away_score, projected_total,
            model_spread, market_spread, market_total,
            market_home_score, market_away_score,
            captured_at, frozen, payload, model_version, decision_at,
            tape_source, updated_at
        ) VALUES (
            :game_id, :season, :week, :home_team, :away_team,
            :projected_home_score, :projected_away_score, :projected_total,
            :model_spread, :market_spread, :market_total,
            :market_home_score, :market_away_score,
            CAST(:captured_at AS TIMESTAMP), :frozen,
            CAST(:payload AS JSONB), :model_version,
            CAST(:decision_at AS TIMESTAMP), :tape_source,
            CURRENT_TIMESTAMP
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
            payload = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.payload
                ELSE EXCLUDED.payload
            END,
            model_version = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.model_version
                ELSE EXCLUDED.model_version
            END,
            decision_at = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.decision_at
                ELSE EXCLUDED.decision_at
            END,
            tape_source = CASE
                WHEN {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen
                THEN COALESCE(
                    {FANTASY_SCHEMA}.fact_betting_projection_snapshot.tape_source,
                    EXCLUDED.tape_source
                )
                ELSE EXCLUDED.tape_source
            END,
            frozen = EXCLUDED.frozen OR
                {FANTASY_SCHEMA}.fact_betting_projection_snapshot.frozen,
            updated_at = CURRENT_TIMESTAMP
    """
    decision_at = (
        snapshot.get("decision_at")
        or (payload.get("decision_at") if isinstance(payload, dict) else None)
        or snapshot.get("captured_at")
        or datetime.now(timezone.utc).isoformat()
    )
    # Preserve unverified when missing — do not invent provenance.
    tape_source = snapshot.get("tape_source")
    if tape_source is None and isinstance(payload, dict):
        tape_source = payload.get("tape_source")
    params = {
        "game_id": snapshot.get("game_id"),
        "season": snapshot.get("season"),
        "week": snapshot.get("week"),
        "home_team": snapshot.get("home_team"),
        "away_team": snapshot.get("away_team"),
        "projected_home_score": snapshot.get("projected_home_score"),
        "projected_away_score": snapshot.get("projected_away_score"),
        "projected_total": snapshot.get("projected_total"),
        "model_spread": snapshot.get("model_spread"),
        "market_spread": snapshot.get("market_spread"),
        "market_total": snapshot.get("market_total"),
        "market_home_score": snapshot.get("market_home_score"),
        "market_away_score": snapshot.get("market_away_score"),
        "frozen": frozen,
        "captured_at": snapshot.get("captured_at")
        or datetime.now(timezone.utc).isoformat(),
        "payload": json.dumps(payload, sort_keys=True, default=str),
        "model_version": snapshot.get("model_version"),
        "decision_at": decision_at,
        "tape_source": tape_source,
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
            confidence, bet_status, bet_label, result, model_correct,
            home_score, away_score,
            actual_total, actual_spread, model_home_score, model_away_score,
            model_total, model_spread, market_spread, market_total,
            total_error, spread_error, closing_line, bet_line, bet_price,
            closing_price, clv, clv_unit, beat_close, clv_available,
            tape_source, bet_line_source, closing_line_source,
            market_probability_source, reference_probability,
            event_label,
            home_team, away_team, projection_captured_at, settled_at, source
        ) VALUES (
            :market_id, :game_id, :season, :week, :market_type, :selection,
            :line, :price, :model_probability, :raw_model_probability,
            :market_probability, :edge,
            :confidence, :bet_status, :bet_label, :result, :model_correct,
            :home_score, :away_score,
            :actual_total, :actual_spread, :model_home_score, :model_away_score,
            :model_total, :model_spread, :market_spread, :market_total,
            :total_error, :spread_error, :closing_line, :bet_line, :bet_price,
            :closing_price, :clv, :clv_unit, :beat_close, :clv_available,
            :tape_source, :bet_line_source, :closing_line_source,
            :market_probability_source, :reference_probability,
            :event_label,
            :home_team, :away_team,
            CAST(:projection_captured_at AS TIMESTAMP),
            CAST(:settled_at AS TIMESTAMP), :source
        )
        ON CONFLICT (market_id) DO UPDATE SET
            selection = EXCLUDED.selection,
            line = EXCLUDED.line,
            price = EXCLUDED.price,
            market_probability = EXCLUDED.market_probability,
            edge = EXCLUDED.edge,
            confidence = EXCLUDED.confidence,
            bet_status = COALESCE(
                EXCLUDED.bet_status,
                {FANTASY_SCHEMA}.fact_betting_market_result.bet_status
            ),
            bet_label = COALESCE(
                EXCLUDED.bet_label,
                {FANTASY_SCHEMA}.fact_betting_market_result.bet_label
            ),
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
            clv_available = EXCLUDED.clv_available,
            tape_source = EXCLUDED.tape_source,
            bet_line_source = EXCLUDED.bet_line_source,
            closing_line_source = EXCLUDED.closing_line_source,
            market_probability_source = EXCLUDED.market_probability_source,
            reference_probability = EXCLUDED.reference_probability,
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
                    "bet_status": row.get("bet_status"),
                    "bet_label": row.get("bet_label"),
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
                    "clv_available": row.get("clv_available"),
                    "tape_source": row.get("tape_source"),
                    "bet_line_source": row.get("bet_line_source"),
                    "closing_line_source": row.get("closing_line_source"),
                    "market_probability_source": row.get(
                        "market_probability_source"
                    ),
                    "reference_probability": row.get(
                        "reference_probability"
                    ),
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


def upsert_residual_challenger(
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

    metrics = model.get("metrics") or {}
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_residual_challenger (
            season, method, active, sample_size, model_version,
            model_json, mae_home, mae_away, note, updated_at
        ) VALUES (
            :season, :method, :active, :sample_size, :model_version,
            CAST(:model_json AS JSONB), :mae_home, :mae_away,
            :note, CURRENT_TIMESTAMP
        )
        ON CONFLICT (season) DO UPDATE SET
            method = EXCLUDED.method,
            active = EXCLUDED.active,
            sample_size = EXCLUDED.sample_size,
            model_version = EXCLUDED.model_version,
            model_json = EXCLUDED.model_json,
            mae_home = EXCLUDED.mae_home,
            mae_away = EXCLUDED.mae_away,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "method": str(model.get("method") or "prior"),
        "active": bool(model.get("active")),
        "sample_size": int(model.get("sample_size") or 0),
        "model_version": model.get("model_version"),
        "model_json": json.dumps(model, sort_keys=True, default=str),
        "mae_home": metrics.get("mae_home"),
        "mae_away": metrics.get("mae_away"),
        "note": model.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_residual_challenger(season: int) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_residual_challenger
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
            return None
    except Exception:
        return None


def upsert_score_distribution(
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
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_score_distribution (
            season, method, active, sample_size, model_version,
            model_json, sigma_home, sigma_away, rho, note, updated_at
        ) VALUES (
            :season, :method, :active, :sample_size, :model_version,
            CAST(:model_json AS JSONB), :sigma_home, :sigma_away,
            :rho, :note, CURRENT_TIMESTAMP
        )
        ON CONFLICT (season) DO UPDATE SET
            method = EXCLUDED.method,
            active = EXCLUDED.active,
            sample_size = EXCLUDED.sample_size,
            model_version = EXCLUDED.model_version,
            model_json = EXCLUDED.model_json,
            sigma_home = EXCLUDED.sigma_home,
            sigma_away = EXCLUDED.sigma_away,
            rho = EXCLUDED.rho,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "method": str(model.get("method") or "prior"),
        "active": bool(model.get("active")),
        "sample_size": int(model.get("sample_size") or 0),
        "model_version": model.get("model_version"),
        "model_json": json.dumps(model, sort_keys=True, default=str),
        "sigma_home": model.get("sigma_home"),
        "sigma_away": model.get("sigma_away"),
        "rho": model.get("rho"),
        "note": model.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_score_distribution(season: int) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_score_distribution
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
            return None
    except Exception:
        return None


def upsert_context_ablation(
    report: dict[str, Any],
    *,
    season: int,
) -> None:
    if not report:
        return
    try:
        ensure_betting_results_tables()
    except Exception:
        return
    import json

    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_context_ablation (
            season, report_json, best_group, note, updated_at
        ) VALUES (
            :season, CAST(:report_json AS JSONB), :best_group,
            :note, CURRENT_TIMESTAMP
        )
        ON CONFLICT (season) DO UPDATE SET
            report_json = EXCLUDED.report_json,
            best_group = EXCLUDED.best_group,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "report_json": json.dumps(report, sort_keys=True, default=str),
        "best_group": report.get("best_group"),
        "note": report.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_context_ablation(season: int) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_context_ablation
            WHERE season = :season
        """
        with engine.connect() as connection:
            row = connection.execute(
                text(sql), {"season": int(season)}
            ).mappings().first()
            if not row:
                return None
            payload = dict(row)
            report = payload.get("report_json")
            if isinstance(report, str):
                import json

                try:
                    report = json.loads(report)
                except json.JSONDecodeError:
                    report = {}
            if isinstance(report, dict):
                return {
                    **report,
                    "season": payload.get("season"),
                    "best_group": payload.get("best_group")
                    or report.get("best_group"),
                    "updated_at": (
                        payload.get("updated_at").isoformat()
                        if hasattr(payload.get("updated_at"), "isoformat")
                        else payload.get("updated_at")
                    ),
                }
            return None
    except Exception:
        return None


def upsert_qualification_thresholds(
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

    metrics = model.get("metrics") or {}
    strong = model.get("strong_bet") or {}
    lean = model.get("lean") or {}
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_qualification_thresholds (
            season, method, active, sample_size, model_json,
            strong_edge_pp, strong_ev_pct, lean_edge_pp, lean_ev_pct,
            holdout_strong_roi, note, updated_at
        ) VALUES (
            :season, :method, :active, :sample_size,
            CAST(:model_json AS JSONB),
            :strong_edge_pp, :strong_ev_pct, :lean_edge_pp, :lean_ev_pct,
            :holdout_strong_roi, :note, CURRENT_TIMESTAMP
        )
        ON CONFLICT (season) DO UPDATE SET
            method = EXCLUDED.method,
            active = EXCLUDED.active,
            sample_size = EXCLUDED.sample_size,
            model_json = EXCLUDED.model_json,
            strong_edge_pp = EXCLUDED.strong_edge_pp,
            strong_ev_pct = EXCLUDED.strong_ev_pct,
            lean_edge_pp = EXCLUDED.lean_edge_pp,
            lean_ev_pct = EXCLUDED.lean_ev_pct,
            holdout_strong_roi = EXCLUDED.holdout_strong_roi,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "method": str(model.get("method") or "prior"),
        "active": bool(model.get("active")),
        "sample_size": int(model.get("sample_size") or 0),
        "model_json": json.dumps(model, sort_keys=True, default=str),
        "strong_edge_pp": strong.get("min_edge_prob_pp"),
        "strong_ev_pct": strong.get("min_ev_pct"),
        "lean_edge_pp": lean.get("min_edge_prob_pp"),
        "lean_ev_pct": lean.get("min_ev_pct"),
        "holdout_strong_roi": metrics.get("holdout_strong_roi"),
        "note": model.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_qualification_thresholds(season: int) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_qualification_thresholds
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
            return None
    except Exception:
        return None


def upsert_model_promotion(
    report: dict[str, Any],
    *,
    season: int,
    component: str = "residual_challenger",
) -> None:
    if not report:
        return
    try:
        ensure_betting_results_tables()
    except Exception:
        return
    import json

    promotion = report.get("promotion") or report
    bootstrap = promotion.get("bootstrap") or {}
    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_model_promotion (
            season, component, decision, active_model, candidate_version,
            sample_size, champion_mae, challenger_mae, relative_improvement,
            bootstrap_confidence, report_json, note, decided_at, updated_at
        ) VALUES (
            :season, :component, :decision, :active_model, :candidate_version,
            :sample_size, :champion_mae, :challenger_mae, :relative_improvement,
            :bootstrap_confidence, CAST(:report_json AS JSONB), :note,
            CAST(:decided_at AS TIMESTAMP), CURRENT_TIMESTAMP
        )
        ON CONFLICT (season, component) DO UPDATE SET
            decision = EXCLUDED.decision,
            active_model = EXCLUDED.active_model,
            candidate_version = EXCLUDED.candidate_version,
            sample_size = EXCLUDED.sample_size,
            champion_mae = EXCLUDED.champion_mae,
            challenger_mae = EXCLUDED.challenger_mae,
            relative_improvement = EXCLUDED.relative_improvement,
            bootstrap_confidence = EXCLUDED.bootstrap_confidence,
            report_json = EXCLUDED.report_json,
            note = EXCLUDED.note,
            decided_at = EXCLUDED.decided_at,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "component": str(component),
        "decision": str(promotion.get("decision") or "hold"),
        "active_model": str(
            promotion.get("active_model") or "champion"
        ),
        "candidate_version": promotion.get("candidate_version"),
        "sample_size": int(promotion.get("sample_size") or 0),
        "champion_mae": promotion.get("champion_projection_mae"),
        "challenger_mae": promotion.get("challenger_projection_mae"),
        "relative_improvement": promotion.get("relative_improvement"),
        "bootstrap_confidence": bootstrap.get("p_challenger_better"),
        "report_json": json.dumps(report, sort_keys=True, default=str),
        "note": promotion.get("note") or report.get("note"),
        "decided_at": promotion.get("decided_at")
        or datetime.now(timezone.utc).isoformat(),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_model_promotion(
    season: int,
    *,
    component: str = "residual_challenger",
) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_model_promotion
            WHERE season = :season AND component = :component
        """
        with engine.connect() as connection:
            row = connection.execute(
                text(sql),
                {"season": int(season), "component": str(component)},
            ).mappings().first()
            if not row:
                return None
            payload = dict(row)
            report_json = payload.get("report_json")
            if isinstance(report_json, str):
                import json

                try:
                    report_json = json.loads(report_json)
                except json.JSONDecodeError:
                    report_json = {}
            return {
                "season": payload.get("season"),
                "component": payload.get("component"),
                "decision": payload.get("decision"),
                "active_model": payload.get("active_model") or "champion",
                "candidate_version": payload.get("candidate_version"),
                "sample_size": payload.get("sample_size"),
                "champion_mae": payload.get("champion_mae"),
                "challenger_mae": payload.get("challenger_mae"),
                "relative_improvement": payload.get(
                    "relative_improvement"
                ),
                "bootstrap_confidence": payload.get(
                    "bootstrap_confidence"
                ),
                "note": payload.get("note"),
                "report": (
                    report_json if isinstance(report_json, dict) else {}
                ),
                "decided_at": (
                    payload.get("decided_at").isoformat()
                    if hasattr(payload.get("decided_at"), "isoformat")
                    else payload.get("decided_at")
                ),
                "updated_at": (
                    payload.get("updated_at").isoformat()
                    if hasattr(payload.get("updated_at"), "isoformat")
                    else payload.get("updated_at")
                ),
            }
    except Exception:
        return None


def get_active_residual_model(season: int) -> str:
    """Return promoted apply target: champion or challenger."""

    row = get_model_promotion(
        int(season), component="residual_challenger"
    )
    if not row:
        return "champion"
    decision = str(row.get("decision") or "")
    active = str(row.get("active_model") or "champion").lower()
    if decision == "demote":
        return "champion"
    if decision == "promote" or active == "challenger":
        return "challenger"
    return "champion"


def upsert_learning_report(
    report: dict[str, Any],
    *,
    season: int,
) -> None:
    if not report:
        return
    try:
        ensure_betting_results_tables()
    except Exception:
        return
    import json

    sql = f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_betting_learning_report (
            season, report_json, n_settled, note, updated_at
        ) VALUES (
            :season, CAST(:report_json AS JSONB), :n_settled, :note,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (season) DO UPDATE SET
            report_json = EXCLUDED.report_json,
            n_settled = EXCLUDED.n_settled,
            note = EXCLUDED.note,
            updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "season": int(season),
        "report_json": json.dumps(report, sort_keys=True, default=str),
        "n_settled": int(report.get("n_settled") or 0),
        "note": report.get("note"),
    }
    try:
        with engine.begin() as connection:
            connection.execute(text(sql), params)
    except Exception:
        return


def get_learning_report(season: int) -> dict[str, Any] | None:
    try:
        ensure_betting_results_tables()
        sql = f"""
            SELECT *
            FROM {FANTASY_SCHEMA}.fact_betting_learning_report
            WHERE season = :season
        """
        with engine.connect() as connection:
            row = connection.execute(
                text(sql), {"season": int(season)}
            ).mappings().first()
            if not row:
                return None
            payload = dict(row)
            report_json = payload.get("report_json")
            if isinstance(report_json, str):
                import json

                try:
                    report_json = json.loads(report_json)
                except json.JSONDecodeError:
                    report_json = {}
            if isinstance(report_json, dict):
                return {
                    **report_json,
                    "season": payload.get("season"),
                    "updated_at": (
                        payload.get("updated_at").isoformat()
                        if hasattr(payload.get("updated_at"), "isoformat")
                        else payload.get("updated_at")
                    ),
                }
            return None
    except Exception:
        return None
