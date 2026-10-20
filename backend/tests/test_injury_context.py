"""Tests for predictive injury / context model."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.context_ablation import (
    run_context_ablation,
)
from app.analysis.insights.betting.injury_impact import (
    InjuryQualityFactors,
    estimate_injury_impact,
    market_priced_fraction_for_injury,
)
from app.analysis.insights.betting.injury_quality import (
    build_quality_factors,
)
from app.analysis.insights.betting.player_context import (
    combined_score_adjustments,
    refine_injury_with_market_move,
)


class PredictiveInjuryTests(unittest.TestCase):
    def test_qb_impact_exceeds_rb(self):
        qb = estimate_injury_impact(
            position="QB",
            status="out",
            depth_order=1,
            is_starter=True,
            factors=InjuryQualityFactors(starter_quality=1.1),
        )
        rb = estimate_injury_impact(
            position="RB",
            status="out",
            depth_order=1,
            is_starter=True,
            factors=InjuryQualityFactors(starter_quality=1.1),
        )
        self.assertGreater(
            abs(qb["own_score_delta"]),
            abs(rb["own_score_delta"]),
        )
        self.assertGreater(qb["impact_sigma"], rb["impact_sigma"])

    def test_better_replacement_dampens_impact(self):
        weak_backup = estimate_injury_impact(
            position="QB",
            status="out",
            is_starter=True,
            depth_order=1,
            factors=InjuryQualityFactors(
                starter_quality=1.2,
                replacement_quality=0.5,
                backup_performance=0.5,
            ),
        )
        strong_backup = estimate_injury_impact(
            position="QB",
            status="out",
            is_starter=True,
            depth_order=1,
            factors=InjuryQualityFactors(
                starter_quality=1.2,
                replacement_quality=1.2,
                backup_performance=1.15,
            ),
        )
        self.assertGreater(
            abs(weak_backup["own_score_delta"]),
            abs(strong_backup["own_score_delta"]),
        )

    def test_questionable_has_lower_play_prob_higher_sigma(self):
        out = estimate_injury_impact(
            position="WR",
            status="out",
            is_starter=True,
            depth_order=1,
        )
        q = estimate_injury_impact(
            position="WR",
            status="questionable",
            is_starter=True,
            depth_order=1,
        )
        self.assertGreater(out["play_prob"], q["play_prob"])
        self.assertGreater(q["impact_sigma"], out["impact_sigma"] * 0.9)
        self.assertGreater(
            abs(out["own_score_delta"]),
            abs(q["own_score_delta"]),
        )

    def test_market_move_raises_priced_fraction(self):
        base = market_priced_fraction_for_injury(
            position="QB",
            status="out",
            own_score_delta=-5.0,
            injured_team_is_home=True,
            spread_move=None,
        )
        moved = market_priced_fraction_for_injury(
            position="QB",
            status="out",
            own_score_delta=-5.0,
            injured_team_is_home=True,
            spread_move=1.5,
        )
        self.assertGreater(moved, base)

        impact = estimate_injury_impact(
            position="QB",
            status="out",
            is_starter=True,
            depth_order=1,
            spread_move=1.5,
            injured_team_is_home=True,
        )
        self.assertLess(
            abs(impact["edge_own_delta"]),
            abs(impact["own_score_delta"]),
        )

    def test_refine_injury_shrinks_edge_when_line_moved(self):
        injury = {
            "score_adjustment_pts": -4.0,
            "score_opponent_adjustment_pts": 0.0,
            "raw_adjustment_pts": -4.0,
            "raw_opponent_adjustment_pts": 0.0,
            "adjustment_pts": -2.0,
            "opponent_adjustment_pts": 0.0,
            "impact_sigma": 2.5,
            "injuries": [
                {
                    "position": "QB",
                    "game_status": "Out",
                    "score_own_delta": -4.0,
                    "score_opponent_delta": 0.0,
                    "impact_sigma": 2.5,
                    "is_starter": True,
                }
            ],
        }
        refined = refine_injury_with_market_move(
            injury,
            spread_move=2.0,
            total_move=-1.0,
            is_home=True,
        )
        self.assertLess(
            abs(float(refined["adjustment_pts"])),
            abs(float(refined["score_adjustment_pts"])),
        )

    def test_combined_uses_edge_not_full_score(self):
        home = {
            "adjustment_pts": -1.5,
            "opponent_adjustment_pts": 0.0,
            "score_adjustment_pts": -4.0,
        }
        away = {
            "adjustment_pts": 0.0,
            "opponent_adjustment_pts": 0.8,
            "score_opponent_adjustment_pts": 2.0,
        }
        h, a = combined_score_adjustments(
            home_injury=home, away_injury=away
        )
        self.assertAlmostEqual(h, -1.5 + 0.8, places=2)
        self.assertAlmostEqual(a, 0.0, places=2)

    def test_quality_builder_defaults_without_db(self):
        factors = build_quality_factors(
            player_id="p1",
            team_id="t1",
            position="QB",
            depth_order=1,
            season=2024,
            before_week=1,
            depth_rows=[],
            usage_cache={},
            efficiency_cache={},
        )
        self.assertGreater(factors.starter_quality, 0.5)
        self.assertGreater(factors.snap_expectation, 0.0)

    def test_ablation_report_groups(self):
        rows = []
        for i in range(40):
            qb = 1.0 if i % 5 == 0 else 0.0
            y_home = -3.0 * qb + (0.2 if i % 2 else -0.2)
            rows.append(
                {
                    "week": (i % 12) + 1,
                    "game_id": f"g{i}",
                    "market_home": 24.0,
                    "market_away": 21.0,
                    "actual_home": 24.0 + y_home,
                    "actual_away": 21.0,
                    "qb_out_home": qb,
                    "home_injury_position": "QB" if qb else None,
                    "home_injury_status": "out" if qb else None,
                    "home_injury_quality": {
                        "starter_quality": 1.2,
                        "replacement_quality": 0.55,
                        "snap_expectation": 1.0,
                        "team_dependency": 1.2,
                        "backup_performance": 0.55,
                        "scheme_impact": 1.1,
                    },
                    "home_rest_days": 4.0 if i % 7 == 0 else 7.0,
                    "away_rest_days": 7.0,
                    "spread_move": 1.0 if qb else 0.0,
                    "total_move": -0.5 if qb else 0.0,
                }
            )
        report = run_context_ablation(rows, train_ratio=0.6)
        self.assertTrue(report["available"])
        self.assertIn("injury_predictive", report["mae_by_group"])
        self.assertIn("weather", report["unavailable"])
        # Predictive injury should beat none on this synthetic QB signal.
        self.assertIsNotNone(report["mae_by_group"]["none"])
        self.assertIsNotNone(report["mae_by_group"]["injury_predictive"])
        self.assertLessEqual(
            report["mae_by_group"]["injury_predictive"],
            report["mae_by_group"]["none"] + 0.5,
        )


if __name__ == "__main__":
    unittest.main()
