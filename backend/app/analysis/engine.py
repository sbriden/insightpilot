from .registry import MODULES
from .candidates import (
    candidate_analysis_ids,
    generate_analytical_candidates,
)
from .insights.findings import (
    collect_candidate_findings_from_dashboards,
    serialize_candidate_finding,
)
from .insights.insight import (
    collect_promoted_insights_from_dashboards,
)
from .insights.validation import (
    collect_validated_findings_from_dashboards,
)
from app.products.catalog import (
    get_analysis_ids_for_products,
)


def generate_analysis_dashboards(
    context,
):

    dashboards = []

    candidate_result = (
        generate_analytical_candidates(
            capabilities=context.capabilities,
            dataset_archetype=(
                context.dataset_archetype
            ),
        )
    )

    context.analytical_candidates = (
        candidate_result.get(
            "candidates",
            [],
        )
    )

    candidate_ids = candidate_analysis_ids(
        candidate_result,
        executable_only=True,
    )

    product_analysis_ids = (
        get_analysis_ids_for_products(
            context.selected_product_ids
        )
    )

    for module in MODULES:

        # Primary gate: semantic capability candidates.
        if module.id not in candidate_ids:
            continue

        # Optional product selection narrows further.
        if (
            product_analysis_ids is not None
            and module.id not in product_analysis_ids
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

        payload = dashboard.to_dict()

        # Normalize findings to plain dicts so dashboards,
        # AnalysisContext, and persistence share one shape.
        payload["candidate_findings"] = [
            serialized
            for serialized in (
                serialize_candidate_finding(item)
                for item in (
                    payload.get("candidate_findings")
                    or []
                )
            )
            if serialized is not None
        ]

        payload["validated_findings"] = (
            collect_validated_findings_from_dashboards(
                [payload],
                scope_by_dashboard=False,
            )
        )

        payload["promoted_insights"] = (
            collect_promoted_insights_from_dashboards(
                [payload],
                scope_by_dashboard=False,
            )
        )

        dashboards.append(payload)

    # Aggregate onto context after dashboards are complete so
    # executive brief / products can read findings without
    # re-running modules.
    context.candidate_findings = (
        collect_candidate_findings_from_dashboards(
            dashboards,
            scope_by_dashboard=False,
        )
    )

    context.validated_findings = (
        collect_validated_findings_from_dashboards(
            dashboards,
            scope_by_dashboard=False,
        )
    )

    context.promoted_insights = (
        collect_promoted_insights_from_dashboards(
            dashboards,
            scope_by_dashboard=False,
        )
    )

    from app.analysis.insights.traceability import (
        stamp_insights_dataset_traceability,
    )

    context.promoted_insights = stamp_insights_dataset_traceability(
        context.promoted_insights,
        dataset_id=getattr(context, "dataset_id", None),
        dataset_version=getattr(context, "dataset_version", None),
        dataset_identity=getattr(context, "dataset_identity", None),
        dataset_label=getattr(context, "source_dataset", None),
        analyzed_at=getattr(context, "created_at", None),
    )

    # Keep per-dashboard promoted insights aligned with context stamp.
    for dashboard in dashboards:
        if not isinstance(dashboard, dict):
            continue
        dashboard["promoted_insights"] = (
            stamp_insights_dataset_traceability(
                dashboard.get("promoted_insights") or [],
                dataset_id=getattr(context, "dataset_id", None),
                dataset_version=getattr(
                    context, "dataset_version", None
                ),
                dataset_identity=getattr(
                    context, "dataset_identity", None
                ),
                dataset_label=getattr(
                    context, "source_dataset", None
                ),
                analyzed_at=getattr(context, "created_at", None),
            )
        )

    from app.analysis.insights.initial_results import (
        build_initial_results,
    )

    context.insight_initial_results = build_initial_results(
        context.promoted_insights
    )

    # When products will be generated, they run AI enrichment once
    # and cache overlays. Skip a duplicate provider pass here —
    # otherwise create-flow analyze waits on OpenAI twice.
    selected_products = getattr(
        context,
        "selected_product_ids",
        None,
    ) or []
    if not selected_products:
        from app.services.ai import enrich_insights_with_ai

        (
            context.promoted_insights,
            context.insight_initial_results,
            _,
        ) = enrich_insights_with_ai(
            promoted_insights=context.promoted_insights,
            initial_results=context.insight_initial_results,
            allow_provider=True,
        )

    return dashboards
