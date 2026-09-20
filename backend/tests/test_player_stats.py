"""Tests for player Stats tab helpers."""

from __future__ import annotations

import unittest

from app.analysis.insights.player_stats import (
    _normalize_scoring,
    _position_group,
    _reception_points,
)


class PlayerStatsHelpersTests(unittest.TestCase):
    def test_scoring_aliases(self):
        self.assertEqual(_normalize_scoring("PPR"), "ppr")
        self.assertEqual(_normalize_scoring("half"), "half_ppr")
        self.assertEqual(_normalize_scoring("standard"), "standard")
        self.assertEqual(_reception_points("ppr"), 1.0)
        self.assertEqual(_reception_points("half_ppr"), 0.5)
        self.assertEqual(_reception_points("standard"), 0.0)

    def test_position_groups(self):
        self.assertEqual(_position_group("FB"), "RB")
        self.assertEqual(_position_group("WR"), "WR")
        self.assertEqual(_position_group("QB"), "QB")


if __name__ == "__main__":
    unittest.main()
