"""
Closing Line Value (CLV) diagnostics.

CLV answers a different question than win rate:

  Did we consistently get a better number than the closing market?

For every bet we store:
  bet_line / bet_price
  closing_line / closing_price
  clv

Positive CLV means the market moved toward our side after we
locked the number — a stronger signal than weekly ATS alone.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from app.analysis.insights.betting.pricing import (
    american_to_implied_prob,
    num,
)


# Kept for callers; diagnostics now use point-edge buckets.
EDGE_BUCKETS = [
    ("0–0.5", 0.0, 0.5),
    ("0.5–1.0", 0.5, 1.0),
    ("1.0–1.5", 1.0, 1.5),
    ("1.5–2.0", 1.5, 2.0),
    ("2.0–2.5", 2.0, 2.5),
    ("2.5–3.0", 2.5, 3.0),
    ("3.0–3.5", 3.0, 3.5),
    ("3.5+", 3.5, None),
]


def selection_side(
    *,
    market_type: str,
    selection: str,
    home_team: str | None,
    away_team: str | None,
) -> str | None:
    """Return home|away|over|under for a settled selection."""

    mtype = str(market_type or "").lower()
    sel = str(selection or "").strip().upper()
    home = str(home_team or "").strip().upper()
    away = str(away_team or "").strip().upper()

    if mtype == "total":
        if "OVER" in sel:
            return "over"
        if "UNDER" in sel:
            return "under"
        return None

    if home and (sel == home or sel.startswith(home + " ")):
        return "home"
    if away and (sel == away or sel.startswith(away + " ")):
        return "away"
    token = sel.split(" ", 1)[0] if sel else ""
    if token == home:
        return "home"
    if token == away:
        return "away"
    return None


def event_spread_as_selection_line(
    market_spread: float | None,
    *,
    side: str | None,
) -> float | None:
    """
    Convert event market_spread (away − home) into the selection's
    spread line (home negative when favored).
    """

    if market_spread is None or side not in {"home", "away"}:
        return None
    spread = float(market_spread)
    return spread if side == "home" else -spread


def compute_clv(
    *,
    market_type: str,
    selection: str,
    home_team: str | None = None,
    away_team: str | None = None,
    bet_line: float | None = None,
    closing_line: float | None = None,
    bet_price: float | None = None,
    closing_price: float | None = None,
) -> dict[str, Any]:
    """
    Compute signed CLV for one bet.

    Spreads/totals: points (positive = beat closing line).
    Moneyline: implied-probability points (positive = beat close).
    """

    mtype = str(market_type or "").lower()
    side = selection_side(
        market_type=mtype,
        selection=selection,
        home_team=home_team,
        away_team=away_team,
    )
    bet_l = num(bet_line)
    close_l = num(closing_line)
    bet_p = num(bet_price)
    close_p = num(closing_price)

    clv = None
    unit = None
    beat_close = None

    if mtype in {"spread", "total"} and bet_l is not None and close_l is not None:
        if mtype == "spread":
            # More points / fewer laid = better. Same-side lines.
            clv = round(float(bet_l) - float(close_l), 2)
            unit = "points"
        elif side == "over":
            clv = round(float(close_l) - float(bet_l), 2)
            unit = "points"
        elif side == "under":
            clv = round(float(bet_l) - float(close_l), 2)
            unit = "points"
        else:
            clv = round(float(bet_l) - float(close_l), 2)
            unit = "points"
        beat_close = clv > 0
    elif mtype == "moneyline" and bet_p is not None and close_p is not None:
        bet_imp = american_to_implied_prob(bet_p)
        close_imp = american_to_implied_prob(close_p)
        if bet_imp is not None and close_imp is not None:
            # Market moved toward selection ⇒ close implied higher.
            clv = round((float(close_imp) - float(bet_imp)) * 100.0, 2)
            unit = "prob_pp"
            beat_close = clv > 0

    return {
        "bet_line": bet_l,
        "closing_line": close_l,
        "bet_price": bet_p,
        "closing_price": close_p,
        "clv": clv,
        "clv_unit": unit,
        "beat_close": beat_close,
        "side": side,
    }


def attach_clv_fields(
    row: dict[str, Any],
    *,
    bet_line: float | None = None,
    closing_line: float | None = None,
    bet_price: float | None = None,
    closing_price: float | None = None,
) -> dict[str, Any]:
    """Mutate/return a settled row with CLV fields filled."""

    payload = dict(row)
    computed = compute_clv(
        market_type=str(payload.get("market_type") or ""),
        selection=str(payload.get("selection") or ""),
        home_team=payload.get("home_team"),
        away_team=payload.get("away_team"),
        bet_line=(
            bet_line
            if bet_line is not None
            else payload.get("bet_line", payload.get("line"))
        ),
        closing_line=(
            closing_line
            if closing_line is not None
            else payload.get("closing_line")
        ),
        bet_price=(
            bet_price
            if bet_price is not None
            else payload.get("bet_price", payload.get("price"))
        ),
        closing_price=(
            closing_price
            if closing_price is not None
            else payload.get("closing_price")
        ),
    )
    payload["bet_line"] = computed["bet_line"]
    payload["closing_line"] = computed["closing_line"]
    payload["bet_price"] = computed["bet_price"]
    payload["closing_price"] = computed["closing_price"]
    payload["clv"] = computed["clv"]
    payload["clv_unit"] = computed["clv_unit"]
    payload["beat_close"] = computed["beat_close"]
    payload["bet_side"] = computed["side"]
    return payload


def unit_result(
    result: str | None,
    price: float | None = None,
) -> float | None:
    """PnL in units for one decided bet (1u flat)."""

    status = str(result or "").lower()
    if status == "push":
        return 0.0
    if status == "lost":
        return -1.0
    if status != "won":
        return None
    odds = float(price) if price is not None else -110.0
    if odds >= 100:
        return round(odds / 100.0, 4)
    if odds <= -100:
        return round(100.0 / abs(odds), 4)
    return round(100.0 / 110.0, 4)


def edge_bucket(edge: float | None) -> str:
    """Assign a point-edge ladder bucket (abs points)."""

    from app.analysis.insights.betting.edge_confidence import (
        assign_point_edge_bucket,
    )

    return assign_point_edge_bucket(edge)


def favorite_underdog_label(row: dict[str, Any]) -> str:
    side = row.get("bet_side") or selection_side(
        market_type=str(row.get("market_type") or ""),
        selection=str(row.get("selection") or ""),
        home_team=row.get("home_team"),
        away_team=row.get("away_team"),
    )
    mtype = str(row.get("market_type") or "").lower()
    line = num(row.get("bet_line", row.get("line")))
    price = num(row.get("bet_price", row.get("price")))

    if mtype == "spread" and line is not None:
        # Selection line negative ⇒ favorite.
        if float(line) < 0:
            return "favorite"
        if float(line) > 0:
            return "underdog"
        return "pickem"
    if mtype == "moneyline" and price is not None:
        if float(price) < 0:
            return "favorite"
        if float(price) > 0:
            return "underdog"
        return "pickem"
    if mtype == "total":
        return side or "total"
    return "unknown"


def home_away_label(row: dict[str, Any]) -> str:
    side = row.get("bet_side") or selection_side(
        market_type=str(row.get("market_type") or ""),
        selection=str(row.get("selection") or ""),
        home_team=row.get("home_team"),
        away_team=row.get("away_team"),
    )
    if side in {"home", "away"}:
        return side
    if side in {"over", "under"}:
        return side
    return "unknown"


def estimate_closing_edge(row: dict[str, Any]) -> float | None:
    """
    Edge vs the closing market, in probability percentage points.

    Prefer model_probability − closing implied. Otherwise back out
    from bet-time edge and CLV (ML CLV is already in pp; spread /
    total CLV points use a ~2.5 pp/point conversion).
    """

    model_p = num(row.get("model_probability"))
    close_price = num(row.get("closing_price"))
    if model_p is not None and close_price is not None:
        close_imp = american_to_implied_prob(close_price)
        if close_imp is not None:
            return round((float(model_p) - float(close_imp)) * 100.0, 2)

    edge = num(row.get("edge"))
    clv = num(row.get("clv"))
    if edge is None or clv is None:
        return None

    mtype = str(row.get("market_type") or "").lower()
    unit = str(row.get("clv_unit") or "")
    if mtype == "moneyline" or unit == "prob_pp":
        return round(float(edge) - float(clv), 2)
    if mtype in {"spread", "total"} or unit == "points":
        # Approximate: each point of line CLV ≈ 2.5 pp of win-prob.
        return round(float(edge) - float(clv) * 2.5, 2)
    return None


def enrich_settled_row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Add derived diagnostic dimensions onto a settled row."""

    from app.analysis.insights.betting.edge_confidence import (
        assign_point_edge_bucket,
        point_edge_magnitude,
    )

    out = attach_clv_fields(row)
    magnitude = point_edge_magnitude(out)
    out["edge_points"] = magnitude
    out["units"] = unit_result(
        out.get("result"),
        out.get("bet_price", out.get("price")),
    )
    out["edge_bucket"] = assign_point_edge_bucket(magnitude)
    out["favorite_underdog"] = favorite_underdog_label(out)
    out["home_away"] = home_away_label(out)
    if num(out.get("closing_edge")) is None:
        out["closing_edge"] = estimate_closing_edge(out)
    return out


def build_clv_diagnostics(
    settled: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Aggregate CLV / ATS / ROI diagnostics with requested breakdowns.
    """

    rows = [enrich_settled_row_metrics(row) for row in settled or []]
    decided = [
        row for row in rows if row.get("result") in {"won", "lost"}
    ]

    def _win_pct(items: list[dict[str, Any]]) -> float | None:
        graded = [
            row for row in items if row.get("result") in {"won", "lost"}
        ]
        if not graded:
            return None
        won = sum(1 for row in graded if row.get("result") == "won")
        return round(100.0 * won / len(graded), 1)

    def _subset(mtype: str) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if str(row.get("market_type") or "").lower() == mtype
        ]

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
    edges = [
        float(row["edge"])
        for row in rows
        if num(row.get("edge")) is not None
    ]
    closing_edges = [
        float(row["closing_edge"])
        for row in rows
        if num(row.get("closing_edge")) is not None
    ]
    beat = [
        row for row in rows if row.get("beat_close") is True
    ]
    clv_known = [
        row for row in rows if row.get("beat_close") is not None
    ]

    stake_units = float(len(decided)) if decided else 0.0
    profit_units = sum(units) if units else 0.0
    roi_pct = (
        round(100.0 * profit_units / stake_units, 1)
        if stake_units > 0
        else None
    )

    summary = {
        "bets": len(rows),
        "decided": len(decided),
        "ats_win_pct": _win_pct(_subset("spread")),
        "ou_win_pct": _win_pct(_subset("total")),
        "ml_win_pct": _win_pct(_subset("moneyline")),
        "hit_rate": _win_pct(rows),
        "average_clv": (
            round(sum(clvs) / len(clvs), 2) if clvs else None
        ),
        "median_clv": (
            round(float(statistics.median(clvs)), 2) if clvs else None
        ),
        "clv_sample": len(clvs),
        "beat_close_pct": (
            round(100.0 * len(beat) / len(clv_known), 1)
            if clv_known
            else None
        ),
        "units": round(profit_units, 2) if units else None,
        "roi_pct": roi_pct,
        "average_edge": (
            round(sum(edges) / len(edges), 2) if edges else None
        ),
        "average_closing_edge": (
            round(sum(closing_edges) / len(closing_edges), 2)
            if closing_edges
            else None
        ),
        "note": (
            "CLV uses bet_line vs closing_line (points) for "
            "spreads/totals and implied-probability points for "
            "moneylines. Positive CLV = beat the closing market."
        ),
    }

    return {
        "summary": summary,
        "by_confidence": _clv_breakdown(rows, "confidence"),
        "by_edge_bucket": _clv_breakdown(rows, "edge_bucket"),
        "by_market_type": _clv_breakdown(rows, "market_type"),
        "by_favorite_underdog": _clv_breakdown(
            rows, "favorite_underdog"
        ),
        "by_home_away": _clv_breakdown(rows, "home_away"),
        "by_week": _clv_breakdown(rows, "week"),
        "settled_markets": rows,
    }


def _clv_breakdown(
    rows: list[dict[str, Any]],
    field: str,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = str(row.get(field) if row.get(field) is not None else "unknown")
        buckets[key].append(row)

    out: list[dict[str, Any]] = []
    for key, items in buckets.items():
        decided = [
            row for row in items if row.get("result") in {"won", "lost"}
        ]
        correct = [
            row for row in decided if row.get("result") == "won"
        ]
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
        edges = [
            float(row["edge"])
            for row in items
            if num(row.get("edge")) is not None
        ]
        closing_edges = [
            float(row["closing_edge"])
            for row in items
            if num(row.get("closing_edge")) is not None
        ]
        beat = [row for row in items if row.get("beat_close") is True]
        clv_known = [
            row for row in items if row.get("beat_close") is not None
        ]
        stake = float(len(decided))
        profit = sum(units) if units else 0.0
        out.append(
            {
                "key": key,
                "bets": len(items),
                "decided": len(decided),
                "correct": len(correct),
                "hit_rate": (
                    round(100.0 * len(correct) / len(decided), 1)
                    if decided
                    else None
                ),
                "average_clv": (
                    round(sum(clvs) / len(clvs), 2) if clvs else None
                ),
                "median_clv": (
                    round(float(statistics.median(clvs)), 2)
                    if clvs
                    else None
                ),
                "beat_close_pct": (
                    round(100.0 * len(beat) / len(clv_known), 1)
                    if clv_known
                    else None
                ),
                "units": round(profit, 2) if units else None,
                "roi_pct": (
                    round(100.0 * profit / stake, 1)
                    if stake > 0 and units
                    else None
                ),
                "average_edge": (
                    round(sum(edges) / len(edges), 2) if edges else None
                ),
                "average_closing_edge": (
                    round(
                        sum(closing_edges) / len(closing_edges), 2
                    )
                    if closing_edges
                    else None
                ),
            }
        )

    out.sort(key=lambda row: (-row["bets"], str(row["key"])))
    return out
