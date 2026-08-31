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
    get_product_definition,
    get_product_definitions,
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
                or insight.get("title")
                or f"insight_{index}"
            )

            insight_id = (
                f"{dashboard_id}:{raw_insight_id}"
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

    return {
        "id": product.id,

        "name": product.name,

        "description": product.description,

        "business_purpose": (
            product.business_purpose
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

        selected_dashboards = [
            dashboard
            for dashboard in dashboards
            if dashboard.get("id")
            in analysis_ids
        ]

        dashboard_by_id = {
            dashboard.get("id"): dashboard
            for dashboard
            in selected_dashboards
        }

        analyses = []

        for analysis_id in analysis_ids:

            dashboard = dashboard_by_id.get(
                analysis_id
            )

            if dashboard:

                analyses.append(
                    DataProductAnalysis(
                        id=analysis_id,

                        title=_dashboard_title(
                            dashboard
                        ),

                        description=(
                            _dashboard_description(
                                dashboard
                            )
                            or dashboard.get(
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

                        title=_analysis_title(
                            analysis_id
                        ),

                        description=(
                            "Not available for "
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

            dashboards=selected_dashboards,

            change_summary=change_summary,

            executive_summary=executive_summary,

            health=health,

            metadata={
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