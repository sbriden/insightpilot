"""
Insight Executive Brief — concise leadership read from explained Insights.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.executive_brief import (
    DEFAULT_BRIEF_INSIGHT_CAP,
    REQUIRED_EXECUTIVE_BRIEF_KEYS,
    TARGET_READING_SECONDS,
    attach_executive_brief_to_initial_results,
    build_executive_brief_fact_pack,
    build_fallback_executive_brief,
    generate_fallback_insight_executive_brief,
    sanitize_executive_brief,
)
from app.analysis.insights.initial_results import build_initial_results
from app.core.responsibilities import (
    EXECUTIVE_BRIEF_CONSTRAINTS,
    assert_ai_not_calculation_engine,
    is_ai_allowed_responsibility,
)
from app.services.ai import generate_insight_executive_brief
from app.services.prompts import build_insight_executive_brief_prompt


def _sample_insights():
    return [
        {
            "insight_id": "i1",
            "title": "Northeast Revenue Decline",
            "finding": (
                "Northeast revenue declined 18% compared with "
                "the previous period."
            ),
            "tier": "critical",
            "importance": "high",
            "category": "Revenue",
            "insight_type": "growth_decline",
            "metric": "revenue_change",
            "observed_value": -0.18,
            "ai_interpretation": {
                "summary": (
                    "The decline is material relative to overall "
                    "revenue performance."
                ),
                "why_it_matters": "Material regional exposure.",
                "potential_drivers": [
                    "Largest customers in Northeast contributed most."
                ],
                "recommended_action": (
                    "Investigate the largest customer and "
                    "product-level contributors to the decline."
                ),
                "caveats": ["4 rows excluded for null region."],
                "layer": "interpretation",
                "source": "fallback",
            },
            "recommendation": (
                "Investigate the largest customer and "
                "product-level contributors to the decline."
            ),
        },
        {
            "insight_id": "i2",
            "title": "High Customer Concentration",
            "finding": "Top 10 customers represent 55% of revenue.",
            "tier": "important",
            "importance": "high",
            "category": "Customers",
            "insight_type": "concentration",
            "metric": "top10_share",
            "observed_value": 0.55,
            "ai_interpretation": {
                "summary": (
                    "Revenue is concentrated among a small "
                    "group of customers."
                ),
                "why_it_matters": "Concentration risk.",
                "potential_drivers": [],
                "recommended_action": (
                    "Review top accounts for renewal risk."
                ),
                "caveats": [],
                "layer": "interpretation",
                "source": "fallback",
            },
            "recommendation": "Review top accounts for renewal risk.",
        },
        {
            "insight_id": "i3",
            "title": "Margin Compression",
            "finding": "Gross margin fell 2.4 points period over period.",
            "tier": "important",
            "importance": "medium",
            "category": "Profitability",
            "insight_type": "trend",
            "metric": "gross_margin",
            "observed_value": -0.024,
            "ai_interpretation": {
                "summary": "Margin pressure may reduce operating flexibility.",
                "why_it_matters": "Profitability signal.",
                "potential_drivers": [],
                "recommended_action": (
                    "Inspect product mix and discounting in the period."
                ),
                "caveats": [],
                "layer": "interpretation",
                "source": "fallback",
            },
        },
    ]


class TestInsightExecutiveBrief(unittest.TestCase):

    def test_responsibility_is_ai_allowed(self):
        self.assertTrue(is_ai_allowed_responsibility("executive_brief"))
        assert_ai_not_calculation_engine("executive_brief")
        self.assertFalse(
            EXECUTIVE_BRIEF_CONSTRAINTS["may_invent_numbers"]
        )
        self.assertEqual(
            EXECUTIVE_BRIEF_CONSTRAINTS["target_reading_seconds"],
            60,
        )

    def test_fact_pack_uses_top_insights_only(self):
        insights = _sample_insights()
        pack = build_executive_brief_fact_pack(
            insights,
            product_name="Revenue Pulse",
            business_purpose="Monitor revenue risk",
            total_discovered=27,
        )

        self.assertIn("constraints", pack)
        self.assertIn("what_matters_most", pack)
        self.assertIn("cross_insight_signals", pack)
        self.assertIn("data_quality_limitations", pack)
        self.assertNotIn("dataframe", pack)
        self.assertNotIn("raw_rows", pack)
        self.assertLessEqual(
            len(pack["what_matters_most"]),
            DEFAULT_BRIEF_INSIGHT_CAP,
        )
        self.assertEqual(pack["what_matters_most"][0]["fact"], insights[0]["finding"])
        self.assertEqual(
            pack["product_context"]["product_name"],
            "Revenue Pulse",
        )
        self.assertTrue(
            any("Null region" in item or "excluded" in item.lower()
                for item in pack["data_quality_limitations"])
            or pack["data_quality_limitations"]
        )

    def test_brief_contract_shape_and_concision(self):
        brief = generate_fallback_insight_executive_brief(
            _sample_insights(),
            product_name="Revenue Pulse",
        )

        self.assertTrue(
            REQUIRED_EXECUTIVE_BRIEF_KEYS.issubset(set(brief))
        )
        self.assertEqual(len(brief["what_matters_most"]), 3)
        self.assertTrue(brief["why_it_matters"])
        self.assertTrue(brief["leadership_investigate"])
        self.assertLessEqual(
            len(brief["leadership_investigate"]),
            5,
        )
        self.assertLessEqual(
            brief["estimated_reading_seconds"],
            TARGET_READING_SECONDS,
        )
        # Facts stay deterministic copies.
        self.assertIn(
            "18%",
            brief["what_matters_most"][0]["fact"],
        )
        self.assertNotIn("this happened because", brief["why_it_matters"].lower())

    def test_sanitize_drops_invented_numbers(self):
        pack = build_executive_brief_fact_pack(_sample_insights())
        polluted = {
            "what_matters_most": pack["what_matters_most"],
            "why_it_matters": (
                "Revenue collapsed by 91.3% because of a secret competitor."
            ),
            "leadership_investigate": [
                "Investigate shared drivers across top insights."
            ],
            "source": "ai",
        }
        cleaned = sanitize_executive_brief(
            polluted,
            fact_pack=pack,
            source="ai",
        )
        self.assertNotIn("91.3", cleaned["why_it_matters"])
        self.assertNotIn(
            "this happened because",
            cleaned["why_it_matters"].lower(),
        )

    def test_prompt_and_ai_service(self):
        pack = build_executive_brief_fact_pack(_sample_insights())
        prompt = build_insight_executive_brief_prompt(pack)
        self.assertIn("30–60 second", prompt)
        self.assertIn("What matters most", prompt)
        self.assertIn("must NOT invent" if "must NOT invent" in prompt else "Do NOT invent", prompt)
        self.assertIn("leadership", prompt.lower())

        brief = generate_insight_executive_brief(
            _sample_insights(),
            product_name="Revenue Pulse",
        )
        self.assertEqual(brief["source"], "fallback")
        self.assertEqual(brief["layer"], "executive_brief")

    def test_attaches_to_initial_results(self):
        insights = _sample_insights()
        results = build_initial_results(insights)
        # Pretend explanations already attached.
        results["recommended_insights"] = insights
        updated = attach_executive_brief_to_initial_results(
            results,
            product_name="Revenue Pulse",
        )
        brief = updated["executive_brief"]
        self.assertIsNotNone(brief)
        self.assertGreaterEqual(len(brief["what_matters_most"]), 3)
        # Fallback builder used via attach when generator omitted.
        rebuilt = build_fallback_executive_brief(
            build_executive_brief_fact_pack(insights)
        )
        self.assertTrue(rebuilt["why_it_matters"])


if __name__ == "__main__":
    unittest.main()
