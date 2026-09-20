"""Position-aware production / opportunity field selection."""

from __future__ import annotations

import unittest

from app.analysis.insights.player_performance import (
    _game_opportunity,
    _game_production,
    opportunity_fields_for_position,
    production_fields_for_position,
)


class PlayerPerformanceTests(unittest.TestCase):

    def test_rb_production_fields(self):
        keys = [
            field["key"]
            for field in production_fields_for_position("RB")
        ]
        self.assertEqual(
            keys,
            [
                "fantasy_points",
                "rush_attempts",
                "rush_yards",
                "targets",
                "receptions",
                "receiving_yards",
                "total_tds",
            ],
        )

    def test_wr_includes_air_yards(self):
        keys = [
            field["key"]
            for field in production_fields_for_position("WR")
        ]
        self.assertIn("air_yards", keys)

    def test_qb_opportunity_fields(self):
        keys = [
            field["key"]
            for field in opportunity_fields_for_position("QB")
        ]
        self.assertIn("dropbacks", keys)
        self.assertIn("qb_rush_share", keys)
        self.assertIn("red_zone_opportunities", keys)
        self.assertIn("goal_line_opportunities", keys)

    def test_ppr_points_in_production(self):
        production = _game_production(
            {
                "rush_yards": 80,
                "rush_tds": 1,
                "receptions": 2,
                "receiving_yards": 20,
                "receiving_tds": 0,
            }
        )
        # 80/10 + 6 + 2 + 20/10 = 8 + 6 + 2 + 2 = 18
        self.assertEqual(production["fantasy_points"], 18)

    def test_route_participation_dropped_when_same_as_snap(self):
        opportunity = _game_opportunity(
            {
                "offensive_snap_share": 0.92,
                "route_participation_rate": 0.92,
                "target_share": 0.25,
            }
        )
        self.assertEqual(opportunity["snap_pct"], 92.0)
        self.assertIsNone(opportunity["route_participation"])
        self.assertEqual(opportunity["target_share"], 25.0)

    def test_route_participation_kept_when_distinct(self):
        opportunity = _game_opportunity(
            {
                "offensive_snap_share": 0.92,
                "route_participation_rate": 0.71,
                "target_share": 0.25,
            }
        )
        self.assertEqual(opportunity["snap_pct"], 92.0)
        self.assertEqual(opportunity["route_participation"], 71.0)


if __name__ == "__main__":
    unittest.main()
