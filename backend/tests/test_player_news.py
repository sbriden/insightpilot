"""Player News tab helper and smoke tests."""

from __future__ import annotations

import unittest

from app.analysis.insights.injury_relevance import (
    evaluate_injury_relevance,
)
from app.analysis.insights.player_news import (
    _depth_change_impact,
    _developments_for_week,
    _normalize_category,
    _normalize_impact_filter,
    _normalize_lookback,
    _self_injury_impact,
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

    def test_wr2_rises_when_wr1_is_out(self):
        impact = evaluate_injury_relevance(
            viewer_position="WR",
            viewer_depth=2,
            injured_position="WR",
            injured_depth=1,
            game_status="Out",
            same_team=True,
            injured_target_share=0.28,
            viewer_target_share=0.22,
            remaining_target_share=0.72,
        )
        self.assertIsNotNone(impact)
        assert impact is not None
        self.assertEqual(impact["level"], "high")
        self.assertEqual(impact["fantasy_impact"], "positive")
        self.assertIn("9 points", impact["summary"])
        self.assertIn("28%", impact["summary"])

    def test_safety_teammate_is_not_relevant_to_wr(self):
        impact = evaluate_injury_relevance(
            viewer_position="WR",
            viewer_depth=1,
            injured_position="SS",
            injured_depth=1,
            game_status="Out",
            same_team=True,
        )
        self.assertIsNone(impact)

    def test_wr1_out_lowers_qb_efficiency_without_flat_drop(self):
        impact = evaluate_injury_relevance(
            viewer_position="QB",
            viewer_depth=1,
            injured_position="WR",
            injured_depth=1,
            game_status="Out",
            same_team=True,
            injured_air_yard_share=0.34,
        )
        self.assertIsNotNone(impact)
        assert impact is not None
        self.assertEqual(impact["fantasy_impact"], "negative")
        self.assertIn("catch rate", impact["summary"])
        self.assertIn("air yards", impact["summary"])

    def test_rb2_rises_when_rb1_is_out(self):
        impact = evaluate_injury_relevance(
            viewer_position="RB",
            viewer_depth=2,
            injured_position="RB",
            injured_depth=1,
            game_status="Out",
            same_team=True,
        )
        self.assertIsNotNone(impact)
        assert impact is not None
        self.assertEqual(impact["level"], "high")
        self.assertEqual(impact["fantasy_impact"], "positive")

    def test_ol_starter_out_hits_qb_and_rb_only(self):
        qb = evaluate_injury_relevance(
            viewer_position="QB",
            viewer_depth=1,
            injured_position="LT",
            injured_depth=1,
            game_status="Out",
            same_team=True,
        )
        rb = evaluate_injury_relevance(
            viewer_position="RB",
            viewer_depth=1,
            injured_position="LT",
            injured_depth=1,
            game_status="Out",
            same_team=True,
        )
        wr = evaluate_injury_relevance(
            viewer_position="WR",
            viewer_depth=1,
            injured_position="LT",
            injured_depth=1,
            game_status="Out",
            same_team=True,
        )
        self.assertEqual(qb["fantasy_impact"], "negative")
        self.assertEqual(rb["fantasy_impact"], "negative")
        self.assertIsNone(wr)

    def test_top_corner_out_lifts_primary_wr(self):
        primary = evaluate_injury_relevance(
            viewer_position="WR",
            viewer_depth=1,
            injured_position="CB",
            injured_depth=1,
            game_status="Out",
            same_team=False,
        )
        wr3 = evaluate_injury_relevance(
            viewer_position="WR",
            viewer_depth=3,
            injured_position="CB",
            injured_depth=1,
            game_status="Out",
            same_team=False,
        )
        self.assertEqual(primary["fantasy_impact"], "positive")
        self.assertIn("covers", primary["summary"])
        self.assertIsNone(wr3)

    def test_featured_window_keeps_only_the_requested_week(self):
        developments = [
            {"week": 2, "headline": "Older"},
            {"week": 4, "headline": "Current"},
            {"week": None, "headline": "Undated"},
        ]
        current = _developments_for_week(developments, 4)
        self.assertEqual(
            [item["headline"] for item in current],
            ["Current"],
        )
        self.assertEqual(_developments_for_week(developments, None), [])

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
