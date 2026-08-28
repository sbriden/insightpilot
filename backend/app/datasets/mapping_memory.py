import json

from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.database import engine


def _parse_json(value: Any, default: Any) -> Any:

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    return default


def get_field_mappings(
    dataset_type_id: str,
) -> dict | None:

    query = text(
        """
        SELECT
            dataset_type_id,
            uploaded_columns,
            mappings,
            updated_at
        FROM dataset_field_mappings
        WHERE dataset_type_id = :dataset_type_id
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            query,
            {
                "dataset_type_id": (
                    dataset_type_id
                ),
            },
        )

        row = (
            result
            .mappings()
            .first()
        )

    if row is None:
        return None

    record = dict(row)

    record["uploaded_columns"] = (
        _parse_json(
            record.get("uploaded_columns"),
            [],
        )
    )

    record["mappings"] = (
        _parse_json(
            record.get("mappings"),
            [],
        )
    )

    updated_at = record.get("updated_at")

    if hasattr(updated_at, "isoformat"):
        record["updated_at"] = (
            updated_at.isoformat()
        )

    return record


def save_field_mappings(
    dataset_type_id: str,
    uploaded_columns: list[str],
    mappings: list[dict],
) -> dict:

    now = datetime.utcnow()

    query = text(
        """
        INSERT INTO dataset_field_mappings (
            dataset_type_id,
            uploaded_columns,
            mappings,
            updated_at
        )
        VALUES (
            :dataset_type_id,
            CAST(:uploaded_columns AS JSONB),
            CAST(:mappings AS JSONB),
            :updated_at
        )
        ON CONFLICT (dataset_type_id) DO UPDATE SET
            uploaded_columns =
                EXCLUDED.uploaded_columns,
            mappings =
                EXCLUDED.mappings,
            updated_at =
                EXCLUDED.updated_at
        RETURNING
            dataset_type_id,
            uploaded_columns,
            mappings,
            updated_at
        """
    )

    params = {
        "dataset_type_id": dataset_type_id,

        "uploaded_columns": json.dumps(
            uploaded_columns or []
        ),

        "mappings": json.dumps(
            mappings or []
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

    record = dict(row)

    record["uploaded_columns"] = (
        _parse_json(
            record.get("uploaded_columns"),
            [],
        )
    )

    record["mappings"] = (
        _parse_json(
            record.get("mappings"),
            [],
        )
    )

    updated_at = record.get("updated_at")

    if hasattr(updated_at, "isoformat"):
        record["updated_at"] = (
            updated_at.isoformat()
        )

    return record
