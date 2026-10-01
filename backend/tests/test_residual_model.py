"""Tests for market + residual projection architecture."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.residual_model import (
    add_situational_residuals,
    apply_score_residuals,
    calibration_score_deltas,
    predict_score_residuals,
)


class ResidualModelTests(unittest.TestCase):
    def test_predict_and_apply_matches_user_example_shape(self):
        # market 24.5 / 21.5; strength implies residuals before shrink.
        # With Moderate shrink 0.25: raw +5.6 / -2.8 → +1.4 / -0.7.
        residual = predict_score_residuals(
            market_home=24.5,
            market_away=21.5,
            home_team_id="home",
            away_team_id="away",
            recent_ppg={"home": 30.1, "away": 18.7},
            policy={
                "weights_by_confidence": {
                    "Low": {"market": 0.75, "model": 0.25},
                },
                "source": "test",
                "learned": False,
            },
        )
        # PPG fallback has no matchup/games → Low confidence.
        self.assertEqual(residual["projection_confidence"], "Low")
        self.assertAlmostEqual(residual["raw_residual_home"], 5.6, places=1)
        self.assertAlmostEqual(residual["raw_residual_away"], -2.8, places=1)
        self.assertAlmostEqual(residual["residual_home"], 1.4, places=1)
        self.assertAlmostEqual(residual["residual_away"], -0.7, places=1)

        home, away, meta = apply_score_residuals(residual)
        self.assertEqual(home, 25.9)
        self.assertEqual(away, 20.8)
        self.assertEqual(meta["mode"], "market_plus_residual")
        self.assertEqual(meta["architecture"], "market + residual")

    def test_situational_residuals_add_on_top(self):
        residual = predict_score_residuals(
            market_home=24.0,
            market_away=20.0,
            home_team_id="h",
            away_team_id="a",
            recent_ppg={"h": 28.0, "a": 16.0},
            policy={
                "weights_by_confidence": {
                    "Low": {"market": 0.85, "model": 0.15},
                },
                "source": "test",
                "learned": False,
            },
        )
        # raw +4 / -4 → shrink 0.15 → +0.6 / -0.6
        residual = add_situational_residuals(
            residual,
            home_adjustment=-1.0,
            away_adjustment=0.5,
        )
        home, away, meta = apply_score_residuals(residual)
        self.assertEqual(home, 23.6)  # 24 + 0.6 - 1.0
        self.assertEqual(away, 19.9)  # 20 - 0.6 + 0.5
        self.assertAlmostEqual(meta["total_residual_home"], -0.4, places=1)
        self.assertAlmostEqual(meta["total_residual_away"], -0.1, places=1)

    def test_market_only_when_no_strength(self):
        residual = predict_score_residuals(
            market_home=24.0,
            market_away=20.0,
        )
        home, away, meta = apply_score_residuals(residual)
        self.assertEqual(home, 24.0)
        self.assertEqual(away, 20.0)
        self.assertEqual(meta["mode"], "market_only")

    def test_calibration_deltas_match_bias_transform(self):
        # total_bias +2 → each side -1; spread_bias +2 → home +1, away -1
        home_d, away_d = calibration_score_deltas(
            projected_home=25.0,
            projected_away=20.0,
            feedback={
                "active": True,
                "total_bias": 2.0,
                "spread_bias": 2.0,
            },
        )
        self.assertEqual(home_d, 0.0)  # -1 + 1
        self.assertEqual(away_d, -2.0)  # -1 - 1


if __name__ == "__main__":
    unittest.main()
