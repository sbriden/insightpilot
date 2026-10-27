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

    def test_calibration_deltas_spread_only(self):
        # Total bias is ignored until season feedback is re-fit;
        # spread_bias +0.6 → home +0.3, away -0.3.
        home_d, away_d = calibration_score_deltas(
            projected_home=25.0,
            projected_away=20.0,
            feedback={
                "active": True,
                "total_bias": -2.325,
                "spread_bias": 0.6,
            },
        )
        self.assertAlmostEqual(home_d, 0.3, places=3)
        self.assertAlmostEqual(away_d, -0.3, places=3)

    def test_cfb_additive_matchup_preserves_market_when_even(self):
        # Even matchup vs market home -11: keep the market margin.
        residual = predict_score_residuals(
            market_home=31.0,
            market_away=20.0,
            home_team_id="h",
            away_team_id="a",
            strength_context={
                "sport": "CFB",
                "league_avg_ppg": 26.0,
                "profiles": {
                    "h": {
                        "offensive_efficiency": 0.0,
                        "defensive_efficiency": 0.0,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                    "a": {
                        "offensive_efficiency": 0.0,
                        "defensive_efficiency": 0.0,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                },
            },
            policy={
                "weights_by_confidence": {
                    "Low": {"market": 0.0, "model": 1.0},
                    "Moderate": {"market": 0.0, "model": 1.0},
                    "High": {"market": 0.0, "model": 1.0},
                },
                "source": "test",
                "learned": False,
            },
        )
        home, away, _ = apply_score_residuals(residual)
        assert home is not None and away is not None
        self.assertGreater(home, away)
        self.assertAlmostEqual(home - away, 11.0, places=1)
        self.assertAlmostEqual(home + away, 51.0, places=1)

    def test_cfb_additive_matchup_can_fade_favorite(self):
        # Opposite-sign away matchup should shrink home chalk.
        residual = predict_score_residuals(
            market_home=31.0,
            market_away=20.0,
            home_team_id="h",
            away_team_id="a",
            strength_context={
                "sport": "CFB",
                "league_avg_ppg": 26.0,
                "profiles": {
                    "h": {
                        "offensive_efficiency": -0.4,
                        "defensive_efficiency": 0.4,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                    "a": {
                        "offensive_efficiency": 0.5,
                        "defensive_efficiency": -0.3,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                },
            },
            policy={
                "weights_by_confidence": {
                    "Low": {"market": 0.0, "model": 1.0},
                    "Moderate": {"market": 0.0, "model": 1.0},
                    "High": {"market": 0.0, "model": 1.0},
                },
                "source": "test",
                "learned": False,
            },
        )
        home, away, _ = apply_score_residuals(residual)
        assert home is not None and away is not None
        self.assertGreater(home, away)
        self.assertLess(home - away, 11.0)

    def test_cfb_same_sign_matchup_does_not_pile_on(self):
        # Same-sign home matchup must not widen market chalk.
        residual = predict_score_residuals(
            market_home=31.0,
            market_away=20.0,
            home_team_id="h",
            away_team_id="a",
            strength_context={
                "sport": "CFB",
                "league_avg_ppg": 26.0,
                "profiles": {
                    "h": {
                        "offensive_efficiency": 0.5,
                        "defensive_efficiency": -0.3,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                    "a": {
                        "offensive_efficiency": -0.4,
                        "defensive_efficiency": 0.4,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                },
            },
            policy={
                "weights_by_confidence": {
                    "Low": {"market": 0.0, "model": 1.0},
                    "Moderate": {"market": 0.0, "model": 1.0},
                    "High": {"market": 0.0, "model": 1.0},
                },
                "source": "test",
                "learned": False,
            },
        )
        home, away, _ = apply_score_residuals(residual)
        assert home is not None and away is not None
        self.assertAlmostEqual(home - away, 11.0, places=1)

    def test_nfl_matchup_anchor_preserves_market_when_even(self):
        residual = predict_score_residuals(
            market_home=27.0,
            market_away=20.0,
            home_team_id="h",
            away_team_id="a",
            strength_context={
                "sport": "NFL",
                "league_avg_ppg": 23.0,
                "profiles": {
                    "h": {
                        "offensive_efficiency": 0.0,
                        "defensive_efficiency": 0.0,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                    "a": {
                        "offensive_efficiency": 0.0,
                        "defensive_efficiency": 0.0,
                        "pace_z": 0.0,
                        "games": 6,
                    },
                },
            },
            policy={
                "weights_by_confidence": {
                    "Low": {"market": 0.0, "model": 1.0},
                    "Moderate": {"market": 0.0, "model": 1.0},
                    "High": {"market": 0.0, "model": 1.0},
                },
                "source": "test",
                "learned": False,
            },
        )
        home, away, _ = apply_score_residuals(residual)
        assert home is not None and away is not None
        self.assertAlmostEqual(home - away, 7.0, places=1)
        self.assertAlmostEqual(home + away, 47.0, places=1)


if __name__ == "__main__":
    unittest.main()
