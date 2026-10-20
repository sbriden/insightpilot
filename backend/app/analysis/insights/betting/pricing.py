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


def win_probability_from_spread(
    model_spread: float | None,
    *,
    scale: float = 7.0,
) -> float | None:
    """
    Home win probability from projected home-team spread
    (negative = home favored), logistic benchmark.
    """

    if model_spread is None:
        return None
    return 1.0 / (
        1.0 + math.exp(float(model_spread) / max(scale, 0.1))
    )


def cover_probability_from_engine(
    *,
    engine: str = "logistic",
    model_spread: float | None = None,
    market_spread: float | None = None,
    simulation: dict[str, Any] | None = None,
    scale: float = 7.5,
) -> float | None:
    """
    Home-cover probability. Prefers simulation when requested
    and available; otherwise logistic fallback.
    """

    label = str(engine or "logistic").strip().lower()
    if label in {"simulation", "sim", "bivariate", "score_distribution"}:
        from app.analysis.insights.betting.score_distribution import (
            probabilities_from_simulation,
        )

        probs = probabilities_from_simulation(
            simulation,
            market_spread=market_spread,
        )
        if probs.get("home_cover") is not None:
            return float(probs["home_cover"])
    return spread_to_cover_probability(
        model_spread,
        market_spread,
        scale=scale,
    )


def over_probability_from_engine(
    *,
    engine: str = "logistic",
    model_total: float | None = None,
    market_total: float | None = None,
    simulation: dict[str, Any] | None = None,
    scale: float = 6.5,
) -> float | None:
    label = str(engine or "logistic").strip().lower()
    if label in {"simulation", "sim", "bivariate", "score_distribution"}:
        from app.analysis.insights.betting.score_distribution import (
            probabilities_from_simulation,
        )

        probs = probabilities_from_simulation(
            simulation,
            market_total=market_total,
        )
        if probs.get("over") is not None:
            return float(probs["over"])
    return total_to_over_probability(
        model_total,
        market_total,
        scale=scale,
    )


def win_probability_from_engine(
    *,
    engine: str = "logistic",
    model_spread: float | None = None,
    simulation: dict[str, Any] | None = None,
    scale: float = 7.0,
) -> float | None:
    """Home win probability."""

    label = str(engine or "logistic").strip().lower()
    if label in {"simulation", "sim", "bivariate", "score_distribution"}:
        from app.analysis.insights.betting.score_distribution import (
            probabilities_from_simulation,
        )

        probs = probabilities_from_simulation(simulation)
        if probs.get("home_win") is not None:
            return float(probs["home_win"])
    return win_probability_from_spread(model_spread, scale=scale)


def american_profit_per_unit(
    american_odds: float | int | None,
) -> float | None:
    """Net profit on a winning one-unit stake (b in EV = p*b − (1−p))."""

    if american_odds is None:
        return None
    try:
        odds = float(american_odds)
    except (TypeError, ValueError):
        return None
    if odds == 0:
        return None
    if odds > 0:
        return odds / 100.0
    return 100.0 / abs(odds)


def expected_value_american(
    model_probability: float | None,
    american_odds: float | int | None,
    *,
    p_push: float | None = 0.0,
) -> float | None:
    """
    Expected value per unit stake at American odds.

    With push probability ``p_push`` (stake refunded):
      EV = p_win * b + p_push * 0 − p_lose * 1
      p_lose = 1 − p_win − p_push
    """

    if model_probability is None or american_odds is None:
        return None
    try:
        p_win = float(model_probability)
        push = float(p_push or 0.0)
    except (TypeError, ValueError):
        return None
    if p_win < 0 or p_win > 1:
        return None
    push = max(0.0, min(1.0 - p_win, push))
    p_lose = 1.0 - p_win - push
    if p_lose < -1e-9:
        return None
    p_lose = max(0.0, p_lose)
    profit = american_profit_per_unit(american_odds)
    if profit is None:
        return None
    # Binary path still requires a non-trivial win probability.
    if p_win <= 0 and push <= 0:
        return None
    if p_win >= 1.0 and push <= 0:
        return profit
    return (p_win * profit) - p_lose


def expected_value(
    model_probability: float | None,
    american_odds: float | int | None,
) -> float | None:
    """
    Expected value as a decimal fraction of stake (no push).

    EV = model_p * profit_per_unit - (1 - model_p)

    Prefer ``expected_value_american(..., p_push=...)`` when push
    probability is available.
    """

    if model_probability is None:
        return None
    try:
        p = float(model_probability)
    except (TypeError, ValueError):
        return None
    # Preserve historical binary contract: exclusive (0, 1).
    if p <= 0.0 or p >= 1.0:
        return None
    return expected_value_american(
        model_probability,
        american_odds,
        p_push=0.0,
    )


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
