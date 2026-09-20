"""Tests for canonical fact_defensive_game."""

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
from app.canonical.fact_defensive_game import (
    build_fact_defensive_game,
)


class FactDefensiveGameTests(unittest.TestCase):

    def test_build_fact_defensive_game(self):
        game = "2024_03_DAL_PHI"
        game_id = make_game_id(
            game_resolution_key(nflverse_game_id=game)
        )

        pbp = pd.DataFrame(
            [
                # PHI defense faces DAL pass completion
                {
                    "game_id": game,
                    "defteam": "PHI",
                    "posteam": "DAL",
                    "season": 2024,
                    "week": 3,
                    "season_type": "REG",
                    "pass": 1,
                    "rush": 0,
                    "epa": 0.8,
                    "yards_gained": 18,
                    "passing_yards": 18,
                    "rushing_yards": None,
                    "receiving_yards": 18,
                    "sack": 0,
                    "qb_hit": 0,
                    "complete_pass": 1,
                    "receiver_player_id": "00-0031111",
                },
                # PHI sack
                {
                    "game_id": game,
                    "defteam": "PHI",
                    "posteam": "DAL",
                    "season": 2024,
                    "week": 3,
                    "season_type": "REG",
                    "pass": 1,
                    "rush": 0,
                    "epa": -1.5,
                    "yards_gained": -7,
                    "passing_yards": 0,
                    "rushing_yards": None,
                    "receiving_yards": None,
                    "sack": 1,
                    "qb_hit": 1,
                    "complete_pass": 0,
                    "receiver_player_id": None,
                },
                # PHI faces rush
                {
                    "game_id": game,
                    "defteam": "PHI",
                    "posteam": "DAL",
                    "season": 2024,
                    "week": 3,
                    "season_type": "REG",
                    "pass": 0,
                    "rush": 1,
                    "epa": 0.2,
                    "yards_gained": 5,
                    "passing_yards": None,
                    "rushing_yards": 5,
                    "receiving_yards": None,
                    "sack": 0,
                    "qb_hit": 0,
                    "complete_pass": 0,
                    "receiver_player_id": None,
                },
                # DAL defense faces PHI incomplete + pressure hit
                {
                    "game_id": game,
                    "defteam": "DAL",
                    "posteam": "PHI",
                    "season": 2024,
                    "week": 3,
                    "season_type": "REG",
                    "pass": 1,
                    "rush": 0,
                    "epa": -0.4,
                    "yards_gained": 0,
                    "passing_yards": 0,
                    "rushing_yards": None,
                    "receiving_yards": None,
                    "sack": 0,
                    "qb_hit": 1,
                    "complete_pass": 0,
                    "receiver_player_id": "00-0032222",
                },
            ]
        )

        schedules = pd.DataFrame(
            [
                {
                    "game_id": game,
                    "season": 2024,
                    "week": 3,
                    "game_type": "REG",
                    "home_team": "PHI",
                    "away_team": "DAL",
                    "home_score": 24,
                    "away_score": 17,
                }
            ]
        )

        with patch(
            "app.canonical.fact_defensive_game.upsert_fact_defensive_game"
        ):
            fact = build_fact_defensive_game(
                [2024],
                persist=True,
                source_frames={
                    "pbp": pbp,
                    "schedules": schedules,
                },
                game_id_lookup={game: game_id},
            )

        self.assertEqual(len(fact), 2)

        phi = fact[
            fact["defensive_team_id"] == make_team_id("PHI")
        ].iloc[0]
        self.assertTrue(is_team_id(phi["defensive_team_id"]))
        self.assertEqual(
            phi["opponent_team_id"],
            make_team_id("DAL"),
        )
        self.assertTrue(is_game_id(phi["game_id"]))
        self.assertEqual(phi["points_allowed"], 17)
        self.assertEqual(phi["yards_allowed"], 16)
        self.assertEqual(phi["pass_yards_allowed"], 18)
        self.assertEqual(phi["rush_yards_allowed"], 5)
        self.assertAlmostEqual(phi["pass_epa_allowed"], -0.7)
        self.assertAlmostEqual(phi["rush_epa_allowed"], 0.2)
        # 2 pass plays faced; 1 pressure (sack+hit counts once)
        self.assertAlmostEqual(phi["pressure_rate"], 0.5)
        self.assertAlmostEqual(phi["sack_rate"], 0.5)
        self.assertEqual(phi["targets_allowed"], 1)
        self.assertEqual(phi["receptions_allowed"], 1)
        self.assertEqual(phi["receiving_yards_allowed"], 18)

        dal = fact[
            fact["defensive_team_id"] == make_team_id("DAL")
        ].iloc[0]
        self.assertEqual(dal["points_allowed"], 24)
        self.assertAlmostEqual(dal["pressure_rate"], 1.0)
        self.assertEqual(dal["targets_allowed"], 1)
        self.assertEqual(dal["receptions_allowed"], 0)

        source_ids = json.loads(phi["source_ids"])
        self.assertEqual(
            source_ids["defensive_team_abbreviation"],
            "PHI",
        )
        self.assertEqual(
            source_ids["nflverse_game_id"],
            game,
        )


if __name__ == "__main__":
    unittest.main()
