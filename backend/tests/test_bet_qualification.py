"""Tests: Strong Bet / Lean / Pass are threshold-based."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.betting.bet_qualification import (
    assess_data_quality,
    evaluate_market_decision,
    market_movement_invalidates_edge,
    qualify_bet,
)
from app.analysis.insights.betting.slate import _enrich_event


class BetQualificationTests(unittest.TestCase):
    def test_negative_ev_is_pass_no_bet(self):
        decision = evaluate_market_decision(
            market_type="spread",
            selection="BUF -3.5",
            model_projection=-6.0,
            market_projection=-3.5,
            raw_probability=0.57,
            calibrated_probability=0.57,
            market_probability=0.524,
            expected_value=-1.5,
            edge_probability=4.6,
            model_confidence="High",
            direction="above_market",
            event={
                "team_strength": {
                    "available": True,
                    "home_games": 4,
                    "away_games": 4,
                },
                "residuals": {"residual_home": 1.2, "confidence": "High"},
            },
            probability_calibrated=True,
            offered_odds=-110,
            expected_value_basis="offered_price",
            edge_probability_basis="vig_adjusted_market",
            market_probability_source="two_way_american",
        )
        self.assertTrue(decision["prediction"]["has_prediction"])
        self.assertTrue(decision["bet"]["no_bet"])
        self.assertFalse(decision["bet"]["qualified"])
        self.assertEqual(decision["bet"]["status"], "pass")
        self.assertEqual(decision["bet"]["label"], "Pass")
        self.assertIn("EV", " ".join(decision["bet"]["reasons_fail"]))

    def test_strong_bet_when_all_strong_thresholds_clear(self):
        decision = evaluate_market_decision(
            market_type="spread",
            selection="BUF -3.5",
            model_projection=-7.0,
            market_projection=-3.5,
            raw_probability=0.62,
            calibrated_probability=0.60,
            market_probability=0.524,
            expected_value=5.0,
            edge_probability=7.6,
            model_confidence="High",
            direction="above_market",
            event={
                "team_strength": {
                    "available": True,
                    "home_games": 4,
                    "away_games": 4,
                    "projection_confidence": "High",
                },
                "residuals": {"residual_home": 1.4, "confidence": "High"},
                "injury_report_week": 4,
                "market_movement": {
                    "moved": False,
                    "opening_spread": -3.5,
                    "vs_model": {"label": "stable"},
                },
            },
            probability_calibrated=True,
            offered_odds=-110,
            expected_value_basis="offered_price",
            edge_probability_basis="vig_adjusted_market",
            market_probability_source="two_way_american",
        )
        self.assertTrue(decision["bet"]["qualified"])
        self.assertFalse(decision["bet"]["no_bet"])
        self.assertEqual(decision["bet"]["status"], "strong_bet")
        self.assertEqual(decision["bet"]["label"], "Strong Bet")
        self.assertEqual(
            decision["pipeline"][-1], "bet_classification"
        )

    def test_lean_when_moderate_thresholds_only(self):
        decision = evaluate_market_decision(
            market_type="spread",
            selection="BUF -3.5",
            model_projection=-5.0,
            market_projection=-3.5,
            raw_probability=0.56,
            calibrated_probability=0.55,
            market_probability=0.524,
            expected_value=2.0,
            edge_probability=2.6,
            model_confidence="Moderate",
            direction="above_market",
            event={
                "team_strength": {
                    "available": True,
                    "home_games": 3,
                    "away_games": 3,
                },
                "residuals": {
                    "residual_home": 0.8,
                    "confidence": "Moderate",
                },
                "injury_report_week": 4,
            },
            probability_calibrated=False,
            offered_odds=-110,
            expected_value_basis="offered_price",
            edge_probability_basis="vig_adjusted_market",
            market_probability_source="two_way_american",
        )
        self.assertEqual(decision["bet"]["status"], "lean")
        self.assertEqual(decision["bet"]["label"], "Lean")
        self.assertTrue(decision["bet"]["qualified"])
        self.assertFalse(decision["bet"]["no_bet"])

    def test_thin_data_quality_forces_pass(self):
        bet = qualify_bet(
            prediction={
                "has_prediction": True,
                "calibrated_probability": 0.56,
                "market_type": "spread",
            },
            market_probability=0.524,
            expected_value=2.0,
            edge_probability=3.6,
            model_confidence="High",
            data_quality={"label": "Low", "score": 0.3, "factors": []},
            offered_odds=-110,
            expected_value_basis="offered_price",
            edge_probability_basis="vig_adjusted_market",
            market_probability_source="two_way_american",
        )
        self.assertTrue(bet["no_bet"])
        self.assertEqual(bet["status"], "pass")
        self.assertIn("Data quality", " ".join(bet["reasons_fail"]))

    def test_market_move_toward_model_can_invalidate(self):
        event = {
            "market_movement": {
                "moved": True,
                "spread_move": -1.5,
                "vs_model": {"label": "line_toward_model"},
            }
        }
        check = market_movement_invalidates_edge(
            event=event,
            market_type="spread",
            edge_probability=2.0,  # below Strong Bet cushion
        )
        self.assertTrue(check["invalidates"])

        bet = qualify_bet(
            prediction={
                "has_prediction": True,
                "calibrated_probability": 0.58,
                "market_type": "spread",
            },
            market_probability=0.524,
            expected_value=4.0,
            edge_probability=2.0,
            model_confidence="High",
            data_quality={"label": "High", "score": 0.9, "factors": []},
            event=event,
            market_type="spread",
            offered_odds=-110,
            expected_value_basis="offered_price",
            edge_probability_basis="vig_adjusted_market",
            market_probability_source="two_way_american",
        )
        self.assertTrue(bet["no_bet"])
        self.assertEqual(bet["status"], "pass")
        self.assertFalse(bet["gates"]["market_movement_ok"])

    def test_data_quality_rewards_strength_and_calibration(self):
        weak = assess_data_quality(event={})
        strong = assess_data_quality(
            event={
                "team_strength": {
                    "available": True,
                    "home_games": 5,
                    "away_games": 5,
                },
                "residuals": {
                    "residual_home": 1.0,
                    "confidence": "High",
                },
                "injury_report_week": 3,
                "market_movement": {"moved": True},
            },
            probability_calibrated=True,
        )
        self.assertGreater(strong["score"], weak["score"])
        self.assertEqual(strong["label"], "High")

    def test_enrich_exposes_no_bet_fields(self):
        raw = {
            "event_id": "ip_game_qual",
            "season": 2026,
            "week": 4,
            "spread": -3.5,
            "over_under": 47.5,
            "home_implied_total": 25.5,
            "away_implied_total": 22.0,
            "home_team": "BUF",
            "away_team": "MIA",
            "home_team_id": "t-buf",
            "away_team_id": "t-mia",
            "start_time": "2026-09-28",
            "market_timestamp": "2026-09-28T13:00:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
        }
        with patch(
            "app.analysis.insights.betting.slate._load_projection_snapshot",
            return_value=None,
        ):
            built = _enrich_event(
                raw,
                recent_ppg={"t-buf": 30.0, "t-mia": 18.0},
            )
        market = built["markets"][0]
        self.assertIn("prediction", market)
        self.assertIn("bet_qualification", market)
        # Without a real offered price, ATS must Pass — forecast remains.
        self.assertEqual(market["bet_status"], "pass")
        self.assertEqual(market["bet_label"], "Pass")
        self.assertTrue(market["no_bet"])
        self.assertTrue(market["prediction"]["has_prediction"])
        self.assertEqual(
            market.get("expected_value_basis"), "assumed_minus_110"
        )
        audit = (market.get("bet_qualification") or {}).get(
            "pricing_audit"
        ) or {}
        self.assertFalse(
            audit.get("pricing_available_for_qualification")
        )
        self.assertIn("No Bet", market["prediction"]["note"])

    def test_assumed_minus_110_cannot_qualify_strong_or_lean(self):
        decision = evaluate_market_decision(
            market_type="spread",
            selection="BUF -3.5",
            model_projection=-7.0,
            market_projection=-3.5,
            raw_probability=0.62,
            calibrated_probability=0.60,
            market_probability=None,
            expected_value=5.0,
            edge_probability=7.6,
            model_confidence="High",
            direction="above_market",
            event={
                "team_strength": {
                    "available": True,
                    "home_games": 4,
                    "away_games": 4,
                    "projection_confidence": "High",
                },
                "residuals": {"residual_home": 1.4, "confidence": "High"},
                "injury_report_week": 4,
            },
            probability_calibrated=True,
            offered_odds=-110,
            expected_value_basis="assumed_minus_110",
            edge_probability_basis="reference_coin_flip",
            market_probability_source="unavailable",
        )
        self.assertEqual(decision["bet"]["status"], "pass")
        self.assertFalse(decision["bet"]["qualified"])
        self.assertFalse(
            decision["bet"]["gates"]["has_valid_offered_price"]
        )
        self.assertIn(
            "PRICING_DATA_UNAVAILABLE",
            decision["bet"]["reason_codes"],
        )
        # Forecast side still present.
        self.assertTrue(decision["prediction"]["has_prediction"])

    def test_real_offered_price_can_qualify(self):
        decision = evaluate_market_decision(
            market_type="moneyline",
            selection="BUF",
            model_projection=None,
            market_projection=None,
            raw_probability=0.62,
            calibrated_probability=0.60,
            market_probability=0.52,
            expected_value=5.0,
            edge_probability=8.0,
            model_confidence="High",
            direction="above_market",
            event={
                "team_strength": {
                    "available": True,
                    "home_games": 4,
                    "away_games": 4,
                    "projection_confidence": "High",
                },
                "residuals": {"residual_home": 1.4, "confidence": "High"},
                "injury_report_week": 4,
                "market_movement": {"moved": False},
            },
            probability_calibrated=True,
            offered_odds=-120,
            expected_value_basis="offered_price",
            edge_probability_basis="single_side_american",
            market_probability_source="single_side_american",
        )
        self.assertEqual(decision["bet"]["status"], "strong_bet")
        self.assertTrue(
            decision["bet"]["gates"]["has_valid_offered_price"]
        )


if __name__ == "__main__":
    unittest.main()
