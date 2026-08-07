from .registry import MODULES


def generate_analysis_dashboards(context):

    dashboards = []

    for module in MODULES:

        if module.supports(context):

            dashboards.append(
                module.run(context)
            )

    return dashboards