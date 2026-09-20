"""
Insight Executive Brief — concise leadership read (30–60 seconds).

Built only after individual Insights can be explained. Deterministic
code selects the top ranked Insights and assembles the fact pack;
AI (or fallback) synthesizes why they matter together and what
leadership should investigate across them.

Contract:

    What matters most?     → top 3–5 ranked Insights (facts)
    Why does it matter?    → short AI synthesis
    What should leadership
    investigate?           → cross-insight recommendations

Not a lengthy report. Prefer omission over invention.
"""

from __future__ import annotations

from typing import Any

from .explanation import (
    AI_INSIGHT_FORBIDDEN_INPUT_KEYS,
    hedge_causal_language,
    strip_invented_numbers,
    collect_allowed_number_tokens,
)


EXECUTIVE_BRIEF_VERSION = "v1"
DEFAULT_BRIEF_INSIGHT_CAP = 5
MIN_BRIEF_INSIGHTS = 3
MAX_LEADERSHIP_ITEMS = 5
TARGET_READING_SECONDS = 60

REQUIRED_EXECUTIVE_BRIEF_KEYS: frozenset[str] = frozenset(
    {
        "what_matters_most",
        "why_it_matters",
        "leadership_investigate",
        "layer",
        "source",
        "version",
    }
)

EXECUTIVE_BRIEF_ALLOWED_INPUT_SECTIONS: frozenset[str] = frozenset(
    {
        "constraints",
        "product_context",
        "what_matters_most",
        "cross_insight_signals",
        "data_quality_limitations",
    }
)

EXECUTIVE_BRIEF_CONSTRAINTS: dict[str, Any] = {
    "role": "executive_brief",
    "may_invent_numbers": False,
    "may_invent_trends": False,
    "may_claim_causation_without_evidence": False,
    "may_alter_calculated_values": False,
    "may_manufacture_business_context": False,
    "may_receive_raw_dataset": False,
    "must_use_only_provided_facts": True,
    "target_reading_seconds": TARGET_READING_SECONDS,
    "max_insights": DEFAULT_BRIEF_INSIGHT_CAP,
    "max_leadership_items": MAX_LEADERSHIP_ITEMS,
    "tone": "concise_leadership",
    "forbidden_input_keys": sorted(AI_INSIGHT_FORBIDDEN_INPUT_KEYS),
    "allowed_input_sections": sorted(
        EXECUTIVE_BRIEF_ALLOWED_INPUT_SECTIONS
    ),
}


def build_executive_brief_constraints() -> dict[str, Any]:
    return dict(EXECUTIVE_BRIEF_CONSTRAINTS)


def empty_executive_brief(*, source: str = "fallback") -> dict[str, Any]:
    return {
        "version": EXECUTIVE_BRIEF_VERSION,
        "what_matters_most": [],
        "why_it_matters": "",
        "leadership_investigate": [],
        "estimated_reading_seconds": 0,
        "layer": "executive_brief",
        "source": source,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
        return payload if isinstance(payload, dict) else {}
    return {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _ai_contract(insight: dict[str, Any]) -> dict[str, Any]:
    ai = insight.get("ai_interpretation")
    if isinstance(ai, dict) and (
        ai.get("summary")
        or ai.get("why_it_matters")
        or ai.get("recommended_action")
    ):
        return ai
    explanation = insight.get("explanation")
    return explanation if isinstance(explanation, dict) else {}


def _insight_fact(insight: dict[str, Any]) -> str:
    return _first_text(
        insight.get("finding"),
        insight.get("what_happened"),
        insight.get("title"),
    )


def _insight_interpretation(insight: dict[str, Any]) -> str:
    ai = _ai_contract(insight)
    parts: list[str] = []
    seen: set[str] = set()
    for value in (
        ai.get("summary"),
        ai.get("why_it_matters"),
        insight.get("business_impact"),
        insight.get("why_it_matters"),
    ):
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(text)
    fact = _insight_fact(insight).lower()
    return " ".join(part for part in parts if part.lower() != fact)


def _insight_recommendation(insight: dict[str, Any]) -> str:
    ai = _ai_contract(insight)
    return _first_text(
        ai.get("recommended_action"),
        ai.get("next_action"),
        insight.get("recommendation"),
        insight.get("recommended_action"),
    )


def select_brief_insights(
    insights: list[Any] | None,
    *,
    cap: int = DEFAULT_BRIEF_INSIGHT_CAP,
) -> list[dict[str, Any]]:
    """
    Prefer the recommended / ranked set already produced by
    Initial Results. Cap at 3–5 for a 30–60 second read.
    """

    limit = max(0, min(int(cap), DEFAULT_BRIEF_INSIGHT_CAP))
    selected: list[dict[str, Any]] = []
    for item in insights or []:
        payload = _as_dict(item)
        if not payload:
            continue
        if not _insight_fact(payload):
            continue
        selected.append(payload)
        if len(selected) >= limit:
            break
    return selected


def _compact_matter_item(
    insight: dict[str, Any],
    *,
    rank: int,
) -> dict[str, Any]:
    ai = _ai_contract(insight)
    return {
        "rank": rank,
        "insight_id": insight.get("insight_id") or insight.get("id"),
        "title": _first_text(insight.get("title"), _insight_fact(insight)),
        "tier": insight.get("tier"),
        "importance": insight.get("importance") or insight.get("priority"),
        "category": insight.get("category"),
        "insight_type": insight.get("insight_type"),
        "fact": _insight_fact(insight),
        "interpretation": _insight_interpretation(insight),
        "recommendation": _insight_recommendation(insight),
        "metric": insight.get("metric"),
        "observed_value": insight.get("observed_value"),
        "baseline": insight.get("baseline"),
        "magnitude": insight.get("magnitude"),
        "confidence": insight.get("confidence"),
        "caveats": list(ai.get("caveats") or []),
    }


def _cross_insight_signals(
    matters: list[dict[str, Any]],
) -> dict[str, Any]:
    categories = sorted(
        {
            str(item.get("category") or "").strip()
            for item in matters
            if str(item.get("category") or "").strip()
        }
    )
    types = sorted(
        {
            str(item.get("insight_type") or "").strip()
            for item in matters
            if str(item.get("insight_type") or "").strip()
        }
    )
    recommendations = []
    seen: set[str] = set()
    for item in matters:
        action = str(item.get("recommendation") or "").strip()
        if not action:
            continue
        key = action.lower()
        if key in seen:
            continue
        seen.add(key)
        recommendations.append(action)

    themes: list[str] = []
    if len(categories) == 1:
        themes.append(f"All highlighted insights relate to {categories[0]}.")
    elif len(categories) > 1:
        themes.append(
            "Highlighted insights span "
            + ", ".join(categories)
            + "."
        )
    if "concentration" in types or "risk" in types:
        themes.append(
            "Concentration or risk signals appear among top insights."
        )
    if "growth_decline" in types or "trend" in types:
        themes.append(
            "Growth, decline, or trend movement appears among top insights."
        )

    return {
        "categories": categories,
        "insight_types": types,
        "shared_themes": themes,
        "per_insight_recommendations": recommendations[
            :MAX_LEADERSHIP_ITEMS
        ],
    }


def _data_quality_limitations(
    matters: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for item in matters:
        for caveat in item.get("caveats") or []:
            text = str(caveat or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            notes.append(text)
    return notes[:MAX_LEADERSHIP_ITEMS]


def build_executive_brief_fact_pack(
    insights: list[Any] | None,
    *,
    product_name: str | None = None,
    business_purpose: str | None = None,
    total_discovered: int | None = None,
    cap: int = DEFAULT_BRIEF_INSIGHT_CAP,
) -> dict[str, Any]:
    """
    Deterministic AI input for the executive brief.

    Includes only top ranked Insights (with their explanations),
    light product context, cross-insight signals, and DQ caveats.
    Never includes the raw dataset.
    """

    selected = select_brief_insights(insights, cap=cap)
    matters = [
        _compact_matter_item(insight, rank=index)
        for index, insight in enumerate(selected, start=1)
    ]

    return {
        "constraints": build_executive_brief_constraints(),
        "product_context": {
            "product_name": str(product_name or "").strip() or None,
            "business_purpose": str(business_purpose or "").strip()
            or None,
            "total_discovered": total_discovered
            if total_discovered is not None
            else len(insights or []),
            "highlighted_count": len(matters),
        },
        "what_matters_most": matters,
        "cross_insight_signals": _cross_insight_signals(matters),
        "data_quality_limitations": _data_quality_limitations(matters),
    }


def _estimate_reading_seconds(brief: dict[str, Any]) -> int:
    words = 0
    for item in brief.get("what_matters_most") or []:
        if isinstance(item, dict):
            words += len(str(item.get("fact") or "").split())
            words += len(str(item.get("title") or "").split())
    words += len(str(brief.get("why_it_matters") or "").split())
    for item in brief.get("leadership_investigate") or []:
        words += len(str(item or "").split())
    # ~200 wpm leadership skim.
    seconds = max(15, round(words / 200 * 60))
    return min(seconds, TARGET_READING_SECONDS)


def _public_matters(
    matters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Trim fact-pack rows to the leadership-facing surface."""

    public: list[dict[str, Any]] = []
    for item in matters:
        public.append(
            {
                "rank": item.get("rank"),
                "insight_id": item.get("insight_id"),
                "title": item.get("title"),
                "tier": item.get("tier"),
                "importance": item.get("importance"),
                "fact": item.get("fact"),
            }
        )
    return public


def build_fallback_executive_brief(
    fact_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Deterministic brief from the fact pack — no LLM required.

    Synthesis stays short and grounded in provided interpretations
    and recommendations only.
    """

    pack = fact_pack or {}
    matters = [
        item
        for item in (pack.get("what_matters_most") or [])
        if isinstance(item, dict) and item.get("fact")
    ]
    if not matters:
        return empty_executive_brief(source="fallback")

    product = pack.get("product_context") or {}
    product_name = str(product.get("product_name") or "This product").strip()
    signals = pack.get("cross_insight_signals") or {}
    themes = list(signals.get("shared_themes") or [])
    dq = list(pack.get("data_quality_limitations") or [])

    interpretation_bits = [
        str(item.get("interpretation") or "").strip()
        for item in matters
        if str(item.get("interpretation") or "").strip()
    ]
    titles = [
        str(item.get("title") or "").strip()
        for item in matters
        if str(item.get("title") or "").strip()
    ]

    if len(matters) == 1:
        why = (
            interpretation_bits[0]
            if interpretation_bits
            else (
                f"{titles[0]} is the primary signal requiring attention "
                f"in {product_name}."
            )
        )
    else:
        lead = (
            f"{product_name} has {len(matters)} priority signals "
            "that deserve leadership attention."
        )
        if themes:
            why = f"{lead} {themes[0]}"
        elif interpretation_bits:
            why = f"{lead} {interpretation_bits[0]}"
        else:
            labeled = "; ".join(titles[:3])
            why = f"{lead} Top items: {labeled}."

    if dq:
        why = f"{why} Caveat: {dq[0]}"

    leadership: list[str] = []
    seen: set[str] = set()
    for action in signals.get("per_insight_recommendations") or []:
        text = hedge_causal_language(str(action or "").strip())
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        leadership.append(text)
        if len(leadership) >= MAX_LEADERSHIP_ITEMS:
            break

    if len(leadership) < 2 and len(matters) >= 2:
        cross = (
            "Compare the top insights together to identify shared "
            "drivers and prioritize a single investigation owner."
        )
        if cross.lower() not in seen:
            leadership.append(cross)

    if not leadership:
        leadership = [
            "Review the highlighted insights with the business owner "
            "and assign follow-up for the highest-importance item."
        ]

    allowed = collect_allowed_number_tokens(pack)
    why = strip_invented_numbers(
        hedge_causal_language(why),
        allowed_numbers=allowed,
    )
    leadership = [
        strip_invented_numbers(
            hedge_causal_language(item),
            allowed_numbers=allowed,
        )
        for item in leadership
    ]
    leadership = [item for item in leadership if item][
        :MAX_LEADERSHIP_ITEMS
    ]

    brief = {
        "version": EXECUTIVE_BRIEF_VERSION,
        "what_matters_most": _public_matters(matters),
        "why_it_matters": why,
        "leadership_investigate": leadership,
        "layer": "executive_brief",
        "source": "fallback",
    }
    brief["estimated_reading_seconds"] = _estimate_reading_seconds(brief)
    return brief


def sanitize_executive_brief(
    value: dict[str, Any] | None,
    *,
    fact_pack: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Keep the brief factual, hedged, and concise."""

    pack = fact_pack or {}
    draft = dict(value or {})
    allowed = collect_allowed_number_tokens(pack)

    matters = draft.get("what_matters_most")
    if not isinstance(matters, list) or not matters:
        matters = _public_matters(pack.get("what_matters_most") or [])
    else:
        # Prefer deterministic facts from the pack when available.
        pack_matters = {
            str(item.get("insight_id") or item.get("rank")): item
            for item in (pack.get("what_matters_most") or [])
            if isinstance(item, dict)
        }
        cleaned_matters: list[dict[str, Any]] = []
        for index, item in enumerate(matters, start=1):
            if not isinstance(item, dict):
                continue
            key = str(item.get("insight_id") or item.get("rank") or index)
            packed = pack_matters.get(key) or item
            cleaned_matters.append(
                {
                    "rank": packed.get("rank") or index,
                    "insight_id": packed.get("insight_id")
                    or item.get("insight_id"),
                    "title": packed.get("title") or item.get("title"),
                    "tier": packed.get("tier") or item.get("tier"),
                    "importance": packed.get("importance")
                    or item.get("importance"),
                    "fact": packed.get("fact") or item.get("fact"),
                }
            )
        matters = cleaned_matters[:DEFAULT_BRIEF_INSIGHT_CAP]

    why = strip_invented_numbers(
        hedge_causal_language(draft.get("why_it_matters")),
        allowed_numbers=allowed,
    )
    leadership = [
        strip_invented_numbers(
            hedge_causal_language(item),
            allowed_numbers=allowed,
        )
        for item in (draft.get("leadership_investigate") or [])
    ]
    leadership = [item for item in leadership if item][
        :MAX_LEADERSHIP_ITEMS
    ]

    if not why and matters:
        return build_fallback_executive_brief(pack)

    brief = {
        "version": EXECUTIVE_BRIEF_VERSION,
        "what_matters_most": matters,
        "why_it_matters": why,
        "leadership_investigate": leadership,
        "layer": "executive_brief",
        "source": source
        or str(draft.get("source") or "fallback"),
    }
    brief["estimated_reading_seconds"] = _estimate_reading_seconds(brief)
    return brief


def generate_fallback_insight_executive_brief(
    insights: list[Any] | None,
    *,
    product_name: str | None = None,
    business_purpose: str | None = None,
    total_discovered: int | None = None,
    cap: int = DEFAULT_BRIEF_INSIGHT_CAP,
) -> dict[str, Any]:
    """Convenience: fact pack + fallback brief in one call."""

    pack = build_executive_brief_fact_pack(
        insights,
        product_name=product_name,
        business_purpose=business_purpose,
        total_discovered=total_discovered,
        cap=cap,
    )
    return sanitize_executive_brief(
        build_fallback_executive_brief(pack),
        fact_pack=pack,
        source="fallback",
    )


def attach_executive_brief_to_initial_results(
    initial_results: dict[str, Any] | None,
    *,
    product_name: str | None = None,
    business_purpose: str | None = None,
    generator: Any = None,
) -> dict[str, Any]:
    """
    Attach an Insight Executive Brief onto Initial Results.

    Uses recommended insights (already explained when available).
    Skips regeneration when a brief is already present.
    """

    results = dict(initial_results or {})
    existing = results.get("executive_brief")
    if (
        isinstance(existing, dict)
        and (
            existing.get("what_matters_most")
            or existing.get("why_it_matters")
        )
    ):
        return results

    recommended = list(results.get("recommended_insights") or [])
    generate = generator or generate_fallback_insight_executive_brief
    brief = generate(
        recommended,
        product_name=product_name,
        business_purpose=business_purpose,
        total_discovered=results.get("total_discovered"),
        cap=min(
            int(results.get("recommended_cap") or DEFAULT_BRIEF_INSIGHT_CAP),
            DEFAULT_BRIEF_INSIGHT_CAP,
        ),
    )
    results["executive_brief"] = brief
    return results
