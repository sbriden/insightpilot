"""
Tests for the deterministic Insight scoring model.
"""

from __future__ import annotations

import unittest

from app.analysis.insights.findings import make_candidate_finding
from app.analysis.insights.insight import (
    REQUIRED_INSIGHT_KEYS,
    SCORING_FIELDS,
    promote_finding,
    promote_validated_findings,
    serialize_insight,
)
from app.analysis.insights.scoring import (
    FACTOR_KEYS,
    FACTOR_WEIGHTS,
    SCORING_VERSION,
    score_insight,
    sort_insights_by_score,
)


class TestInsightScoringModel(unittest.TestCase):

    def _high_impact_finding(self):
        return make_candidate_finding(
            analysis_type="customer_concentration",
            metric="top10_revenue_share",
            observed_value=0.55,
            baseline=0.40,
            comparison="vs_threshold",
            magnitude=0.15,
            magnitude_unit="ratio",
            evidence=(
                "The top 10 customers generate 55.0% "
                "of total revenue."
            ),
            confidence="high",
            relevant_dimensions=["customer"],
            source_columns=["customer_id", "revenue"],
            rule_id="high_concentration",
            severity="high",
            title="High Revenue Concentration",
        )

    def _low_signal_finding(self):
        return make_candidate_finding(
            analysis_type="revenue_trends",
            metric="trend_change",
            observed_value=0.06,
            baseline=0.0,
            comparison="vs_prior_period",
            magnitude=0.06,
            magnitude_unit="ratio",
            evidence="Revenue grew 6% vs prior period.",
            confidence="low",
            relevant_dimensions=["period"],
            source_columns=["order_date", "revenue"],
            rule_id="modest_growth",
            severity="low",
            title="Modest Revenue Growth",
        )

    def test_business_finding_outranks_descriptive_observation(self):
        """
        Interesting ≠ important.

        Concentration risk should rank above a generic average /
        diversified health-check observation.
        """

        concentration = score_insight(
            {
                "title": "High Revenue Concentration",
                "finding": (
                    "Top 10 customers represent 47% of revenue."
                ),
                "metric": "top10_revenue_share",
                "insight_type": "concentration",
                "analysis_type": "customer_concentration",
                "rule_id": "high_concentration",
                "importance": "high",
                "confidence": "high",
                "observed_value": 0.47,
                "baseline": 0.40,
                "magnitude": 0.07,
                "magnitude_unit": "ratio",
                "recommendation": (
                    "Review dependency on top customers with sales."
                ),
            }
        )
        descriptive = score_insight(
            {
                "title": "Average Revenue per Transaction",
                "finding": (
                    "Revenue has an average of $1250 per transaction."
                ),
                "metric": "average_revenue_per_transaction",
                "insight_type": "comparison",
                "analysis_type": "revenue_trends",
                "rule_id": "average_revenue",
                "importance": "medium",
                "confidence": "high",
                "observed_value": 1250,
                "magnitude": 1250,
                "magnitude_unit": "currency",
                "recommendation": (
                    "Monitor average transaction value over time."
                ),
            }
        )

        self.assertGreater(concentration.total, descriptive.total)
        self.assertGreaterEqual(
            concentration.factors.business_impact,
            0.8,
        )
        self.assertLessEqual(
            descriptive.factors.business_impact,
            0.45,
        )

    def test_diversified_all_clear_ranks_below_concentration_risk(self):
        risk = score_insight(
            {
                "title": "High Revenue Concentration",
                "finding": "Top 10 customers represent 47% of revenue.",
                "metric": "top10_revenue_share",
                "insight_type": "concentration",
                "rule_id": "high_concentration",
                "importance": "high",
                "observed_value": 0.47,
                "magnitude": 0.07,
                "magnitude_unit": "ratio",
            }
        )
        diversified = score_insight(
            {
                "title": "Diversified Revenue Base",
                "finding": (
                    "Top 10 customers generate only 18% of revenue."
                ),
                "metric": "top10_revenue_share",
                "insight_type": "concentration",
                "rule_id": "low_concentration",
                "importance": "low",
                "observed_value": 0.18,
                "magnitude": -0.07,
                "magnitude_unit": "ratio",
            }
        )
        self.assertGreater(risk.total, diversified.total)

    def test_score_insight_emits_stable_contract(self):
        insight = promote_finding(
            self._high_impact_finding(),
            recommendation=(
                "Review diversification options with sales leadership."
            ),
            business_impact="Material concentration risk",
            data_quality_score=92,
        )
        self.assertIsNotNone(insight)

        score = insight.scoring
        self.assertIsNotNone(score)
        payload = score.to_dict()

        self.assertEqual(payload["version"], SCORING_VERSION)
        self.assertIn("total", payload)
        self.assertGreaterEqual(payload["total"], 0.0)
        self.assertLessEqual(payload["total"], 100.0)
        self.assertEqual(set(payload["factors"]), set(FACTOR_KEYS))
        self.assertEqual(set(payload["weights"]), set(FACTOR_KEYS))

        for key in FACTOR_KEYS:
            self.assertGreaterEqual(payload["factors"][key], 0.0)
            self.assertLessEqual(payload["factors"][key], 1.0)

    def test_scoring_is_deterministic(self):
        insight = promote_finding(self._high_impact_finding())
        first = score_insight(insight, severity="high").to_dict()
        second = score_insight(insight, severity="high").to_dict()
        self.assertEqual(first, second)

    def test_higher_signal_ranks_above_lower_signal(self):
        high = promote_finding(
            self._high_impact_finding(),
            recommendation=(
                "Assign an owner to diversify the top-account book."
            ),
            business_impact="Concentration threatens revenue durability",
            data_quality_score=95,
        )
        low = promote_finding(
            self._low_signal_finding(),
            require_insight_eligible=False,
            data_quality_score=60,
        )
        self.assertIsNotNone(high)
        self.assertIsNotNone(low)

        high_total = serialize_insight(high)["scoring"]["total"]
        low_total = serialize_insight(low)["scoring"]["total"]
        self.assertGreater(high_total, low_total)

    def test_promote_findings_sorted_by_score(self):
        findings = [
            self._low_signal_finding(),
            self._high_impact_finding(),
        ]
        # Force both through promotion for ordering assertion.
        promoted = promote_validated_findings(
            [
                {
                    **finding.to_dict(),
                    "severity": "high",
                    "importance": "high",
                }
                for finding in findings
            ]
        )
        self.assertGreaterEqual(len(promoted), 2)
        totals = [item["scoring"]["total"] for item in promoted]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_sort_insights_by_score_stable(self):
        ranked = sort_insights_by_score(
            [
                {
                    "insight_id": "b",
                    "metric": "m",
                    "scoring": {"total": 40},
                },
                {
                    "insight_id": "a",
                    "metric": "m",
                    "scoring": {"total": 80},
                },
                {
                    "insight_id": "c",
                    "metric": "m",
                    "scoring": {"total": 40},
                },
            ]
        )
        self.assertEqual(
            [item["insight_id"] for item in ranked],
            ["a", "b", "c"],
        )

    def test_actionability_rises_with_recommendation(self):
        bare = score_insight(
            {
                "insight_type": "trend",
                "confidence": "medium",
                "magnitude": 0.1,
                "magnitude_unit": "ratio",
            },
            severity="medium",
        )
        actionable = score_insight(
            {
                "insight_type": "trend",
                "confidence": "medium",
                "magnitude": 0.1,
                "magnitude_unit": "ratio",
                "recommendation": (
                    "Investigate the drivers of this change with finance."
                ),
            },
            severity="medium",
        )
        self.assertGreater(
            actionable.factors.actionability,
            bare.factors.actionability,
        )
        self.assertGreater(actionable.total, bare.total)

    def test_data_quality_factor_uses_explicit_score(self):
        scored = score_insight(
            {
                "insight_type": "risk",
                "confidence": "medium",
            },
            severity="high",
            data_quality_score=40,
        )
        self.assertAlmostEqual(scored.factors.data_quality, 0.4, places=2)

    def test_required_insight_keys_include_scoring(self):
        self.assertEqual(SCORING_FIELDS, {"scoring"})
        self.assertIn("scoring", REQUIRED_INSIGHT_KEYS)

        insight = promote_finding(self._high_impact_finding())
        payload = serialize_insight(insight)
        self.assertTrue(REQUIRED_INSIGHT_KEYS <= set(payload))
        self.assertIn("total", payload["scoring"])


if __name__ == "__main__":
    unittest.main()
