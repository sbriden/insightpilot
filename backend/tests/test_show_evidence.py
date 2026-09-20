"""
Tests for the Show Evidence UI contract on Insights.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.customer_concentration import (
    RULES as CONCENTRATION_RULES,
)
from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.evidence import (
    REQUIRED_EVIDENCE_KEYS,
    REQUIRED_SHOW_EVIDENCE_KEYS,
    SHOW_EVIDENCE_SECTIONS,
    build_structured_evidence,
)
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding


class TestShowEvidence(unittest.TestCase):

    def test_show_evidence_has_four_sections(self):
        evidence = build_structured_evidence(
            summary="Top 10 customers represent 47% of revenue.",
            metric_name="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            comparison="vs_threshold",
            source_columns=["customer_id", "revenue"],
            source_dataset="sales_orders",
            methodology=[
                "rank customers by revenue descending",
                "top10_share = top10_revenue / total_revenue",
            ],
            calculation={
                "analysis_type": "customer_concentration",
                "measure": "revenue",
                "dimension": "customer",
                "aggregation": "SUM",
                "grouping": "customer_id",
                "ranking": "descending revenue",
                "top_n": 10,
                "comparison": "top 10 / total",
            },
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
            ],
            breakdown=[
                {
                    "id": "c1",
                    "label": "Acme Corp",
                    "value": 1_200_000,
                    "unit": "currency",
                    "share": 0.12,
                },
                {
                    "id": "c2",
                    "label": "Globex",
                    "value": 900_000,
                    "unit": "currency",
                    "share": 0.09,
                },
            ],
            relevant_dimensions=["customer"],
            filters=[{"field": "revenue", "op": ">", "value": 0}],
        )

        payload = evidence.to_dict()
        self.assertTrue(REQUIRED_EVIDENCE_KEYS <= set(payload))
        show = payload["show_evidence"]
        self.assertEqual(
            set(show),
            set(SHOW_EVIDENCE_SECTIONS),
        )
        self.assertTrue(
            REQUIRED_SHOW_EVIDENCE_KEYS <= set(show)
        )

        # Summary — key numbers supporting the insight.
        self.assertEqual(
            show["summary"]["headline"],
            "Top 10 customers represent 47% of revenue.",
        )
        key_keys = {
            item["key"] for item in show["summary"]["key_numbers"]
        }
        self.assertIn("top10_revenue", key_keys)
        self.assertIn("total_revenue", key_keys)

        # Breakdown — relevant groups/entities.
        self.assertEqual(show["breakdown"]["dimension"], "customer")
        self.assertEqual(len(show["breakdown"]["entities"]), 2)
        self.assertEqual(
            show["breakdown"]["entities"][0]["label"],
            "Acme Corp",
        )

        # Methodology — how the result was calculated.
        self.assertTrue(show["methodology"]["steps"])
        self.assertEqual(
            show["methodology"]["calculation"]["top_n"],
            10,
        )
        self.assertEqual(
            show["methodology"]["calculation"]["aggregation"],
            "SUM",
        )

        # Source — dataset and columns.
        self.assertEqual(
            show["source"]["dataset"],
            "sales_orders",
        )
        self.assertEqual(
            show["source"]["columns"],
            ["customer_id", "revenue"],
        )
        self.assertTrue(show["source"]["filters"])
        self.assertTrue(evidence.can_show_evidence)

    def test_insight_preserves_show_evidence(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.07,
            magnitude_unit="ratio",
            evidence="Top 10 customers represent 47% of revenue.",
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
            ],
            confidence=0.9,
            source_columns=["customer_id", "revenue"],
            relevant_dimensions=["customer"],
            calculation={
                "analysis_type": "customer_concentration",
                "measure": "revenue",
                "dimension": "customer",
                "aggregation": "SUM",
                "grouping": "customer_id",
                "ranking": "descending revenue",
                "top_n": 10,
                "comparison": "top 10 / total",
            },
            rule_id="high_concentration",
            severity="high",
            title="Customer concentration",
        )
        self.assertIsNotNone(finding)

        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        show = insight.to_dict()["evidence"]["show_evidence"]
        self.assertTrue(
            REQUIRED_SHOW_EVIDENCE_KEYS <= set(show)
        )
        self.assertTrue(show["summary"]["key_numbers"])
        self.assertEqual(
            show["source"]["columns"],
            ["customer_id", "revenue"],
        )
        self.assertEqual(
            show["methodology"]["calculation"]["top_n"],
            10,
        )

    def test_concentration_engine_show_evidence(self):
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
            source_columns=["customer_id", "revenue"],
            relevant_dimensions=["customer"],
        )

        high = next(
            item
            for item in findings
            if item.rule_id == "high_concentration"
        )
        show = high.evidence.to_dict()["show_evidence"]
        self.assertTrue(show["summary"]["key_numbers"])
        self.assertTrue(show["methodology"]["steps"])
        self.assertEqual(
            show["methodology"]["calculation"]["comparison"],
            "top 10 / total",
        )
        self.assertEqual(
            show["source"]["columns"],
            ["customer_id", "revenue"],
        )
        self.assertEqual(
            show["breakdown"]["dimension"],
            "customer",
        )


if __name__ == "__main__":
    unittest.main()
