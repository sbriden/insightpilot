"""
Separate model predictions from bet recommendations.

Objective:
  Identify bets where calibrated probability meaningfully exceeds
  market-implied probability at the offered price — not "pick a
  side for every game."

Pipeline:
  model prediction → raw probability → calibration → market price
  → push-aware EV → confidence → data quality → uncertainty
  → market-movement → Strong Bet | Lean | Pass

Pass is first-class. Large edges do not override weak calibration
or high uncertainty.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.pricing import num


# Prior bands until empirical thresholds are active.
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

PASS_MIN_EDGE_PROB_PP = CLASSIFICATION_THRESHOLDS["lean"]["min_edge_prob_pp"]
PASS_MIN_EV_PCT = CLASSIFICATION_THRESHOLDS["lean"]["min_ev_pct"]
PASS_MIN_CONFIDENCE = CLASSIFICATION_THRESHOLDS["lean"]["min_confidence"]
PASS_MIN_DATA_QUALITY = CLASSIFICATION_THRESHOLDS["lean"]["min_data_quality"]

MATERIAL_SPREAD_MOVE = 0.5
MATERIAL_TOTAL_MOVE = 0.5

# Uncertainty Pass floors (large edge cannot override).
MIN_MODEL_AGREEMENT = 0.45
MAX_SCORE_SIGMA_MARGIN = 22.0
MAX_ENTROPY_PROXY = 0.95

MIN_EV_PCT = PASS_MIN_EV_PCT
MIN_EDGE_PROB_PP = PASS_MIN_EDGE_PROB_PP
MIN_CONFIDENCE = set(PASS_MIN_CONFIDENCE)
MIN_DATA_QUALITY = set(PASS_MIN_DATA_QUALITY)

STATUS_LABELS = {
    "strong_bet": "Strong Bet",
    "lean": "Lean",
    "pass": "Pass",
}

REASON_CODES = {
    "NO_PREDICTION": "No model prediction available.",
    "NO_MARKET_PRICE": "Missing market implied probability or offered odds.",
    "EV_BELOW_FLOOR": "Expected value below band floor → Pass / No Bet.",
    "EDGE_BELOW_FLOOR": "Probability edge below band floor → Pass / No Bet.",
    "CONFIDENCE_TOO_LOW": "Model confidence below band requirement → Pass.",
    "DATA_QUALITY_LOW": "Data quality insufficient for band → Pass.",
    "UNCERTAINTY_HIGH": (
        "Probability uncertainty / disagreement too high → Pass "
        "(edge does not override)."
    ),
    "CALIBRATION_INACTIVE": (
        "Probability calibration inactive with thin support → Pass."
    ),
    "LINE_MOVED_AGAINST": (
        "Market movement already incorporates the model direction."
    ),
    "PASSES_STRONG": "Clears Strong Bet thresholds.",
    "PASSES_LEAN": "Clears Lean thresholds (not Strong).",
}


def resolve_classification_thresholds(
    learned: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge prior bands with optional learned floors."""

    strong = dict(CLASSIFICATION_THRESHOLDS["strong_bet"])
    lean = dict(CLASSIFICATION_THRESHOLDS["lean"])
    source = "prior"
    active = False
    if learned and isinstance(learned, dict):
        active = bool(learned.get("active"))
        source = str(learned.get("source") or learned.get("method") or "prior")
        strong_l = learned.get("strong_bet") or {}
        lean_l = learned.get("lean") or {}
        if strong_l.get("min_edge_prob_pp") is not None:
            strong["min_edge_prob_pp"] = float(strong_l["min_edge_prob_pp"])
        if strong_l.get("min_ev_pct") is not None:
            strong["min_ev_pct"] = float(strong_l["min_ev_pct"])
        if lean_l.get("min_edge_prob_pp") is not None:
            lean["min_edge_prob_pp"] = float(lean_l["min_edge_prob_pp"])
        if lean_l.get("min_ev_pct") is not None:
            lean["min_ev_pct"] = float(lean_l["min_ev_pct"])
        # Enforce Strong ≻ Lean.
        lean["min_edge_prob_pp"] = min(
            float(lean["min_edge_prob_pp"]),
            float(strong["min_edge_prob_pp"]),
        )
        lean["min_ev_pct"] = min(
            float(lean["min_ev_pct"]),
            float(strong["min_ev_pct"]),
        )
        if not active:
            source = f"{source}_inactive_prior_floors"
    return {
        "strong_bet": strong,
        "lean": lean,
        "source": source,
        "active": active,
        "metrics": (learned or {}).get("metrics"),
        "note": (learned or {}).get("note"),
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


def assess_uncertainty(
    *,
    event: dict[str, Any] | None = None,
    market: dict[str, Any] | None = None,
    data_quality: dict[str, Any] | None = None,
    model_agreement: float | None = None,
    probability_calibrated: bool = False,
) -> dict[str, Any]:
    """
    Hard Pass when probability quality is too weak for any bet size.

    Large edge_probability does not override this gate.
    """

    event = event or {}
    market = market or {}
    quality = data_quality or {}
    quality_label = str(quality.get("label") or "Low").title()

    agreement = num(model_agreement)
    if agreement is None:
        disagreement = (
            market.get("model_disagreement")
            or event.get("model_disagreement")
            or {}
        )
        mtype = str(market.get("market_type") or "").lower()
        block = disagreement.get("total") if mtype == "total" else (
            disagreement.get("spread")
        )
        if isinstance(block, dict):
            agreement = num(block.get("model_agreement"))
        elif num(disagreement.get("model_agreement")) is not None:
            agreement = num(disagreement.get("model_agreement"))

    dist = event.get("score_distribution") or {}
    uncertainty = dist.get("uncertainty") or {}
    sigma_margin = num(uncertainty.get("sigma_margin")) or num(
        (dist.get("sigma") or {}).get("margin")
    )
    entropy = num(uncertainty.get("entropy_proxy"))

    reasons: list[str] = []
    codes: list[str] = []
    high = False

    if quality_label == "Low":
        high = True
        codes.append("DATA_QUALITY_LOW")
        reasons.append("Data quality Low — probability support too thin.")

    if agreement is not None and float(agreement) < MIN_MODEL_AGREEMENT:
        high = True
        codes.append("UNCERTAINTY_HIGH")
        reasons.append(
            f"Model agreement {float(agreement):.2f} < "
            f"{MIN_MODEL_AGREEMENT:.2f}."
        )

    if (
        sigma_margin is not None
        and float(sigma_margin) >= MAX_SCORE_SIGMA_MARGIN
    ):
        high = True
        if "UNCERTAINTY_HIGH" not in codes:
            codes.append("UNCERTAINTY_HIGH")
        reasons.append(
            f"Score-distribution σ_margin {float(sigma_margin):.1f} "
            f"≥ {MAX_SCORE_SIGMA_MARGIN:g}."
        )

    if entropy is not None and float(entropy) >= MAX_ENTROPY_PROXY:
        high = True
        if "UNCERTAINTY_HIGH" not in codes:
            codes.append("UNCERTAINTY_HIGH")
        reasons.append(
            f"Entropy proxy {float(entropy):.2f} ≥ {MAX_ENTROPY_PROXY:g}."
        )

    # Calibration inactive + Low quality → extra uncertainty flag.
    if not probability_calibrated and quality_label == "Low":
        high = True
        codes.append("CALIBRATION_INACTIVE")
        reasons.append(
            "Calibration inactive with Low data quality."
        )

    return {
        "high_uncertainty": high,
        "model_agreement": agreement,
        "sigma_margin": sigma_margin,
        "entropy_proxy": entropy,
        "reason_codes": codes,
        "reasons": reasons,
    }


def market_movement_invalidates_edge(
    *,
    event: dict[str, Any] | None,
    market_type: str | None = None,
    edge_probability: float | None = None,
    strong_edge_pp: float | None = None,
) -> dict[str, Any]:
    """
    Hard No-Bet gate: line already moved toward the model.

    Remaining edge must still clear the Strong Bet cushion.
    """

    event = event or {}
    move = event.get("market_movement") or {}
    vs = move.get("vs_model") or {}
    edge_pp = num(edge_probability)
    mtype = str(market_type or "").lower()

    spread_move = num(move.get("spread_move"))
    total_move = num(move.get("total_move"))
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
    strong_edge = float(
        strong_edge_pp
        if strong_edge_pp is not None
        else CLASSIFICATION_THRESHOLDS["strong_bet"]["min_edge_prob_pp"]
    )

    invalidates = bool(
        toward_model
        and material
        and (
            edge_pp is None
            or float(edge_pp) < strong_edge
        )
    )
    reason = None
    code = None
    if invalidates:
        code = "LINE_MOVED_AGAINST"
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
        "reason_code": code,
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


def _reason(
    code: str,
    detail: str | None = None,
) -> dict[str, str]:
    message = REASON_CODES.get(code, code)
    if detail:
        message = f"{message} {detail}".strip()
    return {"code": code, "message": message}


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
    market: dict[str, Any] | None = None,
    offered_odds: float | int | None = None,
    push_probability: float | None = None,
    model_agreement: float | None = None,
    probability_calibrated: bool = False,
    classification_thresholds: dict[str, Any] | None = None,
    min_ev_pct: float | None = None,
    min_edge_prob_pp: float | None = None,
    min_confidence: set[str] | None = None,
    min_data_quality: set[str] | None = None,
) -> dict[str, Any]:
    """
    Threshold-based classification: Strong Bet | Lean | Pass.

    EV at offered price is the primary gate; edge pp is secondary.
    Uncertainty / data-quality failures force Pass even with large edge.
    """

    confidence = str(model_confidence or "Low").strip().title()
    quality = dict(data_quality or {})
    quality_label = str(quality.get("label") or "Low").title()

    resolved = resolve_classification_thresholds(
        classification_thresholds
    )
    lean_band = dict(resolved["lean"])
    strong_band = dict(resolved["strong_bet"])

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

    ev = num(expected_value)
    edge_pp = num(edge_probability)
    market_p = num(market_probability)
    cal_p = num(prediction.get("calibrated_probability"))
    raw_p = num(prediction.get("raw_probability"))
    mtype = market_type or prediction.get("market_type")
    push = num(push_probability)

    movement = market_movement_invalidates_edge(
        event=event,
        market_type=str(mtype) if mtype else None,
        edge_probability=edge_pp,
        strong_edge_pp=float(strong_band["min_edge_prob_pp"]),
    )
    uncertainty = assess_uncertainty(
        event=event,
        market=market,
        data_quality=quality,
        model_agreement=model_agreement,
        probability_calibrated=probability_calibrated,
    )

    has_price = market_p is not None or offered_odds is not None
    gates = {
        "has_prediction": bool(prediction.get("has_prediction")),
        "has_market_probability": has_price,
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
        "uncertainty_ok": not bool(uncertainty.get("high_uncertainty")),
        "market_movement_ok": not bool(movement.get("invalidates")),
    }

    reason_entries: list[dict[str, str]] = []
    reasons_fail: list[str] = []
    reasons_pass: list[str] = []

    if not gates["has_prediction"]:
        entry = _reason("NO_PREDICTION")
        reason_entries.append(entry)
        reasons_fail.append(entry["message"])
    if not gates["has_market_probability"]:
        entry = _reason("NO_MARKET_PRICE")
        reason_entries.append(entry)
        reasons_fail.append(entry["message"])

    if not gates["positive_ev"]:
        entry = _reason(
            "EV_BELOW_FLOOR",
            f"EV {ev if ev is not None else '—'}% "
            f"< +{lean_band['min_ev_pct']:g}%.",
        )
        reason_entries.append(entry)
        reasons_fail.append(entry["message"])
    else:
        reasons_pass.append(
            f"EV {float(ev):+.1f}% ≥ +{lean_band['min_ev_pct']:g}%."
        )

    if not gates["min_edge"]:
        entry = _reason(
            "EDGE_BELOW_FLOOR",
            f"Edge {edge_pp if edge_pp is not None else '—'} pp "
            f"< +{lean_band['min_edge_prob_pp']:g} pp.",
        )
        reason_entries.append(entry)
        reasons_fail.append(entry["message"])
    else:
        reasons_pass.append(
            f"Edge {float(edge_pp):+.1f} pp ≥ "
            f"+{lean_band['min_edge_prob_pp']:g} pp."
        )

    if not gates["confidence"]:
        entry = _reason(
            "CONFIDENCE_TOO_LOW",
            f"Confidence {confidence} not in "
            f"{sorted(lean_band['min_confidence'])}.",
        )
        reason_entries.append(entry)
        reasons_fail.append(entry["message"])
    else:
        reasons_pass.append(f"Model confidence {confidence}.")

    if not gates["data_quality"]:
        entry = _reason(
            "DATA_QUALITY_LOW",
            f"Data quality {quality_label} not in "
            f"{sorted(lean_band['min_data_quality'])}.",
        )
        reason_entries.append(entry)
        reasons_fail.append(entry["message"])
    else:
        reasons_pass.append(f"Data quality {quality_label}.")

    if not gates["uncertainty_ok"]:
        for code in uncertainty.get("reason_codes") or ["UNCERTAINTY_HIGH"]:
            msg = (
                "; ".join(uncertainty.get("reasons") or [])
                or REASON_CODES.get(code, code)
            )
            entry = {"code": code, "message": msg}
            reason_entries.append(entry)
            reasons_fail.append(msg)
    else:
        reasons_pass.append("Uncertainty within acceptable bounds.")

    if not gates["market_movement_ok"]:
        entry = _reason(
            "LINE_MOVED_AGAINST",
            movement.get("reason"),
        )
        reason_entries.append(entry)
        reasons_fail.append(entry["message"])
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
            "thresholds on EV, edge, confidence, data quality, "
            "uncertainty, and market-movement gates."
        )
        reason_entries.append(_reason("PASSES_STRONG"))
        reasons_pass.append(REASON_CODES["PASSES_STRONG"])
    elif lean_ok:
        status = "lean"
        qualified = True
        no_bet = False
        summary = (
            "Lean — actionable edge clears Lean thresholds, but "
            "not Strong Bet requirements."
        )
        reason_entries.append(_reason("PASSES_LEAN"))
        reasons_pass.append(REASON_CODES["PASSES_LEAN"])
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

    pricing_audit = {
        "offered_odds": offered_odds,
        "calibrated_probability": (
            round(float(cal_p), 4) if cal_p is not None else None
        ),
        "raw_probability": (
            round(float(raw_p), 4) if raw_p is not None else None
        ),
        "push_probability": (
            round(float(push), 4) if push is not None else None
        ),
        "market_probability": (
            round(float(market_p), 4) if market_p is not None else None
        ),
        "expected_value_pct": (
            round(float(ev), 2) if ev is not None else None
        ),
        "edge_probability_pp": (
            round(float(edge_pp), 2) if edge_pp is not None else None
        ),
        "probability_calibrated": bool(probability_calibrated),
        "model_agreement": uncertainty.get("model_agreement"),
        "sigma_margin": uncertainty.get("sigma_margin"),
    }

    return {
        "qualified": qualified,
        "no_bet": no_bet,
        "actionable": qualified,
        "status": status,
        "label": STATUS_LABELS[status],
        "summary": summary,
        "gates": gates,
        "reason_codes": [r["code"] for r in reason_entries],
        "reasons": reason_entries,
        "reasons_pass": reasons_pass,
        "reasons_fail": reasons_fail,
        "market_movement": movement,
        "uncertainty": uncertainty,
        "thresholds_used": {
            "source": resolved["source"],
            "active": resolved["active"],
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
            "metrics": resolved.get("metrics"),
            "note": resolved.get("note"),
        },
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
            "min_ev_pct": lean_band["min_ev_pct"],
            "min_edge_prob_pp": lean_band["min_edge_prob_pp"],
            "min_confidence": sorted(lean_band["min_confidence"]),
            "min_data_quality": sorted(lean_band["min_data_quality"]),
        },
        "pricing_audit": pricing_audit,
        "calibrated_probability": cal_p,
        "market_probability": market_p,
        "expected_value": ev,
        "edge_probability": edge_pp,
        "ev_pct": ev,
        "edge_prob_pp": edge_pp,
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
    market: dict[str, Any] | None = None,
    probability_calibrated: bool = False,
    offered_odds: float | int | None = None,
    push_probability: float | None = None,
    model_agreement: float | None = None,
    classification_thresholds: dict[str, Any] | None = None,
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
    market_payload = dict(market or {})
    market_payload.setdefault("market_type", market_type)
    data_quality = assess_data_quality(
        event=event,
        market=market_payload,
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
        market=market_payload,
        market_type=market_type,
        offered_odds=offered_odds,
        push_probability=push_probability,
        model_agreement=model_agreement,
        probability_calibrated=probability_calibrated,
        classification_thresholds=classification_thresholds,
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
            "push_aware_expected_value",
            "model_confidence",
            "data_quality",
            "uncertainty_check",
            "market_movement_check",
            "bet_classification",
        ],
    }
