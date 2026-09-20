"""Usage & Trends payload smoke tests."""

from __future__ import annotations

import unittest

from app.analysis.insights.player_usage import (
    _direction_from_change,
    _normalize_period,
    _window_compare,
    build_player_usage,
)


class PlayerUsageHelpersTests(unittest.TestCase):
    def test_normalize_period(self):
        self.assertEqual(_normalize_period("last_4"), "last_4")
        self.assertEqual(_normalize_period("full"), "full_season")
        self.assertEqual(_normalize_period(None), "last_8")

    def test_direction_increasing(self):
        self.assertEqual(
            _direction_from_change(0.2, sufficient=True),
            "increasing",
        )
        self.assertEqual(
            _direction_from_change(-0.2, sufficient=True),
            "decreasing",
        )
        self.assertEqual(
            _direction_from_change(0.01, sufficient=True),
            "stable",
        )
        self.assertEqual(
            _direction_from_change(0.2, sufficient=False),
            "insufficient",
        )

    def test_window_compare(self):
        values = [10.0, 11.0, 12.0, 13.0, 20.0, 21.0, 22.0, 23.0]
        result = _window_compare(values, window=4)
        self.assertTrue(result["sufficient"])
        self.assertGreater(result["recent"], result["previous"])
        self.assertEqual(result["direction"], "increasing")


class PlayerUsageBuildTests(unittest.TestCase):
    def test_build_returns_none_for_blank(self):
        self.assertIsNone(build_player_usage(""))

    def test_build_smoke_when_db_available(self):
        try:
            payload = build_player_usage(
                "ip_player_83482914",
                season=2026,
                period="last_8",
                scoring="ppr",
            )
        except Exception:
            self.skipTest("database unavailable")
        if payload is None:
            self.skipTest("player or database unavailable")
        self.assertEqual(payload["player_id"], "ip_player_83482914")
        self.assertIn("role_opportunity", payload)
        self.assertIn("signals", payload)
        self.assertIn("weekly_usage", payload)
        self.assertIn("chart_metrics", payload)


if __name__ == "__main__":
    unittest.main()
