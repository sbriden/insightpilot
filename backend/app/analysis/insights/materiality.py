"""
Materiality gates for candidate findings and narrative insights.

Technically correct statistics are not automatically business
observations. Small period-over-period moves (e.g. +2.1% revenue)
should not become candidate findings.

Materiality is the gate into Candidate Finding — not Insight.
Insight promotion uses a separate validation + eligibility step:

    Raw Data → Candidate Finding → Validated Finding → Insight
"""

from __future__ import annotations

from typing import Any


# Relative change below this is treated as noise for
# growth / decline / prior-period comparisons.
DEFAULT_MIN_ABS_RATIO = 0.05

# Margin / share gaps vs a benchmark need at least this delta.
DEFAULT_MIN_ABS_RATIO_GAP = 0.02

# Currency opportunities below this are not worth surfacing alone.
DEFAULT_MIN_ABS_CURRENCY = 1000.0

# Count-based risk findings need at least one instance.
DEFAULT_MIN_ABS_COUNT = 1.0

# Rule ids that describe "nothing notable" states.
TRIVIAL_RULE_IDS = frozenset(
    {
        "stable_trend",
    }
)

# Comparisons where the observed value itself is a change rate.
CHANGE_COMPARISONS = frozenset(
    {
        "vs_prior_period",
    }
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if numeric != numeric:  # NaN
        return None

    return numeric


def is_material(
    *,
    observed_value: Any = None,
    baseline: Any = None,
    magnitude: Any = None,
    magnitude_unit: str | None = None,
    comparison: str | None = None,
    metric: str | None = None,
    severity: str | None = None,
    rule_id: str | None = None,
    min_abs_magnitude: float | None = None,
    require_material: bool = True,
) -> bool:
    """
    Return True when a finding is a meaningful business observation.

    When ``require_material`` is False, always returns True.
    """

    if not require_material:
        return True

    # Explicitly uninteresting "all clear / stable" style rules.
    if rule_id in TRIVIAL_RULE_IDS:
        return False

    unit = (magnitude_unit or "").strip().lower()
    comparison_key = (comparison or "").strip().lower()
    metric_key = (metric or "").strip().lower()
    severity_key = (severity or "").strip().lower()

    observed = _as_float(observed_value)
    base = _as_float(baseline)
    mag = _as_float(magnitude)

    # Period-over-period / growth rates: require meaningful move.
    is_change_metric = (
        comparison_key in CHANGE_COMPARISONS
        or "growth" in metric_key
        or metric_key.endswith("_change")
        or metric_key == "trend_change"
    )

    if is_change_metric and unit in ("", "ratio"):
        change = observed if observed is not None else mag
        if change is None:
            return False

        threshold = (
            min_abs_magnitude
            if min_abs_magnitude is not None
            else DEFAULT_MIN_ABS_RATIO
        )
        return abs(change) >= threshold

    if unit == "count":
        count = (
            mag
            if mag is not None
            else observed
        )
        if count is None:
            return False

        threshold = (
            min_abs_magnitude
            if min_abs_magnitude is not None
            else DEFAULT_MIN_ABS_COUNT
        )
        return abs(count) >= threshold

    if unit == "currency":
        amount = (
            mag
            if mag is not None
            else observed
        )
        if amount is None:
            return False

        threshold = (
            min_abs_magnitude
            if min_abs_magnitude is not None
            else DEFAULT_MIN_ABS_CURRENCY
        )
        return abs(amount) >= threshold

    if unit == "ratio" or unit == "":
        # Threshold / benchmark rules: the condition already encodes
        # a business gate. Still drop tiny low-severity gaps.
        gap = mag
        if gap is None and observed is not None and base is not None:
            gap = observed - base

        if comparison_key in {
            "vs_threshold",
            "vs_benchmark",
        }:
            if severity_key in {"medium", "high"}:
                return True

            if gap is None:
                return True

            threshold = (
                min_abs_magnitude
                if min_abs_magnitude is not None
                else DEFAULT_MIN_ABS_RATIO_GAP
            )
            return abs(gap) >= threshold

        # Absolute ratio observations (e.g. share levels).
        if observed is not None:
            if min_abs_magnitude is not None:
                return abs(observed) >= min_abs_magnitude
            return True

        if gap is not None:
            threshold = (
                min_abs_magnitude
                if min_abs_magnitude is not None
                else DEFAULT_MIN_ABS_RATIO_GAP
            )
            return abs(gap) >= threshold

    # Unknown shape — keep rather than drop silently.
    return True
