"""
Tests for data-quality context on insight evidence.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.evidence import (
    DATA_QUALITY_EXCLUDED,
    DATA_QUALITY_INVALID,
    DATA_QUALITY_ISSUE_TYPES,
    DATA_QUALITY_MISSING,
    DATA_QUALITY_SAMPLE_SIZE,
    REQUIRED_SHOW_EVIDENCE_KEYS,
    build_structured_evidence,
)
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding


class TestEvidenceDataQuality(unittest.TestCase):

    def test_data_quality_section_shape(self):
        evidence = build_structured_evidence(
            summary="Revenue declined 22%.",
            metric_name="revenue_change",
            observed_value=-0.22,
            baseline=0.0,
            magnitude=-0.22,
            magnitude_unit="ratio",
            data_quality={
                "issues": [
                    {
                        "type": "missing_data",
                        "field": "order_date",
                        "rate": 0.18,
                        "count": 1_842,
                        "description": (
                            "18% of transactions have missing dates."
                        ),
                    },
                    {
                        "type": "excluded_records",
                        "count": 120,
                        "label": "Excluded voided orders",
                    },
                    {
                        "type": "duplicate_records",
                        "count": 14,
                    },
                    {
                        "type": "invalid_values",
                        "field": "revenue",
                        "count": 3,
                    },
                    {
                        "type": "sample_size",
                        "count": 28,
                        "description": (
                            "Only 28 complete periods available."
                        ),
                    },
                ],
                "affects_reliability": True,
            },
        )

        payload = evidence.to_dict()
        self.assertIn("data_quality", payload)
        dq = payload["data_quality"]
        self.assertTrue(dq["has_limitations"])
        self.assertTrue(dq["affects_reliability"])
        self.assertEqual(len(dq["issues"]), 5)

        types = {item["type"] for item in dq["issues"]}
        self.assertEqual(
            types,
            set(DATA_QUALITY_ISSUE_TYPES),
        )

        missing = next(
            item
            for item in dq["issues"]
            if item["type"] == DATA_QUALITY_MISSING
        )
        self.assertEqual(missing["field"], "order_date")
        self.assertAlmostEqual(missing["rate"], 0.18)
        self.assertEqual(missing["count"], 1_842)

        show = payload["show_evidence"]
        self.assertTrue(
            REQUIRED_SHOW_EVIDENCE_KEYS <= set(show)
        )
        self.assertIn("data_quality", show)
        self.assertTrue(show["data_quality"]["has_limitations"])
        self.assertTrue(evidence.can_show_evidence)

    def test_empty_data_quality_is_stable(self):
        evidence = build_structured_evidence(
            summary="Stable revenue.",
            observed_value=0.01,
        )
        dq = evidence.to_dict()["data_quality"]
        self.assertEqual(dq["issues"], [])
        self.assertEqual(dq["notes"], [])
        self.assertFalse(dq["has_limitations"])
        self.assertFalse(dq["affects_reliability"])

    def test_percentage_style_rate_normalizes(self):
        evidence = build_structured_evidence(
            data_quality={
                "issues": [
                    {
                        "type": "missing",
                        "field": "order_date",
                        "percentage": 18,
                    }
                ]
            }
        )
        issue = evidence.to_dict()["data_quality"]["issues"][0]
        self.assertEqual(issue["type"], DATA_QUALITY_MISSING)
        self.assertAlmostEqual(issue["rate"], 0.18)

    def test_insight_preserves_data_quality(self):
        finding = make_candidate_finding(
            analysis_type="revenue_trends",
            metric="revenue_change",
            observed_value=-0.22,
            baseline=0.0,
            comparison="vs_prior_period",
            magnitude=-0.22,
            magnitude_unit="ratio",
            evidence=build_structured_evidence(
                summary="Revenue declined 22%.",
                data_quality={
                    "issues": [
                        {
                            "type": DATA_QUALITY_MISSING,
                            "field": "order_date",
                            "rate": 0.18,
                            "description": (
                                "18% of transactions have missing dates."
                            ),
                        },
                        {
                            "type": DATA_QUALITY_SAMPLE_SIZE,
                            "count": 40,
                        },
                        {
                            "type": DATA_QUALITY_EXCLUDED,
                            "count": 50,
                        },
                        {
                            "type": DATA_QUALITY_INVALID,
                            "field": "revenue",
                            "count": 2,
                        },
                    ],
                    "notes": [
                        "Trend reliability reduced by missing dates."
                    ],
                    "affects_reliability": True,
                },
                source_columns=["revenue", "order_date"],
            ),
            confidence=0.7,
            source_columns=["revenue", "order_date"],
            severity="high",
            title="Revenue decline",
        )
        self.assertIsNotNone(finding)
        insight = promote_finding(finding)
        self.assertIsNotNone(insight)

        dq = insight.to_dict()["evidence"]["data_quality"]
        self.assertTrue(dq["affects_reliability"])
        self.assertTrue(dq["has_limitations"])
        self.assertEqual(len(dq["issues"]), 4)
        self.assertTrue(dq["notes"])
        show_dq = insight.to_dict()["evidence"]["show_evidence"][
            "data_quality"
        ]
        self.assertEqual(
            show_dq["issues"][0]["field"],
            "order_date",
        )


if __name__ == "__main__":
    unittest.main()
