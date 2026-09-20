"""Tests for canonical fact_team_game."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    game_resolution_key,
    is_game_id,
    is_team_id,
    make_game_id,
    make_team_id,
)
from app.canonical.fact_team_game import (
    build_fact_team_game,
)


class FactTeamGameTests(unittest.TestCase):

    def test_build_fact_team_game_environment(self):
        game = "2024_01_KC_BAL"
        game_id = make_game_id(
            game_resolution_key(nflverse_game_id=game)
        )

        pbp = pd.DataFrame(
            [
                {
                    "game_id": game,
                    "posteam": "KC",
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "pass": 1,
                    "rush": 0,
                    "epa": 0.5,
                    "yards_gained": 12,
                    "yardline_100": 40,
                    "touchdown": 0,
                    "td_team": None,
                    "interception": 0,
                    "fumble_lost": 0,
                    "score_differential": 0,
                    "qtr": 1,
                    "game_seconds_remaining": 3600,
                    "fixed_drive": 1,
                },
                {
                    "game_id": game,
                    "posteam": "KC",
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "pass": 0,
                    "rush": 1,
                    "epa": -0.2,
                    "yards_gained": 4,
                    "yardline_100": 15,
                    "touchdown": 0,
                    "td_team": None,
                    "interception": 0,
                    "fumble_lost": 0,
                    "score_differential": 0,
                    "qtr": 2,
                    "game_seconds_remaining": 3000,
                    "fixed_drive": 2,
                },
                {
                    "game_id": game,
                    "posteam": "KC",
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "pass": 1,
                    "rush": 0,
                    "epa": 1.5,
                    "yards_gained": 15,
                    "yardline_100": 8,
                    "touchdown": 1,
                    "td_team": "KC",
                    "interception": 0,
                    "fumble_lost": 0,
                    "score_differential": 3,
                    "qtr": 2,
                    "game_seconds_remaining": 2900,
                    "fixed_drive": 2,
                },
                {
                    "game_id": game,
                    "posteam": "KC",
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "pass": 1,
                    "rush": 0,
                    "epa": -2.0,
                    "yards_gained": 0,
                    "yardline_100": 55,
                    "touchdown": 0,
                    "td_team": None,
                    "interception": 1,
                    "fumble_lost": 0,
                    "score_differential": 14,
                    "qtr": 4,
                    "game_seconds_remaining": 400,
                    "fixed_drive": 3,
                },
                {
                    "game_id": game,
                    "posteam": "BAL",
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "pass": 1,
                    "rush": 0,
                    "epa": 0.1,
                    "yards_gained": 8,
                    "yardline_100": 70,
                    "touchdown": 0,
                    "td_team": None,
                    "interception": 0,
                    "fumble_lost": 1,
                    "score_differential": -3,
                    "qtr": 1,
                    "game_seconds_remaining": 3400,
                    "fixed_drive": 1,
                },
            ]
        )

        schedules = pd.DataFrame(
            [
                {
                    "game_id": game,
                    "season": 2024,
                    "week": 1,
                    "game_type": "REG",
                    "home_team": "BAL",
                    "away_team": "KC",
                    "home_score": 20,
                    "away_score": 27,
                }
            ]
        )

        with patch(
            "app.canonical.fact_team_game.upsert_fact_team_game"
        ):
            fact = build_fact_team_game(
                [2024],
                persist=True,
                source_frames={
                    "pbp": pbp,
                    "schedules": schedules,
                },
                game_id_lookup={game: game_id},
            )

        self.assertEqual(len(fact), 2)
        kc = fact[fact["team_id"] == make_team_id("KC")].iloc[0]
        self.assertTrue(is_team_id(kc["team_id"]))
        self.assertTrue(is_game_id(kc["game_id"]))
        self.assertEqual(kc["offensive_plays"], 4)
        self.assertEqual(kc["pass_attempts"], 3)
        self.assertEqual(kc["rush_attempts"], 1)
        self.assertAlmostEqual(kc["pass_rate"], 0.75)
        # Neutral = first 3 plays (qtr<=3 and |diff|<=7)
        self.assertAlmostEqual(kc["neutral_pass_rate"], 2 / 3)
        self.assertEqual(kc["points"], 27)
        self.assertEqual(kc["yards"], 31)
        self.assertAlmostEqual(kc["offensive_epa"], -0.2)
        self.assertAlmostEqual(kc["pass_epa"], 0.0)
        self.assertAlmostEqual(kc["rush_epa"], -0.2)
        self.assertEqual(kc["red_zone_trips"], 1)
        self.assertAlmostEqual(kc["red_zone_td_rate"], 1.0)
        self.assertEqual(kc["turnovers"], 1)
        self.assertIsNotNone(kc["pace"])

        bal = fact[fact["team_id"] == make_team_id("BAL")].iloc[0]
        self.assertEqual(bal["points"], 20)
        self.assertEqual(bal["turnovers"], 1)

        source_ids = json.loads(kc["source_ids"])
        self.assertEqual(source_ids["team_abbreviation"], "KC")
        self.assertEqual(source_ids["nflverse_game_id"], game)


if __name__ == "__main__":
    unittest.main()
