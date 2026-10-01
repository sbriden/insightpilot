"""Tests for per-market model performance tracking."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.market_performance import (
    apply_market_confidence_thresholds,
    build_market_performance,
)
from app.analysis.insights.betting.pricing import confidence_from_edge
from app.analysis.insights.betting.results import summarize_model_results


def _row(
    *,
    market_id: str,
    market_type: str,
    result: str,
    edge_points: float,
    model_probability: float = 0.55,
    clv: float = 0.5,
    spread_error: float | None = None,
    total_error: float | None = None,
    model_spread: float | None = None,
    market_spread: float | None = None,
    model_total: float | None = None,
    market_total: float | None = None,
) -> dict:
    return {
        "market_id": market_id,
        "market_type": market_type,
        "selection": "GB -3" if market_type == "spread" else (
            "Under 45" if market_type == "total" else "GB"
        ),
        "home_team": "GB",
        "away_team": "ATL",
        "result": result,
        "edge": edge_points,
        "edge_points": edge_points,
        "price": -110,
        "model_probability": model_probability,
        "raw_model_probability": model_probability,
        "bet_line": -3.0 if market_type == "spread" else (
            45.0 if market_type == "total" else None
        ),
        "closing_line": (
            -3.5 if market_type == "spread" else (
                45.5 if market_type == "total" else None
            )
        ),
        "bet_price": -110 if market_type == "moneyline" else None,
        "closing_price": -120 if market_type == "moneyline" else None,
        "clv": clv,
        "spread_error": spread_error,
        "total_error": total_error,
        "model_spread": model_spread,
        "market_spread": market_spread,
        "model_total": model_total,
        "market_total": market_total,
        "actual_spread": -7.0 if market_type == "spread" else None,
        "actual_total": 41.0 if market_type == "total" else None,
    }


class MarketPerformanceTests(unittest.TestCase):
    def test_tracks_markets_separately(self):
        rows = []
        # Strong spread model.
        for i in range(20):
            rows.append(
                _row(
                    market_id=f"s-{i}",
                    market_type="spread",
                    result="won" if i < 14 else "lost",
                    edge_points=3.5,
                    model_probability=0.58,
                    clv=0.8,
                    spread_error=1.5 if i % 2 == 0 else -1.0,
                    model_spread=-5.0,
                    market_spread=-3.0,
                )
            )
        # Weak total model.
        for i in range(20):
            rows.append(
                _row(
                    market_id=f"t-{i}",
                    market_type="total",
                    result="won" if i < 8 else "lost",
                    edge_points=2.0,
                    model_probability=0.54,
                    clv=-0.4,
                    total_error=6.0 if i % 2 == 0 else -5.0,
                    model_total=46.0,
                    market_total=44.0,
                )
            )
        # Decent ML.
        for i in range(16):
            rows.append(
                _row(
                    market_id=f"m-{i}",
                    market_type="moneyline",
                    result="won" if i < 10 else "lost",
                    edge_points=4.0,
                    model_probability=0.56,
                    clv=1.5,
                )
            )

        perf = build_market_performance(rows)
        spread = perf["markets"]["spread"]
        total = perf["markets"]["total"]
        ml = perf["markets"]["moneyline"]

        self.assertEqual(spread["ats_win_pct"], 70.0)
        self.assertIsNotNone(spread["roi_pct"])
        self.assertIsNotNone(spread["average_clv"])
        self.assertIsNotNone(spread["mae"])
        self.assertIsNotNone(spread["calibration"]["gap_pp"])

        self.assertEqual(total["ou_win_pct"], 40.0)
        self.assertIsNotNone(total["mae"])
        self.assertGreater(total["mae"], spread["mae"])

        self.assertIsNotNone(ml["win_pct"])
        self.assertIsNone(ml["mae"])

        self.assertEqual(perf["ranking"][0], "spread")
        self.assertGreater(
            spread["quality_score"], total["quality_score"]
        )
        self.assertTrue(spread["confidence_active"])
        # Stronger market should not require more edge than weaker.
        self.assertLessEqual(
            spread["high_min"], total["high_min"]
        )

    def test_confidence_allocated_by_market(self):
        market_perf = {
            "markets": {
                "spread": {
                    "confidence_active": True,
                    "high_min": 2.5,
                    "moderate_min": 1.0,
                    "confidence_weight": 1.2,
                },
                "total": {
                    "confidence_active": True,
                    "high_min": 4.5,
                    "moderate_min": 2.5,
                    "confidence_weight": 0.7,
                },
            }
        }
        # Same 3.0-point edge: High on spread, Moderate/Low on total.
        self.assertEqual(
            apply_market_confidence_thresholds(
                market_type="spread",
                edge_points=3.0,
                market_performance=market_perf,
            ),
            "High",
        )
        self.assertEqual(
            confidence_from_edge(
                edge_points=3.0,
                market_type="total",
                market_performance=market_perf,
            ),
            "Moderate",
        )

    def test_summary_includes_market_performance(self):
        rows = [
            _row(
                market_id="a",
                market_type="spread",
                result="won",
                edge_points=3.0,
                spread_error=2.0,
                model_spread=-5.0,
                market_spread=-3.0,
            ),
            _row(
                market_id="b",
                market_type="total",
                result="lost",
                edge_points=1.5,
                total_error=-4.0,
                model_total=44.0,
                market_total=45.5,
            ),
        ]
        summary = summarize_model_results(rows)
        self.assertIn("market_performance", summary)
        self.assertIn("spread", summary["market_performance"]["markets"])
        self.assertTrue(summary["by_market"])
        keys = {row["market_type"] for row in summary["by_market"]}
        self.assertIn("spread", keys)
        self.assertIn("total", keys)


if __name__ == "__main__":
    unittest.main()
