"""
Tests for deterministic analysis primitives.
"""

from __future__ import annotations

import unittest

import pandas as pd

from app.analysis.primitives import (
    add_rolling_baseline,
    add_share,
    classify_trend_direction,
    concentration_summary,
    corr_matrix,
    flag_iqr,
    flag_threshold,
    flag_zscore,
    group_delta,
    numeric_summary,
    outlier_summary,
    overall_change,
    pearson_corr,
    percent_change,
    percentile_table,
    period_over_period,
    relative_deviation,
    safe_ratio,
    segment_vs_rest,
    top_1_share,
    top_n_share,
    vs_benchmark,
    window_mean_change,
)


class TestChangePrimitives(unittest.TestCase):

    def test_safe_ratio_scalar_and_zero_denominator(self):
        self.assertEqual(safe_ratio(10, 2), 5.0)
        self.assertEqual(safe_ratio(10, 0), 0.0)
        self.assertEqual(safe_ratio(10, 0, fill=-1.0), -1.0)

    def test_safe_ratio_series(self):
        result = safe_ratio(
            pd.Series([10.0, 5.0, 1.0]),
            pd.Series([2.0, 0.0, 4.0]),
        )

        self.assertEqual(list(result), [5.0, 0.0, 0.25])

    def test_percent_change(self):
        self.assertEqual(percent_change(110, 100), 0.1)
        self.assertEqual(percent_change(90, 100), -0.1)
        self.assertEqual(percent_change(10, 0), 0.0)

    def test_period_over_period(self):
        series = pd.Series([100.0, 110.0, 99.0])
        result = period_over_period(series, fill=0.0)

        self.assertEqual(result.iloc[0], 0.0)
        self.assertAlmostEqual(result.iloc[1], 0.1)
        self.assertAlmostEqual(result.iloc[2], -0.1)

    def test_period_over_period_rejects_invalid_periods(self):
        with self.assertRaises(ValueError):
            period_over_period(pd.Series([1.0]), periods=0)

    def test_overall_change(self):
        self.assertAlmostEqual(
            overall_change(pd.Series([100.0, 120.0, 150.0])),
            0.5,
        )
        self.assertEqual(
            overall_change(pd.Series([10.0])),
            0.0,
        )


class TestSharePrimitives(unittest.TestCase):

    def setUp(self):
        self.df = pd.DataFrame(
            {
                "entity": ["a", "b", "c", "d"],
                "revenue": [40.0, 30.0, 20.0, 10.0],
            }
        )

    def test_add_share(self):
        result = add_share(self.df, "revenue")

        self.assertAlmostEqual(result["share"].sum(), 1.0)
        self.assertAlmostEqual(result.iloc[0]["share"], 0.4)
        # Input not mutated.
        self.assertNotIn("share", self.df.columns)

    def test_top_n_and_top_1_share(self):
        self.assertAlmostEqual(
            top_n_share(self.df, "revenue", n=2),
            0.7,
        )
        self.assertAlmostEqual(
            top_1_share(self.df, "revenue"),
            0.4,
        )

    def test_concentration_summary(self):
        summary = concentration_summary(
            self.df,
            "revenue",
            n=2,
        )

        self.assertEqual(summary["entity_count"], 4)
        self.assertEqual(summary["total"], 100.0)
        self.assertAlmostEqual(summary["top_n_share"], 0.7)
        self.assertAlmostEqual(summary["top_1_share"], 0.4)

    def test_empty_frame_concentration(self):
        summary = concentration_summary(
            pd.DataFrame(columns=["revenue"]),
            "revenue",
        )

        self.assertEqual(summary["entity_count"], 0)
        self.assertEqual(summary["top_n_share"], 0.0)


class TestComparePrimitives(unittest.TestCase):

    def test_group_delta(self):
        delta = group_delta(120, 100)

        self.assertEqual(delta["absolute"], 20.0)
        self.assertAlmostEqual(delta["relative"], 0.2)

    def test_vs_benchmark(self):
        gaps = vs_benchmark(
            pd.Series([0.1, 0.3, 0.2]),
            0.25,
        )

        self.assertAlmostEqual(gaps.iloc[0], -0.15)
        self.assertAlmostEqual(gaps.iloc[1], 0.05)

    def test_segment_vs_rest(self):
        df = pd.DataFrame(
            {
                "segment": ["A", "A", "B", "B"],
                "value": [10.0, 10.0, 5.0, 5.0],
            }
        )

        result = segment_vs_rest(
            df,
            df["segment"] == "A",
            "value",
            aggregation="sum",
        )

        self.assertEqual(result["segment_value"], 20.0)
        self.assertEqual(result["rest_value"], 10.0)
        self.assertAlmostEqual(
            result["relative_difference"],
            1.0,
        )
        self.assertAlmostEqual(
            result["segment_share_of_overall"],
            20 / 30,
        )


class TestDistributionPrimitives(unittest.TestCase):

    def test_numeric_summary(self):
        summary = numeric_summary(
            pd.Series([1.0, 2.0, 3.0, 4.0, None])
        )

        self.assertEqual(summary["count"], 4)
        self.assertEqual(summary["sum"], 10.0)
        self.assertEqual(summary["mean"], 2.5)
        self.assertEqual(summary["median"], 2.5)
        self.assertEqual(summary["missing"], 1)

    def test_percentile_table(self):
        table = percentile_table(
            pd.Series([0.0, 25.0, 50.0, 75.0, 100.0]),
            quantiles=(0.25, 0.5, 0.75),
        )

        self.assertIn("p25", table)
        self.assertIn("p50", table)
        self.assertIn("p75", table)
        self.assertEqual(table["p50"], 50.0)

    def test_empty_numeric_summary(self):
        summary = numeric_summary(pd.Series([None, None]))

        self.assertEqual(summary["count"], 0)
        self.assertEqual(summary["mean"], 0.0)


class TestOutlierPrimitives(unittest.TestCase):

    def test_flag_threshold(self):
        flags = flag_threshold(
            pd.Series([0.05, -0.25, 0.3]),
            abs_threshold=0.2,
        )

        self.assertEqual(list(flags), [False, True, True])

    def test_flag_iqr(self):
        # Clear high outlier.
        series = pd.Series(
            [10, 11, 12, 13, 14, 15, 100]
        )
        flags = flag_iqr(series)

        self.assertTrue(bool(flags.iloc[-1]))
        self.assertFalse(bool(flags.iloc[0]))

    def test_flag_zscore(self):
        # Tight cluster with one extreme outlier.
        series = pd.Series(
            [10.0, 10.1, 9.9, 10.0, 10.05, 9.95, 10.0, 50.0]
        )
        flags = flag_zscore(series, z=2.0)

        self.assertTrue(bool(flags.iloc[-1]))
        self.assertFalse(bool(flags.iloc[0]))

    def test_outlier_summary(self):
        series = pd.Series([1.0, 2.0, 100.0])
        flags = pd.Series([False, False, True])
        summary = outlier_summary(series, flags)

        self.assertEqual(summary["count"], 1)
        self.assertAlmostEqual(summary["rate"], 1 / 3)
        self.assertEqual(summary["max_flagged"], 100.0)


class TestTrendPrimitives(unittest.TestCase):

    def test_rolling_baseline_and_deviation(self):
        series = pd.Series(
            [10.0, 10.0, 10.0, 13.0]
        )
        baseline = add_rolling_baseline(
            series,
            window=3,
            shift=1,
        )
        deviation = relative_deviation(
            series,
            baseline,
        )

        # Fourth point vs mean of first three (=10).
        self.assertAlmostEqual(baseline.iloc[3], 10.0)
        self.assertAlmostEqual(deviation.iloc[3], 0.3)

    def test_classify_trend_direction(self):
        self.assertEqual(
            classify_trend_direction(0.1),
            "growing",
        )
        self.assertEqual(
            classify_trend_direction(-0.1),
            "declining",
        )
        self.assertEqual(
            classify_trend_direction(0.01),
            "stable",
        )

    def test_window_mean_change_growing(self):
        series = pd.Series(
            [10.0, 10.0, 10.0, 20.0, 20.0, 20.0]
        )
        result = window_mean_change(
            series,
            window=3,
        )

        self.assertTrue(result["sufficient_history"])
        self.assertEqual(result["previous"], 10.0)
        self.assertEqual(result["recent"], 20.0)
        self.assertAlmostEqual(result["change"], 1.0)
        self.assertEqual(result["direction"], "growing")

    def test_window_mean_change_insufficient_history(self):
        result = window_mean_change(
            pd.Series([1.0, 2.0, 3.0]),
            window=3,
        )

        self.assertFalse(result["sufficient_history"])
        self.assertEqual(result["direction"], "stable")


class TestRelationshipPrimitives(unittest.TestCase):

    def test_pearson_corr_perfect(self):
        x = pd.Series([1.0, 2.0, 3.0, 4.0])
        y = pd.Series([2.0, 4.0, 6.0, 8.0])

        self.assertAlmostEqual(
            pearson_corr(x, y),
            1.0,
        )

    def test_pearson_corr_insufficient_data(self):
        self.assertIsNone(
            pearson_corr(
                pd.Series([1.0, 2.0]),
                pd.Series([2.0, 4.0]),
                min_periods=3,
            )
        )

    def test_corr_matrix(self):
        df = pd.DataFrame(
            {
                "a": [1.0, 2.0, 3.0, 4.0],
                "b": [2.0, 4.0, 6.0, 8.0],
                "c": [4.0, 3.0, 2.0, 1.0],
            }
        )
        matrix = corr_matrix(df, ["a", "b", "c"])

        self.assertAlmostEqual(matrix.loc["a", "b"], 1.0)
        self.assertAlmostEqual(matrix.loc["a", "c"], -1.0)


if __name__ == "__main__":
    unittest.main()
