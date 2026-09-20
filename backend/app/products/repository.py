import json

from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.database import engine
from app.analysis.insights.findings import (
    collect_candidate_findings_from_dashboards,
)
from app.analysis.insights.insight import (
    collect_promoted_insights_from_dashboards,
)
from app.analysis.insights.validation import (
    collect_validated_findings_from_dashboards,
)


PRODUCT_COLUMNS = """
    id,
    name,
    description,
    business_purpose,
    product_type,
    source_dataset,
    status,
    coverage,
    version,
    definition_id,
    dataset_identity,
    previous_product_id,
    analyses,
    metrics,
    insights,
    dashboards,
    change_summary,
    executive_summary,
    health,
    metadata,
    created_at,
    updated_at
"""


def _json_dumps(
    value: Any,
    default: Any,
) -> str:

    if value is None:
        value = default

    return json.dumps(
        value,
        default=str,
    )


def _parse_json_field(
    value: Any,
    default: Any,
) -> Any:

    if value is None:
        return default

    if isinstance(
        value,
        (dict, list),
    ):
        return value

    if isinstance(value, str):

        try:

            return json.loads(
                value
            )

        except json.JSONDecodeError:

            return default

    return default


def _serialize_row(
    row: Any,
) -> dict | None:

    if row is None:
        return None

    product = dict(row)

    product["analyses"] = _parse_json_field(
        product.get("analyses"),
        [],
    )

    product["metrics"] = _parse_json_field(
        product.get("metrics"),
        [],
    )

    product["insights"] = _parse_json_field(
        product.get("insights"),
        [],
    )

    product["dashboards"] = _parse_json_field(
        product.get("dashboards"),
        [],
    )

    product["change_summary"] = _parse_json_field(
        product.get("change_summary"),
        None,
    )

    product["executive_summary"] = _parse_json_field(
        product.get("executive_summary"),
        None,
    )

    product["health"] = _parse_json_field(
        product.get("health"),
        None,
    )

    product["metadata"] = _parse_json_field(
        product.get("metadata"),
        {},
    )

    from app.products.catalog import (
        resolve_product_type,
    )

    product["product_type"] = resolve_product_type(
        product.get("definition_id"),
        product.get("product_type"),
    )

    # Additive API field: findings persist inside dashboards
    # JSONB; rebuild the top-level list on read so older rows
    # and schema-without-column stay compatible.
    product["candidate_findings"] = (
        collect_candidate_findings_from_dashboards(
            product.get("dashboards") or [],
            scope_by_dashboard=True,
        )
    )

    product["validated_findings"] = (
        collect_validated_findings_from_dashboards(
            product.get("dashboards") or [],
            scope_by_dashboard=True,
        )
    )

    product["promoted_insights"] = (
        collect_promoted_insights_from_dashboards(
            product.get("dashboards") or [],
            scope_by_dashboard=True,
        )
    )

    from app.analysis.insights.ai_cache import (
        apply_insight_ai_cache_to_product,
        cache_has_usable_overlays,
        get_insight_ai_cache,
    )
    from app.services.ai import (
        generate_insight_explanations_for_selection,
        generate_insight_executive_brief_for_results,
    )

    cache = get_insight_ai_cache(product.get("metadata"))

    # Prefer the per-version AI cache. Never re-call the provider
    # on detail reads when overlays were already generated.
    if cache_has_usable_overlays(cache):
        apply_insight_ai_cache_to_product(
            product,
            generate_if_missing=False,
        )
    else:
        # Legacy rows: deterministic fallback only (no provider).
        try:
            apply_insight_ai_cache_to_product(
                product,
                generate_if_missing=True,
                generator_explanations=(
                    generate_insight_explanations_for_selection
                ),
                generator_brief=(
                    generate_insight_executive_brief_for_results
                ),
            )
        except Exception:
            from app.analysis.insights.initial_results import (
                build_initial_results,
            )

            product["insight_initial_results"] = build_initial_results(
                product["promoted_insights"]
            )
            product["executive_brief"] = None

    for field in (
        "created_at",
        "updated_at",
    ):

        value = product.get(field)

        if hasattr(value, "isoformat"):

            product[field] = (
                value.isoformat()
            )

    return product


def _serialize_row_summary(row: Any) -> dict | None:
    """
    Fast serializer for product list endpoints.

    Skips dashboard rehydration and omits bulky analysis payloads
    so the home page / saved-product lists stay responsive.
    """

    if row is None:
        return None

    product = dict(row)

    product["analyses"] = _parse_json_field(
        product.get("analyses"),
        [],
    )
    product["metrics"] = _parse_json_field(
        product.get("metrics"),
        [],
    )
    product["insights"] = _parse_json_field(
        product.get("insights"),
        [],
    )
    product["change_summary"] = _parse_json_field(
        product.get("change_summary"),
        None,
    )
    product["executive_summary"] = _parse_json_field(
        product.get("executive_summary"),
        None,
    )
    product["health"] = _parse_json_field(
        product.get("health"),
        None,
    )
    product["metadata"] = _parse_json_field(
        product.get("metadata"),
        {},
    )

    metadata = product.get("metadata") or {}
    product["dashboards"] = []
    product["candidate_findings"] = []
    product["validated_findings"] = []
    product["promoted_insights"] = []
    product["insight_initial_results"] = {
        "version": "v1",
        "total_discovered": int(
            metadata.get("promoted_insight_count") or 0
        ),
        "tier_counts": {},
        "tiers": [],
        "recommended_cap": 5,
        "recommended_count": 0,
        "recommended_insight_ids": [],
        "recommended_insights": [],
        "headline": "",
        "summary": "",
        "executive_brief": None,
    }
    product["executive_brief"] = None

    for field in (
        "created_at",
        "updated_at",
    ):
        value = product.get(field)
        if hasattr(value, "isoformat"):
            product[field] = value.isoformat()

    return product


def _product_params(
    product: dict,
    *,
    now: datetime | None = None,
) -> dict:

    timestamp = now or datetime.utcnow()

    change_summary = product.get(
        "change_summary"
    )

    executive_summary = product.get(
        "executive_summary"
    )

    health = product.get("health")

    return {
        "id": product["id"],

        "name": product["name"],

        "description": product.get(
            "description",
            "",
        ),

        "business_purpose": product.get(
            "business_purpose",
            "",
        ),

        "product_type": product.get(
            "product_type",
            "user_created",
        ),

        "source_dataset": product.get(
            "source_dataset",
            "",
        ),

        "status": product.get(
            "status",
            "draft",
        ),

        "coverage": product.get(
            "coverage",
            0,
        ),

        "version": product.get(
            "version",
            1,
        ),

        "definition_id": product.get(
            "definition_id"
        ),

        "dataset_identity": product.get(
            "dataset_identity"
        ),

        "previous_product_id": product.get(
            "previous_product_id"
        ),

        "analyses": _json_dumps(
            product.get("analyses"),
            [],
        ),

        "metrics": _json_dumps(
            product.get("metrics"),
            [],
        ),

        "insights": _json_dumps(
            product.get("insights"),
            [],
        ),

        "dashboards": _json_dumps(
            product.get("dashboards"),
            [],
        ),

        "change_summary": (
            None
            if change_summary is None
            else _json_dumps(
                change_summary,
                None,
            )
        ),

        "executive_summary": (
            None
            if executive_summary is None
            else _json_dumps(
                executive_summary,
                None,
            )
        ),

        "health": (
            None
            if health is None
            else _json_dumps(
                health,
                None,
            )
        ),

        "metadata": _json_dumps(
            product.get("metadata"),
            {},
        ),

        "created_at": timestamp,

        "updated_at": timestamp,
    }


def create_data_product(
    product: dict,
) -> dict:
    """
    Insert a new product version.

    Never overwrites an existing row.
    """

    query = text(
        f"""
        INSERT INTO data_products (
            {PRODUCT_COLUMNS}
        )
        VALUES (
            :id,
            :name,
            :description,
            :business_purpose,
            :product_type,
            :source_dataset,
            :status,
            :coverage,
            :version,
            :definition_id,
            :dataset_identity,
            :previous_product_id,
            CAST(:analyses AS JSONB),
            CAST(:metrics AS JSONB),
            CAST(:insights AS JSONB),
            CAST(:dashboards AS JSONB),
            CAST(:change_summary AS JSONB),
            CAST(:executive_summary AS JSONB),
            CAST(:health AS JSONB),
            CAST(:metadata AS JSONB),
            :created_at,
            :updated_at
        )
        RETURNING
            {PRODUCT_COLUMNS}
        """
    )

    params = _product_params(product)

    with engine.begin() as connection:

        result = connection.execute(
            query,
            params,
        )

        row = (
            result
            .mappings()
            .first()
        )

    return _serialize_row(row)


def upsert_data_product(
    product: dict,
) -> dict:
    """
    Compatibility wrapper.

    Versioning always creates a new row.
    """

    return create_data_product(
        product
    )


def get_latest_by_dataset_identity(
    dataset_identity: str,
) -> dict | None:
    """
    Return the highest-version product for a
    dataset identity lineage.
    """

    if not dataset_identity:
        return None

    query = text(
        f"""
        SELECT
            {PRODUCT_COLUMNS}
        FROM data_products
        WHERE dataset_identity = :dataset_identity
          AND status != 'archived'
        ORDER BY version DESC, created_at DESC
        LIMIT 1
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            query,
            {
                "dataset_identity": (
                    dataset_identity
                ),
            },
        )

        row = (
            result
            .mappings()
            .first()
        )

    return _serialize_row(row)


def get_versions_by_definition_id(
    definition_id: str,
) -> list[dict]:
    """
    Return all non-archived versions for a
    catalog product definition, newest first.
    """

    if not definition_id:
        return []

    query = text(
        f"""
        SELECT
            {PRODUCT_COLUMNS}
        FROM data_products
        WHERE definition_id = :definition_id
          AND status != 'archived'
        ORDER BY version DESC, created_at DESC
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            query,
            {
                "definition_id": (
                    definition_id
                ),
            },
        )

        rows = (
            result
            .mappings()
            .all()
        )

    return [
        _serialize_row_summary(row)
        for row in rows
    ]


def get_data_product(
    product_id: str,
):

    query = text(
        f"""
        SELECT
            {PRODUCT_COLUMNS}
        FROM data_products
        WHERE id = :product_id
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            query,
            {
                "product_id": product_id,
            },
        )

        row = (
            result
            .mappings()
            .first()
        )

    return _serialize_row(row)


def get_data_products():

    query = text(
        f"""
        SELECT
            {PRODUCT_COLUMNS}
        FROM data_products
        WHERE status != 'archived'
        ORDER BY updated_at DESC
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            query
        )

        rows = (
            result
            .mappings()
            .all()
        )

    return [
        _serialize_row_summary(row)
        for row in rows
    ]


def list_data_products():

    return get_data_products()


def archive_data_product(
    product_id: str,
):

    query = text(
        f"""
        UPDATE data_products
        SET
            status = 'archived',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :product_id
        RETURNING
            {PRODUCT_COLUMNS}
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            query,
            {
                "product_id": product_id,
            },
        )

        row = (
            result
            .mappings()
            .first()
        )

    return _serialize_row(row)


def update_data_product(
    product_id: str,
    product: dict,
):

    now = datetime.utcnow()

    query = text(
        f"""
        UPDATE data_products
        SET
            name = :name,
            description = :description,
            business_purpose = :business_purpose,
            product_type = :product_type,
            source_dataset = :source_dataset,
            status = :status,
            coverage = :coverage,
            analyses = CAST(:analyses AS JSONB),
            metrics = CAST(:metrics AS JSONB),
            insights = CAST(:insights AS JSONB),
            dashboards = CAST(:dashboards AS JSONB),
            change_summary = CAST(:change_summary AS JSONB),
            executive_summary = CAST(:executive_summary AS JSONB),
            health = CAST(:health AS JSONB),
            metadata = CAST(:metadata AS JSONB),
            updated_at = :updated_at
        WHERE id = :id
        RETURNING
            {PRODUCT_COLUMNS}
        """
    )

    params = {
        "id": product_id,

        "name": product.get(
            "name",
            "",
        ),

        "description": product.get(
            "description",
            "",
        ),

        "business_purpose": product.get(
            "business_purpose",
            "",
        ),

        "product_type": product.get(
            "product_type",
            "user_created",
        ),

        "source_dataset": product.get(
            "source_dataset",
            "",
        ),

        "status": product.get(
            "status",
            "ready",
        ),

        "coverage": product.get(
            "coverage",
            0,
        ),

        "analyses": _json_dumps(
            product.get("analyses"),
            [],
        ),

        "metrics": _json_dumps(
            product.get("metrics"),
            [],
        ),

        "insights": _json_dumps(
            product.get("insights"),
            [],
        ),

        "dashboards": _json_dumps(
            product.get("dashboards"),
            [],
        ),

        "change_summary": (
            None
            if product.get("change_summary") is None
            else _json_dumps(
                product.get("change_summary"),
                None,
            )
        ),

        "executive_summary": (
            None
            if product.get("executive_summary") is None
            else _json_dumps(
                product.get("executive_summary"),
                None,
            )
        ),

        "health": (
            None
            if product.get("health") is None
            else _json_dumps(
                product.get("health"),
                None,
            )
        ),

        "metadata": _json_dumps(
            product.get("metadata"),
            {},
        ),

        "updated_at": now,
    }

    with engine.begin() as connection:

        result = connection.execute(
            query,
            params,
        )

        row = (
            result
            .mappings()
            .first()
        )

    return _serialize_row(row)
