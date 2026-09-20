"""
AI Insight Contract — interpretive layer separate from deterministic Insights.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.evidence import EXPLANATION_LAYER
from app.analysis.insights.explanation import (
    AI_INSIGHT_ALLOWED_INPUT_SECTIONS,
    REQUIRED_AI_INSIGHT_KEYS,
    apply_ai_insight_to_insight,
    assert_ai_insight_fact_pack_safe,
    build_ai_insight_fact_pack,
    build_fallback_ai_insight,
    explain_recommended_insights,
    extract_evidence_supported_drivers,
    fact_pack_contains_forbidden_inputs,
    hedge_causal_language,
    sanitize_ai_insight_contract,
)
from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import (
    INTERPRETIVE_FIELDS,
    promote_finding,
    serialize_insight,
)
from app.analysis.insights.initial_results import build_initial_results
from app.core.responsibilities import (
    INSIGHT_EXPLANATION_CONSTRAINTS,
    assert_ai_not_calculation_engine,
    is_ai_allowed_responsibility,
)
from app.services.ai import generate_insight_explanation
from app.services.prompts import build_insight_explanation_prompt


class TestAIInsightContract(unittest.TestCase):

    def _sample_insight(self, *, with_entities: bool = False):
        evidence_payload = {
            "summary": "Top 10 customers represent 55% of revenue.",
            "metrics": [
                {
                    "key": "top10_share",
                    "label": "Top 10 customer share",
                    "value": 0.55,
                    "unit": "ratio",
                }
            ],
            "entities": [],
            "data_quality": {
                "issues": [
                    {
                        "type": "excluded_records",
                        "label": "Excluded records",
                        "count": 4,
                        "description": "Null customer_id rows excluded",
                    }
                ],
                "affects_reliability": True,
            },
        }
        if with_entities:
            evidence_payload["entities"] = [
                {
                    "id": "acme",
                    "label": "Acme Corp",
                    "value": 1_200_000,
                    "share": 0.18,
                    "unit": "currency",
                }
            ]

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
            rule_id="high_concentration",
            severity="high",
            title="High Revenue Concentration",
        )
        insight = promote_finding(
            finding,
            business_impact="Material concentration risk",
            recommendation=(
                "Review the top accounts for renewal risk and "
                "identify opportunities to diversify revenue."
            ),
        )
        payload = serialize_insight(insight)
        self.assertIsNotNone(payload)
        payload["evidence"] = evidence_payload
        payload["finding"] = "Top 10 customers represent 55% of revenue."
        payload["insight_type"] = "concentration"
        return payload

    def test_contract_is_interpretive_and_ai_allowed(self):
        self.assertIn("ai_interpretation", INTERPRETIVE_FIELDS)
        self.assertTrue(
            is_ai_allowed_responsibility("insight_explanation")
        )
        assert_ai_not_calculation_engine("insight_explanation")

    def test_contract_shape_and_separation_from_finding(self):
        insight = self._sample_insight(with_entities=True)
        contract = build_fallback_ai_insight(insight)

        self.assertEqual(set(contract), REQUIRED_AI_INSIGHT_KEYS)
        self.assertEqual(contract["layer"], EXPLANATION_LAYER)
        self.assertEqual(contract["source"], "fallback")

        # Deterministic finding stays factual; summary is interpretation.
        self.assertEqual(
            insight["finding"],
            "Top 10 customers represent 55% of revenue.",
        )
        self.assertNotEqual(contract["summary"], insight["finding"])
        self.assertIn("concentrated", contract["summary"].lower())

        self.assertEqual(
            contract["why_it_matters"],
            "Material concentration risk",
        )
        self.assertTrue(contract["potential_drivers"])
        self.assertIn("Acme Corp", contract["potential_drivers"][0])
        self.assertIn("diversify", contract["recommended_action"].lower())
        self.assertTrue(
            any("Null customer_id" in item for item in contract["caveats"])
        )

    def test_drivers_only_from_evidence(self):
        insight = self._sample_insight(with_entities=False)
        for driver in extract_evidence_supported_drivers(insight):
            self.assertNotIn("Acme", driver)

        with_entities = self._sample_insight(with_entities=True)
        supported = extract_evidence_supported_drivers(with_entities)
        self.assertTrue(any("Acme Corp" in item for item in supported))

    def test_recommended_insights_receive_contract(self):
        insight = self._sample_insight(with_entities=True)
        initial = build_initial_results([insight])
        promoted, results = explain_recommended_insights(
            promoted_insights=[insight],
            initial_results=initial,
        )

        self.assertIn("ai_interpretation", promoted[0])
        contract = promoted[0]["ai_interpretation"]
        self.assertEqual(set(contract), REQUIRED_AI_INSIGHT_KEYS)
        self.assertEqual(
            results["recommended_insights"][0]["ai_interpretation"][
                "summary"
            ],
            contract["summary"],
        )
        # Deterministic finding remains unchanged.
        self.assertEqual(
            promoted[0]["finding"],
            "Top 10 customers represent 55% of revenue.",
        )

    def test_prompt_uses_contract_fields(self):
        insight = self._sample_insight(with_entities=True)
        fact_pack = build_ai_insight_fact_pack(insight)
        prompt = build_insight_explanation_prompt(fact_pack)
        self.assertIn("summary", prompt)
        self.assertIn("why_it_matters", prompt)
        self.assertIn("potential_drivers", prompt)
        self.assertIn("recommended_action", prompt)
        self.assertIn("caveats", prompt)
        self.assertIn("must NOT", prompt)
        self.assertIn("Potential drivers include", prompt)
        self.assertIn("This happened because", prompt)
        self.assertIn("structured_insight", prompt)

        contract = generate_insight_explanation(insight)
        self.assertEqual(contract["source"], "fallback")
        self.assertEqual(set(contract), REQUIRED_AI_INSIGHT_KEYS)

    def test_fact_pack_excludes_raw_dataset(self):
        insight = self._sample_insight(with_entities=True)
        insight["raw_rows"] = [{"customer_id": "x", "revenue": 1}]
        insight["dataframe"] = "should-not-appear"
        fact_pack = build_ai_insight_fact_pack(insight)

        self.assertEqual(
            set(fact_pack),
            set(AI_INSIGHT_ALLOWED_INPUT_SECTIONS),
        )
        self.assertIn("structured_insight", fact_pack)
        self.assertIn("evidence", fact_pack)
        self.assertIn("dataset_context", fact_pack)
        self.assertIn("data_quality_limitations", fact_pack)
        self.assertNotIn("raw_rows", fact_pack)
        self.assertNotIn("dataframe", fact_pack)
        self.assertEqual(fact_pack_contains_forbidden_inputs(fact_pack), [])
        assert_ai_insight_fact_pack_safe(fact_pack)
        self.assertFalse(fact_pack["constraints"]["may_receive_raw_dataset"])
        self.assertFalse(
            INSIGHT_EXPLANATION_CONSTRAINTS["may_invent_numbers"]
        )

    def test_sanitize_rejects_causation_and_invented_numbers(self):
        insight = self._sample_insight(with_entities=True)
        polluted = {
            "summary": (
                "This happened because Acme lost a contract. "
                "Revenue fell by 99.7% overnight."
            ),
            "why_it_matters": "Material concentration risk",
            "potential_drivers": [
                "This happened because of pricing changes",
                "Acme Corp is a material contributor (1,200,000, 18.0%)",
            ],
            "recommended_action": "Review the top accounts",
            "caveats": ["Null customer_id rows excluded"],
            "layer": EXPLANATION_LAYER,
            "source": "ai",
        }
        cleaned = sanitize_ai_insight_contract(
            polluted,
            insight=insight,
            source="ai",
        )
        combined = " ".join(
            [
                cleaned["summary"],
                cleaned["why_it_matters"],
                " ".join(cleaned["potential_drivers"]),
                cleaned["recommended_action"],
            ]
        ).lower()
        self.assertNotIn("this happened because", combined)
        self.assertNotIn("99.7", cleaned["summary"])
        self.assertTrue(
            any(
                "potential" in item.lower() or "acme" in item.lower()
                for item in cleaned["potential_drivers"]
            )
        )
        # Deterministic finding must remain untouched when applied.
        applied = apply_ai_insight_to_insight(insight, cleaned)
        self.assertEqual(
            applied["finding"],
            "Top 10 customers represent 55% of revenue.",
        )

    def test_hedge_causal_language_helper(self):
        self.assertIn(
            "potential drivers include",
            hedge_causal_language(
                "This happened because of churn"
            ).lower(),
        )


if __name__ == "__main__":
    unittest.main()
