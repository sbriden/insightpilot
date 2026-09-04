"""
Narrative generation over precomputed analytical facts.

The LLM (when wired) is never the calculation engine for data
types, counts, aggregations, distributions, comparisons, trends,
anomalies, statistical calculations, or deterministic confidence.
It may only narrate facts already present on AnalysisContext.
"""

from ..core.analysis_context import AnalysisContext
from ..core.responsibilities import assert_ai_not_calculation_engine
from .prompts import build_executive_brief_prompt


def generate_fallback_brief(
    context: AnalysisContext,
) -> dict:
    """
    Deterministic executive brief assembled from existing facts.

    Uses profile counts, precomputed insights, and recommendations
    — no LLM and no new analytical calculations.
    """

    classification = (
        context.classification.get("dataset_type")
        or context.classification.get("classification")
        or context.classification.get("type")
        or "unknown"
    )

    summary = context.profile.get(
        "summary",
        {}
    )

    rows = summary.get(
        "rows",
        0
    )

    columns = summary.get(
        "columns",
        0
    )

    return {
        "overview": (
            f"This appears to be a {classification} dataset "
            f"containing {rows:,} rows and {columns} columns."
        ),

        "key_findings": [
            insight["description"]
            for insight in context.insights[:3]
        ],

        "risks": [
            insight["description"]
            for insight in context.insights
            if insight["severity"] == "high"
        ],

        "opportunities": [
            recommendation
            for recommendation in context.recommendations[:3]
        ],

        "next_steps": [
            "Review high priority insights",
            "Perform deeper business analysis",
        ],
    }


def generate_executive_brief(
    context: AnalysisContext,
) -> dict:
    """
    Produce an executive brief from precomputed analytical facts.

    Responsibility: narrative_generation only. Never computes
    metrics, trends, aggregations, or other deterministic
    analytical functions. When an LLM client is connected, it
    must receive ``context.to_prompt_context()`` only.
    """

    assert_ai_not_calculation_engine("narrative_generation")

    # Prompt is built for future LLM wiring; today we return the
    # deterministic fallback so analytical numbers stay fact-backed.
    _ = build_executive_brief_prompt(context)

    return generate_fallback_brief(context)
