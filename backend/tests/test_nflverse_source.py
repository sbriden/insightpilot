"""Unit tests for nflverse fantasy foundation helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from app.sources import nflverse as nflverse_source
from app.sources.fantasy import player_fundamentals as pf


class NflverseSourceTests(unittest.TestCase):

    def test_catalog_includes_dim_player(self):
        datasets = nflverse_source.list_datasets()
        ids = {item["id"] for item in datasets}
        self.assertIn("dim_team", ids)
        self.assertIn("dim_player", ids)
        self.assertIn("dim_game", ids)
        self.assertIn("fact_player_game", ids)
        self.assertIn("fact_player_usage", ids)
        self.assertIn("fact_player_efficiency", ids)
        self.assertIn("fact_team_game", ids)
        self.assertIn("fact_defensive_game", ids)
        self.assertIn("fact_injury", ids)
        self.assertIn("fact_depth_chart", ids)
        self.assertIn("fact_market", ids)
        self.assertIn("fact_game_market", ids)
        self.assertIn("player_usage_trend", ids)
        self.assertIn("player_opportunity", ids)
        self.assertIn("player_efficiency", ids)
        self.assertIn("player_matchup", ids)
        self.assertIn("player_environment", ids)
        self.assertIn("player_fantasy_profile", ids)
        self.assertIn("fantasy_signal", ids)
        self.assertIn("player_fundamentals", ids)
        dim = next(
            item for item in datasets if item["id"] == "dim_player"
        )
        self.assertEqual(dim["domain"], "canonical")
        analytics = next(
            item
            for item in datasets
            if item["id"] == "player_usage_trend"
        )
        self.assertEqual(analytics["domain"], "analytics")
        self.assertIn(
            "Fantasy intelligence",
            analytics["domain_label"],
        )
        profile = next(
            item
            for item in datasets
            if item["id"] == "player_fantasy_profile"
        )
        self.assertEqual(profile["domain"], "intelligence")
        self.assertIn(
            "Proprietary",
            profile["domain_label"],
        )

    def test_get_dataset_definition_unknown(self):
        with self.assertRaises(ValueError):
            nflverse_source.get_dataset_definition("pbp")

    @patch(
        "app.sources.nflverse.get_current_season",
        return_value=2024,
    )
    def test_normalize_seasons_default(
        self,
        _mock_season,
    ):
        dataset = nflverse_source.get_dataset_definition(
            "player_fundamentals"
        )
        seasons = nflverse_source.normalize_seasons(
            None,
            dataset=dataset,
        )
        self.assertEqual(
            seasons,
            [2021, 2022, 2023, 2024],
        )

    def test_dataframe_fields(self):
        df = pd.DataFrame(
            {
                "player_id": ["00-0036322"],
                "player_name": ["Ja'Marr Chase"],
            }
        )
        fields = nflverse_source.dataframe_fields(df)
        self.assertEqual(
            [field["name"] for field in fields],
            ["player_id", "player_name"],
        )

    def test_source_label(self):
        dataset = nflverse_source.get_dataset_definition(
            "player_fundamentals"
        )
        label = nflverse_source.source_label(
            dataset,
            [2024],
        )
        self.assertEqual(
            label,
            "nflverse - Player fundamentals (2024)",
        )


class PlayerFundamentalsTests(unittest.TestCase):

    def test_build_joins_on_gsis_and_exposes_player_id(self):
        rosters = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "week": 18,
                    "gsis_id": "00-0036322",
                    "full_name": "Ja'Marr Chase",
                    "first_name": "Ja'Marr",
                    "last_name": "Chase",
                    "football_name": "Ja'Marr",
                    "team": "CIN",
                    "position": "WR",
                    "depth_chart_position": "WR",
                    "status": "ACT",
                    "years_exp": 3,
                    "height": "72",
                    "weight": 201,
                    "birth_date": "2000-03-01",
                    "rookie_year": 2021,
                    "entry_year": 2021,
                    "college": "LSU",
                    "jersey_number": 1,
                    "headshot_url": None,
                },
                {
                    "season": 2023,
                    "week": 18,
                    "gsis_id": "00-0036322",
                    "full_name": "Ja'Marr Chase",
                    "first_name": "Ja'Marr",
                    "last_name": "Chase",
                    "football_name": "Ja'Marr",
                    "team": "CIN",
                    "position": "WR",
                    "depth_chart_position": "WR",
                    "status": "ACT",
                    "years_exp": 2,
                    "height": "72",
                    "weight": 201,
                    "birth_date": "2000-03-01",
                    "rookie_year": 2021,
                    "entry_year": 2021,
                    "college": "LSU",
                    "jersey_number": 1,
                    "headshot_url": None,
                },
            ]
        )
        players = pd.DataFrame(
            [
                {
                    "gsis_id": "00-0036322",
                    "display_name": "Ja'Marr Chase",
                    "latest_team": "CIN",
                    "years_of_experience": 3,
                    "status": "ACT",
                    "rookie_season": 2021,
                    "height": "72",
                    "weight": 201,
                    "birth_date": "2000-03-01",
                    "position": "WR",
                }
            ]
        )
        depth = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "week": 18,
                    "gsis_id": "00-0036322",
                    "depth_position": "LWR",
                    "depth_team": 1,
                    "formation": "Offense",
                    "club_code": "CIN",
                }
            ]
        )
        injuries = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "week": 10,
                    "gsis_id": "00-0036322",
                    "report_status": "Questionable",
                    "report_primary_injury": "Shoulder",
                }
            ]
        )
        ff_ids = pd.DataFrame(
            [
                {
                    "gsis_id": "00-0036322",
                    "sleeper_id": "4983",
                    "espn_id": "4362628",
                    "yahoo_id": "33399",
                    "fantasypros_id": "19216",
                    "mfl_id": "15612",
                    "rotowire_id": "14880",
                    "pfr_id": "ChasJa00",
                }
            ]
        )

        with patch.object(
            pf,
            "_load_raw_frames",
            return_value={
                "rosters": rosters,
                "players": players,
                "depth_charts": depth,
                "injuries": injuries,
                "ff_playerids": ff_ids,
            },
        ), patch(
            "nflreadpy.get_current_season",
            return_value=2024,
        ):
            result = pf.build_player_fundamentals(
                [2024],
                current_season=2024,
                history_seasons=[2023, 2024],
                player_id_lookup={
                    "00-0036322": "ip_player_00004242",
                },
                persist_dim_player=False,
            )

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["player_id"], "ip_player_00004242")
        self.assertEqual(row["gsis_id"], "00-0036322")
        self.assertEqual(row["player_name"], "Ja'Marr Chase")
        self.assertEqual(row["team"], "CIN")
        self.assertEqual(row["depth_chart_position"], "LWR")
        self.assertEqual(row["active_status"], "active")
        self.assertEqual(row["injury_status"], "Questionable")
        self.assertEqual(row["sleeper_id"], "4983")
        self.assertEqual(row["rookie_veteran_status"], "veteran")
        self.assertIn("CIN", str(row["career_teams"]))
        self.assertIn("2023:CIN", str(row["team_season_history"]))


if __name__ == "__main__":
    unittest.main()
