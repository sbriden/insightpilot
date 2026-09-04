"""
Deterministic vs AI responsibility boundary (User Story 8).

Semantic detection and analytical facts are owned by deterministic
code. Narrative generation is separated so an LLM cannot invent
analytical results.

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
    }
)

# Functions an LLM may eventually perform — never calculation.
AI_ALLOWED_RESPONSIBILITIES: Final[frozenset[str]] = frozenset(
    {
        # Prose over precomputed facts / insights only.
        "narrative_generation",
        # Propose structured concept candidates; never raw facts.
        "ambiguous_column_semantics",
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
