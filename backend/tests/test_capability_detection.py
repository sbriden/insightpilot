"""
Tests for analytical capability detection from business concepts.
"""

import unittest

from app.datasets.capability_detection import (
    detect_analytical_capabilities,
)
from app.datasets.concept_identification import (
    identify_business_concepts,
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


def _capability_map(
    concepts: list[dict],
) -> dict[str, dict]:

    result = detect_analytical_capabilities(
        concepts
    )

    return {
        item["capability"]: item
        for item in result["capabilities"]
    }


class TestCapabilityDetection(
    unittest.TestCase
):

    def test_customer_date_revenue_dataset(
        self,
    ):

        concepts = _concepts_for_columns(
            [
                "Customer",
                "Order Date",
                "Revenue",
            ]
        )

        capabilities = _capability_map(
            concepts
        )

        self.assertTrue(
            capabilities[
                "customer_analysis"
            ]["supported"]
        )

        self.assertTrue(
            capabilities[
                "time_series_analysis"
            ]["supported"]
        )

        self.assertTrue(
            capabilities[
                "trend_analysis"
            ]["supported"]
        )

        self.assertTrue(
            capabilities[
                "aggregation"
            ]["supported"]
        )

        self.assertFalse(
            capabilities[
                "product_analysis"
            ]["supported"]
        )

        self.assertIn(
            "Customer",
            capabilities[
                "customer_analysis"
            ]["explanation"],
        )

    def test_employee_department_salary_dataset(
        self,
    ):

        concepts = _concepts_for_columns(
            [
                "Employee",
                "Department",
                "Salary",
            ]
        )

        capabilities = _capability_map(
            concepts
        )

        self.assertFalse(
            capabilities[
                "customer_analysis"
            ]["supported"]
        )

        self.assertFalse(
            capabilities[
                "product_analysis"
            ]["supported"]
        )

        self.assertTrue(
            capabilities[
                "category_comparison"
            ]["supported"]
        )

        self.assertTrue(
            capabilities[
                "aggregation"
            ]["supported"]
        )

    def test_capability_structure(
        self,
    ):

        concepts = _concepts_for_columns(
            ["Customer", "Revenue"]
        )

        result = detect_analytical_capabilities(
            concepts
        )

        self.assertIn(
            "capabilities",
            result,
        )

        self.assertIn(
            "supported_count",
            result,
        )

        for item in result["capabilities"]:

            self.assertIn(
                "capability",
                item,
            )

            self.assertIn(
                "supported",
                item,
            )

            self.assertIn(
                "confidence",
                item,
            )

            self.assertIn(
                "required_concepts",
                item,
            )

            self.assertIn(
                "explanation",
                item,
            )

            self.assertIsInstance(
                item["required_concepts"],
                list,
            )

            self.assertTrue(
                item["explanation"]
            )


if __name__ == "__main__":

    unittest.main()
