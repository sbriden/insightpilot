"""
Tests for materiality gating of insights and findings.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.findings import (
    make_candidate_finding,
)
from app.analysis.insights.materiality import (
    is_material,
)
from app.analysis.insights.revenue_trends import (
    RULES as REVENUE_TREND_RULES,
)


class TestMateriality(unittest.TestCase):

    def test_small_revenue_growth_is_trivial(self):
        self.assertFalse(
            is_material(
                observed_value=0.021,
                baseline=0.0,
                magnitude=0.021,
                magnitude_unit="ratio",
                comparison="vs_prior_period",
                metric="overall_revenue_growth",
                severity="low",
                rule_id="revenue_growth",
            )
        )

    def test_material_revenue_growth(self):
        self.assertTrue(
            is_material(
                observed_value=0.12,
                baseline=0.0,
                magnitude=0.12,
                magnitude_unit="ratio",
                comparison="vs_prior_period",
                metric="overall_revenue_growth",
                severity="low",
                rule_id="revenue_growth",
            )
        )

    def test_stable_trend_is_trivial(self):
        self.assertFalse(
            is_material(
                observed_value=0.01,
                magnitude=0.01,
                magnitude_unit="ratio",
                comparison="vs_threshold",
                metric="trend_change",
                severity="low",
                rule_id="stable_trend",
            )
        )

    def test_high_concentration_remains_material(self):
        self.assertTrue(
            is_material(
                observed_value=0.55,
                baseline=0.40,
                magnitude=0.15,
                magnitude_unit="ratio",
                comparison="vs_threshold",
                metric="top10_revenue_share",
                severity="high",
                rule_id="high_concentration",
            )
        )

    def test_engine_skips_trivial_growth_insight(self):
        facts = {
            "overall_growth": 0.021,
            "trend_direction": "stable",
            "trend_change": 0.01,
            "anomaly_count": 0,
            "largest_positive_anomaly": None,
            "largest_negative_anomaly": None,
            "date_column": "month",
        }

        insights, findings = InsightEngine(
            REVENUE_TREND_RULES
        ).evaluate_with_findings(
            facts,
            analysis_type="revenue_trends",
        )

        insight_ids = {
            item.rule_id for item in insights
        }
        finding_ids = {
            item.rule_id for item in findings
        }

        self.assertNotIn(
            "revenue_growth",
            insight_ids,
        )
        self.assertNotIn(
            "stable_trend",
            insight_ids,
        )
        self.assertNotIn(
            "revenue_growth",
            finding_ids,
        )
        self.assertEqual(insights, [])
        self.assertEqual(findings, [])

    def test_engine_keeps_material_growth(self):
        facts = {
            "overall_growth": 0.18,
            "trend_direction": "growing",
            "trend_change": 0.12,
            "anomaly_count": 0,
            "largest_positive_anomaly": None,
            "largest_negative_anomaly": None,
            "date_column": "month",
        }

        insights, findings = InsightEngine(
            REVENUE_TREND_RULES
        ).evaluate_with_findings(
            facts,
            analysis_type="revenue_trends",
        )

        insight_ids = {
            item.rule_id for item in insights
        }

        self.assertIn(
            "revenue_growth",
            insight_ids,
        )
        self.assertIn(
            "accelerating_trend",
            insight_ids,
        )
        self.assertTrue(findings)

    def test_make_candidate_finding_returns_none_when_trivial(
        self,
    ):
        finding = make_candidate_finding(
            analysis_type="revenue_trends",
            metric="overall_revenue_growth",
            observed_value=0.021,
            baseline=0.0,
            comparison="vs_prior_period",
            magnitude=0.021,
            magnitude_unit="ratio",
            evidence="Revenue increased by 2.1%.",
            rule_id="revenue_growth",
            severity="low",
        )

        self.assertIsNone(finding)


if __name__ == "__main__":
    unittest.main()
