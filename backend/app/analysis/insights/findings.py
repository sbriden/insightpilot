"""
Structured candidate findings produced by analytical modules.

Candidate findings are deterministic factual observations —
distinct from Validated Findings, Insights, and from
analytical_candidates (which analyses to run).

Pipeline:

    Raw Data → Candidate Finding → Validated Finding → Insight

Validate with ``validation.validate_finding``. Promote only
insight-eligible validated findings via ``insight.promote_finding``.
Interpretive fields (potential_drivers, recommendation) must not
be treated as facts established by the analysis.

Every finding carries provenance so reviewers can answer:
"Exactly what data produced this finding?"
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .materiality import is_material
from .evidence import (
    StructuredEvidence,
    build_structured_evidence,
    serialize_evidence,
)
from .calculation import (
    CalculationSpec,
    build_calculation_spec,
    infer_calculation_spec,
    serialize_calculation_spec,
)
from .confidence import (
    normalize_confidence,
    resolve_confidence,
)
from .importance import normalize_importance, resolve_importance
from .traceability import (
    DatasetTraceability,
    serialize_dataset_traceability,
)

@dataclass
class FindingProvenance:
    """
    Traceability for a candidate finding.

    Minimum contract: columns, filters, dimensions, calculations.
    ``dataset`` retains the analyzed dataset relationship when known.
    """

    source_columns: list[str] = field(
        default_factory=list
    )
    dimensions: list[str] = field(
        default_factory=list
    )
    filters: list[dict[str, Any]] = field(
        default_factory=list
    )
    calculations: list[str] = field(
        default_factory=list
    )
    # Structured recipe for reproducing the result.
    calculation: dict[str, Any] = field(
        default_factory=dict
    )
    # Optional extras for richer lineage.
    row_scope: str | None = None
    input_values: dict[str, Any] = field(
        default_factory=dict
    )
    # Dataset relationship (id/version/timestamp/exclusions/method).
    dataset: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["dataset"] = serialize_dataset_traceability(
            self.dataset,
            source_columns=self.source_columns,
            filters=self.filters,
            calculation=self.calculation,
            methodology_steps=self.calculations,
        )
        return payload


def normalize_filter(
    item: Any,
) -> dict[str, Any] | None:
    """Normalize a filter descriptor into a structured dict."""

    if item is None:
        return None

    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {
            "expression": text,
            "label": text,
        }

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


def build_default_calculations(
    *,
    metric: str,
    observed_value: Any,
    baseline: Any,
    comparison: str | None,
    magnitude: Any,
    magnitude_unit: str | None,
) -> list[str]:
    """Deterministic calculation summary when rules omit one."""

    steps: list[str] = [
        f"metric `{metric}` observed = {observed_value!r}",
    ]

    if baseline is not None:
        steps.append(
            f"baseline = {baseline!r}"
            + (
                f" ({comparison})"
                if comparison
                else ""
            )
        )
    elif comparison:
        steps.append(
            f"comparison = {comparison}"
        )

    if magnitude is not None:
        unit = (
            f" {magnitude_unit}"
            if magnitude_unit
            else ""
        )
        if comparison == "vs_threshold":
            steps.append(
                "magnitude = observed - baseline "
                f"= {magnitude!r}{unit}"
            )
        elif comparison == "vs_prior_period":
            steps.append(
                "magnitude = period-over-period change "
                f"= {magnitude!r}{unit}"
            )
        elif comparison == "vs_benchmark":
            steps.append(
                "magnitude = observed - benchmark "
                f"= {magnitude!r}{unit}"
            )
        else:
            steps.append(
                f"magnitude = {magnitude!r}{unit}"
            )

    return steps


def build_finding_provenance(
    *,
    source_columns: list[str] | None = None,
    dimensions: list[str] | None = None,
    filters: list[Any] | None = None,
    calculations: list[str] | None = None,
    calculation: CalculationSpec | dict[str, Any] | None = None,
    row_scope: str | None = None,
    input_values: dict[str, Any] | None = None,
    metric: str | None = None,
    observed_value: Any = None,
    baseline: Any = None,
    comparison: str | None = None,
    magnitude: Any = None,
    magnitude_unit: str | None = None,
    analysis_type: str | None = None,
    dataset: DatasetTraceability | dict[str, Any] | None = None,
    dataset_id: str | None = None,
    dataset_version: str | int | None = None,
    dataset_identity: str | None = None,
    dataset_label: str | None = None,
    analyzed_at: Any = None,
    records_excluded: Any = None,
) -> FindingProvenance:
    """Assemble provenance, filling calculation defaults when needed."""

    normalized_filters: list[dict[str, Any]] = []

    for item in filters or []:
        normalized = normalize_filter(item)
        if normalized is not None:
            normalized_filters.append(normalized)

    calc_steps = [
        str(step).strip()
        for step in (calculations or [])
        if str(step).strip()
    ]

    if not calc_steps and metric:
        calc_steps = build_default_calculations(
            metric=metric,
            observed_value=observed_value,
            baseline=baseline,
            comparison=comparison,
            magnitude=magnitude,
            magnitude_unit=magnitude_unit,
        )

    resolved_columns = [
        str(column).strip()
        for column in (source_columns or [])
        if str(column).strip()
    ]
    resolved_dimensions = [
        str(dimension).strip()
        for dimension in (dimensions or [])
        if str(dimension).strip()
    ]

    resolved_calculation = serialize_calculation_spec(
        infer_calculation_spec(
            analysis_type=analysis_type,
            metric=metric,
            dimensions=resolved_dimensions,
            source_columns=resolved_columns,
            filters=normalized_filters,
            existing=calculation,
        )
    )

    resolved_dataset = serialize_dataset_traceability(
        dataset,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        dataset_identity=dataset_identity,
        dataset_label=dataset_label,
        analyzed_at=analyzed_at,
        source_columns=resolved_columns,
        filters=normalized_filters,
        records_excluded=records_excluded,
        analysis_type=analysis_type,
        calculation=resolved_calculation,
        methodology_steps=calc_steps,
    )

    return FindingProvenance(
        source_columns=resolved_columns,
        dimensions=resolved_dimensions,
        filters=normalized_filters,
        calculations=calc_steps,
        calculation=resolved_calculation,
        row_scope=(
            str(row_scope).strip()
            if row_scope
            else None
        ),
        input_values=dict(input_values or {}),
        dataset=resolved_dataset,
    )


@dataclass
class CandidateFinding:
    """
    Structured finding emitted by an analysis.

    Values are deterministic facts. Narrative layers may
    describe these findings but must not invent them.
    """

    id: str
    analysis_type: str
    metric: str
    observed_value: Any
    baseline: Any = None
    comparison: str | None = None
    magnitude: float | None = None
    magnitude_unit: str | None = None
    # Narrative gloss + machine-readable metrics ("why this?").
    evidence: StructuredEvidence | dict[str, Any] | str = field(
        default_factory=lambda: StructuredEvidence()
    )
    # Confidence in the analytical finding (high|medium|low) —
    # evidence strength only; independent of business importance.
    confidence: str = "medium"
    # Business importance (high|medium|low) — how much this matters.
    # Independent of confidence.
    importance: str = "medium"
    relevant_dimensions: list[str] = field(
        default_factory=list
    )
    source_columns: list[str] = field(
        default_factory=list
    )
    # Traceability: columns, filters, dimensions, calculations.
    provenance: FindingProvenance = field(
        default_factory=FindingProvenance
    )
    filters: list[dict[str, Any]] = field(
        default_factory=list
    )
    calculations: list[str] = field(
        default_factory=list
    )
    # Structured recipe retained for reproducibility.
    calculation: dict[str, Any] = field(
        default_factory=dict
    )
    rule_id: str | None = None
    # Legacy severity label; kept in sync with importance.
    severity: str | None = None
    title: str | None = None
    # Optional explicit Insight gate (None → heuristics later).
    insight_eligible: bool | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)

        # Keep nested provenance explicit for API consumers.
        if hasattr(self.provenance, "to_dict"):
            payload["provenance"] = (
                self.provenance.to_dict()
            )

        payload["evidence"] = serialize_evidence(
            self.evidence,
            input_values=(
                self.provenance.input_values
                if isinstance(self.provenance, FindingProvenance)
                else {}
            ),
            observed_value=self.observed_value,
            baseline=self.baseline,
            magnitude=self.magnitude,
            magnitude_unit=self.magnitude_unit,
            metric_name=self.metric,
            comparison=self.comparison,
            relevant_dimensions=self.relevant_dimensions,
            filters=self.filters,
            source_columns=self.source_columns,
            source_dataset=(
                (self.provenance.dataset or {}).get("dataset_label")
                if isinstance(self.provenance, FindingProvenance)
                else None
            ),
            source_dataset_id=(
                (self.provenance.dataset or {}).get("dataset_id")
                or (self.provenance.dataset or {}).get("dataset_identity")
                if isinstance(self.provenance, FindingProvenance)
                else None
            ),
            dataset_version=(
                (self.provenance.dataset or {}).get("dataset_version")
                if isinstance(self.provenance, FindingProvenance)
                else None
            ),
            analyzed_at=(
                (self.provenance.dataset or {}).get("analyzed_at")
                if isinstance(self.provenance, FindingProvenance)
                else None
            ),
            records_excluded=(
                (self.provenance.dataset or {}).get("records_excluded")
                if isinstance(self.provenance, FindingProvenance)
                else None
            ),
            methodology=self.calculations,
            calculation=self.calculation,
        )

        return payload


def make_candidate_finding(
    *,
    analysis_type: str,
    metric: str,
    observed_value: Any,
    evidence: Any = None,
    baseline: Any = None,
    comparison: str | None = None,
    magnitude: float | None = None,
    magnitude_unit: str | None = None,
    confidence: str | float | None = "medium",
    importance: str | None = None,
    relevant_dimensions: list[str] | None = None,
    source_columns: list[str] | None = None,
    filters: list[Any] | None = None,
    calculations: list[str] | None = None,
    calculation: CalculationSpec | dict[str, Any] | None = None,
    row_scope: str | None = None,
    input_values: dict[str, Any] | None = None,
    evidence_metrics: list[Any] | None = None,
    provenance: FindingProvenance | dict | None = None,
    rule_id: str | None = None,
    severity: str | None = None,
    title: str | None = None,
    finding_id: str | None = None,
    require_material: bool = True,
    min_abs_magnitude: float | None = None,
    insight_eligible: bool | None = None,
) -> CandidateFinding | None:
    """
    Factory for modules that do not use InsightRule projectors.

    Returns ``None`` when the observation is trivial.
    """

    if not is_material(
        observed_value=observed_value,
        baseline=baseline,
        magnitude=magnitude,
        magnitude_unit=magnitude_unit,
        comparison=comparison,
        metric=metric,
        severity=severity,
        rule_id=rule_id,
        min_abs_magnitude=min_abs_magnitude,
        require_material=require_material,
    ):
        return None

    resolved_id = finding_id or (
        f"{analysis_type}:{rule_id}"
        if rule_id
        else f"{analysis_type}:{metric}"
    )

    if isinstance(provenance, FindingProvenance):
        resolved_provenance = provenance
        if calculation is not None and not (
            resolved_provenance.calculation or {}
        ).get("measure"):
            resolved_provenance = build_finding_provenance(
                source_columns=resolved_provenance.source_columns,
                dimensions=resolved_provenance.dimensions,
                filters=resolved_provenance.filters,
                calculations=resolved_provenance.calculations,
                calculation=calculation,
                row_scope=resolved_provenance.row_scope,
                input_values=resolved_provenance.input_values,
                metric=metric,
                observed_value=observed_value,
                baseline=baseline,
                comparison=comparison,
                magnitude=magnitude,
                magnitude_unit=magnitude_unit,
                analysis_type=analysis_type,
                dataset=resolved_provenance.dataset,
            )
    elif isinstance(provenance, dict):
        resolved_provenance = build_finding_provenance(
            source_columns=provenance.get(
                "source_columns",
                source_columns,
            ),
            dimensions=provenance.get(
                "dimensions",
                relevant_dimensions,
            ),
            filters=provenance.get(
                "filters",
                filters,
            ),
            calculations=provenance.get(
                "calculations",
                calculations,
            ),
            calculation=provenance.get(
                "calculation",
                calculation,
            ),
            row_scope=provenance.get(
                "row_scope",
                row_scope,
            ),
            input_values=provenance.get(
                "input_values",
                input_values,
            ),
            metric=metric,
            observed_value=observed_value,
            baseline=baseline,
            comparison=comparison,
            magnitude=magnitude,
            magnitude_unit=magnitude_unit,
            analysis_type=analysis_type,
            dataset=provenance.get("dataset"),
            dataset_id=provenance.get("dataset_id"),
            dataset_version=provenance.get("dataset_version"),
            dataset_identity=provenance.get("dataset_identity"),
            dataset_label=provenance.get("dataset_label"),
            analyzed_at=provenance.get("analyzed_at"),
            records_excluded=provenance.get("records_excluded"),
        )
    else:
        resolved_provenance = build_finding_provenance(
            source_columns=source_columns,
            dimensions=relevant_dimensions,
            filters=filters,
            calculations=calculations,
            calculation=calculation,
            row_scope=row_scope,
            input_values=input_values,
            metric=metric,
            observed_value=observed_value,
            baseline=baseline,
            comparison=comparison,
            magnitude=magnitude,
            magnitude_unit=magnitude_unit,
            analysis_type=analysis_type,
        )

    return CandidateFinding(
        id=resolved_id,
        analysis_type=analysis_type,
        metric=metric,
        observed_value=observed_value,
        baseline=baseline,
        comparison=comparison,
        magnitude=magnitude,
        magnitude_unit=magnitude_unit,
        evidence=build_structured_evidence(
            summary=(
                evidence
                if isinstance(evidence, str)
                else None
            ),
            metrics=evidence_metrics,
            input_values=(
                input_values
                or (
                    resolved_provenance.input_values
                    if isinstance(
                        resolved_provenance,
                        FindingProvenance,
                    )
                    else None
                )
            ),
            observed_value=observed_value,
            baseline=baseline,
            magnitude=magnitude,
            magnitude_unit=magnitude_unit,
            metric_name=metric,
            comparison=comparison,
            relevant_dimensions=list(
                resolved_provenance.dimensions
            ),
            filters=list(resolved_provenance.filters),
            source_columns=list(
                resolved_provenance.source_columns
            ),
            methodology=list(
                resolved_provenance.calculations
            ),
            calculation=dict(
                resolved_provenance.calculation or {}
            ),
            existing=(
                evidence
                if not isinstance(evidence, str)
                else None
            ),
        ),
        confidence=normalize_confidence(confidence),
        importance=resolve_importance(
            explicit=importance,
            severity=severity,
            magnitude=magnitude,
            magnitude_unit=magnitude_unit,
        ),
        relevant_dimensions=list(
            resolved_provenance.dimensions
        ),
        source_columns=list(
            resolved_provenance.source_columns
        ),
        provenance=resolved_provenance,
        filters=list(resolved_provenance.filters),
        calculations=list(
            resolved_provenance.calculations
        ),
        calculation=dict(
            resolved_provenance.calculation or {}
        ),
        rule_id=rule_id,
        severity=normalize_importance(
            importance if importance is not None else severity
        )
        if (importance is not None or severity is not None)
        else None,
        title=title,
        insight_eligible=insight_eligible,
    )





# Re-export for callers that imported clamp from this module.
_clamp_confidence = normalize_confidence


REQUIRED_FINDING_KEYS = (
    "id",
    "analysis_type",
    "metric",
    "observed_value",
    "baseline",
    "comparison",
    "magnitude",
    "magnitude_unit",
    "evidence",
    "confidence",
    "importance",
    "relevant_dimensions",
    "source_columns",
    "provenance",
    "filters",
    "calculations",
    "calculation",
    "rule_id",
    "severity",
    "title",
    "insight_eligible",
)


def serialize_candidate_finding(
    finding: Any,
) -> dict[str, Any] | None:
    """
    Normalize a finding into a plain JSON-safe dict.

    Accepts CandidateFinding instances or dict payloads so
    AnalysisContext, dashboards, and products share one shape.
    Returns None for empty / invalid input.
    """

    if finding is None:
        return None

    if isinstance(finding, CandidateFinding):
        payload = finding.to_dict()
    elif isinstance(finding, dict):
        payload = dict(finding)
    elif hasattr(finding, "to_dict"):
        payload = finding.to_dict()
    else:
        return None

    if not payload.get("analysis_type") and not payload.get("metric"):
        return None

    provenance = payload.get("provenance")
    if isinstance(provenance, FindingProvenance):
        provenance = provenance.to_dict()
    elif not isinstance(provenance, dict):
        provenance = build_finding_provenance(
            source_columns=payload.get("source_columns"),
            dimensions=payload.get("relevant_dimensions"),
            filters=payload.get("filters"),
            calculations=payload.get("calculations"),
            calculation=payload.get("calculation"),
            metric=payload.get("metric"),
            observed_value=payload.get("observed_value"),
            baseline=payload.get("baseline"),
            comparison=payload.get("comparison"),
            magnitude=payload.get("magnitude"),
            magnitude_unit=payload.get("magnitude_unit"),
            analysis_type=payload.get("analysis_type"),
        ).to_dict()
    else:
        # Ensure nested calculation is always a normalized dict.
        provenance = dict(provenance)
        provenance["calculation"] = serialize_calculation_spec(
            infer_calculation_spec(
                analysis_type=payload.get("analysis_type"),
                metric=payload.get("metric"),
                dimensions=provenance.get("dimensions")
                or payload.get("relevant_dimensions"),
                source_columns=provenance.get("source_columns")
                or payload.get("source_columns"),
                filters=provenance.get("filters")
                or payload.get("filters"),
                existing=provenance.get("calculation")
                or payload.get("calculation"),
            )
        )

    filters = provenance.get("filters") or []
    calculations = provenance.get("calculations") or []
    calculation = dict(
        provenance.get("calculation")
        or payload.get("calculation")
        or {}
    )

    analysis_type = str(
        payload.get("analysis_type") or "unknown"
    )
    metric = str(payload.get("metric") or "unknown")
    rule_id = payload.get("rule_id")
    finding_id = payload.get("id") or (
        f"{analysis_type}:{rule_id}"
        if rule_id
        else f"{analysis_type}:{metric}"
    )

    return {
        "id": str(finding_id),
        "analysis_type": analysis_type,
        "metric": metric,
        "observed_value": payload.get("observed_value"),
        "baseline": payload.get("baseline"),
        "comparison": payload.get("comparison"),
        "magnitude": payload.get("magnitude"),
        "magnitude_unit": payload.get("magnitude_unit"),
        "evidence": serialize_evidence(
            payload.get("evidence"),
            input_values=(
                provenance.get("input_values")
                if isinstance(provenance, dict)
                else None
            ),
            observed_value=payload.get("observed_value"),
            baseline=payload.get("baseline"),
            magnitude=payload.get("magnitude"),
            magnitude_unit=payload.get("magnitude_unit"),
            metric_name=metric,
            comparison=payload.get("comparison"),
            relevant_dimensions=list(
                provenance.get("dimensions")
                or payload.get("relevant_dimensions")
                or []
            ),
            filters=list(
                payload.get("filters")
                or provenance.get("filters")
                or []
            ),
            source_columns=list(
                provenance.get("source_columns")
                or payload.get("source_columns")
                or []
            ),
            methodology=list(
                payload.get("calculations")
                or provenance.get("calculations")
                or []
            ),
            calculation=dict(
                payload.get("calculation")
                or provenance.get("calculation")
                or {}
            ),
        ),
        "confidence": normalize_confidence(
            payload.get("confidence")
        ),
        "importance": resolve_importance(
            explicit=payload.get("importance"),
            severity=payload.get("severity"),
            priority=payload.get("priority"),
            magnitude=payload.get("magnitude"),
            magnitude_unit=payload.get("magnitude_unit"),
        ),
        "relevant_dimensions": list(
            provenance.get("dimensions")
            or payload.get("relevant_dimensions")
            or []
        ),
        "source_columns": list(
            provenance.get("source_columns")
            or payload.get("source_columns")
            or []
        ),
        "provenance": provenance,
        "filters": list(
            payload.get("filters") or filters
        ),
        "calculations": list(
            payload.get("calculations") or calculations
        ),
        "calculation": calculation,
        "rule_id": rule_id,
        "severity": (
            normalize_importance(
                payload.get("importance")
                if payload.get("importance") is not None
                else payload.get("severity")
            )
            if (
                payload.get("importance") is not None
                or payload.get("severity") is not None
            )
            else None
        ),
        "title": payload.get("title"),
        "insight_eligible": payload.get("insight_eligible"),
    }


def collect_candidate_findings_from_dashboards(
    dashboards: list[Any] | None,
    *,
    scope_by_dashboard: bool = False,
) -> list[dict[str, Any]]:
    """
    Aggregate candidate findings from dashboard payloads.

    When ``scope_by_dashboard`` is True, ids are prefixed with the
    dashboard id (product API surface). Context aggregation keeps
    module-native ids.
    """

    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for dashboard in dashboards or []:
        if not isinstance(dashboard, dict):
            continue

        dashboard_id = str(
            dashboard.get("id") or "dashboard"
        )

        raw_findings = (
            dashboard.get("candidate_findings") or []
        )

        for index, raw in enumerate(raw_findings):
            serialized = serialize_candidate_finding(raw)
            if serialized is None:
                continue

            finding_id = serialized["id"]
            if scope_by_dashboard:
                finding_id = f"{dashboard_id}:{finding_id}"
                if finding_id in seen:
                    finding_id = (
                        f"{dashboard_id}:"
                        f"{serialized['id']}:{index}"
                    )
                serialized = {
                    **serialized,
                    "id": finding_id,
                }

            if finding_id in seen:
                continue

            seen.add(finding_id)
            collected.append(serialized)

    return collected
