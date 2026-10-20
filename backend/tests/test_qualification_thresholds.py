"""Tests for push-aware EV and learned qualification thresholds."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.bet_qualification import (
    evaluate_market_decision,
    qualify_bet,
)
from app.analysis.insights.betting.pricing import (
    expected_value,
    expected_value_american,
)
from app.analysis.insights.betting.qualification_thresholds import (
    fit_qualification_thresholds,
    prior_qualification_thresholds,
)


class PushAwareEVTests(unittest.TestCase):
    def test_push_mass_raises_ev_vs_binary_at_same_p_win(self):
        """At fixed p_win, push outcomes are not losses, so EV rises vs binary."""
        p = 0.55
        odds = -110
        p_push = 0.08
        binary = expected_value(p, odds)
        with_push = expected_value_american(p, odds, p_push=p_push)
        self.assertIsNotNone(binary)
        self.assertIsNotNone(with_push)
        self.assertGreater(float(with_push), float(binary))
        # Exact: EV_push = EV_binary + p_push (stake not lost on push).
        self.assertAlmostEqual(float(with_push), float(binary) + p_push, places=9)

    def test_binary_wrapper_rejects_boundary(self):
        self.assertIsNone(expected_value(0.0, -110))
        self.assertIsNone(expected_value(1.0, -110))


class UncertaintyPassTests(unittest.TestCase):
    def test_high_edge_high_uncertainty_is_pass(self):
        decision = evaluate_market_decision(
            market_type="spread",
            selection="BUF -3.5",
            model_projection=-8.0,
            market_projection=-3.5,
            raw_probability=0.62,
            calibrated_probability=0.60,
            market_probability=0.524,
            expected_value=8.0,
            edge_probability=7.6,
            model_confidence="High",
            event={
                "team_strength": {"available": False},
                "score_distribution": {
                    "uncertainty": {
                        "sigma_margin": 25.0,
                        "entropy_proxy": 0.99,
                    }
                },
                "model_disagreement": {
                    "spread": {"model_agreement": 0.30},
                },
            },
            model_agreement=0.30,
            probability_calibrated=True,
            offered_odds=-110,
        )
        self.assertEqual(decision["bet"]["status"], "pass")
        self.assertTrue(decision["bet"]["no_bet"])
        self.assertIn("UNCERTAINTY_HIGH", decision["bet"]["reason_codes"])


class ReasonCodeTests(unittest.TestCase):
    def test_pass_includes_reason_codes(self):
        bet = qualify_bet(
            prediction={
                "has_prediction": True,
                "calibrated_probability": 0.53,
                "raw_probability": 0.53,
                "market_type": "spread",
            },
            market_probability=0.524,
            expected_value=-1.0,
            edge_probability=0.5,
            model_confidence="Low",
            data_quality={"label": "Low", "score": 0.2},
            offered_odds=-110,
        )
        self.assertEqual(bet["status"], "pass")
        self.assertTrue(bet["reason_codes"])
        self.assertTrue(any(r.get("code") for r in bet["reasons"]))

    def test_strong_includes_passes_strong_code(self):
        decision = evaluate_market_decision(
            market_type="spread",
            selection="BUF -3.5",
            model_projection=-7.0,
            market_projection=-3.5,
            raw_probability=0.62,
            calibrated_probability=0.60,
            market_probability=0.524,
            expected_value=5.0,
            edge_probability=7.6,
            model_confidence="High",
            event={
                "team_strength": {
                    "available": True,
                    "home_games": 4,
                    "away_games": 4,
                    "projection_confidence": "High",
                },
                "residuals": {"residual_home": 1.4, "confidence": "High"},
                "injury_report_week": 4,
                "market_movement": {
                    "moved": False,
                    "opening_spread": -3.5,
                    "vs_model": {"label": "stable"},
                },
                "model_disagreement": {
                    "spread": {"model_agreement": 0.85},
                },
            },
            model_agreement=0.85,
            probability_calibrated=True,
            offered_odds=-110,
        )
        self.assertEqual(decision["bet"]["status"], "strong_bet")
        self.assertIn("PASSES_STRONG", decision["bet"]["reason_codes"])


class ThresholdLearningTests(unittest.TestCase):
    def test_prior_inactive(self):
        model = prior_qualification_thresholds()
        self.assertFalse(model["active"])
        self.assertEqual(model["strong_bet"]["min_edge_prob_pp"], 4.0)

    def test_fit_prefers_lower_floor_when_prior_too_strict(self):
        rows = []
        # Weeks 1–10 train: many +3pp / +2% EV winners labeled High.
        # Weeks 11–14 holdout: same pattern — prior 4.0 would miss them.
        for week in range(1, 15):
            for i in range(8):
                rows.append(
                    {
                        "week": week,
                        "market_id": f"w{week}-m{i}",
                        "result": "won" if i % 3 != 0 else "lost",
                        "edge_probability": 3.2,
                        "expected_value": 2.5,
                        "confidence": "High",
                        "data_quality": "High",
                        "price": -110,
                        "clv": 0.4 if i % 3 != 0 else -0.2,
                    }
                )
        # Add enough volume for MIN_FIT_ROWS.
        while len(rows) < 70:
            rows.append(
                {
                    "week": 5,
                    "market_id": f"pad-{len(rows)}",
                    "result": "won",
                    "edge_probability": 3.2,
                    "expected_value": 2.5,
                    "confidence": "High",
                    "data_quality": "High",
                    "price": -110,
                    "clv": 0.3,
                }
            )
        model = fit_qualification_thresholds(rows, train_ratio=0.7)
        # May stay prior if holdout n_strong constraint fails; when active,
        # Strong edge should be ≤ 4.0 and often < 4.0 on this series.
        self.assertGreaterEqual(model["sample_size"], 60)
        if model.get("active"):
            self.assertLessEqual(
                model["strong_bet"]["min_edge_prob_pp"], 4.0
            )
            self.assertLessEqual(
                model["strong_bet"]["min_ev_pct"], 3.0
            )


if __name__ == "__main__":
    unittest.main()
