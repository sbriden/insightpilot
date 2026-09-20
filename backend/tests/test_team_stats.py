"""Tests for team stats aggregation helpers."""

from __future__ import annotations

import unittest

import pandas as pd

from app.analysis.insights.team_stats import (
    _group_depth_chart,
    _rank_leaders,
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


if __name__ == "__main__":
    unittest.main()
