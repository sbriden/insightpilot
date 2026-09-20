"""Tests for Fantasy Football semantic framework integration."""

from __future__ import annotations

import unittest

import pandas as pd

from app.analysis.candidates import (
    generate_analytical_candidates,
)
from app.analysis.column_resolver import ColumnResolver
from app.analysis.insights.fantasy_signals import RULES
from app.analysis.insights.engine import InsightEngine
from app.analysis.insights.validation import (
    is_insight_eligible,
    validate_finding,
)
from app.analysis.insights.insight import promote_finding
from app.analysis.modules.fantasy_signals import (
    FantasySignalsModule,
)
from app.core.analysis_context import AnalysisContext
from app.datasets.capability_detection import (
    detect_analytical_capabilities,
)
from app.datasets.concept_identification import (
    identify_business_concepts,
)
from app.datasets.dataset_classification import (
    classify_dataset,
)
from app.datasets.definitions import DATASET_TYPES
from app.products.catalog import (
    get_product_definition,
)


class FantasySemanticIntegrationTests(unittest.TestCase):

    def test_concepts_identify_fantasy_columns(self):
        columns = [
            {"name": name}
            for name in [
                "player_id",
                "season",
                "week",
                "signal_type",
                "signal_strength",
                "confidence",
                "fantasy_points",
                "targets",
            ]
        ]
        result = identify_business_concepts(columns)
        by_concept = {
            item["concept"]: item
            for item in result["concepts"]
        }
        self.assertIn("Player", by_concept)
        self.assertIn("SignalType", by_concept)
        self.assertIn("SignalStrength", by_concept)
        self.assertIn("FantasyPoints", by_concept)
        self.assertIn("Targets", by_concept)

    def test_classification_fantasy_sports(self):
        concepts = [
            {
                "concept": "Player",
                "role": "entity",
                "confidence": 0.95,
                "sourceColumn": "player_id",
            },
            {
                "concept": "SignalType",
                "role": "category",
                "confidence": 0.95,
                "sourceColumn": "signal_type",
            },
            {
                "concept": "SignalStrength",
                "role": "measure",
                "confidence": 0.95,
                "sourceColumn": "signal_strength",
            },
            {
                "concept": "Season",
                "role": "category",
                "confidence": 0.9,
                "sourceColumn": "season",
            },
            {
                "concept": "Week",
                "role": "category",
                "confidence": 0.9,
                "sourceColumn": "week",
            },
        ]
        result = classify_dataset(concepts)
        self.assertEqual(
            result["primary_archetype"],
            "fantasy_sports",
        )

    def test_candidates_include_fantasy_signals(self):
        concepts = [
            {
                "concept": "Player",
                "role": "entity",
                "confidence": 0.95,
                "sourceColumn": "player_id",
            },
            {
                "concept": "SignalType",
                "role": "category",
                "confidence": 0.95,
                "sourceColumn": "signal_type",
            },
            {
                "concept": "SignalStrength",
                "role": "measure",
                "confidence": 0.95,
                "sourceColumn": "signal_strength",
            },
        ]
        capabilities = detect_analytical_capabilities(
            concepts
        )["capabilities"]
        candidates = generate_analytical_candidates(
            capabilities=capabilities,
            dataset_archetype={
                "primary": "fantasy_sports",
                "confidence": 0.9,
            },
        )
        ids = {
            item["id"]
            for item in candidates["candidates"]
        }
        self.assertIn("fantasy_signals", ids)
        fantasy = next(
            item
            for item in candidates["candidates"]
            if item["id"] == "fantasy_signals"
        )
        self.assertTrue(fantasy["executable"])

    def test_module_emits_findings_and_promotes(self):
        frame = pd.DataFrame(
            [
                {
                    "player_id": "ip_player_00000001",
                    "season": 2024,
                    "week": 3,
                    "signal_type": "BREAKOUT_CANDIDATE",
                    "signal_strength": 78.0,
                    "confidence": 70.0,
                },
                {
                    "player_id": "ip_player_00000002",
                    "season": 2024,
                    "week": 3,
                    "signal_type": "BUY_LOW",
                    "signal_strength": 65.0,
                    "confidence": 62.0,
                },
            ]
        )
        profiles = [
            {"name": name, "role": "unknown"}
            for name in frame.columns
        ]
        context = AnalysisContext(
            profile={"row_count": len(frame)},
            metrics={},
            classification={},
            dataframe=frame,
            column_profiles=profiles,
            capabilities=[
                {
                    "capability": "fantasy_signal_analysis",
                    "supported": True,
                    "confidence": 0.95,
                }
            ],
            dataset_archetype={
                "primary": "fantasy_sports",
                "confidence": 0.9,
            },
            analytical_candidates={
                "candidates": [
                    {
                        "id": "fantasy_signals",
                        "executable": True,
                    }
                ]
            },
            dataset_id="nflverse:fantasy_signal:2024",
            dataset_identity="nflverse:fantasy_signal:2024",
            source_dataset="fantasy_signal (2024)",
        )

        module = FantasySignalsModule()
        self.assertTrue(module.supports(context))
        dashboard = module.run(context)
        self.assertGreaterEqual(
            len(dashboard.candidate_findings),
            1,
        )

        finding = dashboard.candidate_findings[0]
        validated = validate_finding(finding)
        self.assertIsNotNone(validated)
        self.assertTrue(validated.insight_eligible)
        self.assertTrue(
            is_insight_eligible(validated)
        )
        insight = promote_finding(finding)
        self.assertIsNotNone(insight)
        provenance = finding.provenance
        dataset_meta = provenance.dataset or {}
        if not isinstance(dataset_meta, dict):
            dataset_meta = {
                "dataset_identity": getattr(
                    dataset_meta,
                    "dataset_identity",
                    None,
                )
            }
        self.assertEqual(
            dataset_meta.get("dataset_identity"),
            "nflverse:fantasy_signal:2024",
        )

    def test_engine_rules_fire_for_breakout(self):
        facts = {
            "player_id": "ip_player_00000001",
            "player_label": "Test Player",
            "signal_type": "BREAKOUT_CANDIDATE",
            "signal_strength": 80.0,
            "confidence": 70.0,
            "season": 2024,
            "week": 4,
        }
        insights, findings = InsightEngine(
            RULES
        ).evaluate_with_findings(
            facts,
            analysis_type="fantasy_signals",
            source_columns=["player_id", "signal_type"],
            relevant_dimensions=["player"],
            dataset_identity="test:fantasy",
        )
        self.assertGreaterEqual(len(findings), 1)
        self.assertTrue(
            any(
                "Breakout" in (insight.title or "")
                for insight in insights
            )
        )

    def test_column_resolver_fantasy_fields(self):
        resolver = ColumnResolver(
            [
                {"name": "player_id"},
                {"name": "signal_type"},
                {"name": "signal_strength"},
                {"name": "confidence"},
                {"name": "season"},
                {"name": "week"},
            ]
        )
        self.assertEqual(
            resolver.player_key(),
            "player_id",
        )
        self.assertEqual(
            resolver.signal_type(),
            "signal_type",
        )
        self.assertEqual(
            resolver.signal_strength(),
            "signal_strength",
        )

    def test_catalog_fantasy_product(self):
        product = get_product_definition(
            "fantasy_football"
        )
        self.assertIsNotNone(product)
        self.assertIn(
            "player_overview",
            product.analyses,
        )
        self.assertNotIn(
            "waiver_wire",
            product.analyses,
        )
        self.assertEqual(
            product.product_type,
            "native",
        )
        type_ids = {
            item.id for item in DATASET_TYPES
        }
        self.assertIn("fantasy_football", type_ids)


if __name__ == "__main__":
    unittest.main()
