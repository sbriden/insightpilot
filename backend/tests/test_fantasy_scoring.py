"""Fantasy scoring helper tests."""

from __future__ import annotations

import unittest

from app.analysis.insights.fantasy_scoring import (
    fantasy_points_from_row,
    fantasy_points_sql,
    normalize_scoring,
)


class FantasyScoringTests(unittest.TestCase):
    def test_normalize_scoring_aliases(self):
        self.assertEqual(normalize_scoring("PPR"), "ppr")
        self.assertEqual(normalize_scoring("half"), "half_ppr")
        self.assertEqual(normalize_scoring("half-ppr"), "half_ppr")
        self.assertEqual(normalize_scoring("standard"), "standard")
        self.assertEqual(normalize_scoring("non_ppr"), "standard")

    def test_reception_scoring_formats(self):
        row = {
            "receptions": 5,
            "receiving_yards": 50,
            "receiving_tds": 0,
        }
        self.assertEqual(
            fantasy_points_from_row(row, scoring="ppr"),
            10.0,
        )
        self.assertEqual(
            fantasy_points_from_row(row, scoring="half_ppr"),
            7.5,
        )
        self.assertEqual(
            fantasy_points_from_row(row, scoring="standard"),
            5.0,
        )

    def test_skill_ppr(self):
        points = fantasy_points_from_row(
            {
                "pass_yards": 250,
                "pass_tds": 2,
                "interceptions": 1,
                "rush_yards": 20,
                "rush_tds": 0,
                "receptions": 0,
                "receiving_yards": 0,
                "receiving_tds": 0,
            },
            scoring="ppr",
        )
        # 10 + 8 - 2 + 2 = 18
        self.assertEqual(points, 18.0)

    def test_kicker_distance(self):
        points = fantasy_points_from_row(
            {
                "fg_made_20_29": 1,
                "fg_made_30_39": 1,
                "fg_made_40_49": 1,
                "fg_made_50_59": 1,
                "pat_made": 3,
            },
            scoring="ppr",
        )
        # 3+3+4+5+3 = 18
        self.assertEqual(points, 18.0)

    def test_sql_includes_kicking(self):
        sql = fantasy_points_sql("ppr", alias="g")
        self.assertIn("fg_made_40_49", sql)
        self.assertIn("pat_made", sql)


if __name__ == "__main__":
    unittest.main()
