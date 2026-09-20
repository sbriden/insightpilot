"""Tests for canonical fact_depth_chart."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    is_player_id,
    is_team_id,
    make_player_id,
    make_team_id,
    player_resolution_key,
)
from app.canonical.fact_depth_chart import (
    build_fact_depth_chart,
)


class FactDepthChartTests(unittest.TestCase):

    def test_build_fact_depth_chart_roles(self):
        gsis_starter = "00-0038001"
        gsis_backup = "00-0038002"
        gsis_returner = "00-0038003"
        gsis_slot = "00-0038004"

        player_lookup = {
            gsis: make_player_id(
                player_resolution_key(gsis_id=gsis)
            )
            for gsis in (
                gsis_starter,
                gsis_backup,
                gsis_returner,
                gsis_slot,
            )
        }

        depth_charts = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "club_code": "ATL",
                    "week": 1,
                    "game_type": "REG",
                    "depth_team": "1",
                    "gsis_id": gsis_starter,
                    "position": "WR",
                    "depth_position": "WR",
                    "formation": "Offense",
                },
                {
                    "season": 2024,
                    "club_code": "ATL",
                    "week": 1,
                    "game_type": "REG",
                    "depth_team": "2",
                    "gsis_id": gsis_backup,
                    "position": "WR",
                    "depth_position": "WR",
                    "formation": "Offense",
                },
                {
                    "season": 2024,
                    "club_code": "ATL",
                    "week": 1,
                    "game_type": "REG",
                    "depth_team": "1",
                    "gsis_id": gsis_returner,
                    "position": "WR",
                    "depth_position": "KR",
                    "formation": "Special Teams",
                },
                {
                    "season": 2024,
                    "club_code": "ATL",
                    "week": 1,
                    "game_type": "REG",
                    "depth_team": "1",
                    "gsis_id": gsis_slot,
                    "position": "CB",
                    "depth_position": "NCB",
                    "formation": "Defense",
                },
            ]
        )

        schedules = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "week": 1,
                    "home_team": "ATL",
                    "away_team": "PIT",
                    "gameday": "2024-09-08",
                }
            ]
        )

        with patch(
            "app.canonical.fact_depth_chart.upsert_fact_depth_chart"
        ):
            fact = build_fact_depth_chart(
                [2024],
                persist=True,
                source_frames={
                    "depth_charts": depth_charts,
                    "schedules": schedules,
                },
                player_id_lookup=player_lookup,
            )

        self.assertEqual(len(fact), 4)

        starter = fact[
            fact["player_id"] == player_lookup[gsis_starter]
        ].iloc[0]
        self.assertTrue(is_player_id(starter["player_id"]))
        self.assertEqual(
            starter["team_id"],
            make_team_id("ATL"),
        )
        self.assertTrue(is_team_id(starter["team_id"]))
        self.assertEqual(starter["position"], "WR")
        self.assertEqual(starter["depth_order"], 1)
        self.assertEqual(starter["role"], "starter")
        self.assertEqual(
            starter["effective_date"],
            "2024-09-08",
        )

        backup = fact[
            fact["player_id"] == player_lookup[gsis_backup]
        ].iloc[0]
        self.assertEqual(backup["depth_order"], 2)
        self.assertEqual(backup["role"], "backup")

        returner = fact[
            fact["player_id"] == player_lookup[gsis_returner]
        ].iloc[0]
        self.assertEqual(returner["role"], "returner")

        slot = fact[
            fact["player_id"] == player_lookup[gsis_slot]
        ].iloc[0]
        self.assertEqual(slot["role"], "slot")

        source_ids = json.loads(starter["source_ids"])
        self.assertEqual(source_ids["gsis_id"], gsis_starter)
        self.assertEqual(source_ids["formation"], "Offense")

    def test_build_fact_depth_chart_snapshot_schema(self):
        gsis_starter = "00-0039001"
        gsis_backup = "00-0039002"
        player_lookup = {
            gsis: make_player_id(
                player_resolution_key(gsis_id=gsis)
            )
            for gsis in (gsis_starter, gsis_backup)
        }

        depth_charts = pd.DataFrame(
            [
                {
                    "dt": "2026-09-16T12:00:00Z",
                    "team": "MIN",
                    "player_name": "Starter",
                    "gsis_id": gsis_starter,
                    "pos_grp": "3WR 1TE",
                    "pos_abb": "QB",
                    "pos_rank": 1,
                },
                {
                    "dt": "2026-09-16T12:00:00Z",
                    "team": "MIN",
                    "player_name": "Backup",
                    "gsis_id": gsis_backup,
                    "pos_grp": "3WR 1TE",
                    "pos_abb": "QB",
                    "pos_rank": 2,
                },
                {
                    # Older snapshot should be ignored.
                    "dt": "2026-09-01T12:00:00Z",
                    "team": "MIN",
                    "player_name": "Old",
                    "gsis_id": gsis_backup,
                    "pos_grp": "3WR 1TE",
                    "pos_abb": "QB",
                    "pos_rank": 1,
                },
            ]
        )
        schedules = pd.DataFrame(
            [
                {
                    "season": 2026,
                    "week": 1,
                    "home_team": "MIN",
                    "away_team": "CHI",
                    "gameday": "2026-09-14",
                }
            ]
        )

        with patch(
            "app.canonical.fact_depth_chart.upsert_fact_depth_chart"
        ):
            fact = build_fact_depth_chart(
                [2026],
                persist=True,
                source_frames={
                    "depth_charts": depth_charts,
                    "schedules": schedules,
                },
                player_id_lookup=player_lookup,
            )

        self.assertEqual(len(fact), 2)
        starter = fact[
            fact["player_id"] == player_lookup[gsis_starter]
        ].iloc[0]
        self.assertEqual(starter["season"], 2026)
        self.assertEqual(starter["week"], 1)
        self.assertEqual(starter["position"], "QB")
        self.assertEqual(starter["depth_order"], 1)
        self.assertEqual(starter["role"], "starter")
        self.assertEqual(starter["effective_date"], "2026-09-16")


if __name__ == "__main__":
    unittest.main()
