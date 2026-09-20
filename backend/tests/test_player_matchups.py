"""Matchups tab helper and smoke tests."""

from __future__ import annotations

import unittest

from app.analysis.insights.player_matchups import (
    _difficulty_from_positional,
    _difficulty_from_score,
    _normalize_view,
    build_player_matchups,
)


class PlayerMatchupsHelperTests(unittest.TestCase):
    def test_normalize_view(self):
        self.assertEqual(_normalize_view("next_4"), "next_4")
        self.assertEqual(_normalize_view("ros"), "rest_of_season")
        self.assertEqual(_normalize_view(None), "next_8")

    def test_difficulty_from_score(self):
        self.assertEqual(
            _difficulty_from_score(75),
            "very_favorable",
        )
        self.assertEqual(_difficulty_from_score(60), "favorable")
        self.assertEqual(_difficulty_from_score(50), "neutral")
        self.assertEqual(_difficulty_from_score(40), "difficult")
        self.assertEqual(
            _difficulty_from_score(20),
            "very_difficult",
        )

    def test_difficulty_from_positional(self):
        level, score = _difficulty_from_positional(
            pct_vs_avg=12.0,
            rank=5,
            rank_of=32,
        )
        self.assertEqual(level, "favorable")
        self.assertIsNotNone(score)


class PlayerMatchupsBuildTests(unittest.TestCase):
    def test_blank_player(self):
        self.assertIsNone(build_player_matchups(""))

    def test_build_smoke(self):
        try:
            payload = build_player_matchups(
                "ip_player_83482914",
                season=2026,
                view="next_8",
            )
        except Exception:
            self.skipTest("database unavailable")
        if payload is None:
            self.skipTest("player or database unavailable")
        self.assertEqual(
            payload["player_id"],
            "ip_player_83482914",
        )
        self.assertIn("upcoming_matchups", payload)
        self.assertIn("outlook_summary", payload)
        self.assertIn("signals", payload)


if __name__ == "__main__":
    unittest.main()
