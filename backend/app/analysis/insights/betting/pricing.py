"""
Betting probability / edge helpers.

American odds conventions for Phase 1 game markets.
"""

from __future__ import annotations

import math
from typing import Any


def american_to_implied_prob(
    odds: float | int | None,
) -> float | None:
    """Convert American odds to implied win probability (0–1)."""

    if odds is None:
        return None
    try:
        value = float(odds)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    if value > 0:
        return 100.0 / (value + 100.0)
    return abs(value) / (abs(value) + 100.0)


def implied_prob_to_american(
    probability: float | None,
) -> float | None:
    """Convert win probability (0–1) to fair American odds."""

    if probability is None:
        return None
    try:
        p = float(probability)
    except (TypeError, ValueError):
        return None
    if p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return round(-100.0 * p / (1.0 - p), 0)
    return round(100.0 * (1.0 - p) / p, 0)


def remove_vig_two_way(
    prob_a: float | None,
    prob_b: float | None,
) -> tuple[float | None, float | None]:
    if prob_a is None or prob_b is None:
        return prob_a, prob_b
    total = float(prob_a) + float(prob_b)
    if total <= 0:
        return prob_a, prob_b
    return float(prob_a) / total, float(prob_b) / total


def spread_to_cover_probability(
    model_spread: float | None,
    market_spread: float | None,
    *,
    scale: float = 7.5,
) -> float | None:
    """
    Approximate favorite-cover probability from model vs market.

    ``model_spread`` / ``market_spread`` use home-team convention
    (negative = home favored), matching nflverse schedules.
    """

    if model_spread is None or market_spread is None:
        return None
    # Edge in points from the home side.
    edge = float(market_spread) - float(model_spread)
    # Logistic transform: each point of edge moves cover odds.
    return 1.0 / (1.0 + math.exp(-edge / max(scale, 0.1)))


def total_to_over_probability(
    model_total: float | None,
    market_total: float | None,
    *,
    scale: float = 6.5,
) -> float | None:
    if model_total is None or market_total is None:
        return None
    edge = float(model_total) - float(market_total)
    return 1.0 / (1.0 + math.exp(-edge / max(scale, 0.1)))


def expected_value(
    model_probability: float | None,
    american_odds: float | int | None,
) -> float | None:
    """
    Expected value as a decimal fraction of stake.

    EV = model_p * profit_per_unit - (1 - model_p)
    """

    if model_probability is None or american_odds is None:
        return None
    try:
        p = float(model_probability)
        odds = float(american_odds)
    except (TypeError, ValueError):
        return None
    if p <= 0 or p >= 1:
        return None
    if odds > 0:
        profit = odds / 100.0
    else:
        profit = 100.0 / abs(odds)
    return (p * profit) - (1.0 - p)


def confidence_from_edge(
    *,
    edge_points: float | None = None,
    edge_probability: float | None = None,
    model_coverage: bool = True,
    thresholds: dict[str, Any] | None = None,
    market_type: str | None = None,
    market_performance: dict[str, Any] | None = None,
    model_agreement: float | None = None,
) -> str:
    """
    Map edge magnitude → High / Moderate / Low.

    When market performance is available, floors are allocated
    per market (spread / total / moneyline) instead of one global
    cutoff. Model disagreement shrinks effective edge so a wide
    ensemble cannot mint High confidence from a coincidental mean.
    """

    from app.analysis.insights.betting.market_performance import (
        apply_market_confidence_thresholds,
    )
    from app.analysis.insights.betting.model_disagreement import (
        agreement_edge_factor,
    )

    factor = agreement_edge_factor(model_agreement)
    adj_points = (
        None
        if edge_points is None
        else float(edge_points) * factor
    )
    adj_prob = (
        None
        if edge_probability is None
        else float(edge_probability) * factor
    )

    return apply_market_confidence_thresholds(
        market_type=market_type,
        edge_points=adj_points,
        edge_probability=adj_prob,
        model_coverage=model_coverage,
        thresholds=thresholds,
        market_performance=market_performance,
    )


def confidence_explanation(label: str) -> str:
    key = str(label or "").strip().lower()
    if key == "high":
        return (
            "Point-edge bucket historically shows useful separation "
            "(win rate / ROI / CLV) versus smaller edges."
        )
    if key == "moderate":
        return (
            "Edge clears the learned noise floor but is below the "
            "High separation band — treat size carefully."
        )
    return (
        "Edge sits in buckets that have not historically separated "
        "from noise — directional only."
    )


def num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
