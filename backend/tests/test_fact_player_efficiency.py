"""Tests for canonical fact_player_efficiency."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    game_resolution_key,
    is_game_id,
    is_player_id,
    make_game_id,
    make_player_id,
    player_resolution_key,
)
from app.canonical.fact_player_efficiency import (
    build_fact_player_efficiency,
)


class FactPlayerEfficiencyTests(unittest.TestCase):

    def test_build_keeps_rates_separate_from_volume(self):
        gsis_id = "00-0030100"
        game = "2024_02_BUF_MIA"
        player_id = make_player_id(
            player_resolution_key(gsis_id=gsis_id)
        )
        game_id = make_game_id(
            game_resolution_key(nflverse_game_id=game)
        )

        stats = pd.DataFrame(
            [
                {
                    "player_id": gsis_id,
                    "game_id": game,
                    "season": 2024,
                    "week": 2,
                    "season_type": "REG",
                    "team": "BUF",
                    "position": "RB",
                    "carries": 10,
                    "rushing_yards": 55,
                    "rushing_tds": 1,
                    "rushing_epa": 2.5,
                    "targets": 5,
                    "receptions": 4,
                    "receiving_yards": 40,
                    "receiving_tds": 0,
                    "attempts": 0,
                    "passing_tds": 0,
                    "passing_epa": None,
                    "fantasy_points_ppr": 19.5,
                }
            ]
        )
        usage = pd.DataFrame(
            [
                {
                    "gsis_id": gsis_id,
                    "nflverse_game_id": game,
                    "routes_run": 8,
                    "dropbacks": None,
                    "touches": 14,
                }
            ]
        )

        with patch(
            "app.canonical.fact_player_efficiency.upsert_fact_player_efficiency"
        ):
            fact = build_fact_player_efficiency(
                [2024],
                persist=True,
                source_frames={
                    "player_stats": stats,
                    "usage": usage,
                },
                player_id_lookup={gsis_id: player_id},
                game_id_lookup={game: game_id},
            )

        self.assertEqual(len(fact), 1)
        row = fact.iloc[0]
        self.assertTrue(is_player_id(row["player_id"]))
        self.assertTrue(is_game_id(row["game_id"]))
        self.assertAlmostEqual(row["yards_per_carry"], 5.5)
        self.assertAlmostEqual(row["yards_per_target"], 8.0)
        self.assertAlmostEqual(row["yards_per_route_run"], 5.0)
        self.assertAlmostEqual(row["catch_rate"], 0.8)
        self.assertAlmostEqual(row["td_rate"], 1.0 / 14.0)
        self.assertIsNone(row["pass_epa_per_dropback"])
        self.assertAlmostEqual(row["rush_epa_per_attempt"], 0.25)
        self.assertAlmostEqual(
            row["fantasy_points_per_touch"],
            19.5 / 14.0,
        )
        self.assertAlmostEqual(
            row["fantasy_points_per_route"],
            19.5 / 8.0,
        )
        # Volume columns must not leak into efficiency.
        self.assertNotIn("carries", fact.columns)
        self.assertNotIn("routes_run", fact.columns)
        self.assertNotIn("touches", fact.columns)

        source_ids = json.loads(row["source_ids"])
        self.assertEqual(source_ids["gsis_id"], gsis_id)

    def test_qb_td_rate_uses_pass_attempts(self):
        gsis_id = "00-0030200"
        game = "2024_02_KC_CIN"
        player_id = make_player_id(
            player_resolution_key(gsis_id=gsis_id)
        )
        game_id = make_game_id(
            game_resolution_key(nflverse_game_id=game)
        )

        stats = pd.DataFrame(
            [
                {
                    "player_id": gsis_id,
                    "game_id": game,
                    "season": 2024,
                    "week": 2,
                    "season_type": "REG",
                    "team": "KC",
                    "position": "QB",
                    "carries": 0,
                    "rushing_yards": 0,
                    "rushing_tds": 0,
                    "rushing_epa": None,
                    "targets": 0,
                    "receptions": 0,
                    "receiving_yards": 0,
                    "receiving_tds": 0,
                    "attempts": 30,
                    "passing_tds": 3,
                    "passing_epa": 6.0,
                    "fantasy_points_ppr": 24.0,
                }
            ]
        )
        usage = pd.DataFrame(
            [
                {
                    "gsis_id": gsis_id,
                    "nflverse_game_id": game,
                    "routes_run": None,
                    "dropbacks": 32,
                    "touches": 0,
                }
            ]
        )

        with patch(
            "app.canonical.fact_player_efficiency.upsert_fact_player_efficiency"
        ):
            fact = build_fact_player_efficiency(
                [2024],
                persist=False,
                source_frames={
                    "player_stats": stats,
                    "usage": usage,
                },
                player_id_lookup={gsis_id: player_id},
                game_id_lookup={game: game_id},
            )

        row = fact.iloc[0]
        self.assertAlmostEqual(row["td_rate"], 0.1)
        self.assertAlmostEqual(row["pass_epa_per_dropback"], 0.1875)
        self.assertIsNone(row["yards_per_carry"])
        self.assertIsNone(row["fantasy_points_per_route"])


if __name__ == "__main__":
    unittest.main()
