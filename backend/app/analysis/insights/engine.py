from __future__ import annotations

from typing import Any

from ..models import Insight

from .findings import (
    CandidateFinding,
    build_finding_provenance,
    resolve_confidence,
)
from .evidence import build_structured_evidence
from .importance import resolve_importance
from .materiality import is_material
from .normalize import (
    DEFAULT_RECOMMENDED_ACTIONS,
    normalize_priority,
)


def _resolve_value(projector, facts):
    if projector is None:
        return None

    if callable(projector):
        return projector(facts)

    return projector


class InsightEngine:

    def __init__(self, rules):
        self.rules = rules

    def evaluate(self, facts):
        """Backward-compatible narrative insights only."""

        insights, _findings = self.evaluate_with_findings(
            facts,
            analysis_type="analysis",
        )

        return insights

    def evaluate_with_findings(
        self,
        facts,
        *,
        analysis_type: str,
        source_columns: list[str] | None = None,
        relevant_dimensions: list[str] | None = None,
        default_filters: list | None = None,
        default_calculations: list[str] | None = None,
        default_row_scope: str | None = None,
        dataset_id: str | None = None,
        dataset_version: str | int | None = None,
        dataset_identity: str | None = None,
        dataset_label: str | None = None,
        analyzed_at: Any = None,
        records_excluded: Any = None,
    ) -> tuple[list[Insight], list[CandidateFinding]]:
        """
        Evaluate rules into narrative insights and structured
        candidate findings, skipping trivial statistics.

        Each finding includes provenance (columns, filters,
        dimensions, calculations) and dataset traceability.
        """

        insights: list[Insight] = []
        findings: list[CandidateFinding] = []

        columns = list(source_columns or [])
        default_dimensions = list(
            relevant_dimensions or []
        )

        for rule in self.rules:

            if not rule.condition(facts):
                continue

            priority = normalize_priority(
                rule.severity
            )

            observed_value = None
            baseline_value = None
            magnitude_value = None

            if rule.metric and rule.observed is not None:
                observed_value = _resolve_value(
                    rule.observed,
                    facts,
                )
                baseline_value = _resolve_value(
                    rule.baseline,
                    facts,
                )
                magnitude_value = _resolve_value(
                    rule.magnitude,
                    facts,
                )

                if magnitude_value is not None:
                    try:
                        magnitude_value = float(
                            magnitude_value
                        )
                    except (TypeError, ValueError):
                        magnitude_value = None

            if not is_material(
                observed_value=observed_value,
                baseline=baseline_value,
                magnitude=magnitude_value,
                magnitude_unit=rule.magnitude_unit,
                comparison=rule.comparison,
                metric=rule.metric,
                severity=priority,
                rule_id=rule.id,
                min_abs_magnitude=rule.min_abs_magnitude,
                require_material=rule.require_material,
            ):
                continue

            why_it_matters = rule.message(facts)

            insights.append(
                Insight(
                    severity=priority,
                    priority=priority,
                    title=rule.title,
                    message=why_it_matters,
                    category=rule.category,
                    what_happened=rule.title,
                    why_it_matters=why_it_matters,
                    recommended_action=(
                        rule.recommended_action
                        or DEFAULT_RECOMMENDED_ACTIONS[
                            priority
                        ]
                    ),
                    id=rule.id,
                    rule_id=rule.id,
                )
            )

            if not rule.metric or rule.observed is None:
                continue

            dimensions = _resolve_value(
                rule.dimensions,
                facts,
            )

            if dimensions is None:
                dimensions = default_dimensions

            if not isinstance(dimensions, list):
                dimensions = [str(dimensions)]

            filters = _resolve_value(
                rule.filters,
                facts,
            )

            if filters is None:
                filters = list(default_filters or [])

            if not isinstance(filters, list):
                filters = [filters]

            calculations = _resolve_value(
                rule.calculations,
                facts,
            )

            if calculations is None:
                calculations = list(
                    default_calculations or []
                )

            if not isinstance(calculations, list):
                calculations = [calculations]

            calculation = _resolve_value(
                getattr(rule, "calculation", None),
                facts,
            )
            if calculation is not None and not isinstance(
                calculation,
                dict,
            ):
                calculation = None

            row_scope = _resolve_value(
                rule.row_scope,
                facts,
            )

            if row_scope is None:
                row_scope = default_row_scope

            input_values = _resolve_value(
                rule.input_values,
                facts,
            )

            if not isinstance(input_values, dict):
                input_values = {
                    "observed_value": observed_value,
                    "baseline": baseline_value,
                    "magnitude": magnitude_value,
                }

            evidence_metrics = _resolve_value(
                rule.evidence_metrics,
                facts,
            )

            if evidence_metrics is None:
                evidence_metrics = []

            if not isinstance(evidence_metrics, list):
                evidence_metrics = [evidence_metrics]

            provenance = build_finding_provenance(
                source_columns=columns,
                dimensions=[
                    str(item)
                    for item in dimensions
                    if item is not None
                    and str(item).strip()
                ],
                filters=filters,
                calculations=[
                    str(step)
                    for step in calculations
                    if str(step).strip()
                ],
                calculation=calculation,
                row_scope=(
                    str(row_scope)
                    if row_scope is not None
                    else None
                ),
                input_values=input_values,
                metric=rule.metric,
                observed_value=observed_value,
                baseline=baseline_value,
                comparison=rule.comparison,
                magnitude=magnitude_value,
                magnitude_unit=rule.magnitude_unit,
                analysis_type=analysis_type,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                dataset_identity=dataset_identity,
                dataset_label=dataset_label,
                analyzed_at=analyzed_at,
                records_excluded=records_excluded,
            )

            dataset_meta = provenance.dataset or {}

            findings.append(
                CandidateFinding(
                    id=f"{analysis_type}:{rule.id}",
                    analysis_type=analysis_type,
                    metric=rule.metric,
                    observed_value=observed_value,
                    baseline=baseline_value,
                    comparison=rule.comparison,
                    magnitude=magnitude_value,
                    magnitude_unit=rule.magnitude_unit,
                    evidence=build_structured_evidence(
                        # Evidence = facts only. Rule messages often
                        # mix facts with interpretation (why_it_matters);
                        # never treat that prose as evidence summary.
                        summary=None,
                        metrics=evidence_metrics,
                        input_values=input_values,
                        observed_value=observed_value,
                        baseline=baseline_value,
                        magnitude=magnitude_value,
                        magnitude_unit=rule.magnitude_unit,
                        metric_name=rule.metric,
                        comparison=rule.comparison,
                        relevant_dimensions=list(
                            provenance.dimensions
                        ),
                        filters=list(provenance.filters),
                        source_columns=list(
                            provenance.source_columns
                        ),
                        source_dataset=dataset_meta.get(
                            "dataset_label"
                        ),
                        source_dataset_id=(
                            dataset_meta.get("dataset_id")
                            or dataset_meta.get("dataset_identity")
                        ),
                        dataset_version=dataset_meta.get(
                            "dataset_version"
                        ),
                        analyzed_at=dataset_meta.get(
                            "analyzed_at"
                        ),
                        records_excluded=dataset_meta.get(
                            "records_excluded"
                        ),
                        methodology=list(
                            provenance.calculations
                        ),
                        calculation=dict(
                            provenance.calculation or {}
                        ),
                    ),
                    confidence=resolve_confidence(
                        facts,
                        rule.confidence,
                        source_columns=columns,
                        evidence_metrics=evidence_metrics,
                    ),
                    importance=resolve_importance(
                        explicit=_resolve_value(
                            getattr(rule, "importance", None),
                            facts,
                        ),
                        severity=priority,
                        magnitude=magnitude_value,
                        magnitude_unit=rule.magnitude_unit,
                    ),
                    relevant_dimensions=list(
                        provenance.dimensions
                    ),
                    source_columns=list(
                        provenance.source_columns
                    ),
                    provenance=provenance,
                    filters=list(provenance.filters),
                    calculations=list(
                        provenance.calculations
                    ),
                    calculation=dict(
                        provenance.calculation or {}
                    ),
                    rule_id=rule.id,
                    severity=priority,
                    title=rule.title,
                    insight_eligible=rule.insight_eligible,
                )
            )

        return insights, findings
