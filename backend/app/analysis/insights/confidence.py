"""
Confidence in an analytical finding.

Confidence reflects trust in the *finding itself* — data quality
and clarity of the analytical signal — not whether the business
should act on a recommendation, and not how important the
observation is.

Importance (see ``importance.py``) answers "how much does this
matter?" Confidence answers "how sure are we?"

    High importance + high confidence   → clear, material signal
    High importance + medium confidence → still surface; flag uncertainty
    Low importance + high confidence    → trustworthy but may not rank high

Confidence must not be the sole reason an Insight disappears.
Levels (intentionally simple; not a statistical score):

- high   — strong data quality and clear analytical signal
- medium — reasonable signal but limitations exist
- low    — potentially interesting but insufficient evidence
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class FindingConfidence(str, Enum):
    """Confidence in the analytical finding, not the recommended action."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


CONFIDENCE_LEVELS: tuple[str, ...] = (
    FindingConfidence.HIGH.value,
    FindingConfidence.MEDIUM.value,
    FindingConfidence.LOW.value,
)

CONFIDENCE_DESCRIPTIONS: dict[str, str] = {
    FindingConfidence.HIGH.value: (
        "Strong data quality and clear analytical signal"
    ),
    FindingConfidence.MEDIUM.value: (
        "Reasonable signal but limitations exist"
    ),
    FindingConfidence.LOW.value: (
        "Potentially interesting but insufficient evidence"
    ),
}

# Legacy numeric scores (0–1) → categorical levels.
_FLOAT_TO_LEVEL: tuple[tuple[float, str], ...] = (
    (0.85, FindingConfidence.HIGH.value),
    (0.65, FindingConfidence.MEDIUM.value),
    (0.0, FindingConfidence.LOW.value),
)


def normalize_confidence(value: Any = None) -> str:
    """
    Normalize any confidence input to high | medium | low.

    Accepts level strings, legacy 0–1 floats, or None (→ medium).
    """

    if value is None:
        return FindingConfidence.MEDIUM.value

    if isinstance(value, FindingConfidence):
        return value.value

    if isinstance(value, str):
        text = value.strip().lower()
        aliases = {
            "high": FindingConfidence.HIGH.value,
            "medium": FindingConfidence.MEDIUM.value,
            "med": FindingConfidence.MEDIUM.value,
            "low": FindingConfidence.LOW.value,
            "strong": FindingConfidence.HIGH.value,
            "moderate": FindingConfidence.MEDIUM.value,
            "weak": FindingConfidence.LOW.value,
        }
        if text in aliases:
            return aliases[text]

        # Numeric string leftover from older payloads.
        try:
            value = float(text)
        except ValueError:
            return FindingConfidence.MEDIUM.value

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return FindingConfidence.MEDIUM.value

    if numeric > 1.0 and numeric <= 100.0:
        numeric = numeric / 100.0

    for threshold, level in _FLOAT_TO_LEVEL:
        if numeric >= threshold:
            return level

    return FindingConfidence.LOW.value


def resolve_confidence(
    facts: dict | None = None,
    explicit: Any = None,
    *,
    source_columns: list[str] | None = None,
    evidence_metrics: list | None = None,
) -> str:
    """
    Deterministic finding confidence (high / medium / low).

    Assesses analytical signal strength and basic data support —
    never recommendation actionability, and never business importance.
    """

    facts = facts or {}

    if callable(explicit):
        explicit = explicit(facts)

    if explicit is not None:
        return normalize_confidence(explicit)

    sample_size = _sample_size(facts)
    columns = [
        str(column).strip()
        for column in (source_columns or [])
        if str(column).strip()
    ]
    metrics = list(evidence_metrics or [])

    # Clear signal + solid support → high.
    if sample_size is not None and sample_size >= 30 and columns:
        if metrics or sample_size >= 100:
            return FindingConfidence.HIGH.value
        return FindingConfidence.MEDIUM.value

    # Modest sample or missing lineage → medium / low.
    if sample_size is not None and sample_size >= 10:
        if columns:
            return FindingConfidence.MEDIUM.value
        return FindingConfidence.LOW.value

    if sample_size is not None and sample_size >= 3:
        return FindingConfidence.LOW.value

    # No sample-size cue: lean on evidence / columns only.
    if columns and metrics:
        return FindingConfidence.MEDIUM.value

    if columns or metrics:
        return FindingConfidence.LOW.value

    return FindingConfidence.MEDIUM.value


def _sample_size(facts: dict) -> float | None:
    sample_keys = (
        "total_customers",
        "entity_count",
        "product_count",
        "period_count",
        "row_count",
        "opportunity_count",
    )

    for key in sample_keys:
        if key not in facts:
            continue

        try:
            count = float(facts[key])
        except (TypeError, ValueError):
            continue

        if count == count:  # not NaN
            return count

    return None


# Backward-compatible alias used by older call sites / tests.
def _clamp_confidence(value: Any) -> str:
    return normalize_confidence(value)
