"""
Insight tiers for prioritized surfacing.

Interesting ≠ important. Tiers decide what the user should see
first — independent of Confidence, complementary to Importance.

    Tier 1 — Critical
        Insights the user should almost certainly see.
        Major revenue decline, significant profitability issue,
        extreme customer concentration, major operational anomaly,
        material customer churn.

    Tier 2 — Important
        Worth surfacing, but less urgent.
        Strong regional differences, product growth opportunities,
        meaningful segment behavior, emerging trends.

    Tier 3 — Supporting
        Useful for exploration; must not dominate initial results.
        Minor trends, descriptive statistics, small differences,
        secondary correlations.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from .importance import normalize_importance
from .scoring import classify_business_signal, _has_token_hint


class InsightTier(str, Enum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    SUPPORTING = "supporting"


# Display / API order (Tier 1 → 3).
TIER_LEVELS: tuple[str, ...] = (
    InsightTier.CRITICAL.value,
    InsightTier.IMPORTANT.value,
    InsightTier.SUPPORTING.value,
)

TIER_LABELS: dict[str, str] = {
    InsightTier.CRITICAL.value: "Tier 1 — Critical",
    InsightTier.IMPORTANT.value: "Tier 2 — Important",
    InsightTier.SUPPORTING.value: "Tier 3 — Supporting",
}

TIER_DESCRIPTIONS: dict[str, str] = {
    InsightTier.CRITICAL.value: (
        "Insights the user should almost certainly see"
    ),
    InsightTier.IMPORTANT.value: (
        "Worth surfacing, but less urgent"
    ),
    InsightTier.SUPPORTING.value: (
        "Useful for exploration; should not dominate initial results"
    ),
}

# Sort key: Critical first.
TIER_SORT_ORDER: dict[str, int] = {
    InsightTier.CRITICAL.value: 0,
    InsightTier.IMPORTANT.value: 1,
    InsightTier.SUPPORTING.value: 2,
}

_CRITICAL_RULE_HINTS = (
    "high_concentration",
    "single_customer",
    "revenue_decline",
    "declining_trend",
    "revenue_drop",
    "revenue_anomaly",
    "negative_product",
    "negative_customer",
    "high_negative",
    "high_product_loss",
    "high_customer_loss",
    "churn",
    "margin_gap",
    "profit_improvement",
)

_CRITICAL_TYPE_HINTS = frozenset(
    {
        "risk",
        "anomaly",
        "concentration",
    }
)

_IMPORTANT_RULE_HINTS = (
    "cross_sell",
    "opportunity",
    "growth",
    "segment",
    "regional",
    "penetration",
    "moderate_concentration",
)

_SUPPORTING_RULE_HINTS = (
    "diversified",
    "low_concentration",
    "stable",
    "broad_adoption",
    "average",
    "mean",
    "per_transaction",
    "modest",
    "positive_trend",
    "accelerating_trend",
    "revenue_growth",
    "product_diversification",
    "customer_diversification",
)


def normalize_tier(value: Any = None) -> str:
    """Normalize any tier input to critical | important | supporting."""

    if value is None:
        return InsightTier.IMPORTANT.value

    if isinstance(value, InsightTier):
        return value.value

    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "critical": InsightTier.CRITICAL.value,
        "tier_1": InsightTier.CRITICAL.value,
        "tier1": InsightTier.CRITICAL.value,
        "1": InsightTier.CRITICAL.value,
        "important": InsightTier.IMPORTANT.value,
        "tier_2": InsightTier.IMPORTANT.value,
        "tier2": InsightTier.IMPORTANT.value,
        "2": InsightTier.IMPORTANT.value,
        "supporting": InsightTier.SUPPORTING.value,
        "tier_3": InsightTier.SUPPORTING.value,
        "tier3": InsightTier.SUPPORTING.value,
        "3": InsightTier.SUPPORTING.value,
        "exploratory": InsightTier.SUPPORTING.value,
        "secondary": InsightTier.SUPPORTING.value,
    }
    return aliases.get(text, InsightTier.IMPORTANT.value)


def resolve_insight_tier(insight: Any = None) -> str:
    """
    Deterministically assign Tier 1 / 2 / 3 for an Insight-like object.

    Uses business-signal classification, importance, type, magnitude,
    and rule/title cues. Does not consult Confidence as a gate.
    """

    data = _as_mapping(insight)
    signal = classify_business_signal(data)
    importance = normalize_importance(
        data.get("importance") or data.get("severity") or data.get("priority")
    )
    insight_type = _normalize_token(data.get("insight_type")) or "other"
    blob = _cue_blob(data)

    # Critical first — never let a descriptive mis-tag bury a major finding.
    if _is_critical(
        data,
        signal=signal,
        importance=importance,
        insight_type=insight_type,
        blob=blob,
    ):
        return InsightTier.CRITICAL.value

    if _is_supporting(
        data,
        signal=signal,
        importance=importance,
        blob=blob,
    ):
        return InsightTier.SUPPORTING.value

    if _is_important(
        data,
        signal=signal,
        importance=importance,
        insight_type=insight_type,
        blob=blob,
    ):
        return InsightTier.IMPORTANT.value

    if signal == "descriptive" or importance == "low":
        return InsightTier.SUPPORTING.value

    return InsightTier.IMPORTANT.value


def tier_sort_key(tier: Any) -> int:
    """Lower sorts first (Critical → Important → Supporting)."""

    return TIER_SORT_ORDER.get(normalize_tier(tier), 1)


def _is_critical(
    data: dict[str, Any],
    *,
    signal: str,
    importance: str,
    insight_type: str,
    blob: str,
) -> bool:
    # Allow critical even if signal was tagged descriptive due to metric naming.
    if _has_token_hint(blob, _CRITICAL_RULE_HINTS):
        if importance in {"high", "medium"}:
            return True

    # Extreme customer concentration (e.g. top 10 ≥ 40%).
    if insight_type == "concentration" and _share_at_least(data, 0.40):
        return True

    # Major revenue / growth decline.
    if insight_type in {"growth_decline", "trend"} and _is_major_decline(data):
        return True

    # Significant profitability / loss issue.
    if _is_major_profitability_issue(data, blob=blob):
        return True

    # Major operational anomaly or material churn.
    if insight_type == "anomaly" and importance in {"high", "medium"}:
        return True
    if "churn" in blob and importance in {"high", "medium"}:
        return True

    if (
        signal == "business"
        and importance == "high"
        and insight_type in _CRITICAL_TYPE_HINTS
    ):
        return True

    return False


def _is_important(
    data: dict[str, Any],
    *,
    signal: str,
    importance: str,
    insight_type: str,
    blob: str,
) -> bool:
    if signal == "business" and importance in {"high", "medium"}:
        return True

    if _has_token_hint(blob, _IMPORTANT_RULE_HINTS):
        return importance != "low"

    if insight_type in {
        "opportunity",
        "segment_difference",
        "contribution",
        "growth_decline",
        "relationship",
    }:
        return importance != "low"

    if insight_type == "concentration" and _share_at_least(data, 0.25):
        return True

    if insight_type in {"trend", "comparison"} and importance == "medium":
        return True

    return False


def _is_supporting(
    data: dict[str, Any],
    *,
    signal: str,
    importance: str,
    blob: str,
) -> bool:
    if signal == "descriptive":
        return True

    # Prefer rule/title cues for all-clear / minor notes (not metric names
    # like overall_revenue_growth, which also power decline findings).
    rule_title = " ".join(
        _normalize_token(data.get(key))
        for key in ("rule_id", "title")
        if data.get(key) is not None
    )
    if _has_token_hint(rule_title, _SUPPORTING_RULE_HINTS):
        return True

    if importance == "low":
        return True

    # Small differences / minor moves on soft analytical shapes.
    if _is_minor_magnitude(data):
        insight_type = _normalize_token(data.get("insight_type"))
        if insight_type in {"trend", "comparison", "distribution", "other"}:
            return True

    return False

def _is_major_decline(data: dict[str, Any]) -> bool:
    value = _signed_effect(data)
    if value is None:
        return False
    # ≤ -15% change, or high-importance decline with ≥ 10% move.
    if value <= -0.15:
        return True
    importance = normalize_importance(
        data.get("importance") or data.get("severity")
    )
    return importance == "high" and value <= -0.10


def _is_major_profitability_issue(data: dict[str, Any], *, blob: str) -> bool:
    if not any(
        token in blob
        for token in (
            "negative_product",
            "negative_customer",
            "loss",
            "margin_gap",
            "unprofit",
        )
    ):
        return False

    importance = normalize_importance(
        data.get("importance") or data.get("severity")
    )
    if importance == "high":
        return True

    unit = str(data.get("magnitude_unit") or "").strip().lower()
    observed = _as_float(data.get("observed_value"))
    magnitude = _as_float(data.get("magnitude"))

    if unit == "ratio" and observed is not None and observed >= 0.20:
        return True
    if unit == "count" and (observed or magnitude or 0) >= 20:
        return True
    if unit == "currency" and abs(magnitude or observed or 0) >= 25_000:
        return True

    return False


def _share_at_least(data: dict[str, Any], threshold: float) -> bool:
    observed = _as_float(data.get("observed_value"))
    if observed is None:
        return False
    share = observed / 100.0 if observed > 1.5 else observed
    return share >= threshold


def _is_minor_magnitude(data: dict[str, Any]) -> bool:
    value = _signed_effect(data)
    if value is None:
        unit = str(data.get("magnitude_unit") or "").strip().lower()
        amount = abs(_as_float(data.get("magnitude")) or 0.0)
        if unit == "currency":
            return amount < 5_000
        if unit == "count":
            return amount < 5
        return False
    return abs(value) < 0.05


def _signed_effect(data: dict[str, Any]) -> float | None:
    magnitude = _as_float(data.get("magnitude"))
    observed = _as_float(data.get("observed_value"))
    baseline = _as_float(data.get("baseline"))
    unit = str(data.get("magnitude_unit") or "").strip().lower()

    value = magnitude
    if value is None and observed is not None and baseline is not None:
        value = observed - baseline
    if value is None:
        value = observed
    if value is None:
        return None

    if unit == "percent" or abs(value) > 1.5:
        value = value / 100.0
    return value


def _cue_blob(data: dict[str, Any]) -> str:
    return " ".join(
        _normalize_token(data.get(key))
        for key in ("rule_id", "metric", "title", "finding", "insight_type")
        if data.get(key) is not None
    )


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(value)
    return {}


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
