"""Tests for canonical fact_injury."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    game_resolution_key,
    is_game_id,
    is_player_id,
    is_team_id,
    make_game_id,
    make_player_id,
    make_team_id,
    player_resolution_key,
)
from app.canonical.fact_injury import (
    build_fact_injury,
)


class FactInjuryTests(unittest.TestCase):

    def test_build_fact_injury(self):
        gsis_out = "00-0039001"
        gsis_q = "00-0039002"
        gsis_full = "00-0039003"
        game = "2024_01_ARI_BUF"
        game_id = make_game_id(
            game_resolution_key(nflverse_game_id=game)
        )

        player_lookup = {
            gsis_out: make_player_id(
                player_resolution_key(gsis_id=gsis_out)
            ),
            gsis_q: make_player_id(
                player_resolution_key(gsis_id=gsis_q)
            ),
            gsis_full: make_player_id(
                player_resolution_key(gsis_id=gsis_full)
            ),
        }

        injuries = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "game_type": "REG",
                    "team": "ARI",
                    "week": 1,
                    "gsis_id": gsis_out,
                    "report_primary_injury": "Oblique",
                    "report_secondary_injury": None,
                    "report_status": "Out",
                    "practice_primary_injury": "Oblique",
                    "practice_secondary_injury": None,
                    "practice_status": "Did Not Participate In Practice",
                    "date_modified": "2024-09-06T19:05:30Z",
                },
                {
                    "season": 2024,
                    "game_type": "REG",
                    "team": "ARI",
                    "week": 1,
                    "gsis_id": gsis_q,
                    "report_primary_injury": "Back",
                    "report_secondary_injury": "Ankle",
                    "report_status": "Questionable",
                    "practice_primary_injury": "Back",
                    "practice_secondary_injury": None,
                    "practice_status": "Limited Participation in Practice",
                    "date_modified": "2024-09-06T19:05:21Z",
                },
                {
                    "season": 2024,
                    "game_type": "REG",
                    "team": "ARI",
                    "week": 1,
                    "gsis_id": gsis_full,
                    "report_primary_injury": None,
                    "report_secondary_injury": None,
                    "report_status": None,
                    "practice_primary_injury": "Knee",
                    "practice_secondary_injury": None,
                    "practice_status": "Full Participation in Practice",
                    "date_modified": "2024-09-06T18:00:00Z",
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
                    "home_team": "BUF",
                    "away_team": "ARI",
                }
            ]
        )

        with patch(
            "app.canonical.fact_injury.upsert_fact_injury"
        ):
            fact = build_fact_injury(
                [2024],
                persist=True,
                source_frames={
                    "injuries": injuries,
                    "schedules": schedules,
                },
                player_id_lookup=player_lookup,
                game_id_lookup={game: game_id},
            )

        self.assertEqual(len(fact), 3)

        out_row = fact[
            fact["player_id"] == player_lookup[gsis_out]
        ].iloc[0]
        self.assertTrue(is_player_id(out_row["player_id"]))
        self.assertEqual(
            out_row["team_id"],
            make_team_id("ARI"),
        )
        self.assertTrue(is_team_id(out_row["team_id"]))
        self.assertEqual(out_row["report_date"], "2024-09-06")
        self.assertTrue(is_game_id(out_row["game_id"]))
        self.assertEqual(out_row["game_id"], game_id)
        self.assertEqual(out_row["injury_type"], "Oblique")
        self.assertEqual(out_row["game_status"], "Out")
        self.assertFalse(out_row["is_expected_to_play"])

        q_row = fact[
            fact["player_id"] == player_lookup[gsis_q]
        ].iloc[0]
        self.assertEqual(
            q_row["injury_type"],
            "Back; Ankle",
        )
        self.assertEqual(q_row["game_status"], "Questionable")
        self.assertIsNone(q_row["is_expected_to_play"])

        full_row = fact[
            fact["player_id"] == player_lookup[gsis_full]
        ].iloc[0]
        self.assertEqual(full_row["injury_type"], "Knee")
        self.assertTrue(full_row["is_expected_to_play"])

        source_ids = json.loads(out_row["source_ids"])
        self.assertEqual(source_ids["gsis_id"], gsis_out)
        self.assertEqual(
            source_ids["nflverse_game_id"],
            game,
        )


if __name__ == "__main__":
    unittest.main()
