"""
Market residual projection model.

InsightPilot does not rebuild the game from scratch. It predicts
where the market is likely to be wrong:

  market baseline
       +
  model residual
       =
  InsightPilot projection

Team strength, pace, and (later) learned residual features produce
a raw residual. Confidence shrinks that residual so the model must
earn the right to move off the market. Situational effects
(injuries, season calibration) are additional residual layers.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.projection_blend import (
    estimate_projection_confidence,
    load_blend_policy,
    resolve_blend_weights,
)
from app.analysis.insights.betting.team_strength import (
    project_strength_scores,
)


def predict_score_residuals(
    *,
    market_home: float | None,
    market_away: float | None,
    home_team_id: str | None = None,
    away_team_id: str | None = None,
    strength_context: dict[str, Any] | None = None,
    recent_ppg: dict[str, float] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Predict home/away score residuals vs the market.

    Returns a structured residual payload. Call
    ``apply_score_residuals`` to form final projections, optionally
    after adding situational residual layers.
    """

    active = policy or load_blend_policy()
    strength_home = None
    strength_away = None
    detail: dict[str, Any] = {"available": False}

    if home_team_id and away_team_id and strength_context:
        strength_home, strength_away, detail = project_strength_scores(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            context=strength_context,
        )

    if not detail.get("available") and recent_ppg:
        home_ppg = recent_ppg.get(str(home_team_id or ""))
        away_ppg = recent_ppg.get(str(away_team_id or ""))
        if home_ppg is not None and away_ppg is not None:
            strength_home = float(home_ppg)
            strength_away = float(away_ppg)
            detail = {
                "available": True,
                "fallback": "recent_ppg",
                "home_matchup": 0.0,
                "away_matchup": 0.0,
                "home_games": 0,
                "away_games": 0,
            }

    confidence = estimate_projection_confidence(
        strength_detail=detail,
        home_games=detail.get("home_games"),
        away_games=detail.get("away_games"),
    )
    weights = resolve_blend_weights(confidence, policy=active)
    shrink = float(weights["model"])

    raw_home = None
    raw_away = None
    if (
        market_home is not None
        and market_away is not None
        and strength_home is not None
        and strength_away is not None
    ):
        # Core residual: disagreement between strength view and market.
        raw_home = float(strength_home) - float(market_home)
        raw_away = float(strength_away) - float(market_away)
    elif strength_home is not None and strength_away is not None:
        # No market — residual is undefined; absolute strength only.
        raw_home = 0.0
        raw_away = 0.0

    shrunk_home = (
        None if raw_home is None else round(shrink * raw_home, 3)
    )
    shrunk_away = (
        None if raw_away is None else round(shrink * raw_away, 3)
    )

    return {
        "available": bool(detail.get("available")),
        "architecture": "market + residual",
        "formula": (
            "final = market + shrink(confidence) * "
            "(team_strength - market) + situational"
        ),
        "projection_confidence": confidence,
        "shrink": round(shrink, 4),
        "market_weight": round(float(weights["market"]), 4),
        "model_weight": round(shrink, 4),
        "policy_source": active.get("source"),
        "policy_learned": bool(active.get("learned")),
        "market_home": market_home,
        "market_away": market_away,
        "strength_home": strength_home,
        "strength_away": strength_away,
        "raw_residual_home": (
            None if raw_home is None else round(raw_home, 3)
        ),
        "raw_residual_away": (
            None if raw_away is None else round(raw_away, 3)
        ),
        "residual_home": shrunk_home,
        "residual_away": shrunk_away,
        "strength": detail,
        "situational_residual_home": 0.0,
        "situational_residual_away": 0.0,
    }


def add_situational_residuals(
    residual_model: dict[str, Any],
    *,
    home_adjustment: float = 0.0,
    away_adjustment: float = 0.0,
) -> dict[str, Any]:
    """
    Attach situational residual layers (injuries, calibration, etc.).

    These are additive to the shrunk team-strength residual and are
    not confidence-shrunk again — callers should already dampen them
    (e.g. injury market weight, calibration dampen).
    """

    payload = dict(residual_model or {})
    home_sit = float(home_adjustment or 0.0)
    away_sit = float(away_adjustment or 0.0)
    payload["situational_residual_home"] = round(home_sit, 3)
    payload["situational_residual_away"] = round(away_sit, 3)
    return payload


def apply_score_residuals(
    residual_model: dict[str, Any],
) -> tuple[float | None, float | None, dict[str, Any]]:
    """
    final = market + strength_residual + situational_residual
    """

    payload = dict(residual_model or {})
    market_home = num(payload.get("market_home"))
    market_away = num(payload.get("market_away"))
    residual_home = num(payload.get("residual_home"))
    residual_away = num(payload.get("residual_away"))
    sit_home = float(payload.get("situational_residual_home") or 0.0)
    sit_away = float(payload.get("situational_residual_away") or 0.0)

    meta = {
        "architecture": "market + residual",
        "confidence": payload.get("projection_confidence"),
        "shrink": payload.get("shrink"),
        "market_weight": payload.get("market_weight"),
        "model_weight": payload.get("model_weight"),
        "policy_source": payload.get("policy_source"),
        "policy_learned": payload.get("policy_learned"),
        "raw_residual_home": payload.get("raw_residual_home"),
        "raw_residual_away": payload.get("raw_residual_away"),
        "residual_home": residual_home,
        "residual_away": residual_away,
        "situational_residual_home": sit_home,
        "situational_residual_away": sit_away,
        "formula": payload.get("formula"),
    }

    if market_home is None or market_away is None:
        strength_home = num(payload.get("strength_home"))
        strength_away = num(payload.get("strength_away"))
        if strength_home is None or strength_away is None:
            return None, None, {**meta, "mode": "unavailable"}
        # No market baseline — fall back to absolute strength + situational.
        home = float(strength_home) + sit_home
        away = float(strength_away) + sit_away
        meta["mode"] = "model_only"
        meta["total_residual_home"] = round(sit_home, 3)
        meta["total_residual_away"] = round(sit_away, 3)
        return round(home, 1), round(away, 1), meta

    if residual_home is None or residual_away is None:
        meta["mode"] = "market_only"
        meta["total_residual_home"] = round(sit_home, 3)
        meta["total_residual_away"] = round(sit_away, 3)
        return (
            round(float(market_home) + sit_home, 1),
            round(float(market_away) + sit_away, 1),
            meta,
        )

    total_home = float(residual_home) + sit_home
    total_away = float(residual_away) + sit_away
    home = float(market_home) + total_home
    away = float(market_away) + total_away
    meta.update(
        {
            "mode": "market_plus_residual",
            "total_residual_home": round(total_home, 3),
            "total_residual_away": round(total_away, 3),
            "home_applied_delta": round(total_home, 2),
            "away_applied_delta": round(total_away, 2),
        }
    )
    return round(home, 1), round(away, 1), meta


def calibration_score_deltas(
    *,
    projected_home: float | None,
    projected_away: float | None,
    feedback: dict[str, Any] | None,
) -> tuple[float, float]:
    """
    Express season calibration as residual deltas.

    Mirrors ``apply_calibration_to_scores`` without requiring the
    absolute scores to already include the adjustment.
    """

    if (
        projected_home is None
        or projected_away is None
        or not feedback
        or not feedback.get("active")
    ):
        return 0.0, 0.0
    total_bias = num(feedback.get("total_bias")) or 0.0
    spread_bias = num(feedback.get("spread_bias")) or 0.0
    # Same transform as apply_calibration_to_scores:
    # home' = home - total/2 + spread/2
    # away' = away - total/2 - spread/2
    home_delta = (-total_bias / 2.0) + (spread_bias / 2.0)
    away_delta = (-total_bias / 2.0) - (spread_bias / 2.0)
    return round(home_delta, 3), round(away_delta, 3)
