"""
Graceful AI failure + per-version AI overlay caching.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.ai_cache import (
    INSIGHT_AI_CACHE_KEY,
    apply_insight_ai_cache_to_product,
    build_insight_ai_cache,
    cache_has_usable_overlays,
    get_insight_ai_cache,
    merge_cached_explanations,
    stamp_metadata_with_ai_cache,
)
from app.services.ai import (
    enrich_insights_with_ai,
    generate_insight_executive_brief,
    generate_insight_explanation,
)
from app.services.ai_client import (
    AI_REASON_INVALID_OUTPUT,
    AI_REASON_NO_CREDENTIALS,
    AI_REASON_PROVIDER_UNAVAILABLE,
    AI_REASON_QUOTA_EXHAUSTED,
    AICompletionResult,
    extract_json_object,
    probe_ai_availability,
)


def _sample_insight(insight_id: str = "i1") -> dict:
    return {
        "insight_id": insight_id,
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
        "evidence": {
            "summary": "Northeast revenue declined 18%.",
            "metrics": [
                {
                    "key": "change",
                    "label": "Change",
                    "value": -0.18,
                    "unit": "ratio",
                }
            ],
        },
    }


class TestAIClientGracefulFailure(unittest.TestCase):

    def test_extract_json_object(self):
        self.assertEqual(
            extract_json_object('{"a": 1}'),
            {"a": 1},
        )
        self.assertEqual(
            extract_json_object('```json\n{"a": 2}\n```'),
            {"a": 2},
        )
        self.assertIsNone(extract_json_object("not json"))

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False)
    def test_probe_without_credentials(self):
        result = probe_ai_availability()
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, AI_REASON_NO_CREDENTIALS)

    @patch(
        "app.services.ai.complete_json",
        return_value=AICompletionResult(
            ok=False,
            reason=AI_REASON_PROVIDER_UNAVAILABLE,
            message="down",
            source="fallback",
        ),
    )
    @patch(
        "app.services.ai.probe_ai_availability",
        return_value=AICompletionResult(
            ok=True,
            reason="ok",
            source="ai",
        ),
    )
    def test_explanation_falls_back_when_provider_unavailable(
        self,
        _probe,
        _complete,
    ):
        contract = generate_insight_explanation(_sample_insight())
        self.assertEqual(contract["source"], "fallback")
        self.assertTrue(contract["summary"])

    @patch(
        "app.services.ai.complete_json",
        return_value=AICompletionResult(
            ok=False,
            reason=AI_REASON_QUOTA_EXHAUSTED,
            message="quota",
            source="fallback",
        ),
    )
    @patch(
        "app.services.ai.probe_ai_availability",
        return_value=AICompletionResult(
            ok=True,
            reason="ok",
            source="ai",
        ),
    )
    def test_brief_falls_back_when_quota_exhausted(self, _probe, _complete):
        brief = generate_insight_executive_brief([_sample_insight()])
        self.assertEqual(brief["source"], "fallback")
        self.assertTrue(brief["what_matters_most"])

    @patch(
        "app.services.ai.complete_json",
        return_value=AICompletionResult(
            ok=False,
            reason=AI_REASON_INVALID_OUTPUT,
            message="bad json",
            source="fallback",
        ),
    )
    @patch(
        "app.services.ai.probe_ai_availability",
        return_value=AICompletionResult(
            ok=True,
            reason="ok",
            source="ai",
        ),
    )
    def test_invalid_output_uses_fallback(self, _probe, _complete):
        contract = generate_insight_explanation(_sample_insight())
        self.assertEqual(contract["source"], "fallback")

    def test_allow_provider_false_skips_ai(self):
        with patch("app.services.ai.complete_json") as complete:
            contract = generate_insight_explanation(
                _sample_insight(),
                allow_provider=False,
            )
            complete.assert_not_called()
            self.assertEqual(contract["source"], "fallback")


class TestInsightAICache(unittest.TestCase):

    def test_build_and_reuse_cache_without_provider(self):
        insights = [_sample_insight("i1"), _sample_insight("i2")]
        promoted, results, status = enrich_insights_with_ai(
            promoted_insights=insights,
            product_name="Revenue Pulse",
            allow_provider=False,
        )
        self.assertEqual(status["mode"], "fallback")
        self.assertTrue(results.get("executive_brief"))

        cache = build_insight_ai_cache(
            promoted_insights=promoted,
            executive_brief=results.get("executive_brief"),
            status=status,
            recommended_insight_ids=results.get(
                "recommended_insight_ids"
            ),
        )
        self.assertTrue(cache_has_usable_overlays(cache))

        metadata = stamp_metadata_with_ai_cache({}, cache)
        self.assertIn(INSIGHT_AI_CACHE_KEY, metadata)
        self.assertIsNotNone(get_insight_ai_cache(metadata))

        # Rebuild as if reading from dashboards (no AI overlays).
        rebuilt = [
            {
                **item,
                "ai_interpretation": None,
                "explanation": None,
            }
            for item in promoted
        ]
        product = {
            "name": "Revenue Pulse",
            "business_purpose": "Monitor revenue",
            "metadata": metadata,
            "promoted_insights": rebuilt,
        }

        with patch(
            "app.services.ai.complete_json"
        ) as complete:
            apply_insight_ai_cache_to_product(
                product,
                generate_if_missing=False,
            )
            complete.assert_not_called()

        restored = product["promoted_insights"]
        self.assertTrue(
            any(
                (item.get("ai_interpretation") or {}).get("summary")
                for item in restored
            )
        )
        self.assertIsNotNone(product.get("executive_brief"))
        self.assertEqual(
            product["executive_brief"]["why_it_matters"],
            results["executive_brief"]["why_it_matters"],
        )

    def test_merge_cached_explanations_by_id(self):
        cache = {
            "explanations": {
                "i1": {
                    "summary": "Material regional decline.",
                    "why_it_matters": "Attention needed.",
                    "potential_drivers": [],
                    "recommended_action": "Investigate contributors.",
                    "caveats": [],
                    "layer": "interpretation",
                    "source": "ai",
                }
            }
        }
        merged = merge_cached_explanations(
            [_sample_insight("i1")],
            cache,
        )
        self.assertEqual(
            merged[0]["ai_interpretation"]["summary"],
            "Material regional decline.",
        )
        self.assertEqual(
            merged[0]["ai_interpretation"]["source"],
            "ai",
        )


if __name__ == "__main__":
    unittest.main()
