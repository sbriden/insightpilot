"""Tests for canonical dim_player and InsightPilot IDs."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    is_player_id,
    make_player_id,
    make_team_id,
    player_resolution_key,
)
from app.canonical.dim_player import (
    build_dim_player,
    player_id_lookup_from_dim,
)
from app.canonical.dim_team import (
    normalize_team_abbreviation,
    resolve_team_id,
)


class CanonicalIdTests(unittest.TestCase):

    def test_player_id_format_and_stability(self):
        first = make_player_id("gsis:00-0036900")
        second = make_player_id("gsis:00-0036900")
        self.assertEqual(first, second)
        self.assertTrue(is_player_id(first))
        self.assertTrue(first.startswith("ip_player_"))
        self.assertNotEqual(first, "00-0036900")

    def test_resolution_key_prefers_gsis(self):
        key = player_resolution_key(
            gsis_id="00-0036900",
            pfr_id="ChasJa00",
        )
        self.assertEqual(key, "gsis:00-0036900")

    def test_team_id_is_insightpilot_owned(self):
        team_id = make_team_id("CIN")
        self.assertTrue(team_id.startswith("ip_team_"))
        self.assertEqual(team_id, make_team_id("cin"))


class DimPlayerTests(unittest.TestCase):

    def test_normalize_team_abbreviation_aliases_and_non_teams(self):
        self.assertEqual(
            normalize_team_abbreviation("oak"),
            "LV",
        )
        self.assertEqual(
            normalize_team_abbreviation("LAR"),
            "LA",
        )
        self.assertIsNone(
            normalize_team_abbreviation("FA")
        )
        self.assertIsNone(
            resolve_team_id(
                "FA",
                team_id_lookup={"CIN": make_team_id("CIN")},
            )
        )
        self.assertEqual(
            resolve_team_id(
                "CIN",
                team_id_lookup={"CIN": make_team_id("CIN")},
            ),
            make_team_id("CIN"),
        )

    def test_build_dim_player_uses_ip_ids_and_source_ids(self):
        players = pd.DataFrame(
            [
                {
                    "gsis_id": "00-0036900",
                    "display_name": "Ja'Marr Chase",
                    "first_name": "Ja'Marr",
                    "last_name": "Chase",
                    "position": "WR",
                    "birth_date": "2000-03-01",
                    "rookie_season": 2021,
                    "latest_team": "CIN",
                    "status": "ACT",
                    "nfl_id": "38582",
                    "pfr_id": "ChasJa00",
                },
                {
                    "gsis_id": "00-0039999",
                    "display_name": "Free Agent",
                    "first_name": "Free",
                    "last_name": "Agent",
                    "position": "WR",
                    "birth_date": "1995-01-01",
                    "rookie_season": 2018,
                    "latest_team": "FA",
                    "status": "ACT",
                    "nfl_id": "99999",
                    "pfr_id": "FreeAg00",
                },
            ]
        )
        ff_ids = pd.DataFrame(
            [
                {
                    "gsis_id": "00-0036900",
                    "fantasypros_id": "19216",
                    "sleeper_id": "7564",
                    "espn_id": "4362628",
                    "pfr_id": "ChasJa00",
                    "name": "Ja'Marr Chase",
                    "position": "WR",
                    "team": "CIN",
                    "birthdate": "2000-03-01",
                    "draft_year": 2021,
                }
            ]
        )
        rosters = pd.DataFrame(
            [
                {
                    "gsis_id": "00-0036900",
                    "team": "CIN",
                    "status": "ACT",
                    "full_name": "Ja'Marr Chase",
                    "first_name": "Ja'Marr",
                    "last_name": "Chase",
                    "position": "WR",
                    "birth_date": "2000-03-01",
                    "rookie_year": 2021,
                    "week": 18,
                }
            ]
        )
        teams = pd.DataFrame(
            [
                {
                    "team_id": make_team_id("CIN"),
                    "team_name": "Cincinnati Bengals",
                    "team_abbreviation": "CIN",
                    "conference": "AFC",
                    "division": "AFC North",
                    "stadium": None,
                    "source_ids": "{}",
                }
            ]
        )

        with patch(
            "app.canonical.dim_player.upsert_dim_player"
        ), patch(
            "app.canonical.dim_team.get_dim_team",
            return_value=teams,
        ):
            dim = build_dim_player(
                persist=True,
                source_frames={
                    "players": players,
                    "ff_playerids": ff_ids,
                    "rosters": rosters,
                },
            )

        self.assertEqual(len(dim), 2)
        chase = dim[
            dim["name"] == "Ja'Marr Chase"
        ].iloc[0]
        free_agent = dim[
            dim["name"] == "Free Agent"
        ].iloc[0]
        self.assertTrue(is_player_id(chase["player_id"]))
        self.assertEqual(chase["position"], "WR")
        self.assertEqual(chase["status"], "Active")
        self.assertEqual(
            chase["current_team_id"],
            make_team_id("CIN"),
        )
        self.assertIsNone(free_agent["current_team_id"])

        source_ids = json.loads(chase["source_ids"])
        self.assertEqual(source_ids["gsis_id"], "00-0036900")
        self.assertEqual(source_ids["nflverse_id"], "38582")
        self.assertEqual(source_ids["pfr_id"], "ChasJa00")
        self.assertEqual(source_ids["fantasypros_id"], "19216")
        self.assertNotIn("player_id", source_ids)

        lookup = player_id_lookup_from_dim(dim)
        self.assertEqual(
            lookup["00-0036900"],
            chase["player_id"],
        )


if __name__ == "__main__":
    unittest.main()
