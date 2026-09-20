"""
Machine-readable evidence for findings and Insights.

Architectural boundary (Increment 5 — Evidence, not Explanation):

    Evidence (this module) — DETERMINISTIC FACTS
        e.g. "Revenue was $4.7M across the top 10 customers,
              representing 47% of total revenue."

    Explanation — INTERPRETATION (future / AI-allowed)
        e.g. "This suggests the business may be exposed to
              customer concentration risk."

Evidence answers: "What numbers support this insight?"
Explanation answers: "What might this mean?" — and must not
live inside the evidence payload.

``summary`` is an optional factual gloss over the numbers —
never a substitute for metrics, and never interpretive prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .traceability import (
    _as_iso_timestamp,
    normalize_records_excluded,
)


# Evidence is the deterministic fact layer — not explanation.
EVIDENCE_LAYER: str = "deterministic_fact"
EXPLANATION_LAYER: str = "interpretation"

# Phrases that signal explanation / interpretation, not evidence.
_INTERPRETIVE_SUMMARY_MARKERS: tuple[str, ...] = (
    "suggests",
    "indicating",
    "indicates",
    "may be",
    "might be",
    "could be",
    "appears to",
    "likely",
    "risk",
    "opportunity to",
    "should consider",
    "recommend",
    "because",
    "due to",
    "driven by",
)

# Known fact keys → (display label, unit).
_EVIDENCE_LABELS: dict[str, tuple[str, str | None]] = {
    "top10_share": ("Top 10 customer share", "ratio"),
    "top10_revenue_share": ("Top 10 customer share", "ratio"),
    "top10_revenue": ("Top 10 revenue", "currency"),
    "total_revenue": ("Total revenue", "currency"),
    "total_customers": ("Customer population", "count"),
    "entity_count": ("Population", "count"),
    "population": ("Population", "count"),
    "top_customer_share": ("Top customer share", "ratio"),
    "top_customer_revenue": ("Top customer revenue", "currency"),
    "observed_value": ("Observed value", None),
    "baseline": ("Baseline", None),
    "magnitude": ("Magnitude", None),
    "difference": ("Difference", None),
    "percentage_change": ("Percentage change", "ratio"),
    "threshold": ("Threshold", "ratio"),
    "overall_growth": ("Overall growth", "ratio"),
    "period_change": ("Period change", "ratio"),
}

# Keys that commonly represent population / count in fact bags.
_POPULATION_KEYS: frozenset[str] = frozenset(
    {
        "population",
        "entity_count",
        "total_customers",
        "customer_count",
        "n",
        "sample_size",
        "row_count",
    }
)

# Core observation keys — belong in Summary when no richer aggregates.
_SUMMARY_CORE_KEYS: frozenset[str] = frozenset(
    {
        "observed_value",
        "baseline",
        "difference",
        "percentage_change",
        "population",
        "magnitude",
    }
)

SHOW_EVIDENCE_SECTIONS: tuple[str, ...] = (
    "summary",
    "breakdown",
    "methodology",
    "source",
    "data_quality",
)

# Lightweight data-quality limitation kinds — not a scoring system.
DATA_QUALITY_MISSING = "missing_data"
DATA_QUALITY_DUPLICATES = "duplicate_records"
DATA_QUALITY_EXCLUDED = "excluded_records"
DATA_QUALITY_INVALID = "invalid_values"
DATA_QUALITY_SAMPLE_SIZE = "sample_size"

DATA_QUALITY_ISSUE_TYPES: tuple[str, ...] = (
    DATA_QUALITY_MISSING,
    DATA_QUALITY_DUPLICATES,
    DATA_QUALITY_EXCLUDED,
    DATA_QUALITY_INVALID,
    DATA_QUALITY_SAMPLE_SIZE,
)

_DATA_QUALITY_TYPE_ALIASES: dict[str, str] = {
    "missing": DATA_QUALITY_MISSING,
    "missing_data": DATA_QUALITY_MISSING,
    "missing_values": DATA_QUALITY_MISSING,
    "nulls": DATA_QUALITY_MISSING,
    "null": DATA_QUALITY_MISSING,
    "duplicate": DATA_QUALITY_DUPLICATES,
    "duplicates": DATA_QUALITY_DUPLICATES,
    "duplicate_records": DATA_QUALITY_DUPLICATES,
    "excluded": DATA_QUALITY_EXCLUDED,
    "excluded_records": DATA_QUALITY_EXCLUDED,
    "filtered_out": DATA_QUALITY_EXCLUDED,
    "invalid": DATA_QUALITY_INVALID,
    "invalid_values": DATA_QUALITY_INVALID,
    "invalid_data": DATA_QUALITY_INVALID,
    "sample": DATA_QUALITY_SAMPLE_SIZE,
    "sample_size": DATA_QUALITY_SAMPLE_SIZE,
    "sample_size_limitation": DATA_QUALITY_SAMPLE_SIZE,
    "small_sample": DATA_QUALITY_SAMPLE_SIZE,
}

_DATA_QUALITY_DEFAULT_LABELS: dict[str, str] = {
    DATA_QUALITY_MISSING: "Missing data",
    DATA_QUALITY_DUPLICATES: "Duplicate records",
    DATA_QUALITY_EXCLUDED: "Excluded records",
    DATA_QUALITY_INVALID: "Invalid values",
    DATA_QUALITY_SAMPLE_SIZE: "Sample-size limitation",
}

# Evidence granularity — not every insight needs record-level detail.
EVIDENCE_LEVEL_AGGREGATE = "aggregate"
EVIDENCE_LEVEL_ENTITY = "entity"
EVIDENCE_LEVEL_DISTRIBUTION = "distribution"
EVIDENCE_LEVEL_RECORD = "record"

EVIDENCE_LEVELS: tuple[str, ...] = (
    EVIDENCE_LEVEL_AGGREGATE,
    EVIDENCE_LEVEL_ENTITY,
    EVIDENCE_LEVEL_DISTRIBUTION,
    EVIDENCE_LEVEL_RECORD,
)

# Prefer structured group-level evidence over raw records when both exist.
_LEVEL_INFERENCE_PRIORITY: tuple[str, ...] = (
    EVIDENCE_LEVEL_DISTRIBUTION,
    EVIDENCE_LEVEL_ENTITY,
    EVIDENCE_LEVEL_AGGREGATE,
    EVIDENCE_LEVEL_RECORD,
)


@dataclass
class EvidenceMetric:
    """Single machine-readable supporting fact or aggregate."""

    key: str
    label: str
    value: Any
    unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
        }


@dataclass
class EvidenceBreakdownEntity:
    """
    One group / category / entity in entity-level evidence.

    Minimum useful fields: label + value. ``id`` and ``share``
    are optional when the analysis can supply them.
    """

    label: str
    value: Any = None
    id: str | None = None
    unit: str | None = None
    share: float | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "share": self.share,
        }
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload


@dataclass
class AggregateEvidenceRow:
    """
    Aggregate evidence row — e.g. region current / previous / change.

    Example:
        Northeast | $820K | $1.0M | -18%
    """

    label: str
    current: Any = None
    previous: Any = None
    change: Any = None
    change_pct: float | None = None
    unit: str | None = None
    id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "current": self.current,
            "previous": self.previous,
            "change": self.change,
            "change_pct": self.change_pct,
            "unit": self.unit,
        }
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload


@dataclass
class DistributionEvidenceBucket:
    """
    One bucket in distribution evidence — e.g. overtime by department.
    """

    label: str
    value: Any = None
    share: float | None = None
    unit: str | None = None
    id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "share": self.share,
            "unit": self.unit,
        }
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload


@dataclass
class RecordEvidenceRef:
    """
    Reference to an underlying record supporting an anomaly.

    Prefer identifiers / keys over dumping full rows. Optional
    ``fields`` may hold a sparse snapshot when useful.
    """

    record_id: str | None = None
    keys: dict[str, Any] = field(default_factory=dict)
    label: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "keys": dict(self.keys),
            "label": self.label,
            "fields": dict(self.fields),
        }


@dataclass
class DataQualityIssue:
    """
    One data-quality limitation that may affect reliability.

    Captures missing data, duplicates, exclusions, invalid values,
    or sample-size constraints — without requiring a full DQ score.
    """

    type: str
    label: str
    count: int | float | None = None
    rate: float | None = None
    # Column / attribute affected (named field_name to avoid
    # shadowing dataclasses.field).
    field_name: str | None = None
    description: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "label": self.label,
            "count": self.count,
            "rate": self.rate,
            "field": self.field_name,
            "description": self.description,
        }
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload


@dataclass
class DataQualityContext:
    """
    Data-quality acknowledgements for an insight.

    Not a sophisticated scoring system — just enough structure to
    say e.g. "18% of transactions have missing dates."
    """

    issues: list[DataQualityIssue | dict[str, Any]] = field(
        default_factory=list
    )
    notes: list[str] = field(default_factory=list)
    # Optional explicit flag; inferred from issues when unset.
    affects_reliability: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        issues = [
            item.to_dict()
            if isinstance(item, DataQualityIssue)
            else dict(item)
            for item in self._normalized_issues()
        ]
        affects = self.affects_reliability
        if affects is None:
            affects = bool(issues or self.notes)
        return {
            "issues": issues,
            "notes": list(self.notes),
            "affects_reliability": bool(affects),
            "has_limitations": bool(issues or self.notes),
        }

    def _normalized_issues(self) -> list[DataQualityIssue]:
        result: list[DataQualityIssue] = []
        for item in self.issues or []:
            normalized = _data_quality_issue_from_mapping(item)
            if normalized is not None:
                result.append(normalized)
        return result

    @property
    def has_limitations(self) -> bool:
        return bool(self._normalized_issues() or self.notes)


def normalize_data_quality_type(value: Any) -> str | None:
    if value is None:
        return None
    text = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    if not text:
        return None
    if text in DATA_QUALITY_ISSUE_TYPES:
        return text
    return _DATA_QUALITY_TYPE_ALIASES.get(text)


def _data_quality_issue_from_mapping(
    item: Any,
) -> DataQualityIssue | None:
    if item is None:
        return None
    if isinstance(item, DataQualityIssue):
        return item
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        inferred = normalize_data_quality_type(text)
        return DataQualityIssue(
            type=inferred or "other",
            label=text,
            description=text,
        )
    if not isinstance(item, dict):
        return None

    issue_type = normalize_data_quality_type(
        item.get("type") or item.get("kind") or item.get("category")
    )
    label = str(item.get("label") or "").strip()
    description = item.get("description") or item.get("message")
    if description is not None:
        description = str(description).strip() or None

    if not issue_type and not label and not description:
        return None

    if not issue_type:
        issue_type = "other"
    if not label:
        label = (
            _DATA_QUALITY_DEFAULT_LABELS.get(issue_type)
            or description
            or issue_type.replace("_", " ").capitalize()
        )

    reserved = {
        "type",
        "kind",
        "category",
        "label",
        "count",
        "rate",
        "pct",
        "percentage",
        "field",
        "column",
        "description",
        "message",
        "extras",
    }
    extras = {
        key: value
        for key, value in item.items()
        if key not in reserved and value is not None
    }
    if isinstance(item.get("extras"), dict):
        extras = {**extras, **item["extras"]}

    rate = item.get("rate")
    if rate is None:
        rate = item.get("pct")
    if rate is None:
        rate = item.get("percentage")
    rate_value = _as_float(rate)
    # Allow percentage-style inputs like 18 for 18%.
    if (
        rate_value is not None
        and rate_value > 1
        and rate_value <= 100
        and item.get("rate") is None
    ):
        rate_value = rate_value / 100.0

    count = item.get("count")
    count_value = _as_float(count)
    if count_value is not None and count_value == int(count_value):
        count_value = int(count_value)

    field_name = item.get("field") or item.get("column")
    return DataQualityIssue(
        type=issue_type,
        label=label,
        count=count_value,
        rate=rate_value,
        field_name=str(field_name).strip() if field_name else None,
        description=description,
        extras=extras,
    )


def build_data_quality_context(
    value: DataQualityContext | dict[str, Any] | list[Any] | str | None = None,
    *,
    issues: list[Any] | None = None,
    notes: list[str] | None = None,
    affects_reliability: bool | None = None,
) -> DataQualityContext:
    """Assemble a data-quality context from flexible inputs."""

    resolved_issues: list[Any] = list(issues or [])
    resolved_notes: list[str] = []
    resolved_affects = affects_reliability

    if isinstance(value, DataQualityContext):
        if not resolved_issues:
            resolved_issues = list(value.issues)
        if not notes:
            resolved_notes = list(value.notes)
        if resolved_affects is None:
            resolved_affects = value.affects_reliability
    elif isinstance(value, dict):
        if not resolved_issues:
            resolved_issues = list(value.get("issues") or [])
        if not notes:
            resolved_notes = [
                str(item).strip()
                for item in (value.get("notes") or [])
                if str(item).strip()
            ]
        if resolved_affects is None and "affects_reliability" in value:
            resolved_affects = bool(value.get("affects_reliability"))
    elif isinstance(value, list):
        if not resolved_issues:
            resolved_issues = list(value)
    elif isinstance(value, str) and value.strip():
        resolved_notes.append(value.strip())

    if notes:
        resolved_notes = [
            str(item).strip() for item in notes if str(item).strip()
        ]

    normalized: list[DataQualityIssue] = []
    for item in resolved_issues:
        issue = _data_quality_issue_from_mapping(item)
        if issue is not None:
            normalized.append(issue)

    return DataQualityContext(
        issues=normalized,
        notes=resolved_notes,
        affects_reliability=resolved_affects,
    )


def normalize_evidence_level(value: Any) -> str | None:
    """Normalize a free-text evidence level to a canonical value."""

    if value is None:
        return None
    text = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    if not text:
        return None

    aliases = {
        "aggregates": EVIDENCE_LEVEL_AGGREGATE,
        "aggregated": EVIDENCE_LEVEL_AGGREGATE,
        "summary_table": EVIDENCE_LEVEL_AGGREGATE,
        "entities": EVIDENCE_LEVEL_ENTITY,
        "entity_level": EVIDENCE_LEVEL_ENTITY,
        "contribution": EVIDENCE_LEVEL_ENTITY,
        "distributions": EVIDENCE_LEVEL_DISTRIBUTION,
        "histogram": EVIDENCE_LEVEL_DISTRIBUTION,
        "records": EVIDENCE_LEVEL_RECORD,
        "record_level": EVIDENCE_LEVEL_RECORD,
        "row": EVIDENCE_LEVEL_RECORD,
        "rows": EVIDENCE_LEVEL_RECORD,
        "raw": EVIDENCE_LEVEL_RECORD,
    }
    if text in EVIDENCE_LEVELS:
        return text
    return aliases.get(text)


def infer_evidence_level(
    *,
    explicit: str | None = None,
    aggregate_rows: list[Any] | None = None,
    entities: list[Any] | None = None,
    distribution: list[Any] | None = None,
    records: list[Any] | None = None,
) -> str | None:
    """
    Choose a primary evidence level.

    Explicit wins. Otherwise prefer distribution / entity /
    aggregate over record so analyses are not forced to
    record-level detail.
    """

    normalized = normalize_evidence_level(explicit)
    if normalized:
        return normalized

    present = {
        EVIDENCE_LEVEL_DISTRIBUTION: bool(distribution),
        EVIDENCE_LEVEL_ENTITY: bool(entities),
        EVIDENCE_LEVEL_AGGREGATE: bool(aggregate_rows),
        EVIDENCE_LEVEL_RECORD: bool(records),
    }
    for level in _LEVEL_INFERENCE_PRIORITY:
        if present.get(level):
            return level
    return None


@dataclass
class StructuredEvidence:
    """
    Structured support for a finding or Insight.

    Flat fields retain machine-readable facts. Evidence may be
    carried at different granularities — aggregate, entity,
    distribution, and optionally record-level. Record-level is
    never required; use it only when appropriate (e.g. anomalies).

    ``show_evidence`` organizes content for a future UI:

    - Summary — key numbers
    - Breakdown — level-aware detail (aggregate / entity / …)
    - Methodology — calculation steps + recipe
    - Source — dataset and columns
    """

    metric: str | None = None
    observed_value: Any = None
    baseline: Any = None
    comparison: str | None = None
    difference: float | None = None
    percentage_change: float | None = None
    population: int | float | None = None
    relevant_dimensions: list[str] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    # Dataset identity for the Source section.
    source_dataset: str | None = None
    source_dataset_id: str | None = None
    dataset_version: str | int | None = None
    analyzed_at: str | None = None
    records_excluded: list[dict[str, Any]] = field(default_factory=list)
    methodology: list[str] = field(default_factory=list)
    # Structured calculation recipe (see calculation.py).
    calculation: dict[str, Any] = field(default_factory=dict)
    # Supporting aggregates (machine-readable facts behind the claim).
    metrics: list[EvidenceMetric] = field(default_factory=list)
    # Optional row-level or grouped supporting records (legacy alias).
    supporting_records: list[dict[str, Any]] = field(
        default_factory=list
    )
    # Explicit entity breakdown (alias for entity-level evidence).
    breakdown: list[EvidenceBreakdownEntity | dict[str, Any]] = field(
        default_factory=list
    )
    # Primary evidence granularity for this insight.
    level: str | None = None
    # Aggregate table rows (e.g. region current/previous/change).
    aggregate_rows: list[AggregateEvidenceRow | dict[str, Any]] = field(
        default_factory=list
    )
    # Entity-level contributions (customers, products, …).
    entities: list[EvidenceBreakdownEntity | dict[str, Any]] = field(
        default_factory=list
    )
    # Distribution across a dimension (departments, segments, …).
    distribution: list[
        DistributionEvidenceBucket | dict[str, Any]
    ] = field(default_factory=list)
    # Optional underlying record references — never required.
    records: list[RecordEvidenceRef | dict[str, Any]] = field(
        default_factory=list
    )
    # Data-quality limitations that may affect reliability.
    data_quality: DataQualityContext | dict[str, Any] = field(
        default_factory=DataQualityContext
    )
    summary: str = ""

    def to_show_evidence(self) -> dict[str, Any]:
        """
        UI contract for a "Show evidence" action.

        Always emits all sections so consumers can rely on
        a stable shape even when a section is empty.
        """

        return {
            "summary": self._summary_section(),
            "breakdown": self._breakdown_section(),
            "methodology": self._methodology_section(),
            "source": self._source_section(),
            "data_quality": self._data_quality_section(),
        }

    def _summary_section(self) -> dict[str, Any]:
        key_numbers = self._summary_key_numbers()
        return {
            # Evidence layer only — never explanation / interpretation.
            "layer": EVIDENCE_LAYER,
            "headline": self.summary,
            "metric": self.metric,
            "observed_value": self.observed_value,
            "baseline": self.baseline,
            "comparison": self.comparison,
            "difference": self.difference,
            "percentage_change": self.percentage_change,
            "population": self.population,
            "key_numbers": [
                item.to_dict()
                if isinstance(item, EvidenceMetric)
                else dict(item)
                for item in key_numbers
            ],
        }

    def _summary_key_numbers(self) -> list[EvidenceMetric]:
        """
        Prefer supporting aggregates for Summary key numbers.
        Fall back to core observation metrics when needed.
        """

        preferred: list[EvidenceMetric] = []
        fallback: list[EvidenceMetric] = []

        for item in self.metrics:
            metric = (
                item
                if isinstance(item, EvidenceMetric)
                else _metric_from_mapping(item)
            )
            if metric is None:
                continue
            if metric.key in _SUMMARY_CORE_KEYS or (
                self.metric and metric.key == self.metric
            ):
                fallback.append(metric)
            else:
                preferred.append(metric)

        return preferred or fallback

    def _resolved_entities(self) -> list[EvidenceBreakdownEntity]:
        entities: list[EvidenceBreakdownEntity] = []
        for item in self.entities or []:
            normalized = _breakdown_entity_from_mapping(item)
            if normalized is not None:
                entities.append(normalized)
        if entities:
            return entities

        for item in self.breakdown or []:
            normalized = _breakdown_entity_from_mapping(item)
            if normalized is not None:
                entities.append(normalized)
        if entities:
            return entities

        # Legacy: supporting_records may encode entity rows.
        for item in self.supporting_records or []:
            if _looks_like_aggregate_row(item) or _looks_like_record_ref(
                item
            ):
                continue
            normalized = _breakdown_entity_from_mapping(item)
            if normalized is not None:
                entities.append(normalized)
        return entities

    def _resolved_aggregate_rows(self) -> list[AggregateEvidenceRow]:
        rows: list[AggregateEvidenceRow] = []
        for item in self.aggregate_rows or []:
            normalized = _aggregate_row_from_mapping(item)
            if normalized is not None:
                rows.append(normalized)
        if rows:
            return rows

        for item in self.supporting_records or []:
            if not _looks_like_aggregate_row(item):
                continue
            normalized = _aggregate_row_from_mapping(item)
            if normalized is not None:
                rows.append(normalized)
        return rows

    def _resolved_distribution(
        self,
    ) -> list[DistributionEvidenceBucket]:
        buckets: list[DistributionEvidenceBucket] = []
        for item in self.distribution or []:
            normalized = _distribution_bucket_from_mapping(item)
            if normalized is not None:
                buckets.append(normalized)
        return buckets

    def _resolved_records(self) -> list[RecordEvidenceRef]:
        refs: list[RecordEvidenceRef] = []
        for item in self.records or []:
            normalized = _record_ref_from_mapping(item)
            if normalized is not None:
                refs.append(normalized)
        if refs:
            return refs

        for item in self.supporting_records or []:
            if not _looks_like_record_ref(item):
                continue
            normalized = _record_ref_from_mapping(item)
            if normalized is not None:
                refs.append(normalized)
        return refs

    def levels_present(self) -> list[str]:
        """Return evidence levels that have content (order stable)."""

        present: list[str] = []
        if self._resolved_aggregate_rows():
            present.append(EVIDENCE_LEVEL_AGGREGATE)
        if self._resolved_entities():
            present.append(EVIDENCE_LEVEL_ENTITY)
        if self._resolved_distribution():
            present.append(EVIDENCE_LEVEL_DISTRIBUTION)
        if self._resolved_records():
            present.append(EVIDENCE_LEVEL_RECORD)
        return present

    def resolved_level(self) -> str | None:
        return infer_evidence_level(
            explicit=self.level,
            aggregate_rows=self._resolved_aggregate_rows(),
            entities=self._resolved_entities(),
            distribution=self._resolved_distribution(),
            records=self._resolved_records(),
        )

    def _breakdown_section(self) -> dict[str, Any]:
        entities = self._resolved_entities()
        aggregate_rows = self._resolved_aggregate_rows()
        distribution = self._resolved_distribution()
        records = self._resolved_records()
        dimension = (
            self.relevant_dimensions[0]
            if self.relevant_dimensions
            else None
        )
        level = infer_evidence_level(
            explicit=self.level,
            aggregate_rows=aggregate_rows,
            entities=entities,
            distribution=distribution,
            records=records,
        )
        levels = []
        if aggregate_rows:
            levels.append(EVIDENCE_LEVEL_AGGREGATE)
        if entities:
            levels.append(EVIDENCE_LEVEL_ENTITY)
        if distribution:
            levels.append(EVIDENCE_LEVEL_DISTRIBUTION)
        if records:
            levels.append(EVIDENCE_LEVEL_RECORD)

        return {
            "level": level,
            "levels_present": levels,
            "dimension": dimension,
            "dimensions": list(self.relevant_dimensions),
            # Backward-compatible entity list.
            "entities": [entity.to_dict() for entity in entities],
            "aggregate": {
                "columns": [
                    "label",
                    "current",
                    "previous",
                    "change",
                    "change_pct",
                ],
                "rows": [row.to_dict() for row in aggregate_rows],
            },
            "distribution": {
                "dimension": dimension,
                "buckets": [
                    bucket.to_dict() for bucket in distribution
                ],
            },
            # Only populated when analyses opt into record-level.
            "records": [ref.to_dict() for ref in records],
        }

    def _methodology_section(self) -> dict[str, Any]:
        return {
            "steps": list(self.methodology),
            "calculation": dict(self.calculation or {}),
        }

    def _source_section(self) -> dict[str, Any]:
        return {
            "dataset": self.source_dataset,
            "dataset_id": self.source_dataset_id,
            "dataset_version": self.dataset_version,
            "analyzed_at": self.analyzed_at,
            "columns": list(self.source_columns),
            "filters": [dict(item) for item in self.filters],
            "records_excluded": [
                dict(item) for item in (self.records_excluded or [])
            ],
            "analytical_method": {
                "analysis_type": (
                    (self.calculation or {}).get("analysis_type")
                    if isinstance(self.calculation, dict)
                    else None
                ),
                "calculation": dict(self.calculation or {}),
                "steps": list(self.methodology),
            },
        }

    def _resolved_data_quality(self) -> DataQualityContext:
        return build_data_quality_context(self.data_quality)

    def _data_quality_section(self) -> dict[str, Any]:
        return self._resolved_data_quality().to_dict()

    def to_dict(self) -> dict[str, Any]:
        entities = self._resolved_entities()
        aggregate_rows = self._resolved_aggregate_rows()
        distribution = self._resolved_distribution()
        records = self._resolved_records()
        data_quality = self._resolved_data_quality()
        level = infer_evidence_level(
            explicit=self.level,
            aggregate_rows=aggregate_rows,
            entities=entities,
            distribution=distribution,
            records=records,
        )
        return {
            "metric": self.metric,
            "observed_value": self.observed_value,
            "baseline": self.baseline,
            "comparison": self.comparison,
            "difference": self.difference,
            "percentage_change": self.percentage_change,
            "population": self.population,
            "relevant_dimensions": list(self.relevant_dimensions),
            "filters": [dict(item) for item in self.filters],
            "source_columns": list(self.source_columns),
            "source_dataset": self.source_dataset,
            "source_dataset_id": self.source_dataset_id,
            "dataset_version": self.dataset_version,
            "analyzed_at": self.analyzed_at,
            "records_excluded": [
                dict(item) for item in (self.records_excluded or [])
            ],
            "methodology": list(self.methodology),
            "calculation": dict(self.calculation or {}),
            "metrics": [
                metric.to_dict()
                if isinstance(metric, EvidenceMetric)
                else dict(metric)
                for metric in self.metrics
            ],
            "supporting_records": [
                dict(item) for item in self.supporting_records
            ],
            "breakdown": [entity.to_dict() for entity in entities],
            "level": level,
            "levels_present": self.levels_present(),
            "aggregate_rows": [
                row.to_dict() for row in aggregate_rows
            ],
            "entities": [entity.to_dict() for entity in entities],
            "distribution": [
                bucket.to_dict() for bucket in distribution
            ],
            "records": [ref.to_dict() for ref in records],
            "data_quality": data_quality.to_dict(),
            "summary": self.summary,
            # Stable UI contract for "Show evidence".
            "show_evidence": self.to_show_evidence(),
        }

    @property
    def has_metrics(self) -> bool:
        return len(self.metrics) > 0

    @property
    def has_numeric_support(self) -> bool:
        """True when evidence carries numbers, not only narrative."""

        if self.observed_value is not None:
            return True
        if self.baseline is not None:
            return True
        if self.difference is not None:
            return True
        if self.percentage_change is not None:
            return True
        if self.population is not None:
            return True
        if self.metrics:
            return True
        if (
            self.supporting_records
            or self.breakdown
            or self.aggregate_rows
            or self.entities
            or self.distribution
            or self.records
        ):
            return True
        return False

    @property
    def can_show_evidence(self) -> bool:
        """True when at least one Show-evidence section has content."""

        view = self.to_show_evidence()
        if view["summary"]["key_numbers"] or view["summary"]["headline"]:
            return True
        breakdown = view["breakdown"]
        if (
            breakdown.get("entities")
            or breakdown.get("aggregate", {}).get("rows")
            or breakdown.get("distribution", {}).get("buckets")
            or breakdown.get("records")
        ):
            return True
        if (
            view["methodology"]["steps"]
            or view["methodology"]["calculation"]
        ):
            return True
        if (
            view["source"]["columns"]
            or view["source"]["dataset"]
            or view["source"]["filters"]
        ):
            return True
        if view["data_quality"].get("has_limitations"):
            return True
        return False


def looks_like_explanation(text: str | None) -> bool:
    """
    Heuristic: True when prose reads as interpretation, not fact.

    Used to keep interpretive language out of the evidence layer.
    """

    if not text or not str(text).strip():
        return False
    lowered = str(text).strip().lower()
    return any(marker in lowered for marker in _INTERPRETIVE_SUMMARY_MARKERS)


def sanitize_evidence_summary(text: str | None) -> str:
    """
    Keep only factual evidence summaries.

    Interpretive / explanatory prose is dropped so it cannot
    masquerade as evidence. Explanation belongs elsewhere.
    """

    if text is None:
        return ""
    cleaned = str(text).strip()
    if not cleaned:
        return ""
    if looks_like_explanation(cleaned):
        return ""
    return cleaned


def _format_factual_metric_value(
    value: Any,
    unit: str | None = None,
) -> str:
    number = _as_float(value)
    unit_text = (unit or "").strip().lower()
    if number is None:
        return str(value)

    if unit_text == "ratio":
        return f"{number * 100:.1f}%"
    if unit_text == "currency":
        return f"${number:,.0f}"
    if unit_text == "count":
        if number == int(number):
            return f"{int(number):,}"
        return f"{number:,.3g}"
    if number == int(number) and abs(number) >= 1:
        return f"{int(number):,}"
    return f"{number:,.4g}"


def build_factual_evidence_summary(
    *,
    metrics: list[Any] | None = None,
    observed_value: Any = None,
    baseline: Any = None,
    metric_name: str | None = None,
    magnitude_unit: str | None = None,
    existing_summary: str | None = None,
) -> str:
    """
    Deterministic factual gloss for evidence — never explanation.

    Prefers an existing factual summary. Otherwise synthesizes a
    short statement from supporting metrics / observation fields.
    """

    factual = sanitize_evidence_summary(existing_summary)
    if factual:
        return factual

    parts: list[str] = []
    seen: set[str] = set()

    for item in metrics or []:
        metric = (
            item
            if isinstance(item, EvidenceMetric)
            else _metric_from_mapping(item)
        )
        if metric is None or metric.value is None:
            continue
        if metric.key in seen:
            continue
        if metric.key in {"difference", "percentage_change", "magnitude"}:
            continue
        seen.add(metric.key)
        parts.append(
            f"{metric.label} was "
            f"{_format_factual_metric_value(metric.value, metric.unit)}"
        )
        if len(parts) >= 4:
            break

    if not parts and observed_value is not None:
        label, unit = humanize_evidence_key(
            metric_name or "observed_value"
        )
        parts.append(
            f"{label} was "
            f"{_format_factual_metric_value(
                observed_value,
                unit or magnitude_unit,
            )}"
        )
        if baseline is not None:
            parts.append(
                "baseline was "
                f"{_format_factual_metric_value(
                    baseline,
                    unit or magnitude_unit,
                )}"
            )

    if not parts:
        return ""
    return "; ".join(parts) + "."


def humanize_evidence_key(key: str) -> tuple[str, str | None]:
    """Return (label, unit) for a known or inferred evidence key."""

    normalized = str(key).strip()
    if normalized in _EVIDENCE_LABELS:
        return _EVIDENCE_LABELS[normalized]

    lowered = normalized.lower()
    if lowered in _EVIDENCE_LABELS:
        return _EVIDENCE_LABELS[lowered]

    label = normalized.replace("_", " ").strip().capitalize()
    unit: str | None = None

    if "share" in lowered or "growth" in lowered or "rate" in lowered:
        unit = "ratio"
    elif "revenue" in lowered or "sales" in lowered or "profit" in lowered:
        unit = "currency"
    elif "count" in lowered or "customers" in lowered or "population" in lowered:
        unit = "count"

    return label, unit


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _as_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    result: list[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


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

    field_name = (
        item.get("field")
        or item.get("column")
        or item.get("metric")
    )
    op = item.get("op") or item.get("operator")
    value = item.get("value")
    expression = item.get("expression")
    label = item.get("label")

    if not label:
        if field_name and op is not None:
            label = f"{field_name} {op} {value}"
        elif expression:
            label = str(expression)
        elif field_name is not None:
            label = str(field_name)
        else:
            label = "filter"

    return {
        "field": field_name,
        "op": op,
        "value": value,
        "expression": expression,
        "label": label,
    }


def _normalize_filters(values: Any) -> list[dict[str, Any]]:
    if not values:
        return []
    if isinstance(values, dict):
        values = [values]
    result: list[dict[str, Any]] = []
    for item in values:
        normalized = _normalize_filter_item(item)
        if normalized is not None:
            result.append(normalized)
    return result


def _normalize_records(values: Any) -> list[dict[str, Any]]:
    if not values:
        return []
    if isinstance(values, dict):
        values = [values]
    result: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, dict):
            result.append(dict(item))
    return result


def _breakdown_entity_from_mapping(
    item: Any,
) -> EvidenceBreakdownEntity | None:
    if item is None:
        return None

    if isinstance(item, EvidenceBreakdownEntity):
        return item

    if not isinstance(item, dict):
        return None

    label = (
        item.get("label")
        or item.get("name")
        or item.get("entity")
        or item.get("customer")
        or item.get("product")
        or item.get("group")
        or item.get("category")
    )
    if label is None and item.get("id") is not None:
        label = item.get("id")
    if label is None:
        return None

    reserved = {
        "id",
        "label",
        "name",
        "entity",
        "customer",
        "product",
        "group",
        "category",
        "value",
        "unit",
        "share",
        "contribution",
        "extras",
    }
    extras = {
        key: value
        for key, value in item.items()
        if key not in reserved and value is not None
    }
    if isinstance(item.get("extras"), dict):
        extras = {**extras, **item["extras"]}

    entity_id = item.get("id")
    share = item.get("share")
    if share is None:
        share = item.get("contribution")
    return EvidenceBreakdownEntity(
        id=str(entity_id) if entity_id is not None else None,
        label=str(label),
        value=item.get("value", item.get("revenue", item.get("amount"))),
        unit=(
            str(item["unit"]).strip()
            if item.get("unit")
            else None
        ),
        share=_as_float(share),
        extras=extras,
    )


def _looks_like_aggregate_row(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return any(
        key in item
        for key in (
            "current",
            "previous",
            "change",
            "change_pct",
            "prior",
            "pct_change",
        )
    )


def _looks_like_record_ref(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("record_id") is not None:
        return True
    if isinstance(item.get("keys"), dict) and item.get("keys"):
        return True
    return False


def _aggregate_row_from_mapping(
    item: Any,
) -> AggregateEvidenceRow | None:
    if item is None:
        return None
    if isinstance(item, AggregateEvidenceRow):
        return item
    if not isinstance(item, dict):
        return None

    label = (
        item.get("label")
        or item.get("name")
        or item.get("region")
        or item.get("group")
        or item.get("category")
        or item.get("segment")
    )
    if label is None and item.get("id") is not None:
        label = item.get("id")
    if label is None:
        return None

    reserved = {
        "id",
        "label",
        "name",
        "region",
        "group",
        "category",
        "segment",
        "current",
        "previous",
        "prior",
        "change",
        "change_pct",
        "pct_change",
        "unit",
        "extras",
    }
    extras = {
        key: value
        for key, value in item.items()
        if key not in reserved and value is not None
    }
    if isinstance(item.get("extras"), dict):
        extras = {**extras, **item["extras"]}

    row_id = item.get("id")
    change_pct = item.get("change_pct")
    if change_pct is None:
        change_pct = item.get("pct_change")

    return AggregateEvidenceRow(
        id=str(row_id) if row_id is not None else None,
        label=str(label),
        current=item.get("current"),
        previous=item.get("previous", item.get("prior")),
        change=item.get("change"),
        change_pct=_as_float(change_pct),
        unit=(
            str(item["unit"]).strip()
            if item.get("unit")
            else None
        ),
        extras=extras,
    )


def _distribution_bucket_from_mapping(
    item: Any,
) -> DistributionEvidenceBucket | None:
    if item is None:
        return None
    if isinstance(item, DistributionEvidenceBucket):
        return item
    if not isinstance(item, dict):
        return None

    label = (
        item.get("label")
        or item.get("name")
        or item.get("bucket")
        or item.get("department")
        or item.get("category")
        or item.get("group")
        or item.get("segment")
    )
    if label is None and item.get("id") is not None:
        label = item.get("id")
    if label is None:
        return None

    reserved = {
        "id",
        "label",
        "name",
        "bucket",
        "department",
        "category",
        "group",
        "segment",
        "value",
        "share",
        "unit",
        "extras",
    }
    extras = {
        key: value
        for key, value in item.items()
        if key not in reserved and value is not None
    }
    if isinstance(item.get("extras"), dict):
        extras = {**extras, **item["extras"]}

    bucket_id = item.get("id")
    return DistributionEvidenceBucket(
        id=str(bucket_id) if bucket_id is not None else None,
        label=str(label),
        value=item.get("value", item.get("count", item.get("amount"))),
        share=_as_float(item.get("share")),
        unit=(
            str(item["unit"]).strip()
            if item.get("unit")
            else None
        ),
        extras=extras,
    )


def _record_ref_from_mapping(item: Any) -> RecordEvidenceRef | None:
    if item is None:
        return None
    if isinstance(item, RecordEvidenceRef):
        return item
    if not isinstance(item, dict):
        return None

    record_id = item.get("record_id") or item.get("id")
    keys = item.get("keys")
    if not isinstance(keys, dict):
        keys = {}
    fields = item.get("fields")
    if not isinstance(fields, dict):
        fields = {}

    label = item.get("label") or item.get("name")
    if record_id is None and not keys and not fields and not label:
        return None

    return RecordEvidenceRef(
        record_id=str(record_id) if record_id is not None else None,
        keys=dict(keys),
        label=str(label) if label is not None else None,
        fields=dict(fields),
    )

def infer_difference_and_pct(
    *,
    observed_value: Any = None,
    baseline: Any = None,
    magnitude: Any = None,
    magnitude_unit: str | None = None,
    comparison: str | None = None,
    difference: Any = None,
    percentage_change: Any = None,
) -> tuple[float | None, float | None]:
    """
    Derive difference and percentage_change when not supplied.

    Prefer explicit values. Fall back to magnitude + unit, then
    observed vs baseline arithmetic.
    """

    resolved_difference = _as_float(difference)
    resolved_pct = _as_float(percentage_change)
    mag = _as_float(magnitude)
    unit = (magnitude_unit or "").strip().lower()

    if resolved_difference is None and mag is not None:
        if unit in {"ratio", "percent", "pct", "%"} and comparison in {
            "vs_prior_period",
            "vs_baseline",
            "period_over_period",
        }:
            if resolved_pct is None:
                resolved_pct = mag if unit != "percent" else mag / 100.0
        elif unit not in {"ratio", "percent", "pct", "%"}:
            resolved_difference = mag

    observed = _as_float(observed_value)
    base = _as_float(baseline)

    if (
        resolved_difference is None
        and observed is not None
        and base is not None
    ):
        resolved_difference = observed - base

    if (
        resolved_pct is None
        and observed is not None
        and base is not None
        and base != 0
    ):
        resolved_pct = (observed - base) / abs(base)

    if (
        resolved_pct is None
        and mag is not None
        and unit in {"ratio", "percent", "pct", "%"}
    ):
        resolved_pct = mag if unit != "percent" else mag / 100.0

    return resolved_difference, resolved_pct


def infer_population(
    *,
    population: Any = None,
    input_values: dict[str, Any] | None = None,
    metrics: list[EvidenceMetric] | None = None,
) -> int | float | None:
    """Pick a population/count from explicit value or known keys."""

    explicit = _as_float(population)
    if explicit is not None:
        if explicit == int(explicit):
            return int(explicit)
        return explicit

    for key in _POPULATION_KEYS:
        if input_values and key in input_values:
            value = _as_float(input_values.get(key))
            if value is not None:
                return int(value) if value == int(value) else value

    for metric in metrics or []:
        if metric.key in _POPULATION_KEYS:
            value = _as_float(metric.value)
            if value is not None:
                return int(value) if value == int(value) else value

    return None


def _metric_from_mapping(
    item: Any,
    *,
    fallback_key: str | None = None,
) -> EvidenceMetric | None:
    if item is None:
        return None

    if isinstance(item, EvidenceMetric):
        return item

    if isinstance(item, dict):
        key = str(
            item.get("key")
            or item.get("id")
            or fallback_key
            or ""
        ).strip()
        if not key:
            return None

        label = str(item.get("label") or "").strip()
        unit = item.get("unit")
        if not label:
            label, inferred_unit = humanize_evidence_key(key)
            if unit is None:
                unit = inferred_unit

        if "value" not in item:
            return None

        return EvidenceMetric(
            key=key,
            label=label,
            value=item.get("value"),
            unit=str(unit).strip() if unit else None,
        )

    return None


def build_structured_evidence(
    *,
    summary: str | None = None,
    metrics: list[Any] | None = None,
    input_values: dict[str, Any] | None = None,
    observed_value: Any = None,
    baseline: Any = None,
    magnitude: Any = None,
    magnitude_unit: str | None = None,
    metric_name: str | None = None,
    comparison: str | None = None,
    difference: Any = None,
    percentage_change: Any = None,
    population: Any = None,
    relevant_dimensions: list[str] | None = None,
    filters: list[Any] | None = None,
    source_columns: list[str] | None = None,
    source_dataset: str | None = None,
    source_dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    analyzed_at: Any = None,
    records_excluded: list[Any] | None = None,
    methodology: list[str] | None = None,
    calculation: dict[str, Any] | None = None,
    supporting_records: list[Any] | None = None,
    breakdown: list[Any] | None = None,
    level: str | None = None,
    aggregate_rows: list[Any] | None = None,
    entities: list[Any] | None = None,
    distribution: list[Any] | None = None,
    records: list[Any] | None = None,
    data_quality: (
        DataQualityContext | dict[str, Any] | list[Any] | str | None
    ) = None,
    existing: StructuredEvidence | dict[str, Any] | str | None = None,
) -> StructuredEvidence:
    """
    Assemble structured evidence from explicit fields and known facts.

    Prefer explicit arguments. Fill gaps from ``existing``,
    ``input_values``, and core observation fields so Insights always
    retain the numbers behind the conclusion.

    ``summary`` must be factual. Interpretive prose is stripped;
    a deterministic gloss is built from metrics when needed.
    Explanation / interpretation does not belong here.
    """

    summary_text = str(summary or "").strip()
    collected: list[EvidenceMetric] = []
    seen_keys: set[str] = set()

    resolved_metric = (
        str(metric_name).strip() if metric_name else None
    ) or None
    resolved_observed = observed_value
    resolved_baseline = baseline
    resolved_comparison = (
        str(comparison).strip() if comparison else None
    ) or None
    resolved_dimensions = _as_string_list(relevant_dimensions)
    resolved_filters = _normalize_filters(filters)
    resolved_columns = _as_string_list(source_columns)
    resolved_dataset = (
        str(source_dataset).strip() if source_dataset else None
    ) or None
    resolved_dataset_id = (
        str(source_dataset_id).strip() if source_dataset_id else None
    ) or None
    resolved_dataset_version = dataset_version
    if isinstance(resolved_dataset_version, str):
        resolved_dataset_version = (
            resolved_dataset_version.strip() or None
        )
    resolved_analyzed_at = _as_iso_timestamp(analyzed_at)
    resolved_records_excluded = normalize_records_excluded(
        records_excluded
    )
    resolved_methodology = _as_string_list(methodology)
    resolved_calculation = dict(calculation or {})
    resolved_records_legacy = _normalize_records(supporting_records)
    resolved_breakdown = list(breakdown or [])
    resolved_level = normalize_evidence_level(level)
    resolved_aggregate_rows = list(aggregate_rows or [])
    resolved_entities = list(entities or [])
    resolved_distribution = list(distribution or [])
    resolved_record_refs = list(records or [])
    resolved_data_quality = data_quality
    resolved_difference = difference
    resolved_pct = percentage_change
    resolved_population = population

    def add_metric(metric: EvidenceMetric | None) -> None:
        if metric is None:
            return
        if metric.key in seen_keys:
            return
        if metric.value is None:
            return
        seen_keys.add(metric.key)
        collected.append(metric)

    # Preserve / normalize an existing evidence payload first.
    if isinstance(existing, StructuredEvidence):
        if not summary_text:
            summary_text = existing.summary
        if resolved_metric is None:
            resolved_metric = existing.metric
        if resolved_observed is None:
            resolved_observed = existing.observed_value
        if resolved_baseline is None:
            resolved_baseline = existing.baseline
        if resolved_comparison is None:
            resolved_comparison = existing.comparison
        if resolved_difference is None:
            resolved_difference = existing.difference
        if resolved_pct is None:
            resolved_pct = existing.percentage_change
        if resolved_population is None:
            resolved_population = existing.population
        if not resolved_dimensions:
            resolved_dimensions = list(existing.relevant_dimensions)
        if not resolved_filters:
            resolved_filters = list(existing.filters)
        if not resolved_columns:
            resolved_columns = list(existing.source_columns)
        if resolved_dataset is None:
            resolved_dataset = existing.source_dataset
        if resolved_dataset_id is None:
            resolved_dataset_id = existing.source_dataset_id
        if resolved_dataset_version is None:
            resolved_dataset_version = existing.dataset_version
        if resolved_analyzed_at is None:
            resolved_analyzed_at = existing.analyzed_at
        if not resolved_records_excluded:
            resolved_records_excluded = list(
                existing.records_excluded or []
            )
        if not resolved_methodology:
            resolved_methodology = list(existing.methodology)
        if not resolved_calculation:
            resolved_calculation = dict(existing.calculation or {})
        if not resolved_records_legacy:
            resolved_records_legacy = list(existing.supporting_records)
        if not resolved_breakdown:
            resolved_breakdown = list(existing.breakdown)
        if resolved_level is None:
            resolved_level = normalize_evidence_level(existing.level)
        if not resolved_aggregate_rows:
            resolved_aggregate_rows = list(existing.aggregate_rows)
        if not resolved_entities:
            resolved_entities = list(existing.entities)
        if not resolved_distribution:
            resolved_distribution = list(existing.distribution)
        if not resolved_record_refs:
            resolved_record_refs = list(existing.records)
        if resolved_data_quality is None:
            resolved_data_quality = existing.data_quality
        for item in existing.metrics:
            add_metric(
                item
                if isinstance(item, EvidenceMetric)
                else _metric_from_mapping(item)
            )
    elif isinstance(existing, dict):
        if not summary_text:
            summary_text = str(existing.get("summary") or "").strip()
        if resolved_metric is None and existing.get("metric"):
            resolved_metric = str(existing.get("metric")).strip() or None
        if resolved_observed is None:
            resolved_observed = existing.get("observed_value")
        if resolved_baseline is None:
            resolved_baseline = existing.get("baseline")
        if resolved_comparison is None and existing.get("comparison"):
            resolved_comparison = (
                str(existing.get("comparison")).strip() or None
            )
        if resolved_difference is None:
            resolved_difference = existing.get("difference")
        if resolved_pct is None:
            resolved_pct = existing.get("percentage_change")
        if resolved_population is None:
            resolved_population = existing.get("population")
        if not resolved_dimensions:
            resolved_dimensions = _as_string_list(
                existing.get("relevant_dimensions")
                or existing.get("dimensions")
            )
        if not resolved_filters:
            resolved_filters = _normalize_filters(
                existing.get("filters")
            )
        if not resolved_columns:
            resolved_columns = _as_string_list(
                existing.get("source_columns")
            )
        if resolved_dataset is None and existing.get("source_dataset"):
            resolved_dataset = (
                str(existing.get("source_dataset")).strip() or None
            )
        if (
            resolved_dataset_id is None
            and existing.get("source_dataset_id")
        ):
            resolved_dataset_id = (
                str(existing.get("source_dataset_id")).strip() or None
            )
        if (
            resolved_dataset_version is None
            and existing.get("dataset_version") is not None
        ):
            resolved_dataset_version = existing.get("dataset_version")
        if resolved_analyzed_at is None and existing.get("analyzed_at"):
            resolved_analyzed_at = _as_iso_timestamp(
                existing.get("analyzed_at")
            )
        if not resolved_records_excluded:
            resolved_records_excluded = normalize_records_excluded(
                existing.get("records_excluded")
            )
        if not resolved_methodology:
            resolved_methodology = _as_string_list(
                existing.get("methodology")
                or existing.get("calculations")
            )
        if not resolved_calculation and isinstance(
            existing.get("calculation"),
            dict,
        ):
            resolved_calculation = dict(existing.get("calculation") or {})
        # Prefer nested show_evidence methodology/source when present.
        show = existing.get("show_evidence")
        if isinstance(show, dict):
            methodology_section = show.get("methodology") or {}
            source_section = show.get("source") or {}
            if not resolved_methodology:
                resolved_methodology = _as_string_list(
                    methodology_section.get("steps")
                )
            if not resolved_calculation and isinstance(
                methodology_section.get("calculation"),
                dict,
            ):
                resolved_calculation = dict(
                    methodology_section.get("calculation") or {}
                )
            if resolved_dataset is None and source_section.get("dataset"):
                resolved_dataset = (
                    str(source_section.get("dataset")).strip() or None
                )
            if (
                resolved_dataset_id is None
                and source_section.get("dataset_id")
            ):
                resolved_dataset_id = (
                    str(source_section.get("dataset_id")).strip() or None
                )
            if not resolved_columns:
                resolved_columns = _as_string_list(
                    source_section.get("columns")
                )
            breakdown_section = show.get("breakdown") or {}
            if not resolved_breakdown:
                resolved_breakdown = list(
                    breakdown_section.get("entities") or []
                )
            if not resolved_entities:
                resolved_entities = list(
                    breakdown_section.get("entities") or []
                )
            if not resolved_aggregate_rows:
                aggregate_payload = breakdown_section.get("aggregate") or {}
                resolved_aggregate_rows = list(
                    aggregate_payload.get("rows") or []
                )
            if not resolved_distribution:
                distribution_payload = (
                    breakdown_section.get("distribution") or {}
                )
                resolved_distribution = list(
                    distribution_payload.get("buckets") or []
                )
            if not resolved_record_refs:
                resolved_record_refs = list(
                    breakdown_section.get("records") or []
                )
            if resolved_level is None:
                resolved_level = normalize_evidence_level(
                    breakdown_section.get("level")
                )
        if not resolved_records_legacy:
            resolved_records_legacy = _normalize_records(
                existing.get("supporting_records")
            )
        if not resolved_breakdown:
            resolved_breakdown = list(existing.get("breakdown") or [])
        if resolved_level is None:
            resolved_level = normalize_evidence_level(
                existing.get("level")
            )
        if not resolved_aggregate_rows:
            resolved_aggregate_rows = list(
                existing.get("aggregate_rows") or []
            )
        if not resolved_entities:
            resolved_entities = list(existing.get("entities") or [])
        if not resolved_distribution:
            resolved_distribution = list(
                existing.get("distribution") or []
            )
        if not resolved_record_refs:
            resolved_record_refs = list(existing.get("records") or [])
        if resolved_data_quality is None:
            resolved_data_quality = existing.get("data_quality")
            if resolved_data_quality is None:
                show = existing.get("show_evidence")
                if isinstance(show, dict):
                    resolved_data_quality = show.get("data_quality")
        for item in existing.get("metrics") or []:
            add_metric(_metric_from_mapping(item))
    elif isinstance(existing, str) and existing.strip():
        if not summary_text:
            summary_text = existing.strip()

    for item in metrics or []:
        add_metric(_metric_from_mapping(item))

    # Core observation facts — always useful for "why this insight".
    if resolved_observed is not None:
        label, unit = humanize_evidence_key(
            resolved_metric or "observed_value"
        )
        if resolved_metric:
            add_metric(
                EvidenceMetric(
                    key=str(resolved_metric),
                    label=label,
                    value=resolved_observed,
                    unit=unit or magnitude_unit,
                )
            )
        else:
            add_metric(
                EvidenceMetric(
                    key="observed_value",
                    label="Observed value",
                    value=resolved_observed,
                    unit=magnitude_unit,
                )
            )

    if resolved_baseline is not None:
        label, unit = humanize_evidence_key("baseline")
        add_metric(
            EvidenceMetric(
                key="baseline",
                label=label,
                value=resolved_baseline,
                unit=unit or magnitude_unit,
            )
        )

    if magnitude is not None:
        label, unit = humanize_evidence_key("magnitude")
        add_metric(
            EvidenceMetric(
                key="magnitude",
                label=label,
                value=magnitude,
                unit=unit or magnitude_unit,
            )
        )

    for key, value in (input_values or {}).items():
        if value is None:
            continue
        label, unit = humanize_evidence_key(str(key))
        add_metric(
            EvidenceMetric(
                key=str(key),
                label=label,
                value=value,
                unit=unit,
            )
        )

    derived_diff, derived_pct = infer_difference_and_pct(
        observed_value=resolved_observed,
        baseline=resolved_baseline,
        magnitude=magnitude,
        magnitude_unit=magnitude_unit,
        comparison=resolved_comparison,
        difference=resolved_difference,
        percentage_change=resolved_pct,
    )

    if derived_diff is not None:
        add_metric(
            EvidenceMetric(
                key="difference",
                label="Difference",
                value=derived_diff,
                unit=magnitude_unit
                if (magnitude_unit or "").lower()
                not in {"ratio", "percent", "pct", "%"}
                else None,
            )
        )

    if derived_pct is not None:
        add_metric(
            EvidenceMetric(
                key="percentage_change",
                label="Percentage change",
                value=derived_pct,
                unit="ratio",
            )
        )

    resolved_population = infer_population(
        population=resolved_population,
        input_values=input_values,
        metrics=collected,
    )
    if resolved_population is not None:
        add_metric(
            EvidenceMetric(
                key="population",
                label="Population",
                value=resolved_population,
                unit="count",
            )
        )

    normalized_breakdown: list[EvidenceBreakdownEntity] = []
    for item in resolved_breakdown:
        entity = _breakdown_entity_from_mapping(item)
        if entity is not None:
            normalized_breakdown.append(entity)

    normalized_entities: list[EvidenceBreakdownEntity] = []
    for item in resolved_entities:
        entity = _breakdown_entity_from_mapping(item)
        if entity is not None:
            normalized_entities.append(entity)
    if not normalized_entities:
        normalized_entities = list(normalized_breakdown)

    normalized_aggregate: list[AggregateEvidenceRow] = []
    for item in resolved_aggregate_rows:
        row = _aggregate_row_from_mapping(item)
        if row is not None:
            normalized_aggregate.append(row)

    normalized_distribution: list[DistributionEvidenceBucket] = []
    for item in resolved_distribution:
        bucket = _distribution_bucket_from_mapping(item)
        if bucket is not None:
            normalized_distribution.append(bucket)

    normalized_record_refs: list[RecordEvidenceRef] = []
    for item in resolved_record_refs:
        ref = _record_ref_from_mapping(item)
        if ref is not None:
            normalized_record_refs.append(ref)

    resolved_level = infer_evidence_level(
        explicit=resolved_level,
        aggregate_rows=normalized_aggregate,
        entities=normalized_entities,
        distribution=normalized_distribution,
        records=normalized_record_refs,
    )

    # Evidence summary = facts only. Strip interpretation; synthesize
    # a deterministic gloss from metrics when needed.
    summary_text = build_factual_evidence_summary(
        metrics=collected,
        observed_value=resolved_observed,
        baseline=resolved_baseline,
        metric_name=resolved_metric,
        magnitude_unit=magnitude_unit,
        existing_summary=summary_text,
    )

    return StructuredEvidence(
        metric=resolved_metric,
        observed_value=resolved_observed,
        baseline=resolved_baseline,
        comparison=resolved_comparison,
        difference=derived_diff,
        percentage_change=derived_pct,
        population=resolved_population,
        relevant_dimensions=resolved_dimensions,
        filters=resolved_filters,
        source_columns=resolved_columns,
        source_dataset=resolved_dataset,
        source_dataset_id=resolved_dataset_id,
        dataset_version=resolved_dataset_version,
        analyzed_at=resolved_analyzed_at,
        records_excluded=resolved_records_excluded,
        methodology=resolved_methodology,
        calculation=resolved_calculation,
        metrics=collected,
        supporting_records=resolved_records_legacy,
        breakdown=normalized_breakdown or normalized_entities,
        level=resolved_level,
        aggregate_rows=normalized_aggregate,
        entities=normalized_entities,
        distribution=normalized_distribution,
        records=normalized_record_refs,
        data_quality=build_data_quality_context(resolved_data_quality),
        summary=summary_text,
    )


def serialize_evidence(
    evidence: StructuredEvidence | dict[str, Any] | str | None,
    *,
    input_values: dict[str, Any] | None = None,
    observed_value: Any = None,
    baseline: Any = None,
    magnitude: Any = None,
    magnitude_unit: str | None = None,
    metric_name: str | None = None,
    comparison: str | None = None,
    difference: Any = None,
    percentage_change: Any = None,
    population: Any = None,
    relevant_dimensions: list[str] | None = None,
    filters: list[Any] | None = None,
    source_columns: list[str] | None = None,
    source_dataset: str | None = None,
    source_dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    analyzed_at: Any = None,
    records_excluded: list[Any] | None = None,
    methodology: list[str] | None = None,
    calculation: dict[str, Any] | None = None,
    supporting_records: list[Any] | None = None,
    breakdown: list[Any] | None = None,
    level: str | None = None,
    aggregate_rows: list[Any] | None = None,
    entities: list[Any] | None = None,
    distribution: list[Any] | None = None,
    records: list[Any] | None = None,
    data_quality: (
        DataQualityContext | dict[str, Any] | list[Any] | str | None
    ) = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Normalize any evidence shape into the canonical JSON dict."""

    structured = build_structured_evidence(
        summary=summary,
        input_values=input_values,
        observed_value=observed_value,
        baseline=baseline,
        magnitude=magnitude,
        magnitude_unit=magnitude_unit,
        metric_name=metric_name,
        comparison=comparison,
        difference=difference,
        percentage_change=percentage_change,
        population=population,
        relevant_dimensions=relevant_dimensions,
        filters=filters,
        source_columns=source_columns,
        source_dataset=source_dataset,
        source_dataset_id=source_dataset_id,
        dataset_version=dataset_version,
        analyzed_at=analyzed_at,
        records_excluded=records_excluded,
        methodology=methodology,
        calculation=calculation,
        supporting_records=supporting_records,
        breakdown=breakdown,
        level=level,
        aggregate_rows=aggregate_rows,
        entities=entities,
        distribution=distribution,
        records=records,
        data_quality=data_quality,
        existing=evidence,
    )
    return structured.to_dict()


REQUIRED_EVIDENCE_KEYS: frozenset[str] = frozenset(
    {
        "metric",
        "observed_value",
        "baseline",
        "comparison",
        "difference",
        "percentage_change",
        "population",
        "relevant_dimensions",
        "filters",
        "source_columns",
        "source_dataset",
        "source_dataset_id",
        "dataset_version",
        "analyzed_at",
        "records_excluded",
        "methodology",
        "calculation",
        "metrics",
        "supporting_records",
        "breakdown",
        "level",
        "levels_present",
        "aggregate_rows",
        "entities",
        "distribution",
        "records",
        "data_quality",
        "summary",
        "show_evidence",
    }
)

REQUIRED_SHOW_EVIDENCE_KEYS: frozenset[str] = frozenset(
    SHOW_EVIDENCE_SECTIONS
)

REQUIRED_EVIDENCE_LEVELS: frozenset[str] = frozenset(EVIDENCE_LEVELS)

REQUIRED_DATA_QUALITY_ISSUE_TYPES: frozenset[str] = frozenset(
    DATA_QUALITY_ISSUE_TYPES
)

REQUIRED_EVIDENCE_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "key",
        "label",
        "value",
        "unit",
    }
)
