"""Tests for DFS slate windows (main / thu / snf / mnf)."""

from __future__ import annotations

import unittest

from app.analysis.insights.dfs.slate import (
    _classify_game,
    _parse_slate_id,
    _slate_id,
    list_dfs_slates,
)


class DfsSlateParseTests(unittest.TestCase):
    def test_parse_legacy_main(self):
        parsed = _parse_slate_id("nfl-2026-main", 2026)
        self.assertEqual(parsed["season"], 2026)
        self.assertIsNone(parsed["week"])
        self.assertEqual(parsed["kind"], "main")

    def test_parse_week_and_kind(self):
        parsed = _parse_slate_id("nfl-2026-2-snf", 2026)
        self.assertEqual(parsed["season"], 2026)
        self.assertEqual(parsed["week"], 2)
        self.assertEqual(parsed["kind"], "snf")

    def test_parse_aliases(self):
        self.assertEqual(
            _parse_slate_id("nfl-2026-thursday", 2026)["kind"],
            "thu",
        )
        self.assertEqual(
            _parse_slate_id(
                "nfl-2026-2-monday-night", 2026
            )["kind"],
            "mnf",
        )

    def test_slate_id_format(self):
        self.assertEqual(
            _slate_id(2026, 2, "thu"),
            "nfl-2026-2-thu",
        )


class DfsSlateClassifyTests(unittest.TestCase):
    def test_thursday(self):
        self.assertEqual(
            _classify_game(
                {
                    "weekday": "Thursday",
                    "gametime": "20:15",
                }
            ),
            "thu",
        )

    def test_monday(self):
        self.assertEqual(
            _classify_game(
                {
                    "weekday": "Monday",
                    "gametime": "20:15",
                }
            ),
            "mnf",
        )

    def test_sunday_afternoon_main(self):
        self.assertEqual(
            _classify_game(
                {
                    "weekday": "Sunday",
                    "gametime": "13:00",
                }
            ),
            "main",
        )
        self.assertEqual(
            _classify_game(
                {
                    "weekday": "Sunday",
                    "gametime": "16:25",
                }
            ),
            "main",
        )

    def test_sunday_night(self):
        self.assertEqual(
            _classify_game(
                {
                    "weekday": "Sunday",
                    "gametime": "20:20",
                }
            ),
            "snf",
        )


class DfsSlateListTests(unittest.TestCase):
    def test_lists_four_windows(self):
        slates = list_dfs_slates(season=2026, week=2)
        kinds = [item["kind"] for item in slates]
        self.assertEqual(kinds, ["main", "thu", "snf", "mnf"])
        by_kind = {item["kind"]: item for item in slates}
        self.assertGreaterEqual(by_kind["main"]["game_count"], 1)
        self.assertEqual(by_kind["thu"]["game_count"], 1)
        self.assertEqual(by_kind["snf"]["game_count"], 1)
        self.assertEqual(by_kind["mnf"]["game_count"], 1)
        self.assertEqual(
            set(by_kind["thu"]["teams"]),
            {"BUF", "DET"},
        )
        self.assertEqual(
            set(by_kind["snf"]["teams"]),
            {"KC", "IND"},
        )
        self.assertEqual(
            set(by_kind["mnf"]["teams"]),
            {"LA", "NYG"},
        )

    def test_lists_showdown_games(self):
        slates = list_dfs_slates(
            season=2026,
            week=2,
            contest_type="showdown",
        )
        self.assertGreaterEqual(len(slates), 14)
        self.assertTrue(
            all(item["contest_type"] == "showdown" for item in slates)
        )
        self.assertTrue(
            all(item["game_count"] == 1 for item in slates)
        )
        ids = {item["slate_id"] for item in slates}
        self.assertIn("nfl-2026-2-sd-DET-BUF", ids)
        self.assertIn("nfl-2026-2-sd-IND-KC", ids)

    def test_parse_showdown_id(self):
        parsed = _parse_slate_id(
            "nfl-2026-2-sd-BUF-DET",
            2026,
        )
        self.assertEqual(parsed["kind"], "sd")
        self.assertEqual(parsed["away_team"], "BUF")
        self.assertEqual(parsed["home_team"], "DET")
        self.assertEqual(parsed["contest_type"], "showdown")
