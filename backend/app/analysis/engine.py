from .registry import MODULES


def generate_analysis_dashboards(
    context,
):

    dashboards = []

    for module in MODULES:

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