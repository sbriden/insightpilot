"""Product type (user_created vs native) on catalog and instances."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.products.catalog import (
    get_product_definition,
    resolve_product_type,
    serialize_product_definition,
)
from app.products.models import (
    PRODUCT_TYPE_NATIVE,
    PRODUCT_TYPE_USER_CREATED,
    DataProduct,
)
from app.products.service import (
    _serialize_product,
)


class ProductTypeTests(unittest.TestCase):

    def test_fantasy_is_native(self):
        product = get_product_definition(
            "fantasy_football"
        )
        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(
            product.product_type,
            PRODUCT_TYPE_NATIVE,
        )
        serialized = serialize_product_definition(
            product
        )
        self.assertEqual(
            serialized["product_type"],
            PRODUCT_TYPE_NATIVE,
        )

    def test_sales_products_are_user_created(self):
        for product_id in (
            "customer_intelligence",
            "product_performance",
            "sales_performance",
        ):
            product = get_product_definition(
                product_id
            )
            self.assertIsNotNone(product)
            assert product is not None
            self.assertEqual(
                product.product_type,
                PRODUCT_TYPE_USER_CREATED,
            )

    def test_resolve_prefers_stored_value(self):
        self.assertEqual(
            resolve_product_type(
                "fantasy_football",
                PRODUCT_TYPE_USER_CREATED,
            ),
            PRODUCT_TYPE_USER_CREATED,
        )

    def test_resolve_falls_back_to_catalog(self):
        self.assertEqual(
            resolve_product_type(
                "fantasy_football",
                None,
            ),
            PRODUCT_TYPE_NATIVE,
        )
        self.assertEqual(
            resolve_product_type(
                "customer_intelligence",
                "",
            ),
            PRODUCT_TYPE_USER_CREATED,
        )
        self.assertEqual(
            resolve_product_type(None, None),
            PRODUCT_TYPE_USER_CREATED,
        )

    def test_resolve_legacy_pre_canned_alias(self):
        self.assertEqual(
            resolve_product_type(
                "fantasy_football",
                "pre_canned",
            ),
            PRODUCT_TYPE_NATIVE,
        )

    def test_serialize_product_includes_type(self):
        now = datetime.now(timezone.utc)
        product = DataProduct(
            id="fantasy_football__abc__v1",
            name="Fantasy Football",
            description="test",
            product_type=PRODUCT_TYPE_NATIVE,
            definition_id="fantasy_football",
            created_at=now,
            updated_at=now,
        )
        serialized = _serialize_product(product)
        self.assertEqual(
            serialized["product_type"],
            PRODUCT_TYPE_NATIVE,
        )


if __name__ == "__main__":
    unittest.main()
