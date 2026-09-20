"""Tests for canonical dim_game."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    is_game_id,
    make_game_id,
    make_team_id,
)
from app.canonical.dim_game import (
    build_dim_game,
)


class DimGameTests(unittest.TestCase):

    def test_game_id_is_insightpilot_owned(self):
        game_id = make_game_id("nflverse_game:2024_01_CIN_NE")
        self.assertTrue(is_game_id(game_id))
        self.assertEqual(
            game_id,
            make_game_id("nflverse_game:2024_01_CIN_NE"),
        )
        self.assertNotEqual(game_id, "2024_01_CIN_NE")

    def test_build_dim_game(self):
        schedules = pd.DataFrame(
            [
                {
                    "game_id": "2024_01_CIN_NE",
                    "season": 2024,
                    "week": 1,
                    "game_type": "REG",
                    "gameday": "2024-09-08",
                    "home_team": "CIN",
                    "away_team": "NE",
                    "home_score": 16,
                    "away_score": 10,
                    "gsis": "12345",
                },
                {
                    "game_id": "2024_18_KC_DEN",
                    "season": 2024,
                    "week": 18,
                    "game_type": "REG",
                    "gameday": "2025-01-05",
                    "home_team": "KC",
                    "away_team": "DEN",
                    "home_score": None,
                    "away_score": None,
                },
            ]
        )

        with (
            patch(
                "app.canonical.dim_game.upsert_dim_game"
            ),
            patch(
                "app.canonical.dim_team.get_dim_team",
                return_value=pd.DataFrame(),
            ),
        ):
            dim = build_dim_game(
                [2024],
                persist=True,
                source_frames={"schedules": schedules},
            )

        self.assertEqual(len(dim), 2)

        cin = dim[
            dim["home_team_id"] == make_team_id("CIN")
        ].iloc[0]
        self.assertTrue(is_game_id(cin["game_id"]))
        self.assertEqual(cin["season"], 2024)
        self.assertEqual(cin["week"], 1)
        self.assertEqual(cin["season_type"], "REG")
        self.assertEqual(cin["game_date"], "2024-09-08")
        self.assertEqual(
            cin["away_team_id"],
            make_team_id("NE"),
        )
        self.assertEqual(cin["home_score"], 16)
        self.assertEqual(cin["away_score"], 10)
        self.assertEqual(cin["game_status"], "Final")
        source_ids = json.loads(cin["source_ids"])
        self.assertEqual(
            source_ids["nflverse_game_id"],
            "2024_01_CIN_NE",
        )
        self.assertEqual(source_ids["gsis"], "12345")

        scheduled = dim[
            dim["home_team_id"] == make_team_id("KC")
        ].iloc[0]
        self.assertEqual(scheduled["game_status"], "Scheduled")
        self.assertIsNone(scheduled["home_score"])
        self.assertIsNone(scheduled["away_score"])


if __name__ == "__main__":
    unittest.main()
