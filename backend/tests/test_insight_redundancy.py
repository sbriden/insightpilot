"""
Tests for redundant Insight detection and consolidation.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_validated_findings
from app.analysis.insights.redundancy import (
    are_redundant,
    consolidate_redundant_insights,
    insight_direction,
    metric_family,
    redundancy_cluster_key,
    type_family,
)


def _scored_insight(
    *,
    insight_id: str,
    title: str,
    finding: str,
    metric: str,
    insight_type: str,
    magnitude: float,
    score: float,
    rule_id: str,
    analysis_type: str = "revenue_trends",
    importance: str = "medium",
    confidence: str = "high",
) -> dict:
    return {
        "insight_id": insight_id,
        "title": title,
        "finding": finding,
        "metric": metric,
        "insight_type": insight_type,
        "analysis_type": analysis_type,
        "magnitude": magnitude,
        "observed_value": magnitude,
        "baseline": 0.0,
        "magnitude_unit": "ratio",
        "dimensions": ["date"],
        "importance": importance,
        "confidence": confidence,
        "rule_id": rule_id,
        "scoring": {"total": score},
    }


class TestInsightRedundancy(unittest.TestCase):

    def test_revenue_decline_variants_are_same_cluster(self):
        variants = [
            _scored_insight(
                insight_id="a",
                title="Revenue Decline",
                finding="Revenue declined 15%.",
                metric="overall_revenue_growth",
                insight_type="growth_decline",
                magnitude=-0.15,
                score=72,
                rule_id="revenue_decline",
            ),
            _scored_insight(
                insight_id="b",
                title="Declining Revenue Trend",
                finding="Revenue declined significantly.",
                metric="trend_change",
                insight_type="trend",
                magnitude=-0.12,
                score=68,
                rule_id="declining_trend",
            ),
            _scored_insight(
                insight_id="c",
                title="Lower Quarterly Revenue",
                finding="Revenue was lower this quarter.",
                metric="overall_revenue_growth",
                insight_type="growth_decline",
                magnitude=-0.15,
                score=65,
                rule_id="quarterly_revenue_lower",
            ),
            _scored_insight(
                insight_id="d",
                title="Quarterly Revenue Decreased",
                finding="Quarterly revenue decreased.",
                metric="revenue_change",
                insight_type="growth_decline",
                magnitude=-0.14,
                score=60,
                rule_id="quarterly_decrease",
            ),
        ]

        for left, right in zip(variants, variants[1:]):
            self.assertTrue(
                are_redundant(left, right),
                msg=f"{left['insight_id']} vs {right['insight_id']}",
            )

        consolidated = consolidate_redundant_insights(variants)
        self.assertEqual(len(consolidated), 1)
        winner = consolidated[0]
        self.assertEqual(winner["insight_id"], "a")
        self.assertEqual(winner["redundancy"]["cluster_size"], 4)
        self.assertEqual(
            set(winner["redundancy"]["suppressed_insight_ids"]),
            {"b", "c", "d"},
        )
        self.assertFalse(winner["redundancy"]["suppressed"])

    def test_opposite_directions_are_not_redundant(self):
        decline = _scored_insight(
            insight_id="down",
            title="Revenue Decline",
            finding="Revenue declined 15%.",
            metric="overall_revenue_growth",
            insight_type="growth_decline",
            magnitude=-0.15,
            score=70,
            rule_id="revenue_decline",
        )
        growth = _scored_insight(
            insight_id="up",
            title="Revenue Growth",
            finding="Revenue increased 15%.",
            metric="overall_revenue_growth",
            insight_type="growth_decline",
            magnitude=0.15,
            score=70,
            rule_id="revenue_growth",
        )
        self.assertFalse(are_redundant(decline, growth))
        consolidated = consolidate_redundant_insights([decline, growth])
        self.assertEqual(len(consolidated), 2)

    def test_anomaly_not_collapsed_into_trend_decline(self):
        decline = _scored_insight(
            insight_id="decline",
            title="Revenue Decline",
            finding="Revenue declined 15%.",
            metric="overall_revenue_growth",
            insight_type="growth_decline",
            magnitude=-0.15,
            score=70,
            rule_id="revenue_decline",
        )
        drop = _scored_insight(
            insight_id="drop",
            title="Revenue Drop",
            finding="Revenue was unusually low in March.",
            metric="trend_deviation",
            insight_type="anomaly",
            magnitude=-0.35,
            score=75,
            rule_id="revenue_drop",
        )
        self.assertFalse(are_redundant(decline, drop))
        self.assertEqual(
            len(consolidate_redundant_insights([decline, drop])),
            2,
        )

    def test_keeps_highest_score(self):
        weak = _scored_insight(
            insight_id="weak",
            title="Soft decline wording",
            finding="Revenue was lower this quarter.",
            metric="overall_revenue_growth",
            insight_type="growth_decline",
            magnitude=-0.15,
            score=55,
            rule_id="soft",
        )
        strong = _scored_insight(
            insight_id="strong",
            title="Revenue Decline",
            finding="Revenue declined 15%.",
            metric="trend_change",
            insight_type="trend",
            magnitude=-0.15,
            score=81,
            rule_id="strong",
        )
        consolidated = consolidate_redundant_insights([weak, strong])
        self.assertEqual(consolidated[0]["insight_id"], "strong")

    def test_metric_and_type_families(self):
        self.assertEqual(
            metric_family("overall_revenue_growth", "revenue_trends"),
            "revenue_momentum",
        )
        self.assertEqual(
            metric_family("trend_change", "revenue_trends"),
            "revenue_momentum",
        )
        self.assertEqual(type_family("trend"), "growth_decline")
        self.assertEqual(type_family("growth_decline"), "growth_decline")
        self.assertEqual(type_family("anomaly"), "anomaly")

    def test_direction_from_magnitude_and_text(self):
        self.assertEqual(
            insight_direction({"magnitude": -0.1}),
            "down",
        )
        self.assertEqual(
            insight_direction({"magnitude": 0.1}),
            "up",
        )
        self.assertEqual(
            insight_direction(
                {
                    "title": "Revenue was lower this quarter",
                    "finding": "Quarterly revenue decreased.",
                }
            ),
            "down",
        )

    def test_promote_path_consolidates_redundant_findings(self):
        findings = [
            make_candidate_finding(
                analysis_type="revenue_trends",
                metric="overall_revenue_growth",
                observed_value=-0.15,
                baseline=0.0,
                comparison="vs_prior_period",
                magnitude=-0.15,
                magnitude_unit="ratio",
                evidence="Revenue declined 15%.",
                confidence="high",
                importance="high",
                source_columns=["revenue", "order_date"],
                relevant_dimensions=["date"],
                rule_id="revenue_decline",
                severity="high",
                title="Revenue Decline",
            ),
            make_candidate_finding(
                analysis_type="revenue_trends",
                metric="trend_change",
                observed_value=-0.12,
                baseline=-0.05,
                comparison="vs_threshold",
                magnitude=-0.07,
                magnitude_unit="ratio",
                evidence="Revenue declined significantly.",
                confidence="high",
                importance="medium",
                source_columns=["revenue", "order_date"],
                relevant_dimensions=["date"],
                rule_id="declining_trend",
                severity="medium",
                title="Declining Revenue Trend",
            ),
            make_candidate_finding(
                analysis_type="revenue_trends",
                metric="overall_revenue_growth",
                observed_value=-0.15,
                baseline=0.0,
                comparison="vs_prior_period",
                magnitude=-0.15,
                magnitude_unit="ratio",
                evidence="Revenue was lower this quarter.",
                confidence="medium",
                importance="medium",
                source_columns=["revenue", "order_date"],
                relevant_dimensions=["date"],
                rule_id="quarterly_lower",
                severity="medium",
                title="Lower Quarterly Revenue",
            ),
        ]
        self.assertTrue(all(item is not None for item in findings))

        promoted = promote_validated_findings(findings)
        self.assertEqual(len(promoted), 1)
        self.assertGreaterEqual(
            promoted[0]["redundancy"]["cluster_size"],
            2,
        )
        self.assertTrue(
            promoted[0]["redundancy"]["suppressed_insight_ids"]
            or promoted[0]["redundancy"]["suppressed_rule_ids"]
        )

    def test_product_loss_count_and_rate_are_redundant(self):
        """
        Product Performance often emits both:
        - Loss-Making Products (negative_product_count)
        - High Product Loss Rate (negative_product_rate)
        Those are the same loss-making story.
        """

        count_insight = {
            "insight_id": "product_performance:negative_products",
            "title": "Loss-Making Products",
            "finding": (
                "12 products (24.0% of products) generated "
                "negative profit, contributing $48000 in "
                "aggregate losses."
            ),
            "metric": "negative_product_count",
            "insight_type": "growth_decline",
            "analysis_type": "product_performance",
            "magnitude": 12.0,
            "observed_value": 12,
            "baseline": 0,
            "magnitude_unit": "count",
            "dimensions": ["product"],
            "importance": "medium",
            "confidence": "high",
            "rule_id": "negative_products",
            "scoring": {"total": 64.0},
        }
        rate_insight = {
            "insight_id": "product_performance:high_negative_product_rate",
            "title": "High Product Loss Rate",
            "finding": (
                "24.0% of products generated negative profit, "
                "suggesting a broader pricing or cost-structure issue."
            ),
            "metric": "negative_product_rate",
            "insight_type": "growth_decline",
            "analysis_type": "product_performance",
            "magnitude": 0.04,
            "observed_value": 0.24,
            "baseline": 0.20,
            "magnitude_unit": "ratio",
            "dimensions": ["product"],
            "importance": "high",
            "confidence": "high",
            "rule_id": "high_negative_product_rate",
            "scoring": {"total": 71.0},
        }

        self.assertEqual(
            metric_family(
                "negative_product_count",
                "product_performance",
                rule_id="negative_products",
                title="Loss-Making Products",
            ),
            "loss_making_products",
        )
        self.assertEqual(
            metric_family(
                "negative_product_rate",
                "product_performance",
                rule_id="high_negative_product_rate",
                title="High Product Loss Rate",
            ),
            "loss_making_products",
        )
        self.assertTrue(are_redundant(count_insight, rate_insight))

        consolidated = consolidate_redundant_insights(
            [count_insight, rate_insight]
        )
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(
            consolidated[0]["insight_id"],
            "product_performance:high_negative_product_rate",
        )
        self.assertEqual(
            consolidated[0]["redundancy"]["suppressed_insight_ids"],
            ["product_performance:negative_products"],
        )

    def test_loss_making_not_collapsed_with_low_margin(self):
        loss = {
            "insight_id": "loss",
            "title": "Loss-Making Products",
            "metric": "negative_product_count",
            "insight_type": "growth_decline",
            "analysis_type": "product_performance",
            "magnitude": 5,
            "dimensions": ["product"],
            "rule_id": "negative_products",
            "scoring": {"total": 60},
        }
        low_margin = {
            "insight_id": "margin",
            "title": "Low-Margin Products",
            "metric": "low_margin_product_rate",
            "insight_type": "growth_decline",
            "analysis_type": "product_performance",
            "magnitude": 0.05,
            "dimensions": ["product"],
            "rule_id": "low_margin_products",
            "scoring": {"total": 60},
        }
        self.assertFalse(are_redundant(loss, low_margin))

    def test_cross_module_loss_making_products_are_redundant(self):
        """
        Product Performance and Profitability both emit
        Loss-Making Products with the same numbers.
        """

        product_perf = {
            "insight_id": "product_performance:negative_products",
            "title": "Loss-Making Products",
            "category": "Product",
            "finding": (
                "301 products (16.2% of products) generated "
                "negative profit, contributing $77,263 in "
                "aggregate losses."
            ),
            "metric": "negative_product_count",
            "insight_type": "growth_decline",
            "analysis_type": "product_performance",
            "magnitude": 301.0,
            "observed_value": 301,
            "baseline": 0,
            "magnitude_unit": "count",
            "dimensions": ["product"],
            "importance": "medium",
            "confidence": "low",
            "rule_id": "negative_products",
            "scoring": {"total": 67.6},
        }
        profitability = {
            "insight_id": "profitability:negative_products",
            "title": "Loss-Making Products",
            "category": "Profitability",
            "finding": (
                "301 products (16.2% of products) generated "
                "negative profit, contributing $77,263 in "
                "aggregate losses."
            ),
            "metric": "negative_product_count",
            "insight_type": "comparison",
            "analysis_type": "profitability",
            "magnitude": 301.0,
            "observed_value": 301,
            "baseline": 0,
            "magnitude_unit": "count",
            "dimensions": ["product"],
            "importance": "medium",
            "confidence": "low",
            "rule_id": "negative_products",
            "scoring": {"total": 67.1},
        }

        self.assertTrue(are_redundant(product_perf, profitability))
        consolidated = consolidate_redundant_insights(
            [product_perf, profitability]
        )
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(
            consolidated[0]["insight_id"],
            "product_performance:negative_products",
        )
        self.assertEqual(
            consolidated[0]["redundancy"]["suppressed_insight_ids"],
            ["profitability:negative_products"],
        )

    def test_different_analysis_types_stay_separate(self):
        revenue = _scored_insight(
            insight_id="rev",
            title="Revenue Decline",
            finding="Revenue declined 15%.",
            metric="overall_revenue_growth",
            insight_type="growth_decline",
            magnitude=-0.15,
            score=70,
            rule_id="revenue_decline",
            analysis_type="revenue_trends",
        )
        customer = _scored_insight(
            insight_id="cust",
            title="Customer Revenue Decline",
            finding="Customer revenue declined 15%.",
            metric="revenue_change",
            insight_type="growth_decline",
            magnitude=-0.15,
            score=70,
            rule_id="customer_decline",
            analysis_type="customer_performance",
        )
        self.assertNotEqual(
            redundancy_cluster_key(revenue),
            redundancy_cluster_key(customer),
        )


if __name__ == "__main__":
    unittest.main()
