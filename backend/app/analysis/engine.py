from .registry import MODULES
from app.products.catalog import (
    get_analysis_ids_for_products,
)


def generate_analysis_dashboards(
    context,
):

    dashboards = []

    allowed_analysis_ids = (
        get_analysis_ids_for_products(
            context.selected_product_ids
        )
    )

    for module in MODULES:

        if (
            allowed_analysis_ids is not None
            and module.id not in allowed_analysis_ids
        ):
            continue

        if not module.supports(context):
            continue

        # Opportunity summary consumes the
        # dashboards generated before it.
        if module.id == "opportunity_summary":

            context.analysis_dashboards = (
                dashboards
            )

        dashboard = module.run(
            context
        )

        dashboards.append(
            dashboard.to_dict()
        )

    return dashboards