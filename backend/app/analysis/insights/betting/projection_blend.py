"""
Confidence-dependent market residual shrink.

Projection structure:
  market baseline
       +
  shrink(confidence) * (team_strength - market)
       +
  situational residual (injuries, calibration)
       =
  InsightPilot projection

The market remains the baseline. Model influence scales with
projection confidence so the model must earn the right to
move farther from the market.

Blend weights below are provisional priors used as residual
shrink factors. They should be replaced by historically
backtested / learned weights via ``load_blend_policy`` once
enough settled residuals exist.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.pricing import num


# Provisional priors — not yet learned from backtests.
# Keys are projection-confidence labels used before market-edge
# confidence is computed on priced markets.
DEFAULT_BLEND_WEIGHTS: dict[str, dict[str, float]] = {
    "Low": {"market": 0.85, "model": 0.15},
    "Moderate": {"market": 0.75, "model": 0.25},
    "High": {"market": 0.65, "model": 0.35},
}

# CFB is noisier than NFL but still needs room to express matchups.
# Model weights are a bit higher than the first CFB prior so opposite-sign
# matchup residuals can clear the spread deadband after shrink.
CFB_BLEND_WEIGHTS: dict[str, dict[str, float]] = {
    "Low": {"market": 0.75, "model": 0.25},
    "Moderate": {"market": 0.65, "model": 0.35},
    "High": {"market": 0.55, "model": 0.45},
}

BLEND_POLICY_SOURCE = "prior_v1"
BLEND_POLICY_SOURCE_CFB = "prior_cfb_v1"


def load_blend_policy(
    *,
    season: int | None = None,
    sport: str | None = None,
) -> dict[str, Any]:
    """
    Return the active market/model blend policy.

    Today this returns hardcoded priors. Hook point for loading
    season-specific weights learned from settled projection
    residuals (backtest / calibration table).
    """

    del season  # reserved for learned-policy lookup
    sport_key = str(sport or "NFL").strip().upper()
    table = (
        CFB_BLEND_WEIGHTS
        if sport_key == "CFB"
        else DEFAULT_BLEND_WEIGHTS
    )
    return {
        "weights_by_confidence": {
            key: dict(value) for key, value in table.items()
        },
        "source": (
            BLEND_POLICY_SOURCE_CFB
            if sport_key == "CFB"
            else BLEND_POLICY_SOURCE
        ),
        "learned": False,
        "sport": sport_key,
        "note": (
            "Provisional confidence-dependent priors. "
            "Replace with backtested weights when residual "
            "history supports learning."
        ),
    }


def estimate_projection_confidence(
    *,
    strength_detail: dict[str, Any] | None,
    home_games: int | None = None,
    away_games: int | None = None,
) -> str:
    """
    Confidence in the *model adjustment*, not market-edge confidence.

    Uses matchup separation and sample depth so strong, well-sampled
    signals earn more weight vs the market.
    """

    detail = strength_detail or {}
    if not detail.get("available"):
        return "Low"

    home_m = abs(float(num(detail.get("home_matchup")) or 0.0))
    away_m = abs(float(num(detail.get("away_matchup")) or 0.0))
    matchup_mag = home_m + away_m
    # Informative SOS differential supports trusting the model more.
    sos_mag = abs(float(num(detail.get("sos_differential")) or 0.0))
    signal_mag = matchup_mag + 0.35 * sos_mag
    games = min(
        int(home_games or detail.get("home_games") or 0),
        int(away_games or detail.get("away_games") or 0),
    )
    if games <= 0:
        # Profiles present but game counts omitted — use matchup only.
        if signal_mag >= 2.5:
            return "High"
        if signal_mag >= 1.2:
            return "Moderate"
        return "Low"

    if games >= 4 and signal_mag >= 2.5:
        return "High"
    if games >= 3 and signal_mag >= 1.2:
        return "Moderate"
    if games >= 2 and signal_mag >= 0.75:
        return "Moderate"
    return "Low"


def resolve_blend_weights(
    confidence: str,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, float]:
    active = policy or load_blend_policy()
    table = active.get("weights_by_confidence") or DEFAULT_BLEND_WEIGHTS
    label = str(confidence or "Low").strip().title()
    if label not in table:
        label = "Low"
    weights = dict(table[label])
    market_w = float(weights.get("market") or 0.85)
    model_w = float(weights.get("model") or 0.15)
    total = market_w + model_w
    if total <= 0:
        return {"market": 0.85, "model": 0.15, "confidence": label}
    return {
        "market": market_w / total,
        "model": model_w / total,
        "confidence": label,
    }


def apply_market_anchor_blend(
    *,
    market_home: float | None,
    market_away: float | None,
    model_home: float | None,
    model_away: float | None,
    confidence: str | None = None,
    policy: dict[str, Any] | None = None,
) -> tuple[float | None, float | None, dict[str, Any]]:
    """
    Market baseline + confidence-scaled model adjustment.

    Equivalent form:
      final = market + model_weight * (model − market)
            = (1 − α) * market + α * model

    Low confidence keeps α small; high confidence earns a larger
    departure from the market.
    """

    active = policy or load_blend_policy()
    conf = str(confidence or "Low")
    weights = resolve_blend_weights(conf, policy=active)
    market_w = float(weights["market"])
    model_w = float(weights["model"])
    meta = {
        "confidence": weights["confidence"],
        "market_weight": round(market_w, 4),
        "model_weight": round(model_w, 4),
        "policy_source": active.get("source"),
        "policy_learned": bool(active.get("learned")),
        "formula": "market + model_weight * (model - market)",
    }

    if market_home is None or market_away is None:
        if model_home is None or model_away is None:
            return None, None, {**meta, "mode": "unavailable"}
        meta["mode"] = "model_only"
        return (
            round(float(model_home), 1),
            round(float(model_away), 1),
            meta,
        )
    if model_home is None or model_away is None:
        meta["mode"] = "market_only"
        meta["model_weight"] = 0.0
        meta["market_weight"] = 1.0
        return (
            round(float(market_home), 1),
            round(float(market_away), 1),
            meta,
        )

    # Market anchor + earned model delta.
    home_delta = float(model_home) - float(market_home)
    away_delta = float(model_away) - float(market_away)
    home = float(market_home) + model_w * home_delta
    away = float(market_away) + model_w * away_delta
    meta.update(
        {
            "mode": "market_anchor",
            "home_model_delta": round(home_delta, 2),
            "away_model_delta": round(away_delta, 2),
            "home_applied_delta": round(model_w * home_delta, 2),
            "away_applied_delta": round(model_w * away_delta, 2),
        }
    )
    return round(home, 1), round(away, 1), meta
