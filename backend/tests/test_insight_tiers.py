"""
Tests for Insight tiers (Critical / Important / Supporting).
"""

from __future__ import annotations

import unittest

from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding
from app.analysis.insights.scoring import sort_insights_by_score
from app.analysis.insights.tiers import (
    InsightTier,
    TIER_LABELS,
    normalize_tier,
    resolve_insight_tier,
)


class TestInsightTiers(unittest.TestCase):

    def test_normalize_tier(self):
        self.assertEqual(normalize_tier("critical"), "critical")
        self.assertEqual(normalize_tier("Tier 1"), "critical")
        self.assertEqual(normalize_tier(2), "important")
        self.assertEqual(normalize_tier("supporting"), "supporting")

    def test_critical_examples(self):
        cases = [
            {
                "title": "Major Revenue Decline",
                "finding": "Revenue declined 18% vs prior period.",
                "metric": "overall_revenue_growth",
                "insight_type": "growth_decline",
                "rule_id": "revenue_decline",
                "importance": "high",
                "observed_value": -0.18,
                "magnitude": -0.18,
                "magnitude_unit": "ratio",
            },
            {
                "title": "High Revenue Concentration",
                "finding": "Top 10 customers represent 47% of revenue.",
                "metric": "top10_revenue_share",
                "insight_type": "concentration",
                "rule_id": "high_concentration",
                "importance": "high",
                "observed_value": 0.47,
                "magnitude": 0.07,
                "magnitude_unit": "ratio",
            },
            {
                "title": "High Product Loss Rate",
                "finding": "24% of products generated negative profit.",
                "metric": "negative_product_rate",
                "insight_type": "risk",
                "rule_id": "high_negative_product_rate",
                "importance": "high",
                "observed_value": 0.24,
                "magnitude": 0.04,
                "magnitude_unit": "ratio",
            },
            {
                "title": "Revenue Anomaly",
                "finding": "Major operational anomaly in March revenue.",
                "metric": "anomaly_count",
                "insight_type": "anomaly",
                "rule_id": "revenue_anomaly",
                "importance": "medium",
                "observed_value": 3,
                "magnitude": 3,
                "magnitude_unit": "count",
            },
            {
                "title": "Material Customer Churn",
                "finding": "Segment X shows material customer churn.",
                "metric": "churn_rate",
                "insight_type": "risk",
                "rule_id": "segment_churn",
                "importance": "high",
                "observed_value": 0.22,
                "magnitude": 0.14,
                "magnitude_unit": "ratio",
            },
        ]
        for case in cases:
            self.assertEqual(
                resolve_insight_tier(case),
                InsightTier.CRITICAL.value,
                msg=case["title"],
            )

    def test_important_examples(self):
        cases = [
            {
                "title": "Regional Performance Difference",
                "finding": "Northeast revenue growth exceeds South by 12%.",
                "metric": "regional_growth_gap",
                "insight_type": "segment_difference",
                "rule_id": "regional_gap",
                "importance": "medium",
                "observed_value": 0.12,
                "magnitude": 0.12,
                "magnitude_unit": "ratio",
            },
            {
                "title": "Cross-Sell Opportunity",
                "finding": "Strong product growth opportunity identified.",
                "metric": "cross_sell_score",
                "insight_type": "opportunity",
                "rule_id": "high_confidence_cross_sell",
                "importance": "medium",
                "observed_value": 12,
                "magnitude": 12,
                "magnitude_unit": "count",
            },
            {
                "title": "Emerging Revenue Trend",
                "finding": "Meaningful emerging upward trend in revenue.",
                "metric": "trend_change",
                "insight_type": "trend",
                "rule_id": "emerging_trend",
                "importance": "medium",
                "observed_value": 0.08,
                "magnitude": 0.08,
                "magnitude_unit": "ratio",
            },
        ]
        for case in cases:
            self.assertEqual(
                resolve_insight_tier(case),
                InsightTier.IMPORTANT.value,
                msg=case["title"],
            )

    def test_supporting_examples(self):
        cases = [
            {
                "title": "Average Revenue per Transaction",
                "finding": "Revenue has an average of $1,250 per transaction.",
                "metric": "average_revenue_per_transaction",
                "insight_type": "comparison",
                "rule_id": "average_revenue",
                "importance": "medium",
                "observed_value": 1250,
                "magnitude": 1250,
                "magnitude_unit": "currency",
            },
            {
                "title": "Diversified Revenue Base",
                "finding": "Top 10 customers generate only 18% of revenue.",
                "metric": "top10_revenue_share",
                "insight_type": "concentration",
                "rule_id": "low_concentration",
                "importance": "low",
                "observed_value": 0.18,
                "magnitude": -0.07,
                "magnitude_unit": "ratio",
            },
            {
                "title": "Modest Revenue Growth",
                "finding": "Minor upward trend of 3%.",
                "metric": "trend_change",
                "insight_type": "trend",
                "rule_id": "modest_growth",
                "importance": "low",
                "observed_value": 0.03,
                "magnitude": 0.03,
                "magnitude_unit": "ratio",
            },
        ]
        for case in cases:
            self.assertEqual(
                resolve_insight_tier(case),
                InsightTier.SUPPORTING.value,
                msg=case["title"],
            )

    def test_sort_orders_by_tier_then_score(self):
        ranked = sort_insights_by_score(
            [
                {
                    "insight_id": "support",
                    "tier": "supporting",
                    "scoring": {"total": 90},
                    "metric": "average",
                },
                {
                    "insight_id": "critical_low_score",
                    "tier": "critical",
                    "scoring": {"total": 60},
                    "metric": "decline",
                },
                {
                    "insight_id": "important",
                    "tier": "important",
                    "scoring": {"total": 80},
                    "metric": "opportunity",
                },
                {
                    "insight_id": "critical_high_score",
                    "tier": "critical",
                    "scoring": {"total": 85},
                    "metric": "concentration",
                },
            ]
        )
        self.assertEqual(
            [item["insight_id"] for item in ranked],
            [
                "critical_high_score",
                "critical_low_score",
                "important",
                "support",
            ],
        )

    def test_promote_assigns_tier(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.07,
            magnitude_unit="ratio",
            evidence="Top 10 customers represent 47% of revenue.",
            confidence="high",
            importance="high",
            source_columns=["customer_id", "revenue"],
            relevant_dimensions=["customer"],
            rule_id="high_concentration",
            severity="high",
            title="High Revenue Concentration",
        )
        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        self.assertEqual(insight.tier, InsightTier.CRITICAL.value)
        payload = insight.to_dict()
        self.assertEqual(payload["tier"], "critical")
        self.assertEqual(
            TIER_LABELS[payload["tier"]],
            "Tier 1 — Critical",
        )


if __name__ == "__main__":
    unittest.main()
