"""Tests for Closing Line Value diagnostics."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.clv import (
    build_clv_diagnostics,
    compute_clv,
)
from app.analysis.insights.betting.results import (
    settle_event_markets,
    summarize_model_results,
)


class ClvTests(unittest.TestCase):
    def test_spread_clv_positive_when_bet_gets_better_number(self):
        # Bet home -3, close home -4.5 → laid fewer points → +1.5 CLV.
        out = compute_clv(
            market_type="spread",
            selection="GB -3",
            home_team="GB",
            away_team="ATL",
            bet_line=-3.0,
            closing_line=-4.5,
        )
        self.assertEqual(out["clv"], 1.5)
        self.assertTrue(out["beat_close"])
        self.assertEqual(out["clv_unit"], "points")

    def test_under_clv_positive_when_total_falls(self):
        # Bet under 47, close 45.5 → got the higher (better) number.
        out = compute_clv(
            market_type="total",
            selection="Under 47",
            bet_line=47.0,
            closing_line=45.5,
        )
        self.assertEqual(out["clv"], 1.5)
        self.assertTrue(out["beat_close"])

    def test_under_clv_negative_when_total_rises(self):
        # Bet under 45.5, close 47 → got the lower (worse) number.
        out = compute_clv(
            market_type="total",
            selection="Under 45.5",
            bet_line=45.5,
            closing_line=47.0,
        )
        self.assertEqual(out["clv"], -1.5)
        self.assertFalse(out["beat_close"])

    def test_over_clv_positive_when_total_rises(self):
        out = compute_clv(
            market_type="total",
            selection="Over 45.5",
            bet_line=45.5,
            closing_line=47.0,
        )
        self.assertEqual(out["clv"], 1.5)
        self.assertTrue(out["beat_close"])

    def test_settle_stores_bet_and_closing_not_final_score(self):
        event = {
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
            "market_spread": -3.0,  # closing (away-home)
            "market_total": 47.0,
            "opening_spread": -2.0,
            "opening_total": 45.5,
            "current_spread": -3.0,
            "current_total": 47.0,
        }
        snapshot = {
            "projected_home_score": 23.0,
            "projected_away_score": 18.0,
            "projected_total": 41.0,
            "model_spread": -5.0,
            "market_spread": -2.0,  # bet-time
            "market_total": 45.5,
            "captured_at": "2026-09-20T12:00:00+00:00",
            "frozen": True,
        }
        markets = [
            {
                "market_id": "g1:spread",
                "market_type": "spread",
                "selection": "GB -2",
                "line": -2.0,
                "price": -110,
                "home_team": "GB",
                "away_team": "ATL",
                "model_probability": 0.58,
                "edge_probability": 4.0,
                "confidence": "High",
            },
            {
                "market_id": "g1:total",
                "market_type": "total",
                "selection": "Under 45.5",
                "line": 45.5,
                "price": -110,
                "home_team": "GB",
                "away_team": "ATL",
                "model_probability": 0.55,
                "edge_probability": 2.0,
                "confidence": "Moderate",
            },
        ]
        settled = settle_event_markets(
            event, markets, snapshot=snapshot
        )
        by_id = {row["market_id"]: row for row in settled}
        spread = by_id["g1:spread"]
        total = by_id["g1:total"]

        self.assertEqual(spread["bet_line"], -2.0)
        self.assertEqual(spread["closing_line"], -3.0)
        self.assertEqual(spread["clv"], 1.0)
        # Must not use final margin (24-17 = +7 home) as closing line.
        self.assertNotEqual(spread["closing_line"], -7.0)

        self.assertEqual(total["bet_line"], 45.5)
        self.assertEqual(total["closing_line"], 47.0)
        # Under got worse number as total rose → negative CLV.
        self.assertEqual(total["clv"], -1.5)
        self.assertNotEqual(total["closing_line"], 41.0)

    def test_summary_includes_clv_and_breakdowns(self):
        rows = [
            {
                "market_id": "a:spread",
                "event_id": "a",
                "week": 1,
                "market_type": "spread",
                "selection": "GB -3",
                "home_team": "GB",
                "away_team": "ATL",
                "result": "won",
                "bet_line": -3.0,
                "closing_line": -4.5,
                "bet_line_source": "snapshot",
                "closing_line_source": "closing",
                "price": -110,
                "edge": 4.0,
                "confidence": "High",
            },
            {
                "market_id": "b:total",
                "event_id": "b",
                "week": 1,
                "market_type": "total",
                "selection": "Over 44",
                "home_team": "GB",
                "away_team": "ATL",
                "result": "lost",
                "bet_line": 44.0,
                "closing_line": 45.5,
                "bet_line_source": "snapshot",
                "closing_line_source": "closing",
                "price": -110,
                "edge": 2.0,
                "confidence": "Moderate",
            },
            {
                "market_id": "c:moneyline",
                "event_id": "c",
                "week": 2,
                "market_type": "moneyline",
                "selection": "ATL",
                "home_team": "GB",
                "away_team": "ATL",
                "result": "won",
                "bet_price": 150,
                "closing_price": 120,
                "bet_price_source": "opening",
                "closing_price_source": "closing",
                "price": 150,
                "edge": 3.0,
                "confidence": "High",
            },
        ]
        summary = summarize_model_results(rows)
        self.assertIsNotNone(summary["average_clv"])
        self.assertIsNotNone(summary["median_clv"])
        self.assertIsNotNone(summary["ats_win_pct"])
        self.assertIsNotNone(summary["ou_win_pct"])
        self.assertIsNotNone(summary["ml_win_pct"])
        self.assertIsNotNone(summary["roi_pct"])
        self.assertIsNotNone(summary["units"])
        self.assertTrue(summary["by_edge_bucket"])
        self.assertTrue(summary["by_favorite_underdog"])
        self.assertTrue(summary["by_home_away"])
        self.assertTrue(summary["by_week"])

        diag = build_clv_diagnostics(rows)
        self.assertGreater(diag["summary"]["clv_sample"], 0)
        self.assertIsNotNone(diag["summary"]["average_closing_edge"])
        # Headline average_clv is points-only (excludes ML prob_pp).
        self.assertEqual(diag["summary"]["average_clv"], 1.5)
        self.assertEqual(diag["summary"]["average_clv_points"], 1.5)
        self.assertIsNotNone(diag["summary"]["average_clv_prob_pp"])
        self.assertNotEqual(
            diag["summary"]["average_clv"],
            diag["summary"]["average_clv_prob_pp"],
        )

    def test_grades_on_bet_line_not_closing_line(self):
        # Actual margin home +7. Bet home -2 covers; close -6.5 also
        # covers — use a total where bet vs close diverge on grade.
        event = {
            "event_id": "g2",
            "label": "ATL @ GB",
            "season": 2026,
            "week": 4,
            "status": "Final",
            "home_team": "GB",
            "away_team": "ATL",
            "home_score": 27,
            "away_score": 20,
            "projected_home_score": 24.0,
            "projected_away_score": 20.0,
            "projected_total": 44.0,
            "model_spread": -4.0,
            "market_spread": -3.5,
            "market_total": 45.5,
            "opening_spread": -2.0,
            "opening_total": 47.0,
            "current_spread": -3.5,
            "current_total": 45.5,
        }
        snapshot = {
            "projected_home_score": 24.0,
            "projected_away_score": 20.0,
            "projected_total": 44.0,
            "model_spread": -4.0,
            "market_spread": -2.0,
            "market_total": 47.0,
            "tape_source": "first_publish",
            "captured_at": "2026-09-27T12:00:00+00:00",
            "frozen": True,
        }
        markets = [
            {
                "market_id": "g2:total",
                "market_type": "total",
                "selection": "Under 45.5",
                "line": 45.5,  # closing published line
                "price": -110,
                "home_team": "GB",
                "away_team": "ATL",
                "model_probability": 0.55,
                "edge_probability": 2.0,
                "confidence": "Moderate",
                "bet_status": "lean",
            },
        ]
        settled = settle_event_markets(
            event, markets, snapshot=snapshot
        )
        total = settled[0]
        self.assertEqual(total["bet_line"], 47.0)
        self.assertEqual(total["closing_line"], 45.5)
        # Actual 47 graded on bet 47 → push (not lost vs close 45.5).
        self.assertEqual(total["result"], "push")
        self.assertEqual(total["clv"], 1.5)


if __name__ == "__main__":
    unittest.main()
