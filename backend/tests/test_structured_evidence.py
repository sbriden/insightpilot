"""
Tests for machine-readable Insight evidence.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.customer_concentration import (
    RULES as CONCENTRATION_RULES,
)
from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.evidence import (
    REQUIRED_EVIDENCE_KEYS,
    REQUIRED_EVIDENCE_METRIC_KEYS,
    build_structured_evidence,
    serialize_evidence,
)
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding


class TestStructuredEvidence(unittest.TestCase):

    def test_build_structured_evidence_shape(self):
        evidence = build_structured_evidence(
            summary="Top 10 customers represent 47% of revenue.",
            metric_name="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.07,
            magnitude_unit="ratio",
            population=842,
            relevant_dimensions=["customer"],
            source_columns=["customer_id", "revenue"],
            filters=[{"field": "revenue", "op": ">", "value": 0}],
            methodology=[
                "top10_share = sum(top10 revenue) / total revenue",
            ],
            metrics=[
                {
                    "key": "top10_revenue",
                    "label": "Top 10 revenue",
                    "value": 4_700_000,
                    "unit": "currency",
                },
                {
                    "key": "total_revenue",
                    "label": "Total revenue",
                    "value": 10_000_000,
                    "unit": "currency",
                },
                {
                    "key": "total_customers",
                    "label": "Customer population",
                    "value": 842,
                    "unit": "count",
                },
                {
                    "key": "top10_share",
                    "label": "Top 10 customer share",
                    "value": 0.47,
                    "unit": "ratio",
                },
            ],
            supporting_records=[
                {"customer": "Acme", "revenue": 1_200_000},
            ],
        )

        payload = evidence.to_dict()
        self.assertTrue(
            REQUIRED_EVIDENCE_KEYS <= set(payload)
        )
        self.assertEqual(payload["metric"], "top10_revenue_share")
        self.assertEqual(payload["observed_value"], 0.47)
        self.assertEqual(payload["baseline"], 0.40)
        self.assertEqual(payload["comparison"], "vs_threshold")
        self.assertAlmostEqual(payload["difference"], 0.07)
        self.assertAlmostEqual(payload["percentage_change"], 0.175)
        self.assertEqual(payload["population"], 842)
        self.assertEqual(
            payload["relevant_dimensions"],
            ["customer"],
        )
        self.assertEqual(
            payload["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertTrue(payload["filters"])
        self.assertTrue(payload["methodology"])
        self.assertTrue(payload["supporting_records"])
        self.assertTrue(payload["metrics"])
        for metric in payload["metrics"]:
            self.assertTrue(
                REQUIRED_EVIDENCE_METRIC_KEYS <= set(metric)
            )

        keys = {item["key"] for item in payload["metrics"]}
        self.assertIn("top10_revenue", keys)
        self.assertIn("total_revenue", keys)
        self.assertIn("top10_share", keys)

    def test_insight_preserves_structured_evidence(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.07,
            magnitude_unit="ratio",
            evidence=(
                "Top 10 customers represent 47% of revenue."
            ),
            evidence_metrics=[
                {
                    "key": "top10_revenue",
                    "label": "Top 10 revenue",
                    "value": 4_700_000,
                    "unit": "currency",
                },
                {
                    "key": "total_revenue",
                    "label": "Total revenue",
                    "value": 10_000_000,
                    "unit": "currency",
                },
                {
                    "key": "total_customers",
                    "label": "Customer population",
                    "value": 842,
                    "unit": "count",
                },
                {
                    "key": "top10_share",
                    "label": "Top 10 customer share",
                    "value": 0.47,
                    "unit": "ratio",
                },
            ],
            confidence=0.9,
            source_columns=["customer_id", "revenue"],
            relevant_dimensions=["customer"],
            filters=[{"field": "period", "op": "=", "value": "2024"}],
            calculations=[
                "top10_share = top10_revenue / total_revenue",
            ],
            rule_id="high_concentration",
            severity="high",
            title="Customer concentration",
        )
        self.assertIsNotNone(finding)

        insight = promote_finding(
            finding,
            finding_text=(
                "Top 10 customers represent 47% of revenue."
            ),
        )
        self.assertIsNotNone(insight)

        payload = insight.to_dict()
        evidence = payload["evidence"]
        self.assertIsInstance(evidence, dict)
        self.assertTrue(
            REQUIRED_EVIDENCE_KEYS <= set(evidence)
        )
        self.assertEqual(evidence["metric"], "top10_revenue_share")
        self.assertEqual(evidence["observed_value"], 0.47)
        self.assertEqual(evidence["baseline"], 0.40)
        self.assertEqual(evidence["population"], 842)
        self.assertEqual(
            evidence["relevant_dimensions"],
            ["customer"],
        )
        self.assertEqual(
            evidence["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertTrue(evidence["methodology"])
        self.assertTrue(evidence["metrics"])

        by_key = {
            item["key"]: item
            for item in evidence["metrics"]
        }
        self.assertEqual(
            by_key["top10_revenue"]["value"],
            4_700_000,
        )
        self.assertEqual(
            by_key["total_revenue"]["value"],
            10_000_000,
        )
        self.assertEqual(
            by_key["total_customers"]["value"],
            842,
        )
        self.assertEqual(
            by_key["top10_share"]["value"],
            0.47,
        )
        self.assertEqual(
            payload["finding"],
            "Top 10 customers represent 47% of revenue.",
        )

    def test_string_evidence_normalizes_to_structured(self):
        payload = serialize_evidence(
            "Narrative only",
            observed_value=0.12,
            baseline=0.0,
            magnitude=0.12,
            magnitude_unit="ratio",
            metric_name="overall_growth",
            comparison="vs_prior_period",
            relevant_dimensions=["time"],
            source_columns=["revenue", "period"],
        )
        self.assertEqual(payload["summary"], "Narrative only")
        self.assertEqual(payload["metric"], "overall_growth")
        self.assertEqual(payload["observed_value"], 0.12)
        self.assertEqual(payload["comparison"], "vs_prior_period")
        self.assertEqual(payload["relevant_dimensions"], ["time"])
        self.assertEqual(
            payload["source_columns"],
            ["revenue", "period"],
        )
        self.assertTrue(payload["metrics"])
        keys = {item["key"] for item in payload["metrics"]}
        self.assertIn("overall_growth", keys)
        self.assertIn("baseline", keys)

    def test_evidence_is_numbers_not_only_narrative(self):
        evidence = build_structured_evidence(
            summary="Revenue grew.",
            metric_name="overall_growth",
            observed_value=1_200_000,
            baseline=1_000_000,
            comparison="vs_prior_period",
            magnitude=0.20,
            magnitude_unit="ratio",
        )
        payload = evidence.to_dict()
        self.assertTrue(evidence.has_numeric_support)
        self.assertEqual(payload["observed_value"], 1_200_000)
        self.assertEqual(payload["baseline"], 1_000_000)
        self.assertEqual(payload["difference"], 200_000)
        self.assertAlmostEqual(payload["percentage_change"], 0.20)
        # Narrative alone is insufficient — numbers are present.
        self.assertNotEqual(payload["summary"], "")
        self.assertIsNotNone(payload["observed_value"])

    def test_concentration_engine_emits_structured_evidence(self):
        facts = {
            "total_customers": 842,
            "top10_share": 0.47,
            "top10_revenue": 4_700_000,
            "total_revenue": 10_000_000,
            "top_customer_share": 0.18,
            "top_customer_revenue": 1_800_000,
        }

        _insights, findings = InsightEngine(
            CONCENTRATION_RULES
        ).evaluate_with_findings(
            facts,
            analysis_type="customer_concentration",
            source_columns=["Customer", "Revenue"],
            relevant_dimensions=["customer"],
        )

        high = next(
            item
            for item in findings
            if item.rule_id == "high_concentration"
        )
        evidence = high.evidence.to_dict()
        self.assertTrue(
            REQUIRED_EVIDENCE_KEYS <= set(evidence)
        )
        self.assertEqual(evidence["metric"], "top10_revenue_share")
        self.assertEqual(evidence["observed_value"], 0.47)
        self.assertEqual(evidence["population"], 842)
        self.assertEqual(
            evidence["source_columns"],
            ["Customer", "Revenue"],
        )
        self.assertEqual(
            evidence["relevant_dimensions"],
            ["customer"],
        )
        self.assertTrue(evidence["methodology"])
        self.assertTrue(evidence["metrics"])
        keys = {item["key"] for item in evidence["metrics"]}
        self.assertIn("top10_revenue", keys)
        self.assertIn("total_revenue", keys)
        self.assertIn("total_customers", keys)
        self.assertIn("top10_share", keys)

        insight = promote_finding(high)
        self.assertIsNotNone(insight)
        promoted = insight.to_dict()["evidence"]
        self.assertTrue(promoted["metrics"])
        self.assertEqual(promoted["population"], 842)
        self.assertEqual(
            promoted["source_columns"],
            ["Customer", "Revenue"],
        )


if __name__ == "__main__":
    unittest.main()
