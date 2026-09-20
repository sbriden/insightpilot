"""
Tests for structured candidate findings from analytical modules.
"""

from __future__ import annotations

import unittest
from datetime import datetime

from app.analysis.insights.customer_concentration import (
    RULES as CONCENTRATION_RULES,
)
from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.findings import (
    CandidateFinding,
    collect_candidate_findings_from_dashboards,
    make_candidate_finding,
    resolve_confidence,
    serialize_candidate_finding,
)
from app.analysis.insights.insight import (
    REQUIRED_INSIGHT_KEYS,
    collect_promoted_insights_from_dashboards,
)
from app.analysis.models import AnalysisDashboard
from app.core.analysis_context import AnalysisContext
from app.core.responsibilities import (
    NARRATIVE_PROMPT_FACT_KEYS,
)
from app.products.models import DataProduct
from app.products.service import (
    _extract_candidate_findings,
    _extract_promoted_insights,
    _serialize_product,
)


REQUIRED_FINDING_KEYS = {
    "id",
    "analysis_type",
    "metric",
    "observed_value",
    "baseline",
    "comparison",
    "magnitude",
    "evidence",
    "confidence",
    "relevant_dimensions",
    "source_columns",
    "provenance",
    "filters",
    "calculations",
    "calculation",
}


REQUIRED_PROVENANCE_KEYS = {
    "source_columns",
    "dimensions",
    "filters",
    "calculations",
    "calculation",
}


class TestCandidateFindings(unittest.TestCase):

    def test_make_candidate_finding_shape(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.55,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.15,
            magnitude_unit="ratio",
            evidence="Top 10 share is elevated.",
            confidence=0.9,
            relevant_dimensions=["customer"],
            source_columns=["customer_id", "revenue"],
            rule_id="high_concentration",
            severity="high",
            title="High Revenue Concentration",
        )

        self.assertIsNotNone(finding)
        payload = finding.to_dict()

        self.assertTrue(
            REQUIRED_FINDING_KEYS <= set(payload)
        )
        self.assertTrue(
            REQUIRED_PROVENANCE_KEYS
            <= set(payload["provenance"])
        )
        self.assertEqual(
            finding.source_columns,
            ["customer_id", "revenue"],
        )
        self.assertTrue(finding.calculations)
        self.assertEqual(
            finding.id,
            "customer_concentration:high_concentration",
        )
        self.assertEqual(
            finding.analysis_type,
            "customer_concentration",
        )

    def test_concentration_engine_emits_findings(self):
        facts = {
            "total_customers": 50,
            "top10_share": 0.55,
            "top_customer_share": 0.18,
            "top_customer_revenue": 1800.0,
        }

        insights, findings = InsightEngine(
            CONCENTRATION_RULES
        ).evaluate_with_findings(
            facts,
            analysis_type="customer_concentration",
            source_columns=["Customer", "Revenue"],
            relevant_dimensions=["customer"],
        )

        self.assertTrue(insights)
        self.assertTrue(findings)

        finding_ids = {
            item.id for item in findings
        }

        self.assertIn(
            "customer_concentration:high_concentration",
            finding_ids,
        )
        self.assertIn(
            "customer_concentration:single_customer_concentration",
            finding_ids,
        )

        high = next(
            item
            for item in findings
            if item.rule_id == "high_concentration"
        )

        self.assertEqual(
            high.metric,
            "top10_revenue_share",
        )
        self.assertEqual(high.observed_value, 0.55)
        self.assertEqual(high.baseline, 0.40)
        self.assertEqual(
            high.comparison,
            "vs_threshold",
        )
        self.assertAlmostEqual(high.magnitude, 0.15)
        self.assertTrue(high.evidence)
        self.assertIn(high.confidence, {"high", "medium", "low"})
        self.assertEqual(high.confidence, "high")
        self.assertEqual(
            high.relevant_dimensions,
            ["customer"],
        )
        self.assertEqual(
            high.source_columns,
            ["Customer", "Revenue"],
        )
        self.assertEqual(
            high.provenance.source_columns,
            ["Customer", "Revenue"],
        )
        self.assertEqual(
            high.provenance.dimensions,
            ["customer"],
        )
        self.assertTrue(high.filters)
        self.assertEqual(
            high.filters[0]["field"],
            "top10_share",
        )
        self.assertTrue(high.calculations)
        self.assertIn(
            "top10_share",
            " ".join(high.calculations),
        )
        self.assertTrue(high.provenance.row_scope)
        self.assertIn(
            "top10_share",
            high.provenance.input_values,
        )

    def test_dashboard_serializes_candidate_findings(self):
        dashboard = AnalysisDashboard(
            id="customer_concentration",
            title="Customer Concentration",
            summary="Test",
        )

        dashboard.candidate_findings.append(
            make_candidate_finding(
                analysis_type="customer_concentration",
                metric="top10_revenue_share",
                observed_value=0.42,
                baseline=0.40,
                comparison="vs_threshold",
                magnitude=0.02,
                evidence="Elevated concentration.",
                confidence=0.88,
                source_columns=["revenue"],
                rule_id="high_concentration",
            )
        )

        payload = dashboard.to_dict()

        self.assertIn("candidate_findings", payload)
        self.assertEqual(
            len(payload["candidate_findings"]),
            1,
        )
        self.assertEqual(
            payload["candidate_findings"][0]["metric"],
            "top10_revenue_share",
        )

    def test_context_exposes_candidate_findings(self):
        context = AnalysisContext(
            profile={},
            metrics={},
            classification={},
            candidate_findings=[
                {
                    "id": "x:y",
                    "analysis_type": "x",
                    "metric": "m",
                    "observed_value": 1,
                    "evidence": "e",
                    "confidence": 0.8,
                    "relevant_dimensions": [],
                    "source_columns": [],
                }
            ],
        )

        api = context.to_api_response()
        facts = context.analytical_facts()
        prompt = context.to_prompt_context()

        self.assertIn("candidate_findings", api)
        self.assertIn("candidate_findings", facts)
        self.assertIn(
            "candidate_findings",
            NARRATIVE_PROMPT_FACT_KEYS,
        )
        self.assertEqual(
            len(prompt["candidate_findings"]),
            1,
        )

    def test_resolve_confidence_from_sample_size(self):
        self.assertEqual(
            resolve_confidence({"total_customers": 120}, source_columns=["a"]),
            "high",
        )
        self.assertEqual(
            resolve_confidence({"total_customers": 5}),
            "low",
        )
        self.assertEqual(
            resolve_confidence({}, explicit=0.82),
            "medium",
        )
        self.assertEqual(
            resolve_confidence({}, explicit="high"),
            "high",
        )

    def test_serialize_candidate_finding_plain_dict(self):
        finding = make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.55,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.15,
            evidence="High concentration.",
            source_columns=["revenue"],
            rule_id="high_concentration",
        )
        assert finding is not None

        payload = serialize_candidate_finding(finding)
        assert payload is not None
        self.assertTrue(
            REQUIRED_FINDING_KEYS.issubset(payload.keys())
        )
        self.assertIsInstance(payload["provenance"], dict)
        self.assertTrue(
            REQUIRED_PROVENANCE_KEYS.issubset(
                payload["provenance"].keys()
            )
        )

        # Round-trip from dict stays stable.
        again = serialize_candidate_finding(payload)
        self.assertEqual(again["id"], payload["id"])
        self.assertEqual(
            again["metric"],
            payload["metric"],
        )

    def test_collect_findings_from_dashboards(self):
        dashboards = [
            {
                "id": "customer_concentration",
                "candidate_findings": [
                    {
                        "id": "a:b",
                        "analysis_type": "customer_concentration",
                        "metric": "top10_revenue_share",
                        "observed_value": 0.5,
                        "evidence": "e",
                        "confidence": 0.9,
                        "source_columns": ["revenue"],
                        "relevant_dimensions": [],
                    }
                ],
            }
        ]

        context_findings = (
            collect_candidate_findings_from_dashboards(
                dashboards,
                scope_by_dashboard=False,
            )
        )
        self.assertEqual(len(context_findings), 1)
        self.assertEqual(context_findings[0]["id"], "a:b")

        product_findings = (
            collect_candidate_findings_from_dashboards(
                dashboards,
                scope_by_dashboard=True,
            )
        )
        self.assertEqual(
            product_findings[0]["id"],
            "customer_concentration:a:b",
        )

    def test_product_serialize_includes_candidate_findings(self):
        dashboards = [
            {
                "id": "revenue_trends",
                "insights": [
                    {
                        "id": "growth",
                        "rule_id": "growth",
                        "title": "Revenue Growth",
                        "category": "Revenue Trends",
                        "message": "Revenue grew.",
                        "recommended_action": (
                            "Reinforce what is working."
                        ),
                    }
                ],
                "candidate_findings": [
                    {
                        "id": "revenue_trends:growth",
                        "analysis_type": "revenue_trends",
                        "metric": "revenue_change_pct",
                        "observed_value": 0.12,
                        "evidence": "Revenue grew.",
                        "confidence": 0.85,
                        "source_columns": ["revenue"],
                        "relevant_dimensions": [],
                        "rule_id": "growth",
                        "title": "Revenue Growth",
                        "severity": "medium",
                    }
                ],
            }
        ]

        extracted = _extract_candidate_findings(dashboards)
        self.assertEqual(len(extracted), 1)
        self.assertTrue(
            extracted[0]["id"].startswith("revenue_trends:")
        )

        promoted = _extract_promoted_insights(dashboards)
        self.assertEqual(len(promoted), 1)
        self.assertTrue(
            REQUIRED_INSIGHT_KEYS <= set(promoted[0])
        )
        self.assertEqual(
            promoted[0]["category"],
            "Revenue",
        )
        self.assertEqual(
            promoted[0]["recommendation"],
            "Reinforce what is working.",
        )
        self.assertEqual(
            promoted[0]["potential_drivers"],
            [],
        )

        product = DataProduct(
            id="p1",
            name="Sales Performance",
            description="desc",
            analyses=[],
            insights=[],
            candidate_findings=extracted,
            promoted_insights=promoted,
            dashboards=dashboards,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        serialized = _serialize_product(product)
        self.assertIn("candidate_findings", serialized)
        self.assertIn("promoted_insights", serialized)
        self.assertIn("insight_initial_results", serialized)
        self.assertEqual(
            serialized["insight_initial_results"]["total_discovered"],
            1,
        )
        self.assertEqual(
            serialized["insight_initial_results"]["recommended_count"],
            1,
        )
        self.assertEqual(
            len(serialized["candidate_findings"]),
            1,
        )
        self.assertEqual(
            len(serialized["promoted_insights"]),
            1,
        )
        self.assertEqual(
            serialized["promoted_insights"][0]["insight_id"],
            promoted[0]["insight_id"],
        )
        # Existing surfaces remain intact.
        self.assertIn("dashboards", serialized)
        self.assertIn("insights", serialized)
        self.assertEqual(
            serialized["dashboards"][0]["id"],
            "revenue_trends",
        )

    def test_collect_promoted_insights_from_dashboards(self):
        dashboards = [
            {
                "id": "customer_concentration",
                "insights": [
                    {
                        "id": "high_concentration",
                        "category": "Customer Concentration",
                        "recommended_action": (
                            "Diversify the book."
                        ),
                    }
                ],
                "candidate_findings": [
                    {
                        "id": "customer_concentration:high_concentration",
                        "analysis_type": "customer_concentration",
                        "metric": "top10_revenue_share",
                        "observed_value": 0.5,
                        "evidence": "Elevated concentration.",
                        "confidence": 0.9,
                        "source_columns": ["revenue"],
                        "relevant_dimensions": ["customer"],
                        "rule_id": "high_concentration",
                        "title": "High Revenue Concentration",
                    }
                ],
            }
        ]

        promoted = collect_promoted_insights_from_dashboards(
            dashboards,
            scope_by_dashboard=False,
        )
        self.assertEqual(len(promoted), 1)
        self.assertEqual(
            promoted[0]["insight_type"],
            "concentration",
        )
        self.assertEqual(
            promoted[0]["recommendation"],
            "Diversify the book.",
        )
        self.assertEqual(
            promoted[0]["candidate_finding_id"],
            "customer_concentration:high_concentration",
        )
        self.assertEqual(
            promoted[0]["traceability"]["analysis_type"],
            "customer_concentration",
        )

    def test_context_exposes_promoted_insights(self):
        context = AnalysisContext(
            profile={},
            metrics={},
            classification={},
            candidate_findings=[
                {
                    "id": "x:y",
                    "analysis_type": "customer_concentration",
                    "metric": "top10_revenue_share",
                    "observed_value": 0.47,
                    "baseline": 0.40,
                    "evidence": "Top 10 share is 47%.",
                    "confidence": 0.8,
                    "relevant_dimensions": ["customer"],
                    "source_columns": ["revenue"],
                    "title": "High Concentration",
                    "severity": "high",
                    "rule_id": "high_concentration",
                }
            ],
        )

        api = context.to_api_response()
        facts = context.analytical_facts()
        prompt = context.to_prompt_context()

        self.assertIn("validated_findings", api)
        self.assertIn("promoted_insights", api)
        self.assertIn("insight_initial_results", api)
        self.assertIn("validated_findings", facts)
        self.assertIn("promoted_insights", facts)
        self.assertIn("insight_initial_results", facts)
        self.assertIn(
            "validated_findings",
            NARRATIVE_PROMPT_FACT_KEYS,
        )
        self.assertIn(
            "promoted_insights",
            NARRATIVE_PROMPT_FACT_KEYS,
        )
        self.assertEqual(
            api["insight_initial_results"]["total_discovered"],
            1,
        )
        self.assertEqual(
            api["insight_initial_results"]["recommended_count"],
            1,
        )
        self.assertEqual(
            len(api["validated_findings"]),
            1,
        )
        self.assertEqual(
            len(api["promoted_insights"]),
            1,
        )
        self.assertEqual(
            api["promoted_insights"][0]["category"],
            "Customer",
        )
        self.assertEqual(
            api["promoted_insights"][0]["candidate_finding_id"],
            "x:y",
        )
        self.assertEqual(
            api["promoted_insights"][0]["traceability"]["analysis_type"],
            "customer_concentration",
        )
        self.assertEqual(
            len(prompt["promoted_insights"]),
            1,
        )

    def test_low_severity_finding_stays_validated_not_insight(self):
        context = AnalysisContext(
            profile={},
            metrics={},
            classification={},
            candidate_findings=[
                {
                    "id": "revenue_trends:growth",
                    "analysis_type": "revenue_trends",
                    "metric": "overall_revenue_growth",
                    "observed_value": 0.08,
                    "evidence": "Revenue increased 8%.",
                    "confidence": 0.85,
                    "relevant_dimensions": [],
                    "source_columns": ["revenue"],
                    "title": "Revenue Growth",
                    "severity": "low",
                    "rule_id": "revenue_growth",
                    "comparison": "vs_prior_period",
                    "magnitude": 0.08,
                    "magnitude_unit": "ratio",
                }
            ],
        )

        api = context.to_api_response()
        self.assertEqual(len(api["candidate_findings"]), 1)
        self.assertEqual(len(api["validated_findings"]), 1)
        self.assertFalse(
            api["validated_findings"][0]["insight_eligible"]
        )
        self.assertEqual(len(api["promoted_insights"]), 0)


if __name__ == "__main__":
    unittest.main()
