"""
Tests for multi-level evidence (aggregate / entity / distribution / record).
"""

from __future__ import annotations

import unittest

from app.analysis.insights.evidence import (
    EVIDENCE_LEVEL_AGGREGATE,
    EVIDENCE_LEVEL_DISTRIBUTION,
    EVIDENCE_LEVEL_ENTITY,
    EVIDENCE_LEVEL_RECORD,
    EVIDENCE_LEVELS,
    build_structured_evidence,
    infer_evidence_level,
)
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import promote_finding


class TestEvidenceLevels(unittest.TestCase):

    def test_aggregate_evidence_shape(self):
        evidence = build_structured_evidence(
            summary="Northeast revenue declined 18%.",
            metric_name="region_revenue_change",
            observed_value=820_000,
            baseline=1_000_000,
            level="aggregate",
            relevant_dimensions=["region"],
            aggregate_rows=[
                {
                    "label": "Northeast",
                    "current": 820_000,
                    "previous": 1_000_000,
                    "change": -180_000,
                    "change_pct": -0.18,
                    "unit": "currency",
                }
            ],
            # Record-level must remain optional — not forced.
            records=[],
        )
        payload = evidence.to_dict()
        self.assertEqual(payload["level"], EVIDENCE_LEVEL_AGGREGATE)
        self.assertEqual(
            payload["levels_present"],
            [EVIDENCE_LEVEL_AGGREGATE],
        )
        self.assertEqual(len(payload["aggregate_rows"]), 1)
        self.assertEqual(
            payload["aggregate_rows"][0]["label"],
            "Northeast",
        )
        self.assertEqual(payload["records"], [])

        show = payload["show_evidence"]["breakdown"]
        self.assertEqual(show["level"], EVIDENCE_LEVEL_AGGREGATE)
        self.assertEqual(len(show["aggregate"]["rows"]), 1)
        self.assertAlmostEqual(
            show["aggregate"]["rows"][0]["change_pct"],
            -0.18,
        )

    def test_entity_evidence_shape(self):
        evidence = build_structured_evidence(
            summary=(
                "Three customers account for 62% of overdue invoices."
            ),
            level="entity",
            relevant_dimensions=["customer"],
            entities=[
                {
                    "id": "c1",
                    "label": "Acme",
                    "value": 120_000,
                    "share": 0.28,
                    "unit": "currency",
                },
                {
                    "id": "c2",
                    "label": "Globex",
                    "value": 90_000,
                    "share": 0.21,
                    "unit": "currency",
                },
                {
                    "id": "c3",
                    "label": "Initech",
                    "value": 56_000,
                    "share": 0.13,
                    "unit": "currency",
                },
            ],
        )
        payload = evidence.to_dict()
        self.assertEqual(payload["level"], EVIDENCE_LEVEL_ENTITY)
        self.assertEqual(len(payload["entities"]), 3)
        total_share = sum(
            item["share"] for item in payload["entities"]
        )
        self.assertAlmostEqual(total_share, 0.62)
        self.assertEqual(
            payload["show_evidence"]["breakdown"]["level"],
            EVIDENCE_LEVEL_ENTITY,
        )

    def test_distribution_evidence_shape(self):
        evidence = build_structured_evidence(
            summary=(
                "Employee overtime is heavily concentrated "
                "in one department."
            ),
            level="distribution",
            relevant_dimensions=["department"],
            distribution=[
                {
                    "label": "Operations",
                    "value": 420,
                    "share": 0.61,
                    "unit": "count",
                },
                {
                    "label": "Sales",
                    "value": 140,
                    "share": 0.20,
                    "unit": "count",
                },
                {
                    "label": "Support",
                    "value": 130,
                    "share": 0.19,
                    "unit": "count",
                },
            ],
        )
        payload = evidence.to_dict()
        self.assertEqual(
            payload["level"],
            EVIDENCE_LEVEL_DISTRIBUTION,
        )
        buckets = payload["show_evidence"]["breakdown"][
            "distribution"
        ]["buckets"]
        self.assertEqual(buckets[0]["label"], "Operations")
        self.assertAlmostEqual(buckets[0]["share"], 0.61)

    def test_record_evidence_optional_and_not_forced(self):
        # Without records, level stays aggregate/entity/distribution.
        aggregate_only = build_structured_evidence(
            aggregate_rows=[
                {
                    "label": "Northeast",
                    "current": 100,
                    "previous": 120,
                    "change_pct": -0.167,
                }
            ],
            records=[
                {
                    "record_id": "inv-99",
                    "label": "Invoice 99",
                    "keys": {"invoice_id": "inv-99"},
                }
            ],
        )
        # Prefer aggregate over record when both exist.
        self.assertEqual(
            aggregate_only.resolved_level(),
            EVIDENCE_LEVEL_AGGREGATE,
        )
        self.assertIn(
            EVIDENCE_LEVEL_RECORD,
            aggregate_only.levels_present(),
        )

        record_only = build_structured_evidence(
            level="record",
            records=[
                {
                    "record_id": "ord-1",
                    "keys": {"order_id": "ord-1"},
                    "fields": {"amount": 12_500},
                }
            ],
        )
        payload = record_only.to_dict()
        self.assertEqual(payload["level"], EVIDENCE_LEVEL_RECORD)
        self.assertEqual(
            payload["records"][0]["record_id"],
            "ord-1",
        )
        self.assertEqual(
            payload["show_evidence"]["breakdown"]["records"][0][
                "keys"
            ]["order_id"],
            "ord-1",
        )

    def test_infer_evidence_level_priority(self):
        self.assertEqual(
            infer_evidence_level(
                distribution=[{"label": "A"}],
                entities=[{"label": "B"}],
                aggregate_rows=[{"label": "C", "current": 1}],
                records=[{"record_id": "1"}],
            ),
            EVIDENCE_LEVEL_DISTRIBUTION,
        )
        self.assertEqual(
            infer_evidence_level(
                entities=[{"label": "B"}],
                records=[{"record_id": "1"}],
            ),
            EVIDENCE_LEVEL_ENTITY,
        )
        self.assertEqual(
            infer_evidence_level(
                records=[{"record_id": "1"}],
            ),
            EVIDENCE_LEVEL_RECORD,
        )
        self.assertIsNone(infer_evidence_level())
        self.assertEqual(
            set(EVIDENCE_LEVELS),
            {
                EVIDENCE_LEVEL_AGGREGATE,
                EVIDENCE_LEVEL_ENTITY,
                EVIDENCE_LEVEL_DISTRIBUTION,
                EVIDENCE_LEVEL_RECORD,
            },
        )

    def test_insight_preserves_evidence_level(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="overdue_concentration",
            observed_value=0.62,
            baseline=0.30,
            comparison="vs_threshold",
            magnitude=0.32,
            magnitude_unit="ratio",
            evidence=build_structured_evidence(
                summary=(
                    "Three customers account for 62% "
                    "of overdue invoices."
                ),
                level="entity",
                entities=[
                    {
                        "label": "Acme",
                        "value": 120_000,
                        "share": 0.28,
                    },
                    {
                        "label": "Globex",
                        "value": 90_000,
                        "share": 0.21,
                    },
                    {
                        "label": "Initech",
                        "value": 56_000,
                        "share": 0.13,
                    },
                ],
                relevant_dimensions=["customer"],
                source_columns=["customer_id", "amount"],
            ),
            confidence=0.9,
            source_columns=["customer_id", "amount"],
            relevant_dimensions=["customer"],
            severity="high",
            title="Overdue concentration",
        )
        self.assertIsNotNone(finding)
        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        evidence = insight.to_dict()["evidence"]
        self.assertEqual(evidence["level"], EVIDENCE_LEVEL_ENTITY)
        self.assertEqual(len(evidence["entities"]), 3)
        self.assertEqual(
            evidence["show_evidence"]["breakdown"]["level"],
            EVIDENCE_LEVEL_ENTITY,
        )
        # Still no forced record-level payload.
        self.assertEqual(evidence["records"], [])


if __name__ == "__main__":
    unittest.main()
