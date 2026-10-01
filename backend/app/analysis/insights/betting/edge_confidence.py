"""
Learned confidence from point-edge backtests.

Fixed cutoffs (edge ≥ 3.5 → High, ≥ 1.5 → Moderate) are not
inherently meaningful. Instead we bucket historical point edges:

  0–0.5, 0.5–1.0, 1.0–1.5, 1.5–2.0,
  2.0–2.5, 2.5–3.0, 3.0–3.5, 3.5+

and measure win rate, ROI, CLV, sample size, and calibration
in each bucket. Confidence thresholds are then derived from
where the model actually separates — often not at 1.5 / 3.5.
"""

from __future__ import annotations

import statistics
from typing import Any

from app.analysis.insights.betting.pricing import num


# Inclusive lower bound, exclusive upper (except open-ended top).
POINT_EDGE_BUCKETS: list[tuple[str, float, float | None]] = [
    ("0–0.5", 0.0, 0.5),
    ("0.5–1.0", 0.5, 1.0),
    ("1.0–1.5", 1.0, 1.5),
    ("1.5–2.0", 1.5, 2.0),
    ("2.0–2.5", 2.0, 2.5),
    ("2.5–3.0", 2.5, 3.0),
    ("3.0–3.5", 3.0, 3.5),
    ("3.5+", 3.5, None),
]

# Fallback until enough settled history exists.
DEFAULT_HIGH_MIN = 3.5
DEFAULT_MODERATE_MIN = 1.5

BREAKEVEN_WIN_PCT = 52.4  # approx. -110
MIN_BUCKET_SAMPLES = 12
MIN_ACTIVE_SAMPLES = 40
# Material separation vs baseline (win-rate pp / ROI pp / CLV pts).
SEPARATION_WIN_PP = 3.0
SEPARATION_ROI_PP = 2.0
SEPARATION_CLV = 0.15


def point_edge_magnitude(row: dict[str, Any]) -> float | None:
    """
    Absolute model−market point edge for a market / settled row.

    Prefers explicit ``edge_points``, then projection deltas,
    then abs(edge) when it looks like a point edge (spreads/totals).
    """

    explicit = num(row.get("edge_points"))
    if explicit is not None:
        return abs(float(explicit))

    mtype = str(row.get("market_type") or "").lower()
    if mtype == "spread":
        model = num(row.get("model_spread", row.get("model_projection")))
        market = num(
            row.get("market_spread", row.get("market_implied_projection"))
        )
        if model is not None and market is not None:
            return abs(float(model) - float(market))
    if mtype == "total":
        model = num(row.get("model_total", row.get("model_projection")))
        market = num(
            row.get(
                "market_total",
                row.get("market_implied_projection"),
            )
        )
        if model is not None and market is not None:
            return abs(float(model) - float(market))

    # Live market rows store point edge on ``edge`` for spread/total.
    edge = num(row.get("edge"))
    if edge is not None and mtype in {"spread", "total"}:
        return abs(float(edge))

    # Moneyline: treat abs probability-pp edge on the same scale.
    if mtype == "moneyline":
        ep = num(row.get("edge_probability", row.get("edge")))
        if ep is not None:
            # edge_probability may be fraction or already pp.
            value = abs(float(ep))
            if value <= 1.0:
                value *= 100.0
            return value
    return None


def assign_point_edge_bucket(edge_points: float | None) -> str:
    if edge_points is None:
        return "unknown"
    value = abs(float(edge_points))
    for label, lo, hi in POINT_EDGE_BUCKETS:
        if hi is None:
            if value >= lo:
                return label
        elif lo <= value < hi:
            return label
    return "unknown"


def bucket_bounds(label: str) -> tuple[float | None, float | None]:
    for name, lo, hi in POINT_EDGE_BUCKETS:
        if name == label:
            return lo, hi
    return None, None


def backtest_point_edge_buckets(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Historical metrics for each point-edge bucket.

    Always returns every bucket (even empty) so the ladder is visible.
    """

    from app.analysis.insights.betting.clv import (
        attach_clv_fields,
        unit_result,
    )

    enriched: list[dict[str, Any]] = []
    for row in rows or []:
        item = attach_clv_fields(dict(row))
        magnitude = point_edge_magnitude(item)
        item["edge_points"] = magnitude
        item["point_edge_bucket"] = assign_point_edge_bucket(magnitude)
        if num(item.get("units")) is None:
            item["units"] = unit_result(
                item.get("result"),
                item.get("bet_price", item.get("price")),
            )
        enriched.append(item)

    by_label: dict[str, list[dict[str, Any]]] = {
        label: [] for label, _, _ in POINT_EDGE_BUCKETS
    }
    for item in enriched:
        label = str(item.get("point_edge_bucket") or "unknown")
        if label in by_label:
            by_label[label].append(item)

    return [
        _bucket_metrics(label, by_label[label], lo=lo, hi=hi)
        for label, lo, hi in POINT_EDGE_BUCKETS
    ]


def fit_confidence_thresholds(
    rows: list[dict[str, Any]] | None = None,
    *,
    buckets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Learn High / Moderate point-edge floors from bucket backtests.

    High  = lowest floor among top consecutive buckets that show
            useful separation vs the small-edge baseline.
    Moderate = lowest floor where performance clears noise /
            breakeven (weaker bar than High).
    """

    ladder = buckets if buckets is not None else backtest_point_edge_buckets(
        rows or []
    )
    sample_size = sum(int(b.get("sample_size") or 0) for b in ladder)
    baseline = _baseline_metrics(ladder)

    if sample_size < MIN_ACTIVE_SAMPLES:
        return _inactive_model(
            ladder=ladder,
            baseline=baseline,
            sample_size=sample_size,
            reason="insufficient_samples",
        )

    strong_floors: list[float] = []
    useful_floors: list[float] = []
    for bucket in ladder:
        n = int(bucket.get("sample_size") or 0)
        if n < MIN_BUCKET_SAMPLES:
            continue
        lo = num(bucket.get("lo"))
        if lo is None:
            continue
        if _is_strong_bucket(bucket, baseline):
            strong_floors.append(float(lo))
        if _is_useful_bucket(bucket, baseline):
            useful_floors.append(float(lo))

    # Prefer the lowest strong floor that still has a contiguous
    # strong band toward the top of the ladder (3.5+ downward).
    high_min = _contiguous_top_floor(ladder, strong_floors)
    moderate_min = (
        min(useful_floors) if useful_floors else DEFAULT_MODERATE_MIN
    )
    if high_min is None:
        high_min = DEFAULT_HIGH_MIN
    # Keep ordering: High should not sit below Moderate.
    if moderate_min > high_min:
        moderate_min = high_min

    note = (
        f"Learned from {sample_size} settled bets. "
        f"High ≥ {high_min:g} pts, Moderate ≥ {moderate_min:g} pts "
        f"(baseline win {baseline.get('win_rate')}%, "
        f"ROI {baseline.get('roi_pct')}%). "
        "Cutoffs follow where point-edge buckets separate historically "
        "— not fixed 1.5 / 3.5 rules."
    )
    return {
        "active": True,
        "method": "point_edge_backtest",
        "sample_size": sample_size,
        "high_min": round(float(high_min), 2),
        "moderate_min": round(float(moderate_min), 2),
        "fallback_high_min": DEFAULT_HIGH_MIN,
        "fallback_moderate_min": DEFAULT_MODERATE_MIN,
        "baseline": baseline,
        "buckets": ladder,
        "note": note,
    }


def apply_confidence_thresholds(
    *,
    edge_points: float | None = None,
    edge_probability: float | None = None,
    model_coverage: bool = True,
    thresholds: dict[str, Any] | None = None,
) -> str:
    """Label confidence using learned floors when active."""

    if not model_coverage:
        return "Low"

    magnitude = 0.0
    if edge_points is not None:
        magnitude = max(magnitude, abs(float(edge_points)))
    if edge_probability is not None:
        ep = abs(float(edge_probability))
        # Accept fraction or percentage points.
        if ep <= 1.0:
            ep *= 100.0
        magnitude = max(magnitude, ep)

    high_min = DEFAULT_HIGH_MIN
    moderate_min = DEFAULT_MODERATE_MIN
    if thresholds and thresholds.get("active"):
        high_min = float(
            num(thresholds.get("high_min")) or DEFAULT_HIGH_MIN
        )
        moderate_min = float(
            num(thresholds.get("moderate_min")) or DEFAULT_MODERATE_MIN
        )

    if magnitude >= high_min:
        return "High"
    if magnitude >= moderate_min:
        return "Moderate"
    return "Low"


def build_edge_confidence_diagnostics(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Full payload: bucket ladder + learned thresholds."""

    buckets = backtest_point_edge_buckets(rows)
    model = fit_confidence_thresholds(buckets=buckets)
    return {
        "thresholds": {
            "active": bool(model.get("active")),
            "method": model.get("method"),
            "sample_size": model.get("sample_size"),
            "high_min": model.get("high_min"),
            "moderate_min": model.get("moderate_min"),
            "note": model.get("note"),
        },
        "baseline": model.get("baseline"),
        "buckets": buckets,
        "note": model.get("note"),
    }


def _bucket_metrics(
    label: str,
    items: list[dict[str, Any]],
    *,
    lo: float,
    hi: float | None,
) -> dict[str, Any]:
    decided = [
        row for row in items if row.get("result") in {"won", "lost"}
    ]
    won = [row for row in decided if row.get("result") == "won"]
    clvs = [
        float(row["clv"])
        for row in items
        if num(row.get("clv")) is not None
    ]
    units = [
        float(row["units"])
        for row in decided
        if num(row.get("units")) is not None
    ]
    preds = []
    actuals = []
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
    mean_pred = (
        round(100.0 * sum(preds) / len(preds), 1) if preds else None
    )
    calibration_gap = (
        round(float(win_rate) - float(mean_pred), 1)
        if win_rate is not None and mean_pred is not None
        else None
    )

    return {
        "key": label,
        "lo": lo,
        "hi": hi,
        "bets": len(items),
        "sample_size": len(decided),
        "decided": len(decided),
        "correct": len(won),
        "hit_rate": win_rate,
        "win_rate": win_rate,
        "roi_pct": roi_pct,
        "units": round(profit, 2) if units else None,
        "average_clv": avg_clv,
        "median_clv": median_clv,
        "clv_sample": len(clvs),
        "mean_predicted_pct": mean_pred,
        "calibration_gap": calibration_gap,
        "calibration": {
            "mean_predicted_pct": mean_pred,
            "actual_win_pct": win_rate,
            "gap_pp": calibration_gap,
            "n": len(preds),
        },
    }


def _baseline_metrics(
    ladder: list[dict[str, Any]],
) -> dict[str, Any]:
    """Small-edge regime (buckets with hi ≤ 1.5) as the noise floor."""

    base_rows_n = 0
    won_weight = 0.0
    profit = 0.0
    clv_sum = 0.0
    clv_n = 0
    for bucket in ladder:
        hi = num(bucket.get("hi"))
        if hi is None or float(hi) > 1.5:
            continue
        n = int(bucket.get("sample_size") or 0)
        if n <= 0:
            continue
        wr = num(bucket.get("win_rate"))
        if wr is not None:
            won_weight += float(wr) * n / 100.0
            base_rows_n += n
        roi = num(bucket.get("roi_pct"))
        if roi is not None:
            profit += float(roi) * n / 100.0
        clv = num(bucket.get("average_clv"))
        cn = int(bucket.get("clv_sample") or 0)
        if clv is not None and cn > 0:
            clv_sum += float(clv) * cn
            clv_n += cn

    if base_rows_n <= 0:
        return {
            "win_rate": BREAKEVEN_WIN_PCT,
            "roi_pct": 0.0,
            "average_clv": 0.0,
            "sample_size": 0,
        }
    return {
        "win_rate": round(100.0 * won_weight / base_rows_n, 1),
        "roi_pct": round(100.0 * profit / base_rows_n, 1),
        "average_clv": (
            round(clv_sum / clv_n, 2) if clv_n else 0.0
        ),
        "sample_size": base_rows_n,
    }


def _is_strong_bucket(
    bucket: dict[str, Any],
    baseline: dict[str, Any],
) -> bool:
    wr = num(bucket.get("win_rate"))
    roi = num(bucket.get("roi_pct"))
    clv = num(bucket.get("average_clv"))
    base_wr = float(baseline.get("win_rate") or BREAKEVEN_WIN_PCT)
    signals = 0
    if wr is not None and float(wr) >= base_wr + SEPARATION_WIN_PP:
        signals += 1
    if wr is not None and float(wr) >= BREAKEVEN_WIN_PCT + 1.0:
        signals += 1
    if roi is not None and float(roi) >= SEPARATION_ROI_PP:
        signals += 1
    if clv is not None and float(clv) >= SEPARATION_CLV:
        signals += 1
    return signals >= 2


def _is_useful_bucket(
    bucket: dict[str, Any],
    baseline: dict[str, Any],
) -> bool:
    wr = num(bucket.get("win_rate"))
    roi = num(bucket.get("roi_pct"))
    clv = num(bucket.get("average_clv"))
    base_wr = float(baseline.get("win_rate") or BREAKEVEN_WIN_PCT)
    if wr is not None and float(wr) >= max(base_wr, BREAKEVEN_WIN_PCT):
        return True
    if roi is not None and float(roi) > 0:
        return True
    if clv is not None and float(clv) > 0:
        return True
    return False


def _contiguous_top_floor(
    ladder: list[dict[str, Any]],
    strong_floors: list[float],
) -> float | None:
    """
    Walk from 3.5+ downward; keep extending High while buckets
    remain strong. Returns the lowest such floor.
    """

    if not strong_floors:
        return None
    strong_set = {round(f, 2) for f in strong_floors}
    floor: float | None = None
    for bucket in reversed(ladder):
        lo = num(bucket.get("lo"))
        if lo is None:
            continue
        n = int(bucket.get("sample_size") or 0)
        if n < MIN_BUCKET_SAMPLES:
            # Skip thin buckets without breaking the band.
            continue
        if round(float(lo), 2) in strong_set:
            floor = float(lo)
            continue
        break
    return floor


def _inactive_model(
    *,
    ladder: list[dict[str, Any]],
    baseline: dict[str, Any],
    sample_size: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "active": False,
        "method": "fallback",
        "sample_size": sample_size,
        "high_min": DEFAULT_HIGH_MIN,
        "moderate_min": DEFAULT_MODERATE_MIN,
        "fallback_high_min": DEFAULT_HIGH_MIN,
        "fallback_moderate_min": DEFAULT_MODERATE_MIN,
        "baseline": baseline,
        "buckets": ladder,
        "reason": reason,
        "note": (
            f"Using fallback High ≥ {DEFAULT_HIGH_MIN:g} / "
            f"Moderate ≥ {DEFAULT_MODERATE_MIN:g} until "
            f"{MIN_ACTIVE_SAMPLES} settled bets are available "
            f"(have {sample_size}). Backtested buckets still shown."
        ),
    }
