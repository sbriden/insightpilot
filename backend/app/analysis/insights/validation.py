"""
Finding validation and insight eligibility.

Pipeline (do not collapse stages):

    Raw Data → Candidate Finding → Validated Finding → Insight

- Candidate Finding: deterministic factual observation
- Validated Finding: structurally sound candidate
- Insight: validated finding with enough business importance to surface

Not every validated finding becomes an Insight. Eligibility here is a
binary importance / relevance gate — not a ranking score, and not a
confidence gate. Medium confidence must not erase high-importance
Insights.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .findings import (
    CandidateFinding,
    collect_candidate_findings_from_dashboards,
    serialize_candidate_finding,
)
from .calculation import serialize_calculation_spec
from .confidence import normalize_confidence
from .evidence import serialize_evidence
from .importance import resolve_importance
from .insight import (
    InsightType,
    infer_insight_type,
)


# Soft floor: only reject clearly invalid / empty confidence.
# Low confidence findings may still validate and promote.
_VALID_CONFIDENCE = frozenset({"high", "medium", "low"})

# Analytical shapes that routinely warrant Insight attention even
# when importance is labeled low (risk / opportunity / anomaly signals).
INSIGHT_ELIGIBLE_TYPES: frozenset[str] = frozenset(
    {
        InsightType.CONCENTRATION.value,
        InsightType.ANOMALY.value,
        InsightType.OPPORTUNITY.value,
        InsightType.RISK.value,
    }
)

# Importance labels that indicate business relevance for Insights.
# (Severity remains a legacy alias for importance.)
INSIGHT_ELIGIBLE_IMPORTANCE: frozenset[str] = frozenset(
    {
        "medium",
        "high",
    }
)

# Backward-compatible alias.
INSIGHT_ELIGIBLE_SEVERITIES = INSIGHT_ELIGIBLE_IMPORTANCE


@dataclass
class ValidatedFinding:
    """
    A CandidateFinding that passed structural validation.

    ``insight_eligible`` records whether this finding may be
    promoted to an Insight. It is not a rank or priority score.
    Eligibility is driven by importance / type — not confidence.
    """

    # Identity / fact surface mirrors the candidate finding.
    id: str
    analysis_type: str
    metric: str
    observed_value: Any
    baseline: Any = None
    comparison: str | None = None
    magnitude: float | None = None
    magnitude_unit: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: str = "medium"
    importance: str = "medium"
    relevant_dimensions: list[str] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    filters: list[dict[str, Any]] = field(default_factory=list)
    calculations: list[str] = field(default_factory=list)
    calculation: dict[str, Any] = field(default_factory=dict)
    rule_id: str | None = None
    severity: str | None = None
    title: str | None = None

    # Validation metadata
    stage: str = "validated"
    validation_notes: list[str] = field(default_factory=list)
    insight_eligible: bool = False
    insight_eligibility_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_validated_finding(self)


def validate_finding(
    finding: CandidateFinding | dict[str, Any] | None,
    *,
    min_confidence: str | None = None,
    insight_eligible: bool | None = None,
) -> ValidatedFinding | None:
    """
    Validate a candidate finding.

    Returns ``None`` when the candidate is incomplete. Does not
    decide Insight ranking — only whether the finding is
    structurally valid and optionally insight-eligible.

    Confidence is categorical (high|medium|low) and reflects
    trust in the analytical finding, not business importance.
    By default, low/medium confidence does not block validation
    or Insight eligibility.
    """

    serialized = serialize_candidate_finding(finding)
    if serialized is None:
        return None

    notes: list[str] = []

    metric = str(serialized.get("metric") or "").strip()
    if not metric or metric == "unknown":
        return None

    analysis_type = str(
        serialized.get("analysis_type") or ""
    ).strip()
    if not analysis_type or analysis_type == "unknown":
        return None

    if serialized.get("observed_value") is None:
        notes.append("missing_observed_value")
        return None

    confidence = normalize_confidence(
        serialized.get("confidence")
    )
    if confidence not in _VALID_CONFIDENCE:
        return None

    # Optional floor: e.g. require at least medium.
    # Callers must opt in — confidence is not a default gate.
    if min_confidence is not None:
        order = {"low": 0, "medium": 1, "high": 2}
        floor = normalize_confidence(min_confidence)
        if order.get(confidence, 0) < order.get(floor, 0):
            notes.append(f"confidence_below_{floor}")
            return None

    importance = resolve_importance(
        explicit=serialized.get("importance"),
        severity=serialized.get("severity"),
        priority=serialized.get("priority"),
        insight_type=serialized.get("insight_type"),
        magnitude=serialized.get("magnitude"),
        magnitude_unit=serialized.get("magnitude_unit"),
    )

    evidence_payload = serialize_evidence(
        serialized.get("evidence"),
        input_values=(
            (serialized.get("provenance") or {}).get("input_values")
            if isinstance(serialized.get("provenance"), dict)
            else None
        ),
        observed_value=serialized.get("observed_value"),
        baseline=serialized.get("baseline"),
        magnitude=serialized.get("magnitude"),
        magnitude_unit=serialized.get("magnitude_unit"),
        metric_name=metric,
        comparison=serialized.get("comparison"),
        relevant_dimensions=list(
            serialized.get("relevant_dimensions") or []
        ),
        filters=list(serialized.get("filters") or []),
        source_columns=list(
            serialized.get("source_columns") or []
        ),
        methodology=list(
            serialized.get("calculations") or []
        ),
        calculation=dict(
            serialized.get("calculation")
            or (serialized.get("provenance") or {}).get("calculation")
            or {}
        ),
    )
    if (
        not evidence_payload.get("metrics")
        and not evidence_payload.get("summary")
        and evidence_payload.get("observed_value") is None
    ):
        notes.append("missing_evidence")

    source_columns = list(serialized.get("source_columns") or [])
    if not source_columns:
        notes.append("missing_source_columns")

    # Soft notes do not block validation; hard gates already returned.
    notes.append("structurally_valid")

    eligible, reason = resolve_insight_eligibility(
        {
            **serialized,
            "importance": importance,
            "confidence": confidence,
        },
        explicit=insight_eligible,
    )

    magnitude = serialized.get("magnitude")
    if magnitude is not None:
        try:
            magnitude = float(magnitude)
        except (TypeError, ValueError):
            magnitude = None

    return ValidatedFinding(
        id=str(serialized["id"]),
        analysis_type=analysis_type,
        metric=metric,
        observed_value=serialized.get("observed_value"),
        baseline=serialized.get("baseline"),
        comparison=serialized.get("comparison"),
        magnitude=magnitude,
        magnitude_unit=serialized.get("magnitude_unit"),
        evidence=evidence_payload,
        confidence=confidence,
        importance=importance,
        relevant_dimensions=list(
            serialized.get("relevant_dimensions") or []
        ),
        source_columns=source_columns,
        provenance=dict(serialized.get("provenance") or {}),
        filters=list(serialized.get("filters") or []),
        calculations=list(serialized.get("calculations") or []),
        calculation=serialize_calculation_spec(
            serialized.get("calculation")
            or (serialized.get("provenance") or {}).get("calculation"),
            analysis_type=analysis_type,
            dimension=(
                (serialized.get("relevant_dimensions") or [None])[0]
                if serialized.get("relevant_dimensions")
                else None
            ),
            filters=list(serialized.get("filters") or []),
            source_columns=source_columns,
            parameters={"metric": metric},
        ),
        rule_id=serialized.get("rule_id"),
        severity=serialized.get("severity") or importance,
        title=serialized.get("title"),
        stage="validated",
        validation_notes=notes,
        insight_eligible=eligible,
        insight_eligibility_reason=reason,
    )


def resolve_insight_eligibility(
    finding: dict[str, Any],
    *,
    explicit: bool | None = None,
) -> tuple[bool, str]:
    """
    Binary business-importance gate for Insight promotion.

    Not a ranking system and not a confidence filter: returns
    eligible / not eligible with a short reason. Callers may pass
    ``explicit`` to override.
    """

    if explicit is True:
        return True, "explicit_eligible"

    if explicit is False:
        return False, "explicit_not_eligible"

    if "insight_eligible" in finding and finding["insight_eligible"] is not None:
        flag = bool(finding["insight_eligible"])
        return (
            flag,
            "explicit_eligible"
            if flag
            else "explicit_not_eligible",
        )

    importance = resolve_importance(
        explicit=finding.get("importance"),
        severity=finding.get("severity"),
        priority=finding.get("priority"),
        insight_type=finding.get("insight_type"),
        magnitude=finding.get("magnitude"),
        magnitude_unit=finding.get("magnitude_unit"),
    )
    if importance in INSIGHT_ELIGIBLE_IMPORTANCE:
        return True, f"importance_{importance}"

    insight_type = infer_insight_type(
        analysis_type=finding.get("analysis_type"),
        comparison=finding.get("comparison"),
        rule_id=finding.get("rule_id"),
        explicit=finding.get("insight_type"),
    )
    if insight_type in INSIGHT_ELIGIBLE_TYPES:
        # Type alone must not promote all-clear / descriptive notes
        # (e.g. diversified concentration) that are explicitly low importance.
        if importance == "low" and _is_descriptive_all_clear(finding):
            return False, "descriptive_low_importance"
        return True, f"insight_type_{insight_type}"

    return (
        False,
        "insufficient_business_importance",
    )


def _is_descriptive_all_clear(finding: dict[str, Any]) -> bool:
    """Health-check / diversified findings are interesting, not important."""

    blob = " ".join(
        str(finding.get(key) or "").lower()
        for key in ("rule_id", "title", "metric")
    )
    return any(
        token in blob
        for token in (
            "diversified",
            "low_concentration",
            "stable",
            "broad_adoption",
            "average",
            "mean",
            "per_transaction",
        )
    )


def is_insight_eligible(
    finding: ValidatedFinding | dict[str, Any] | None,
) -> bool:
    """Return whether a validated finding may become an Insight."""

    if finding is None:
        return False

    if isinstance(finding, ValidatedFinding):
        return bool(finding.insight_eligible)

    if isinstance(finding, dict):
        if "insight_eligible" in finding:
            return bool(finding.get("insight_eligible"))
        eligible, _reason = resolve_insight_eligibility(finding)
        return eligible

    return False


REQUIRED_VALIDATED_FINDING_KEYS: frozenset[str] = frozenset(
    {
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
        "stage",
        "validation_notes",
        "insight_eligible",
        "insight_eligibility_reason",
    }
)


def serialize_validated_finding(
    finding: ValidatedFinding | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Normalize a validated finding into a JSON-safe dict."""

    if finding is None:
        return None

    if isinstance(finding, ValidatedFinding):
        payload = asdict(finding)
    elif isinstance(finding, dict):
        # Re-validate dict candidates / validated payloads.
        validated = validate_finding(finding)
        if validated is None:
            return None
        payload = asdict(validated)
    elif hasattr(finding, "to_dict"):
        return serialize_validated_finding(finding.to_dict())
    else:
        return None

    importance = resolve_importance(
        explicit=payload.get("importance"),
        severity=payload.get("severity"),
        priority=payload.get("priority"),
        magnitude=payload.get("magnitude"),
        magnitude_unit=payload.get("magnitude_unit"),
    )

    return {
        "id": str(payload.get("id") or ""),
        "analysis_type": str(payload.get("analysis_type") or ""),
        "metric": str(payload.get("metric") or ""),
        "observed_value": payload.get("observed_value"),
        "baseline": payload.get("baseline"),
        "comparison": payload.get("comparison"),
        "magnitude": payload.get("magnitude"),
        "magnitude_unit": payload.get("magnitude_unit"),
        "evidence": serialize_evidence(
            payload.get("evidence"),
            input_values=(
                (payload.get("provenance") or {}).get("input_values")
                if isinstance(payload.get("provenance"), dict)
                else None
            ),
            observed_value=payload.get("observed_value"),
            baseline=payload.get("baseline"),
            magnitude=payload.get("magnitude"),
            magnitude_unit=payload.get("magnitude_unit"),
            metric_name=payload.get("metric"),
            comparison=payload.get("comparison"),
            relevant_dimensions=list(
                payload.get("relevant_dimensions") or []
            ),
            filters=list(payload.get("filters") or []),
            source_columns=list(
                payload.get("source_columns") or []
            ),
            methodology=list(
                payload.get("calculations") or []
            ),
            calculation=dict(
                payload.get("calculation")
                or (payload.get("provenance") or {}).get("calculation")
                or {}
            ),
        ),
        "confidence": normalize_confidence(
            payload.get("confidence")
        ),
        "importance": importance,
        "relevant_dimensions": list(
            payload.get("relevant_dimensions") or []
        ),
        "source_columns": list(
            payload.get("source_columns") or []
        ),
        "provenance": dict(payload.get("provenance") or {}),
        "filters": list(payload.get("filters") or []),
        "calculations": list(payload.get("calculations") or []),
        "calculation": serialize_calculation_spec(
            payload.get("calculation")
            or (payload.get("provenance") or {}).get("calculation"),
            analysis_type=payload.get("analysis_type"),
            dimension=(
                (payload.get("relevant_dimensions") or [None])[0]
                if payload.get("relevant_dimensions")
                else None
            ),
            filters=list(payload.get("filters") or []),
            source_columns=list(
                payload.get("source_columns") or []
            ),
            parameters={"metric": payload.get("metric")},
        ),
        "rule_id": payload.get("rule_id"),
        "severity": payload.get("severity") or importance,
        "title": payload.get("title"),
        "stage": str(payload.get("stage") or "validated"),
        "validation_notes": list(
            payload.get("validation_notes") or []
        ),
        "insight_eligible": bool(
            payload.get("insight_eligible", False)
        ),
        "insight_eligibility_reason": payload.get(
            "insight_eligibility_reason"
        ),
    }


def validate_findings(
    findings: list[Any] | None,
) -> list[dict[str, Any]]:
    """Validate many candidates; drop those that fail."""

    validated: list[dict[str, Any]] = []
    seen: set[str] = set()

    for finding in findings or []:
        serialized = serialize_validated_finding(
            validate_finding(finding)
        )
        if serialized is None:
            continue

        finding_id = serialized["id"]
        if not finding_id or finding_id in seen:
            continue

        seen.add(finding_id)
        validated.append(serialized)

    return validated


def collect_validated_findings_from_dashboards(
    dashboards: list[Any] | None,
    *,
    scope_by_dashboard: bool = False,
) -> list[dict[str, Any]]:
    """Lift and validate candidate findings from dashboards."""

    candidates = collect_candidate_findings_from_dashboards(
        dashboards,
        scope_by_dashboard=scope_by_dashboard,
    )
    return validate_findings(candidates)


def insight_eligible_findings(
    findings: list[Any] | None,
) -> list[dict[str, Any]]:
    """
    Return validated findings that may be promoted to Insights.

    Filters by business importance / type eligibility only —
    confidence is never the sole filter here.
    """

    eligible: list[dict[str, Any]] = []

    for finding in findings or []:
        if isinstance(finding, ValidatedFinding):
            serialized = serialize_validated_finding(finding)
        elif isinstance(finding, dict) and finding.get("stage") == "validated":
            serialized = serialize_validated_finding(finding)
        else:
            serialized = serialize_validated_finding(
                validate_finding(finding)
            )

        if serialized is None:
            continue

        if not serialized.get("insight_eligible"):
            continue

        eligible.append(serialized)

    return eligible
