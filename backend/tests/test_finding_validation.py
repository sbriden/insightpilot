"""
Tests for finding validation and Insight eligibility separation.

Pipeline: Candidate Finding → Validated Finding → Insight
"""

from __future__ import annotations

import unittest

from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding
from app.analysis.insights.validation import (
    REQUIRED_VALIDATED_FINDING_KEYS,
    insight_eligible_findings,
    is_insight_eligible,
    validate_finding,
    validate_findings,
)


class TestFindingValidation(unittest.TestCase):

    def test_low_severity_trend_validates_but_not_insight(self):
        """
        Mild / routine observations can be valid findings without
        becoming Insights (e.g. modest revenue growth).
        """

        finding = make_candidate_finding(
            analysis_type="revenue_trends",
            metric="overall_revenue_growth",
            observed_value=0.08,
            baseline=0.0,
            comparison="vs_prior_period",
            magnitude=0.08,
            magnitude_unit="ratio",
            evidence="Revenue increased 8.0%.",
            confidence=0.85,
            source_columns=["revenue", "order_date"],
            rule_id="revenue_growth",
            severity="low",
            title="Revenue Growth",
        )
        self.assertIsNotNone(finding)

        validated = validate_finding(finding)
        self.assertIsNotNone(validated)
        self.assertEqual(validated.stage, "validated")
        self.assertFalse(validated.insight_eligible)
        self.assertEqual(
            validated.insight_eligibility_reason,
            "insufficient_business_importance",
        )
        self.assertTrue(
            REQUIRED_VALIDATED_FINDING_KEYS
            <= set(validated.to_dict())
        )

        self.assertIsNone(promote_finding(finding))
        self.assertIsNotNone(
            promote_finding(
                finding,
                require_insight_eligible=False,
            )
        )

    def test_concentration_risk_is_insight_eligible(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.07,
            magnitude_unit="ratio",
            evidence=(
                "The top 10 customers generate 47% of revenue, "
                "creating significant customer concentration risk."
            ),
            confidence=0.9,
            source_columns=["customer_id", "revenue"],
            relevant_dimensions=["customer"],
            rule_id="high_concentration",
            severity="high",
            title="High Revenue Concentration",
        )
        self.assertIsNotNone(finding)

        validated = validate_finding(finding)
        self.assertIsNotNone(validated)
        self.assertTrue(validated.insight_eligible)
        self.assertEqual(
            validated.insight_eligibility_reason,
            "importance_high",
        )

        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        self.assertIn("47%", insight.finding)

    def test_explicit_insight_eligible_override(self):
        finding = make_candidate_finding(
            analysis_type="revenue_trends",
            metric="overall_revenue_growth",
            observed_value=0.12,
            baseline=0.0,
            comparison="vs_prior_period",
            magnitude=0.12,
            magnitude_unit="ratio",
            evidence="Revenue increased 12%.",
            confidence=0.9,
            source_columns=["revenue"],
            rule_id="revenue_growth",
            severity="low",
            title="Revenue Growth",
            insight_eligible=True,
        )
        self.assertIsNotNone(finding)
        self.assertTrue(is_insight_eligible(validate_finding(finding)))
        self.assertIsNotNone(promote_finding(finding))

    def test_insight_eligible_findings_filters(self):
        low = make_candidate_finding(
            analysis_type="revenue_trends",
            metric="overall_revenue_growth",
            observed_value=0.08,
            magnitude=0.08,
            magnitude_unit="ratio",
            comparison="vs_prior_period",
            evidence="Revenue increased 8%.",
            confidence=0.8,
            source_columns=["revenue"],
            severity="low",
            rule_id="revenue_growth",
            title="Revenue Growth",
        )
        high = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            magnitude=0.07,
            magnitude_unit="ratio",
            comparison="vs_threshold",
            evidence="Top 10 share is 47%.",
            confidence=0.9,
            source_columns=["revenue"],
            severity="high",
            rule_id="high_concentration",
            title="High Concentration",
        )

        validated = validate_findings([low, high])
        self.assertEqual(len(validated), 2)

        eligible = insight_eligible_findings(validated)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(
            eligible[0]["rule_id"],
            "high_concentration",
        )

    def test_incomplete_candidate_fails_validation(self):
        self.assertIsNone(
            validate_finding(
                {
                    "id": "x",
                    "analysis_type": "revenue_trends",
                    "metric": "overall_revenue_growth",
                    "observed_value": None,
                    "evidence": "missing value",
                    "confidence": 0.9,
                    "source_columns": ["revenue"],
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
