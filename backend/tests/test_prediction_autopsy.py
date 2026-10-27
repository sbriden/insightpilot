"""Smoke tests for prediction autopsy metrics helpers."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.prediction_autopsy import (
    _bootstrap_mean_ci,
    _probability_report,
)


class PredictionAutopsyTests(unittest.TestCase):
    def test_probability_report_perfect_forecast(self):
        samples = [(1.0, 1), (0.0, 0), (1.0, 1), (0.0, 0)] * 3
        report = _probability_report(samples)
        self.assertEqual(report["n"], 12)
        self.assertLess(report["brier"], 0.01)

    def test_bootstrap_ci_requires_sample(self):
        self.assertIsNone(_bootstrap_mean_ci([1.0, -1.0], seed=1))
        ci = _bootstrap_mean_ci(
            [0.1] * 10 + [-0.1] * 10,
            seed=1,
            as_roi=True,
        )
        assert ci is not None
        self.assertLessEqual(ci["low"], ci["high"])


if __name__ == "__main__":
    unittest.main()
