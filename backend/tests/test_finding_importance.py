"""
Importance vs Confidence — independent Insight dimensions.

Importance: how much the observation matters to the business.
Confidence: how strong the supporting evidence is.

Medium confidence must not erase a high-importance Insight.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.importance import (
    IMPORTANCE_DESCRIPTIONS,
    IMPORTANCE_LEVELS,
    FindingImportance,
    normalize_importance,
    resolve_importance,
)
from app.analysis.insights.insight import promote_finding
from app.analysis.insights.validation import (
    resolve_insight_eligibility,
    validate_finding,
)


class TestImportanceSeparateFromConfidence(unittest.TestCase):

    def test_catalog(self):
        self.assertEqual(IMPORTANCE_LEVELS, ("high", "medium", "low"))
        self.assertIn("business", IMPORTANCE_DESCRIPTIONS["high"].lower())

    def test_normalize_importance(self):
        self.assertEqual(normalize_importance("high"), "high")
        self.assertEqual(normalize_importance("CRITICAL"), "high")
        self.assertEqual(normalize_importance("warning"), "medium")
        self.assertEqual(normalize_importance(None), "medium")
        self.assertEqual(
            normalize_importance(FindingImportance.LOW),
            "low",
        )

    def test_resolve_prefers_explicit_over_severity(self):
        self.assertEqual(
            resolve_importance(explicit="high", severity="low"),
            "high",
        )
        self.assertEqual(
            resolve_importance(severity="high"),
            "high",
        )

    def test_northeast_revenue_decline_example(self):
        """
        Revenue declined 18% in the Northeast.
        Importance: High, Confidence: High
        """

        finding = make_candidate_finding(
            analysis_type="revenue_trends",
            metric="revenue_change",
            observed_value=-0.18,
            baseline=0.0,
            comparison="vs_prior_period",
            magnitude=-0.18,
            magnitude_unit="ratio",
            evidence=(
                "Revenue declined 18% in the Northeast."
            ),
            confidence="high",
            importance="high",
            source_columns=["region", "revenue", "order_date"],
            relevant_dimensions=["region"],
            rule_id="northeast_revenue_decline",
            title="Northeast revenue decline",
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.importance, "high")
        self.assertEqual(finding.confidence, "high")

        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        self.assertEqual(insight.importance, "high")
        self.assertEqual(insight.confidence, "high")

    def test_segment_churn_example_survives_medium_confidence(self):
        """
        Customers in Segment X appear to have unusually high churn.
        Importance: High, Confidence: Medium — still promoted.
        """

        finding = make_candidate_finding(
            analysis_type="customer_performance",
            metric="churn_rate",
            observed_value=0.22,
            baseline=0.08,
            comparison="vs_segment",
            magnitude=0.14,
            magnitude_unit="ratio",
            evidence=(
                "Customers in Segment X appear to have "
                "unusually high churn."
            ),
            confidence="medium",
            importance="high",
            source_columns=["customer_id", "segment", "status"],
            relevant_dimensions=["segment"],
            rule_id="segment_x_churn_anomaly",
            title="Elevated Segment X churn",
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.importance, "high")
        self.assertEqual(finding.confidence, "medium")

        validated = validate_finding(finding)
        self.assertIsNotNone(validated)
        self.assertTrue(validated.insight_eligible)
        self.assertEqual(validated.importance, "high")
        self.assertEqual(validated.confidence, "medium")

        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        self.assertEqual(insight.importance, "high")
        self.assertEqual(insight.confidence, "medium")
        payload = insight.to_dict()
        self.assertEqual(payload["importance"], "high")
        self.assertEqual(payload["confidence"], "medium")

    def test_eligibility_ignores_confidence(self):
        eligible, reason = resolve_insight_eligibility(
            {
                "importance": "high",
                "confidence": "low",
                "analysis_type": "revenue_trends",
                "severity": "low",
            }
        )
        self.assertTrue(eligible)
        self.assertEqual(reason, "importance_high")

        # Confidence alone never grants or denies eligibility.
        eligible_low_importance, reason_low = resolve_insight_eligibility(
            {
                "importance": "low",
                "confidence": "high",
                "analysis_type": "revenue_trends",
                "rule_id": "stable_trend_watch",
            }
        )
        self.assertFalse(eligible_low_importance)
        self.assertEqual(reason_low, "insufficient_business_importance")

    def test_importance_and_confidence_are_independent_fields(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.55,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.15,
            magnitude_unit="ratio",
            evidence="Top 10 share is 55%.",
            confidence="low",
            importance="high",
            source_columns=["customer_id", "revenue"],
            severity="high",
            rule_id="high_concentration",
            title="Concentration risk",
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.confidence, "low")
        self.assertEqual(finding.importance, "high")
        self.assertNotEqual(finding.confidence, finding.importance)


if __name__ == "__main__":
    unittest.main()
