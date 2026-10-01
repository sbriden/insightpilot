"""Tests for learned point-edge confidence thresholds."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.edge_confidence import (
    POINT_EDGE_BUCKETS,
    assign_point_edge_bucket,
    backtest_point_edge_buckets,
    build_edge_confidence_diagnostics,
    fit_confidence_thresholds,
    point_edge_magnitude,
)
from app.analysis.insights.betting.pricing import confidence_from_edge


class EdgeConfidenceTests(unittest.TestCase):
    def test_bucket_ladder_matches_spec(self):
        labels = [label for label, _, _ in POINT_EDGE_BUCKETS]
        self.assertEqual(
            labels,
            [
                "0–0.5",
                "0.5–1.0",
                "1.0–1.5",
                "1.5–2.0",
                "2.0–2.5",
                "2.5–3.0",
                "3.0–3.5",
                "3.5+",
            ],
        )
        self.assertEqual(assign_point_edge_bucket(0.4), "0–0.5")
        self.assertEqual(assign_point_edge_bucket(1.8), "1.5–2.0")
        self.assertEqual(assign_point_edge_bucket(3.5), "3.5+")
        self.assertEqual(assign_point_edge_bucket(4.2), "3.5+")

    def test_point_edge_from_spread_projections(self):
        mag = point_edge_magnitude(
            {
                "market_type": "spread",
                "model_spread": -6.0,
                "market_spread": -3.0,
            }
        )
        self.assertEqual(mag, 3.0)

    def test_fallback_thresholds_until_enough_samples(self):
        rows = [
            {
                "market_type": "spread",
                "model_spread": -4.0,
                "market_spread": -3.0,
                "result": "won",
                "edge": 1.0,
                "price": -110,
            }
            for _ in range(10)
        ]
        model = fit_confidence_thresholds(rows)
        self.assertFalse(model["active"])
        self.assertEqual(model["high_min"], 3.5)
        self.assertEqual(model["moderate_min"], 1.5)
        self.assertEqual(len(model["buckets"]), 8)

    def test_learns_high_where_buckets_separate(self):
        rows: list[dict] = []
        # Small edges look like noise (~50%).
        for i in range(20):
            rows.append(
                {
                    "market_id": f"small-{i}",
                    "market_type": "spread",
                    "model_spread": -3.3,
                    "market_spread": -3.0,
                    "result": "won" if i % 2 == 0 else "lost",
                    "edge": 0.3,
                    "edge_points": 0.3,
                    "price": -110,
                    "model_probability": 0.52,
                    "bet_line": -3.0,
                    "closing_line": -3.0,
                }
            )
        # Mid edges also flat.
        for i in range(20):
            rows.append(
                {
                    "market_id": f"mid-{i}",
                    "market_type": "spread",
                    "model_spread": -4.8,
                    "market_spread": -3.0,
                    "result": "won" if i % 2 == 0 else "lost",
                    "edge": 1.8,
                    "edge_points": 1.8,
                    "price": -110,
                    "model_probability": 0.54,
                    "bet_line": -3.0,
                    "closing_line": -3.0,
                }
            )
        # 3.5+ separates strongly with +CLV.
        for i in range(24):
            rows.append(
                {
                    "market_id": f"big-{i}",
                    "market_type": "spread",
                    "model_spread": -7.0,
                    "market_spread": -3.0,
                    "result": "won" if i < 18 else "lost",
                    "edge": 4.0,
                    "edge_points": 4.0,
                    "price": -110,
                    "model_probability": 0.60,
                    "bet_line": -3.0,
                    "closing_line": -4.5,
                }
            )

        buckets = backtest_point_edge_buckets(rows)
        by_key = {b["key"]: b for b in buckets}
        self.assertGreaterEqual(by_key["3.5+"]["sample_size"], 12)
        self.assertGreater(by_key["3.5+"]["win_rate"], 60.0)
        self.assertIsNotNone(by_key["3.5+"]["average_clv"])
        self.assertIsNotNone(by_key["3.5+"]["roi_pct"])
        self.assertIsNotNone(by_key["3.5+"]["calibration"]["gap_pp"])

        model = fit_confidence_thresholds(buckets=buckets)
        self.assertTrue(model["active"])
        # Mid 1.8 edge should not force High if only 3.5+ separates.
        self.assertGreaterEqual(model["high_min"], 3.0)
        self.assertLessEqual(model["moderate_min"], model["high_min"])

        self.assertEqual(
            confidence_from_edge(
                edge_points=1.8, thresholds=model
            ),
            "Low" if model["moderate_min"] > 1.8 else "Moderate",
        )
        self.assertEqual(
            confidence_from_edge(
                edge_points=4.0, thresholds=model
            ),
            "High",
        )

    def test_diagnostics_payload_shape(self):
        diag = build_edge_confidence_diagnostics([])
        self.assertIn("thresholds", diag)
        self.assertIn("buckets", diag)
        self.assertEqual(len(diag["buckets"]), 8)


if __name__ == "__main__":
    unittest.main()
