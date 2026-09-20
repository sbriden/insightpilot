"""
Initial Results Contract for Alpha insight surfacing.

The engine may discover many Insights. Alpha should not dump them
all onto the user. The Initial Results Contract answers:

    Total insights discovered: 27
    Tier 1: 3
    Tier 2: 7
    Tier 3: 17
    Recommended insights to surface: 5

The recommended set is the primary surface — roughly five things
InsightPilot thinks the user should know. The full ranked list
remains available for exploration.
"""

from __future__ import annotations

from typing import Any

from .scoring import sort_insights_by_score
from .tiers import (
    InsightTier,
    TIER_LABELS,
    normalize_tier,
    resolve_insight_tier,
)


INITIAL_RESULTS_VERSION = "v1"
DEFAULT_RECOMMENDED_CAP = 5


def build_initial_results(
    insights: list[Any] | None,
    *,
    recommended_cap: int = DEFAULT_RECOMMENDED_CAP,
) -> dict[str, Any]:
    """
    Build the Alpha Initial Results Contract from promoted Insights.

    ``recommended_insights`` prefers Tier 1 (Critical), then Tier 2
    (Important), and only fills with Tier 3 (Supporting) when needed
    to reach the cap.
    """

    cap = max(0, int(recommended_cap))
    ranked = sort_insights_by_score(_normalize_insight_list(insights))

    for payload in ranked:
        if not payload.get("tier"):
            payload["tier"] = resolve_insight_tier(payload)
        else:
            payload["tier"] = normalize_tier(payload.get("tier"))

    tier_counts = {
        InsightTier.CRITICAL.value: 0,
        InsightTier.IMPORTANT.value: 0,
        InsightTier.SUPPORTING.value: 0,
    }
    for payload in ranked:
        tier = normalize_tier(payload.get("tier"))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    recommended = select_recommended_insights(ranked, cap=cap)
    recommended_count = len(recommended)
    total = len(ranked)

    return {
        "version": INITIAL_RESULTS_VERSION,
        "total_discovered": total,
        "tier_counts": {
            "tier_1": tier_counts[InsightTier.CRITICAL.value],
            "tier_2": tier_counts[InsightTier.IMPORTANT.value],
            "tier_3": tier_counts[InsightTier.SUPPORTING.value],
            "critical": tier_counts[InsightTier.CRITICAL.value],
            "important": tier_counts[InsightTier.IMPORTANT.value],
            "supporting": tier_counts[InsightTier.SUPPORTING.value],
        },
        "tiers": [
            {
                "tier": 1,
                "key": InsightTier.CRITICAL.value,
                "label": TIER_LABELS[InsightTier.CRITICAL.value],
                "count": tier_counts[InsightTier.CRITICAL.value],
            },
            {
                "tier": 2,
                "key": InsightTier.IMPORTANT.value,
                "label": TIER_LABELS[InsightTier.IMPORTANT.value],
                "count": tier_counts[InsightTier.IMPORTANT.value],
            },
            {
                "tier": 3,
                "key": InsightTier.SUPPORTING.value,
                "label": TIER_LABELS[InsightTier.SUPPORTING.value],
                "count": tier_counts[InsightTier.SUPPORTING.value],
            },
        ],
        "recommended_cap": cap,
        "recommended_count": recommended_count,
        "recommended_insight_ids": [
            str(item.get("insight_id") or "")
            for item in recommended
            if item.get("insight_id")
        ],
        "recommended_insights": recommended,
        "headline": _headline(recommended_count, total),
        "summary": (
            f"Total insights discovered: {total}. "
            f"Tier 1: {tier_counts[InsightTier.CRITICAL.value]}, "
            f"Tier 2: {tier_counts[InsightTier.IMPORTANT.value]}, "
            f"Tier 3: {tier_counts[InsightTier.SUPPORTING.value]}. "
            f"Recommended insights to surface: {recommended_count}."
        ),
    }


def select_recommended_insights(
    insights: list[dict[str, Any]],
    *,
    cap: int = DEFAULT_RECOMMENDED_CAP,
) -> list[dict[str, Any]]:
    """
    Pick the Alpha recommended surface set.

    Order: Critical (by score) → Important → Supporting, capped.
    """

    if cap <= 0 or not insights:
        return []

    ranked = sort_insights_by_score(insights)
    buckets = {
        InsightTier.CRITICAL.value: [],
        InsightTier.IMPORTANT.value: [],
        InsightTier.SUPPORTING.value: [],
    }
    for payload in ranked:
        tier = normalize_tier(
            payload.get("tier") or resolve_insight_tier(payload)
        )
        buckets.setdefault(tier, []).append(payload)

    selected: list[dict[str, Any]] = []
    for tier in (
        InsightTier.CRITICAL.value,
        InsightTier.IMPORTANT.value,
        InsightTier.SUPPORTING.value,
    ):
        for payload in buckets.get(tier, []):
            if len(selected) >= cap:
                return selected
            selected.append(payload)

    return selected


def _headline(recommended_count: int, total: int) -> str:
    if recommended_count <= 0:
        if total <= 0:
            return "No insights to surface yet."
        return "Insights were discovered, but none are recommended to surface yet."

    if recommended_count == 1:
        return "This is the one thing I think you should know."

    return (
        f"These are the {recommended_count} things I think you should know."
    )


def _normalize_insight_list(insights: list[Any] | None) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in insights or []:
        if isinstance(item, dict):
            payloads.append(dict(item))
        elif hasattr(item, "to_dict"):
            serialized = item.to_dict()
            if isinstance(serialized, dict):
                payloads.append(dict(serialized))
    return payloads
