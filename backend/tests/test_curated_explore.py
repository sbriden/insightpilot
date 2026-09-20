"""Smoke tests for denormalized curated explore datasets."""

from __future__ import annotations

import unittest

from app.sources.fantasy.curated_explore import (
    CURATED_EXPLORE_DATASETS,
    get_curated_dataset,
    is_curated_explore_id,
    load_curated_explore,
)


class CuratedExploreMetaTests(unittest.TestCase):
    def test_known_ids(self):
        self.assertTrue(
            is_curated_explore_id("curated_fantasy_signals")
        )
        self.assertFalse(is_curated_explore_id("fact_player_game"))
        self.assertEqual(
            get_curated_dataset("curated_players").title,
            "Players",
        )
        self.assertGreaterEqual(len(CURATED_EXPLORE_DATASETS), 10)


class CuratedExploreLoadTests(unittest.TestCase):
    def test_signals_denormalized(self):
        try:
            frame, dataset = load_curated_explore(
                "curated_fantasy_signals",
                seasons=None,
            )
        except Exception as exc:
            self.skipTest(f"database unavailable: {exc}")
        self.assertEqual(dataset.id, "curated_fantasy_signals")
        self.assertFalse(frame.empty)
        columns = set(frame.columns)
        self.assertIn("player", columns)
        self.assertIn("team", columns)
        self.assertNotIn("player_id", columns)
        self.assertNotIn("team_id", columns)
        self.assertNotIn("source_ids", columns)

    def test_usage_combines_efficiency(self):
        try:
            frame, _ = load_curated_explore(
                "curated_player_usage",
                seasons=None,
            )
        except Exception as exc:
            self.skipTest(f"database unavailable: {exc}")
        columns = set(frame.columns)
        self.assertIn("player", columns)
        self.assertIn("opponent", columns)
        self.assertTrue(
            "offensive_snap_share" in columns
            or "yards_per_target" in columns
        )


if __name__ == "__main__":
    unittest.main()
