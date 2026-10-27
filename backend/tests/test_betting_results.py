"""Tests for auto-settled betting model results."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.results import (
    apply_calibration_to_scores,
    build_bet_tape_snapshot,
    build_performance_trend,
    calibration_feedback_from_results,
    filter_learning_rows,
    settle_event_markets,
    summarize_model_results,
)
from app.analysis.insights.betting.slate import _sync_event_results


def _event(**overrides):
    base = {
        "event_id": "g1",
        "label": "ATL @ GB",
        "season": 2026,
        "week": 3,
        "status": "Final",
        "home_team": "GB",
        "away_team": "ATL",
        "home_score": 24,
        "away_score": 17,
        "projected_home_score": 23.0,
        "projected_away_score": 18.0,
        "projected_total": 41.0,
        "model_spread": -5.0,
        "market_spread": -5.5,
        "market_total": 42.5,
    }
    base.update(overrides)
    return base


def _markets():
    return [
        {
            "market_id": "g1:spread",
            "event_id": "g1",
            "market_type": "spread",
            "selection": "GB -5.5",
            "line": -5.5,
            "price": -110,
            "home_team": "GB",
            "away_team": "ATL",
            "model_probability": 0.58,
            "edge_probability": 5.6,
            "confidence": "High",
        },
        {
            "market_id": "g1:total",
            "event_id": "g1",
            "market_type": "total",
            "selection": "Under 42.5",
            "line": 42.5,
            "price": -110,
            "home_team": "GB",
            "away_team": "ATL",
            "model_probability": 0.55,
            "edge_probability": 2.6,
            "confidence": "Moderate",
        },
        {
            "market_id": "g1:moneyline",
            "event_id": "g1",
            "market_type": "moneyline",
            "selection": "GB",
            "line": None,
            "price": -220,
            "home_team": "GB",
            "away_team": "ATL",
            "model_probability": 0.7,
            "edge_probability": 4.0,
            "confidence": "High",
        },
    ]


class BettingModelResultsTests(unittest.TestCase):
    def test_settle_event_markets_from_final_score(self):
        settled = settle_event_markets(_event(), _markets())
        by_id = {row["market_id"]: row for row in settled}
        # GB won 24-17 → covered -5.5, under 42.5, ML win.
        self.assertEqual(by_id["g1:spread"]["result"], "won")
        self.assertEqual(by_id["g1:total"]["result"], "won")
        self.assertEqual(by_id["g1:moneyline"]["result"], "won")
        # Without opening/current ML quotes, bet/close prices stay missing.
        self.assertIsNone(by_id["g1:moneyline"]["bet_price"])
        self.assertIsNone(by_id["g1:moneyline"]["closing_price"])
        self.assertFalse(by_id["g1:moneyline"]["clv_available"])
        self.assertEqual(by_id["g1:total"]["actual_total"], 41)
        self.assertEqual(by_id["g1:spread"]["total_error"], 0.0)

    def test_moneyline_prices_follow_the_selected_side(self):
        event = _event(
            opening_moneyline=-180,
            current_moneyline=-210,
        )
        markets = _markets()
        markets[2] = {
            **markets[2],
            "selection": "ATL",
            "price": 175,
            "opening_price": 160,
        }
        settled = settle_event_markets(event, markets)
        moneyline = next(
            row
            for row in settled
            if row["market_type"] == "moneyline"
        )
        self.assertGreater(moneyline["bet_price"], 0)
        self.assertGreater(moneyline["closing_price"], 0)
        self.assertNotEqual(
            moneyline["bet_price"],
            moneyline["closing_price"],
        )

    def test_summarize_and_feedback(self):
        settled = settle_event_markets(_event(), _markets())
        # Fabricate more games so feedback activates.
        rows = []
        for index in range(6):
            for row in settled:
                copy = dict(row)
                copy["event_id"] = f"g{index}"
                copy["market_id"] = f"g{index}:{row['market_type']}"
                copy["total_error"] = 2.0
                copy["spread_error"] = -1.0
                rows.append(copy)
        summary = summarize_model_results(rows)
        self.assertEqual(summary["games_settled"], 6)
        self.assertIsNotNone(summary["hit_rate"])
        feedback = calibration_feedback_from_results(rows)
        self.assertTrue(feedback["active"])
        home, away = apply_calibration_to_scores(
            24.0, 20.0, feedback=feedback
        )
        self.assertIsNotNone(home)
        self.assertIsNotNone(away)
        # Total bias is currently held at 0 in residual calibration
        # (avoids re-inflating overs); spread bias still shifts margin.
        self.assertAlmostEqual(home + away, 44.0, places=1)
        self.assertNotEqual(home - away, 4.0)

    def test_performance_trend_by_week(self):
        rows = []
        for week, correct in ((1, True), (2, False), (3, True)):
            for market_type in ("spread", "total"):
                rows.append(
                    {
                        "market_id": f"g{week}:{market_type}",
                        "event_id": f"g{week}",
                        "season": 2026,
                        "week": week,
                        "market_type": market_type,
                        "result": "won" if correct else "lost",
                        "total_error": 1.0 if week == 1 else -2.0,
                        "spread_error": -1.5,
                        "confidence": "High",
                        "edge_probability": 3.0,
                    }
                )
        trend = build_performance_trend(rows)
        self.assertEqual(len(trend), 3)
        self.assertEqual(trend[0]["week"], 1)
        self.assertEqual(trend[0]["hit_rate"], 100.0)
        self.assertEqual(trend[1]["hit_rate"], 0.0)
        self.assertEqual(trend[2]["cumulative_hit_rate"], 66.7)
        summary = summarize_model_results(rows)
        self.assertEqual(len(summary["performance_trend"]), 3)
        self.assertIsNotNone(summary["trend_summary"])
        self.assertEqual(
            summary["trend_summary"]["direction"], "declining"
        )

    def test_sync_does_not_overwrite_existing_pregame_snapshot(self):
        from unittest.mock import MagicMock, patch

        event = _event(status="scheduled", home_score=None, away_score=None)
        markets = _markets()
        existing = {
            "game_id": "g1",
            "projected_home_score": 23.0,
            "projected_away_score": 18.0,
            "frozen": False,
        }
        upsert = MagicMock()
        with patch(
            "app.canonical.fact_betting_results.get_projection_snapshot",
            return_value=existing,
        ), patch(
            "app.canonical.fact_betting_results.upsert_projection_snapshot",
            upsert,
        ), patch(
            "app.canonical.fact_betting_results.freeze_projection_snapshot",
        ), patch(
            "app.canonical.fact_betting_results.upsert_market_results",
        ):
            settled = _sync_event_results(event, markets)
        self.assertEqual(settled, [])
        upsert.assert_not_called()

    def test_bet_tape_prefers_opening_when_no_pregame_snapshot(self):
        event = _event(
            market_spread=-3.5,
            market_total=45.5,
            opening_spread=-2.0,
            opening_total=47.0,
            current_spread=-3.5,
            current_total=45.5,
        )
        snap = build_bet_tape_snapshot(event, prefer_opening=True)
        self.assertEqual(snap["market_spread"], -2.0)
        self.assertEqual(snap["market_total"], 47.0)
        self.assertEqual(snap["tape_source"], "opening_fallback")

        settled = settle_event_markets(
            event, _markets(), snapshot=snap
        )
        by_id = {row["market_id"]: row for row in settled}
        self.assertEqual(by_id["g1:spread"]["bet_line"], -2.0)
        self.assertEqual(by_id["g1:spread"]["closing_line"], -3.5)
        self.assertEqual(by_id["g1:spread"]["clv"], 1.5)
        self.assertEqual(by_id["g1:total"]["bet_line"], 47.0)

    def test_learning_cohort_prefers_strong_and_lean(self):
        rows = []
        for index in range(20):
            rows.append(
                {
                    "market_id": f"a{index}",
                    "bet_status": "strong_bet" if index < 10 else "lean",
                    "result": "won",
                }
            )
            rows.append(
                {
                    "market_id": f"p{index}",
                    "bet_status": "pass",
                    "result": "lost",
                }
            )
        cohort, label = filter_learning_rows(rows)
        self.assertEqual(label, "strong_lean")
        self.assertEqual(len(cohort), 20)
        self.assertTrue(
            all(
                row["bet_status"] in {"strong_bet", "lean"}
                for row in cohort
            )
        )


if __name__ == "__main__":
    unittest.main()
