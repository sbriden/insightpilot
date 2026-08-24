from datetime import datetime

from .repository import (
    update_data_product as repository_update_data_product,
    create_data_product as repository_create_data_product,
    get_data_product as repository_get_data_product,
    get_data_products as repository_get_data_products,
)

from .models import (
    DataProduct,
    DataProductAnalysis,
    DataProductInsight,
    DataProductMetric,
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

            insights.append(
                DataProductInsight(
                    id=insight_id,

                    title=(
                        insight.get("title")
                        or "Insight"
                    ),

                    message=(
                        insight.get(
                            "message"
                        )
                        or insight.get(
                            "description"
                        )
                        or ""
                    ),

                    severity=(
                        insight.get(
                            "severity"
                        )
                        or "low"
                    ),

                    category=insight.get(
                        "category"
                    ),
                )
            )

    return insights


def _calculate_coverage(
    profile: dict,
) -> float:

    summary = profile.get(
        "summary",
        {},
    )

    score = summary.get(
        "data_quality_score"
    )

    if score is None:
        return 0.0

    try:

        return round(
            float(score),
            1,
        )

    except (
        TypeError,
        ValueError,
    ):

        return 0.0


def _determine_status(
    coverage: float,
) -> str:

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
                "category": insight.category,
            }
            for insight
            in product.insights
        ],

        "metadata": product.metadata,

        "created_at": (
            product.created_at.isoformat()
        ),

        "updated_at": (
            product.updated_at.isoformat()
        ),
    }


def generate_data_products(
    context,
    selected_product_ids: list[str] | None = None,
) -> list[dict]:
    """
    Generate data products for the current analysis.

    If selected_product_ids is provided, only those products
    are generated.

    If selected_product_ids is None, all available products
    are generated. This preserves the existing behavior for
    callers that have not yet been updated to pass selection.
    """

    dashboards = (
        context.analysis_dashboards
        or []
    )

    profile = (
        context.profile
        or {}
    )

    coverage = _calculate_coverage(
        profile
    )

    status = _determine_status(
        coverage
    )

    product_definitions = [
        {
            "id": "customer_intelligence",

            "name": "Customer Intelligence",

            "description": (
                "Understand customer behavior, "
                "concentration, growth, "
                "profitability, and "
                "cross-sell opportunities."
            ),

            "business_purpose": (
                "Help organizations understand "
                "customer value and identify "
                "opportunities to improve "
                "retention, growth, and revenue."
            ),

            "analysis_ids": [
                "customer_concentration",
                "customer_growth",
                "cross_sell",
            ],
        },

        {
            "id": "revenue_intelligence",

            "name": "Revenue Intelligence",

            "description": (
                "Understand revenue trends, "
                "concentration, and unusual "
                "revenue behavior."
            ),

            "business_purpose": (
                "Provide visibility into revenue "
                "performance, concentration, "
                "trends, and anomalies."
            ),

            "analysis_ids": [
                "revenue_trends",
                "customer_concentration",
                "anomaly_detection",
            ],
        },

        {
            "id": "profitability_intelligence",

            "name": "Profitability Intelligence",

            "description": (
                "Identify profitability drivers, "
                "loss-making customers and "
                "products, and improvement "
                "opportunities."
            ),

            "business_purpose": (
                "Help decision makers understand "
                "profitability and identify "
                "actions that can improve margins."
            ),

            "analysis_ids": [
                "profitability",
                "profit_improvement",
            ],
        },
    ]

    
    """
    /*
     * Normalize the selection once so the rest of
     * the function can work with a simple list.
     *
     * None means "no selection supplied yet" and
     * preserves the previous behavior of generating
     * all products.
     */
     """

    normalized_selected_ids = None

    if selected_product_ids is not None:

        normalized_selected_ids = {
            str(product_id)
            for product_id
            in selected_product_ids
            if product_id
        }

    products = []

    for definition in product_definitions:

        """
        /*
         * If product selection was supplied, skip any
         * product that was not selected.
         */
         """

        if (
            normalized_selected_ids is not None
            and definition["id"]
            not in normalized_selected_ids
        ):

            continue

        selected_dashboards = [
            dashboard
            for dashboard in dashboards
            if dashboard.get("id")
            in definition["analysis_ids"]
        ]

        analyses = [
            DataProductAnalysis(
                id=dashboard.get("id"),

                title=_dashboard_title(
                    dashboard
                ),

                description=(
                    _dashboard_description(
                        dashboard
                    )
                ),
            )
            for dashboard
            in selected_dashboards
        ]

        metrics = _extract_metrics(
            selected_dashboards
        )

        insights = _extract_insights(
            selected_dashboards
        )

        product = DataProduct(

            id=definition["id"],

            name=definition["name"],

            description=definition[
                "description"
            ],

            business_purpose=definition[
                "business_purpose"
            ],

            source_dataset=(
                "uploaded_dataset"
            ),

            status=status,

            coverage=coverage,

            analyses=analyses,

            metrics=metrics,

            insights=insights,

            metadata={
                "analysis_count": len(
                    analyses
                ),

                "metric_count": len(
                    metrics
                ),

                "insight_count": len(
                    insights
                ),
            },

            version=1,

            created_at=datetime.utcnow(),

            updated_at=datetime.utcnow(),
        )

        products.append(
            _serialize_product(
                product
            )
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