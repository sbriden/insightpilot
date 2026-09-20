"""Tests for team-defense fantasy scoring."""

from __future__ import annotations

import unittest

from app.analysis.insights.fantasy_scoring import (
    dst_game_fantasy_points,
    dst_points_allowed_points,
)


class DstScoringTests(unittest.TestCase):
    def test_points_allowed_brackets(self):
        self.assertEqual(dst_points_allowed_points(0), 10.0)
        self.assertEqual(dst_points_allowed_points(6), 7.0)
        self.assertEqual(dst_points_allowed_points(13), 4.0)
        self.assertEqual(dst_points_allowed_points(20), 1.0)
        self.assertEqual(dst_points_allowed_points(27), 0.0)
        self.assertEqual(dst_points_allowed_points(34), -1.0)
        self.assertEqual(dst_points_allowed_points(35), -4.0)

    def test_full_game_score(self):
        points = dst_game_fantasy_points(
            {
                "points_allowed": 10,
                "sacks": 3,
                "interceptions": 1,
                "fumbles_recovered": 1,
                "safeties": 0,
                "defensive_tds": 1,
                "special_teams_tds": 0,
                "def_fg_blocks": 1,
            }
        )
        # 4 (PA) + 3 (sacks) + 2 (INT) + 2 (FR) + 6 (TD) + 2 (block) = 19
        self.assertEqual(points, 19.0)

    def test_recovery_and_return_tds(self):
        points = dst_game_fantasy_points(
            {
                "points_allowed": 14,
                "sacks": 0,
                "fumble_recovery_tds": 1,
                "pt_return_tds": 1,
                "def_2pt_made": 1,
            }
        )
        # 1 (PA) + 6 + 6 + 2 = 15
        self.assertEqual(points, 15.0)


if __name__ == "__main__":
    unittest.main()
