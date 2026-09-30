"""Tests for canonical fact_player_game."""

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
    make_team_id,
    player_resolution_key,
)
from app.canonical.fact_player_game import (
    build_fact_player_game,
)


class FactPlayerGameTests(unittest.TestCase):

    def test_build_fact_player_game(self):
        gsis_id = "00-0023459"
        nflverse_game_id = "2024_01_NYJ_SF"
        player_id = make_player_id(
            player_resolution_key(gsis_id=gsis_id)
        )
        game_id = make_game_id(
            game_resolution_key(
                nflverse_game_id=nflverse_game_id,
            )
        )

        stats = pd.DataFrame(
            [
                {
                    "player_id": gsis_id,
                    "game_id": nflverse_game_id,
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "team": "NYJ",
                    "attempts": 21,
                    "completions": 13,
                    "passing_yards": 167,
                    "passing_tds": 1,
                    "passing_interceptions": 1,
                    "passing_epa": 3.25,
                    "passing_cpoe": -5.9,
                    "carries": 1,
                    "rushing_yards": -1,
                    "rushing_tds": 0,
                    "rushing_epa": 0.0,
                    "targets": 0,
                    "receptions": 0,
                    "receiving_yards": 0,
                    "receiving_tds": 0,
                    "receiving_epa": None,
                }
            ]
        )

        with patch(
            "app.canonical.fact_player_game.upsert_fact_player_game"
        ):
            fact = build_fact_player_game(
                [2024],
                persist=True,
                source_frames={"player_stats": stats},
                player_id_lookup={gsis_id: player_id},
                game_id_lookup={nflverse_game_id: game_id},
            )

        self.assertEqual(len(fact), 1)
        row = fact.iloc[0]
        self.assertTrue(is_player_id(row["player_id"]))
        self.assertTrue(is_game_id(row["game_id"]))
        self.assertEqual(row["player_id"], player_id)
        self.assertEqual(row["game_id"], game_id)
        self.assertEqual(row["season"], 2024)
        self.assertEqual(row["week"], 1)
        self.assertEqual(row["season_type"], "REG")
        self.assertEqual(row["team_id"], make_team_id("NYJ"))
        self.assertEqual(row["pass_attempts"], 21)
        self.assertEqual(row["pass_completions"], 13)
        self.assertEqual(row["pass_yards"], 167)
        self.assertEqual(row["pass_tds"], 1)
        self.assertEqual(row["interceptions"], 1)
        self.assertAlmostEqual(row["pass_epa"], 3.25)
        self.assertAlmostEqual(row["pass_cpoe"], -5.9)
        self.assertEqual(row["rush_attempts"], 1)
        self.assertEqual(row["rush_yards"], -1)
        self.assertEqual(row["rush_tds"], 0)
        self.assertEqual(row["rush_epa"], 0.0)
        self.assertEqual(row["targets"], 0)
        self.assertEqual(row["receptions"], 0)
        self.assertEqual(row["receiving_yards"], 0)
        self.assertEqual(row["receiving_tds"], 0)
        self.assertIsNone(row["receiving_epa"])
        source_ids = json.loads(row["source_ids"])
        self.assertEqual(source_ids["gsis_id"], gsis_id)
        self.assertEqual(
            source_ids["nflverse_game_id"],
            nflverse_game_id,
        )

    def test_build_fact_player_game_kicker(self):
        gsis_id = "00-0034567"
        nflverse_game_id = "2024_01_KC_BAL"
        player_id = make_player_id(
            player_resolution_key(gsis_id=gsis_id)
        )
        game_id = make_game_id(
            game_resolution_key(
                nflverse_game_id=nflverse_game_id,
            )
        )
        stats = pd.DataFrame(
            [
                {
                    "player_id": gsis_id,
                    "game_id": nflverse_game_id,
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "team": "KC",
                    "fg_made": 3,
                    "fg_att": 3,
                    "fg_made_0_19": 0,
                    "fg_made_20_29": 1,
                    "fg_made_30_39": 1,
                    "fg_made_40_49": 1,
                    "fg_made_50_59": 0,
                    "fg_made_60_": 0,
                    "pat_made": 2,
                    "pat_att": 2,
                }
            ]
        )
        with patch(
            "app.canonical.fact_player_game.upsert_fact_player_game"
        ):
            fact = build_fact_player_game(
                [2024],
                persist=True,
                source_frames={"player_stats": stats},
                player_id_lookup={gsis_id: player_id},
                game_id_lookup={nflverse_game_id: game_id},
            )
        row = fact.iloc[0]
        self.assertEqual(int(row["fg_made"]), 3)
        self.assertEqual(int(row["fg_made_40_49"]), 1)
        self.assertEqual(int(row["pat_made"]), 2)

        from app.analysis.insights.fantasy_scoring import (
            fantasy_points_from_row,
        )

        # 3+3+4 FG + 2 PAT = 12
        self.assertEqual(
            fantasy_points_from_row(
                row.to_dict(),
                scoring="ppr",
            ),
            12.0,
        )

    def test_active_snap_zero_production_included(self):
        """Offensive snaps without box stats count as a 0-point game."""

        scored_gsis = "00-0033858"
        inactive_gsis = "00-0099999"
        game_w1 = "2026_01_GB_MIN"
        game_w2 = "2026_02_GB_NYJ"
        player_id = make_player_id(
            player_resolution_key(gsis_id=scored_gsis)
        )
        inactive_player_id = make_player_id(
            player_resolution_key(gsis_id=inactive_gsis)
        )
        game1 = make_game_id(
            game_resolution_key(nflverse_game_id=game_w1)
        )
        game2 = make_game_id(
            game_resolution_key(nflverse_game_id=game_w2)
        )

        stats = pd.DataFrame(
            [
                {
                    "player_id": scored_gsis,
                    "game_id": game_w1,
                    "season": 2026,
                    "week": 1,
                    "season_type": "REG",
                    "team": "GB",
                    "targets": 3,
                    "receptions": 2,
                    "receiving_yards": 50,
                    "receiving_tds": 0,
                }
            ]
        )
        snaps = pd.DataFrame(
            [
                {
                    "game_id": game_w1,
                    "season": 2026,
                    "week": 1,
                    "game_type": "REG",
                    "team": "GB",
                    "pfr_player_id": "SmitJo01",
                    "position": "TE",
                    "offense_snaps": 32,
                },
                {
                    # Active week 2 with no box-score row.
                    "game_id": game_w2,
                    "season": 2026,
                    "week": 2,
                    "game_type": "REG",
                    "team": "GB",
                    "pfr_player_id": "SmitJo01",
                    "position": "TE",
                    "offense_snaps": 13,
                },
                {
                    # Inactive: no offensive snaps → omitted.
                    "game_id": game_w2,
                    "season": 2026,
                    "week": 2,
                    "game_type": "REG",
                    "team": "GB",
                    "pfr_player_id": "Inact01",
                    "position": "TE",
                    "offense_snaps": 0,
                },
            ]
        )

        with (
            patch(
                "app.canonical.fact_player_game.upsert_fact_player_game"
            ),
            patch(
                "app.canonical.fact_player_game.get_dim_player",
            ),
        ):
            fact = build_fact_player_game(
                [2026],
                persist=True,
                source_frames={
                    "player_stats": stats,
                    "snap_counts": snaps,
                    "pfr_to_gsis": {
                        "SmitJo01": scored_gsis,
                        "Inact01": inactive_gsis,
                    },
                },
                player_id_lookup={
                    scored_gsis: player_id,
                    inactive_gsis: inactive_player_id,
                },
                game_id_lookup={
                    game_w1: game1,
                    game_w2: game2,
                },
            )

        self.assertEqual(len(fact), 2)
        weeks = sorted(int(v) for v in fact["week"].tolist())
        self.assertEqual(weeks, [1, 2])
        week2 = fact[fact["week"] == 2].iloc[0]
        self.assertEqual(int(week2["targets"] or 0), 0)
        self.assertEqual(int(week2["receptions"] or 0), 0)
        self.assertEqual(int(week2["receiving_yards"] or 0), 0)
        source_ids = json.loads(week2["source_ids"])
        self.assertEqual(
            source_ids.get("participation"),
            "snap_counts",
        )
        # Inactive player never appears.
        self.assertFalse(
            (fact["player_id"] == inactive_player_id).any()
        )


if __name__ == "__main__":
    unittest.main()
