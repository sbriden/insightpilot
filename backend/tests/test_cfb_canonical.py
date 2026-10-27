"""Unit tests for college_football canonical builders."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.cfb import dim_game
from app.canonical.cfb import dim_player
from app.canonical.cfb import dim_team
from app.canonical.cfb import fact_defensive_game
from app.canonical.cfb import fact_game_market
from app.canonical.cfb import fact_player_game
from app.canonical.cfb import fact_team_game
from app.canonical.cfb.ids import (
    cfb_game_resolution_key,
    cfb_player_resolution_key,
    cfb_team_resolution_key,
    mint_cfb_game_id,
    mint_cfb_player_id,
    mint_cfb_team_id,
)


class CfbIdTests(unittest.TestCase):

    def test_team_resolution_prefers_espn_id(self):
        key = cfb_team_resolution_key(
            espn_team_id="333",
            team_abbreviation="ALA",
        )
        self.assertEqual(key, "cfb_espn_team:333")
        team_id = mint_cfb_team_id(resolution_key=key)
        self.assertTrue(team_id.startswith("ip_team_"))

    def test_player_and_game_keys(self):
        player_key = cfb_player_resolution_key(
            athlete_id="4429013",
        )
        game_key = cfb_game_resolution_key(game_id="401628345")
        self.assertEqual(player_key, "cfb_athlete:4429013")
        self.assertEqual(game_key, "cfb_game:401628345")
        self.assertTrue(
            mint_cfb_player_id(
                resolution_key=player_key,
            ).startswith("ip_player_")
        )
        self.assertTrue(
            mint_cfb_game_id(
                resolution_key=game_key,
            ).startswith("ip_game_")
        )


class CfbDimBuilderTests(unittest.TestCase):

    def setUp(self):
        dim_team.clear_dim_team_cache()
        dim_player.clear_dim_player_cache()
        dim_game.clear_dim_game_cache()

    def test_build_dim_team_from_source_frames(self):
        teams = pd.DataFrame(
            [
                {
                    "team_id": "333",
                    "school": "Alabama",
                    "abbreviation": "ALA",
                    "conference": "SEC",
                    "classification": "fbs",
                    "venue": "Bryant-Denny Stadium",
                },
                {
                    "team_id": "61",
                    "school": "Georgia",
                    "abbreviation": "UGA",
                    "conference": "SEC",
                    "classification": "fbs",
                    "venue": "Sanford Stadium",
                },
            ]
        )
        with patch.object(
            dim_team,
            "upsert_dim_team",
        ) as upsert:
            frame = dim_team.build_dim_team(
                persist=True,
                source_frames={"team_info": teams},
            )
            upsert.assert_called_once()

        self.assertEqual(len(frame), 2)
        self.assertIn("team_id", frame.columns)
        self.assertTrue(
            all(
                str(value).startswith("ip_team_")
                for value in frame["team_id"]
            )
        )
        source = json.loads(frame.iloc[0]["source_ids"])
        self.assertIn("espn_team_id", source)

    def test_build_dim_player_joins_team(self):
        dim_team.build_dim_team(
            persist=False,
            source_frames={
                "team_info": pd.DataFrame(
                    [
                        {
                            "team_id": "333",
                            "school": "Alabama",
                            "abbreviation": "ALA",
                            "conference": "SEC",
                        }
                    ]
                )
            },
        )
        rosters = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "athlete_id": "4429013",
                    "full_name": "Jalen Milroe",
                    "first_name": "Jalen",
                    "last_name": "Milroe",
                    "position": "QB",
                    "team_id": "333",
                    "team_abbreviation": "ALA",
                    "class": "JR",
                }
            ]
        )
        with patch.object(dim_player, "upsert_dim_player"):
            frame = dim_player.build_dim_player(
                [2024],
                persist=True,
                source_frames={"rosters": rosters},
            )

        self.assertEqual(len(frame), 1)
        self.assertTrue(
            str(frame.iloc[0]["player_id"]).startswith(
                "ip_player_"
            )
        )
        self.assertIsNotNone(frame.iloc[0]["current_team_id"])

    def test_build_dim_game(self):
        dim_team.build_dim_team(
            persist=False,
            source_frames={
                "team_info": pd.DataFrame(
                    [
                        {
                            "team_id": "333",
                            "school": "Alabama",
                            "abbreviation": "ALA",
                        },
                        {
                            "team_id": "61",
                            "school": "Georgia",
                            "abbreviation": "UGA",
                        },
                    ]
                )
            },
        )
        schedule = pd.DataFrame(
            [
                {
                    "game_id": "401628345",
                    "season": 2024,
                    "week": 1,
                    "season_type": "regular",
                    "home_id": "333",
                    "away_id": "61",
                    "home_team": "ALA",
                    "away_team": "UGA",
                    "home_points": 24,
                    "away_points": 21,
                    "neutral_site": False,
                    "conference_game": True,
                    "start_date": "2024-08-31",
                }
            ]
        )
        with patch.object(dim_game, "upsert_dim_game"):
            frame = dim_game.build_dim_game(
                [2024],
                persist=True,
                source_frames={"schedule": schedule},
            )

        self.assertEqual(len(frame), 1)
        self.assertTrue(
            str(frame.iloc[0]["game_id"]).startswith("ip_game_")
        )
        self.assertTrue(bool(frame.iloc[0]["conference_game"]))


class CfbFactBuilderTests(unittest.TestCase):

    def setUp(self):
        dim_team.clear_dim_team_cache()
        dim_player.clear_dim_player_cache()
        dim_game.clear_dim_game_cache()
        fact_player_game.clear_fact_player_game_cache()
        fact_team_game.clear_fact_team_game_cache()
        fact_defensive_game.clear_fact_defensive_game_cache()
        fact_game_market.clear_fact_game_market_cache()

        dim_team.build_dim_team(
            persist=False,
            source_frames={
                "team_info": pd.DataFrame(
                    [
                        {
                            "team_id": "333",
                            "school": "Alabama",
                            "abbreviation": "ALA",
                        },
                        {
                            "team_id": "61",
                            "school": "Georgia",
                            "abbreviation": "UGA",
                        },
                    ]
                )
            },
        )
        dim_player.build_dim_player(
            [2024],
            persist=False,
            source_frames={
                "rosters": pd.DataFrame(
                    [
                        {
                            "season": 2024,
                            "athlete_id": "4429013",
                            "full_name": "Jalen Milroe",
                            "position": "QB",
                            "team_id": "333",
                        }
                    ]
                )
            },
        )
        dim_game.build_dim_game(
            [2024],
            persist=False,
            source_frames={
                "schedule": pd.DataFrame(
                    [
                        {
                            "game_id": "401628345",
                            "season": 2024,
                            "week": 1,
                            "home_id": "333",
                            "away_id": "61",
                            "home_team": "ALA",
                            "away_team": "UGA",
                            "home_points": 24,
                            "away_points": 21,
                        }
                    ]
                )
            },
        )

    def test_fact_player_game(self):
        box = pd.DataFrame(
            [
                {
                    "athlete_id": "4429013",
                    "game_id": "401628345",
                    "season": 2024,
                    "week": 1,
                    "team_id": "333",
                    "pass_attempts": 25,
                    "pass_completions": 18,
                    "pass_yards": 240,
                    "pass_tds": 2,
                    "interceptions": 0,
                    "rush_attempts": 8,
                    "rush_yards": 55,
                    "rush_tds": 1,
                }
            ]
        )
        with patch.object(
            fact_player_game,
            "upsert_fact_player_game",
        ):
            frame = fact_player_game.build_fact_player_game(
                [2024],
                persist=True,
                source_frames={"player_box": box},
            )
        self.assertEqual(len(frame), 1)
        self.assertEqual(int(frame.iloc[0]["pass_yards"]), 240)

    def test_fact_team_and_defensive_game(self):
        box = pd.DataFrame(
            [
                {
                    "game_id": "401628345",
                    "season": 2024,
                    "week": 1,
                    "team_id": "333",
                    "pass_attempts": 30,
                    "rush_attempts": 35,
                    "points": 24,
                    "yards": 410,
                    "turnovers": 1,
                },
                {
                    "game_id": "401628345",
                    "season": 2024,
                    "week": 1,
                    "team_id": "61",
                    "pass_attempts": 40,
                    "rush_attempts": 25,
                    "points": 21,
                    "yards": 380,
                    "turnovers": 2,
                },
            ]
        )
        with patch.object(fact_team_game, "upsert_fact_team_game"):
            offense = fact_team_game.build_fact_team_game(
                [2024],
                persist=True,
                source_frames={"team_box": box},
            )
        self.assertEqual(len(offense), 2)

        with patch.object(
            fact_defensive_game,
            "upsert_fact_defensive_game",
        ):
            defense = fact_defensive_game.build_fact_defensive_game(
                [2024],
                persist=True,
                source_frames={"team_box": box},
            )
        self.assertEqual(len(defense), 2)
        points = set(
            int(value) for value in defense["points_allowed"]
        )
        self.assertEqual(points, {21, 24})

    def test_fact_game_market(self):
        betting = pd.DataFrame(
            [
                {
                    "game_id": "401628345",
                    "season": 2024,
                    "week": 1,
                    "provider": "consensus",
                    "spread": -3.5,
                    "over_under": 52.5,
                    "home_moneyline": -165,
                    "away_moneyline": 140,
                }
            ]
        )
        with patch.object(
            fact_game_market,
            "upsert_fact_game_market",
        ):
            frame = fact_game_market.build_fact_game_market(
                [2024],
                persist=True,
                source_frames={"betting": betting},
            )
        self.assertEqual(len(frame), 1)
        self.assertAlmostEqual(
            float(frame.iloc[0]["spread"]),
            -3.5,
        )
        self.assertIsNotNone(
            frame.iloc[0]["home_implied_total"]
        )
        for col in (
            "opening_spread",
            "opening_over_under",
            "opening_home_implied_total",
            "opening_away_implied_total",
            "opening_captured_at",
        ):
            self.assertIn(col, frame.columns)
            self.assertTrue(pd.isna(frame.iloc[0][col]))


class CfbLifecycleTests(unittest.TestCase):

    @patch(
        "app.sources.cfb_lifecycle.sdv_source.get_current_season",
        return_value=2024,
    )
    def test_historical_seasons(self, _mock):
        from app.sources import cfb_lifecycle

        seasons = cfb_lifecycle.historical_seasons(
            current_season=2024,
        )
        self.assertEqual(seasons, [2021, 2022, 2023, 2024])

    @patch(
        "app.sources.cfb_lifecycle.sdv_source.get_current_season",
        return_value=2024,
    )
    def test_layers_for_reprocess(self, _mock):
        from app.sources import cfb_lifecycle

        layers = cfb_lifecycle.layers_for_mode("reprocess")
        self.assertEqual(layers, ["facts"])

    @patch(
        "app.sources.cfb_lifecycle.sdv_source.clear_all_cfb_caches"
    )
    @patch(
        "app.sources.cfb_lifecycle.sdv_source.get_current_season",
        return_value=2024,
    )
    @patch("app.sources.cfb_lifecycle.refresh_dataset")
    @patch("app.sources.cfb_lifecycle._record_ingestion_state")
    def test_run_ingest_incremental(
        self,
        _record,
        refresh_dataset,
        _season,
        _clear,
    ):
        from app.sources import cfb_lifecycle

        refresh_dataset.side_effect = (
            lambda dataset_id, seasons, **kwargs: {
                "dataset_id": dataset_id,
                "seasons": seasons,
                "row_count": 1,
                "persisted": True,
                "force_refresh": True,
            }
        )
        result = cfb_lifecycle.run_ingest(mode="incremental")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["foundation"], "college_football")
        self.assertEqual(result["seasons"], [2024])
        called_ids = [
            call.args[0] for call in refresh_dataset.call_args_list
        ]
        self.assertEqual(
            called_ids,
            cfb_lifecycle.REFRESH_PIPELINE,
        )


if __name__ == "__main__":
    unittest.main()
