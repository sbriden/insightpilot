"""
Tests for reproducible calculation specs on Insights.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.calculation import (
    REQUIRED_CALCULATION_KEYS,
    build_calculation_spec,
    serialize_calculation_spec,
)
from app.analysis.insights.customer_concentration import (
    RULES as CONCENTRATION_RULES,
)
from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding


class TestReproducibleCalculations(unittest.TestCase):

    def test_calculation_spec_shape(self):
        spec = build_calculation_spec(
            analysis_type="customer_concentration",
            measure="revenue",
            dimension="customer",
            aggregation="SUM",
            grouping="customer_id",
            ranking="descending revenue",
            top_n=10,
            comparison="top 10 / total",
            source_columns=["customer_id", "revenue"],
        )
        payload = spec.to_dict()
        self.assertTrue(
            REQUIRED_CALCULATION_KEYS <= set(payload)
        )
        self.assertEqual(payload["measure"], "revenue")
        self.assertEqual(payload["aggregation"], "SUM")
        self.assertEqual(payload["grouping"], "customer_id")
        self.assertEqual(payload["top_n"], 10)
        self.assertEqual(
            payload["comparison"],
            "top 10 / total",
        )

    def test_insight_retains_calculation_recipe(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.47,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.07,
            magnitude_unit="ratio",
            evidence="Top 10 customers represent 47% of revenue.",
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
        self.assertEqual(
            finding.calculation["top_n"],
            10,
        )
        self.assertEqual(
            finding.calculation["aggregation"],
            "SUM",
        )

        insight = promote_finding(
            finding,
            finding_text=(
                "Top 10 customers represent 47% of revenue."
            ),
        )
        self.assertIsNotNone(insight)
        payload = insight.to_dict()
        calculation = payload["calculation"]
        self.assertTrue(
            REQUIRED_CALCULATION_KEYS <= set(calculation)
        )
        self.assertEqual(
            calculation["analysis_type"],
            "customer_concentration",
        )
        self.assertEqual(calculation["measure"], "revenue")
        self.assertEqual(calculation["dimension"], "customer")
        self.assertEqual(calculation["aggregation"], "SUM")
        self.assertEqual(calculation["grouping"], "customer_id")
        self.assertEqual(
            calculation["ranking"],
            "descending revenue",
        )
        self.assertEqual(calculation["top_n"], 10)
        self.assertEqual(
            calculation["comparison"],
            "top 10 / total",
        )
        # Also retained on traceability for engine consumers.
        self.assertEqual(
            payload["traceability"]["calculation"]["top_n"],
            10,
        )

    def test_concentration_engine_emits_calculation(self):
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
        calculation = high.calculation
        self.assertEqual(calculation["measure"], "revenue")
        self.assertEqual(calculation["dimension"], "customer")
        self.assertEqual(calculation["aggregation"], "SUM")
        self.assertEqual(calculation["grouping"], "customer_id")
        self.assertEqual(
            calculation["ranking"],
            "descending revenue",
        )
        self.assertEqual(calculation["top_n"], 10)
        self.assertEqual(
            calculation["comparison"],
            "top 10 / total",
        )

        insight = promote_finding(high)
        self.assertIsNotNone(insight)
        promoted = insight.to_dict()["calculation"]
        self.assertEqual(promoted["top_n"], 10)
        self.assertEqual(promoted["aggregation"], "SUM")

        single = next(
            item
            for item in findings
            if item.rule_id == "single_customer_concentration"
        )
        self.assertEqual(single.calculation["top_n"], 1)
        self.assertEqual(
            single.calculation["comparison"],
            "top 1 / total",
        )

    def test_serialize_preserves_empty_contract_keys(self):
        payload = serialize_calculation_spec(None)
        self.assertTrue(
            REQUIRED_CALCULATION_KEYS <= set(payload)
        )
        self.assertIsNone(payload["measure"])
        self.assertEqual(payload["filters"], [])
        self.assertEqual(payload["parameters"], {})


if __name__ == "__main__":
    unittest.main()
