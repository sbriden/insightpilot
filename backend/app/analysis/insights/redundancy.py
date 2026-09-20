"""
Detect and consolidate redundant Insights.

Pipeline position (after scoring, before final ranking):

    Validated Finding → Insight (+ score) → consolidate → sort

The engine can emit multiple rules that describe the same business
observation with different wording, e.g.:

    Revenue declined 15%.
    Revenue declined significantly.
    Revenue was lower this quarter.
    Quarterly revenue decreased.

Those should surface once. This layer clusters related Insights,
keeps the highest-scoring member, and records suppressed siblings
for traceability — it does not invent new wording.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .importance import normalize_importance


REDUNDANCY_VERSION = "v1"

# Metrics that describe the same underlying revenue momentum story.
_REVENUE_MOMENTUM_METRICS = frozenset(
    {
        "overall_revenue_growth",
        "revenue_growth",
        "revenue_decline",
        "revenue_change",
        "trend_change",
        "overall_growth",
    }
)

# Count / rate / pct suffixes collapsed when stemming related metrics.
_MEASURE_SUFFIXES = (
    "_count",
    "_rate",
    "_pct",
    "_percentage",
    "_percent",
    "_share",
    "_profit",
    "_total",
)

# Explicit stems → shared loss / margin story themes.
_THEME_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "loss_making_products",
        (
            "negative_product",
            "product_loss",
            "loss_making_product",
            "high_product_loss",
            "loss_products",
        ),
    ),
    (
        "loss_making_customers",
        (
            "negative_customer",
            "customer_loss",
            "loss_making_customer",
            "high_customer_loss",
            "loss_customers",
        ),
    ),
    (
        "loss_making_combinations",
        (
            "negative_combination",
            "combination_loss",
            "negative_customer_product",
        ),
    ),
    (
        "low_margin_products",
        (
            "low_margin_product",
        ),
    ),
    (
        "low_margin_customers",
        (
            "low_margin_customer",
        ),
    ),
)

# Insight types that are interchangeable for redundancy clustering.
_TYPE_FAMILIES: dict[str, str] = {
    "growth_decline": "growth_decline",
    "trend": "growth_decline",
    "anomaly": "anomaly",
    "concentration": "concentration",
    "comparison": "comparison",
    "segment_difference": "segment_difference",
    "contribution": "contribution",
    "distribution": "distribution",
    "relationship": "relationship",
    "opportunity": "opportunity",
    "risk": "risk",
    "other": "other",
}


def consolidate_redundant_insights(
    insights: list[Any] | None,
    *,
    suppress: bool = True,
) -> list[dict[str, Any]]:
    """
    Collapse redundant Insights into a single ranked representative.

    When ``suppress`` is True (default), only cluster winners are
    returned. Winners carry a ``redundancy`` block listing suppressed
    siblings. When False, suppressed Insights remain in the list with
    ``redundancy.suppressed = True`` for debugging.
    """

    payloads: list[dict[str, Any]] = []
    for item in insights or []:
        if isinstance(item, dict):
            payloads.append(dict(item))
        elif hasattr(item, "to_dict"):
            serialized = item.to_dict()
            if isinstance(serialized, dict):
                payloads.append(dict(serialized))

    if len(payloads) <= 1:
        if payloads:
            payloads[0]["redundancy"] = _singleton_redundancy(
                payloads[0]
            )
        return payloads

    clusters: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(
        list
    )
    for payload in payloads:
        clusters[redundancy_cluster_key(payload)].append(payload)

    winners: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []

    for cluster in clusters.values():
        ordered = sorted(
            cluster,
            key=lambda item: (
                -_score_total(item),
                -_importance_rank(item),
                str(item.get("insight_id") or ""),
            ),
        )
        winner = dict(ordered[0])
        siblings = ordered[1:]

        winner["redundancy"] = {
            "version": REDUNDANCY_VERSION,
            "cluster_key": _format_cluster_key(
                redundancy_cluster_key(winner)
            ),
            "cluster_size": len(ordered),
            "suppressed": False,
            "suppressed_insight_ids": [
                str(item.get("insight_id") or "")
                for item in siblings
                if item.get("insight_id")
            ],
            "suppressed_rule_ids": [
                str(item.get("rule_id"))
                for item in siblings
                if item.get("rule_id")
            ],
            "related_titles": [
                str(item.get("title") or "").strip()
                for item in siblings
                if str(item.get("title") or "").strip()
            ],
        }
        winners.append(winner)

        if not suppress:
            for sibling in siblings:
                marked = dict(sibling)
                marked["redundancy"] = {
                    "version": REDUNDANCY_VERSION,
                    "cluster_key": winner["redundancy"]["cluster_key"],
                    "cluster_size": len(ordered),
                    "suppressed": True,
                    "kept_insight_id": winner.get("insight_id"),
                    "suppressed_insight_ids": [],
                    "suppressed_rule_ids": [],
                    "related_titles": [],
                }
                suppressed.append(marked)

    result = winners + suppressed
    # Preserve score ordering among winners; suppressed trail if kept.
    result.sort(
        key=lambda item: (
            0 if not (item.get("redundancy") or {}).get("suppressed") else 1,
            -_score_total(item),
            str(item.get("insight_id") or ""),
        )
    )
    return result


def redundancy_cluster_key(insight: dict[str, Any]) -> tuple[str, ...]:
    """
    Deterministic key for Insights that tell the same story.

    Module-local stories keep ``analysis_type`` in the key.
    Cross-cutting themes (e.g. loss-making products emitted by
    both Product Performance and Profitability) intentionally
    ignore analysis/type so the same observation surfaces once.
    """

    analysis_type = _normalize_token(insight.get("analysis_type")) or "unknown"
    insight_type = _normalize_token(insight.get("insight_type")) or "other"
    family = metric_family(
        insight.get("metric"),
        analysis_type,
        rule_id=insight.get("rule_id"),
        title=insight.get("title"),
        finding=insight.get("finding"),
    )
    direction = insight_direction(insight, metric_family_name=family)
    dimensions = dimension_signature(insight.get("dimensions"))

    if _is_cross_module_theme(family):
        return (
            "cross_module",
            family,
            "theme",
            direction,
            dimensions,
        )

    return (
        analysis_type,
        family,
        type_family(insight_type),
        direction,
        dimensions,
    )


def _is_cross_module_theme(family: str) -> bool:
    """Themes that multiple analysis modules routinely restate."""

    return family.startswith("loss_making_") or family.startswith(
        "low_margin_"
    )


def metric_family(
    metric: str | None,
    analysis_type: str = "",
    *,
    rule_id: str | None = None,
    title: str | None = None,
    finding: str | None = None,
) -> str:
    """Map metrics that describe the same quantity / story."""

    text = _normalize_token(metric)
    analysis = _normalize_token(analysis_type)
    rule = _normalize_token(rule_id)
    title_text = _normalize_token(title)
    finding_text = _normalize_token(finding)

    stem = text
    for suffix in _MEASURE_SUFFIXES:
        if stem.endswith(suffix) and len(stem) > len(suffix):
            stem = stem[: -len(suffix)]
            break

    theme_blob = " ".join(
        part
        for part in (stem, text, rule, title_text, finding_text)
        if part
    )
    theme = _match_theme(theme_blob)
    if theme:
        return theme

    if text in _REVENUE_MOMENTUM_METRICS:
        return "revenue_momentum"

    if analysis in {"revenue_trends", "revenue"}:
        if any(
            token in text
            for token in ("growth", "decline", "trend_change", "momentum")
        ):
            return "revenue_momentum"
        if "deviation" in text or "anomaly" in text:
            return "revenue_anomaly"

    # Collapse common change suffixes: foo_growth / foo_change → foo_change.
    for suffix in (
        "_growth",
        "_decline",
        "_increase",
        "_decrease",
        "_change",
        "_delta",
    ):
        if text.endswith(suffix) and len(text) > len(suffix):
            return f"{text[: -len(suffix)]}_change"

    # Count/rate pairs with the same stem tell the same story.
    if stem and stem != text:
        return f"{stem}_level"

    return text or "unknown"


def _match_theme(blob: str) -> str | None:
    for theme, patterns in _THEME_PATTERNS:
        if any(pattern in blob for pattern in patterns):
            return theme
    return None


def type_family(insight_type: str) -> str:
    """Map interchangeable analytical shapes onto one family."""

    text = _normalize_token(insight_type) or "other"
    return _TYPE_FAMILIES.get(text, text)


def insight_direction(
    insight: dict[str, Any],
    *,
    metric_family_name: str | None = None,
) -> str:
    """
    Coarse directional signal: up | down | flat | adverse | na.

    Loss-making / low-margin themes use ``adverse`` so count vs rate
    variants (both positive magnitudes) still collapse together.
    """

    family = metric_family_name or metric_family(
        insight.get("metric"),
        insight.get("analysis_type") or "",
        rule_id=insight.get("rule_id"),
        title=insight.get("title"),
        finding=insight.get("finding"),
    )
    if family.startswith("loss_making_") or family.startswith("low_margin_"):
        return "adverse"

    magnitude = _as_float(insight.get("magnitude"))
    observed = _as_float(insight.get("observed_value"))
    baseline = _as_float(insight.get("baseline"))

    value = magnitude
    if value is None and observed is not None and baseline is not None:
        value = observed - baseline
    if value is None:
        value = observed

    if value is None:
        # Text cues as a weak fallback.
        blob = " ".join(
            [
                str(insight.get("title") or ""),
                str(insight.get("finding") or ""),
            ]
        ).lower()
        if any(
            token in blob
            for token in (
                "declin",
                "decreas",
                "drop",
                "lower",
                "down",
                "fell",
                "fall",
                "negative",
                "loss",
            )
        ):
            return "down"
        if any(
            token in blob
            for token in (
                "growth",
                "increas",
                "rise",
                "rose",
                "up",
                "higher",
                "improv",
                "gain",
            )
        ):
            return "up"
        return "na"

    if abs(value) < 1e-12:
        return "flat"
    return "up" if value > 0 else "down"


def dimension_signature(dimensions: Any) -> str:
    """Stable grain signature so different entities don't collapse."""

    if not dimensions:
        return ""

    if isinstance(dimensions, str):
        parts = [dimensions]
    else:
        parts = [str(item).strip() for item in dimensions if str(item).strip()]

    if not parts:
        return ""

    # Date-only grain is effectively the same for period-level stories.
    normalized = sorted({_normalize_token(part) for part in parts if part})
    if normalized == ["date"] or normalized == ["period"]:
        return "period"

    return "|".join(normalized)


def are_redundant(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return True when two Insights belong to the same redundancy cluster."""

    return redundancy_cluster_key(left) == redundancy_cluster_key(right)


def _singleton_redundancy(insight: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": REDUNDANCY_VERSION,
        "cluster_key": _format_cluster_key(redundancy_cluster_key(insight)),
        "cluster_size": 1,
        "suppressed": False,
        "suppressed_insight_ids": [],
        "suppressed_rule_ids": [],
        "related_titles": [],
    }


def _format_cluster_key(key: tuple[str, ...]) -> str:
    return "::".join(key)


def _importance_rank(insight: dict[str, Any]) -> float:
    importance = normalize_importance(
        insight.get("importance") or insight.get("severity")
    )
    return {"high": 3.0, "medium": 2.0, "low": 1.0}.get(importance, 2.0)


def _score_total(insight: dict[str, Any]) -> float:
    scoring = insight.get("scoring")
    if isinstance(scoring, dict):
        try:
            return float(scoring.get("total") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    text = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    while "__" in text:
        text = text.replace("__", "_")
    return text


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:
        return None
    return numeric
