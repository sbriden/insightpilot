"""Tests for entity key/label resolution and display mapping."""

from __future__ import annotations

import pandas as pd
import unittest

from app.analysis.column_resolver import (
    ColumnResolver,
    apply_entity_labels,
    build_entity_label_map,
    format_entity_label,
    labeled_entity_pair,
)


class TestEntityDisplayLabels(unittest.TestCase):

    def test_prefers_id_for_key_and_name_for_label(self):
        resolver = ColumnResolver(
            [
                {"name": "customer_id", "role": "categorical"},
                {"name": "customer_name", "role": "categorical"},
                {"name": "product_id", "role": "categorical"},
                {"name": "product_name", "role": "categorical"},
                {"name": "revenue", "role": "numeric"},
            ]
        )

        self.assertEqual(resolver.customer_key(), "customer_id")
        self.assertEqual(resolver.customer_label(), "customer_name")
        self.assertEqual(resolver.product_key(), "product_id")
        self.assertEqual(resolver.product_label(), "product_name")
        self.assertEqual(resolver.customer(), "customer_id")
        self.assertEqual(resolver.product(), "product_id")

    def test_label_falls_back_to_key_when_name_missing(self):
        resolver = ColumnResolver(
            [
                {"name": "customer_id", "role": "categorical"},
                {"name": "product_id", "role": "categorical"},
            ]
        )
        self.assertEqual(resolver.customer_label(), "customer_id")
        self.assertEqual(resolver.product_label(), "product_id")

    def test_build_and_apply_label_map(self):
        source = pd.DataFrame(
            {
                "customer_id": [1, 1, 2],
                "customer_name": ["Acme", "Acme", "Beta Co"],
                "revenue": [10, 20, 30],
            }
        )
        summary = pd.DataFrame(
            {
                "customer_id": [1, 2],
                "revenue": [30, 30],
            }
        )

        label_map = build_entity_label_map(
            source,
            "customer_id",
            "customer_name",
        )
        self.assertEqual(label_map[1], "Acme")
        self.assertEqual(label_map[2], "Beta Co")

        labeled = apply_entity_labels(
            summary,
            key_column="customer_id",
            label_map=label_map,
        )
        self.assertEqual(
            list(labeled["customer_id"]),
            ["Acme", "Beta Co"],
        )
        self.assertEqual(
            format_entity_label(1, label_map),
            "Acme",
        )
        self.assertEqual(
            labeled_entity_pair(
                1,
                2,
                left_map=label_map,
                right_map=label_map,
            ),
            "Acme → Beta Co",
        )

    def test_no_map_when_label_column_equals_key(self):
        source = pd.DataFrame({"customer_id": [1, 2]})
        self.assertEqual(
            build_entity_label_map(
                source,
                "customer_id",
                "customer_id",
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()
