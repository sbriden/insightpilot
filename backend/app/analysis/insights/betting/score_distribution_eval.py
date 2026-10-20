"""
Time-ordered eval: simulation vs logistic probability engines.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.analysis.insights.betting.pricing import (
    num,
    spread_to_cover_probability,
    total_to_over_probability,
    win_probability_from_spread,
)
from app.analysis.insights.betting.score_distribution import (
    fit_score_distribution,
    simulate_game_scores,
)


def evaluate_score_distribution_vs_logistic(
    rows: list[dict[str, Any]],
    *,
    train_ratio: float = 0.7,
    n_sims: int = 2000,
) -> dict[str, Any]:
    """
    Fit distribution on earlier weeks; score both engines on holdout
    cover / over / ML Brier scores.
    """

    ordered = sorted(
        rows or [],
        key=lambda row: (
            int(row.get("week") or 0),
            str(row.get("game_id") or ""),
        ),
    )
    if len(ordered) < 20:
        return {
            "available": False,
            "n": len(ordered),
            "note": "Need at least 20 labeled games for eval.",
        }

    cut = max(1, int(len(ordered) * train_ratio))
    train = ordered[:cut]
    test = ordered[cut:] or ordered[-1:]
    model = fit_score_distribution(train)

    sim_cover: list[float] = []
    log_cover: list[float] = []
    sim_over: list[float] = []
    log_over: list[float] = []
    sim_ml: list[float] = []
    log_ml: list[float] = []

    for row in test:
        market_home = num(row.get("market_home"))
        market_away = num(row.get("market_away"))
        actual_home = num(row.get("actual_home"))
        actual_away = num(row.get("actual_away"))
        if (
            market_home is None
            or market_away is None
            or actual_home is None
            or actual_away is None
        ):
            continue

        # Use market means as "projection" baseline for eval fairness.
        mean_home = float(market_home)
        mean_away = float(market_away)
        model_spread = mean_away - mean_home  # away − home? 
        # Slate uses home-team spread convention (nflverse): 
        # market_spread ≈ -(home_implied - away) wait:
        # home favored → negative home line. home 24 away 21 →
        # home -3 → market_spread = away - home = -3. Yes.
        market_spread = float(mean_away) - float(mean_home)
        market_total = float(mean_home) + float(mean_away)
        # Prefer stored market lines when present.
        if num(row.get("market_spread")) is not None:
            market_spread = float(row["market_spread"])
        if num(row.get("market_total")) is not None:
            market_total = float(row["market_total"])
        # Model spread from means (same convention).
        model_spread = float(mean_away) - float(mean_home)
        model_total = float(mean_home) + float(mean_away)

        sim = simulate_game_scores(
            mean_home=mean_home,
            mean_away=mean_away,
            model=model,
            features=row.get("features") or row.get("dist_features"),
            market_spread=market_spread,
            market_total=market_total,
            n_sims=n_sims,
            event_id=str(row.get("game_id") or ""),
        )

        # Actual outcomes.
        actual_margin = float(actual_home) - float(actual_away)
        home_covered = 1.0 if (actual_margin + market_spread) > 0 else 0.0
        if abs(actual_margin + market_spread) < 1e-9:
            continue  # skip pushes for Brier
        went_over = 1.0 if (float(actual_home) + float(actual_away)) > market_total else 0.0
        if abs(
            float(actual_home) + float(actual_away) - market_total
        ) < 1e-9:
            continue
        home_won = 1.0 if actual_home > actual_away else 0.0
        if actual_home == actual_away:
            continue

        cover_sim = num((sim.get("cover_at_line") or {}).get("home_cover"))
        over_sim = num((sim.get("over_at_line") or {}).get("over"))
        win_sim = num(sim.get("home_win_prob"))

        cover_log = spread_to_cover_probability(model_spread, market_spread)
        over_log = total_to_over_probability(model_total, market_total)
        win_log = win_probability_from_spread(model_spread)

        if cover_sim is not None and cover_log is not None:
            sim_cover.append((float(cover_sim) - home_covered) ** 2)
            log_cover.append((float(cover_log) - home_covered) ** 2)
        if over_sim is not None and over_log is not None:
            sim_over.append((float(over_sim) - went_over) ** 2)
            log_over.append((float(over_log) - went_over) ** 2)
        if win_sim is not None and win_log is not None:
            sim_ml.append((float(win_sim) - home_won) ** 2)
            log_ml.append((float(win_log) - home_won) ** 2)

    def _brier(vals: list[float]) -> float | None:
        if not vals:
            return None
        return round(float(np.mean(vals)), 4)

    return {
        "available": True,
        "n_train": len(train),
        "n_test": len(test),
        "model_active": bool(model.get("active")),
        "model_method": model.get("method"),
        "simulation_brier": {
            "cover": _brier(sim_cover),
            "over": _brier(sim_over),
            "moneyline": _brier(sim_ml),
        },
        "logistic_brier": {
            "cover": _brier(log_cover),
            "over": _brier(log_over),
            "moneyline": _brier(log_ml),
        },
        "note": (
            "Holdout Brier (lower better) for simulation vs "
            "logistic engines on the same games."
        ),
    }
