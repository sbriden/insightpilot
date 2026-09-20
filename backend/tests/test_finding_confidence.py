"""
Tests for analytical finding confidence (high / medium / low).

Confidence reflects trust in the finding — not whether to act
on a recommendation.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.confidence import (
    CONFIDENCE_DESCRIPTIONS,
    CONFIDENCE_LEVELS,
    FindingConfidence,
    normalize_confidence,
    resolve_confidence,
)
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding


class TestFindingConfidence(unittest.TestCase):

    def test_catalog_and_descriptions(self):
        self.assertEqual(
            CONFIDENCE_LEVELS,
            ("high", "medium", "low"),
        )
        self.assertIn(
            "clear analytical signal",
            CONFIDENCE_DESCRIPTIONS["high"].lower(),
        )
        self.assertIn(
            "limitations",
            CONFIDENCE_DESCRIPTIONS["medium"].lower(),
        )
        self.assertIn(
            "insufficient evidence",
            CONFIDENCE_DESCRIPTIONS["low"].lower(),
        )

    def test_normalize_accepts_levels_and_legacy_floats(self):
        self.assertEqual(normalize_confidence("high"), "high")
        self.assertEqual(normalize_confidence("MEDIUM"), "medium")
        self.assertEqual(normalize_confidence("weak"), "low")
        self.assertEqual(normalize_confidence(0.95), "high")
        self.assertEqual(normalize_confidence(0.75), "medium")
        self.assertEqual(normalize_confidence(0.4), "low")
        self.assertEqual(normalize_confidence(None), "medium")

    def test_resolve_uses_sample_and_support(self):
        self.assertEqual(
            resolve_confidence(
                {"total_customers": 120},
                source_columns=["customer", "revenue"],
                evidence_metrics=[{"key": "share", "value": 0.5}],
            ),
            FindingConfidence.HIGH.value,
        )
        self.assertEqual(
            resolve_confidence(
                {"total_customers": 12},
                source_columns=["revenue"],
            ),
            FindingConfidence.MEDIUM.value,
        )
        self.assertEqual(
            resolve_confidence(
                {"total_customers": 4},
            ),
            FindingConfidence.LOW.value,
        )

    def test_confidence_is_about_finding_not_action(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            magnitude=0.07,
            magnitude_unit="ratio",
            comparison="vs_threshold",
            evidence="Top 10 share is 47%.",
            confidence="high",
            source_columns=["customer_id", "revenue"],
            severity="high",
            rule_id="high_concentration",
            title="Customer concentration",
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.confidence, "high")

        insight = promote_finding(
            finding,
            recommendation="Diversify the book.",
        )
        self.assertIsNotNone(insight)
        self.assertEqual(insight.confidence, "high")
        # Recommendation is interpretive and independent of confidence.
        self.assertEqual(
            insight.recommendation,
            "Diversify the book.",
        )
        payload = insight.to_dict()
        self.assertEqual(payload["confidence"], "high")
        self.assertIn("importance", payload)
        self.assertNotIn(
            "should take",
            CONFIDENCE_DESCRIPTIONS[payload["confidence"]].lower(),
        )

    def test_confidence_independent_of_importance(self):
        finding = make_candidate_finding(
            analysis_type="customer_performance",
            metric="churn_rate",
            observed_value=0.22,
            baseline=0.08,
            magnitude=0.14,
            magnitude_unit="ratio",
            comparison="vs_segment",
            evidence="Segment churn looks elevated.",
            confidence="medium",
            importance="high",
            source_columns=["segment", "status"],
            rule_id="segment_churn",
            title="Segment churn",
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.confidence, "medium")
        self.assertEqual(finding.importance, "high")
        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        self.assertEqual(insight.confidence, "medium")
        self.assertEqual(insight.importance, "high")


if __name__ == "__main__":
    unittest.main()
