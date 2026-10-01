"""Tests for multi-model disagreement / ensemble diagnostics."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.model_disagreement import (
    agreement_edge_factor,
    agreement_from_stddev,
    build_model_disagreement,
    summarize_estimates,
)
from app.analysis.insights.betting.pricing import confidence_from_edge


class ModelDisagreementTests(unittest.TestCase):
    def test_tight_cluster_high_agreement(self):
        estimates = {
            "market": -3.5,
            "efficiency": -5.1,
            "recent_form": -4.7,
            "matchup": -5.3,
            "injury": -4.9,
        }
        out = summarize_estimates(estimates, scale=1.5)
        self.assertAlmostEqual(out["projection_mean"], -4.7, places=1)
        self.assertLess(out["projection_stddev"], 1.0)
        self.assertGreaterEqual(out["model_agreement"], 0.55)
        self.assertEqual(out["n_models"], 5)

    def test_wide_disagreement_low_agreement(self):
        estimates = {
            "market": -3.5,
            "efficiency": -7.2,
            "recent_form": -2.1,
            "matchup": -6.8,
        }
        out = summarize_estimates(estimates, scale=1.5)
        self.assertGreater(out["projection_stddev"], 1.5)
        self.assertLess(out["model_agreement"], 0.55)
        self.assertEqual(out["label"], "low")

    def test_agreement_formula(self):
        self.assertEqual(agreement_from_stddev(0.0, scale=1.5), 1.0)
        self.assertEqual(agreement_from_stddev(1.5, scale=1.5), 0.5)

    def test_build_includes_market_and_injury(self):
        ensemble = build_model_disagreement(
            market_home=24.0,
            market_away=20.5,
            market_spread=-3.5,
            market_total=44.5,
            home_injury_adj=-1.5,
            away_injury_adj=0.0,
        )
        spread = ensemble["spread"]
        self.assertIn("market", spread["estimates"])
        self.assertIn("injury", spread["estimates"])
        self.assertEqual(spread["estimates"]["market"], -3.5)
        # Home injury of -1.5 pts ⇒ spread moves +1.5 (away - home).
        self.assertEqual(spread["estimates"]["injury"], -2.0)
        self.assertIsNotNone(spread["projection_mean"])
        self.assertIsNotNone(spread["model_agreement"])

    def test_disagreement_damps_confidence(self):
        # Same 4-point edge: high agreement → High, low agreement → not High.
        high = confidence_from_edge(
            edge_points=4.0,
            model_agreement=0.9,
        )
        low = confidence_from_edge(
            edge_points=4.0,
            model_agreement=0.4,
        )
        self.assertEqual(high, "High")
        self.assertIn(low, {"Moderate", "Low"})
        self.assertEqual(agreement_edge_factor(0.9), 0.9)
        self.assertEqual(agreement_edge_factor(0.2), 0.4)


if __name__ == "__main__":
    unittest.main()
