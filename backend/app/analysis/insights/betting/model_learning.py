"""
Continuous learning: prediction snapshots and post-settle evaluation.

Every pregame view is stored with features, model versions, odds, and
decision timestamp. After settlement we measure residuals, calibration,
CLV, and cohort performance so model changes are judged by evidence —
not by ad-hoc weight tweaks after a bad week.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.results import (
    build_projection_snapshot,
    filter_learning_rows,
)


def build_enriched_prediction_snapshot(
    event: dict[str, Any],
    markets: list[dict[str, Any]] | None = None,
    *,
    model_versions: dict[str, Any] | None = None,
    prefer_opening: bool = False,
) -> dict[str, Any]:
    """
    Pregame prediction log for one game.

    Extends the projection tape with feature snapshot, model versions,
    per-market probabilities / odds, and decision metadata.
    """

    from app.analysis.insights.betting.results import (
        build_bet_tape_snapshot,
    )

    if prefer_opening:
        snap = build_bet_tape_snapshot(event, prefer_opening=True)
    else:
        snap = build_projection_snapshot(event)

    residual_meta = (
        (event.get("team_strength") or {}).get("residuals")
        or (event.get("strength") or {}).get("residuals")
        or event.get("residuals")
        or {}
    )
    feature_block = (
        residual_meta.get("feature_snapshot")
        or residual_meta.get("features")
        or event.get("residual_features")
    )
    decision_at = datetime.now(timezone.utc).isoformat()
    market_rows = []
    for market in markets or []:
        market_rows.append(
            {
                "market_id": market.get("market_id"),
                "market_type": market.get("market_type"),
                "selection": market.get("selection"),
                "offered_line": num(
                    market.get("offered_line")
                    if market.get("offered_line") is not None
                    else market.get("line")
                ),
                "offered_odds": num(
                    market.get("offered_odds")
                    if market.get("offered_odds") is not None
                    else market.get("price")
                ),
                "model_probability": num(
                    market.get("model_probability")
                ),
                "raw_model_probability": num(
                    market.get("raw_model_probability")
                ),
                "push_probability": num(
                    market.get("push_probability")
                ),
                "market_probability": num(
                    market.get("market_probability")
                ),
                "expected_value": num(market.get("expected_value")),
                "edge_probability": num(
                    market.get("edge_probability")
                ),
                "confidence": market.get("confidence"),
                "bet_status": market.get("bet_status"),
                "bet_label": market.get("bet_label"),
                "bet_qualified": bool(market.get("bet_qualified")),
                "probability_calibrated": bool(
                    market.get("probability_calibrated")
                ),
            }
        )

    payload = {
        "feature_snapshot": feature_block,
        "model_versions": model_versions or _model_versions_from_event(
            event
        ),
        "applied_residual_model": (
            residual_meta.get("applied_model")
            or (event.get("residual_model"))
            or "champion"
        ),
        "probabilities": market_rows,
        "decision_at": decision_at,
        "event_status": event.get("status"),
        "uncertainty": {
            "score_distribution": (
                (event.get("score_distribution") or {}).get(
                    "uncertainty"
                )
            ),
            "model_disagreement": event.get("model_disagreement"),
        },
    }
    snap["payload"] = payload
    snap["decision_at"] = decision_at
    snap["model_version"] = (
        (payload.get("model_versions") or {}).get("bundle")
        or (payload.get("model_versions") or {}).get(
            "residual_challenger"
        )
    )
    return snap


def _model_versions_from_event(event: dict[str, Any]) -> dict[str, Any]:
    residual_meta = (
        (event.get("team_strength") or {}).get("residuals")
        or (event.get("strength") or {}).get("residuals")
        or {}
    )
    chall = residual_meta.get("challenger") or {}
    score_dist = event.get("score_distribution") or {}
    return {
        "residual_applied": residual_meta.get("applied_model")
        or "champion",
        "residual_challenger": chall.get("model_version"),
        "residual_challenger_method": chall.get("method"),
        "score_distribution": score_dist.get("model_version"),
        "bundle": (
            f"challenger={(chall.get('model_version') or 'none')}"
            f"|dist={(score_dist.get('model_version') or 'none')}"
        ),
    }


def evaluate_settled_learning(
    settled: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Post-settle evaluation: residuals, calibration surface, CLV, and
    breakdowns by market / edge bucket / confidence.
    """

    rows = list(settled or [])
    learn_rows, cohort = filter_learning_rows(rows)

    residuals = _residual_summary(rows)
    calibration = _probability_calibration_summary(learn_rows)
    clv = _clv_summary(learn_rows)
    betting = _betting_result_summary(learn_rows)
    by_market = _group_metrics(learn_rows, "market_type")
    by_edge = _group_metrics(learn_rows, "edge_bucket")
    by_confidence = _group_metrics(learn_rows, "confidence")

    return {
        "available": bool(rows),
        "n_settled": len(rows),
        "n_learning": len(learn_rows),
        "learning_cohort": cohort,
        "residuals": residuals,
        "probability_calibration": calibration,
        "clv": clv,
        "betting_results": betting,
        "by_market": by_market,
        "by_edge_bucket": by_edge,
        "by_confidence": by_confidence,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Evidence report for continuous learning. Residuals use "
            "all settled games; CLV / betting / calibration prefer "
            f"the {cohort} cohort."
        ),
    }


def _residual_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Score, margin (spread), and total residuals vs frozen projections."""

    games: dict[str, dict[str, Any]] = {}
    for row in rows:
        gid = str(row.get("game_id") or row.get("event_id") or "")
        if not gid or gid in games:
            continue
        games[gid] = row

    total_err: list[float] = []
    spread_err: list[float] = []
    home_err: list[float] = []
    away_err: list[float] = []
    for row in games.values():
        te = num(row.get("total_error"))
        se = num(row.get("spread_error"))
        if te is not None:
            total_err.append(float(te))
        if se is not None:
            spread_err.append(float(se))
        mh = num(row.get("model_home_score"))
        ma = num(row.get("model_away_score"))
        ah = num(row.get("home_score"))
        aa = num(row.get("away_score"))
        if mh is not None and ah is not None:
            home_err.append(float(mh) - float(ah))
        if ma is not None and aa is not None:
            away_err.append(float(ma) - float(aa))

    def _stats(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"n": 0, "mean": None, "mae": None, "rmse": None}
        n = len(values)
        mean = sum(values) / n
        mae = sum(abs(v) for v in values) / n
        rmse = (sum(v * v for v in values) / n) ** 0.5
        return {
            "n": n,
            "mean": round(mean, 3),
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
        }

    return {
        "games": len(games),
        "total": _stats(total_err),
        "margin": _stats(spread_err),
        "home_score": _stats(home_err),
        "away_score": _stats(away_err),
    }


def _probability_calibration_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    from app.analysis.insights.betting.probability_calibration import (
        fit_probability_calibration,
    )

    if len(rows) < 10:
        return {
            "available": False,
            "n": len(rows),
            "note": "Need at least 10 learning rows.",
        }
    fitted = fit_probability_calibration(rows, method="auto")
    return {
        "available": True,
        "n": len(rows),
        "method": (fitted or {}).get("method"),
        "active": bool((fitted or {}).get("active")),
        "metrics": (fitted or {}).get("metrics"),
        "note": (fitted or {}).get("note"),
    }


def _clv_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from app.analysis.insights.betting.clv import build_clv_diagnostics

    diag = build_clv_diagnostics(rows)
    summary = diag.get("summary") or {}
    return {
        "n": len(rows),
        "mean_clv": summary.get("average_clv"),
        "beat_close_rate": summary.get("beat_close_pct"),
        "by_market": diag.get("by_market_type"),
        "summary": summary,
    }


def _betting_result_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    decided = [
        r
        for r in rows
        if str(r.get("result") or "").lower() in {"won", "lost", "win", "loss"}
    ]
    wins = sum(
        1
        for r in decided
        if str(r.get("result") or "").lower() in {"won", "win"}
    )
    losses = len(decided) - wins
    # Unit PnL at -110 when price missing.
    pnl = 0.0
    for row in decided:
        result = str(row.get("result") or "").lower()
        price = num(row.get("bet_price") or row.get("price")) or -110.0
        if result in {"won", "win"}:
            if price < 0:
                pnl += 100.0 / abs(float(price))
            else:
                pnl += float(price) / 100.0
        elif result in {"lost", "loss"}:
            pnl -= 1.0
    n = len(decided)
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "win_rate": round(100.0 * wins / n, 1) if n else None,
        "unit_roi_pct": round(100.0 * pnl / n, 2) if n else None,
    }


def _group_metrics(
    rows: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if key == "edge_bucket":
            label = _edge_bucket(row)
        else:
            label = str(row.get(key) or "unknown")
        buckets[label].append(row)

    out: list[dict[str, Any]] = []
    for label, group in sorted(buckets.items()):
        betting = _betting_result_summary(group)
        clvs = [num(r.get("clv")) for r in group if num(r.get("clv")) is not None]
        out.append(
            {
                key if key != "edge_bucket" else "edge_bucket": label,
                "n": len(group),
                "win_rate": betting.get("win_rate"),
                "unit_roi_pct": betting.get("unit_roi_pct"),
                "mean_clv": (
                    round(sum(float(v) for v in clvs) / len(clvs), 3)
                    if clvs
                    else None
                ),
                "model_correct_rate": _model_correct_rate(group),
            }
        )
    return out


def _edge_bucket(row: dict[str, Any]) -> str:
    edge = num(row.get("edge_probability"))
    if edge is None:
        edge = num(row.get("edge"))
    if edge is None:
        return "unknown"
    e = abs(float(edge))
    if e < 1.5:
        return "0-1.5"
    if e < 3.0:
        return "1.5-3"
    if e < 5.0:
        return "3-5"
    return "5+"


def _model_correct_rate(rows: list[dict[str, Any]]) -> float | None:
    flagged = [r for r in rows if r.get("model_correct") is not None]
    if not flagged:
        return None
    correct = sum(1 for r in flagged if r.get("model_correct"))
    return round(100.0 * correct / len(flagged), 1)
