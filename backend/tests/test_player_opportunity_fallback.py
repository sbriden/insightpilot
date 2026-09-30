"""Tests for opportunity score volume fallbacks."""

from __future__ import annotations

import unittest

from app.canonical.analytics.player_opportunity import (
    _qb_opportunity_score,
    _receiving_opportunity,
    _rushing_opportunity,
    _skill_opportunity_score,
)
from app.canonical.cache_control import clear_all_fantasy_caches


class OpportunityFallbackTests(unittest.TestCase):
    def test_receiving_falls_back_to_routes(self):
        score = _receiving_opportunity(
            {
                "target_share": None,
                "route_participation_rate": None,
                "air_yard_share": None,
                "routes_run": 40,
                "red_zone_targets": 2,
            }
        )
        self.assertIsNotNone(score)
        assert score is not None
        self.assertGreater(score, 50)

    def test_rushing_falls_back_to_touches(self):
        score = _rushing_opportunity(
            {
                "rush_share": None,
                "touch_share": None,
                "touches": 18,
                "goal_line_carries": 1,
                "inside_5_carries": 0,
            }
        )
        self.assertIsNotNone(score)
        assert score is not None
        self.assertGreater(score, 40)

    def test_skill_falls_back_to_snap_volume(self):
        score = _skill_opportunity_score(
            {
                "offensive_snap_share": None,
                "snap_count": 60,
                "touches": 8,
                "routes_run": 20,
            },
            receiving=None,
            rushing=None,
            red_zone=None,
        )
        self.assertIsNotNone(score)

    def test_qb_falls_back_to_dropbacks(self):
        score = _qb_opportunity_score(
            {
                "offensive_snap_share": None,
                "dropbacks": 35,
                "snap_count": 65,
                "designed_rush_attempts": 4,
                "deep_pass_attempts": None,
            },
            rushing=None,
            red_zone=None,
        )
        self.assertIsNotNone(score)

    def test_rates_still_preferred(self):
        score = _receiving_opportunity(
            {
                "target_share": 0.25,
                "route_participation_rate": 0.8,
                "air_yard_share": 0.3,
                "routes_run": 1,
            }
        )
        self.assertIsNotNone(score)
        assert score is not None
        # Rate path should dominate over tiny volume.
        self.assertGreater(score, 30)


class CacheControlTests(unittest.TestCase):
    def test_clear_all_fantasy_caches_runs(self):
        cleared = clear_all_fantasy_caches()
        self.assertGreaterEqual(cleared, 0)


if __name__ == "__main__":
    unittest.main()
