from typing import List

from .catalog import DATA_PRODUCTS
from .models import DataProduct

from app.analysis.column_resolver import ColumnResolver


class DataProductMatcher:

    def __init__(self, context):

        self.context = context

        self.resolver = ColumnResolver(
            context.column_profiles
        )

    def match(self) -> List[DataProduct]:

        capabilities = (
            self._get_capabilities()
        )

        products = []

        for definition in DATA_PRODUCTS:

            coverage = (
                self._calculate_coverage(
                    definition,
                    capabilities,
                )
            )

            if coverage <= 0:
                continue

            products.append(
                DataProduct(
                    id=definition.id,
                    name=definition.name,
                    description=definition.description,
                    status=self._get_status(
                        coverage
                    ),
                    coverage=coverage,
                    analyses=definition.analyses,
                )
            )

        return products

    def _get_capabilities(self):

        return {
            "customer": bool(
                self.resolver.customer()
            ),

            "sales": bool(
                self.resolver.sales()
            ),

            "profit": bool(
                self.resolver.profit()
            ),

            "product": bool(
                self.resolver.product()
            ),

            "date": bool(
                self.resolver.date()
            ),
        }

    def _calculate_coverage(
        self,
        definition,
        capabilities,
    ):

        required = (
            definition.required_fields
        )

        optional = (
            definition.optional_fields
        )

        required_matches = sum(
            capabilities.get(
                field,
                False,
            )
            for field in required
        )

        optional_matches = sum(
            capabilities.get(
                field,
                False,
            )
            for field in optional
        )

        if required and (
            required_matches == 0
        ):
            return 0

        required_score = (
            required_matches
            / len(required)
            if required
            else 1
        )

        optional_score = (
            optional_matches
            / len(optional)
            if optional
            else 1
        )

        return round(
            (
                required_score * 70
            )
            + (
                optional_score * 30
            )
        )

    def _get_status(
        self,
        coverage,
    ):

        if coverage >= 80:
            return "ready"

        if coverage >= 50:
            return "partial"

        return "limited"