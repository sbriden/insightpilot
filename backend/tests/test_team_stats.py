"""Tests for team stats aggregation helpers."""

from __future__ import annotations

import unittest

import pandas as pd

from app.analysis.insights.team_stats import (
    _group_depth_chart,
    _rank_leaders,
    build_team_totals,
    team_logo_url,
)


class TeamStatsTests(unittest.TestCase):
    def test_rank_leaders_by_metric(self):
        players = [
            {
                "name": "A",
                "pass_yards": 100,
                "pass_attempts": 20,
            },
            {
                "name": "B",
                "pass_yards": 250,
                "pass_attempts": 40,
            },
            {
                "name": "C",
                "pass_yards": 10,
                "pass_attempts": 0,
            },
        ]
        leaders = _rank_leaders(
            players,
            metric="pass_yards",
            require=("pass_attempts",),
        )
        self.assertEqual(
            [row["name"] for row in leaders],
            ["B", "A"],
        )

    def test_group_depth_chart_orders_positions(self):
        frame = pd.DataFrame(
            [
                {
                    "position": "WR",
                    "player_id": "p2",
                    "name": "Receiver",
                    "depth_order": 1,
                    "role": "starter",
                },
                {
                    "position": "QB",
                    "player_id": "p1",
                    "name": "Passer",
                    "depth_order": 1,
                    "role": "starter",
                },
                {
                    "position": "QB",
                    "player_id": "p3",
                    "name": "Backup",
                    "depth_order": 2,
                    "role": "backup",
                },
            ]
        )
        groups = _group_depth_chart(frame)
        self.assertEqual(
            [group["position"] for group in groups],
            ["QB", "WR"],
        )
        self.assertEqual(
            [player["name"] for player in groups[0]["players"]],
            ["Passer", "Backup"],
        )

    def test_team_logo_url_uses_espn_abbreviations(self):
        self.assertEqual(
            team_logo_url("KC"),
            "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
        )
        self.assertEqual(
            team_logo_url("LA"),
            "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png",
        )
        self.assertEqual(
            team_logo_url("WAS"),
            "https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png",
        )
        self.assertIsNone(team_logo_url(""))

    def test_build_team_totals_derives_efficiency(self):
        totals = build_team_totals(
            {
                "games": 2,
                "points": 40,
                "yards": 700,
                "offensive_plays": 120,
                "pass_attempts": 70,
                "rush_attempts": 50,
                "offensive_epa": 12,
                "pass_epa": 8,
                "rush_epa": 4,
                "red_zone_trips": 6,
                "red_zone_tds": 3,
                "turnovers": 2,
                "pace": 28.5,
                "wins": 1,
                "losses": 1,
                "ties": 0,
                "points_allowed": 35,
                "yards_allowed": 600,
                "pass_yards_allowed": 400,
                "rush_yards_allowed": 200,
                "pass_epa_allowed": 2,
                "rush_epa_allowed": -1,
                "sack_rate": 0.08,
                "pressure_rate": 0.3,
                "defense_games": 2,
            },
            [
                {
                    "pass_completions": 40,
                    "pass_attempts": 60,
                    "pass_yards": 450,
                    "rush_yards": 180,
                    "rush_attempts": 40,
                    "receptions": 30,
                    "targets": 45,
                    "receiving_yards": 360,
                },
                {
                    "pass_completions": 0,
                    "pass_attempts": 10,
                    "pass_yards": 50,
                    "rush_yards": 20,
                    "rush_attempts": 10,
                },
            ],
        )
        self.assertIsNotNone(totals)
        assert totals is not None
        self.assertEqual(totals["record"]["wins"], 1)
        self.assertEqual(totals["record"]["losses"], 1)
        self.assertEqual(
            totals["record"]["point_differential"],
            5,
        )
        self.assertEqual(totals["offense"]["points_per_game"], 20.0)
        self.assertEqual(totals["offense"]["yards_per_play"], 5.83)
        self.assertEqual(totals["offense"]["epa_per_play"], 0.1)
        self.assertEqual(
            totals["offense"]["pass_epa_per_attempt"],
            0.114,
        )
        self.assertEqual(totals["offense"]["pass_rate"], 0.5833)
        self.assertEqual(
            totals["offense"]["red_zone_td_rate"],
            0.5,
        )
        self.assertEqual(
            totals["defense"]["points_allowed_per_game"],
            17.5,
        )
        self.assertEqual(
            totals["efficiency"]["completion_pct"],
            0.5714,
        )
        self.assertEqual(
            totals["efficiency"]["yards_per_attempt"],
            7.14,
        )
        self.assertEqual(
            totals["efficiency"]["yards_per_carry"],
            4.0,
        )
        self.assertEqual(
            totals["efficiency"]["catch_rate"],
            0.6667,
        )
        self.assertEqual(
            totals["efficiency"]["yards_per_target"],
            8.0,
        )

    def test_build_team_totals_skill_only(self):
        totals = build_team_totals(
            None,
            [
                {
                    "receptions": 8,
                    "targets": 10,
                    "receiving_yards": 90,
                }
            ],
        )
        self.assertEqual(
            totals["efficiency"]["catch_rate"],
            0.8,
        )
        self.assertIsNone(totals["offense"])
        self.assertIsNone(totals["record"])

    def test_build_team_totals_empty(self):
        self.assertIsNone(build_team_totals(None, []))
        self.assertIsNone(build_team_totals({"games": 0}, []))


if __name__ == "__main__":
    unittest.main()
