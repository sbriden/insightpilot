import json

from datetime import datetime

from sqlalchemy import text

from app.database import engine


def create_data_product(
    product: dict,
) -> dict:

    query = text(
        """
        INSERT INTO data_products (
            id,
            name,
            description,
            business_purpose,
            source_dataset,
            status,
            coverage,
            version,
            analyses,
            metrics,
            insights,
            metadata,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :name,
            :description,
            :business_purpose,
            :source_dataset,
            :status,
            :coverage,
            :version,
            CAST(:analyses AS JSONB),
            CAST(:metrics AS JSONB),
            CAST(:insights AS JSONB),
            CAST(:metadata AS JSONB),
            :created_at,
            :updated_at
        )
        RETURNING *
        """
    )

    now = datetime.utcnow()

    params = {
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

        "analyses": json.dumps(
            product.get(
                "analyses",
                [],
            )
        ),

        "metrics": json.dumps(
            product.get(
                "metrics",
                [],
            )
        ),

        "insights": json.dumps(
            product.get(
                "insights",
                [],
            )
        ),

        "metadata": json.dumps(
            product.get(
                "metadata",
                {},
            )
        ),

        "created_at": now,

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

    if row is None:
        return None

    return dict(row)


def get_data_product(
    product_id: str,
):
    query = text(
        """
        SELECT
            id,
            name,
            description,
            business_purpose,
            source_dataset,
            status,
            coverage,
            version,
            analyses,
            metrics,
            insights,
            metadata,
            created_at,
            updated_at
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

    if row is None:
        return None

    return dict(row)


def get_data_products():
    query = text(
        """
        SELECT
            id,
            name,
            description,
            business_purpose,
            source_dataset,
            status,
            coverage,
            version,
            analyses,
            metrics,
            insights,
            metadata,
            created_at,
            updated_at
        FROM data_products
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
        dict(row)
        for row in rows
    ]


def list_data_products():

    query = text(
        """
        SELECT
            id,
            name,
            description,
            business_purpose,
            source_dataset,
            status,
            coverage,
            version,
            analyses,
            metrics,
            insights,
            metadata,
            created_at,
            updated_at
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
        dict(row)
        for row in rows
    ]


def archive_data_product(
    product_id: str,
):

    query = text(
        """
        UPDATE data_products
        SET
            status = 'archived',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :product_id
        RETURNING *
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

    if row is None:
        return None

    return dict(row)


def update_data_product(
    product_id: str,
    product: dict,
):

    now = datetime.utcnow()

    query = text(
        """
        UPDATE data_products
        SET
            name = :name,
            description = :description,
            business_purpose = :business_purpose,
            source_dataset = :source_dataset,
            status = :status,
            coverage = :coverage,
            version = version + 1,
            analyses = CAST(:analyses AS JSONB),
            metrics = CAST(:metrics AS JSONB),
            insights = CAST(:insights AS JSONB),
            metadata = CAST(:metadata AS JSONB),
            updated_at = :updated_at
        WHERE id = :id
        RETURNING *
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

        "analyses": json.dumps(
            product.get(
                "analyses",
                [],
            )
        ),

        "metrics": json.dumps(
            product.get(
                "metrics",
                [],
            )
        ),

        "insights": json.dumps(
            product.get(
                "insights",
                [],
            )
        ),

        "metadata": json.dumps(
            product.get(
                "metadata",
                {},
            )
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

    if row is None:
        return None

    return dict(row)