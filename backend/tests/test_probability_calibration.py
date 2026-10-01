"""Tests for probability calibration (Platt / isotonic / beta)."""

from __future__ import annotations

import unittest

import numpy as np

from app.analysis.insights.betting.probability_calibration import (
    apply_probability_calibration,
    calibrate_market_probability,
    collect_calibration_samples,
    fit_probability_calibration,
    reliability_metrics,
)
from app.analysis.insights.betting.slate import _enrich_event
from unittest.mock import patch


class ProbabilityCalibrationTests(unittest.TestCase):
    def _overconfident_samples(self, n: int = 80) -> list[dict]:
        """
        Model says ~0.57 but true win rate is ~0.52.
        """

        rng = np.random.default_rng(7)
        samples = []
        for i in range(n):
            raw = 0.57 + rng.normal(0, 0.02)
            raw = float(np.clip(raw, 0.51, 0.65))
            # True outcome ~52%.
            y = 1 if rng.random() < 0.52 else 0
            samples.append(
                {
                    "predicted_probability": raw,
                    "actual_result": y,
                    "market_type": "spread",
                    "edge": 4.0,
                    "confidence": "Moderate",
                }
            )
        return samples

    def test_collect_prefers_raw_probability(self):
        rows = [
            {
                "result": "won",
                "raw_model_probability": 0.57,
                "model_probability": 0.52,
                "market_type": "spread",
            },
            {
                "result": "lost",
                "model_probability": 0.60,
                "market_type": "total",
            },
            {"result": "push", "model_probability": 0.55},
        ]
        samples = collect_calibration_samples(rows)
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(
            samples[0]["predicted_probability"], 0.57
        )
        self.assertEqual(samples[0]["actual_result"], 1)

    def test_platt_pulls_overconfident_probs_down(self):
        samples = self._overconfident_samples(60)
        model = fit_probability_calibration(samples, method="platt")
        self.assertTrue(model["active"])
        self.assertEqual(model["method"], "platt")
        cal = apply_probability_calibration(0.57, model)
        assert cal is not None
        # Should move toward empirical ~52%.
        self.assertLess(float(cal), 0.57)
        self.assertGreater(float(cal), 0.45)
        metrics = model["metrics"]
        self.assertLessEqual(
            metrics["brier_calibrated"],
            metrics["brier_raw"] + 1e-6,
        )

    def test_isotonic_is_monotone(self):
        samples = self._overconfident_samples(50)
        # Add spread of predicted probs so isotonic has structure.
        for i, row in enumerate(samples):
            row["predicted_probability"] = 0.50 + (i % 10) * 0.02
            row["actual_result"] = 1 if (i % 10) < 5 else 0
        model = fit_probability_calibration(samples, method="isotonic")
        self.assertTrue(model["active"])
        self.assertEqual(model["method"], "isotonic")
        xs = np.linspace(0.5, 0.7, 9)
        ys = apply_probability_calibration(xs, model)
        assert ys is not None
        self.assertTrue(np.all(np.diff(ys) >= -1e-9))

    def test_identity_until_min_samples(self):
        samples = self._overconfident_samples(10)
        model = fit_probability_calibration(samples, method="auto")
        self.assertFalse(model["active"])
        self.assertEqual(model["method"], "identity")
        self.assertEqual(
            apply_probability_calibration(0.57, model), 0.57
        )

    def test_calibrate_market_probability_wrapper(self):
        samples = self._overconfident_samples(60)
        model = fit_probability_calibration(samples, method="platt")
        out = calibrate_market_probability(0.57, model=model)
        self.assertTrue(out["calibrated"])
        self.assertEqual(out["raw_model_probability"], 0.57)
        self.assertLess(out["model_probability"], 0.57)

    def test_enrich_applies_calibration_to_markets(self):
        samples = self._overconfident_samples(60)
        model = fit_probability_calibration(samples, method="platt")
        raw = {
            "event_id": "ip_game_cal",
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
                probability_calibration=model,
            )
        market = built["markets"][0]
        self.assertIsNotNone(market["raw_model_probability"])
        self.assertIsNotNone(market["model_probability"])
        self.assertTrue(market["probability_calibrated"])
        self.assertEqual(market["probability_calibration_method"], "platt")
        # Calibrated should differ from raw for overconfident model.
        self.assertNotAlmostEqual(
            market["raw_model_probability"],
            market["model_probability"],
            places=3,
        )

    def test_reliability_metrics_shape(self):
        p = np.array([0.55, 0.60, 0.70, 0.52])
        y = np.array([1.0, 0.0, 1.0, 0.0])
        metrics = reliability_metrics(p, y, p)
        self.assertIn("brier_raw", metrics)
        self.assertIn("ece_raw", metrics)
        self.assertEqual(metrics["n"], 4)


if __name__ == "__main__":
    unittest.main()
