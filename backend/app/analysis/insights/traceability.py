"""
Dataset traceability for findings and Insights.

Retains the relationship between an Insight and the analyzed
dataset so multi-dataset uploads and cross-analysis comparison
remain possible:

    - dataset identifier / version (when available)
    - analysis timestamp
    - source columns
    - filters applied
    - records excluded
    - analytical method

This is factual lineage — not explanation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


REQUIRED_DATASET_TRACEABILITY_KEYS: frozenset[str] = frozenset(
    {
        "dataset_id",
        "dataset_version",
        "dataset_identity",
        "dataset_label",
        "analyzed_at",
        "source_columns",
        "filters",
        "records_excluded",
        "analytical_method",
    }
)


def _as_iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _normalize_filter_item(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {"expression": text, "label": text}
    if not isinstance(item, dict):
        return None
    return dict(item)


def normalize_records_excluded(value: Any) -> list[dict[str, Any]]:
    """
    Normalize excluded-record acknowledgements.

    Accepts DQ issue dicts, simple count ints, or structured rows.
    """

    if value is None:
        return []

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        count = int(value)
        if count <= 0:
            return []
        return [
            {
                "type": "excluded_records",
                "label": "Excluded records",
                "count": count,
                "description": f"{count} records excluded from analysis",
            }
        ]

    if isinstance(value, dict):
        value = [value]

    if not isinstance(value, list):
        return []

    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        if "type" not in row:
            row["type"] = "excluded_records"
        if "label" not in row or not str(row.get("label") or "").strip():
            row["label"] = "Excluded records"
        rows.append(row)
    return rows


def records_excluded_from_evidence(
    evidence: Any,
) -> list[dict[str, Any]]:
    """Pull excluded-record notes from structured evidence DQ context."""

    if evidence is None:
        return []

    payload = evidence
    if hasattr(evidence, "to_dict"):
        payload = evidence.to_dict()
    if not isinstance(payload, dict):
        return []

    data_quality = payload.get("data_quality") or {}
    if not isinstance(data_quality, dict):
        return []

    issues = data_quality.get("issues") or []
    excluded: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_type = str(issue.get("type") or "").strip().lower()
        if issue_type in {"excluded_records", "excluded", "filtered_out"}:
            excluded.append(dict(issue))
    return normalize_records_excluded(excluded)


def build_analytical_method(
    *,
    analysis_type: str | None = None,
    calculation: dict[str, Any] | None = None,
    steps: list[str] | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the analytical-method block for dataset lineage."""

    base = dict(existing or {})
    resolved_type = (
        str(analysis_type).strip()
        if analysis_type
        else str(base.get("analysis_type") or "").strip()
    ) or None

    resolved_calculation = dict(calculation or {})
    if not resolved_calculation and isinstance(base.get("calculation"), dict):
        resolved_calculation = dict(base.get("calculation") or {})

    resolved_steps = _as_string_list(steps)
    if not resolved_steps:
        resolved_steps = _as_string_list(base.get("steps"))

    if (
        not resolved_type
        and isinstance(resolved_calculation, dict)
        and resolved_calculation.get("analysis_type")
    ):
        resolved_type = str(
            resolved_calculation.get("analysis_type")
        ).strip() or None

    return {
        "analysis_type": resolved_type,
        "calculation": resolved_calculation,
        "steps": resolved_steps,
    }


@dataclass
class DatasetTraceability:
    """
    Relationship between an Insight/finding and the analyzed dataset.
    """

    dataset_id: str | None = None
    dataset_version: str | int | None = None
    dataset_identity: str | None = None
    dataset_label: str | None = None
    analyzed_at: str | None = None
    source_columns: list[str] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)
    records_excluded: list[dict[str, Any]] = field(default_factory=list)
    analytical_method: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "dataset_identity": self.dataset_identity,
            "dataset_label": self.dataset_label,
            "analyzed_at": self.analyzed_at,
            "source_columns": list(self.source_columns),
            "filters": [dict(item) for item in self.filters],
            "records_excluded": [
                dict(item) for item in self.records_excluded
            ],
            "analytical_method": dict(self.analytical_method or {}),
        }

    @property
    def has_dataset_identity(self) -> bool:
        return bool(
            self.dataset_id
            or self.dataset_identity
            or self.dataset_label
            or self.dataset_version is not None
        )


def build_dataset_traceability(
    *,
    dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    dataset_identity: str | None = None,
    dataset_label: str | None = None,
    analyzed_at: Any = None,
    source_columns: list[str] | None = None,
    filters: list[Any] | None = None,
    records_excluded: Any = None,
    analytical_method: dict[str, Any] | None = None,
    analysis_type: str | None = None,
    calculation: dict[str, Any] | None = None,
    methodology_steps: list[str] | None = None,
    existing: DatasetTraceability | dict[str, Any] | None = None,
) -> DatasetTraceability:
    """
    Assemble dataset traceability, filling gaps from ``existing``.
    """

    base: dict[str, Any] = {}
    if isinstance(existing, DatasetTraceability):
        base = existing.to_dict()
    elif isinstance(existing, dict):
        base = dict(existing)

    resolved_id = (
        str(dataset_id).strip()
        if dataset_id
        else str(base.get("dataset_id") or "").strip()
    ) or None

    resolved_version = (
        dataset_version
        if dataset_version is not None
        else base.get("dataset_version")
    )
    if isinstance(resolved_version, str):
        resolved_version = resolved_version.strip() or None

    resolved_identity = (
        str(dataset_identity).strip()
        if dataset_identity
        else str(base.get("dataset_identity") or "").strip()
    ) or None

    resolved_label = (
        str(dataset_label).strip()
        if dataset_label
        else str(base.get("dataset_label") or "").strip()
    ) or None

    resolved_analyzed_at = _as_iso_timestamp(analyzed_at)
    if resolved_analyzed_at is None:
        resolved_analyzed_at = _as_iso_timestamp(base.get("analyzed_at"))

    resolved_columns = _as_string_list(source_columns)
    if not resolved_columns:
        resolved_columns = _as_string_list(base.get("source_columns"))

    resolved_filters: list[dict[str, Any]] = []
    for item in filters or []:
        normalized = _normalize_filter_item(item)
        if normalized is not None:
            resolved_filters.append(normalized)
    if not resolved_filters:
        for item in base.get("filters") or []:
            normalized = _normalize_filter_item(item)
            if normalized is not None:
                resolved_filters.append(normalized)

    resolved_excluded = normalize_records_excluded(records_excluded)
    if not resolved_excluded:
        resolved_excluded = normalize_records_excluded(
            base.get("records_excluded")
        )

    method = build_analytical_method(
        analysis_type=analysis_type,
        calculation=calculation,
        steps=methodology_steps,
        existing=(
            analytical_method
            if isinstance(analytical_method, dict)
            else base.get("analytical_method")
            if isinstance(base.get("analytical_method"), dict)
            else None
        ),
    )

    return DatasetTraceability(
        dataset_id=resolved_id,
        dataset_version=resolved_version,
        dataset_identity=resolved_identity,
        dataset_label=resolved_label,
        analyzed_at=resolved_analyzed_at,
        source_columns=resolved_columns,
        filters=resolved_filters,
        records_excluded=resolved_excluded,
        analytical_method=method,
    )


def serialize_dataset_traceability(
    value: DatasetTraceability | dict[str, Any] | None,
    *,
    dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    dataset_identity: str | None = None,
    dataset_label: str | None = None,
    analyzed_at: Any = None,
    source_columns: list[str] | None = None,
    filters: list[Any] | None = None,
    records_excluded: Any = None,
    analytical_method: dict[str, Any] | None = None,
    analysis_type: str | None = None,
    calculation: dict[str, Any] | None = None,
    methodology_steps: list[str] | None = None,
) -> dict[str, Any]:
    """Normalize any dataset-traceability shape into the canonical dict."""

    return build_dataset_traceability(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        dataset_identity=dataset_identity,
        dataset_label=dataset_label,
        analyzed_at=analyzed_at,
        source_columns=source_columns,
        filters=filters,
        records_excluded=records_excluded,
        analytical_method=analytical_method,
        analysis_type=analysis_type,
        calculation=calculation,
        methodology_steps=methodology_steps,
        existing=value,
    ).to_dict()


def merge_dataset_traceability(
    current: DatasetTraceability | dict[str, Any] | None,
    *,
    dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    dataset_identity: str | None = None,
    dataset_label: str | None = None,
    analyzed_at: Any = None,
    source_columns: list[str] | None = None,
    filters: list[Any] | None = None,
    records_excluded: Any = None,
    analytical_method: dict[str, Any] | None = None,
    analysis_type: str | None = None,
    calculation: dict[str, Any] | None = None,
    methodology_steps: list[str] | None = None,
) -> dict[str, Any]:
    """
    Overlay dataset identity fields onto an existing payload.

    Prefer explicit keyword values; keep existing analytical
    lineage (columns/filters/method) when not overridden.
    """

    return serialize_dataset_traceability(
        current,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        dataset_identity=dataset_identity,
        dataset_label=dataset_label,
        analyzed_at=analyzed_at,
        source_columns=source_columns,
        filters=filters,
        records_excluded=records_excluded,
        analytical_method=analytical_method,
        analysis_type=analysis_type,
        calculation=calculation,
        methodology_steps=methodology_steps,
    )


def stamp_insight_dataset_traceability(
    insight: dict[str, Any] | None,
    *,
    dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    dataset_identity: str | None = None,
    dataset_label: str | None = None,
    analyzed_at: Any = None,
) -> dict[str, Any] | None:
    """
    Stamp dataset identity onto a serialized Insight.

    Preserves analytical lineage already on the insight
    (columns, filters, method, exclusions).
    """

    if not isinstance(insight, dict):
        return insight

    payload = dict(insight)
    traceability = payload.get("traceability")
    if not isinstance(traceability, dict):
        traceability = {}
    else:
        traceability = dict(traceability)

    existing_dataset = traceability.get("dataset")
    evidence = payload.get("evidence")
    excluded = records_excluded_from_evidence(evidence)

    dataset = merge_dataset_traceability(
        existing_dataset if isinstance(existing_dataset, dict) else None,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        dataset_identity=dataset_identity,
        dataset_label=dataset_label,
        analyzed_at=analyzed_at,
        source_columns=list(
            traceability.get("source_columns")
            or payload.get("source_columns")
            or []
        ),
        filters=list(
            traceability.get("filters")
            or payload.get("filters")
            or []
        ),
        records_excluded=(
            excluded
            or (
                existing_dataset.get("records_excluded")
                if isinstance(existing_dataset, dict)
                else None
            )
        ),
        analysis_type=str(
            traceability.get("analysis_type")
            or payload.get("analysis_type")
            or ""
        ) or None,
        calculation=dict(
            traceability.get("calculation")
            or payload.get("calculation")
            or {}
        ),
        methodology_steps=list(
            traceability.get("calculations")
            or payload.get("calculations")
            or []
        ),
    )

    traceability["dataset"] = dataset
    # Keep flat mirrors for consumers that already read them.
    if dataset.get("source_columns") and not traceability.get(
        "source_columns"
    ):
        traceability["source_columns"] = list(dataset["source_columns"])
    if dataset.get("filters") and not traceability.get("filters"):
        traceability["filters"] = list(dataset["filters"])

    payload["traceability"] = traceability

    # Keep evidence source section aligned when present.
    if isinstance(evidence, dict):
        evidence_payload = dict(evidence)
        evidence_payload["source_dataset"] = (
            evidence_payload.get("source_dataset")
            or dataset.get("dataset_label")
        )
        evidence_payload["source_dataset_id"] = (
            evidence_payload.get("source_dataset_id")
            or dataset.get("dataset_id")
            or dataset.get("dataset_identity")
        )
        evidence_payload["dataset_version"] = (
            evidence_payload.get("dataset_version")
            if evidence_payload.get("dataset_version") is not None
            else dataset.get("dataset_version")
        )
        evidence_payload["analyzed_at"] = (
            evidence_payload.get("analyzed_at")
            or dataset.get("analyzed_at")
        )
        evidence_payload["records_excluded"] = list(
            evidence_payload.get("records_excluded")
            or dataset.get("records_excluded")
            or []
        )
        show = evidence_payload.get("show_evidence")
        if isinstance(show, dict):
            show_payload = dict(show)
            source = dict(show_payload.get("source") or {})
            source["dataset"] = (
                source.get("dataset")
                or dataset.get("dataset_label")
            )
            source["dataset_id"] = (
                source.get("dataset_id")
                or dataset.get("dataset_id")
                or dataset.get("dataset_identity")
            )
            if source.get("dataset_version") is None:
                source["dataset_version"] = dataset.get("dataset_version")
            source["analyzed_at"] = (
                source.get("analyzed_at")
                or dataset.get("analyzed_at")
            )
            source["records_excluded"] = list(
                source.get("records_excluded")
                or dataset.get("records_excluded")
                or []
            )
            method = dataset.get("analytical_method") or {}
            if isinstance(method, dict):
                source["analytical_method"] = dict(method)
            show_payload["source"] = source
            evidence_payload["show_evidence"] = show_payload
        payload["evidence"] = evidence_payload

    return payload


def stamp_insights_dataset_traceability(
    insights: list[Any] | None,
    *,
    dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    dataset_identity: str | None = None,
    dataset_label: str | None = None,
    analyzed_at: Any = None,
) -> list[dict[str, Any]]:
    """Stamp a list of serialized Insights with dataset lineage."""

    stamped: list[dict[str, Any]] = []
    for item in insights or []:
        if not isinstance(item, dict):
            continue
        updated = stamp_insight_dataset_traceability(
            item,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            dataset_identity=dataset_identity,
            dataset_label=dataset_label,
            analyzed_at=analyzed_at,
        )
        if isinstance(updated, dict):
            stamped.append(updated)
    return stamped
