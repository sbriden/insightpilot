from datetime import datetime
import hashlib

from .repository import (
    update_data_product as repository_update_data_product,
    create_data_product as repository_create_data_product,
    get_data_product as repository_get_data_product,
    get_data_products as repository_get_data_products,
    get_latest_by_dataset_identity as repository_get_latest_by_dataset_identity,
)

from .models import (
    DataProduct,
    DataProductAnalysis,
    DataProductInsight,
    DataProductMetric,
)

from .catalog import (
    expand_to_module_ids,
    get_product_definition,
    get_product_definitions,
    product_analysis_description,
    product_analysis_title,
    resolve_product_type,
)

from .identity import (
    build_dataset_identity,
    build_product_instance_id,
)

from .comparison import (
    compare_product_metrics,
)

from .change_summary import (
    merge_change_summaries,
)

from .data_quality_snapshot import (
    build_data_quality_snapshot,
    snapshot_from_product_metadata,
)

from .data_quality_changes import (
    compare_data_quality,
)

from app.analysis.insights.normalize import (
    normalize_insight_record,
)
from app.analysis.insights.findings import (
    collect_candidate_findings_from_dashboards,
)
from app.analysis.insights.insight import (
    collect_promoted_insights_from_dashboards,
)
from app.analysis.insights.traceability import (
    stamp_insights_dataset_traceability,
)
from app.analysis.insights.validation import (
    collect_validated_findings_from_dashboards,
)

from .executive_summary import (
    build_product_executive_summary,
)

from .health import (
    assess_product_health,
)


def _dashboard_title(
    dashboard: dict,
) -> str:

    return (
        dashboard.get("title")
        or dashboard.get("name")
        or dashboard.get("id")
        or "Analysis"
    )


def _dashboard_description(
    dashboard: dict,
) -> str:

    return (
        dashboard.get("description")
        or ""
    )


def _extract_metrics(
    dashboards: list[dict],
) -> list[DataProductMetric]:

    metrics = []

    for dashboard in dashboards:

        dashboard_id = dashboard.get(
            "id",
            "dashboard",
        )

        for index, metric in enumerate(
            dashboard.get("metrics", [])
        ):

            if not isinstance(
                metric,
                dict,
            ):
                continue

            raw_metric_id = (
                metric.get("id")
                or metric.get("name")
                or f"metric_{index}"
            )

            metric_id = (
                f"{dashboard_id}:{raw_metric_id}"
            )

            metrics.append(
                DataProductMetric(
                    id=metric_id,

                    name=(
                        metric.get("title")
                        or metric.get("name")
                        or raw_metric_id
                    ),

                    value=metric.get(
                        "value"
                    ),

                    description=(
                        metric.get(
                            "description"
                        )
                        or ""
                    ),

                    unit=metric.get(
                        "unit"
                    ),
                )
            )

    return metrics


def _extract_insights(
    dashboards: list[dict],
) -> list[DataProductInsight]:

    insights = []

    for dashboard in dashboards:

        dashboard_id = dashboard.get(
            "id",
            "dashboard",
        )

        for index, insight in enumerate(
            dashboard.get("insights", [])
        ):

            if not isinstance(
                insight,
                dict,
            ):
                continue

            raw_insight_id = (
                insight.get("id")
                or insight.get("rule_id")
                or f"insight_{index}"
            )

            insight_id = (
                f"{dashboard_id}:{raw_insight_id}"
            )

            # Titles are not unique (modules often fall
            # back to the dashboard title). Guarantee a
            # stable unique id per emitted insight.
            if any(
                existing.id == insight_id
                for existing in insights
            ):
                insight_id = (
                    f"{dashboard_id}:{raw_insight_id}"
                    f":{index}"
                )

            normalized = normalize_insight_record(
                insight,
                default_category=_dashboard_title(
                    dashboard
                ),
            )

            insights.append(
                DataProductInsight(
                    id=insight_id,

                    title=normalized["title"],

                    message=normalized["message"],

                    severity=normalized["severity"],

                    priority=normalized["priority"],

                    category=normalized["category"],

                    what_happened=normalized[
                        "what_happened"
                    ],

                    why_it_matters=normalized[
                        "why_it_matters"
                    ],

                    recommended_action=normalized[
                        "recommended_action"
                    ],
                )
            )

    return insights


def _extract_candidate_findings(
    dashboards: list[dict],
) -> list[dict]:
    """
    Lift candidate findings from selected dashboards.

    Persistence keeps findings inside dashboards JSONB;
    this top-level list is the product API convenience surface.
    """

    return collect_candidate_findings_from_dashboards(
        dashboards,
        scope_by_dashboard=True,
    )


def _extract_promoted_insights(
    dashboards: list[dict],
) -> list[dict]:
    """
    Promote validated findings into consistent business Insights.

    Persistence keeps findings inside dashboards JSONB; this
    top-level list is the product API convenience surface.
    Narrative recommended_action may populate interpretive
    recommendation — potential_drivers stay empty unless supplied.
    """

    return collect_promoted_insights_from_dashboards(
        dashboards,
        scope_by_dashboard=True,
    )


def _consolidated_promoted_insights(
    cached: list[dict] | None,
    dashboards: list[dict],
) -> list[dict]:
    """
    Prefer a fresh promote+consolidate from dashboards.

    Falls back to consolidating a cached list so older product
    payloads still drop cross-module duplicates (e.g. the same
    Loss-Making Products insight from Product Performance and
    Profitability).
    """

    from app.analysis.insights.redundancy import (
        consolidate_redundant_insights,
    )
    from app.analysis.insights.scoring import (
        sort_insights_by_score,
    )

    if dashboards:
        return _extract_promoted_insights(dashboards)

    if not cached:
        return []

    return sort_insights_by_score(
        consolidate_redundant_insights(cached)
    )


def _build_insight_initial_results(
    promoted_insights: list[dict] | None,
    *,
    product_name: str | None = None,
    business_purpose: str | None = None,
) -> dict:
    """Alpha Initial Results Contract for the product Insights surface."""

    from app.services.ai import enrich_insights_with_ai
    from app.analysis.insights.initial_results import (
        build_initial_results,
    )

    results = build_initial_results(promoted_insights or [])
    _, results, _ = enrich_insights_with_ai(
        promoted_insights=promoted_insights or [],
        initial_results=results,
        product_name=product_name,
        business_purpose=business_purpose,
        allow_provider=True,
    )
    return results


def _with_insight_explanations(
    promoted_insights: list[dict] | None,
    *,
    product_name: str | None = None,
    business_purpose: str | None = None,
    allow_provider: bool = True,
) -> tuple[list[dict], dict, dict]:
    """
    Stamp explanations + executive brief onto recommended Insights.

    Returns ``(promoted_insights, initial_results, ai_status)``.
    """

    from app.analysis.insights.initial_results import (
        build_initial_results,
    )
    from app.services.ai import enrich_insights_with_ai

    results = build_initial_results(promoted_insights or [])
    return enrich_insights_with_ai(
        promoted_insights=promoted_insights or [],
        initial_results=results,
        product_name=product_name,
        business_purpose=business_purpose,
        allow_provider=allow_provider,
    )

def _extract_validated_findings(
    dashboards: list[dict],
) -> list[dict]:
    """
    Lift validated findings from selected dashboards.

    Validated findings are a subset of candidates. Insight
    promotion is a further subset (insight_eligible only).
    """

    return collect_validated_findings_from_dashboards(
        dashboards,
        scope_by_dashboard=True,
    )


def _determine_status(
    coverage: float,
    can_analyze: bool,
) -> str:
    """
    Status is driven by field readiness for
    the product, not dataset quality score.
    """

    if not can_analyze:
        return "limited"

    if coverage >= 80:
        return "ready"

    if coverage >= 50:
        return "partial"

    return "limited"


def _serialize_product(
    product: DataProduct,
) -> dict:

    promoted_insights = _consolidated_promoted_insights(
        product.promoted_insights,
        product.dashboards or [],
    )

    from app.analysis.insights.ai_cache import (
        apply_insight_ai_cache_to_product,
        cache_has_usable_overlays,
        get_insight_ai_cache,
    )

    cached = get_insight_ai_cache(product.metadata)
    if cache_has_usable_overlays(cached):
        hydrated = apply_insight_ai_cache_to_product(
            {
                "name": product.name,
                "business_purpose": product.business_purpose,
                "metadata": product.metadata or {},
                "promoted_insights": promoted_insights,
            },
            generate_if_missing=False,
        )
        promoted_insights = hydrated.get("promoted_insights") or promoted_insights
        insight_initial_results = hydrated.get("insight_initial_results") or {}
        ai_status = hydrated.get("ai_status")
    else:
        # Detail serialize without a cache: deterministic overlays only.
        # Do not call the AI provider on every read.
        promoted_insights, insight_initial_results, ai_status = (
            _with_insight_explanations(
                promoted_insights,
                product_name=product.name,
                business_purpose=product.business_purpose,
                allow_provider=False,
            )
        )

    return {
        "id": product.id,

        "name": product.name,

        "description": product.description,

        "business_purpose": (
            product.business_purpose
        ),

        "product_type": resolve_product_type(
            product.definition_id,
            product.product_type,
        ),

        "source_dataset": (
            product.source_dataset
        ),

        "status": product.status,

        "coverage": product.coverage,

        "version": product.version,

        "definition_id": (
            product.definition_id
        ),

        "dataset_identity": (
            product.dataset_identity
        ),

        "previous_product_id": (
            product.previous_product_id
        ),

        "analyses": [
            {
                "id": analysis.id,
                "title": analysis.title,
                "description": (
                    analysis.description
                ),
            }
            for analysis
            in product.analyses
        ],

        "metrics": [
            {
                "id": metric.id,
                "name": metric.name,
                "value": metric.value,
                "description": (
                    metric.description
                ),
                "unit": metric.unit,
            }
            for metric
            in product.metrics
        ],

        "insights": [
            {
                "id": insight.id,
                "title": insight.title,
                "message": insight.message,
                "severity": (
                    insight.severity
                ),
                "priority": (
                    insight.priority
                    or insight.severity
                ),
                "category": insight.category,
                "what_happened": (
                    insight.what_happened
                ),
                "why_it_matters": (
                    insight.why_it_matters
                ),
                "recommended_action": (
                    insight.recommended_action
                ),
            }
            for insight
            in product.insights
        ],

        # Additive: derived from dashboards; not a DB column.
        "candidate_findings": (
            product.candidate_findings
            or _extract_candidate_findings(
                product.dashboards or []
            )
        ),

        # Additive: validated subset; not a DB column.
        "validated_findings": (
            product.validated_findings
            or _extract_validated_findings(
                product.dashboards or []
            )
        ),

        # Additive: Insights from eligible validated findings.
        # Always re-consolidate so cross-module redundancy fixes
        # apply even when an older promoted_insights list is cached.
        "promoted_insights": promoted_insights,

        # Alpha Initial Results Contract — recommended surface set.
        "insight_initial_results": insight_initial_results,

        # Concise leadership brief derived from explained Insights.
        "executive_brief": (
            insight_initial_results.get("executive_brief")
            if isinstance(insight_initial_results, dict)
            else None
        ),

        "ai_status": ai_status,

        "dashboards": (
            product.dashboards
        ),

        "change_summary": (
            product.change_summary
        ),

        "executive_summary": (
            product.executive_summary
        ),

        "health": product.health,

        "metadata": product.metadata,

        "created_at": (
            product.created_at.isoformat()
        ),

        "updated_at": (
            product.updated_at.isoformat()
        ),
    }


def _analysis_title(
    analysis_id: str,
) -> str:

    return (
        analysis_id
        .replace("_", " ")
        .title()
    )


def _product_field_coverage(
    required_fields: list[str],
    optional_fields: list[str],
    columns: list[str],
) -> tuple[float, float, bool]:
    """
    Return overall coverage, required coverage,
    and whether the product can be analyzed.

    Coverage = share of this product's field
    contract present in the mapped dataset.
    """

    column_set = set(columns)

    required = list(required_fields or [])
    optional = list(optional_fields or [])

    mapped_required = sum(
        1
        for field in required
        if field in column_set
    )

    mapped_optional = sum(
        1
        for field in optional
        if field in column_set
    )

    required_count = len(required)
    optional_count = len(optional)
    total = required_count + optional_count

    required_coverage = (
        100.0
        if required_count == 0
        else round(
            (mapped_required / required_count)
            * 100,
            1,
        )
    )

    overall_coverage = (
        100.0
        if total == 0
        else round(
            (
                (mapped_required + mapped_optional)
                / total
            )
            * 100,
            1,
        )
    )

    can_analyze = (
        mapped_required == required_count
    )

    return (
        overall_coverage,
        required_coverage,
        can_analyze,
    )


def _definitions_for_selection(
    selected_product_ids: list[str] | None,
):

    definitions = (
        get_product_definitions()
    )

    if selected_product_ids is None:
        return list(definitions)

    definition_by_id = {
        definition.id: definition
        for definition in definitions
    }

    ordered = []

    for product_id in selected_product_ids:

        normalized_id = str(
            product_id
        ).strip()

        if not normalized_id:
            continue

        definition = definition_by_id.get(
            normalized_id
        ) or get_product_definition(
            normalized_id
        )

        if definition is None:
            continue

        ordered.append(definition)

    return ordered


def generate_data_products(
    context,
    selected_product_ids: list[str] | None = None,
) -> list[dict]:
    """
    Generate a separate versioned result for each
    selected data product.

    When the dataset identity matches a prior
    product, a new version is created and key
    metrics are compared. Prior versions are
    never overwritten.
    """

    dashboards = (
        context.analysis_dashboards
        or []
    )

    columns = []

    if context.dataframe is not None:
        columns = list(
            context.dataframe.columns
        )

    classification_type = ""

    if isinstance(
        context.classification,
        dict,
    ):
        classification_type = str(
            context.classification.get("type")
            or context.classification.get(
                "dataset_type"
            )
            or ""
        )

    products = []

    upload_batch_id = hashlib.sha256(
        "|".join(
            [
                context.created_at.isoformat()
                if context.created_at
                else datetime.utcnow().isoformat(),
                classification_type.lower(),
                ",".join(
                    sorted(
                        str(column).strip()
                        for column in columns
                        if str(column).strip()
                    )
                ),
            ]
        ).encode("utf-8")
    ).hexdigest()[:32]

    profile_summary = {}

    if isinstance(
        context.profile,
        dict,
    ):
        profile_summary = (
            context.profile.get("summary")
            or {}
        )

    metrics_dataset = {}

    if isinstance(
        context.metrics,
        dict,
    ):
        metrics_dataset = (
            context.metrics.get("dataset")
            or {}
        )

    batch_created_at = datetime.utcnow()

    for definition in _definitions_for_selection(
        selected_product_ids
    ):

        analysis_ids = (
            definition.analyses or []
        )

        module_ids = expand_to_module_ids(
            analysis_ids
        )

        module_dashboards = {
            dashboard.get("id"): dashboard
            for dashboard in dashboards
            if dashboard.get("id") in module_ids
        }

        selected_dashboards = []
        analyses = []

        for analysis_id in analysis_ids:

            title = product_analysis_title(
                analysis_id
            )
            description = (
                product_analysis_description(
                    analysis_id
                )
            )

            module_dashboard = None
            for module_id in expand_to_module_ids(
                [analysis_id]
            ):
                module_dashboard = (
                    module_dashboards.get(module_id)
                )
                if module_dashboard is not None:
                    break

            if module_dashboard is not None:

                remapped = {
                    **module_dashboard,
                    "id": analysis_id,
                    "title": title,
                }
                if description:
                    remapped["summary"] = description

                selected_dashboards.append(remapped)

                analyses.append(
                    DataProductAnalysis(
                        id=analysis_id,
                        title=title,
                        description=(
                            description
                            or _dashboard_description(
                                module_dashboard
                            )
                            or module_dashboard.get(
                                "summary",
                                "",
                            )
                        ),
                    )
                )

            else:

                analyses.append(
                    DataProductAnalysis(
                        id=analysis_id,
                        title=title,
                        description=(
                            description
                            or "Not available for "
                            "this dataset."
                        ),
                    )
                )

        metrics = _extract_metrics(
            selected_dashboards
        )

        insights = _extract_insights(
            selected_dashboards
        )

        candidate_findings = (
            _extract_candidate_findings(
                selected_dashboards
            )
        )

        validated_findings = (
            _extract_validated_findings(
                selected_dashboards
            )
        )

        promoted_insights = (
            _extract_promoted_insights(
                selected_dashboards
            )
        )

        coverage, required_coverage, can_analyze = (
            _product_field_coverage(
                definition.required_fields,
                definition.optional_fields,
                columns,
            )
        )

        dataset_identity = (
            build_dataset_identity(
                definition_id=definition.id,
                classification_type=(
                    classification_type
                ),
                grain=definition.grain or "",
                required_fields=(
                    definition.required_fields
                    or []
                ),
                columns=columns,
            )
        )

        previous_product = (
            repository_get_latest_by_dataset_identity(
                dataset_identity
            )
        )

        previous_version = 0
        previous_product_id = None
        change_summary = None

        current_snapshot = (
            build_data_quality_snapshot(
                profile_summary=(
                    profile_summary
                ),

                metrics_dataset=(
                    metrics_dataset
                ),

                columns=columns,

                required_fields=(
                    definition.required_fields
                    or []
                ),

                optional_fields=(
                    definition.optional_fields
                    or []
                ),

                required_coverage=(
                    required_coverage
                ),

                overall_coverage=coverage,

                can_analyze=can_analyze,
            )
        )

        if previous_product:

            previous_version = int(
                previous_product.get(
                    "version",
                    1,
                )
                or 1
            )

            previous_product_id = (
                previous_product.get("id")
            )

            metric_summary = (
                compare_product_metrics(
                    previous_metrics=(
                        previous_product.get(
                            "metrics"
                        )
                        or []
                    ),
                    current_metrics=[
                        {
                            "id": metric.id,
                            "name": metric.name,
                            "value": metric.value,
                            "unit": metric.unit,
                        }
                        for metric in metrics
                    ],
                    previous_version=(
                        previous_version
                    ),
                    current_version=(
                        previous_version + 1
                    ),
                )
            )

            previous_snapshot = (
                snapshot_from_product_metadata(
                    previous_product.get(
                        "metadata"
                    )
                )
            )

            data_quality_summary = (
                compare_data_quality(
                    previous_snapshot=(
                        previous_snapshot
                    ),

                    current_snapshot=(
                        current_snapshot
                    ),

                    previous_version=(
                        previous_version
                    ),

                    current_version=(
                        previous_version + 1
                    ),
                )
            )

            change_summary = (
                merge_change_summaries(
                    metric_summary,
                    data_quality_summary,
                )
            )

        version = previous_version + 1

        promoted_insights = stamp_insights_dataset_traceability(
            promoted_insights,
            dataset_id=dataset_identity,
            dataset_version=version,
            dataset_identity=dataset_identity,
            dataset_label="uploaded_dataset",
            analyzed_at=(
                context.created_at
                if getattr(context, "created_at", None)
                else batch_created_at
            ),
        )
        promoted_insights, insight_initial_results, ai_status = (
            _with_insight_explanations(
                promoted_insights,
                product_name=definition.name,
                business_purpose=definition.business_purpose,
                allow_provider=True,
            )
        )

        from app.analysis.insights.ai_cache import (
            build_insight_ai_cache,
            stamp_metadata_with_ai_cache,
        )

        insight_ai_cache = build_insight_ai_cache(
            promoted_insights=promoted_insights,
            executive_brief=(
                insight_initial_results.get("executive_brief")
                if isinstance(insight_initial_results, dict)
                else None
            ),
            status=ai_status,
            recommended_insight_ids=(
                insight_initial_results.get("recommended_insight_ids")
                if isinstance(insight_initial_results, dict)
                else None
            ),
        )

        executive_summary = (
            build_product_executive_summary(
                product_name=definition.name,

                business_purpose=(
                    definition.business_purpose
                ),

                description=(
                    definition.description
                ),

                analyses=analyses,

                dashboards=selected_dashboards,

                metrics=metrics,

                insights=insights,

                promoted_insights=promoted_insights,

                change_summary=change_summary,
            )
        )

        product_status = _determine_status(
            coverage,
            can_analyze,
        )

        health = assess_product_health(
            can_analyze=can_analyze,

            required_coverage=required_coverage,

            overall_coverage=coverage,

            data_quality_score=(
                profile_summary.get(
                    "data_quality_score"
                )
            ),

            missing_percentage=(
                metrics_dataset.get(
                    "missing_percentage"
                )
            ),

            status=product_status,

            analysis_count=len(
                selected_dashboards
            ),

            expected_analysis_count=len(
                analysis_ids
            ),

            insights=[
                {
                    "priority": insight.priority,
                    "severity": insight.severity,
                }
                for insight in insights
            ],

            change_summary=change_summary,
        )

        product_id = (
            build_product_instance_id(
                definition.id,
                dataset_identity,
                version,
            )
        )

        product = DataProduct(

            id=product_id,

            name=definition.name,

            description=definition.description,

            business_purpose=(
                definition.business_purpose
            ),

            product_type=resolve_product_type(
                definition.id,
                definition.product_type,
            ),

            source_dataset=(
                "uploaded_dataset"
            ),

            status=product_status,

            coverage=coverage,

            version=version,

            definition_id=definition.id,

            dataset_identity=dataset_identity,

            previous_product_id=(
                previous_product_id
            ),

            analyses=analyses,

            metrics=metrics,

            insights=insights,

            candidate_findings=(
                candidate_findings
            ),

            validated_findings=(
                validated_findings
            ),

            promoted_insights=(
                promoted_insights
            ),

            dashboards=selected_dashboards,

            change_summary=change_summary,

            executive_summary=executive_summary,

            health=health,

            metadata=stamp_metadata_with_ai_cache(
                {
                "analysis_count": len(
                    selected_dashboards
                ),

                "expected_analysis_count": len(
                    analysis_ids
                ),

                "metric_count": len(
                    metrics
                ),

                "insight_count": len(
                    insights
                ),

                "candidate_finding_count": len(
                    candidate_findings
                ),

                "validated_finding_count": len(
                    validated_findings
                ),

                "promoted_insight_count": len(
                    promoted_insights
                ),

                "completed_analysis_ids": [
                    dashboard.get("id")
                    for dashboard
                    in selected_dashboards
                ],

                "persisted": True,

                "dataset_identity": (
                    dataset_identity
                ),

                "definition_id": (
                    definition.id
                ),

                "previous_version": (
                    previous_version
                    if previous_version > 0
                    else None
                ),

                "required_coverage": (
                    required_coverage
                ),

                "can_analyze": can_analyze,

                "field_coverage": coverage,

                "upload_batch_id": (
                    upload_batch_id
                ),

                "data_quality_score": (
                    profile_summary.get(
                        "data_quality_score"
                    )
                ),

                "dataset_rows": (
                    profile_summary.get("rows")
                ),

                "dataset_columns": (
                    profile_summary.get(
                        "columns"
                    )
                ),

                "classification_type": (
                    classification_type
                ),

                "missing_percentage": (
                    metrics_dataset.get(
                        "missing_percentage"
                    )
                ),

                "duplicate_count": (
                    metrics_dataset.get(
                        "duplicates"
                    )
                ),

                "column_names": (
                    current_snapshot.get(
                        "column_names"
                    )
                ),

                "mapped_required_fields": (
                    current_snapshot.get(
                        "mapped_required_fields"
                    )
                ),

                "missing_required_fields": (
                    current_snapshot.get(
                        "missing_required_fields"
                    )
                ),

                "mapped_optional_fields": (
                    current_snapshot.get(
                        "mapped_optional_fields"
                    )
                ),

                "data_quality_snapshot": (
                    current_snapshot
                ),
                },
                insight_ai_cache,
            ),

            created_at=batch_created_at,

            updated_at=batch_created_at,
        )

        serialized = _serialize_product(
            product
        )

        # Persist as a new version. Prior rows
        # remain intact for comparison history.

        persisted = (
            repository_create_data_product(
                serialized
            )
        )

        products.append(
            persisted or serialized
        )

    return products


def get_data_products():

    return (
        repository_get_data_products()
    )


def update_data_product(
    product_id: str,
    product: dict,
):

    return (
        repository_update_data_product(
            product_id,
            product,
        )
    )