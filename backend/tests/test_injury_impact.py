"""Tests for position-specific injury impact modeling."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.injury_impact import (
    InjuryQualityFactors,
    canonicalize_position,
    depth_role_multiplier,
    estimate_injury_impact,
)
from app.analysis.insights.betting.player_context import (
    INJURY_MARKET_WEIGHT,
    combined_score_adjustments,
)


class InjuryImpactTests(unittest.TestCase):
    def test_canonicalizes_line_and_secondary(self):
        self.assertEqual(canonicalize_position("LT"), "OL")
        self.assertEqual(canonicalize_position("DE"), "DL")
        self.assertEqual(canonicalize_position("MLB"), "LB")
        self.assertEqual(canonicalize_position("FS"), "S")
        self.assertEqual(canonicalize_position("HB"), "RB")

    def test_qb_out_dwarfs_rotational_lb(self):
        qb = estimate_injury_impact(
            position="QB",
            status="out",
            depth_order=1,
            is_starter=True,
        )
        lb = estimate_injury_impact(
            position="LB",
            status="out",
            depth_order=2,
            is_starter=False,
        )
        self.assertLess(qb["own_score_delta"], -4.0)
        self.assertEqual(qb["side"], "offense")
        self.assertEqual(lb["side"], "defense")
        self.assertGreater(lb["opponent_score_delta"], 0.0)
        self.assertGreater(
            abs(qb["raw_magnitude"]),
            abs(lb["raw_magnitude"]) * 3,
        )

    def test_rotational_lb_much_smaller_than_starter_cb(self):
        starter_cb = estimate_injury_impact(
            position="CB",
            status="out",
            depth_order=1,
            is_starter=True,
        )
        rotational_lb = estimate_injury_impact(
            position="LB",
            status="out",
            depth_order=2,
            is_starter=False,
        )
        self.assertGreater(
            starter_cb["raw_magnitude"],
            rotational_lb["raw_magnitude"],
        )

    def test_backup_qb_out_while_starter_healthy_is_tiny(self):
        backup = estimate_injury_impact(
            position="QB",
            status="out",
            depth_order=2,
            is_starter=False,
        )
        self.assertLess(backup["raw_magnitude"], 0.6)

    def test_defense_injury_raises_opponent_score(self):
        dl = estimate_injury_impact(
            position="DL",
            status="out",
            depth_order=1,
            is_starter=True,
        )
        self.assertEqual(dl["own_score_delta"], 0.0)
        self.assertGreater(dl["opponent_score_delta"], 0.5)

    def test_quality_factors_scale_impact(self):
        elite = estimate_injury_impact(
            position="WR",
            status="out",
            depth_order=1,
            is_starter=True,
            factors=InjuryQualityFactors(
                starter_quality=1.25,
                replacement_quality=0.7,
                team_dependency=1.15,
            ),
        )
        ordinary = estimate_injury_impact(
            position="WR",
            status="out",
            depth_order=1,
            is_starter=True,
        )
        self.assertGreater(
            abs(elite["own_score_delta"]),
            abs(ordinary["own_score_delta"]),
        )

    def test_combined_score_adjustments_cross_apply_defense(self):
        home = {
            "adjustment_pts": -2.0,  # offense hit
            "opponent_adjustment_pts": 0.8,  # our D out → they score more
        }
        away = {
            "adjustment_pts": -0.5,
            "opponent_adjustment_pts": 0.0,
        }
        home_adj, away_adj = combined_score_adjustments(
            home_injury=home,
            away_injury=away,
        )
        self.assertEqual(home_adj, -2.0)
        self.assertEqual(away_adj, 0.3)  # -0.5 + 0.8

    def test_role_multiplier_starter_vs_rotation(self):
        self.assertEqual(
            depth_role_multiplier(
                position="LB", depth_order=1, is_starter=True
            ),
            1.0,
        )
        self.assertLess(
            depth_role_multiplier(
                position="LB", depth_order=2, is_starter=False
            ),
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
