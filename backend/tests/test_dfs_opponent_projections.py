"""Tests for opponent-adjusted DFS projections."""

from __future__ import annotations

import unittest

from app.analysis.insights.dfs.slate import (
    _matchup_label_from_score,
    _opponent_adjusted_projection,
    _position_matchup_score,
    _to_dfs_player,
)


class OpponentProjectionTests(unittest.TestCase):
    def test_favorable_matchup_lifts_projection(self):
        result = _opponent_adjusted_projection(
            base=20.0,
            position="WR",
            context={
                "matchup": {
                    "matchup_score": 70,
                    "receiving_matchup_score": 70,
                },
                "environment": {
                    "game_environment_score": 60,
                },
            },
            has_opponent=True,
        )
        self.assertGreater(result["projection"], 20.0)
        self.assertGreater(result["adjustment_factor"], 1.0)

    def test_difficult_matchup_cuts_projection(self):
        result = _opponent_adjusted_projection(
            base=20.0,
            position="RB",
            context={
                "matchup": {
                    "matchup_score": 30,
                    "rush_matchup_score": 30,
                    "receiving_matchup_score": 30,
                }
            },
            has_opponent=True,
        )
        self.assertLess(result["projection"], 20.0)
        self.assertLess(result["adjustment_factor"], 1.0)

    def test_no_opponent_keeps_base(self):
        result = _opponent_adjusted_projection(
            base=18.5,
            position="QB",
            context={
                "matchup": {"pass_matchup_score": 80},
            },
            has_opponent=False,
        )
        self.assertAlmostEqual(result["projection"], 18.5)
        self.assertIsNone(result["adjustment_factor"])

    def test_position_matchup_prefers_receiving_for_wr(self):
        score = _position_matchup_score(
            "WR",
            {
                "matchup_score": 40,
                "receiving_matchup_score": 72,
                "pass_matchup_score": 55,
            },
        )
        self.assertEqual(score, 72)

    def test_defense_inverts_overall_matchup(self):
        score = _position_matchup_score(
            "DEF",
            {"matchup_score": 70},
        )
        self.assertEqual(score, 30)

    def test_matchup_labels(self):
        self.assertEqual(
            _matchup_label_from_score(70),
            "Very Favorable",
        )
        self.assertEqual(
            _matchup_label_from_score(40),
            "Difficult",
        )

    def test_to_dfs_player_applies_context(self):
        player = _to_dfs_player(
            {
                "player_id": "p1",
                "name": "Test WR",
                "position": "WR",
                "team": "BUF",
                "fppg": 15.0,
                "games": 8,
                "opportunity_score": 60,
            },
            site="draftkings",
            opponents={"BUF": "NYJ"},
            baseline={
                "historical_baseline": 14.5,
                "historical_games": 50,
                "historical_p90": 22.0,
            },
            matchup_context={
                "matchup": {
                    "receiving_matchup_score": 70,
                    "matchup_score": 70,
                }
            },
        )
        self.assertIsNotNone(player)
        assert player is not None
        self.assertEqual(player["opponent"], "NYJ")
        self.assertEqual(player["raw_projection"], 15.0)
        self.assertGreater(
            player["projection"],
            player["base_projection"],
        )
        self.assertEqual(player["matchup_label"], "Very Favorable")
        self.assertIn("projection_confidence", player)

    def test_calibration_regresses_early_season_spike(self):
        player = _to_dfs_player(
            {
                "player_id": "qb1",
                "name": "Hot QB",
                "position": "QB",
                "team": "BUF",
                "fppg": 45.0,
                "games": 2,
                "opportunity_score": 70,
            },
            site="draftkings",
            opponents={"BUF": "NYJ"},
            baseline={
                "historical_baseline": 24.0,
                "historical_games": 80,
                "historical_p90": 32.0,
            },
        )
        self.assertIsNotNone(player)
        assert player is not None
        self.assertEqual(player["raw_projection"], 45.0)
        self.assertLess(player["insightpilot_projection"], 33.0)
        self.assertLess(player["projection"], 35.0)

    def test_opponent_priors_fill_missing_player_matchup(self):
        from app.analysis.insights.dfs.slate import (
            _resolve_player_week_context,
        )

        ctx = _resolve_player_week_context(
            player_id="p1",
            opponent="NYJ",
            week_context={
                "by_player": {
                    "p1": {
                        "environment": {
                            "game_environment_score": 55,
                        }
                    }
                },
                "by_opponent": {
                    "NYJ": {
                        "matchup_score": 68,
                        "receiving_matchup_score": 72,
                        "pass_matchup_score": 65,
                        "rush_matchup_score": 60,
                    }
                },
            },
        )
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(
            ctx["matchup"]["receiving_matchup_score"], 72
        )
        self.assertEqual(
            ctx["environment"]["game_environment_score"], 55
        )

        player = _to_dfs_player(
            {
                "player_id": "p1",
                "name": "Test WR",
                "position": "WR",
                "team": "BUF",
                "fppg": 12.0,
                "games": 8,
                "opportunity_score": 55,
            },
            site="draftkings",
            opponents={"BUF": "NYJ"},
            baseline={
                "historical_baseline": 12.0,
                "historical_games": 40,
                "historical_p90": 20.0,
            },
            week_context={
                "by_player": {},
                "by_opponent": {
                    "NYJ": {
                        "matchup_score": 70,
                        "receiving_matchup_score": 70,
                    }
                },
            },
        )
        self.assertIsNotNone(player)
        assert player is not None
        self.assertGreater(
            player["projection"],
            player["base_projection"],
        )
        self.assertIsNotNone(player["matchup_score"])

    def test_active_depth_backup_kept_without_games(self):
        """QB3 / depth backups must stay on the slate for search."""

        player = _to_dfs_player(
            {
                "player_id": "ip_player_keenum",
                "name": "Case Keenum",
                "position": "QB",
                "team": "CHI",
                "status": "Active",
                "depth_order": 3,
                "games": None,
                "fppg": None,
            },
            site="draftkings",
            contest_type="classic",
            opponents={"CHI": "DET"},
        )
        self.assertIsNotNone(player)
        assert player is not None
        self.assertEqual(player["name"], "Case Keenum")
        self.assertEqual(player["salary_source"], "synthetic")

    def test_uploaded_salary_keeps_player_without_depth(self):
        player = _to_dfs_player(
            {
                "player_id": "sal1",
                "name": "Salary Only",
                "position": "WR",
                "team": "CHI",
                "status": "Active",
                "games": None,
                "fppg": None,
            },
            site="draftkings",
            salary_map={"sal1": 4200},
        )
        self.assertIsNotNone(player)
        assert player is not None
        self.assertEqual(player["salary"], 4200)
        self.assertEqual(player["salary_source"], "uploaded")

    def test_reserve_deep_depth_without_salary_still_dropped(self):
        player = _to_dfs_player(
            {
                "player_id": "res1",
                "name": "Reserve Ghost",
                "position": "WR",
                "team": "CHI",
                "status": "Reserve",
                "depth_order": 6,
                "games": None,
                "fppg": None,
            },
            site="draftkings",
        )
        self.assertIsNone(player)


if __name__ == "__main__":
    unittest.main()
