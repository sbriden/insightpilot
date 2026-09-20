"""
Tests for analytical candidate generation from semantic capabilities.
"""

from __future__ import annotations

import unittest

from app.analysis.candidates import (
    generate_analytical_candidates,
)
from app.analysis.engine import (
    generate_analysis_dashboards,
)
from app.core.analysis_context import (
    AnalysisContext,
)
from app.datasets.capability_detection import (
    detect_analytical_capabilities,
)
from app.datasets.concept_identification import (
    identify_business_concepts,
)
from app.datasets.dataset_classification import (
    classify_dataset,
)


def _concepts_for_columns(
    column_names: list[str],
) -> list[dict]:

    result = identify_business_concepts(
        [
            {"name": name}
            for name in column_names
        ]
    )

    return result["concepts"]


def _candidate_ids(
    result: dict,
) -> set[str]:

    return {
        item["id"]
        for item in result["candidates"]
    }


class TestAnalyticalCandidates(
    unittest.TestCase
):

    def test_sales_dataset_yields_sales_candidates(
        self,
    ):

        concepts = _concepts_for_columns(
            [
                "Customer",
                "Product",
                "Order Date",
                "Revenue",
            ]
        )

        capabilities = detect_analytical_capabilities(
            concepts
        )["capabilities"]

        archetype = classify_dataset(
            concepts
        )

        result = generate_analytical_candidates(
            capabilities=capabilities,
            dataset_archetype={
                "primary": archetype[
                    "primary_archetype"
                ],
            },
        )

        ids = _candidate_ids(result)

        self.assertEqual(
            archetype["primary_archetype"],
            "sales_revenue",
        )

        self.assertTrue(
            ids.intersection(
                {
                    "revenue_trends",
                    "customer_concentration",
                    "customer_performance",
                    "product_performance",
                    "cross_sell",
                }
            )
        )

        self.assertTrue(
            all(
                item["domain"] == "sales"
                for item in result["candidates"]
            )
        )

        self.assertFalse(
            ids.intersection(
                {
                    "workforce_composition",
                    "compensation_analysis",
                    "department_comparison",
                }
            )
        )

    def test_workforce_dataset_yields_workforce_candidates(
        self,
    ):

        concepts = _concepts_for_columns(
            [
                "Employee",
                "Department",
                "Salary",
            ]
        )

        capabilities = detect_analytical_capabilities(
            concepts
        )["capabilities"]

        archetype = classify_dataset(
            concepts
        )

        result = generate_analytical_candidates(
            capabilities=capabilities,
            dataset_archetype={
                "primary": archetype[
                    "primary_archetype"
                ],
            },
        )

        ids = _candidate_ids(result)

        self.assertEqual(
            archetype["primary_archetype"],
            "workforce",
        )

        self.assertTrue(
            ids.intersection(
                {
                    "workforce_composition",
                    "compensation_analysis",
                    "department_comparison",
                    "workforce_segmentation",
                }
            )
        )

        self.assertTrue(
            all(
                item["domain"] == "workforce"
                for item in result["candidates"]
            )
        )

        self.assertFalse(
            ids.intersection(
                {
                    "revenue_trends",
                    "customer_concentration",
                    "customer_performance",
                    "cross_sell",
                    "product_performance",
                }
            )
        )

    def test_engine_does_not_run_sales_modules_for_workforce(
        self,
    ):

        concepts = _concepts_for_columns(
            [
                "Employee",
                "Department",
                "Salary",
            ]
        )

        capabilities = detect_analytical_capabilities(
            concepts
        )["capabilities"]

        archetype = classify_dataset(
            concepts
        )

        context = AnalysisContext(
            profile={},
            metrics={},
            classification={
                "type": "Unknown",
                "confidence": 0,
            },
            capabilities=capabilities,
            dataset_archetype={
                "primary": archetype[
                    "primary_archetype"
                ],
                "confidence": archetype[
                    "confidence"
                ],
                "alternatives": [],
            },
            selected_product_ids=None,
        )

        dashboards = (
            generate_analysis_dashboards(
                context
            )
        )

        candidate_ids = {
            item["id"]
            for item in context.analytical_candidates
        }

        self.assertTrue(
            candidate_ids.intersection(
                {
                    "workforce_composition",
                    "compensation_analysis",
                }
            )
        )

        # Workforce candidates are not executable yet,
        # so the engine must not emit sales dashboards.
        self.assertEqual(dashboards, [])

        sales_ids = {
            "revenue_trends",
            "customer_concentration",
            "cross_sell",
        }

        self.assertFalse(
            candidate_ids.intersection(
                sales_ids
            )
        )

    def test_candidate_structure(
        self,
    ):

        concepts = _concepts_for_columns(
            [
                "Customer",
                "Order Date",
                "Revenue",
            ]
        )

        capabilities = detect_analytical_capabilities(
            concepts
        )["capabilities"]

        result = generate_analytical_candidates(
            capabilities=capabilities,
            dataset_archetype={
                "primary": "sales_revenue",
            },
        )

        self.assertIn("candidates", result)
        self.assertIn(
            "candidate_count",
            result,
        )

        for item in result["candidates"]:

            self.assertIn("id", item)
            self.assertIn("title", item)
            self.assertIn("domain", item)
            self.assertIn(
                "required_capabilities",
                item,
            )
            self.assertIn(
                "confidence",
                item,
            )
            self.assertIn(
                "explanation",
                item,
            )
            self.assertTrue(
                item["explanation"]
            )


if __name__ == "__main__":

    unittest.main()
