"""
Evidence vs Explanation — architectural boundary (Increment 5).

Evidence = deterministic facts.
Explanation = interpretation (future / AI-allowed).
"""

from __future__ import annotations

import unittest

from app.analysis.insights.customer_concentration import (
    RULES as CONCENTRATION_RULES,
)
from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.evidence import (
    EVIDENCE_LAYER,
    EXPLANATION_LAYER,
    build_factual_evidence_summary,
    build_structured_evidence,
    looks_like_explanation,
    sanitize_evidence_summary,
)
from app.core.responsibilities import (
    AI_ALLOWED_RESPONSIBILITIES,
    DETERMINISTIC_RESPONSIBILITIES,
)


class TestEvidenceVsExplanation(unittest.TestCase):

    def test_layers_are_distinct(self):
        self.assertEqual(EVIDENCE_LAYER, "deterministic_fact")
        self.assertEqual(EXPLANATION_LAYER, "interpretation")
        self.assertNotEqual(EVIDENCE_LAYER, EXPLANATION_LAYER)

    def test_example_fact_is_not_explanation(self):
        fact = (
            "Revenue was $4.7M across the top 10 customers, "
            "representing 47% of total revenue."
        )
        self.assertFalse(looks_like_explanation(fact))
        self.assertEqual(sanitize_evidence_summary(fact), fact)

    def test_example_interpretation_is_explanation(self):
        explanation = (
            "This suggests the business may be exposed to "
            "customer concentration risk."
        )
        self.assertTrue(looks_like_explanation(explanation))
        self.assertEqual(sanitize_evidence_summary(explanation), "")

    def test_build_rejects_interpretive_summary(self):
        evidence = build_structured_evidence(
            summary=(
                "This suggests the business may be exposed to "
                "customer concentration risk."
            ),
            metrics=[
                {
                    "key": "top10_revenue",
                    "label": "Top 10 revenue",
                    "value": 4_700_000,
                    "unit": "currency",
                },
                {
                    "key": "top10_share",
                    "label": "Top 10 customer share",
                    "value": 0.47,
                    "unit": "ratio",
                },
                {
                    "key": "total_revenue",
                    "label": "Total revenue",
                    "value": 10_000_000,
                    "unit": "currency",
                },
            ],
        )
        self.assertFalse(looks_like_explanation(evidence.summary))
        self.assertIn("Top 10 revenue", evidence.summary)
        self.assertIn("$4,700,000", evidence.summary)
        self.assertNotIn("suggests", evidence.summary.lower())
        self.assertNotIn("risk", evidence.summary.lower())

        view = evidence.to_show_evidence()
        self.assertEqual(view["summary"]["layer"], EVIDENCE_LAYER)
        self.assertEqual(view["summary"]["headline"], evidence.summary)

    def test_factual_summary_preserved(self):
        fact = (
            "Top 10 customers represent 47% of revenue."
        )
        evidence = build_structured_evidence(
            summary=fact,
            metrics=[
                {
                    "key": "top10_share",
                    "label": "Top 10 customer share",
                    "value": 0.47,
                    "unit": "ratio",
                },
            ],
        )
        self.assertEqual(evidence.summary, fact)

    def test_build_factual_summary_from_metrics(self):
        summary = build_factual_evidence_summary(
            metrics=[
                {
                    "key": "top10_revenue",
                    "label": "Top 10 revenue",
                    "value": 4_700_000,
                    "unit": "currency",
                },
                {
                    "key": "top10_share",
                    "label": "Top 10 customer share",
                    "value": 0.47,
                    "unit": "ratio",
                },
            ],
        )
        self.assertIn("Top 10 revenue was $4,700,000", summary)
        self.assertIn("Top 10 customer share was 47.0%", summary)
        self.assertFalse(looks_like_explanation(summary))

    def test_engine_does_not_put_rule_message_in_evidence(self):
        """
        Concentration rule messages mix facts with interpretation.
        Evidence must keep only the factual layer.
        """

        engine = InsightEngine(CONCENTRATION_RULES)
        insights, findings = engine.evaluate_with_findings(
            {
                "top10_share": 0.47,
                "top10_revenue": 4_700_000,
                "total_revenue": 10_000_000,
                "total_customers": 842,
                "top_customer_share": 0.08,
            },
            analysis_type="customer_concentration",
            source_columns=["customer_id", "revenue"],
        )
        self.assertTrue(insights)
        self.assertTrue(findings)

        # Insight narrative may still carry interpretive wording.
        why = insights[0].why_it_matters
        self.assertTrue(
            looks_like_explanation(why)
            or "indicating" in why.lower()
            or "risk" in why.lower()
            or "monitored" in why.lower()
        )

        for finding in findings:
            summary = finding.evidence.summary
            self.assertFalse(
                looks_like_explanation(summary),
                msg=f"Evidence summary must be factual: {summary!r}",
            )
            for marker in (
                "suggests",
                "indicating",
                "risk",
                "may be",
            ):
                self.assertNotIn(marker, summary.lower())

            payload = finding.evidence.to_dict()
            self.assertEqual(
                payload["show_evidence"]["summary"]["layer"],
                EVIDENCE_LAYER,
            )

    def test_responsibilities_separate_evidence_from_explanation(self):
        self.assertIn(
            "structured_evidence",
            DETERMINISTIC_RESPONSIBILITIES,
        )
        self.assertIn(
            "insight_explanation",
            AI_ALLOWED_RESPONSIBILITIES,
        )
        self.assertNotIn(
            "insight_explanation",
            DETERMINISTIC_RESPONSIBILITIES,
        )
        self.assertNotIn(
            "structured_evidence",
            AI_ALLOWED_RESPONSIBILITIES,
        )


if __name__ == "__main__":
    unittest.main()
