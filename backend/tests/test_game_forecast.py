"""Game forecast is the shared environment for player projections."""

from __future__ import annotations

import unittest

from app.analysis.insights.dfs.player_game_projection import (
    project_player_from_game_forecast,
)
from app.analysis.insights.dfs.slate import _to_dfs_player
from app.analysis.insights.game_forecast import (
    GAME_FORECAST_MODEL_VERSION,
    LEAGUE_POINTS,
    build_game_forecast,
    index_team_environments,
)


def _forecast(
    home: float,
    away: float,
    *,
    pace_z: float | None = None,
) -> dict:
    return build_game_forecast(
        event_id="g1",
        season=2025,
        week=6,
        home_team="BUF",
        away_team="NYJ",
        projected_home_points=home,
        projected_away_points=away,
        source="insightpilot_game_model",
        timestamp="2026-10-15T15:00:00+00:00",
        pace_z=pace_z,
    )


def _side(home: float, away: float, team: str = "BUF", **kwargs) -> dict:
    forecast = _forecast(home, away, **kwargs)
    return index_team_environments(forecast)[team]


class GameForecastTests(unittest.TestCase):
    def test_forecast_exposes_score_volume_and_provenance(self):
        forecast = _forecast(27.0, 20.0)
        self.assertEqual(forecast["projected_home_points"], 27.0)
        self.assertEqual(forecast["projected_away_points"], 20.0)
        self.assertEqual(forecast["projected_total"], 47.0)
        self.assertEqual(forecast["projected_margin"], 7.0)
        self.assertEqual(forecast["source"], "insightpilot_game_model")
        self.assertEqual(
            forecast["model_version"],
            GAME_FORECAST_MODEL_VERSION,
        )
        self.assertTrue(forecast["timestamp"])
        self.assertIn("margin_sd", forecast["uncertainty"])
        self.assertFalse(
            forecast["score_distribution"]["applied_to_players"]
        )
        self.assertEqual(
            forecast["score_distribution"]["status"],
            "deferred",
        )
        self.assertFalse(forecast["game_scripts"]["applied_to_players"])

        buf = index_team_environments(forecast)["BUF"]
        for key in (
            "expected_plays",
            "expected_possessions",
            "expected_drives",
            "expected_scoring_opportunities",
            "expected_pass_attempts",
            "expected_rush_attempts",
            "expected_pass_tds",
            "expected_rush_tds",
            "expected_field_goals",
            "expected_turnovers",
        ):
            self.assertGreater(buf[key], 0.0, key)

    def test_team_points_match_touchdowns_and_field_goals(self):
        buf = _side(27.5, 19.5)
        component = (
            buf["expected_offensive_tds"] * 7.0
            + buf["expected_field_goals"] * 3.0
        )
        self.assertAlmostEqual(
            component,
            buf["projected_points"],
            places=2,
        )
        self.assertAlmostEqual(
            buf["points_from_components"],
            buf["projected_points"],
            places=2,
        )

    def test_high_total_adds_scoring_opportunities_not_only_plays(self):
        neutral = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        shootout = _side(31.0, 28.0)
        self.assertGreater(
            shootout["expected_scoring_opportunities"],
            neutral["expected_scoring_opportunities"],
        )
        self.assertGreater(
            shootout["expected_offensive_tds"],
            neutral["expected_offensive_tds"],
        )
        self.assertAlmostEqual(
            shootout["expected_plays"],
            neutral["expected_plays"],
            places=2,
        )

    def test_pace_changes_plays_without_changing_team_points(self):
        slow = _side(24.0, 21.0, pace_z=0.0)
        fast = _side(24.0, 21.0, pace_z=2.0)
        self.assertGreater(fast["expected_plays"], slow["expected_plays"])
        self.assertAlmostEqual(
            fast["projected_points"],
            slow["projected_points"],
            places=2,
        )

    def test_favorite_script_shifts_volume_toward_the_run(self):
        even = _side(24.0, 24.0)
        blowout = _side(24.0, 10.0)
        self.assertLess(
            blowout["expected_pass_attempts"],
            even["expected_pass_attempts"],
        )
        self.assertGreater(
            blowout["expected_rush_attempts"],
            even["expected_rush_attempts"],
        )
        self.assertLess(
            blowout["expected_pass_tds"],
            even["expected_pass_tds"],
        )
        self.assertGreater(
            blowout["expected_rush_tds"],
            even["expected_rush_tds"],
        )


class PlayerGameProjectionTests(unittest.TestCase):
    def test_neutral_forecast_preserves_calibrated_baseline(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        result = project_player_from_game_forecast(
            base_projection=15.0,
            position="WR",
            team_forecast=side,
            opportunity_score=60,
            depth_order=1,
        )
        self.assertEqual(result["projection"], 15.0)
        self.assertEqual(result["adjustment_source"], "game_forecast")
        self.assertTrue(result["environment_counted_once"])
        self.assertFalse(result["matchup_multiplier_applied"])
        self.assertIsNone(result["adjustment_factor"])

    def test_same_team_points_move_wr_and_rb_in_opposite_directions(self):
        even = _side(24.0, 24.0)
        blowout = _side(24.0, 10.0)
        wr_even = project_player_from_game_forecast(
            base_projection=16.0,
            position="WR",
            team_forecast=even,
            depth_order=1,
            opportunity_score=70,
        )
        wr_blowout = project_player_from_game_forecast(
            base_projection=16.0,
            position="WR",
            team_forecast=blowout,
            depth_order=1,
            opportunity_score=70,
        )
        rb_even = project_player_from_game_forecast(
            base_projection=16.0,
            position="RB",
            team_forecast=even,
            depth_order=1,
            opportunity_score=70,
        )
        rb_blowout = project_player_from_game_forecast(
            base_projection=16.0,
            position="RB",
            team_forecast=blowout,
            depth_order=1,
            opportunity_score=70,
        )
        self.assertLess(
            wr_blowout["projection"],
            wr_even["projection"],
        )
        self.assertGreater(
            rb_blowout["projection"],
            rb_even["projection"],
        )
        self.assertTrue(
            any("pass" in line.lower() for line in wr_blowout["drivers"])
        )
        self.assertTrue(
            any("rush" in line.lower() for line in rb_blowout["drivers"])
        )

    def test_higher_team_total_raises_scoring_without_a_second_boost(self):
        quiet = _side(17.0, 14.0)
        shootout = _side(31.0, 28.0)
        quiet_wr = project_player_from_game_forecast(
            base_projection=14.0,
            position="WR",
            team_forecast=quiet,
            depth_order=1,
        )
        shootout_wr = project_player_from_game_forecast(
            base_projection=14.0,
            position="WR",
            team_forecast=shootout,
            depth_order=1,
        )
        self.assertGreater(
            shootout_wr["projection"],
            quiet_wr["projection"],
        )
        reason = shootout_wr["projection_environment_reason"].lower()
        self.assertIn("touchdown", reason)
        self.assertIn("not applied", reason)

    def test_kicker_follows_field_goals_and_defense_follows_opponent(self):
        quiet = _side(16.0, 14.0)
        shootout = _side(31.0, 28.0)
        kicker_quiet = project_player_from_game_forecast(
            base_projection=8.0,
            position="K",
            team_forecast=quiet,
        )
        kicker_shootout = project_player_from_game_forecast(
            base_projection=8.0,
            position="K",
            team_forecast=shootout,
        )
        self.assertGreater(
            kicker_shootout["projection"],
            kicker_quiet["projection"],
        )
        self.assertTrue(
            any(
                "field goal" in line.lower()
                for line in kicker_shootout["drivers"]
            )
        )

        defense = project_player_from_game_forecast(
            base_projection=8.0,
            position="DEF",
            team_forecast=shootout,
        )
        self.assertLess(defense["projection"], 8.0)
        self.assertTrue(
            any("opponent" in line.lower() for line in defense["drivers"])
        )

    def test_dfs_player_does_not_apply_matchup_multiplier_on_top(self):
        forecasts = index_team_environments(_forecast(27.0, 20.0))
        context = {
            "matchup": {
                "receiving_matchup_score": 80,
                "matchup_score": 80,
            },
            "environment": {"game_environment_score": 90},
        }
        player = _to_dfs_player(
            {
                "player_id": "wr1",
                "name": "Test WR",
                "position": "WR",
                "team": "BUF",
                "fppg": 15.0,
                "games": 10,
                "opportunity_score": 60,
                "depth_order": 1,
            },
            site="draftkings",
            opponents={"BUF": "NYJ"},
            baseline={
                "historical_baseline": 15.0,
                "historical_games": 50,
                "historical_p90": 24.0,
            },
            matchup_context=context,
            game_forecasts=forecasts,
        )
        self.assertIsNotNone(player)
        assert player is not None
        direct = project_player_from_game_forecast(
            base_projection=player["base_projection"],
            position="WR",
            team_forecast=forecasts["BUF"],
            opportunity_score=60,
            depth_order=1,
            current_season_games=10,
            historical_baseline=15.0,
            raw_projection=15.0,
            matchup_score=80,
        )
        self.assertEqual(player["projection"], direct["projection"])
        self.assertEqual(player["adjustment_source"], "game_forecast")
        self.assertFalse(player["matchup_multiplier_applied"])
        self.assertIsNone(player["matchup_adjustment_factor"])
        self.assertEqual(player["matchup_label"], "Very Favorable")
        self.assertEqual(player["environment_score"], 90.0)
        self.assertTrue(player["projection_drivers"])
        self.assertIsNotNone(player["scoring_components"])
        self.assertIn("targets", player["role_forecast"]["opportunities"])


class PlayerRoleTests(unittest.TestCase):
    def test_starter_without_current_points_is_not_zero(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        result = project_player_from_game_forecast(
            base_projection=0.0,
            raw_projection=0.0,
            position="QB",
            team_forecast=side,
            depth_order=1,
            current_season_games=0,
            historical_baseline=22.0,
        )
        self.assertGreater(result["projection"], 12.0)
        self.assertGreater(
            result["role_forecast"]["opportunities"]["attempts"],
            20.0,
        )
        self.assertIn(
            "dropbacks",
            result["role_forecast"]["opportunities"],
        )

    def test_backup_does_not_keep_a_starter_average(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        starter = project_player_from_game_forecast(
            base_projection=0.0,
            raw_projection=0.0,
            position="RB",
            team_forecast=side,
            depth_order=1,
            current_season_games=0,
            historical_baseline=18.0,
        )
        backup = project_player_from_game_forecast(
            base_projection=0.0,
            raw_projection=0.0,
            position="RB",
            team_forecast=side,
            depth_order=4,
            current_season_games=0,
            historical_baseline=18.0,
        )
        self.assertGreater(starter["projection"], 10.0)
        self.assertLess(backup["projection"], 8.0)
        self.assertLess(
            backup["role_forecast"]["opportunities"]["carries"],
            starter["role_forecast"]["opportunities"]["carries"],
        )
        former_starter = project_player_from_game_forecast(
            base_projection=18.0,
            raw_projection=4.0,
            position="QB",
            team_forecast=side,
            depth_order=2,
            current_season_games=4,
            historical_baseline=22.0,
            historical_usage={"offensive_snap_share": 0.98},
            current_usage={"offensive_snap_share": 0.12},
        )
        self.assertLess(former_starter["projection"], 8.0)
        self.assertLess(
            former_starter["role_forecast"]["opportunities"]["attempts"],
            8.0,
        )
        deep_receiver = project_player_from_game_forecast(
            base_projection=0.0,
            raw_projection=0.6,
            position="WR",
            team_forecast=side,
            depth_order=4,
            current_season_games=2,
            historical_baseline=14.0,
            historical_usage={
                "route_participation_rate": 0.92,
                "target_share": 0.22,
            },
            current_usage={
                "route_participation_rate": 0.20,
                "target_share": 0.03,
            },
        )
        self.assertLess(deep_receiver["projection"], 8.0)
        self.assertLess(
            deep_receiver["role_forecast"]["opportunities"]["targets"],
            4.0,
        )
        chart_only = project_player_from_game_forecast(
            base_projection=7.5,
            raw_projection=0.0,
            position="RB",
            team_forecast=side,
            depth_order=1,
            current_season_games=5,
            historical_baseline=12.5,
            current_usage={
                "offensive_snap_share": 0.06,
                "rush_share": 0.0,
                "target_share": 0.0,
            },
        )
        self.assertLess(chart_only["projection"], 8.0)
        self.assertLess(
            chart_only["role_forecast"]["opportunities"]["carries"],
            4.0,
        )

    def test_promotion_changes_targets_before_fantasy_average_changes(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        shared = dict(
            base_projection=11.0,
            raw_projection=11.0,
            position="WR",
            team_forecast=side,
            depth_order=2,
            current_season_games=6,
            historical_baseline=11.0,
            current_usage={"target_share": 0.18, "route_participation_rate": 0.88},
        )
        regular = project_player_from_game_forecast(**shared)
        promoted = project_player_from_game_forecast(
            **shared,
            teammates_ahead_out=1,
        )
        self.assertGreater(
            promoted["role_forecast"]["opportunities"]["targets"],
            regular["role_forecast"]["opportunities"]["targets"],
        )
        self.assertGreater(
            promoted["projection"],
            regular["projection"],
        )
        self.assertTrue(promoted["role_forecast"]["promoted"])
        self.assertEqual(regular["role_forecast"]["effective_depth"], 2)

    def test_unavailable_starter_loses_the_role(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        active = project_player_from_game_forecast(
            base_projection=16.0,
            position="WR",
            team_forecast=side,
            depth_order=1,
            current_season_games=8,
            historical_baseline=16.0,
            raw_projection=16.0,
        )
        out = project_player_from_game_forecast(
            base_projection=16.0,
            position="WR",
            team_forecast=side,
            depth_order=1,
            current_season_games=8,
            historical_baseline=16.0,
            raw_projection=16.0,
            injury_status="Out",
        )
        self.assertGreater(active["projection"], 10.0)
        self.assertEqual(out["projection"], 0.0)
        self.assertEqual(
            out["role_forecast"]["opportunities"]["targets"],
            0.0,
        )


class ProductionComponentTests(unittest.TestCase):
    def test_projection_is_the_sum_of_scored_stats(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        result = project_player_from_game_forecast(
            base_projection=16.0,
            raw_projection=16.0,
            position="RB",
            team_forecast=side,
            depth_order=1,
            current_season_games=8,
            historical_baseline=16.0,
        )
        components = result["scoring_components"]["components"]
        scored = sum(part["points"] for part in components)
        self.assertAlmostEqual(scored, result["projection"], places=1)
        keys = {part["key"] for part in components}
        self.assertIn("rush_yards", keys)
        self.assertIn("receptions", keys)
        self.assertIn("rush_tds", keys)
        self.assertIn("receiving_yards", keys)
        stats = result["scoring_components"]["stats"]
        self.assertGreater(stats["rush_yards"], 0.0)
        self.assertGreater(stats["rush_tds"], 0.0)
        reason = result["projection_environment_reason"].lower()
        self.assertIn("touchdown", reason)
        self.assertIn("yards", reason)

    def test_touchdowns_ignore_a_historical_touchdown_rate(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        shared = dict(
            base_projection=14.0,
            raw_projection=14.0,
            position="WR",
            team_forecast=side,
            depth_order=1,
            current_season_games=10,
            historical_baseline=14.0,
        )
        plain = project_player_from_game_forecast(**shared)
        spiked = project_player_from_game_forecast(
            **shared,
            current_efficiency={
                "td_rate": 0.5,
                "td_rate_games": 40,
                "yards_per_target": 8.4,
                "yards_per_target_games": 2,
            },
        )
        self.assertAlmostEqual(
            plain["scoring_components"]["stats"]["receiving_tds"],
            spiked["scoring_components"]["stats"]["receiving_tds"],
            places=2,
        )

    def test_noisy_yards_per_carry_shrinks_toward_the_prior(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        result = project_player_from_game_forecast(
            base_projection=14.0,
            raw_projection=14.0,
            position="RB",
            team_forecast=side,
            depth_order=1,
            current_season_games=3,
            historical_baseline=14.0,
            current_efficiency={
                "yards_per_carry": 7.5,
                "yards_per_carry_games": 3,
            },
        )
        rate = result["scoring_components"]["rates"]["yards_per_carry"]
        self.assertGreater(rate, 4.3)
        self.assertLess(rate, 7.5)
        carries = result["role_forecast"]["opportunities"]["carries"]
        yards = result["scoring_components"]["stats"]["rush_yards"]
        self.assertGreater(yards, 0.0)
        self.assertLess(yards / carries, 7.5)

    def test_quarterback_splits_passing_and_rushing(self):
        side = _side(LEAGUE_POINTS, LEAGUE_POINTS)
        result = project_player_from_game_forecast(
            base_projection=22.0,
            raw_projection=22.0,
            position="QB",
            team_forecast=side,
            depth_order=1,
            current_season_games=8,
            historical_baseline=22.0,
        )
        points = result["scoring_components"]["points"]
        self.assertGreater(points["pass_yards"], 0.0)
        self.assertGreater(points["pass_tds"], 0.0)
        self.assertLess(points["interceptions"], 0.0)
        self.assertGreater(points["rush_yards"], 0.0)
        scored = sum(points.values())
        self.assertAlmostEqual(scored, result["projection"], places=1)


if __name__ == "__main__":
    unittest.main()
