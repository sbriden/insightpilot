"""
Business importance of a finding or Insight.

Importance is how much the observation matters to the business.
It is independent of Confidence (how strong the evidence is).

Example:

    Revenue declined 18% in the Northeast.
      Importance: High   Confidence: High

    Customers in Segment X appear to have unusually high churn.
      Importance: High   Confidence: Medium

Medium (or even low) confidence must not erase a high-importance
Insight. Confidence may lower ranking weight; it must not be the
sole gate for whether the Insight surfaces.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from .normalize import normalize_priority


class FindingImportance(str, Enum):
    """How significant the finding is to the business."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


IMPORTANCE_LEVELS: tuple[str, ...] = (
    FindingImportance.HIGH.value,
    FindingImportance.MEDIUM.value,
    FindingImportance.LOW.value,
)

IMPORTANCE_DESCRIPTIONS: dict[str, str] = {
    FindingImportance.HIGH.value: (
        "Material business significance — worth attention"
    ),
    FindingImportance.MEDIUM.value: (
        "Notable but not necessarily urgent"
    ),
    FindingImportance.LOW.value: (
        "Limited business significance on its own"
    ),
}


def normalize_importance(value: Any = None) -> str:
    """
    Normalize any importance input to high | medium | low.

    Accepts level strings, legacy severity/priority labels,
    or None (→ medium).
    """

    if value is None:
        return FindingImportance.MEDIUM.value

    if isinstance(value, FindingImportance):
        return value.value

    if isinstance(value, str):
        text = value.strip().lower()
        aliases = {
            "high": FindingImportance.HIGH.value,
            "medium": FindingImportance.MEDIUM.value,
            "med": FindingImportance.MEDIUM.value,
            "low": FindingImportance.LOW.value,
            "critical": FindingImportance.HIGH.value,
            "warning": FindingImportance.MEDIUM.value,
            "info": FindingImportance.LOW.value,
            "success": FindingImportance.LOW.value,
            "significant": FindingImportance.HIGH.value,
            "material": FindingImportance.HIGH.value,
            "notable": FindingImportance.MEDIUM.value,
            "minor": FindingImportance.LOW.value,
        }
        if text in aliases:
            return aliases[text]

    # Severity / priority historically stood in for importance.
    return normalize_priority(str(value) if value is not None else None)


def resolve_importance(
    *,
    explicit: Any = None,
    severity: Any = None,
    priority: Any = None,
    insight_type: str | None = None,
    magnitude: Any = None,
    magnitude_unit: str | None = None,
) -> str:
    """
    Deterministic business importance (high / medium / low).

    Prefers an explicit importance label. Falls back to severity /
    priority (legacy), then light type / magnitude cues.
    Never consults Confidence — the two concepts stay independent.
    """

    if explicit is not None and str(explicit).strip():
        return normalize_importance(explicit)

    if severity is not None and str(severity).strip():
        return normalize_importance(severity)

    if priority is not None and str(priority).strip():
        return normalize_importance(priority)

    type_key = str(insight_type or "").strip().lower()
    type_defaults = {
        "risk": FindingImportance.HIGH.value,
        "anomaly": FindingImportance.HIGH.value,
        "concentration": FindingImportance.HIGH.value,
        "opportunity": FindingImportance.MEDIUM.value,
        "growth_decline": FindingImportance.MEDIUM.value,
        "contribution": FindingImportance.MEDIUM.value,
        "segment_difference": FindingImportance.MEDIUM.value,
        "comparison": FindingImportance.MEDIUM.value,
        "relationship": FindingImportance.MEDIUM.value,
        "distribution": FindingImportance.LOW.value,
        "trend": FindingImportance.LOW.value,
        "other": FindingImportance.LOW.value,
    }
    if type_key in type_defaults:
        # Large currency / share moves can still elevate importance.
        elevated = _magnitude_suggests_high(
            magnitude=magnitude,
            magnitude_unit=magnitude_unit,
        )
        if elevated and type_defaults[type_key] != FindingImportance.HIGH.value:
            return FindingImportance.HIGH.value
        return type_defaults[type_key]

    if _magnitude_suggests_high(
        magnitude=magnitude,
        magnitude_unit=magnitude_unit,
    ):
        return FindingImportance.HIGH.value

    return FindingImportance.MEDIUM.value


def _magnitude_suggests_high(
    *,
    magnitude: Any,
    magnitude_unit: str | None,
) -> bool:
    try:
        abs_mag = abs(float(magnitude))
    except (TypeError, ValueError):
        return False

    unit = (magnitude_unit or "").strip().lower()
    if unit == "currency":
        return abs_mag >= 25_000
    if unit == "count":
        return abs_mag >= 20
    if unit in {"ratio", "percent", ""}:
        if unit == "percent" or abs_mag > 1.5:
            abs_mag = abs_mag / 100.0
        return abs_mag >= 0.15
    return False
