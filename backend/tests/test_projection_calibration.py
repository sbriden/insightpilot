"""Sanity tests for projection calibration guardrails."""

from __future__ import annotations

import unittest

from app.analysis.insights.dfs.projection_calibration import (
    calibrate_projection,
    current_season_weight_for_games,
)


class ProjectionCalibrationTests(unittest.TestCase):
    def test_two_elite_games_regress_toward_baseline(self):
        """Josh Allen-style early-season spike must not stay at 45."""

        result = calibrate_projection(
            raw_projection=45.0,
            position="QB",
            current_season_games=2,
            historical_baseline=24.5,
            historical_games=80,
            historical_p90=32.0,
            opportunity_score=72,
        )
        self.assertEqual(result.raw_projection, 45.0)
        self.assertLess(result.insightpilot_projection, 32.0)
        self.assertGreater(result.insightpilot_projection, 20.0)
        self.assertLess(result.projection_adjustment, -5.0)
        self.assertIn(
            "limited current-season sample",
            result.projection_adjustment_reason.lower(),
        )
        self.assertEqual(result.projection_confidence, "Very Low")

    def test_two_terrible_games_do_not_collapse_to_zero(self):
        result = calibrate_projection(
            raw_projection=4.0,
            position="QB",
            current_season_games=2,
            historical_baseline=22.0,
            historical_games=60,
            historical_p90=30.0,
            opportunity_score=65,
        )
        self.assertGreater(result.insightpilot_projection, 14.0)
        self.assertGreater(result.projection_adjustment, 0.0)

    def test_legitimate_elite_with_sample_stays_high(self):
        result = calibrate_projection(
            raw_projection=28.5,
            position="QB",
            current_season_games=12,
            historical_baseline=25.0,
            historical_games=90,
            historical_p90=34.0,
            opportunity_score=85,
        )
        self.assertGreaterEqual(
            result.insightpilot_projection, 26.0
        )
        self.assertIn(
            result.projection_confidence,
            {"High", "Very High", "Moderate"},
        )

    def test_rookie_uses_positional_prior(self):
        result = calibrate_projection(
            raw_projection=30.0,
            position="WR",
            current_season_games=2,
            historical_baseline=None,
            historical_games=0,
            opportunity_score=55,
        )
        self.assertIn("positional_prior", result.flags)
        self.assertLess(result.insightpilot_projection, 22.0)
        self.assertGreater(result.insightpilot_projection, 8.0)

    def test_zero_point_depth_chart_wr_not_inflated(self):
        """Inactive / no-usage WR must not get ~WR-average FPPG."""

        result = calibrate_projection(
            raw_projection=0.0,
            position="WR",
            current_season_games=1,
            historical_baseline=None,
            historical_games=0,
            opportunity_score=4.4,
            depth_order=6,
        )
        self.assertIn("dormant_usage", result.flags)
        self.assertLessEqual(result.insightpilot_projection, 2.0)
        self.assertEqual(result.raw_projection, 0.0)

    def test_one_target_reserve_wr_not_inflated_by_prior(self):
        """
        Omar Cooper Jr.–style: Reserve WR6, 1 target / 4 FPPG
        from a single catch must not get ~WR average (~11).
        """

        result = calibrate_projection(
            raw_projection=4.0,
            position="WR",
            current_season_games=1,
            historical_baseline=None,
            historical_games=0,
            opportunity_score=3.2,
            depth_order=6,
            roster_status="Reserve",
        )
        self.assertIn("dormant_usage", result.flags)
        self.assertIn("inactive_roster", result.flags)
        self.assertLessEqual(result.insightpilot_projection, 2.5)
        self.assertLess(
            result.insightpilot_projection,
            result.raw_projection,
        )

    def test_one_catch_without_depth_still_dormant_on_weak_opp(self):
        """Missing depth chart must not unlock positional prior."""

        result = calibrate_projection(
            raw_projection=4.0,
            position="WR",
            current_season_games=1,
            historical_baseline=None,
            historical_games=0,
            opportunity_score=3.2,
            depth_order=None,
            roster_status="Reserve",
        )
        self.assertIn("dormant_usage", result.flags)
        self.assertLessEqual(result.insightpilot_projection, 2.5)

    def test_deep_qb_with_modest_opportunity_stays_low(self):
        result = calibrate_projection(
            raw_projection=2.0,
            position="QB",
            current_season_games=1,
            historical_baseline=None,
            historical_games=0,
            opportunity_score=28.0,
            depth_order=4,
        )
        self.assertIn("dormant_usage", result.flags)
        self.assertLessEqual(result.insightpilot_projection, 4.0)

    def test_depth_chart_starter_without_season_stats_gets_prior(self):
        result = calibrate_projection(
            raw_projection=0.0,
            position="QB",
            current_season_games=0,
            historical_baseline=18.0,
            historical_games=20,
            opportunity_score=None,
            depth_order=1,
        )
        self.assertIn("depth_starter_prior", result.flags)
        self.assertGreaterEqual(result.insightpilot_projection, 12.0)
        self.assertNotIn("dormant_usage", result.flags)

    def test_active_zero_backup_not_propped_by_history(self):
        """TE2 with an active 0-pt week must not stay near historical FPPG."""

        result = calibrate_projection(
            raw_projection=3.5,
            position="TE",
            current_season_games=2,
            historical_baseline=8.9,
            historical_games=35,
            historical_p90=21.0,
            opportunity_score=11.0,
            depth_order=2,
        )
        self.assertIn("dormant_usage", result.flags)
        self.assertLessEqual(result.insightpilot_projection, 5.0)
        self.assertAlmostEqual(result.raw_projection, 3.5, delta=0.05)
        self.assertNotIn("depth_starter_prior", result.flags)

    def test_opportunity_increase_allows_higher_projection(self):
        low_opp = calibrate_projection(
            raw_projection=22.0,
            position="RB",
            current_season_games=4,
            historical_baseline=12.0,
            historical_games=40,
            opportunity_score=40,
        )
        high_opp = calibrate_projection(
            raw_projection=22.0,
            position="RB",
            current_season_games=4,
            historical_baseline=12.0,
            historical_games=40,
            opportunity_score=90,
        )
        self.assertGreaterEqual(
            high_opp.insightpilot_projection,
            low_opp.insightpilot_projection,
        )

    def test_backup_becoming_starter_opportunity_matters(self):
        as_backup = calibrate_projection(
            raw_projection=18.0,
            position="RB",
            current_season_games=3,
            historical_baseline=6.0,
            historical_games=30,
            opportunity_score=25,
        )
        as_starter = calibrate_projection(
            raw_projection=18.0,
            position="RB",
            current_season_games=3,
            historical_baseline=6.0,
            historical_games=30,
            opportunity_score=88,
        )
        self.assertGreater(
            as_starter.insightpilot_projection,
            as_backup.insightpilot_projection,
        )

    def test_injury_return_small_sample_stays_cautious(self):
        result = calibrate_projection(
            raw_projection=26.0,
            position="WR",
            current_season_games=1,
            historical_baseline=14.0,
            historical_games=50,
            historical_p90=22.0,
            opportunity_score=60,
        )
        self.assertLess(result.insightpilot_projection, 20.0)
        self.assertEqual(
            result.sample_size_confidence, "Very Low"
        )

    def test_normal_veteran_near_baseline(self):
        result = calibrate_projection(
            raw_projection=13.2,
            position="WR",
            current_season_games=8,
            historical_baseline=12.8,
            historical_games=70,
            historical_p90=20.0,
            opportunity_score=58,
        )
        self.assertAlmostEqual(
            result.insightpilot_projection,
            13.0,
            delta=1.5,
        )

    def test_sample_weight_schedule_increases(self):
        w2 = current_season_weight_for_games(2)
        w5 = current_season_weight_for_games(5)
        w10 = current_season_weight_for_games(10)
        self.assertLess(w2, w5)
        self.assertLess(w5, w10)

    def test_emits_floor_ceiling_and_reason(self):
        result = calibrate_projection(
            raw_projection=40.0,
            position="QB",
            current_season_games=2,
            historical_baseline=23.0,
            historical_games=70,
        )
        self.assertLess(
            result.projection_floor,
            result.insightpilot_projection,
        )
        self.assertGreater(
            result.projection_ceiling,
            result.insightpilot_projection,
        )
        self.assertTrue(result.projection_adjustment_reason)


if __name__ == "__main__":
    unittest.main()
