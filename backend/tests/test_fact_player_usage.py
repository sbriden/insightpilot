"""Tests for canonical fact_player_usage."""

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
from app.canonical.fact_player_usage import (
    build_fact_player_usage,
)


class FactPlayerUsageTests(unittest.TestCase):

    def test_build_fact_player_usage_position_aware(self):
        rb_gsis = "00-0030001"
        wr_gsis = "00-0030002"
        qb_gsis = "00-0030003"
        game = "2024_01_KC_BAL"

        player_lookup = {
            rb_gsis: make_player_id(
                player_resolution_key(gsis_id=rb_gsis)
            ),
            wr_gsis: make_player_id(
                player_resolution_key(gsis_id=wr_gsis)
            ),
            qb_gsis: make_player_id(
                player_resolution_key(gsis_id=qb_gsis)
            ),
        }
        game_id = make_game_id(
            game_resolution_key(nflverse_game_id=game)
        )
        game_lookup = {game: game_id}

        stats = pd.DataFrame(
            [
                {
                    "player_id": rb_gsis,
                    "game_id": game,
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "team": "KC",
                    "position": "RB",
                    "carries": 12,
                    "receptions": 3,
                    "targets": 4,
                    "target_share": 0.12,
                    "receiving_air_yards": 15,
                    "air_yards_share": 0.08,
                },
                {
                    "player_id": wr_gsis,
                    "game_id": game,
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "team": "KC",
                    "position": "WR",
                    "carries": 0,
                    "receptions": 5,
                    "targets": 8,
                    "target_share": 0.25,
                    "receiving_air_yards": 90,
                    "air_yards_share": 0.35,
                },
                {
                    "player_id": qb_gsis,
                    "game_id": game,
                    "season": 2024,
                    "week": 1,
                    "season_type": "REG",
                    "team": "KC",
                    "position": "QB",
                    "carries": 4,
                    "receptions": 0,
                    "targets": 0,
                    "target_share": 0.0,
                    "receiving_air_yards": 0,
                    "air_yards_share": 0.0,
                },
            ]
        )

        snaps = pd.DataFrame(
            [
                {
                    "game_id": game,
                    "pfr_player_id": "RBxx00",
                    "offense_snaps": 45,
                    "offense_pct": 0.7,
                },
                {
                    "game_id": game,
                    "pfr_player_id": "WRxx00",
                    "offense_snaps": 55,
                    "offense_pct": 0.85,
                },
                {
                    "game_id": game,
                    "pfr_player_id": "QBxx00",
                    "offense_snaps": 65,
                    "offense_pct": 1.0,
                },
            ]
        )

        pbp = pd.DataFrame(
            [
                # RB rush inside 5
                {
                    "game_id": game,
                    "play_id": 1,
                    "posteam": "KC",
                    "rush_attempt": 1,
                    "pass_attempt": 0,
                    "qb_dropback": 0,
                    "qb_scramble": 0,
                    "pass": 0,
                    "rusher_player_id": rb_gsis,
                    "receiver_player_id": None,
                    "passer_player_id": None,
                    "yardline_100": 3,
                    "air_yards": None,
                    "complete_pass": 0,
                },
                # WR end-zone target
                {
                    "game_id": game,
                    "play_id": 2,
                    "posteam": "KC",
                    "rush_attempt": 0,
                    "pass_attempt": 1,
                    "qb_dropback": 1,
                    "qb_scramble": 0,
                    "pass": 1,
                    "rusher_player_id": None,
                    "receiver_player_id": wr_gsis,
                    "passer_player_id": qb_gsis,
                    "yardline_100": 8,
                    "air_yards": 12,
                    "complete_pass": 1,
                },
                # QB scramble
                {
                    "game_id": game,
                    "play_id": 3,
                    "posteam": "KC",
                    "rush_attempt": 1,
                    "pass_attempt": 0,
                    "qb_dropback": 1,
                    "qb_scramble": 1,
                    "pass": 0,
                    "rusher_player_id": qb_gsis,
                    "receiver_player_id": None,
                    "passer_player_id": qb_gsis,
                    "yardline_100": 40,
                    "air_yards": None,
                    "complete_pass": 0,
                },
                # QB designed rush
                {
                    "game_id": game,
                    "play_id": 4,
                    "posteam": "KC",
                    "rush_attempt": 1,
                    "pass_attempt": 0,
                    "qb_dropback": 0,
                    "qb_scramble": 0,
                    "pass": 0,
                    "rusher_player_id": qb_gsis,
                    "receiver_player_id": None,
                    "passer_player_id": None,
                    "yardline_100": 1,
                    "air_yards": None,
                    "complete_pass": 0,
                },
                # Deep pass
                {
                    "game_id": game,
                    "play_id": 5,
                    "posteam": "KC",
                    "rush_attempt": 0,
                    "pass_attempt": 1,
                    "qb_dropback": 1,
                    "qb_scramble": 0,
                    "pass": 1,
                    "rusher_player_id": None,
                    "receiver_player_id": wr_gsis,
                    "passer_player_id": qb_gsis,
                    "yardline_100": 55,
                    "air_yards": 28,
                    "complete_pass": 0,
                },
            ]
        )

        participation = pd.DataFrame(
            [
                {
                    "nflverse_game_id": game,
                    "play_id": 2,
                    "offense_players": f"{qb_gsis};{wr_gsis};{rb_gsis}",
                },
                {
                    "nflverse_game_id": game,
                    "play_id": 5,
                    "offense_players": f"{qb_gsis};{wr_gsis}",
                },
            ]
        )

        with (
            patch(
                "app.canonical.fact_player_usage.upsert_fact_player_usage"
            ),
            patch(
                "app.canonical.fact_player_usage._pfr_to_gsis_lookup",
                return_value={
                    "RBxx00": rb_gsis,
                    "WRxx00": wr_gsis,
                    "QBxx00": qb_gsis,
                },
            ),
        ):
            fact = build_fact_player_usage(
                [2024],
                persist=True,
                source_frames={
                    "player_stats": stats,
                    "snap_counts": snaps,
                    "pbp": pbp,
                    "participation": participation,
                },
                player_id_lookup=player_lookup,
                game_id_lookup=game_lookup,
            )

        self.assertEqual(len(fact), 3)

        rb = fact[fact["position"] == "RB"].iloc[0]
        self.assertTrue(is_player_id(rb["player_id"]))
        self.assertTrue(is_game_id(rb["game_id"]))
        self.assertEqual(rb["snap_count"], 45)
        self.assertAlmostEqual(rb["offensive_snap_share"], 0.7)
        self.assertEqual(rb["touches"], 15)
        self.assertEqual(rb["inside_5_carries"], 1)
        self.assertEqual(rb["goal_line_carries"], 1)
        self.assertIsNotNone(rb["rush_share"])
        self.assertIsNotNone(rb["routes_run"])

        wr = fact[fact["position"] == "WR"].iloc[0]
        self.assertEqual(wr["air_yards"], 90)
        self.assertAlmostEqual(wr["target_share"], 0.25)
        self.assertEqual(wr["end_zone_targets"], 1)
        self.assertEqual(wr["red_zone_targets"], 1)
        # WR should not require QB metrics
        self.assertTrue(
            wr["dropbacks"] is None or wr["dropbacks"] == 0
        )

        qb = fact[fact["position"] == "QB"].iloc[0]
        self.assertEqual(qb["dropbacks"], 3)
        self.assertEqual(qb["scrambles"], 1)
        self.assertEqual(qb["designed_rush_attempts"], 1)
        self.assertEqual(qb["deep_pass_attempts"], 1)
        self.assertIsNotNone(qb["qb_rush_share"])

        source_ids = json.loads(rb["source_ids"])
        self.assertEqual(source_ids["gsis_id"], rb_gsis)
        self.assertEqual(source_ids["nflverse_game_id"], game)


if __name__ == "__main__":
    unittest.main()
