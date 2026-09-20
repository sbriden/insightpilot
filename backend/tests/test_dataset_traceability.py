"""
Dataset traceability on Insights (Increment 5).

An Insight retains its relationship to the analyzed dataset:
identifier/version, analysis timestamp, source columns,
filters, excluded records, and analytical method.
"""

from __future__ import annotations

import unittest
from datetime import datetime

from app.analysis.insights.customer_concentration import (
    RULES as CONCENTRATION_RULES,
)
from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import (
    promote_finding,
    serialize_insight,
)
from app.analysis.insights.traceability import (
    REQUIRED_DATASET_TRACEABILITY_KEYS,
    build_dataset_traceability,
    stamp_insight_dataset_traceability,
)


class TestDatasetTraceability(unittest.TestCase):

    def test_required_keys(self):
        payload = build_dataset_traceability(
            dataset_id="ds_1",
            dataset_version=2,
            analyzed_at=datetime(2026, 9, 11, 18, 0, 0),
            source_columns=["customer_id", "revenue"],
            filters=[{"field": "revenue", "op": ">", "value": 0}],
            records_excluded=12,
            analysis_type="customer_concentration",
            calculation={"analysis_type": "customer_concentration"},
            methodology_steps=["rank customers by revenue"],
        ).to_dict()

        self.assertEqual(
            set(payload),
            REQUIRED_DATASET_TRACEABILITY_KEYS,
        )
        self.assertEqual(payload["dataset_id"], "ds_1")
        self.assertEqual(payload["dataset_version"], 2)
        self.assertEqual(
            payload["analyzed_at"],
            "2026-09-11T18:00:00",
        )
        self.assertEqual(
            payload["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertEqual(len(payload["filters"]), 1)
        self.assertEqual(
            payload["records_excluded"][0]["count"],
            12,
        )
        self.assertEqual(
            payload["analytical_method"]["analysis_type"],
            "customer_concentration",
        )
        self.assertEqual(
            payload["analytical_method"]["steps"],
            ["rank customers by revenue"],
        )

    def test_promoted_insight_includes_dataset_block(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.55,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.15,
            magnitude_unit="ratio",
            evidence="Top 10 customers represent 55% of revenue.",
            confidence=0.9,
            relevant_dimensions=["customer"],
            source_columns=["customer_id", "revenue"],
            filters=[
                {
                    "field": "top10_share",
                    "op": ">=",
                    "value": 0.40,
                }
            ],
            calculations=[
                "top10_share = top10_revenue / total_revenue",
            ],
            rule_id="high_concentration",
            severity="high",
            title="High Revenue Concentration",
            provenance={
                "source_columns": ["customer_id", "revenue"],
                "dimensions": ["customer"],
                "filters": [
                    {
                        "field": "top10_share",
                        "op": ">=",
                        "value": 0.40,
                    }
                ],
                "calculations": [
                    "top10_share = top10_revenue / total_revenue",
                ],
                "dataset": {
                    "dataset_id": "upload_abc",
                    "dataset_version": 3,
                    "dataset_label": "sales_orders",
                    "analyzed_at": "2026-09-11T12:00:00",
                    "records_excluded": [
                        {
                            "type": "excluded_records",
                            "label": "Excluded records",
                            "count": 4,
                            "description": "Null customer_id rows",
                        }
                    ],
                },
            },
        )
        self.assertIsNotNone(finding)

        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        payload = serialize_insight(insight)
        self.assertIsNotNone(payload)

        dataset = payload["traceability"]["dataset"]
        self.assertEqual(dataset["dataset_id"], "upload_abc")
        self.assertEqual(dataset["dataset_version"], 3)
        self.assertEqual(dataset["dataset_label"], "sales_orders")
        self.assertEqual(
            dataset["analyzed_at"],
            "2026-09-11T12:00:00",
        )
        self.assertEqual(
            dataset["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertTrue(dataset["filters"])
        self.assertEqual(dataset["records_excluded"][0]["count"], 4)
        self.assertEqual(
            dataset["analytical_method"]["analysis_type"],
            "customer_concentration",
        )
        self.assertTrue(
            dataset["analytical_method"]["steps"]
            or dataset["analytical_method"]["calculation"]
        )

        evidence = payload["evidence"]
        self.assertEqual(evidence["source_dataset"], "sales_orders")
        self.assertEqual(evidence["source_dataset_id"], "upload_abc")
        self.assertEqual(evidence["dataset_version"], 3)
        self.assertEqual(
            evidence["analyzed_at"],
            "2026-09-11T12:00:00",
        )
        source = evidence["show_evidence"]["source"]
        self.assertEqual(source["dataset_version"], 3)
        self.assertIn("analytical_method", source)
        self.assertIn("records_excluded", source)

    def test_engine_provenance_carries_dataset_fields(self):
        _, findings = InsightEngine(
            CONCENTRATION_RULES
        ).evaluate_with_findings(
            {
                "top10_share": 0.47,
                "top10_revenue": 4_700_000,
                "total_revenue": 10_000_000,
                "total_customers": 842,
                "top_customer_share": 0.08,
            },
            analysis_type="customer_concentration",
            source_columns=["customer_id", "revenue"],
            dataset_id="ds_42",
            dataset_version=1,
            dataset_identity="identity_42",
            dataset_label="uploaded_dataset",
            analyzed_at="2026-09-11T15:30:00",
            records_excluded=7,
        )
        self.assertTrue(findings)
        provenance = findings[0].provenance.to_dict()
        dataset = provenance["dataset"]
        self.assertEqual(dataset["dataset_id"], "ds_42")
        self.assertEqual(dataset["dataset_version"], 1)
        self.assertEqual(dataset["dataset_identity"], "identity_42")
        self.assertEqual(dataset["analyzed_at"], "2026-09-11T15:30:00")
        self.assertEqual(dataset["records_excluded"][0]["count"], 7)
        self.assertEqual(
            dataset["analytical_method"]["analysis_type"],
            "customer_concentration",
        )

        evidence = findings[0].evidence.to_dict()
        self.assertEqual(evidence["source_dataset_id"], "ds_42")
        self.assertEqual(evidence["dataset_version"], 1)

    def test_stamp_fills_identity_without_erasing_method(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.55,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.15,
            magnitude_unit="ratio",
            evidence="Top 10 customers represent 55% of revenue.",
            source_columns=["customer_id", "revenue"],
            rule_id="high_concentration",
            severity="high",
        )
        insight = promote_finding(finding)
        payload = serialize_insight(insight)
        stamped = stamp_insight_dataset_traceability(
            payload,
            dataset_id="identity_x",
            dataset_version=5,
            dataset_identity="identity_x",
            dataset_label="uploaded_dataset",
            analyzed_at="2026-09-11T16:00:00",
        )
        dataset = stamped["traceability"]["dataset"]
        self.assertEqual(dataset["dataset_id"], "identity_x")
        self.assertEqual(dataset["dataset_version"], 5)
        self.assertEqual(
            dataset["source_columns"],
            ["customer_id", "revenue"],
        )
        self.assertEqual(
            dataset["analytical_method"]["analysis_type"],
            "customer_concentration",
        )


if __name__ == "__main__":
    unittest.main()
