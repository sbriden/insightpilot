"""
Standardized Insight model for promoted findings.

Pipeline (do not collapse stages):

    Raw Data → Candidate Finding → Validated Finding → Insight

An Insight is the business-facing contract built from a
*validated, insight-eligible* finding plus optional estimated /
interpretive layers. Not every candidate — or even every
validated finding — becomes an Insight.

Field layers (do not conflate):

- FACT_FIELDS — established by deterministic analysis
- ESTIMATED_FIELDS — significance estimates when determinable
- INTERPRETIVE_FIELDS — hypotheses and suggested actions;
  never treat these as analytical facts
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .findings import (
    CandidateFinding,
    serialize_candidate_finding,
)
from .confidence import normalize_confidence
from .calculation import (
    serialize_calculation_spec,
)
from .evidence import (
    StructuredEvidence,
    serialize_evidence,
)
from .importance import resolve_importance
from .scoring import (
    InsightScore,
    score_insight,
    serialize_insight_score,
    sort_insights_by_score,
)
from .redundancy import consolidate_redundant_insights
from .tiers import normalize_tier, resolve_insight_tier
from .traceability import (
    records_excluded_from_evidence,
    serialize_dataset_traceability,
)
from .explanation import serialize_ai_insight


class InsightCategory(str, Enum):
    """Business domain for a promoted insight."""

    REVENUE = "Revenue"
    CUSTOMER = "Customer"
    OPERATIONS = "Operations"
    PROFITABILITY = "Profitability"
    PRODUCT = "Product"
    OTHER = "Other"


class InsightType(str, Enum):
    """
    Analytical shape of an Insight — domain-agnostic.

    Kept intentionally small. Not tied to sales-specific concepts.
    """

    TREND = "trend"
    GROWTH_DECLINE = "growth_decline"
    ANOMALY = "anomaly"
    CONCENTRATION = "concentration"
    COMPARISON = "comparison"
    SEGMENT_DIFFERENCE = "segment_difference"
    CONTRIBUTION = "contribution"
    DISTRIBUTION = "distribution"
    RELATIONSHIP = "relationship"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    OTHER = "other"


# Canonical ordered catalog for APIs / UI (excludes OTHER).
INSIGHT_TYPES: tuple[str, ...] = tuple(
    item.value
    for item in InsightType
    if item is not InsightType.OTHER
)


# Established by deterministic analysis — not speculation.
FACT_FIELDS: frozenset[str] = frozenset(
    {
        "insight_id",
        "title",
        "category",
        "insight_type",
        "finding",
        "metric",
        "observed_value",
        "baseline",
        "magnitude",
        "dimensions",
        "evidence",
        "confidence",
        "importance",
        "tier",
        "source_columns",
        "analysis_type",
        "calculation",
    }
)

# Significance estimates when the analysis can derive them.
ESTIMATED_FIELDS: frozenset[str] = frozenset(
    {
        "business_impact",
    }
)

# AI Insight Contract + optional legacy mirrors — not established facts.
# ``ai_interpretation`` holds summary / why_it_matters /
# potential_drivers / recommended_action / caveats.
# It must never live inside StructuredEvidence or replace ``finding``.
INTERPRETIVE_FIELDS: frozenset[str] = frozenset(
    {
        "ai_interpretation",
        "potential_drivers",
        "recommendation",
        "explanation",  # legacy mirror of ai_interpretation
    }
)

# Ranking metadata — not a fact, estimate, or interpretation.
SCORING_FIELDS: frozenset[str] = frozenset(
    {
        "scoring",
    }
)

REQUIRED_INSIGHT_KEYS: frozenset[str] = (
    FACT_FIELDS
    | ESTIMATED_FIELDS
    | INTERPRETIVE_FIELDS
    | SCORING_FIELDS
)

# Map module / rule category strings → InsightCategory values.
_CATEGORY_ALIASES: dict[str, str] = {
    "revenue": InsightCategory.REVENUE.value,
    "revenue trends": InsightCategory.REVENUE.value,
    "customer": InsightCategory.CUSTOMER.value,
    "customer concentration": InsightCategory.CUSTOMER.value,
    "customer performance": InsightCategory.CUSTOMER.value,
    "customer & product": InsightCategory.CUSTOMER.value,
    "cross-sell": InsightCategory.CUSTOMER.value,
    "cross sell": InsightCategory.CUSTOMER.value,
    "operations": InsightCategory.OPERATIONS.value,
    "profitability": InsightCategory.PROFITABILITY.value,
    "profit improvement": InsightCategory.PROFITABILITY.value,
    "product": InsightCategory.PRODUCT.value,
    "product performance": InsightCategory.PRODUCT.value,
}

# Map analysis_type → InsightCategory when no explicit category.
_ANALYSIS_TYPE_TO_CATEGORY: dict[str, str] = {
    "revenue_trends": InsightCategory.REVENUE.value,
    "customer_concentration": InsightCategory.CUSTOMER.value,
    "customer_performance": InsightCategory.CUSTOMER.value,
    "customer_product": InsightCategory.CUSTOMER.value,
    "cross_sell": InsightCategory.CUSTOMER.value,
    "product_performance": InsightCategory.PRODUCT.value,
    "profitability": InsightCategory.PROFITABILITY.value,
    "profit_improvement": InsightCategory.PROFITABILITY.value,
}

# Map analysis_type / comparison hints → InsightType values.
# Module ids are examples only — types themselves are domain-agnostic.
_ANALYSIS_TYPE_TO_INSIGHT_TYPE: dict[str, str] = {
    "revenue_trends": InsightType.TREND.value,
    "customer_concentration": InsightType.CONCENTRATION.value,
    "customer_performance": InsightType.GROWTH_DECLINE.value,
    "product_performance": InsightType.GROWTH_DECLINE.value,
    "customer_product": InsightType.SEGMENT_DIFFERENCE.value,
    "cross_sell": InsightType.OPPORTUNITY.value,
    "profitability": InsightType.COMPARISON.value,
    "profit_improvement": InsightType.OPPORTUNITY.value,
}

_COMPARISON_TO_INSIGHT_TYPE: dict[str, str] = {
    "vs_prior_period": InsightType.GROWTH_DECLINE.value,
    "vs_threshold": InsightType.COMPARISON.value,
    "vs_benchmark": InsightType.COMPARISON.value,
    "vs_segment": InsightType.SEGMENT_DIFFERENCE.value,
    "absolute": InsightType.ANOMALY.value,
}


@dataclass
class Insight:
    """
    Standardized promoted finding.

    ``ai_interpretation`` is the AI Insight Contract (summary,
    why_it_matters, potential_drivers, recommended_action, caveats).
    It is interpretive and separate from deterministic ``finding``.
    ``potential_drivers`` / ``recommendation`` may mirror the
    contract for older consumers.
    """

    insight_id: str
    title: str
    category: str
    insight_type: str
    finding: str
    metric: str
    observed_value: Any
    baseline: Any = None
    magnitude: float | None = None
    dimensions: list[str] = field(default_factory=list)
    # Machine-readable support for "why is InsightPilot telling me this?"
    evidence: StructuredEvidence | dict[str, Any] = field(
        default_factory=StructuredEvidence
    )
    # Confidence in the analytical finding (high|medium|low),
    # not whether the business should take the recommendation,
    # and not how important the observation is.
    confidence: str = "medium"
    # Business importance (high|medium|low) — independent of confidence.
    importance: str = "medium"
    # Surfacing tier (critical|important|supporting).
    tier: str = "important"
    business_impact: str | None = None
    potential_drivers: list[str] = field(default_factory=list)
    recommendation: str | None = None
    # AI Insight Contract — separate from deterministic finding.
    ai_interpretation: dict[str, Any] | None = None
    # Legacy mirror of ai_interpretation for older UI clients.
    explanation: dict[str, Any] | None = None
    candidate_finding_id: str = ""
    source_columns: list[str] = field(default_factory=list)
    analysis_type: str = ""
    # Structured recipe retained so the engine can reproduce the result.
    # Not required to be end-user-facing yet.
    calculation: dict[str, Any] = field(default_factory=dict)
    traceability: dict[str, Any] = field(default_factory=dict)

    # Optional factual extras retained from CandidateFinding.
    comparison: str | None = None
    magnitude_unit: str | None = None
    rule_id: str | None = None
    severity: str | None = None

    # Deterministic ranking payload (see scoring.py).
    scoring: InsightScore | dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_insight(self)

    @property
    def facts(self) -> dict[str, Any]:
        """Subset established by deterministic analysis."""

        payload = asdict(self)
        return {
            key: payload[key]
            for key in FACT_FIELDS
            if key in payload
        }

    @property
    def interpretive(self) -> dict[str, Any]:
        """Hypotheses and suggested actions — not proven facts."""

        return {
            "ai_interpretation": self.ai_interpretation,
            "potential_drivers": list(self.potential_drivers),
            "recommendation": self.recommendation,
            "explanation": self.explanation,
        }


def normalize_category(value: str | None) -> str:
    """Normalize free-text category labels to InsightCategory values."""

    if not value:
        return InsightCategory.OTHER.value

    text = str(value).strip()
    if not text:
        return InsightCategory.OTHER.value

    known = {item.value.lower(): item.value for item in InsightCategory}
    lowered = text.lower()

    if lowered in known:
        return known[lowered]

    if lowered in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[lowered]

    for alias, canonical in _CATEGORY_ALIASES.items():
        if alias in lowered:
            return canonical

    return text


def normalize_insight_type(value: str | None) -> str:
    """Normalize insight_type to a known InsightType value when possible."""

    if not value:
        return InsightType.OTHER.value

    text = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )
    if not text:
        return InsightType.OTHER.value

    # Collapse repeated underscores from "growth / decline" style labels.
    while "__" in text:
        text = text.replace("__", "_")

    for item in InsightType:
        if text == item.value or text == item.name.lower():
            return item.value

    aliases = {
        "growth": InsightType.GROWTH_DECLINE.value,
        "decline": InsightType.GROWTH_DECLINE.value,
        "growth_decline": InsightType.GROWTH_DECLINE.value,
        "period_over_period": InsightType.GROWTH_DECLINE.value,
        "outlier": InsightType.ANOMALY.value,
        "outliers": InsightType.ANOMALY.value,
        "segment": InsightType.SEGMENT_DIFFERENCE.value,
        "segment_diff": InsightType.SEGMENT_DIFFERENCE.value,
        "segments": InsightType.SEGMENT_DIFFERENCE.value,
        "share": InsightType.CONTRIBUTION.value,
        "contribution_share": InsightType.CONTRIBUTION.value,
        "correlation": InsightType.RELATIONSHIP.value,
        "relationships": InsightType.RELATIONSHIP.value,
        "distributions": InsightType.DISTRIBUTION.value,
        "risks": InsightType.RISK.value,
        "exposure": InsightType.RISK.value,
        "upsell": InsightType.OPPORTUNITY.value,
        "cross_sell": InsightType.OPPORTUNITY.value,
        "performance": InsightType.COMPARISON.value,
    }

    known = {item.value for item in InsightType}
    resolved = aliases.get(text, text)
    return resolved if resolved in known else InsightType.OTHER.value


def infer_insight_type(
    *,
    analysis_type: str | None = None,
    comparison: str | None = None,
    rule_id: str | None = None,
    explicit: str | None = None,
) -> str:
    """Derive insight_type from explicit value or finding provenance."""

    if explicit:
        return normalize_insight_type(explicit)

    if rule_id:
        rule_key = str(rule_id).strip().lower()
        for hint, insight_type in (
            ("concentration", InsightType.CONCENTRATION.value),
            ("anomaly", InsightType.ANOMALY.value),
            ("outlier", InsightType.ANOMALY.value),
            ("opportunity", InsightType.OPPORTUNITY.value),
            ("risk", InsightType.RISK.value),
            ("exposure", InsightType.RISK.value),
            ("contribution", InsightType.CONTRIBUTION.value),
            ("share", InsightType.CONTRIBUTION.value),
            ("distribution", InsightType.DISTRIBUTION.value),
            ("relationship", InsightType.RELATIONSHIP.value),
            ("correlation", InsightType.RELATIONSHIP.value),
            ("segment", InsightType.SEGMENT_DIFFERENCE.value),
            ("growth", InsightType.GROWTH_DECLINE.value),
            ("decline", InsightType.GROWTH_DECLINE.value),
            ("trend", InsightType.TREND.value),
        ):
            if hint in rule_key:
                return insight_type

    if analysis_type:
        mapped = _ANALYSIS_TYPE_TO_INSIGHT_TYPE.get(
            str(analysis_type).strip().lower()
        )
        if mapped:
            return mapped

    if comparison:
        mapped = _COMPARISON_TO_INSIGHT_TYPE.get(
            str(comparison).strip().lower()
        )
        if mapped:
            return mapped

    return InsightType.OTHER.value


def promote_finding(
    finding: CandidateFinding | dict[str, Any],
    *,
    title: str | None = None,
    category: str | None = None,
    insight_type: str | None = None,
    finding_text: str | None = None,
    business_impact: str | None = None,
    potential_drivers: list[str] | None = None,
    recommendation: str | None = None,
    insight_id: str | None = None,
    require_insight_eligible: bool = True,
    data_quality_score: float | None = None,
) -> Insight | None:
    """
    Promote a validated, insight-eligible finding into an Insight.

    By default, candidates that are not validated or not insight-
    eligible return ``None`` (they remain findings). Set
    ``require_insight_eligible=False`` only for explicit overrides —
    never to bulk-promote every candidate.

    ``potential_drivers`` and ``recommendation`` are optional
    interpretive overlays. Pass them only when intentionally
    distinguishing hypotheses / next actions from facts.
    """

    from .validation import (
        is_insight_eligible,
        serialize_validated_finding,
        validate_finding,
    )

    validated = validate_finding(finding)
    if validated is None:
        return None

    serialized = serialize_validated_finding(validated)
    if serialized is None:
        return None

    if require_insight_eligible and not is_insight_eligible(validated):
        return None

    resolved_title = (
        str(title).strip()
        if title
        else str(serialized.get("title") or "").strip()
        or str(serialized.get("metric") or "Finding")
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
        metric_name=serialized.get("metric"),
        comparison=serialized.get("comparison"),
        relevant_dimensions=list(
            serialized.get("relevant_dimensions")
            or serialized.get("dimensions")
            or []
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
    provenance_payload = (
        serialized.get("provenance")
        if isinstance(serialized.get("provenance"), dict)
        else {}
    )
    dataset_from_provenance = provenance_payload.get("dataset")
    if isinstance(dataset_from_provenance, dict):
        evidence_payload = serialize_evidence(
            evidence_payload,
            source_dataset=dataset_from_provenance.get("dataset_label"),
            source_dataset_id=(
                dataset_from_provenance.get("dataset_id")
                or dataset_from_provenance.get("dataset_identity")
            ),
            dataset_version=dataset_from_provenance.get("dataset_version"),
            analyzed_at=dataset_from_provenance.get("analyzed_at"),
            records_excluded=dataset_from_provenance.get(
                "records_excluded"
            ),
        )
    evidence_summary = str(evidence_payload.get("summary") or "").strip()
    resolved_finding = (
        str(finding_text).strip()
        if finding_text
        else evidence_summary
        or resolved_title
    )

    dimensions = list(
        serialized.get("relevant_dimensions")
        or serialized.get("dimensions")
        or []
    )

    magnitude = serialized.get("magnitude")
    if magnitude is not None:
        try:
            magnitude = float(magnitude)
        except (TypeError, ValueError):
            magnitude = None

    drivers = [
        str(item).strip()
        for item in (potential_drivers or [])
        if str(item).strip()
    ]

    resolved_recommendation = (
        str(recommendation).strip()
        if recommendation is not None and str(recommendation).strip()
        else None
    )

    resolved_impact = (
        str(business_impact).strip()
        if business_impact is not None and str(business_impact).strip()
        else None
    )

    analysis_type = str(serialized.get("analysis_type") or "unknown")
    rule_id = serialized.get("rule_id")
    candidate_finding_id = str(
        serialized.get("id") or f"{analysis_type}:{rule_id or 'finding'}"
    )
    calculation_payload = serialize_calculation_spec(
        serialized.get("calculation")
        or (serialized.get("provenance") or {}).get("calculation"),
        analysis_type=analysis_type,
        dimension=(
            dimensions[0]
            if dimensions
            else None
        ),
        filters=list(serialized.get("filters") or []),
        source_columns=list(serialized.get("source_columns") or []),
        parameters={"metric": serialized.get("metric")},
    )
    traceability = {
        "candidate_finding_id": candidate_finding_id,
        "source_columns": list(serialized.get("source_columns") or []),
        "analysis_type": analysis_type,
        "dimensions": [str(item) for item in dimensions if item is not None],
        "filters": list(serialized.get("filters") or []),
        "calculations": list(serialized.get("calculations") or []),
        "calculation": calculation_payload,
        "rule_id": rule_id,
        "dataset": serialize_dataset_traceability(
            dataset_from_provenance
            if isinstance(dataset_from_provenance, dict)
            else None,
            source_columns=list(serialized.get("source_columns") or []),
            filters=list(serialized.get("filters") or []),
            records_excluded=(
                records_excluded_from_evidence(evidence_payload)
                or (
                    dataset_from_provenance.get("records_excluded")
                    if isinstance(dataset_from_provenance, dict)
                    else None
                )
            ),
            analysis_type=analysis_type,
            calculation=calculation_payload,
            methodology_steps=list(
                serialized.get("calculations") or []
            ),
            dataset_id=(
                evidence_payload.get("source_dataset_id")
                if isinstance(evidence_payload, dict)
                else None
            ),
            dataset_label=(
                evidence_payload.get("source_dataset")
                if isinstance(evidence_payload, dict)
                else None
            ),
            dataset_version=(
                evidence_payload.get("dataset_version")
                if isinstance(evidence_payload, dict)
                else None
            ),
            analyzed_at=(
                evidence_payload.get("analyzed_at")
                if isinstance(evidence_payload, dict)
                else None
            ),
        ),
    }

    resolved_category = category
    if not resolved_category:
        resolved_category = _ANALYSIS_TYPE_TO_CATEGORY.get(
            analysis_type.strip().lower()
        )

    resolved_insight_type = infer_insight_type(
        analysis_type=analysis_type,
        comparison=serialized.get("comparison"),
        rule_id=rule_id,
        explicit=insight_type,
    )
    resolved_severity = serialized.get("severity")
    resolved_confidence = normalize_confidence(
        serialized.get("confidence")
    )
    resolved_importance = resolve_importance(
        explicit=serialized.get("importance"),
        severity=resolved_severity,
        magnitude=magnitude,
        magnitude_unit=serialized.get("magnitude_unit"),
        insight_type=resolved_insight_type,
    )

    insight = Insight(
        insight_id=str(
            insight_id or serialized.get("id") or f"{analysis_type}:insight"
        ),
        title=resolved_title,
        category=normalize_category(resolved_category),
        insight_type=resolved_insight_type,
        finding=resolved_finding,
        metric=str(serialized.get("metric") or "unknown"),
        observed_value=serialized.get("observed_value"),
        baseline=serialized.get("baseline"),
        magnitude=magnitude,
        dimensions=[str(item) for item in dimensions if item is not None],
        evidence=evidence_payload,
        confidence=resolved_confidence,
        importance=resolved_importance,
        tier="important",
        business_impact=resolved_impact,
        potential_drivers=drivers,
        recommendation=resolved_recommendation,
        ai_interpretation=None,
        explanation=None,
        candidate_finding_id=candidate_finding_id,
        source_columns=list(serialized.get("source_columns") or []),
        analysis_type=analysis_type,
        calculation=calculation_payload,
        traceability=traceability,
        comparison=serialized.get("comparison"),
        magnitude_unit=serialized.get("magnitude_unit"),
        rule_id=rule_id,
        severity=resolved_severity or resolved_importance,
    )
    insight.scoring = score_insight(
        insight,
        severity=resolved_severity or resolved_importance,
        data_quality_score=data_quality_score,
    )
    insight.tier = resolve_insight_tier(insight)
    return insight


def serialize_insight(
    insight: Insight | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Normalize an Insight into a plain JSON-safe dict.

    Always emits FACT, ESTIMATED, and INTERPRETIVE keys so consumers
    can rely on a stable contract. Interpretive fields may be empty.
    """

    if insight is None:
        return None

    if isinstance(insight, Insight):
        payload = asdict(insight)
    elif isinstance(insight, dict):
        payload = dict(insight)
    elif hasattr(insight, "to_dict"):
        payload = insight.to_dict()
    else:
        return None

    insight_id = payload.get("insight_id") or payload.get("id")
    if not insight_id and not payload.get("metric"):
        return None

    analysis_type = str(payload.get("analysis_type") or "unknown")
    metric = str(payload.get("metric") or "unknown")
    title = str(payload.get("title") or metric).strip() or metric
    evidence_payload = serialize_evidence(
        payload.get("evidence"),
        observed_value=payload.get("observed_value"),
        baseline=payload.get("baseline"),
        magnitude=payload.get("magnitude"),
        magnitude_unit=payload.get("magnitude_unit"),
        metric_name=metric,
        comparison=payload.get("comparison"),
        relevant_dimensions=list(
            payload.get("dimensions")
            or payload.get("relevant_dimensions")
            or []
        ),
        filters=list(
            (payload.get("traceability") or {}).get("filters")
            or payload.get("filters")
            or []
        ),
        source_columns=list(
            payload.get("source_columns") or []
        ),
        source_dataset=(
            (
                (payload.get("traceability") or {}).get("dataset")
                or {}
            ).get("dataset_label")
            if isinstance(
                (payload.get("traceability") or {}).get("dataset"),
                dict,
            )
            else None
        ),
        source_dataset_id=(
            (
                (payload.get("traceability") or {}).get("dataset")
                or {}
            ).get("dataset_id")
            or (
                (payload.get("traceability") or {}).get("dataset")
                or {}
            ).get("dataset_identity")
            if isinstance(
                (payload.get("traceability") or {}).get("dataset"),
                dict,
            )
            else None
        ),
        dataset_version=(
            (
                (payload.get("traceability") or {}).get("dataset")
                or {}
            ).get("dataset_version")
            if isinstance(
                (payload.get("traceability") or {}).get("dataset"),
                dict,
            )
            else None
        ),
        analyzed_at=(
            (
                (payload.get("traceability") or {}).get("dataset")
                or {}
            ).get("analyzed_at")
            if isinstance(
                (payload.get("traceability") or {}).get("dataset"),
                dict,
            )
            else None
        ),
        records_excluded=(
            (
                (payload.get("traceability") or {}).get("dataset")
                or {}
            ).get("records_excluded")
            if isinstance(
                (payload.get("traceability") or {}).get("dataset"),
                dict,
            )
            else None
        ),
        methodology=list(
            (payload.get("traceability") or {}).get("calculations")
            or payload.get("calculations")
            or []
        ),
        calculation=dict(
            payload.get("calculation")
            or (payload.get("traceability") or {}).get("calculation")
            or (
                (payload.get("evidence") or {}).get("calculation")
                if isinstance(payload.get("evidence"), dict)
                else {}
            )
            or {}
        ),
    )
    evidence_summary = str(evidence_payload.get("summary") or "").strip()
    finding_text = (
        str(payload.get("finding") or "").strip()
        or evidence_summary
        or title
    )

    magnitude = payload.get("magnitude")
    if magnitude is not None:
        try:
            magnitude = float(magnitude)
        except (TypeError, ValueError):
            magnitude = None

    drivers_raw = payload.get("potential_drivers") or []
    if isinstance(drivers_raw, str):
        drivers = [drivers_raw.strip()] if drivers_raw.strip() else []
    else:
        drivers = [
            str(item).strip()
            for item in drivers_raw
            if str(item).strip()
        ]

    recommendation = payload.get("recommendation")
    if recommendation is not None:
        recommendation = str(recommendation).strip() or None

    business_impact = payload.get("business_impact")
    if business_impact is not None:
        business_impact = str(business_impact).strip() or None

    dimensions = list(
        payload.get("dimensions")
        or payload.get("relevant_dimensions")
        or []
    )
    candidate_finding_id = str(
        payload.get("candidate_finding_id")
        or payload.get("finding_id")
        or payload.get("id")
        or insight_id
        or f"{analysis_type}:{payload.get('rule_id') or metric}"
    )
    traceability = payload.get("traceability")
    if not isinstance(traceability, dict):
        traceability = {}
    traceability = {
        "candidate_finding_id": str(
            traceability.get("candidate_finding_id")
            or candidate_finding_id
        ),
        "source_columns": list(
            traceability.get("source_columns")
            or payload.get("source_columns")
            or []
        ),
        "analysis_type": str(
            traceability.get("analysis_type")
            or analysis_type
        ),
        "dimensions": [
            str(item)
            for item in (
                traceability.get("dimensions")
                or dimensions
                or []
            )
            if item is not None
        ],
        "filters": list(
            traceability.get("filters")
            or payload.get("filters")
            or []
        ),
        "calculations": list(
            traceability.get("calculations")
            or payload.get("calculations")
            or []
        ),
        "calculation": serialize_calculation_spec(
            traceability.get("calculation")
            or payload.get("calculation"),
            analysis_type=analysis_type,
            dimension=(
                dimensions[0]
                if dimensions
                else None
            ),
            filters=list(
                traceability.get("filters")
                or payload.get("filters")
                or []
            ),
            source_columns=list(
                traceability.get("source_columns")
                or payload.get("source_columns")
                or []
            ),
            parameters={"metric": metric},
        ),
        "rule_id": traceability.get("rule_id") or payload.get("rule_id"),
        "dataset": serialize_dataset_traceability(
            traceability.get("dataset")
            if isinstance(traceability.get("dataset"), dict)
            else None,
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
            records_excluded=records_excluded_from_evidence(
                evidence_payload
            ),
            analysis_type=str(
                traceability.get("analysis_type") or analysis_type
            ),
            calculation=serialize_calculation_spec(
                traceability.get("calculation")
                or payload.get("calculation"),
                analysis_type=analysis_type,
                dimension=(
                    dimensions[0]
                    if dimensions
                    else None
                ),
                filters=list(
                    traceability.get("filters")
                    or payload.get("filters")
                    or []
                ),
                source_columns=list(
                    traceability.get("source_columns")
                    or payload.get("source_columns")
                    or []
                ),
                parameters={"metric": metric},
            ),
            methodology_steps=list(
                traceability.get("calculations")
                or payload.get("calculations")
                or []
            ),
            dataset_id=(
                evidence_payload.get("source_dataset_id")
                if isinstance(evidence_payload, dict)
                else None
            ),
            dataset_label=(
                evidence_payload.get("source_dataset")
                if isinstance(evidence_payload, dict)
                else None
            ),
            dataset_version=(
                evidence_payload.get("dataset_version")
                if isinstance(evidence_payload, dict)
                else None
            ),
            analyzed_at=(
                evidence_payload.get("analyzed_at")
                if isinstance(evidence_payload, dict)
                else None
            ),
        ),
    }

    severity = payload.get("severity")
    importance = resolve_importance(
        explicit=payload.get("importance"),
        severity=severity,
        magnitude=magnitude,
        magnitude_unit=payload.get("magnitude_unit"),
        insight_type=payload.get("insight_type"),
    )
    resolved_insight_type = infer_insight_type(
        analysis_type=analysis_type,
        comparison=payload.get("comparison"),
        rule_id=payload.get("rule_id"),
        explicit=payload.get("insight_type"),
    )
    serialized = {
        "insight_id": str(
            insight_id or f"{analysis_type}:{metric}"
        ),
        "title": title,
        "category": normalize_category(payload.get("category")),
        "insight_type": resolved_insight_type,
        "finding": finding_text,
        "metric": metric,
        "observed_value": payload.get("observed_value"),
        "baseline": payload.get("baseline"),
        "magnitude": magnitude,
        "dimensions": [str(item) for item in dimensions if item is not None],
        "evidence": evidence_payload,
        "confidence": normalize_confidence(payload.get("confidence")),
        "importance": importance,
        "tier": (
            normalize_tier(payload.get("tier"))
            if payload.get("tier") is not None
            else resolve_insight_tier(
                {
                    **payload,
                    "importance": importance,
                    "insight_type": resolved_insight_type,
                }
            )
        ),
        "business_impact": business_impact,
        "potential_drivers": drivers,
        "recommendation": recommendation,
        "ai_interpretation": None,
        "explanation": None,
        "candidate_finding_id": candidate_finding_id,
        "source_columns": list(payload.get("source_columns") or []),
        "analysis_type": analysis_type,
        "calculation": serialize_calculation_spec(
            payload.get("calculation")
            or traceability.get("calculation"),
            analysis_type=analysis_type,
            dimension=(
                dimensions[0]
                if dimensions
                else None
            ),
            filters=list(
                traceability.get("filters")
                or payload.get("filters")
                or []
            ),
            source_columns=list(payload.get("source_columns") or []),
            parameters={"metric": metric},
        ),
        "traceability": traceability,
        "comparison": payload.get("comparison"),
        "magnitude_unit": payload.get("magnitude_unit"),
        "rule_id": payload.get("rule_id"),
        "severity": severity or importance,
    }

    contract = serialize_ai_insight(
        payload.get("ai_interpretation") or payload.get("explanation")
    )
    if contract is not None:
        from .explanation import apply_ai_insight_to_insight

        mirrored = apply_ai_insight_to_insight(
            serialized,
            contract,
            sync_legacy_fields=False,
        )
        if mirrored is not None:
            serialized = mirrored

    scoring_payload = serialize_insight_score(payload.get("scoring"))
    if scoring_payload is None:
        scoring_payload = score_insight(
            serialized,
            severity=severity or importance,
            data_quality_score=payload.get("data_quality_score"),
        ).to_dict()
    serialized["scoring"] = scoring_payload
    return serialized


def promote_findings(
    findings: list[Any] | None,
    *,
    overlays: dict[str, dict[str, Any]] | None = None,
    require_insight_eligible: bool = True,
    data_quality_score: float | None = None,
) -> list[dict[str, Any]]:
    """
    Promote insight-eligible validated findings into Insights.

    Candidates that fail validation or eligibility are skipped —
    they remain available as findings. Redundant Insights that
    describe the same business observation are consolidated
    (highest score kept). Returned Insights are ranked by
    deterministic scoring.total (descending).
    """

    from .validation import insight_eligible_findings, validate_findings

    promoted: list[dict[str, Any]] = []
    seen: set[str] = set()
    overlay_map = overlays or {}

    source_findings = (
        insight_eligible_findings(findings)
        if require_insight_eligible
        else validate_findings(findings)
    )

    for serialized_finding in source_findings:
        finding_id = str(serialized_finding.get("id") or "")
        rule_id = serialized_finding.get("rule_id")
        overlay = (
            overlay_map.get(finding_id)
            or (
                overlay_map.get(str(rule_id))
                if rule_id is not None
                else None
            )
            or {}
        )

        insight = promote_finding(
            serialized_finding,
            title=overlay.get("title"),
            category=overlay.get("category"),
            insight_type=overlay.get("insight_type"),
            finding_text=overlay.get("finding"),
            business_impact=overlay.get("business_impact"),
            potential_drivers=overlay.get("potential_drivers"),
            recommendation=overlay.get("recommendation"),
            insight_id=overlay.get("insight_id") or finding_id,
            require_insight_eligible=require_insight_eligible,
            data_quality_score=(
                overlay.get("data_quality_score")
                if overlay.get("data_quality_score") is not None
                else data_quality_score
            ),
        )
        if insight is None:
            continue

        payload = serialize_insight(insight)
        if payload is None:
            continue

        insight_id = payload["insight_id"]
        if insight_id in seen:
            continue

        seen.add(insight_id)
        promoted.append(payload)

    consolidated = consolidate_redundant_insights(promoted)
    return sort_insights_by_score(consolidated)


def promote_validated_findings(
    findings: list[Any] | None,
    *,
    overlays: dict[str, dict[str, Any]] | None = None,
    data_quality_score: float | None = None,
) -> list[dict[str, Any]]:
    """
    Promote validated findings into consistent business Insights.

    Discovery remains the responsibility of the candidate-finding
    engine. This layer is only responsible for taking validated,
    insight-eligible findings and applying the standardized
    business-facing Insight contract (including ranking scores).
    """

    return promote_findings(
        findings,
        overlays=overlays,
        require_insight_eligible=True,
        data_quality_score=data_quality_score,
    )


def collect_promoted_insights_from_dashboards(
    dashboards: list[Any] | None,
    *,
    scope_by_dashboard: bool = False,
) -> list[dict[str, Any]]:
    """
    Aggregate Insights from insight-eligible validated findings.

    Candidate findings that are not eligible remain findings only.
    Narrative dashboard insights may supply category and
    recommendation overlays — never potential_drivers.
    """

    from .findings import collect_candidate_findings_from_dashboards

    findings = collect_candidate_findings_from_dashboards(
        dashboards,
        scope_by_dashboard=scope_by_dashboard,
    )

    overlays: dict[str, dict[str, Any]] = {}

    for dashboard in dashboards or []:
        if not isinstance(dashboard, dict):
            continue

        dashboard_id = str(dashboard.get("id") or "dashboard")

        for raw_insight in dashboard.get("insights") or []:
            if not isinstance(raw_insight, dict):
                continue

            rule_id = (
                raw_insight.get("rule_id")
                or raw_insight.get("id")
            )
            if not rule_id:
                continue

            recommendation = (
                raw_insight.get("recommended_action")
                or raw_insight.get("recommendation")
            )
            category = raw_insight.get("category")
            title = raw_insight.get("title")

            overlay: dict[str, Any] = {}
            if category:
                overlay["category"] = category
            if title:
                overlay["title"] = title
            if recommendation and str(recommendation).strip():
                # Interpretive: rule-authored suggestion, not a fact.
                overlay["recommendation"] = str(recommendation).strip()

            if not overlay:
                continue

            keys = [str(rule_id)]
            if scope_by_dashboard:
                keys.append(f"{dashboard_id}:{rule_id}")
                keys.append(
                    f"{dashboard_id}:{dashboard_id}:{rule_id}"
                )

            for key in keys:
                overlays[key] = {
                    **overlays.get(key, {}),
                    **overlay,
                }

    return promote_validated_findings(
        findings,
        overlays=overlays,
    )
