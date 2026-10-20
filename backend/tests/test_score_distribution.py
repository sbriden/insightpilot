"""Tests for bivariate score-distribution probability engine."""

from __future__ import annotations

import unittest

import numpy as np

from app.analysis.insights.betting.pricing import (
    cover_probability_from_engine,
    over_probability_from_engine,
    spread_to_cover_probability,
    win_probability_from_engine,
    win_probability_from_spread,
)
from app.analysis.insights.betting.score_distribution import (
    MIN_FIT_SAMPLES,
    estimate_game_covariance,
    fit_score_distribution,
    prior_score_distribution_model,
    simulate_game_scores,
)
from app.analysis.insights.betting.score_distribution_eval import (
    evaluate_score_distribution_vs_logistic,
)


def _residual_rows(n: int, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for i in range(n):
        # Correlated residuals ~ ρ=0.3
        z1 = rng.normal()
        z2 = 0.3 * z1 + math_sqrt(1 - 0.09) * rng.normal()
        rh = 13.0 * z1
        ra = 13.0 * z2
        market_home = 24.0
        market_away = 21.0
        rows.append(
            {
                "week": (i % 14) + 1,
                "game_id": f"g{i}",
                "resid_home": rh,
                "resid_away": ra,
                "market_home": market_home,
                "market_away": market_away,
                "actual_home": market_home + rh,
                "actual_away": market_away + ra,
                "market_spread": market_away - market_home,
                "market_total": market_home + market_away,
                "features": {
                    "early_season": 1.0 if i % 10 == 0 else 0.0,
                    "thin_sample": 1.0 if i % 8 == 0 else 0.0,
                    "pace_abs": float(rng.uniform(0, 1)),
                    "turnover_env": float(rng.uniform(0, 1)),
                    "disagreement": float(rng.uniform(0, 1)),
                    "min_games": float(rng.integers(2, 12)),
                },
            }
        )
    return rows


def math_sqrt(x: float) -> float:
    return float(np.sqrt(x))


class ScoreDistributionTests(unittest.TestCase):
    def test_prior_inactive_below_min_samples(self):
        model = fit_score_distribution(_residual_rows(MIN_FIT_SAMPLES - 10))
        self.assertFalse(model["active"])
        self.assertEqual(model["method"], "prior")

    def test_fit_active_with_enough_samples(self):
        model = fit_score_distribution(_residual_rows(MIN_FIT_SAMPLES + 20))
        self.assertTrue(model["active"])
        self.assertEqual(model["method"], "empirical_bivariate")
        self.assertGreater(model["sigma_home"], 8.0)
        self.assertGreater(model["rho"], 0.05)

    def test_positive_rho_widens_total_narrows_margin(self):
        model = {
            **prior_score_distribution_model(),
            "sigma_home": 13.0,
            "sigma_away": 13.0,
            "rho": 0.0,
            "scale_weights": {},
        }
        indep = estimate_game_covariance(model=model, features={})
        model_dep = {**model, "rho": 0.4}
        dep = estimate_game_covariance(model=model_dep, features={})
        # Analytic: σ_total² = σh²+σa²+2ρσhσa
        sigma_total_indep = (
            indep["sigma_home"] ** 2
            + indep["sigma_away"] ** 2
        ) ** 0.5
        sigma_total_dep = (
            dep["sigma_home"] ** 2
            + dep["sigma_away"] ** 2
            + 2 * dep["rho"] * dep["sigma_home"] * dep["sigma_away"]
        ) ** 0.5
        self.assertGreater(sigma_total_dep, sigma_total_indep)

        # Margin SD shrinks with positive ρ.
        sigma_margin_indep = (
            indep["sigma_home"] ** 2 + indep["sigma_away"] ** 2
        ) ** 0.5
        sigma_margin_dep = (
            dep["sigma_home"] ** 2
            + dep["sigma_away"] ** 2
            - 2 * dep["rho"] * dep["sigma_home"] * dep["sigma_away"]
        ) ** 0.5
        self.assertLess(sigma_margin_dep, sigma_margin_indep)

    def test_cover_near_half_when_mean_matches_line(self):
        # mean margin = home - away = 3; line = -3 → adj = 0 center
        sim = simulate_game_scores(
            mean_home=24.0,
            mean_away=21.0,
            model=prior_score_distribution_model(),
            market_spread=-3.0,
            market_total=45.0,
            n_sims=8000,
            seed=123,
        )
        cover = sim["cover_at_line"]["home_cover"]
        self.assertAlmostEqual(cover, 0.5, delta=0.05)

    def test_cover_moves_with_mean_shift(self):
        base = simulate_game_scores(
            mean_home=24.0,
            mean_away=21.0,
            model=prior_score_distribution_model(),
            market_spread=-3.0,
            n_sims=6000,
            seed=7,
        )
        shifted = simulate_game_scores(
            mean_home=27.0,
            mean_away=21.0,
            model=prior_score_distribution_model(),
            market_spread=-3.0,
            n_sims=6000,
            seed=7,
        )
        self.assertGreater(
            shifted["cover_at_line"]["home_cover"],
            base["cover_at_line"]["home_cover"],
        )

    def test_high_sigma_pulls_cover_toward_half(self):
        tight = {
            **prior_score_distribution_model(),
            "sigma_home": 6.0,
            "sigma_away": 6.0,
            "rho": 0.2,
            "scale_weights": {},
        }
        wide = {
            **prior_score_distribution_model(),
            "sigma_home": 22.0,
            "sigma_away": 22.0,
            "rho": 0.2,
            "scale_weights": {},
        }
        # Strong favorite mean vs line.
        p_tight = simulate_game_scores(
            mean_home=30.0,
            mean_away=17.0,
            model=tight,
            market_spread=-3.0,
            n_sims=6000,
            seed=99,
        )["cover_at_line"]["home_cover"]
        p_wide = simulate_game_scores(
            mean_home=30.0,
            mean_away=17.0,
            model=wide,
            market_spread=-3.0,
            n_sims=6000,
            seed=99,
        )["cover_at_line"]["home_cover"]
        self.assertGreater(abs(p_tight - 0.5), abs(p_wide - 0.5))

    def test_pricing_falls_back_to_logistic(self):
        logistic = spread_to_cover_probability(-3.0, -6.0)
        via_engine = cover_probability_from_engine(
            engine="simulation",
            model_spread=-3.0,
            market_spread=-6.0,
            simulation=None,
        )
        self.assertEqual(logistic, via_engine)

        over_log = over_probability_from_engine(
            engine="logistic",
            model_total=48.0,
            market_total=45.0,
        )
        self.assertIsNotNone(over_log)

        win_log = win_probability_from_spread(-7.0)
        win_eng = win_probability_from_engine(
            engine="logistic",
            model_spread=-7.0,
        )
        self.assertEqual(win_log, win_eng)

    def test_pricing_uses_simulation_when_available(self):
        sim = simulate_game_scores(
            mean_home=28.0,
            mean_away=20.0,
            model=prior_score_distribution_model(),
            market_spread=-3.0,
            market_total=45.0,
            n_sims=4000,
            seed=3,
        )
        cover = cover_probability_from_engine(
            engine="simulation",
            model_spread=-8.0,
            market_spread=-3.0,
            simulation=sim,
        )
        self.assertAlmostEqual(
            cover,
            sim["cover_at_line"]["home_cover"],
            places=4,
        )

    def test_eval_helper_on_synthetic(self):
        rows = _residual_rows(100, seed=11)
        report = evaluate_score_distribution_vs_logistic(
            rows,
            train_ratio=0.7,
            n_sims=1500,
        )
        self.assertTrue(report["available"])
        self.assertIsNotNone(report["simulation_brier"]["cover"])
        self.assertIsNotNone(report["logistic_brier"]["cover"])


if __name__ == "__main__":
    unittest.main()
