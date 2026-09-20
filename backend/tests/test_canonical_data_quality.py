"""Tests for canonical ingestion data-quality checks."""

from __future__ import annotations

import unittest

import pandas as pd

from app.canonical.data_quality import (
    validate_canonical_frames,
)
from app.canonical.ids import (
    make_game_id,
    make_player_id,
    make_team_id,
    game_resolution_key,
    player_resolution_key,
)


class CanonicalDataQualityTests(unittest.TestCase):

    def _ids(self) -> dict[str, str]:
        return {
            "player": make_player_id(
                player_resolution_key(gsis_id="00-0036900")
            ),
            "player2": make_player_id(
                player_resolution_key(gsis_id="00-0036901")
            ),
            "team": make_team_id("CIN"),
            "game": make_game_id(
                game_resolution_key(
                    nflverse_game_id="2024_01_CIN_BAL"
                )
            ),
        }

    def _valid_frames(self) -> dict[str, pd.DataFrame]:
        ids = self._ids()
        teams = pd.DataFrame(
            [
                {
                    "team_id": make_team_id(f"T{index:02d}"),
                    "team_abbreviation": f"T{index:02d}",
                }
                for index in range(32)
            ]
        )
        # Ensure CIN exists for referential checks.
        teams.loc[0, "team_id"] = ids["team"]
        teams.loc[0, "team_abbreviation"] = "CIN"

        players = pd.DataFrame(
            [
                {
                    "player_id": ids["player"],
                    "position": "WR",
                    "current_team_id": ids["team"],
                }
            ]
            + [
                {
                    "player_id": make_player_id(
                        player_resolution_key(
                            gsis_id=f"00-0036{index:03d}"
                        )
                    ),
                    "position": "RB",
                    "current_team_id": ids["team"],
                }
                for index in range(100)
            ]
        )
        games = pd.DataFrame(
            [
                {
                    "game_id": ids["game"],
                    "season": 2024,
                    "week": 1,
                }
            ]
        )
        facts = pd.DataFrame(
            [
                {
                    "player_id": ids["player"],
                    "game_id": ids["game"],
                    "season": 2024,
                    "week": 1,
                    "team_id": ids["team"],
                    "pass_attempts": 0,
                    "pass_completions": 0,
                    "pass_yards": 0,
                    "pass_tds": 0,
                    "interceptions": 0,
                    "rush_attempts": 2,
                    "rush_yards": 12,
                    "rush_tds": 0,
                    "targets": 8,
                    "receptions": 6,
                    "receiving_yards": 80,
                    "receiving_tds": 1,
                }
            ]
        )
        usage = pd.DataFrame(
            [
                {
                    "player_id": ids["player"],
                    "game_id": ids["game"],
                    "season": 2024,
                    "week": 1,
                    "team_id": ids["team"],
                    "position": "WR",
                }
            ]
        )
        return {
            "dim_team": teams,
            "dim_player": players,
            "dim_game": games,
            "fact_player_game": facts,
            "fact_player_usage": usage,
        }

    def test_valid_bundle_passes(self):
        report = validate_canonical_frames(
            self._valid_frames(),
            seasons=[2024],
            current_season=2024,
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.status, "passed")
        self.assertEqual(
            report.message,
            "The data loaded successfully and passed validation.",
        )

    def test_duplicate_player_game_fails(self):
        frames = self._valid_frames()
        frames["fact_player_game"] = pd.concat(
            [
                frames["fact_player_game"],
                frames["fact_player_game"],
            ],
            ignore_index=True,
        )
        report = validate_canonical_frames(
            frames,
            seasons=[2024],
            current_season=2024,
            require_core_facts=False,
        )
        self.assertFalse(report.passed)
        self.assertEqual(report.status, "failed")
        self.assertIn("failed validation", report.message)
        dup = next(
            check
            for check in report.checks
            if check.check_id
            == "fact_player_game.duplicate_player_game"
        )
        self.assertFalse(dup.passed)

    def test_missing_player_id_fails(self):
        frames = self._valid_frames()
        frames["fact_player_game"].loc[0, "player_id"] = None
        report = validate_canonical_frames(
            frames,
            seasons=[2024],
            current_season=2024,
            require_core_facts=False,
        )
        self.assertFalse(report.passed)
        missing = next(
            check
            for check in report.checks
            if check.check_id == "fact_player_game.player_ids"
        )
        self.assertFalse(missing.passed)

    def test_invalid_season_week_fails(self):
        frames = self._valid_frames()
        frames["fact_player_game"].loc[0, "week"] = 99
        report = validate_canonical_frames(
            frames,
            seasons=[2024],
            current_season=2024,
            require_core_facts=False,
        )
        self.assertFalse(report.passed)

    def test_orphan_game_id_fails_referential_check(self):
        frames = self._valid_frames()
        frames["fact_player_game"].loc[0, "game_id"] = make_game_id(
            game_resolution_key(
                nflverse_game_id="2024_02_MISSING"
            )
        )
        report = validate_canonical_frames(
            frames,
            seasons=[2024],
            current_season=2024,
            require_core_facts=False,
        )
        self.assertFalse(report.passed)
        ref = next(
            check
            for check in report.checks
            if check.check_id == "ref.fact_player_game.game_id"
        )
        self.assertFalse(ref.passed)

    def test_negative_stats_warn(self):
        frames = self._valid_frames()
        frames["fact_player_game"].loc[0, "receiving_yards"] = -5
        report = validate_canonical_frames(
            frames,
            seasons=[2024],
            current_season=2024,
            require_core_facts=False,
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.status, "passed_with_warnings")
        stats = next(
            check
            for check in report.checks
            if check.check_id == "fact_player_game.stats"
        )
        self.assertFalse(stats.passed)


if __name__ == "__main__":
    unittest.main()
