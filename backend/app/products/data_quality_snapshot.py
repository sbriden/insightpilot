from __future__ import annotations

from typing import Any


def build_data_quality_snapshot(
    *,
    profile_summary: dict | None,
    metrics_dataset: dict | None,
    columns: list[str],
    required_fields: list[str],
    optional_fields: list[str],
    required_coverage: float,
    overall_coverage: float,
    can_analyze: bool,
) -> dict[str, Any]:

    profile_summary = profile_summary or {}
    metrics_dataset = metrics_dataset or {}

    row_count = int(
        profile_summary.get("rows")
        or metrics_dataset.get("rows")
        or 0
    )

    column_count = int(
        profile_summary.get("columns")
        or metrics_dataset.get("columns")
        or len(columns)
    )

    duplicate_count = int(
        metrics_dataset.get("duplicates")
        or 0
    )

    missing_percentage = float(
        metrics_dataset.get(
            "missing_percentage"
        )
        or 0
    )

    data_quality_score = profile_summary.get(
        "data_quality_score"
    )

    if data_quality_score is not None:
        data_quality_score = float(
            data_quality_score
        )

    duplicate_rate = (
        round(
            (duplicate_count / row_count) * 100,
            2,
        )
        if row_count > 0
        else 0.0
    )

    column_names = sorted(
        {
            str(column).strip()
            for column in columns
            if str(column).strip()
        }
    )

    required = list(required_fields or [])
    optional = list(optional_fields or [])
    column_set = set(column_names)

    mapped_required = [
        field
        for field in required
        if field in column_set
    ]

    missing_required = [
        field
        for field in required
        if field not in column_set
    ]

    mapped_optional = [
        field
        for field in optional
        if field in column_set
    ]

    return {
        "row_count": row_count,

        "column_count": column_count,

        "missing_percentage": (
            missing_percentage
        ),

        "duplicate_count": duplicate_count,

        "duplicate_rate": duplicate_rate,

        "data_quality_score": (
            data_quality_score
        ),

        "required_coverage": float(
            required_coverage
        ),

        "overall_coverage": float(
            overall_coverage
        ),

        "can_analyze": bool(can_analyze),

        "mapped_required_fields": (
            mapped_required
        ),

        "missing_required_fields": (
            missing_required
        ),

        "mapped_optional_fields": (
            mapped_optional
        ),

        "column_names": column_names,
    }


def snapshot_from_product_metadata(
    metadata: dict | None,
) -> dict[str, Any] | None:

    if not isinstance(
        metadata,
        dict,
    ):
        return None

    stored = metadata.get(
        "data_quality_snapshot"
    )

    if isinstance(
        stored,
        dict,
    ):
        return stored

    row_count = metadata.get(
        "dataset_rows"
    )

    if (
        row_count is None
        and metadata.get(
            "dataset_columns"
        )
        is None
    ):
        return None

    duplicates = int(
        metadata.get(
            "duplicate_count"
        )
        or 0
    )

    row_count_int = int(
        row_count or 0
    )

    duplicate_rate = (
        round(
            (duplicates / row_count_int)
            * 100,
            2,
        )
        if row_count_int > 0
        else 0.0
    )

    column_names = metadata.get(
        "column_names"
    )

    if not isinstance(
        column_names,
        list,
    ):
        column_names = []

    return {
        "row_count": row_count_int,

        "column_count": int(
            metadata.get(
                "dataset_columns"
            )
            or len(column_names)
        ),

        "missing_percentage": float(
            metadata.get(
                "missing_percentage"
            )
            or 0
        ),

        "duplicate_count": duplicates,

        "duplicate_rate": duplicate_rate,

        "data_quality_score": (
            float(
                metadata["data_quality_score"]
            )
            if metadata.get(
                "data_quality_score"
            )
            is not None
            else None
        ),

        "required_coverage": float(
            metadata.get(
                "required_coverage"
            )
            or 0
        ),

        "overall_coverage": float(
            metadata.get(
                "field_coverage"
            )
            or metadata.get(
                "coverage"
            )
            or 0
        ),

        "can_analyze": bool(
            metadata.get(
                "can_analyze",
                True,
            )
        ),

        "mapped_required_fields": list(
            metadata.get(
                "mapped_required_fields"
            )
            or []
        ),

        "missing_required_fields": list(
            metadata.get(
                "missing_required_fields"
            )
            or []
        ),

        "mapped_optional_fields": list(
            metadata.get(
                "mapped_optional_fields"
            )
            or []
        ),

        "column_names": column_names,
    }
