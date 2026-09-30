"""Tests for confidence-dependent market/model projection blending."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.projection_blend import (
    apply_market_anchor_blend,
    estimate_projection_confidence,
    load_blend_policy,
    resolve_blend_weights,
)
from app.analysis.insights.betting.team_strength import (
    blend_market_and_strength,
)


class ProjectionBlendTests(unittest.TestCase):
    def test_policy_priors_match_requested_schedule(self):
        policy = load_blend_policy()
        self.assertFalse(policy["learned"])
        self.assertEqual(
            resolve_blend_weights("Low", policy=policy)["model"],
            0.15,
        )
        self.assertEqual(
            resolve_blend_weights("Moderate", policy=policy)["model"],
            0.25,
        )
        self.assertEqual(
            resolve_blend_weights("High", policy=policy)["model"],
            0.35,
        )

    def test_high_confidence_moves_farther_from_market(self):
        low_home, _, low_meta = apply_market_anchor_blend(
            market_home=24.0,
            market_away=20.0,
            model_home=30.0,
            model_away=14.0,
            confidence="Low",
        )
        high_home, _, high_meta = apply_market_anchor_blend(
            market_home=24.0,
            market_away=20.0,
            model_home=30.0,
            model_away=14.0,
            confidence="High",
        )
        assert low_home is not None and high_home is not None
        # Market 24, model 30 → deltas applied 0.15 vs 0.35 of +6.
        self.assertEqual(low_home, 24.9)
        self.assertEqual(high_home, 26.1)
        self.assertGreater(
            abs(high_meta["home_applied_delta"]),
            abs(low_meta["home_applied_delta"]),
        )

    def test_estimate_confidence_from_matchup_and_sample(self):
        low = estimate_projection_confidence(
            strength_detail={
                "available": True,
                "home_matchup": 0.2,
                "away_matchup": 0.1,
            },
            home_games=2,
            away_games=2,
        )
        high = estimate_projection_confidence(
            strength_detail={
                "available": True,
                "home_matchup": 1.5,
                "away_matchup": 1.2,
            },
            home_games=5,
            away_games=5,
        )
        self.assertEqual(low, "Low")
        self.assertEqual(high, "High")

    def test_blend_wrapper_returns_meta(self):
        home, away, meta = blend_market_and_strength(
            market_home=24.0,
            market_away=20.0,
            strength_home=30.0,
            strength_away=14.0,
            confidence="Moderate",
        )
        self.assertEqual(home, 25.5)  # 24 + 0.25*6
        self.assertEqual(away, 18.5)  # 20 + 0.25*(-6)
        self.assertEqual(meta["confidence"], "Moderate")
        self.assertEqual(meta["mode"], "market_anchor")


if __name__ == "__main__":
    unittest.main()
