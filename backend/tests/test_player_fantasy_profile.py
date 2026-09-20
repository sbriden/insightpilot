"""Tests for InsightPilot proprietary player_fantasy_profile."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.analytics.player_fantasy_profile import (
    build_player_fantasy_profile,
)
from app.canonical.ids import (
    game_resolution_key,
    make_game_id,
    make_player_id,
    make_team_id,
    player_resolution_key,
)


class PlayerFantasyProfileTests(unittest.TestCase):

    def test_composes_proprietary_weekly_profile(self):
        player_id = make_player_id(
            player_resolution_key(gsis_id="00-0038888")
        )
        team_id = make_team_id("BUF")
        game_id = make_game_id(
            game_resolution_key(
                nflverse_game_id="2024_03_BUF_MIA"
            )
        )

        production = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "game_id": game_id,
                    "season": 2024,
                    "week": 3,
                    "team_id": team_id,
                    "pass_yards": 0,
                    "pass_tds": 0,
                    "interceptions": 0,
                    "rush_yards": 80,
                    "rush_tds": 1,
                    "receptions": 4,
                    "receiving_yards": 30,
                    "receiving_tds": 0,
                }
            ]
        )
        opportunity = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "season": 2024,
                    "week": 3,
                    "opportunity_score": 72.0,
                }
            ]
        )
        efficiency = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "season": 2024,
                    "week": 3,
                    "efficiency_score": 61.0,
                }
            ]
        )
        trends = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "season": 2024,
                    "week": 3,
                    "opportunity_trend": 0.05,
                    "snap_share_change": 0.04,
                    "target_share_change": 0.02,
                }
            ]
        )
        matchups = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "season": 2024,
                    "week": 3,
                    "matchup_score": 58.0,
                }
            ]
        )
        environments = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "season": 2024,
                    "week": 3,
                    "game_environment_score": 64.0,
                }
            ]
        )
        injuries = pd.DataFrame(
            [
                {
                    "player_id": player_id,
                    "season": 2024,
                    "week": 3,
                    "game_status": "Questionable",
                    "is_expected_to_play": None,
                }
            ]
        )

        with patch(
            "app.canonical.analytics.player_fantasy_profile.upsert_player_fantasy_profile"
        ):
            frame = build_player_fantasy_profile(
                [2024],
                persist=True,
                source_frames={
                    "production": production,
                    "opportunity": opportunity,
                    "efficiency": efficiency,
                    "trends": trends,
                    "matchups": matchups,
                    "environments": environments,
                    "injuries": injuries,
                },
            )

        self.assertEqual(len(frame), 1)
        row = frame.iloc[0]
        self.assertEqual(
            list(frame.columns),
            [
                "player_id",
                "season",
                "week",
                "production_score",
                "opportunity_score",
                "efficiency_score",
                "trend_score",
                "matchup_score",
                "environment_score",
                "risk_score",
                "fantasy_value_score",
                "source_ids",
            ],
        )
        self.assertAlmostEqual(
            float(row["opportunity_score"]),
            72.0,
            places=5,
        )
        self.assertAlmostEqual(
            float(row["efficiency_score"]),
            61.0,
            places=5,
        )
        self.assertAlmostEqual(
            float(row["matchup_score"]),
            58.0,
            places=5,
        )
        self.assertAlmostEqual(
            float(row["environment_score"]),
            64.0,
            places=5,
        )
        # trend 0.05 → 50 + 10 = 60
        self.assertAlmostEqual(
            float(row["trend_score"]),
            60.0,
            places=5,
        )
        self.assertIsNotNone(row["production_score"])
        self.assertIsNotNone(row["risk_score"])
        self.assertGreater(float(row["risk_score"]), 40)
        self.assertIsNotNone(row["fantasy_value_score"])
        self.assertGreater(
            float(row["fantasy_value_score"]),
            0,
        )
        self.assertLessEqual(
            float(row["fantasy_value_score"]),
            100,
        )


if __name__ == "__main__":
    unittest.main()
