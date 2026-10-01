"""Tests for canonical fact_game_market."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    game_resolution_key,
    is_game_id,
    make_game_id,
)
from app.canonical.fact_game_market import (
    build_fact_game_market,
)


class FactGameMarketTests(unittest.TestCase):

    def test_build_fact_game_market_implied_totals(self):
        game = "2024_01_BAL_KC"
        game_id = make_game_id(
            game_resolution_key(nflverse_game_id=game)
        )

        schedules = pd.DataFrame(
            [
                {
                    "game_id": game,
                    "season": 2024,
                    "week": 1,
                    "game_type": "REG",
                    "home_team": "KC",
                    "away_team": "BAL",
                    "gameday": "2024-09-05",
                    "gametime": "20:20",
                    "spread_line": 3.0,
                    "total_line": 46.0,
                },
                {
                    "game_id": "2024_01_HOU_IND",
                    "season": 2024,
                    "week": 1,
                    "game_type": "REG",
                    "home_team": "IND",
                    "away_team": "HOU",
                    "gameday": "2024-09-08",
                    "gametime": "13:00:00",
                    "spread_line": -3.0,
                    "total_line": 49.0,
                },
                {
                    # No lines — skipped
                    "game_id": "2024_01_NO_LINE",
                    "season": 2024,
                    "week": 1,
                    "game_type": "REG",
                    "home_team": "NO",
                    "away_team": "CAR",
                    "gameday": "2024-09-08",
                    "gametime": "13:00",
                    "spread_line": None,
                    "total_line": None,
                },
            ]
        )

        dog_game_id = make_game_id(
            game_resolution_key(
                nflverse_game_id="2024_01_HOU_IND"
            )
        )

        with patch(
            "app.canonical.fact_game_market.upsert_fact_game_market"
        ):
            fact = build_fact_game_market(
                [2024],
                persist=True,
                source_frames={"schedules": schedules},
                game_id_lookup={
                    game: game_id,
                    "2024_01_HOU_IND": dog_game_id,
                },
            )

        self.assertEqual(len(fact), 2)

        kc = fact[fact["game_id"] == game_id].iloc[0]
        self.assertTrue(is_game_id(kc["game_id"]))
        self.assertEqual(kc["source"], "nflverse_schedules")
        self.assertEqual(kc["timestamp"], "2024-09-05T20:20:00")
        self.assertEqual(kc["spread"], 3.0)
        self.assertEqual(kc["over_under"], 46.0)
        self.assertEqual(kc["opening_spread"], 3.0)
        self.assertEqual(kc["opening_over_under"], 46.0)
        # home favored by 3 → home 24.5, away 21.5
        self.assertAlmostEqual(kc["home_implied_total"], 24.5)
        self.assertAlmostEqual(kc["away_implied_total"], 21.5)

        ind = fact[fact["game_id"] == dog_game_id].iloc[0]
        self.assertEqual(ind["spread"], -3.0)
        self.assertAlmostEqual(ind["home_implied_total"], 23.0)
        self.assertAlmostEqual(ind["away_implied_total"], 26.0)

        source_ids = json.loads(kc["source_ids"])
        self.assertEqual(source_ids["nflverse_game_id"], game)
        self.assertEqual(source_ids["home_team"], "KC")


if __name__ == "__main__":
    unittest.main()
