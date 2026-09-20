"""
Tests for the Alpha Initial Results Contract.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.initial_results import (
    DEFAULT_RECOMMENDED_CAP,
    build_initial_results,
    select_recommended_insights,
)


def _insight(
    *,
    insight_id: str,
    tier: str,
    score: float,
    title: str | None = None,
) -> dict:
    return {
        "insight_id": insight_id,
        "title": title or insight_id,
        "tier": tier,
        "metric": "m",
        "scoring": {"total": score},
    }


class TestInsightInitialResults(unittest.TestCase):

    def test_contract_shape_and_counts(self):
        insights = [
            *[_insight(insight_id=f"c{i}", tier="critical", score=90 - i) for i in range(3)],
            *[_insight(insight_id=f"i{i}", tier="important", score=80 - i) for i in range(7)],
            *[_insight(insight_id=f"s{i}", tier="supporting", score=50 - i) for i in range(17)],
        ]

        results = build_initial_results(insights)

        self.assertEqual(results["total_discovered"], 27)
        self.assertEqual(results["tier_counts"]["tier_1"], 3)
        self.assertEqual(results["tier_counts"]["tier_2"], 7)
        self.assertEqual(results["tier_counts"]["tier_3"], 17)
        self.assertEqual(results["recommended_cap"], DEFAULT_RECOMMENDED_CAP)
        self.assertEqual(results["recommended_count"], 5)
        self.assertEqual(len(results["recommended_insights"]), 5)
        self.assertIn("These are the 5 things", results["headline"])
        self.assertIn("Total insights discovered: 27", results["summary"])
        self.assertIn("Recommended insights to surface: 5", results["summary"])

    def test_recommended_prefers_critical_then_important(self):
        insights = [
            _insight(insight_id="support-high", tier="supporting", score=99),
            _insight(insight_id="important-a", tier="important", score=70),
            _insight(insight_id="critical-a", tier="critical", score=60),
            _insight(insight_id="critical-b", tier="critical", score=80),
            _insight(insight_id="important-b", tier="important", score=75),
            _insight(insight_id="important-c", tier="important", score=65),
        ]

        recommended = select_recommended_insights(insights, cap=5)
        ids = [item["insight_id"] for item in recommended]

        self.assertEqual(
            ids,
            [
                "critical-b",
                "critical-a",
                "important-b",
                "important-a",
                "important-c",
            ],
        )
        self.assertNotIn("support-high", ids)

    def test_fills_with_supporting_only_when_needed(self):
        insights = [
            _insight(insight_id="critical-a", tier="critical", score=90),
            _insight(insight_id="important-a", tier="important", score=80),
            _insight(insight_id="support-a", tier="supporting", score=40),
            _insight(insight_id="support-b", tier="supporting", score=30),
        ]

        recommended = select_recommended_insights(insights, cap=4)
        ids = [item["insight_id"] for item in recommended]
        self.assertEqual(
            ids,
            ["critical-a", "important-a", "support-a", "support-b"],
        )

    def test_empty_insights(self):
        results = build_initial_results([])
        self.assertEqual(results["total_discovered"], 0)
        self.assertEqual(results["recommended_count"], 0)
        self.assertEqual(results["recommended_insights"], [])
        self.assertIn("No insights", results["headline"])


if __name__ == "__main__":
    unittest.main()
