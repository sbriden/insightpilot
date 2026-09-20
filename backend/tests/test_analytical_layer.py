"""Tests for analytical-layer fantasy intelligence models."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.analytics.player_efficiency import (
    build_player_efficiency,
)
from app.canonical.analytics.player_environment import (
    build_player_environment,
)
from app.canonical.analytics.player_matchup import (
    build_player_matchup,
)
from app.canonical.analytics.player_opportunity import (
    build_player_opportunity,
)
from app.canonical.analytics.player_usage_trend import (
    build_player_usage_trend,
)
from app.canonical.ids import (
    make_player_id,
    make_team_id,
    make_game_id,
    player_resolution_key,
    game_resolution_key,
)


def _ids() -> dict[str, str]:
    player_id = make_player_id(
        player_resolution_key(gsis_id="00-0039999")
    )
    team_id = make_team_id("BUF")
    opp_id = make_team_id("MIA")
    game1 = make_game_id(
        game_resolution_key(nflverse_game_id="2024_01_MIA_BUF")
    )
    game2 = make_game_id(
        game_resolution_key(nflverse_game_id="2024_02_BUF_MIA")
    )
    return {
        "player_id": player_id,
        "team_id": team_id,
        "opp_id": opp_id,
        "game1": game1,
        "game2": game2,
    }


class PlayerUsageTrendTests(unittest.TestCase):

    def test_builds_rolling_shares_and_changes(self):
        ids = _ids()
        usage = pd.DataFrame(
            [
                {
                    "player_id": ids["player_id"],
                    "season": 2024,
                    "week": 1,
                    "offensive_snap_share": 0.50,
                    "target_share": 0.10,
                    "rush_share": 0.20,
                    "route_participation_rate": 0.40,
                },
                {
                    "player_id": ids["player_id"],
                    "season": 2024,
                    "week": 2,
                    "offensive_snap_share": 0.70,
                    "target_share": 0.20,
                    "rush_share": 0.30,
                    "route_participation_rate": 0.60,
                },
            ]
        )

        with patch(
            "app.canonical.analytics.player_usage_trend.upsert_player_usage_trend"
        ):
            frame = build_player_usage_trend(
                [2024],
                persist=True,
                source_frames={"usage": usage},
            )

        self.assertEqual(len(frame), 2)
        week2 = frame[frame["week"] == 2].iloc[0]
        self.assertAlmostEqual(
            float(week2["snap_share_3wk"]),
            0.60,
            places=5,
        )
        self.assertAlmostEqual(
            float(week2["target_share_3wk"]),
            0.15,
            places=5,
        )
        self.assertIsNotNone(week2["target_share_change"])
        self.assertIsNotNone(week2["opportunity_trend"])
        self.assertEqual(
            list(frame.columns),
            [
                "player_id",
                "season",
                "week",
                "snap_share_3wk",
                "target_share_3wk",
                "rush_share_3wk",
                "route_participation_3wk",
                "target_share_change",
                "snap_share_change",
                "opportunity_trend",
                "source_ids",
            ],
        )


class PlayerOpportunityTests(unittest.TestCase):

    def test_scores_opportunity_from_usage(self):
        ids = _ids()
        usage = pd.DataFrame(
            [
                {
                    "player_id": ids["player_id"],
                    "season": 2024,
                    "week": 2,
                    "offensive_snap_share": 0.80,
                    "target_share": 0.25,
                    "route_participation_rate": 0.70,
                    "air_yard_share": 0.30,
                    "rush_share": 0.10,
                    "touch_share": 0.15,
                    "red_zone_touches": 2,
                    "red_zone_targets": 1,
                    "goal_line_carries": 1,
                }
            ]
        )

        with patch(
            "app.canonical.analytics.player_opportunity.upsert_player_opportunity"
        ):
            frame = build_player_opportunity(
                [2024],
                persist=True,
                source_frames={"usage": usage},
            )

        row = frame.iloc[0]
        self.assertIsNotNone(row["opportunity_score"])
        self.assertIsNotNone(row["receiving_opportunity_score"])
        self.assertIsNotNone(row["rushing_opportunity_score"])
        self.assertIsNotNone(row["red_zone_opportunity_score"])
        self.assertGreater(float(row["opportunity_score"]), 0)

    def test_qb_opportunity_ignores_receiving_zeros(self):
        ids = _ids()
        usage = pd.DataFrame(
            [
                {
                    "player_id": ids["player_id"],
                    "season": 2024,
                    "week": 2,
                    "position": "QB",
                    "offensive_snap_share": 1.0,
                    "target_share": 0.0,
                    "route_participation_rate": None,
                    "air_yard_share": None,
                    "rush_share": 0.20,
                    "qb_rush_share": 0.20,
                    "touch_share": 0.12,
                    "dropbacks": 36,
                    "deep_pass_attempts": 4,
                    "designed_rush_attempts": 5,
                    "scrambles": 2,
                    "red_zone_touches": 1,
                    "red_zone_targets": None,
                    "goal_line_carries": 1,
                }
            ]
        )

        with patch(
            "app.canonical.analytics.player_opportunity.upsert_player_opportunity"
        ):
            frame = build_player_opportunity(
                [2024],
                persist=True,
                source_frames={"usage": usage},
            )

        row = frame.iloc[0]
        # Receiving is not part of the QB model.
        self.assertTrue(
            row["receiving_opportunity_score"] is None
            or (
                isinstance(row["receiving_opportunity_score"], float)
                and pd.isna(row["receiving_opportunity_score"])
            )
        )
        self.assertIsNotNone(row["opportunity_score"])
        # Must beat the old skill model that treated target_share=0
        # as a 35% zero weight (~34 with these inputs).
        self.assertGreater(float(row["opportunity_score"]), 50.0)


class PlayerEfficiencyAnalyticsTests(unittest.TestCase):

    def test_scores_distinct_from_raw_rates(self):
        ids = _ids()
        efficiency = pd.DataFrame(
            [
                {
                    "player_id": ids["player_id"],
                    "season": 2024,
                    "week": 2,
                    "yards_per_carry": 4.5,
                    "yards_per_target": 8.0,
                    "yards_per_route_run": 2.0,
                    "catch_rate": 0.70,
                    "td_rate": 0.05,
                    "pass_epa_per_dropback": None,
                    "rush_epa_per_attempt": 0.1,
                }
            ]
        )

        with patch(
            "app.canonical.analytics.player_efficiency.upsert_player_efficiency"
        ):
            frame = build_player_efficiency(
                [2024],
                persist=True,
                source_frames={"efficiency": efficiency},
            )

        row = frame.iloc[0]
        self.assertIsNotNone(row["efficiency_score"])
        self.assertIsNotNone(row["receiving_efficiency"])
        self.assertIsNotNone(row["rushing_efficiency"])
        # Scores are 0–100 intelligence, not raw ypc/ypt.
        self.assertGreater(float(row["rushing_efficiency"]), 10)
        self.assertLessEqual(
            float(row["rushing_efficiency"]),
            100,
        )


class PlayerMatchupTests(unittest.TestCase):

    def test_uses_prior_opponent_defense(self):
        ids = _ids()
        players = pd.DataFrame(
            [
                {
                    "player_id": ids["player_id"],
                    "game_id": ids["game2"],
                    "season": 2024,
                    "week": 2,
                    "team_id": ids["team_id"],
                }
            ]
        )
        games = pd.DataFrame(
            [
                {
                    "game_id": ids["game1"],
                    "season": 2024,
                    "week": 1,
                    "home_team_id": ids["team_id"],
                    "away_team_id": ids["opp_id"],
                },
                {
                    "game_id": ids["game2"],
                    "season": 2024,
                    "week": 2,
                    "home_team_id": ids["opp_id"],
                    "away_team_id": ids["team_id"],
                },
            ]
        )
        defense = pd.DataFrame(
            [
                {
                    "defensive_team_id": ids["opp_id"],
                    "game_id": ids["game1"],
                    "season": 2024,
                    "week": 1,
                    "pass_epa_allowed": 0.2,
                    "rush_epa_allowed": 0.1,
                    "pass_yards_allowed": 280,
                    "rush_yards_allowed": 140,
                    "receiving_yards_allowed": 220,
                    "targets_allowed": 35,
                    "pressure_rate": 0.25,
                    "sack_rate": 0.06,
                },
                {
                    "defensive_team_id": ids["opp_id"],
                    "game_id": ids["game2"],
                    "season": 2024,
                    "week": 2,
                    "pass_epa_allowed": -0.1,
                    "rush_epa_allowed": -0.2,
                    "pass_yards_allowed": 180,
                    "rush_yards_allowed": 80,
                    "receiving_yards_allowed": 140,
                    "targets_allowed": 20,
                    "pressure_rate": 0.40,
                    "sack_rate": 0.10,
                },
            ]
        )

        with patch(
            "app.canonical.analytics.player_matchup.upsert_player_matchup"
        ):
            frame = build_player_matchup(
                [2024],
                persist=True,
                source_frames={
                    "players": players,
                    "games": games,
                    "defense": defense,
                },
            )

        row = frame.iloc[0]
        self.assertEqual(row["week"], 2)
        self.assertIsNotNone(row["matchup_score"])
        self.assertIsNotNone(row["pass_matchup_score"])
        self.assertIsNotNone(row["rush_matchup_score"])
        self.assertIsNotNone(row["receiving_matchup_score"])


class PlayerEnvironmentTests(unittest.TestCase):

    def test_builds_environment_from_market_and_pace(self):
        ids = _ids()
        players = pd.DataFrame(
            [
                {
                    "player_id": ids["player_id"],
                    "game_id": ids["game2"],
                    "season": 2024,
                    "week": 2,
                    "team_id": ids["team_id"],
                }
            ]
        )
        games = pd.DataFrame(
            [
                {
                    "game_id": ids["game2"],
                    "season": 2024,
                    "week": 2,
                    "home_team_id": ids["team_id"],
                    "away_team_id": ids["opp_id"],
                }
            ]
        )
        markets = pd.DataFrame(
            [
                {
                    "game_id": ids["game2"],
                    "source": "nflverse_schedules",
                    "spread": -3.5,
                    "over_under": 48.0,
                    "home_implied_total": 25.75,
                    "away_implied_total": 22.25,
                    "season": 2024,
                    "week": 2,
                }
            ]
        )
        team_games = pd.DataFrame(
            [
                {
                    "team_id": ids["team_id"],
                    "game_id": ids["game1"],
                    "season": 2024,
                    "week": 1,
                    "pace": 68.0,
                },
                {
                    "team_id": ids["team_id"],
                    "game_id": ids["game2"],
                    "season": 2024,
                    "week": 2,
                    "pace": 70.0,
                },
            ]
        )

        with patch(
            "app.canonical.analytics.player_environment.upsert_player_environment"
        ):
            frame = build_player_environment(
                [2024],
                persist=True,
                source_frames={
                    "players": players,
                    "games": games,
                    "markets": markets,
                    "team_games": team_games,
                },
            )

        row = frame.iloc[0]
        self.assertAlmostEqual(
            float(row["team_total"]),
            25.75,
            places=5,
        )
        self.assertIsNotNone(row["game_environment_score"])
        self.assertIsNotNone(row["pace_expectation"])
        self.assertIsNotNone(row["game_script_expectation"])


if __name__ == "__main__":
    unittest.main()
