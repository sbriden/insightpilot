"""Tests for canonical dim_team."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.dim_team import (
    build_dim_team,
    normalize_team_abbreviation,
)
from app.canonical.ids import (
    is_team_id,
    make_team_id,
)


class DimTeamTests(unittest.TestCase):

    def test_team_id_is_insightpilot_owned(self):
        team_id = make_team_id("CIN")
        self.assertTrue(is_team_id(team_id))
        self.assertEqual(team_id, make_team_id("cin"))
        self.assertNotEqual(team_id, "CIN")

    def test_historical_aliases_share_team_id(self):
        self.assertEqual(
            normalize_team_abbreviation("OAK"),
            "LV",
        )
        self.assertEqual(make_team_id("OAK"), make_team_id("LV"))
        self.assertEqual(make_team_id("SD"), make_team_id("LAC"))

    def test_build_dim_team_collapses_oakland_to_lv(self):
        teams = pd.DataFrame(
            [
                {
                    "team_abbr": "OAK",
                    "team_name": "Oakland Raiders",
                    "team_id": "2520",
                    "team_conf": "AFC",
                    "team_division": "AFC West",
                },
                {
                    "team_abbr": "LV",
                    "team_name": "Las Vegas Raiders",
                    "team_id": "2520",
                    "team_conf": "AFC",
                    "team_division": "AFC West",
                },
            ]
        )
        with patch("app.canonical.dim_team.upsert_dim_team"):
            dim = build_dim_team(
                persist=True,
                source_frames={
                    "teams": teams,
                    "schedules": pd.DataFrame(),
                },
            )
        self.assertEqual(len(dim), 1)
        self.assertEqual(dim.iloc[0]["team_abbreviation"], "LV")
        self.assertEqual(
            dim.iloc[0]["team_name"],
            "Las Vegas Raiders",
        )
        self.assertEqual(
            dim.iloc[0]["team_id"],
            make_team_id("LV"),
        )

    def test_build_dim_team(self):
        teams = pd.DataFrame(
            [
                {
                    "team_abbr": "CIN",
                    "team_name": "Cincinnati Bengals",
                    "team_id": "3230",
                    "team_conf": "AFC",
                    "team_division": "AFC North",
                },
                {
                    "team_abbr": "KC",
                    "team_name": "Kansas City Chiefs",
                    "team_id": "2310",
                    "team_conf": "AFC",
                    "team_division": "AFC West",
                },
            ]
        )
        schedules = pd.DataFrame(
            [
                {
                    "home_team": "CIN",
                    "stadium": "Paycor Stadium",
                    "week": 10,
                },
                {
                    "home_team": "KC",
                    "stadium": "GEHA Field at Arrowhead Stadium",
                    "week": 10,
                },
            ]
        )

        with patch(
            "app.canonical.dim_team.upsert_dim_team"
        ):
            dim = build_dim_team(
                persist=True,
                source_frames={
                    "teams": teams,
                    "schedules": schedules,
                },
            )

        self.assertEqual(len(dim), 2)
        cin = dim[dim["team_abbreviation"] == "CIN"].iloc[0]
        self.assertTrue(is_team_id(cin["team_id"]))
        self.assertEqual(
            cin["team_name"],
            "Cincinnati Bengals",
        )
        self.assertEqual(cin["conference"], "AFC")
        self.assertEqual(cin["division"], "AFC North")
        self.assertEqual(cin["stadium"], "Paycor Stadium")
        source_ids = json.loads(cin["source_ids"])
        self.assertEqual(
            source_ids["nflverse_team_id"],
            "3230",
        )


if __name__ == "__main__":
    unittest.main()
