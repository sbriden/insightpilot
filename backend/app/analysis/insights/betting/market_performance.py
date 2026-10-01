"""
Per-market model performance.

Spread, total, and moneyline are separate models — do not roll
them into one hit rate. Track each with its own win metric, ROI,
CLV, MAE (where a projection exists), and probability calibration.

Confidence allocation then favors markets that historically
separate; weaker markets need more edge to reach High/Moderate.
"""

from __future__ import annotations

import statistics
from typing import Any

from app.analysis.insights.betting.edge_confidence import (
    BREAKEVEN_WIN_PCT,
    DEFAULT_HIGH_MIN,
    DEFAULT_MODERATE_MIN,
    fit_confidence_thresholds,
)
from app.analysis.insights.betting.pricing import num


MARKET_TYPES = ("spread", "total", "moneyline")

MARKET_LABELS = {
    "spread": "Spread",
    "total": "Total",
    "moneyline": "Moneyline",
}

WIN_METRIC_KEYS = {
    "spread": "ats_win_pct",
    "total": "ou_win_pct",
    "moneyline": "win_pct",
}

MIN_SAMPLES_FOR_WEIGHT = 15
MIN_SAMPLES_FOR_ACTIVE = 20


def build_market_performance(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Full per-market scorecard + confidence allocation weights.
    """

    from app.analysis.insights.betting.clv import (
        attach_clv_fields,
        unit_result,
    )

    enriched: list[dict[str, Any]] = []
    for row in rows or []:
        item = attach_clv_fields(dict(row))
        if num(item.get("units")) is None:
            item["units"] = unit_result(
                item.get("result"),
                item.get("bet_price", item.get("price")),
            )
        enriched.append(item)

    markets: dict[str, dict[str, Any]] = {}
    for mtype in MARKET_TYPES:
        subset = [
            row
            for row in enriched
            if str(row.get("market_type") or "").lower() == mtype
        ]
        markets[mtype] = _market_card(mtype, subset)

    ranking = sorted(
        MARKET_TYPES,
        key=lambda key: (
            float(markets[key].get("quality_score") or 0.0),
            int(markets[key].get("sample_size") or 0),
        ),
        reverse=True,
    )
    allocation = _allocate_confidence(markets)
    for mtype, adj in allocation.items():
        markets[mtype].update(adj)

    best = ranking[0] if ranking else None
    note = (
        "Each market is scored independently. Confidence floors "
        "tighten on weaker markets and ease on stronger ones."
    )
    if best and markets[best].get("sample_size", 0) >= MIN_SAMPLES_FOR_WEIGHT:
        note = (
            f"{MARKET_LABELS.get(best, best)} currently leads on "
            f"quality score "
            f"({markets[best].get('quality_score')}). "
            + note
        )

    return {
        "markets": markets,
        "ranking": ranking,
        "best_market": best,
        "note": note,
        "active": any(
            bool(markets[m].get("confidence_active"))
            for m in MARKET_TYPES
        ),
    }


def apply_market_confidence_thresholds(
    *,
    market_type: str | None,
    edge_points: float | None = None,
    edge_probability: float | None = None,
    model_coverage: bool = True,
    thresholds: dict[str, Any] | None = None,
    market_performance: dict[str, Any] | None = None,
) -> str:
    """
    Confidence label using global floors, then market-specific
    overrides from performance allocation when available.
    """

    from app.analysis.insights.betting.edge_confidence import (
        apply_confidence_thresholds,
    )

    mtype = str(market_type or "").lower() or None
    effective = dict(thresholds or {})

    # Prefer explicit by_market block on the edge-confidence model.
    by_market = (effective.get("by_market") or {}) if effective else {}
    market_floor = by_market.get(mtype) if mtype else None

    # Fall back to live market_performance allocation.
    if not market_floor and market_performance and mtype:
        card = (market_performance.get("markets") or {}).get(mtype)
        if card:
            market_floor = {
                "active": bool(card.get("confidence_active")),
                "high_min": card.get("high_min"),
                "moderate_min": card.get("moderate_min"),
                "weight": card.get("confidence_weight"),
            }

    if market_floor and (
        market_floor.get("active")
        or market_floor.get("high_min") is not None
    ):
        effective = {
            **effective,
            "active": True,
            "high_min": market_floor.get(
                "high_min", effective.get("high_min", DEFAULT_HIGH_MIN)
            ),
            "moderate_min": market_floor.get(
                "moderate_min",
                effective.get("moderate_min", DEFAULT_MODERATE_MIN),
            ),
        }

    return apply_confidence_thresholds(
        edge_points=edge_points,
        edge_probability=edge_probability,
        model_coverage=model_coverage,
        thresholds=effective or None,
    )


def merge_edge_confidence_with_markets(
    edge_model: dict[str, Any] | None,
    market_perf: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach per-market floors onto an edge-confidence payload."""

    base = dict(edge_model or {})
    by_market: dict[str, Any] = {}
    markets = (market_perf or {}).get("markets") or {}
    for mtype, card in markets.items():
        by_market[mtype] = {
            "active": bool(card.get("confidence_active")),
            "high_min": card.get("high_min"),
            "moderate_min": card.get("moderate_min"),
            "weight": card.get("confidence_weight"),
            "quality_score": card.get("quality_score"),
            "sample_size": card.get("sample_size"),
        }
    if by_market:
        base["by_market"] = by_market
    if market_perf and market_perf.get("note"):
        base["market_note"] = market_perf.get("note")
    return base


def _market_card(
    market_type: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    decided = [
        row for row in rows if row.get("result") in {"won", "lost"}
    ]
    won = [row for row in decided if row.get("result") == "won"]
    clvs = [
        float(row["clv"])
        for row in rows
        if num(row.get("clv")) is not None
    ]
    units = [
        float(row["units"])
        for row in decided
        if num(row.get("units")) is not None
    ]
    preds: list[float] = []
    actuals: list[float] = []
    for row in decided:
        pred = num(
            row.get("raw_model_probability", row.get("model_probability"))
        )
        if pred is None:
            continue
        preds.append(float(pred))
        actuals.append(1.0 if row.get("result") == "won" else 0.0)

    stake = float(len(decided))
    profit = sum(units) if units else 0.0
    win_rate = (
        round(100.0 * len(won) / len(decided), 1) if decided else None
    )
    roi_pct = (
        round(100.0 * profit / stake, 1) if stake > 0 else None
    )
    avg_clv = round(sum(clvs) / len(clvs), 2) if clvs else None
    median_clv = (
        round(float(statistics.median(clvs)), 2) if clvs else None
    )
    mae = _mae_for_market(market_type, rows)
    mean_pred = (
        round(100.0 * sum(preds) / len(preds), 1) if preds else None
    )
    cal_gap = (
        round(float(win_rate) - float(mean_pred), 1)
        if win_rate is not None and mean_pred is not None
        else None
    )
    brier = None
    if preds and actuals and len(preds) == len(actuals):
        brier = round(
            sum((p - a) ** 2 for p, a in zip(preds, actuals))
            / len(preds),
            4,
        )

    # Per-market edge thresholds from this market's history alone.
    edge_fit = fit_confidence_thresholds(rows)
    quality = _quality_score(
        win_rate=win_rate,
        roi_pct=roi_pct,
        average_clv=avg_clv,
        mae=mae,
        calibration_gap=cal_gap,
        sample_size=len(decided),
        market_type=market_type,
    )

    win_key = WIN_METRIC_KEYS[market_type]
    card: dict[str, Any] = {
        "market_type": market_type,
        "label": MARKET_LABELS[market_type],
        "key": market_type,
        "bets": len(rows),
        "sample_size": len(decided),
        "decided": len(decided),
        "correct": len(won),
        "hit_rate": win_rate,
        win_key: win_rate,
        "roi_pct": roi_pct,
        "units": round(profit, 2) if units else None,
        "average_clv": avg_clv,
        "median_clv": median_clv,
        "mae": mae,
        "mean_predicted_pct": mean_pred,
        "calibration_gap": cal_gap,
        "brier": brier,
        "calibration": {
            "mean_predicted_pct": mean_pred,
            "actual_win_pct": win_rate,
            "gap_pp": cal_gap,
            "brier": brier,
            "n": len(preds),
        },
        "quality_score": quality,
        "edge_thresholds": {
            "active": bool(edge_fit.get("active")),
            "high_min": edge_fit.get("high_min"),
            "moderate_min": edge_fit.get("moderate_min"),
            "sample_size": edge_fit.get("sample_size"),
            "note": edge_fit.get("note"),
        },
    }
    return card


def _mae_for_market(
    market_type: str,
    rows: list[dict[str, Any]],
) -> float | None:
    if market_type == "spread":
        errs = [
            abs(float(row["spread_error"]))
            for row in rows
            if num(row.get("spread_error")) is not None
        ]
        if not errs:
            # Fallback: model vs actual spread on the row.
            errs = []
            for row in rows:
                model = num(row.get("model_spread"))
                actual = num(row.get("actual_spread"))
                if model is not None and actual is not None:
                    errs.append(abs(float(model) - float(actual)))
        return round(sum(errs) / len(errs), 2) if errs else None

    if market_type == "total":
        errs = [
            abs(float(row["total_error"]))
            for row in rows
            if num(row.get("total_error")) is not None
        ]
        if not errs:
            errs = []
            for row in rows:
                model = num(row.get("model_total"))
                actual = num(row.get("actual_total"))
                if model is not None and actual is not None:
                    errs.append(abs(float(model) - float(actual)))
        return round(sum(errs) / len(errs), 2) if errs else None

    return None


def _quality_score(
    *,
    win_rate: float | None,
    roi_pct: float | None,
    average_clv: float | None,
    mae: float | None,
    calibration_gap: float | None,
    sample_size: int,
    market_type: str,
) -> float:
    """
    0–100 composite. Heavily sample-shrunk until enough decisions.
    """

    if sample_size <= 0:
        return 0.0

    score = 50.0
    if win_rate is not None:
        score += max(-20.0, min(20.0, float(win_rate) - BREAKEVEN_WIN_PCT))
    if roi_pct is not None:
        score += max(-15.0, min(15.0, float(roi_pct) * 0.5))
    if average_clv is not None:
        # Points for spread/total; pp for ML — both reward positive CLV.
        score += max(-10.0, min(10.0, float(average_clv) * 4.0))
    if calibration_gap is not None:
        # Prefer small absolute miscalibration.
        score -= min(10.0, abs(float(calibration_gap)) * 0.5)
    if mae is not None and market_type in {"spread", "total"}:
        # ~3 pt MAE is average; lower is better.
        score += max(-10.0, min(10.0, (3.0 - float(mae)) * 2.0))

    # Shrink toward neutral when thin.
    weight = min(1.0, sample_size / float(MIN_SAMPLES_FOR_ACTIVE))
    shrunk = 50.0 + (score - 50.0) * weight
    return round(max(0.0, min(100.0, shrunk)), 1)


def _allocate_confidence(
    markets: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Map quality → confidence weight and High/Moderate floors.

    Stronger markets inherit (or ease) their learned floors.
    Weaker markets push floors up so Low is more common.
    """

    scored = [
        (mtype, float(card.get("quality_score") or 0.0), card)
        for mtype, card in markets.items()
    ]
    usable = [
        (m, q, c)
        for m, q, c in scored
        if int(c.get("sample_size") or 0) >= MIN_SAMPLES_FOR_WEIGHT
    ]

    if not usable:
        return {
            mtype: {
                "confidence_weight": 1.0,
                "confidence_active": False,
                "high_min": DEFAULT_HIGH_MIN,
                "moderate_min": DEFAULT_MODERATE_MIN,
            }
            for mtype in MARKET_TYPES
        }

    qualities = [q for _, q, _ in usable]
    mean_q = sum(qualities) / len(qualities)
    out: dict[str, dict[str, Any]] = {}

    for mtype, quality, card in scored:
        n = int(card.get("sample_size") or 0)
        edge = card.get("edge_thresholds") or {}
        base_high = float(
            num(edge.get("high_min")) or DEFAULT_HIGH_MIN
        )
        base_mod = float(
            num(edge.get("moderate_min")) or DEFAULT_MODERATE_MIN
        )

        if n < MIN_SAMPLES_FOR_WEIGHT:
            out[mtype] = {
                "confidence_weight": 1.0,
                "confidence_active": False,
                "high_min": base_high,
                "moderate_min": base_mod,
            }
            continue

        # Relative to peer mean: +10 quality ≈ slightly easier floors.
        delta = (quality - mean_q) / 10.0
        # Weight centered at 1.0; clamp to keep betting sane.
        weight = round(max(0.6, min(1.4, 1.0 + delta * 0.15)), 3)
        # Better market → lower edge needed; worse → higher.
        high_min = round(
            max(2.0, min(5.0, base_high - delta * 0.35)), 2
        )
        moderate_min = round(
            max(0.5, min(3.5, base_mod - delta * 0.25)), 2
        )
        if moderate_min > high_min:
            moderate_min = high_min

        out[mtype] = {
            "confidence_weight": weight,
            "confidence_active": True,
            "high_min": high_min,
            "moderate_min": moderate_min,
        }

    return out
