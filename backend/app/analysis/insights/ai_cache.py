"""
Per product-version cache for AI insight overlays.

AI enrichment runs at most once per product version. Subsequent
reads reuse the stored overlays. Deterministic Insights and
evidence remain available even when the cache is fallback-only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .explanation import (
    apply_ai_insight_to_insight,
    serialize_ai_insight,
)
from .initial_results import build_initial_results


INSIGHT_AI_CACHE_KEY = "insight_ai_cache"
INSIGHT_AI_CACHE_VERSION = "v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_ai_status(
    *,
    reason: str = "fallback",
    message: str | None = None,
    mode: str = "fallback",
) -> dict[str, Any]:
    return {
        "available": mode == "ai",
        "mode": mode,  # ai | fallback
        "reason": reason,
        "message": message,
        "generated_at": _utc_now_iso(),
    }


def build_insight_ai_cache(
    *,
    promoted_insights: list[dict[str, Any]] | None,
    executive_brief: dict[str, Any] | None,
    status: dict[str, Any] | None = None,
    recommended_insight_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Snapshot AI overlays for a product version."""

    explanations: dict[str, Any] = {}
    for insight in promoted_insights or []:
        if not isinstance(insight, dict):
            continue
        insight_id = str(insight.get("insight_id") or "").strip()
        if not insight_id:
            continue
        contract = serialize_ai_insight(
            insight.get("ai_interpretation") or insight.get("explanation")
        )
        if contract and contract.get("summary"):
            explanations[insight_id] = contract

    return {
        "schema_version": INSIGHT_AI_CACHE_VERSION,
        "status": status or empty_ai_status(),
        "recommended_insight_ids": list(recommended_insight_ids or []),
        "explanations": explanations,
        "executive_brief": executive_brief,
        "cached_at": _utc_now_iso(),
    }


def get_insight_ai_cache(
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    cache = metadata.get(INSIGHT_AI_CACHE_KEY)
    if not isinstance(cache, dict):
        return None
    if not isinstance(cache.get("explanations"), dict) and not cache.get(
        "executive_brief"
    ):
        return None
    return cache


def cache_has_usable_overlays(cache: dict[str, Any] | None) -> bool:
    if not isinstance(cache, dict):
        return False
    explanations = cache.get("explanations") or {}
    brief = cache.get("executive_brief")
    has_explanations = isinstance(explanations, dict) and any(
        isinstance(value, dict) and value.get("summary")
        for value in explanations.values()
    )
    has_brief = isinstance(brief, dict) and bool(
        brief.get("what_matters_most") or brief.get("why_it_matters")
    )
    return has_explanations or has_brief


def merge_cached_explanations(
    insights: list[Any] | None,
    cache: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Apply cached AI contracts onto rebuilt promoted Insights."""

    explanations = {}
    if isinstance(cache, dict) and isinstance(cache.get("explanations"), dict):
        explanations = cache["explanations"]

    merged: list[dict[str, Any]] = []
    for item in insights or []:
        payload = dict(item) if isinstance(item, dict) else None
        if payload is None:
            continue
        insight_id = str(payload.get("insight_id") or "").strip()
        contract = explanations.get(insight_id) if insight_id else None
        if isinstance(contract, dict) and contract.get("summary"):
            applied = apply_ai_insight_to_insight(payload, contract)
            merged.append(applied or payload)
        else:
            merged.append(payload)
    return merged


def apply_insight_ai_cache_to_product(
    product: dict[str, Any],
    *,
    generate_if_missing: bool = False,
    generator_explanations: Any = None,
    generator_brief: Any = None,
) -> dict[str, Any]:
    """
    Restore AI overlays from the product-version cache.

    When no cache exists (legacy rows), optionally build deterministic
    fallback overlays without calling an external AI provider.
    """

    metadata = product.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        product["metadata"] = metadata

    cache = get_insight_ai_cache(metadata)
    promoted = list(product.get("promoted_insights") or [])

    if cache_has_usable_overlays(cache):
        promoted = merge_cached_explanations(promoted, cache)
        results = build_initial_results(promoted)
        # Prefer cached recommended set ordering when present.
        cached_ids = [
            str(item).strip()
            for item in (cache.get("recommended_insight_ids") or [])
            if str(item).strip()
        ]
        if cached_ids:
            by_id = {
                str(item.get("insight_id") or ""): item
                for item in promoted
                if item.get("insight_id")
            }
            recommended = [
                by_id[insight_id]
                for insight_id in cached_ids
                if insight_id in by_id
            ]
            if recommended:
                results["recommended_insights"] = recommended
                results["recommended_insight_ids"] = [
                    str(item.get("insight_id"))
                    for item in recommended
                ]
                results["recommended_count"] = len(recommended)

        brief = cache.get("executive_brief")
        if isinstance(brief, dict):
            results["executive_brief"] = brief
        elif generator_brief is not None:
            results = generator_brief(
                initial_results=results,
                product_name=product.get("name"),
                business_purpose=product.get("business_purpose"),
                allow_provider=False,
            )

        product["promoted_insights"] = promoted
        product["insight_initial_results"] = results
        product["executive_brief"] = results.get("executive_brief")
        product["ai_status"] = cache.get("status") or empty_ai_status(
            reason="cached"
        )
        return product

    if not generate_if_missing:
        results = build_initial_results(promoted)
        product["insight_initial_results"] = results
        product["executive_brief"] = None
        product["ai_status"] = empty_ai_status(
            reason="cache_missing",
            message="AI overlays not yet generated for this version.",
        )
        return product

    # Legacy / missing cache: deterministic fallback only.
    if generator_explanations is not None:
        promoted, results = generator_explanations(
            promoted_insights=promoted,
            initial_results=build_initial_results(promoted),
            allow_provider=False,
        )
    else:
        results = build_initial_results(promoted)

    if generator_brief is not None:
        results = generator_brief(
            initial_results=results,
            product_name=product.get("name"),
            business_purpose=product.get("business_purpose"),
            allow_provider=False,
        )

    product["promoted_insights"] = promoted
    product["insight_initial_results"] = results
    product["executive_brief"] = (
        results.get("executive_brief")
        if isinstance(results, dict)
        else None
    )
    product["ai_status"] = empty_ai_status(
        reason="fallback",
        message="Using deterministic overlays; no cached AI run.",
    )
    return product


def stamp_metadata_with_ai_cache(
    metadata: dict[str, Any] | None,
    cache: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload[INSIGHT_AI_CACHE_KEY] = cache
    return payload
