"""
Learn Strong Bet / Lean EV and edge floors from history.

Priors match CLASSIFICATION_THRESHOLDS until enough settled rows
exist. Fit on earlier weeks; validate on untouched later weeks.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.analysis.insights.betting.bet_qualification import (
    CLASSIFICATION_THRESHOLDS,
)
from app.analysis.insights.betting.pricing import num


MIN_FIT_ROWS = 60
MIN_STRONG_HOLDOUT = 20
STRONG_EDGE_GRID = (2.5, 3.0, 3.5, 4.0, 5.0)
STRONG_EV_GRID = (1.5, 2.0, 3.0, 4.0)
LEAN_EDGE_GRID = (1.0, 1.5, 2.0, 2.5)
LEAN_EV_GRID = (0.5, 1.0, 1.5, 2.0)


def prior_qualification_thresholds() -> dict[str, Any]:
    strong = CLASSIFICATION_THRESHOLDS["strong_bet"]
    lean = CLASSIFICATION_THRESHOLDS["lean"]
    return {
        "method": "prior",
        "source": "prior",
        "active": False,
        "sample_size": 0,
        "strong_bet": {
            "min_edge_prob_pp": float(strong["min_edge_prob_pp"]),
            "min_ev_pct": float(strong["min_ev_pct"]),
        },
        "lean": {
            "min_edge_prob_pp": float(lean["min_edge_prob_pp"]),
            "min_ev_pct": float(lean["min_ev_pct"]),
        },
        "metrics": None,
        "note": (
            "Cold-start prior floors (Strong 4.0 pp / 3.0% EV). "
            f"Active after {MIN_FIT_ROWS} settled learning rows "
            "with holdout validation."
        ),
    }


def fit_qualification_thresholds(
    rows: list[dict[str, Any]],
    *,
    train_ratio: float = 0.7,
) -> dict[str, Any]:
    """
    Grid-search Strong/Lean floors on train; pick by holdout ROI.

    Objective: maximize holdout Strong Bet ROI subject to
    n_strong ≥ MIN_STRONG_HOLDOUT and Lean ROI ≥ −2%.
    Secondary: average CLV when available.
    """

    ordered = _ordered_rows(rows)
    n = len(ordered)
    if n < MIN_FIT_ROWS:
        model = prior_qualification_thresholds()
        model["sample_size"] = n
        model["note"] = (
            f"Insufficient samples ({n} < {MIN_FIT_ROWS}); "
            "using prior floors."
        )
        return model

    cut = max(1, int(n * train_ratio))
    train = ordered[:cut]
    test = ordered[cut:] or ordered[-1:]

    best: dict[str, Any] | None = None
    best_score = None
    candidates_tried = 0

    for s_edge in STRONG_EDGE_GRID:
        for s_ev in STRONG_EV_GRID:
            for l_edge in LEAN_EDGE_GRID:
                for l_ev in LEAN_EV_GRID:
                    if l_edge > s_edge or l_ev > s_ev:
                        continue
                    candidates_tried += 1
                    # Prefer candidates that look good on train ROI,
                    # then confirm on holdout.
                    train_m = _score_thresholds(
                        train,
                        strong_edge=s_edge,
                        strong_ev=s_ev,
                        lean_edge=l_edge,
                        lean_ev=l_ev,
                    )
                    if train_m["n_strong"] < 8:
                        continue
                    hold = _score_thresholds(
                        test,
                        strong_edge=s_edge,
                        strong_ev=s_ev,
                        lean_edge=l_edge,
                        lean_ev=l_ev,
                    )
                    if hold["n_strong"] < MIN_STRONG_HOLDOUT:
                        continue
                    if hold["lean_roi"] is not None and hold["lean_roi"] < -0.02:
                        continue
                    score = (
                        float(hold["strong_roi"] or -1.0),
                        float(hold["avg_clv"] or 0.0),
                        -abs(s_edge - 4.0),  # mild preference near prior
                    )
                    if best_score is None or score > best_score:
                        best_score = score
                        best = {
                            "strong_edge": s_edge,
                            "strong_ev": s_ev,
                            "lean_edge": l_edge,
                            "lean_ev": l_ev,
                            "train": train_m,
                            "holdout": hold,
                        }

    if best is None:
        model = prior_qualification_thresholds()
        model["sample_size"] = n
        model["note"] = (
            f"No grid candidate met holdout constraints "
            f"(n={n}, candidates={candidates_tried}); using prior."
        )
        return model

    hold = best["holdout"]
    return {
        "method": "holdout_roi_grid",
        "source": "learned",
        "active": True,
        "sample_size": n,
        "n_train": len(train),
        "n_holdout": len(test),
        "strong_bet": {
            "min_edge_prob_pp": float(best["strong_edge"]),
            "min_ev_pct": float(best["strong_ev"]),
        },
        "lean": {
            "min_edge_prob_pp": float(best["lean_edge"]),
            "min_ev_pct": float(best["lean_ev"]),
        },
        "metrics": {
            "candidates_tried": candidates_tried,
            "holdout_strong_n": hold["n_strong"],
            "holdout_strong_roi": hold["strong_roi"],
            "holdout_lean_n": hold["n_lean"],
            "holdout_lean_roi": hold["lean_roi"],
            "holdout_avg_clv": hold["avg_clv"],
            "train_strong_roi": best["train"]["strong_roi"],
        },
        "note": (
            f"Learned Strong {best['strong_edge']:g} pp / "
            f"{best['strong_ev']:g}% EV; Lean {best['lean_edge']:g} pp / "
            f"{best['lean_ev']:g}% EV. Holdout Strong ROI "
            f"{(hold['strong_roi'] or 0):+.1%} on "
            f"{hold['n_strong']} bets."
        ),
    }


def evaluate_qualification_thresholds(
    rows: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Score a threshold set on labeled rows."""

    strong = thresholds.get("strong_bet") or {}
    lean = thresholds.get("lean") or {}
    return _score_thresholds(
        _ordered_rows(rows),
        strong_edge=float(
            strong.get("min_edge_prob_pp")
            or CLASSIFICATION_THRESHOLDS["strong_bet"]["min_edge_prob_pp"]
        ),
        strong_ev=float(
            strong.get("min_ev_pct")
            or CLASSIFICATION_THRESHOLDS["strong_bet"]["min_ev_pct"]
        ),
        lean_edge=float(
            lean.get("min_edge_prob_pp")
            or CLASSIFICATION_THRESHOLDS["lean"]["min_edge_prob_pp"]
        ),
        lean_ev=float(
            lean.get("min_ev_pct")
            or CLASSIFICATION_THRESHOLDS["lean"]["min_ev_pct"]
        ),
    )


def _ordered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows or [],
        key=lambda row: (
            int(row.get("week") or 0),
            str(row.get("market_id") or row.get("game_id") or ""),
        ),
    )


def _score_thresholds(
    rows: list[dict[str, Any]],
    *,
    strong_edge: float,
    strong_ev: float,
    lean_edge: float,
    lean_ev: float,
) -> dict[str, Any]:
    strong_pnls: list[float] = []
    lean_pnls: list[float] = []
    clvs: list[float] = []

    for row in rows:
        result = str(row.get("result") or "").lower()
        if result not in {"won", "lost"}:
            continue
        edge = num(row.get("edge_probability"))
        ev = num(row.get("expected_value"))
        # expected_value may be fraction or percent; normalize to %.
        if ev is not None and abs(float(ev)) <= 1.5:
            ev = float(ev) * 100.0
        if edge is None or ev is None:
            continue
        confidence = str(row.get("confidence") or "Low").title()
        # Approximate data quality from calibration / agreement if present.
        quality = str(
            row.get("data_quality")
            or row.get("data_quality_label")
            or "Moderate"
        ).title()
        pnl = 1.0 if result == "won" else -1.0
        # Rough EV settlement: use American -110 unit PnL when available.
        price = num(row.get("price") or row.get("bet_price")) or -110.0
        if result == "won":
            if float(price) > 0:
                pnl = float(price) / 100.0
            else:
                pnl = 100.0 / abs(float(price))
        else:
            pnl = -1.0

        strong_ok = (
            float(edge) >= strong_edge
            and float(ev) >= strong_ev
            and confidence == "High"
            and quality == "High"
        )
        lean_ok = (
            float(edge) >= lean_edge
            and float(ev) >= lean_ev
            and confidence in {"High", "Moderate"}
            and quality in {"High", "Moderate"}
        )
        if strong_ok:
            strong_pnls.append(pnl)
            clv_v = num(row.get("clv"))
            if clv_v is not None:
                clvs.append(float(clv_v))
        elif lean_ok:
            lean_pnls.append(pnl)
            clv_v = num(row.get("clv"))
            if clv_v is not None:
                clvs.append(float(clv_v))

    def _roi(pnls: list[float]) -> float | None:
        if not pnls:
            return None
        return round(float(np.mean(pnls)), 4)

    return {
        "n_strong": len(strong_pnls),
        "n_lean": len(lean_pnls),
        "strong_roi": _roi(strong_pnls),
        "lean_roi": _roi(lean_pnls),
        "avg_clv": (
            round(float(np.mean(clvs)), 4) if clvs else None
        ),
    }
