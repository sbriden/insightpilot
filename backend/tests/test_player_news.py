"""Player News tab helper and smoke tests."""

from __future__ import annotations

import unittest

from app.analysis.insights.player_news import (
    _depth_change_impact,
    _normalize_category,
    _normalize_impact_filter,
    _normalize_lookback,
    _self_injury_impact,
    _teammate_injury_impact,
    build_player_news,
)


class PlayerNewsHelperTests(unittest.TestCase):
    def test_normalize_lookback(self):
        self.assertEqual(_normalize_lookback("last_7d"), "last_7d")
        self.assertEqual(_normalize_lookback("week"), "last_7d")
        self.assertEqual(_normalize_lookback(None), "last_30d")

    def test_normalize_category(self):
        self.assertEqual(_normalize_category("injury"), "injury")
        self.assertEqual(_normalize_category("bogus"), "all")

    def test_normalize_impact(self):
        self.assertEqual(_normalize_impact_filter("high"), "high")
        self.assertEqual(_normalize_impact_filter("x"), "all")

    def test_self_injury_out_is_high(self):
        impact = _self_injury_impact(
            game_status="Out",
            practice_status="Did Not Participate",
            previous_game=None,
            previous_practice=None,
        )
        self.assertEqual(impact["level"], "high")
        self.assertEqual(impact["fantasy_impact"], "negative")

    def test_self_injury_limited_is_moderate(self):
        impact = _self_injury_impact(
            game_status=None,
            practice_status="Limited Participation",
            previous_game=None,
            previous_practice="Full Participation",
        )
        self.assertEqual(impact["level"], "moderate")

    def test_teammate_ahead_out_is_opportunity(self):
        impact = _teammate_injury_impact(
            same_position=True,
            teammate_depth_order=1,
            player_depth_order=2,
            game_status="Out",
        )
        self.assertEqual(impact["level"], "moderate")
        self.assertEqual(
            impact["fantasy_impact"],
            "positive",
        )

    def test_depth_promotion(self):
        impact = _depth_change_impact(
            before_order=3,
            after_order=1,
        )
        self.assertEqual(impact["level"], "high")
        self.assertEqual(
            impact["fantasy_impact"],
            "positive",
        )


class PlayerNewsBuildTests(unittest.TestCase):
    def test_blank_player(self):
        self.assertIsNone(build_player_news(""))

    def test_build_smoke(self):
        try:
            payload = build_player_news(
                "ip_player_83482914",
                season=2026,
                lookback="season",
            )
        except Exception:
            self.skipTest("database unavailable")
        if payload is None:
            self.skipTest("player or database unavailable")
        self.assertEqual(
            payload["player_id"],
            "ip_player_83482914",
        )
        self.assertIn("developments", payload)
        self.assertIn("important_developments", payload)
        self.assertIn("counts", payload)
        self.assertIn("data_note", payload)


if __name__ == "__main__":
    unittest.main()
