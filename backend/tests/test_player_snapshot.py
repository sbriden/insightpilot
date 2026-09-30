"""Player Snapshot assessment is grounded in engine scores/signals."""

from __future__ import annotations

import unittest

from app.analysis.insights.player_snapshot import (
    build_assessment_narrative,
    build_player_snapshot,
    overall_assessment_for_player,
    overall_assessment_label,
)


class PlayerSnapshotTests(unittest.TestCase):

    def test_overall_assessment_bands(self):
        self.assertEqual(
            overall_assessment_label(82),
            "Elite",
        )
        self.assertEqual(
            overall_assessment_label(66),
            "Strong",
        )
        self.assertEqual(
            overall_assessment_label(50),
            "Solid",
        )
        self.assertEqual(
            overall_assessment_label(None),
            "Insufficient data",
        )

    def test_kicker_assessment_uses_fantasy_pace(self):
        self.assertEqual(
            overall_assessment_for_player(
                position="K",
                fantasy_value_score=17.0,
                fppg=12.0,
            ),
            "Elite",
        )
        self.assertEqual(
            overall_assessment_for_player(
                position="K",
                fantasy_value_score=17.0,
                fppg=8.0,
            ),
            "Solid",
        )
        self.assertEqual(
            overall_assessment_for_player(
                position="K",
                fantasy_value_score=17.0,
                fantasy_points=19.0,
                games=1,
            ),
            "Elite",
        )

    def test_narrative_from_opportunity_and_lagging_production(self):
        narrative = build_assessment_narrative(
            profile={
                "opportunity_score": 78,
                "production_score": 48,
                "trend_score": 68,
                "efficiency_score": 60,
                "fantasy_value_score": 64,
            },
            signals=[
                {
                    "signal_type": "BUY_LOW",
                    "signal_strength": 70,
                    "confidence": 65,
                }
            ],
        )
        self.assertIn(
            "Usage remains elite and has increased",
            narrative,
        )
        self.assertIn(
            "Production has lagged behind opportunity",
            narrative,
        )
        self.assertIn(
            "positive regression",
            narrative,
        )

    def test_snapshot_includes_identity_and_assessment(self):
        snapshot = build_player_snapshot(
            player_id="p1",
            name="Example Player",
            position="WR",
            team="KC",
            season=2025,
            week=3,
            status="Active",
            injury_status="Questionable",
            injury_type="Knee",
            profile={
                "fantasy_value_score": 67,
                "opportunity_score": 74,
                "production_score": 50,
                "trend_score": 66,
            },
            signals=[
                {
                    "signal_type": "BREAKOUT_CANDIDATE",
                    "signal_strength": 72,
                    "confidence": 70,
                }
            ],
            include_performance=False,
        )
        self.assertEqual(snapshot["name"], "Example Player")
        self.assertEqual(snapshot["position"], "WR")
        self.assertEqual(snapshot["team"], "KC")
        self.assertEqual(snapshot["season"], 2025)
        self.assertEqual(snapshot["week"], 3)
        self.assertNotIn("opponent", snapshot)
        self.assertEqual(snapshot["status"], "Active")
        self.assertEqual(
            snapshot["injury_status"],
            "Questionable",
        )
        self.assertEqual(snapshot["injury_type"], "Knee")
        self.assertEqual(
            snapshot["overall_assessment"],
            "Strong",
        )
        self.assertEqual(
            snapshot["evidence_source"],
            "player_fantasy_profile+fantasy_signal",
        )
        self.assertTrue(
            snapshot["assessment_narrative"]
        )
        self.assertTrue(snapshot["key_takeaways"])
        self.assertEqual(
            snapshot["recommendation"]["headline"],
            "Premium fantasy asset",
        )

    def test_select_profile_prefers_opportunity_week(self):
        from app.analysis.insights.player_snapshot import (
            _select_profile_for_snapshot,
        )

        profiles = [
            {
                "season": 2025,
                "week": 1,
                "opportunity_score": 40,
                "production_score": 30,
            },
            {
                "season": 2025,
                "week": 2,
                "opportunity_score": None,
                "production_score": 55,
            },
        ]
        selected = _select_profile_for_snapshot(
            profiles,
            season=2025,
            week=None,
        )
        self.assertEqual(selected["week"], 1)
        self.assertEqual(selected["opportunity_score"], 40)

    def test_snapshot_seasonizes_production_from_fppg(self):
        """Season FPPG should drive production/assessment over one week."""

        hot_week = build_player_snapshot(
            player_id="pollard",
            name="Tony Pollard",
            position="RB",
            season=2025,
            week=2,
            profile={
                "fantasy_value_score": 40,
                "opportunity_score": 35,
                "production_score": 75,
                "efficiency_score": 40,
                "trend_score": 40,
                "matchup_score": 40,
                "environment_score": 40,
                "risk_score": 40,
            },
            season_stats={
                "fppg": 8.0,
                "fantasy_points": 16.0,
                "games": 2,
            },
            include_performance=False,
        )
        volume_lead = build_player_snapshot(
            player_id="stevenson",
            name="Rhamondre Stevenson",
            position="RB",
            season=2025,
            week=2,
            profile={
                "fantasy_value_score": 35,
                "opportunity_score": 55,
                "production_score": 20,
                "efficiency_score": 40,
                "trend_score": 40,
                "matchup_score": 40,
                "environment_score": 40,
                "risk_score": 40,
            },
            season_stats={
                "fppg": 14.5,
                "fantasy_points": 29.0,
                "games": 2,
            },
            include_performance=False,
        )

        self.assertGreater(
            volume_lead["production_score"],
            hot_week["production_score"],
        )
        self.assertGreater(
            volume_lead["fantasy_value_score"],
            hot_week["fantasy_value_score"],
        )
        assessment_rank = {
            "Elite": 5,
            "Strong": 4,
            "Solid": 3,
            "Cautious": 2,
            "Weak": 1,
            "Insufficient data": 0,
        }
        self.assertGreaterEqual(
            assessment_rank[volume_lead["overall_assessment"]],
            assessment_rank[hot_week["overall_assessment"]],
        )


    def test_search_players_matches_name(self):
        from unittest.mock import patch
        import pandas as pd

        players = pd.DataFrame(
            [
                {
                    "player_id": "p1",
                    "name": "Patrick Mahomes",
                    "position": "QB",
                    "current_team_id": "t_kc",
                    "status": "Active",
                },
                {
                    "player_id": "p2",
                    "name": "Travis Kelce",
                    "position": "TE",
                    "current_team_id": "t_kc",
                    "status": "Active",
                },
                {
                    "player_id": "p3",
                    "name": "Chris Jones",
                    "position": "DT",
                    "current_team_id": "t_kc",
                    "status": "Active",
                },
                {
                    "player_id": "p4",
                    "name": "Trent McDuffie",
                    "position": "CB",
                    "current_team_id": "t_kc",
                    "status": "Active",
                },
            ]
        )
        teams = pd.DataFrame(
            [
                {
                    "team_id": "t_kc",
                    "team_abbreviation": "KC",
                }
            ]
        )

        with (
            patch(
                "app.canonical.dim_player.get_dim_player",
                return_value=players,
            ),
            patch(
                "app.canonical.dim_team.get_dim_team",
                return_value=teams,
            ),
        ):
            from app.analysis.insights.player_snapshot import (
                _search_players_fallback,
            )

            hits = _search_players_fallback("mahomes")
            self.assertEqual(len(hits), 1)
            self.assertEqual(
                hits[0]["player_id"],
                "p1",
            )
            self.assertEqual(
                hits[0]["team"],
                "KC",
            )

            self.assertEqual(_search_players_fallback("chris"), [])
            self.assertEqual(_search_players_fallback("mcduffie"), [])
            kelce = _search_players_fallback("kelce")
            self.assertEqual(len(kelce), 1)
            self.assertEqual(kelce[0]["position"], "TE")
