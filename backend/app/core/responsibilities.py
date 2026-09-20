"""
Deterministic vs AI responsibility boundary (User Story 8).

Semantic detection and analytical facts are owned by deterministic
code. Narrative generation is separated so an LLM cannot invent
analytical results.

Evidence vs Explanation (Increment 5):

    Evidence — DETERMINISTIC FACTS (this boundary)
        Numbers, methodology, source, data-quality limitations.
        e.g. "Revenue was $4.7M across the top 10 customers,
              representing 47% of total revenue."

    Explanation — INTERPRETATION (future / AI-allowed)
        What the facts might mean for the business.
        e.g. "This suggests the business may be exposed to
              customer concentration risk."

Evidence must never carry explanation. Explanation must never
invent or replace analytical facts.

Prevent hallucination (insight_explanation):

    The AI may receive only structured insight, evidence,
    relevant dataset context, and data-quality limitations.
    It must not receive the entire raw dataset by default.
    It must not invent numbers or trends, claim causation
    without evidence, introduce unsupported entity facts,
    alter calculated values, or manufacture business context.
    Unsupported causes must use potential language
    ("Potential drivers include...") rather than
    ("This happened because...").

Deterministic code remains responsible for:

    - data types
    - counts
    - aggregations
    - distributions
    - comparisons
    - trends
    - anomalies
    - statistical calculations
    - confidence calculations where deterministic
    - structured evidence (facts supporting an insight)

Reusable calculation entry points live in
``app.analysis.primitives`` (period change, shares,
concentration, distributions, outliers, trends,
segment comparisons, correlation). Analytical modules
and services must call those helpers — or equivalent
deterministic code — rather than an LLM.

The LLM must never be introduced as the calculation engine for
those functions. It may eventually help interpret ambiguous column
semantics, but that output must be structured and validated before
becoming part of the analysis context.
"""

from __future__ import annotations

from typing import Any, Final


# Analytical functions that must stay in deterministic code.
DETERMINISTIC_RESPONSIBILITIES: Final[frozenset[str]] = frozenset(
    {
        "data_types",
        "counts",
        "aggregations",
        "distributions",
        "comparisons",
        "trends",
        "anomalies",
        "statistical_calculations",
        "confidence_calculations",
        "period_over_period_change",
        "concentration",
        "contribution_share",
        "growth_decline",
        "segment_differences",
        "relationship_correlation",
        "outlier_detection",
        # Machine-readable facts behind an insight — never narrative.
        "structured_evidence",
    }
)

# Functions an LLM may eventually perform — never calculation.
AI_ALLOWED_RESPONSIBILITIES: Final[frozenset[str]] = frozenset(
    {
        # Prose over precomputed facts / insights only.
        "narrative_generation",
        # Propose structured concept candidates; never raw facts.
        "ambiguous_column_semantics",
        # Interpretation of precomputed evidence / insights — never invents facts.
        "insight_explanation",
        "insight_potential_drivers",
        "insight_recommendation",
        # Concise leadership brief over explained Insights.
        "executive_brief",
    }
)

# Keys that may appear in LLM narrative prompt context.
# Raw dataframe rows / series are intentionally excluded.
NARRATIVE_PROMPT_FACT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "profile",
        "metrics",
        "classification",
        "semantic_model",
        "capabilities",
        "dataset_archetype",
        "analytical_candidates",
        "candidate_findings",
        "validated_findings",
        "promoted_insights",
        "recommendations",
        "insights",
        "analysis_dashboards",
        "narrative_constraints",
    }
)

NARRATIVE_CONSTRAINTS: Final[dict[str, Any]] = {
    "role": "narrative_generation",
    "may_invent_numbers": False,
    "may_compute_aggregations": False,
    "may_compute_trends": False,
    "may_compute_anomalies": False,
    "may_compute_statistics": False,
    "must_use_only_provided_facts": True,
    "deterministic_responsibilities": sorted(
        DETERMINISTIC_RESPONSIBILITIES
    ),
}

# Anti-hallucination constraints for insight interpretation.
# AI receives structured insight + evidence + dataset context +
# data-quality limitations — never the raw dataset by default.
INSIGHT_EXPLANATION_CONSTRAINTS: Final[dict[str, Any]] = {
    "role": "insight_explanation",
    "may_invent_numbers": False,
    "may_invent_trends": False,
    "may_claim_causation_without_evidence": False,
    "may_introduce_unsupported_entity_facts": False,
    "may_alter_calculated_values": False,
    "may_manufacture_business_context": False,
    "may_receive_raw_dataset": False,
    "must_use_only_provided_facts": True,
    "driver_language": "potential",
    "preferred_driver_preamble": "Potential drivers include",
    "forbidden_causal_phrases": [
        "this happened because",
        "happened because",
        "caused by",
        "was caused by",
        "is caused by",
        "as a result of",
        "resulting from",
        "due to the fact that",
        "the reason is",
        "the root cause is",
        "driven solely by",
    ],
    "allowed_inputs": [
        "structured_insight",
        "evidence",
        "dataset_context",
        "data_quality_limitations",
    ],
}

EXECUTIVE_BRIEF_CONSTRAINTS: Final[dict[str, Any]] = {
    "role": "executive_brief",
    "may_invent_numbers": False,
    "may_invent_trends": False,
    "may_claim_causation_without_evidence": False,
    "may_alter_calculated_values": False,
    "may_manufacture_business_context": False,
    "may_receive_raw_dataset": False,
    "must_use_only_provided_facts": True,
    "target_reading_seconds": 60,
    "max_insights": 5,
    "tone": "concise_leadership",
    "allowed_inputs": [
        "what_matters_most",
        "cross_insight_signals",
        "data_quality_limitations",
        "product_context",
    ],
}


def is_deterministic_responsibility(name: str) -> bool:
    return name in DETERMINISTIC_RESPONSIBILITIES


def is_ai_allowed_responsibility(name: str) -> bool:
    return name in AI_ALLOWED_RESPONSIBILITIES


def assert_ai_not_calculation_engine(responsibility: str) -> None:
    """
    Guard used by callers / tests when wiring AI features.

    Raises if the requested responsibility belongs to the
    deterministic analytical surface.
    """
    if responsibility in DETERMINISTIC_RESPONSIBILITIES:
        raise ValueError(
            f"AI must not act as the calculation engine for "
            f"'{responsibility}'. Deterministic code owns "
            f"{sorted(DETERMINISTIC_RESPONSIBILITIES)}."
        )

    if responsibility not in AI_ALLOWED_RESPONSIBILITIES:
        raise ValueError(
            f"Unsupported AI responsibility '{responsibility}'. "
            f"Allowed: {sorted(AI_ALLOWED_RESPONSIBILITIES)}."
        )


def build_narrative_constraints() -> dict[str, Any]:
    """Copy of constraints attached to LLM prompt context."""

    return dict(NARRATIVE_CONSTRAINTS)


def build_insight_explanation_constraints() -> dict[str, Any]:
    """Copy of anti-hallucination constraints for insight AI."""

    return dict(INSIGHT_EXPLANATION_CONSTRAINTS)


def build_executive_brief_narrative_constraints() -> dict[str, Any]:
    """Copy of constraints for the insight executive brief."""

    return dict(EXECUTIVE_BRIEF_CONSTRAINTS)
