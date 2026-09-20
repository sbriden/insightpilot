"""
Narrative generation over precomputed analytical facts.

The LLM (when wired) is never the calculation engine for data
types, counts, aggregations, distributions, comparisons, trends,
anomalies, statistical calculations, or deterministic confidence.
It may only narrate facts already present on AnalysisContext.

AI is an enhancement. Provider failures, missing credentials,
invalid output, and exhausted quota all fall back to
deterministic overlays so Insights and evidence stay available.
"""

from __future__ import annotations

import logging
from typing import Any

from ..core.responsibilities import assert_ai_not_calculation_engine
from ..analysis.insights.explanation import (
    REQUIRED_AI_INSIGHT_KEYS,
    apply_ai_insight_to_insight,
    build_ai_insight_fact_pack,
    build_fallback_ai_insight,
    explain_recommended_insights,
    sanitize_ai_insight_contract,
    serialize_ai_insight,
)
from ..analysis.insights.executive_brief import (
    REQUIRED_EXECUTIVE_BRIEF_KEYS,
    attach_executive_brief_to_initial_results,
    build_executive_brief_fact_pack,
    build_fallback_executive_brief,
    sanitize_executive_brief,
)
from .ai_client import (
    AI_REASON_FALLBACK,
    AI_REASON_INVALID_OUTPUT,
    AI_REASON_OK,
    complete_json,
    probe_ai_availability,
)
from .prompts import (
    build_executive_brief_prompt,
    build_insight_executive_brief_prompt,
    build_insight_explanation_prompt,
)


logger = logging.getLogger(__name__)


def generate_fallback_brief(context) -> dict:
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


def generate_executive_brief(context) -> dict:
    """
    Produce an executive brief from precomputed analytical facts.

    Responsibility: narrative_generation only. Never computes
    metrics, trends, aggregations, or other deterministic
    analytical functions. When an LLM client is connected, it
    must receive ``context.to_prompt_context()`` only.
    """

    assert_ai_not_calculation_engine("narrative_generation")

    prompt = build_executive_brief_prompt(context)
    availability = probe_ai_availability()
    if not availability.ok:
        return generate_fallback_brief(context)

    result = complete_json(prompt, required_keys={"overview"})
    if not result.ok or not result.data:
        logger.info(
            "Dataset executive brief falling back (%s)",
            result.reason,
        )
        return generate_fallback_brief(context)

    data = result.data
    fallback = generate_fallback_brief(context)
    return {
        "overview": str(data.get("overview") or fallback["overview"]),
        "key_findings": list(
            data.get("key_findings") or fallback["key_findings"]
        ),
        "risks": list(data.get("risks") or fallback["risks"]),
        "opportunities": list(
            data.get("opportunities") or fallback["opportunities"]
        ),
        "next_steps": list(
            data.get("next_steps") or fallback["next_steps"]
        ),
    }


def _fallback_insight_explanation(insight: Any) -> dict:
    fact_pack = build_ai_insight_fact_pack(insight)
    return sanitize_ai_insight_contract(
        build_fallback_ai_insight(insight),
        insight=insight,
        fact_pack=fact_pack,
        source="fallback",
    )


def generate_insight_explanation(
    insight,
    *,
    allow_provider: bool = True,
) -> dict:
    """
    Produce the AI Insight Contract for one deterministic Insight.

    On any AI failure, returns the deterministic evidence-backed
    fallback so analytical correctness is unchanged.
    """

    assert_ai_not_calculation_engine("insight_explanation")

    fact_pack = build_ai_insight_fact_pack(insight)
    prompt = build_insight_explanation_prompt(fact_pack)
    fallback = sanitize_ai_insight_contract(
        build_fallback_ai_insight(insight),
        insight=insight,
        fact_pack=fact_pack,
        source="fallback",
    )

    if not allow_provider:
        return fallback

    availability = probe_ai_availability()
    if not availability.ok:
        return fallback

    result = complete_json(
        prompt,
        required_keys={"summary"},
    )
    if not result.ok or not result.data:
        logger.info(
            "Insight explanation falling back (%s)",
            result.reason,
        )
        return fallback

    try:
        sanitized = sanitize_ai_insight_contract(
            result.data,
            insight=insight,
            fact_pack=fact_pack,
            source="ai",
        )
    except Exception as exc:
        logger.info(
            "Insight explanation sanitize failed; fallback (%s)",
            exc,
        )
        return fallback

    if not sanitized.get("summary"):
        return fallback

    # Ensure required contract keys survived sanitization.
    if not REQUIRED_AI_INSIGHT_KEYS.issubset(set(sanitized)):
        return {
            **fallback,
            "source": "fallback",
        }

    return sanitized


def generate_insight_explanations_for_selection(
    *,
    promoted_insights: list | None,
    initial_results: dict | None = None,
    allow_provider: bool = True,
) -> tuple[list, dict]:
    """
    Attach AI Insight Contracts to the recommended / selected set.
    """

    assert_ai_not_calculation_engine("insight_explanation")

    def _generator(insight):
        return generate_insight_explanation(
            insight,
            allow_provider=allow_provider,
        )

    return explain_recommended_insights(
        promoted_insights=promoted_insights,
        initial_results=initial_results,
        generator=_generator,
    )


def attach_insight_explanation(insight) -> dict | None:
    """Convenience: attach AI contract and return the Insight payload."""

    contract = generate_insight_explanation(insight)
    return apply_ai_insight_to_insight(
        insight,
        serialize_ai_insight(contract),
    )


def _fallback_insight_executive_brief(
    insights,
    *,
    product_name: str | None = None,
    business_purpose: str | None = None,
    total_discovered: int | None = None,
    cap: int = 5,
) -> dict:
    fact_pack = build_executive_brief_fact_pack(
        insights,
        product_name=product_name,
        business_purpose=business_purpose,
        total_discovered=total_discovered,
        cap=cap,
    )
    return sanitize_executive_brief(
        build_fallback_executive_brief(fact_pack),
        fact_pack=fact_pack,
        source="fallback",
    )


def generate_insight_executive_brief(
    insights,
    *,
    product_name: str | None = None,
    business_purpose: str | None = None,
    total_discovered: int | None = None,
    cap: int = 5,
    allow_provider: bool = True,
) -> dict:
    """
    Produce a concise Insight Executive Brief for leadership.

    Deterministic input = top ranked explained Insights.
    AI synthesizes when available; otherwise fallback.
    """

    assert_ai_not_calculation_engine("executive_brief")

    fact_pack = build_executive_brief_fact_pack(
        insights,
        product_name=product_name,
        business_purpose=business_purpose,
        total_discovered=total_discovered,
        cap=cap,
    )
    prompt = build_insight_executive_brief_prompt(fact_pack)
    fallback = sanitize_executive_brief(
        build_fallback_executive_brief(fact_pack),
        fact_pack=fact_pack,
        source="fallback",
    )

    if not allow_provider:
        return fallback

    availability = probe_ai_availability()
    if not availability.ok:
        return fallback

    result = complete_json(
        prompt,
        required_keys={"why_it_matters"},
    )
    if not result.ok or not result.data:
        logger.info(
            "Insight executive brief falling back (%s)",
            result.reason,
        )
        return fallback

    try:
        sanitized = sanitize_executive_brief(
            result.data,
            fact_pack=fact_pack,
            source="ai",
        )
    except Exception as exc:
        logger.info(
            "Insight executive brief sanitize failed; fallback (%s)",
            exc,
        )
        return fallback

    if not sanitized.get("why_it_matters") and not sanitized.get(
        "what_matters_most"
    ):
        return fallback

    if not REQUIRED_EXECUTIVE_BRIEF_KEYS.issubset(set(sanitized)):
        # Keep deterministic facts even if AI omitted keys.
        return {
            **fallback,
            "why_it_matters": sanitized.get("why_it_matters")
            or fallback.get("why_it_matters"),
            "leadership_investigate": sanitized.get(
                "leadership_investigate"
            )
            or fallback.get("leadership_investigate"),
            "source": "fallback",
        }

    return sanitized


def generate_insight_executive_brief_for_results(
    *,
    initial_results: dict | None,
    product_name: str | None = None,
    business_purpose: str | None = None,
    allow_provider: bool = True,
) -> dict:
    """Attach an executive brief onto Initial Results."""

    assert_ai_not_calculation_engine("executive_brief")

    def _generator(
        insights,
        *,
        product_name=None,
        business_purpose=None,
        total_discovered=None,
        cap=5,
    ):
        return generate_insight_executive_brief(
            insights,
            product_name=product_name,
            business_purpose=business_purpose,
            total_discovered=total_discovered,
            cap=cap,
            allow_provider=allow_provider,
        )

    return attach_executive_brief_to_initial_results(
        initial_results,
        product_name=product_name,
        business_purpose=business_purpose,
        generator=_generator,
    )


def enrich_insights_with_ai(
    *,
    promoted_insights: list | None,
    initial_results: dict | None = None,
    product_name: str | None = None,
    business_purpose: str | None = None,
    allow_provider: bool = True,
) -> tuple[list, dict, dict]:
    """
    Run insight explanations + executive brief once.

    Returns ``(promoted_insights, initial_results, ai_status)``.
    Never raises for provider failures.
    """

    availability = probe_ai_availability()
    use_provider = allow_provider and availability.ok

    try:
        promoted, results = generate_insight_explanations_for_selection(
            promoted_insights=promoted_insights,
            initial_results=initial_results,
            allow_provider=use_provider,
        )
        results = generate_insight_executive_brief_for_results(
            initial_results=results,
            product_name=product_name,
            business_purpose=business_purpose,
            allow_provider=use_provider,
        )
    except Exception as exc:
        logger.exception("AI enrichment failed; using fallbacks: %s", exc)
        promoted, results = generate_insight_explanations_for_selection(
            promoted_insights=promoted_insights,
            initial_results=initial_results,
            allow_provider=False,
        )
        results = generate_insight_executive_brief_for_results(
            initial_results=results,
            product_name=product_name,
            business_purpose=business_purpose,
            allow_provider=False,
        )
        return (
            promoted,
            results,
            {
                "available": False,
                "mode": "fallback",
                "reason": AI_REASON_FALLBACK,
                "message": str(exc),
            },
        )

    # Infer mode from produced overlays.
    brief = results.get("executive_brief") if isinstance(results, dict) else None
    sources = []
    if isinstance(brief, dict) and brief.get("source"):
        sources.append(str(brief.get("source")))
    for item in results.get("recommended_insights") or []:
        if not isinstance(item, dict):
            continue
        ai = item.get("ai_interpretation") or item.get("explanation") or {}
        if isinstance(ai, dict) and ai.get("source"):
            sources.append(str(ai.get("source")))

    mode = "ai" if sources and all(source == "ai" for source in sources) else (
        "ai" if any(source == "ai" for source in sources) else "fallback"
    )
    reason = AI_REASON_OK if mode == "ai" else (
        availability.reason if not availability.ok else AI_REASON_FALLBACK
    )

    return (
        promoted,
        results,
        {
            "available": mode == "ai",
            "mode": mode,
            "reason": reason,
            "message": availability.message
            if not availability.ok
            else (
                None
                if mode == "ai"
                else "Deterministic overlays used."
            ),
        },
    )
