"""
Separate model predictions from bet recommendations.

Objective:
  Identify bets where calibrated probability meaningfully exceeds
  market-implied probability — not "pick a side for every game."

Pipeline:
  model prediction
       ↓
  raw probability
       ↓
  probability calibration
       ↓
  market implied probability
       ↓
  expected value
       ↓
  model confidence
       ↓
  data quality
       ↓
  market-movement check
       ↓
  classification (threshold-based)
       → Strong Bet | Lean | Pass (No Bet)

Pass is a first-class outcome. Edge below threshold, weak
confidence, thin data, or a move that already prices in the
edge all force Pass — the system must not invent a side.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.pricing import num


# ---------------------------------------------------------------------------
# Explicit classification thresholds (not subjective labels).
# edge_probability is percentage points vs market.
# expected_value is percent of stake (slate convention, e.g. +2.5).
# ---------------------------------------------------------------------------

CLASSIFICATION_THRESHOLDS: dict[str, dict[str, Any]] = {
    "strong_bet": {
        "label": "Strong Bet",
        "min_edge_prob_pp": 4.0,
        "min_ev_pct": 3.0,
        "min_confidence": frozenset({"High"}),
        "min_data_quality": frozenset({"High"}),
    },
    "lean": {
        "label": "Lean",
        "min_edge_prob_pp": 1.5,
        "min_ev_pct": 1.0,
        "min_confidence": frozenset({"High", "Moderate"}),
        "min_data_quality": frozenset({"High", "Moderate"}),
    },
}

# Hard Pass gates — fail any → No Bet (even if directional).
PASS_MIN_EDGE_PROB_PP = CLASSIFICATION_THRESHOLDS["lean"]["min_edge_prob_pp"]
PASS_MIN_EV_PCT = CLASSIFICATION_THRESHOLDS["lean"]["min_ev_pct"]
PASS_MIN_CONFIDENCE = CLASSIFICATION_THRESHOLDS["lean"]["min_confidence"]
PASS_MIN_DATA_QUALITY = CLASSIFICATION_THRESHOLDS["lean"]["min_data_quality"]

# Material line move that counts as "already incorporating" the edge.
MATERIAL_SPREAD_MOVE = 0.5
MATERIAL_TOTAL_MOVE = 0.5

# Backward-compatible aliases used by older call sites / tests.
MIN_EV_PCT = PASS_MIN_EV_PCT
MIN_EDGE_PROB_PP = PASS_MIN_EDGE_PROB_PP
MIN_CONFIDENCE = set(PASS_MIN_CONFIDENCE)
MIN_DATA_QUALITY = set(PASS_MIN_DATA_QUALITY)

STATUS_LABELS = {
    "strong_bet": "Strong Bet",
    "lean": "Lean",
    "pass": "Pass",
}


def assess_data_quality(
    *,
    event: dict[str, Any] | None = None,
    market: dict[str, Any] | None = None,
    probability_calibrated: bool = False,
) -> dict[str, Any]:
    """
    Score supporting data depth for a market decision.

    This is intentionally separate from edge magnitude /
    confidence-from-edge.
    """

    event = event or {}
    market = market or {}
    factors: list[str] = []
    score = 0.35  # baseline when a market line exists

    strength = event.get("team_strength") or {}
    if strength.get("available"):
        score += 0.2
        factors.append("opponent-adjusted team strength available")
        games = min(
            int(strength.get("home_games") or 0),
            int(strength.get("away_games") or 0),
        )
        if games >= 3:
            score += 0.1
            factors.append(f"strength sample ≥3 games/side ({games})")
        elif games > 0:
            factors.append(f"thin strength sample ({games} games/side)")
    else:
        factors.append("team strength sparse — relying on market/PPG fallback")

    residuals = event.get("residuals") or {}
    if residuals.get("residual_home") is not None:
        score += 0.1
        factors.append("market residual architecture active")

    proj_conf = (
        (event.get("projection_blend") or {}).get("confidence")
        or residuals.get("confidence")
        or strength.get("projection_confidence")
    )
    if proj_conf == "High":
        score += 0.1
        factors.append("high projection confidence")
    elif proj_conf == "Moderate":
        score += 0.05
        factors.append("moderate projection confidence")
    elif proj_conf == "Low":
        factors.append("low projection confidence")

    if event.get("injury_report_week") is not None:
        score += 0.05
        factors.append("injury report attached for slate week")

    move = event.get("market_movement") or {}
    if move.get("opening_spread") is not None or move.get("moved"):
        score += 0.05
        factors.append("opening/current market movement tracked")

    if probability_calibrated or market.get("probability_calibrated"):
        score += 0.1
        factors.append("probability calibration active")
    else:
        factors.append("probability calibration not yet active")

    disagreement = (
        event.get("model_disagreement")
        or market.get("model_disagreement")
        or {}
    )
    mtype = str(market.get("market_type") or "").lower()
    block = None
    if mtype == "total":
        block = disagreement.get("total")
    elif mtype in {"spread", "moneyline"}:
        block = disagreement.get("spread")
    if not block and isinstance(disagreement, dict):
        # Market-level condensed payload.
        if disagreement.get("model_agreement") is not None:
            block = disagreement
    if block and num(block.get("model_agreement")) is not None:
        agreement = float(block["model_agreement"])
        stddev = num(block.get("projection_stddev"))
        if agreement >= 0.75:
            score += 0.1
            factors.append(
                f"models agree (σ={stddev if stddev is not None else '—'}, "
                f"agreement {agreement:.2f})"
            )
        elif agreement >= 0.55:
            score += 0.03
            factors.append(
                f"moderate model agreement ({agreement:.2f})"
            )
        else:
            score -= 0.08
            factors.append(
                f"models disagree (σ={stddev if stddev is not None else '—'}, "
                f"agreement {agreement:.2f}) — confidence dampened"
            )

    score = max(0.0, min(1.0, round(score, 3)))
    if score >= 0.75:
        label = "High"
    elif score >= 0.5:
        label = "Moderate"
    else:
        label = "Low"

    return {
        "score": score,
        "label": label,
        "factors": factors,
    }


def market_movement_invalidates_edge(
    *,
    event: dict[str, Any] | None,
    market_type: str | None = None,
    edge_probability: float | None = None,
) -> dict[str, Any]:
    """
    Hard No-Bet gate: line already moved toward the model.

    If the market has incorporated the residual direction, the
    remaining priced edge is no longer a clean actionable bet
    unless it still clears the Strong Bet edge cushion.
    """

    event = event or {}
    move = event.get("market_movement") or {}
    vs = move.get("vs_model") or {}
    edge_pp = num(edge_probability)
    mtype = str(market_type or "").lower()

    spread_move = num(move.get("spread_move"))
    total_move = num(move.get("total_move"))
    material = False
    if mtype == "total":
        material = (
            total_move is not None
            and abs(float(total_move)) >= MATERIAL_TOTAL_MOVE
        )
    else:
        material = (
            spread_move is not None
            and abs(float(spread_move)) >= MATERIAL_SPREAD_MOVE
        ) or bool(move.get("moved"))

    toward_model = vs.get("label") == "line_toward_model"
    strong_edge = CLASSIFICATION_THRESHOLDS["strong_bet"][
        "min_edge_prob_pp"
    ]

    invalidates = bool(
        toward_model
        and material
        and (
            edge_pp is None
            or float(edge_pp) < float(strong_edge)
        )
    )
    reason = None
    if invalidates:
        reason = (
            "Market movement already incorporates the model "
            "direction; remaining edge does not clear the "
            f"Strong Bet cushion ({strong_edge:g} pp)."
        )
    elif toward_model and material and edge_pp is not None:
        reason = (
            "Line moved toward the model, but remaining edge "
            f"{float(edge_pp):+.1f} pp still clears Strong Bet "
            "cushion — movement gate passes."
        )

    return {
        "invalidates": invalidates,
        "toward_model": toward_model,
        "material_move": material,
        "reason": reason,
        "vs_model_label": vs.get("label"),
    }


def build_prediction(
    *,
    market_type: str,
    selection: str,
    model_projection: float | None,
    market_projection: float | None,
    raw_probability: float | None,
    calibrated_probability: float | None,
    direction: str | None = None,
) -> dict[str, Any]:
    """Directional model view — not a bet recommendation."""

    raw = num(raw_probability)
    cal = num(calibrated_probability)
    has_prediction = cal is not None or model_projection is not None
    resolved_direction = direction
    if resolved_direction is None and raw is not None:
        resolved_direction = "aligned"

    return {
        "has_prediction": bool(has_prediction),
        "market_type": market_type,
        "selection": selection,
        "direction": resolved_direction,
        "model_projection": model_projection,
        "market_projection": market_projection,
        "raw_probability": (
            round(float(raw), 4) if raw is not None else None
        ),
        "calibrated_probability": (
            round(float(cal), 4) if cal is not None else None
        ),
        "note": (
            "Directional model view only — the system may still "
            "return Pass / No Bet when priced edge is not actionable."
        ),
    }


def _clears_band(
    *,
    band: dict[str, Any],
    edge_pp: float | None,
    ev: float | None,
    confidence: str,
    quality_label: str,
) -> bool:
    return (
        edge_pp is not None
        and float(edge_pp) >= float(band["min_edge_prob_pp"])
        and ev is not None
        and float(ev) >= float(band["min_ev_pct"])
        and confidence in set(band["min_confidence"])
        and quality_label in set(band["min_data_quality"])
    )


def qualify_bet(
    *,
    prediction: dict[str, Any],
    market_probability: float | None,
    expected_value: float | None,
    edge_probability: float | None,
    model_confidence: str | None,
    data_quality: dict[str, Any] | None,
    event: dict[str, Any] | None = None,
    market_type: str | None = None,
    min_ev_pct: float | None = None,
    min_edge_prob_pp: float | None = None,
    min_confidence: set[str] | None = None,
    min_data_quality: set[str] | None = None,
) -> dict[str, Any]:
    """
    Threshold-based classification: Strong Bet | Lean | Pass.

    Optional min_* overrides only tighten the Lean / Pass floor
    (used by stance profiles). They never invent a side when
    hard gates fail.
    """

    confidence = str(model_confidence or "Low").strip().title()
    quality = dict(data_quality or {})
    quality_label = str(quality.get("label") or "Low").title()

    ev = num(expected_value)
    edge_pp = num(edge_probability)
    market_p = num(market_probability)
    cal_p = num(prediction.get("calibrated_probability"))
    mtype = market_type or prediction.get("market_type")

    # Allow callers to tighten the Lean floor (never loosen Strong).
    lean_band = dict(CLASSIFICATION_THRESHOLDS["lean"])
    if min_ev_pct is not None:
        lean_band["min_ev_pct"] = max(
            float(lean_band["min_ev_pct"]), float(min_ev_pct)
        )
    if min_edge_prob_pp is not None:
        lean_band["min_edge_prob_pp"] = max(
            float(lean_band["min_edge_prob_pp"]),
            float(min_edge_prob_pp),
        )
    if min_confidence is not None:
        lean_band["min_confidence"] = frozenset(min_confidence)
    if min_data_quality is not None:
        lean_band["min_data_quality"] = frozenset(min_data_quality)

    strong_band = CLASSIFICATION_THRESHOLDS["strong_bet"]
    movement = market_movement_invalidates_edge(
        event=event,
        market_type=str(mtype) if mtype else None,
        edge_probability=edge_pp,
    )

    gates = {
        "has_prediction": bool(prediction.get("has_prediction")),
        "has_market_probability": market_p is not None,
        "min_edge": (
            edge_pp is not None
            and float(edge_pp) >= float(lean_band["min_edge_prob_pp"])
        ),
        "positive_ev": (
            ev is not None
            and float(ev) >= float(lean_band["min_ev_pct"])
        ),
        "confidence": confidence in set(lean_band["min_confidence"]),
        "data_quality": (
            quality_label in set(lean_band["min_data_quality"])
        ),
        "market_movement_ok": not bool(movement.get("invalidates")),
    }

    reasons_fail: list[str] = []
    reasons_pass: list[str] = []

    if not gates["has_prediction"]:
        reasons_fail.append("No model prediction available.")
    if not gates["has_market_probability"]:
        reasons_fail.append("Missing market implied probability.")

    if not gates["min_edge"]:
        reasons_fail.append(
            f"Edge {edge_pp if edge_pp is not None else '—'} pp "
            f"< +{lean_band['min_edge_prob_pp']:g} pp → Pass / No Bet."
        )
    else:
        reasons_pass.append(
            f"Edge {float(edge_pp):+.1f} pp ≥ "
            f"+{lean_band['min_edge_prob_pp']:g} pp."
        )

    if not gates["positive_ev"]:
        reasons_fail.append(
            f"EV {ev if ev is not None else '—'}% "
            f"< +{lean_band['min_ev_pct']:g}% → Pass / No Bet."
        )
    else:
        reasons_pass.append(
            f"EV {float(ev):+.1f}% ≥ +{lean_band['min_ev_pct']:g}%."
        )

    if not gates["confidence"]:
        reasons_fail.append(
            f"Confidence {confidence} below "
            f"{sorted(lean_band['min_confidence'])} → Pass / No Bet."
        )
    else:
        reasons_pass.append(f"Model confidence {confidence}.")

    if not gates["data_quality"]:
        reasons_fail.append(
            f"Data quality {quality_label} insufficient "
            f"({sorted(lean_band['min_data_quality'])} required) "
            "→ Pass / No Bet."
        )
    else:
        reasons_pass.append(f"Data quality {quality_label}.")

    if not gates["market_movement_ok"]:
        reasons_fail.append(
            movement.get("reason")
            or "Market movement invalidates edge → Pass / No Bet."
        )
    elif movement.get("reason"):
        reasons_pass.append(str(movement["reason"]))
    else:
        reasons_pass.append("Market movement does not invalidate edge.")

    lean_ok = all(gates.values())
    strong_ok = lean_ok and _clears_band(
        band=strong_band,
        edge_pp=edge_pp,
        ev=ev,
        confidence=confidence,
        quality_label=quality_label,
    )

    if strong_ok:
        status = "strong_bet"
        qualified = True
        no_bet = False
        summary = (
            "Strong Bet — calibrated probability clears Strong "
            "thresholds on edge, EV, High confidence, High data "
            "quality, and market-movement gate."
        )
    elif lean_ok:
        status = "lean"
        qualified = True
        no_bet = False
        summary = (
            "Lean — actionable edge clears Lean thresholds, but "
            "not Strong Bet requirements."
        )
    else:
        status = "pass"
        qualified = False
        no_bet = True
        failed = [key for key, ok in gates.items() if not ok]
        summary = (
            "Pass / No Bet — no actionable edge after threshold "
            "gates"
            + (f" (failed: {', '.join(failed)})." if failed else ".")
        )

    return {
        "qualified": qualified,
        "no_bet": no_bet,
        "actionable": qualified,
        "status": status,
        "label": STATUS_LABELS[status],
        "summary": summary,
        "gates": gates,
        "reasons_pass": reasons_pass,
        "reasons_fail": reasons_fail,
        "market_movement": movement,
        "thresholds": {
            "strong_bet": {
                "min_edge_prob_pp": strong_band["min_edge_prob_pp"],
                "min_ev_pct": strong_band["min_ev_pct"],
                "min_confidence": sorted(strong_band["min_confidence"]),
                "min_data_quality": sorted(
                    strong_band["min_data_quality"]
                ),
            },
            "lean": {
                "min_edge_prob_pp": lean_band["min_edge_prob_pp"],
                "min_ev_pct": lean_band["min_ev_pct"],
                "min_confidence": sorted(lean_band["min_confidence"]),
                "min_data_quality": sorted(
                    lean_band["min_data_quality"]
                ),
            },
            # Compat keys (Lean floor).
            "min_ev_pct": lean_band["min_ev_pct"],
            "min_edge_prob_pp": lean_band["min_edge_prob_pp"],
            "min_confidence": sorted(lean_band["min_confidence"]),
            "min_data_quality": sorted(lean_band["min_data_quality"]),
        },
        "calibrated_probability": cal_p,
        "market_probability": market_p,
        "expected_value": ev,
        "edge_probability": edge_pp,
        "model_confidence": confidence,
        "data_quality": quality_label,
    }


def evaluate_market_decision(
    *,
    market_type: str,
    selection: str,
    model_projection: float | None,
    market_projection: float | None,
    raw_probability: float | None,
    calibrated_probability: float | None,
    market_probability: float | None,
    expected_value: float | None,
    edge_probability: float | None,
    model_confidence: str | None,
    direction: str | None = None,
    event: dict[str, Any] | None = None,
    probability_calibrated: bool = False,
) -> dict[str, Any]:
    """Full prediction → Strong Bet / Lean / Pass payload."""

    prediction = build_prediction(
        market_type=market_type,
        selection=selection,
        model_projection=model_projection,
        market_projection=market_projection,
        raw_probability=raw_probability,
        calibrated_probability=calibrated_probability,
        direction=direction,
    )
    data_quality = assess_data_quality(
        event=event,
        probability_calibrated=probability_calibrated,
    )
    bet = qualify_bet(
        prediction=prediction,
        market_probability=market_probability,
        expected_value=expected_value,
        edge_probability=edge_probability,
        model_confidence=model_confidence,
        data_quality=data_quality,
        event=event,
        market_type=market_type,
    )
    return {
        "prediction": prediction,
        "data_quality": data_quality,
        "bet": bet,
        "pipeline": [
            "model_prediction",
            "raw_probability",
            "probability_calibration",
            "market_implied_probability",
            "expected_value",
            "model_confidence",
            "data_quality",
            "market_movement_check",
            "bet_classification",
        ],
    }
