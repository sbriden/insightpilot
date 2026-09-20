"""
Tests for the standardized promoted Insight model.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import (
    ESTIMATED_FIELDS,
    FACT_FIELDS,
    INSIGHT_TYPES,
    INTERPRETIVE_FIELDS,
    REQUIRED_INSIGHT_KEYS,
    Insight,
    InsightCategory,
    InsightType,
    collect_promoted_insights_from_dashboards,
    infer_insight_type,
    normalize_category,
    promote_finding,
    promote_validated_findings,
    serialize_insight,
)


class TestStandardInsightModel(unittest.TestCase):

    def _sample_finding(self):
        return make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.55,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.15,
            magnitude_unit="ratio",
            evidence=(
                "The top 10 customers generate 55.0% "
                "of total revenue."
            ),
            confidence=0.9,
            relevant_dimensions=["customer"],
            source_columns=["customer_id", "revenue"],
            rule_id="high_concentration",
            severity="high",
            title="High Revenue Concentration",
        )

    def test_required_keys_cover_contract(self):
        expected = {
            "insight_id",
            "title",
            "category",
            "insight_type",
            "finding",
            "metric",
            "observed_value",
            "baseline",
            "magnitude",
            "dimensions",
            "evidence",
            "confidence",
            "importance",
            "tier",
            "business_impact",
            "ai_interpretation",
            "potential_drivers",
            "recommendation",
            "explanation",
            "source_columns",
            "analysis_type",
            "calculation",
            "scoring",
        }
        self.assertEqual(REQUIRED_INSIGHT_KEYS, expected)
        self.assertTrue(
            FACT_FIELDS.isdisjoint(INTERPRETIVE_FIELDS)
        )
        self.assertTrue(
            ESTIMATED_FIELDS.isdisjoint(INTERPRETIVE_FIELDS)
        )
        self.assertEqual(
            INTERPRETIVE_FIELDS,
            {
                "ai_interpretation",
                "potential_drivers",
                "recommendation",
                "explanation",
            },
        )

    def test_insight_types_catalog_is_domain_agnostic(self):
        expected = (
            "trend",
            "growth_decline",
            "anomaly",
            "concentration",
            "comparison",
            "segment_difference",
            "contribution",
            "distribution",
            "relationship",
            "opportunity",
            "risk",
        )
        self.assertEqual(INSIGHT_TYPES, expected)
        self.assertNotIn("performance", INSIGHT_TYPES)
        self.assertNotIn("other", INSIGHT_TYPES)

    def test_promote_finding_shape(self):
        finding = self._sample_finding()
        self.assertIsNotNone(finding)

        insight = promote_finding(
            finding,
            category="Customer Concentration",
            business_impact="Material concentration risk",
            potential_drivers=[
                "Top-account dependence",
                "Limited mid-market coverage",
            ],
            recommendation=(
                "Review diversification options with sales."
            ),
        )

        self.assertIsInstance(insight, Insight)
        payload = insight.to_dict()

        self.assertTrue(
            REQUIRED_INSIGHT_KEYS <= set(payload)
        )
        self.assertEqual(
            payload["insight_id"],
            "customer_concentration:high_concentration",
        )
        self.assertEqual(
            payload["title"],
            "High Revenue Concentration",
        )
        self.assertEqual(
            payload["category"],
            InsightCategory.CUSTOMER.value,
        )
        self.assertEqual(
            payload["insight_type"],
            InsightType.CONCENTRATION.value,
        )
        self.assertEqual(
            payload["finding"],
            finding.evidence.summary,
        )
        self.assertIsInstance(payload["evidence"], dict)
        self.assertIn("metrics", payload["evidence"])
        self.assertTrue(payload["evidence"]["metrics"])
        self.assertEqual(
            payload["metric"],
            "top10_revenue_share",
        )
        self.assertEqual(payload["observed_value"], 0.55)
        self.assertEqual(payload["baseline"], 0.40)
        self.assertEqual(payload["magnitude"], 0.15)
        self.assertEqual(payload["dimensions"], ["customer"])
        self.assertEqual(payload["confidence"], "high")
        self.assertEqual(
            payload["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertEqual(
            payload["analysis_type"],
            "customer_concentration",
        )
        self.assertEqual(
            payload["business_impact"],
            "Material concentration risk",
        )
        self.assertEqual(
            payload["potential_drivers"],
            [
                "Top-account dependence",
                "Limited mid-market coverage",
            ],
        )
        self.assertEqual(
            payload["recommendation"],
            "Review diversification options with sales.",
        )
        self.assertEqual(
            payload["candidate_finding_id"],
            "customer_concentration:high_concentration",
        )
        self.assertEqual(
            payload["traceability"]["analysis_type"],
            "customer_concentration",
        )
        self.assertEqual(
            payload["traceability"]["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertEqual(
            payload["traceability"]["dimensions"],
            ["customer"],
        )
        self.assertIn("filters", payload["traceability"])
        self.assertIn("calculations", payload["traceability"])
        self.assertIn("dataset", payload["traceability"])
        dataset = payload["traceability"]["dataset"]
        self.assertEqual(
            dataset["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertEqual(
            dataset["analytical_method"]["analysis_type"],
            "customer_concentration",
        )

    def test_interpretive_fields_default_empty(self):
        insight = promote_finding(self._sample_finding())
        self.assertIsNotNone(insight)

        self.assertEqual(insight.potential_drivers, [])
        self.assertIsNone(insight.recommendation)
        self.assertIsNone(insight.business_impact)

        facts = insight.facts
        self.assertIn("metric", facts)
        self.assertNotIn("potential_drivers", facts)
        self.assertNotIn("recommendation", facts)

        interpretive = insight.interpretive
        self.assertEqual(
            set(interpretive),
            INTERPRETIVE_FIELDS,
        )
        self.assertEqual(
            interpretive["potential_drivers"],
            [],
        )
        self.assertIsNone(interpretive["recommendation"])
        self.assertIsNone(interpretive["explanation"])
        self.assertIsNone(interpretive["ai_interpretation"])

    def test_normalize_category_aliases(self):
        self.assertEqual(
            normalize_category("Revenue Trends"),
            InsightCategory.REVENUE.value,
        )
        self.assertEqual(
            normalize_category("Profitability"),
            InsightCategory.PROFITABILITY.value,
        )
        self.assertEqual(
            normalize_category("Operations"),
            InsightCategory.OPERATIONS.value,
        )
        self.assertEqual(
            normalize_category(""),
            InsightCategory.OTHER.value,
        )

    def test_infer_insight_type(self):
        self.assertEqual(
            infer_insight_type(
                analysis_type="revenue_trends"
            ),
            InsightType.TREND.value,
        )
        self.assertEqual(
            infer_insight_type(
                analysis_type="cross_sell"
            ),
            InsightType.OPPORTUNITY.value,
        )
        self.assertEqual(
            infer_insight_type(
                comparison="vs_prior_period"
            ),
            InsightType.GROWTH_DECLINE.value,
        )
        self.assertEqual(
            infer_insight_type(
                rule_id="high_concentration"
            ),
            InsightType.CONCENTRATION.value,
        )
        self.assertEqual(
            infer_insight_type(explicit="anomaly"),
            InsightType.ANOMALY.value,
        )
        self.assertEqual(
            infer_insight_type(explicit="segment difference"),
            InsightType.SEGMENT_DIFFERENCE.value,
        )
        self.assertEqual(
            infer_insight_type(explicit="risk"),
            InsightType.RISK.value,
        )
        self.assertEqual(
            infer_insight_type(explicit="relationship"),
            InsightType.RELATIONSHIP.value,
        )
        self.assertEqual(
            infer_insight_type(explicit="contribution"),
            InsightType.CONTRIBUTION.value,
        )
        self.assertEqual(
            infer_insight_type(explicit="distribution"),
            InsightType.DISTRIBUTION.value,
        )
        self.assertEqual(
            infer_insight_type(explicit="growth"),
            InsightType.GROWTH_DECLINE.value,
        )

    def test_serialize_insight_from_dict(self):
        payload = serialize_insight(
            {
                "insight_id": "demo:1",
                "title": "Demo",
                "category": "Revenue",
                "insight_type": "trend",
                "finding": "Revenue rose 8%.",
                "metric": "overall_growth",
                "observed_value": 0.08,
                "baseline": 0.0,
                "magnitude": 0.08,
                "dimensions": ["period"],
                "evidence": "Period-over-period growth.",
                "confidence": 0.85,
                "business_impact": None,
                "potential_drivers": "Seasonality",
                "recommendation": "",
                "source_columns": ["order_date", "revenue"],
                "analysis_type": "revenue_trends",
            }
        )

        self.assertIsNotNone(payload)
        self.assertEqual(
            payload["potential_drivers"],
            ["Seasonality"],
        )
        self.assertIsNone(payload["recommendation"])
        self.assertTrue(
            REQUIRED_INSIGHT_KEYS <= set(payload)
        )
        self.assertIn("candidate_finding_id", payload)
        self.assertIn("traceability", payload)
        self.assertEqual(
            payload["traceability"]["candidate_finding_id"],
            "demo:1",
        )

    def test_promote_infers_category_from_analysis_type(self):
        insight = promote_finding(self._sample_finding())
        self.assertIsNotNone(insight)
        self.assertEqual(
            insight.category,
            InsightCategory.CUSTOMER.value,
        )

    def test_collect_promoted_with_recommendation_overlay(self):
        dashboards = [
            {
                "id": "customer_concentration",
                "insights": [
                    {
                        "id": "high_concentration",
                        "category": "Customer Concentration",
                        "recommended_action": (
                            "Build a diversification plan."
                        ),
                    }
                ],
                "candidate_findings": [
                    self._sample_finding().to_dict()
                ],
            }
        ]

        promoted = collect_promoted_insights_from_dashboards(
            dashboards,
            scope_by_dashboard=True,
        )
        self.assertEqual(len(promoted), 1)
        self.assertEqual(
            promoted[0]["recommendation"],
            "Build a diversification plan.",
        )
        self.assertEqual(
            promoted[0]["potential_drivers"],
            [],
        )
        self.assertTrue(
            promoted[0]["insight_id"].startswith(
                "customer_concentration:"
            )
        )

    def test_promote_validated_findings_only_promotes_eligible(self):
        findings = [
            self._sample_finding().to_dict(),
            make_candidate_finding(
                analysis_type="revenue_trends",
                metric="overall_revenue_growth",
                observed_value=0.08,
                baseline=0.0,
                comparison="vs_prior_period",
                magnitude=0.08,
                magnitude_unit="ratio",
                evidence="Revenue increased 8%.",
                confidence=0.85,
                source_columns=["revenue"],
                rule_id="revenue_growth",
                severity="low",
                title="Revenue Growth",
            ).to_dict(),
        ]

        promoted = promote_validated_findings(findings)
        self.assertEqual(len(promoted), 1)
        self.assertEqual(
            promoted[0]["rule_id"],
            "high_concentration",
        )


if __name__ == "__main__":
    unittest.main()
