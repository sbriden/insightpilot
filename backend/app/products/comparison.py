"""
Compare key metrics between product versions.

Only meaningful changes become structured findings.
"""

from __future__ import annotations

import re
from typing import Any


# Relative change of at least 5% is meaningful
# when the prior value is non-zero.
RELATIVE_THRESHOLD = 0.05

# Absolute change thresholds by display unit.
ABSOLUTE_CURRENCY = 1.0
ABSOLUTE_PERCENT = 1.0
ABSOLUTE_COUNT = 1.0


def _parse_numeric(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if not text or text in {"—", "-", "N/A", "n/a"}:
        return None

    # Keep digits, decimal point, and minus.
    cleaned = re.sub(
        r"[^0-9.\-]",
        "",
        text.replace(",", ""),
    )

    if cleaned in {"", "-", ".", "-."}:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _detect_unit(
    name: str,
    value: Any,
) -> str:

    text = f"{name} {value}".lower()

    if "$" in text or "revenue" in text or "profit" in text:
        return "currency"

    if "%" in text or "share" in text or "penetration" in text:
        return "percent"

    return "count"


def _format_value(
    value: float | None,
    unit: str,
) -> str:

    if value is None:
        return "—"

    if unit == "currency":
        return f"${value:,.0f}"

    if unit == "percent":
        return f"{value:.1f}%"

    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"

    return f"{value:,.2f}"


def _is_meaningful(
    previous: float,
    current: float,
    unit: str,
) -> bool:

    delta = current - previous

    if abs(delta) < 1e-12:
        return False

    if previous == 0:
        return abs(delta) >= (
            ABSOLUTE_CURRENCY
            if unit == "currency"
            else ABSOLUTE_PERCENT
            if unit == "percent"
            else ABSOLUTE_COUNT
        )

    relative = abs(delta / previous)

    if relative >= RELATIVE_THRESHOLD:
        return True

    if unit == "currency":
        return abs(delta) >= ABSOLUTE_CURRENCY * 100

    if unit == "percent":
        return abs(delta) >= ABSOLUTE_PERCENT

    return abs(delta) >= ABSOLUTE_COUNT


def _severity(
    previous: float,
    current: float,
) -> str:

    if previous == 0:
        return "medium"

    relative = abs(
        (current - previous) / previous
    )

    if relative >= 0.25:
        return "high"

    if relative >= 0.10:
        return "medium"

    return "low"


def _direction(
    previous: float,
    current: float,
) -> str:

    if current > previous:
        return "increase"

    if current < previous:
        return "decrease"

    return "unchanged"


def compare_product_metrics(
    *,
    previous_metrics: list[dict],
    current_metrics: list[dict],
    previous_version: int,
    current_version: int,
) -> dict | None:
    """
    Build a structured change summary.

    Returns None when there is nothing to compare.
    """

    if not previous_metrics:
        return None

    previous_by_id = {
        str(metric.get("id")): metric
        for metric in previous_metrics
        if isinstance(metric, dict)
        and metric.get("id")
    }

    findings = []

    for metric in current_metrics:

        if not isinstance(metric, dict):
            continue

        metric_id = metric.get("id")

        if not metric_id:
            continue

        prior = previous_by_id.get(
            str(metric_id)
        )

        if not prior:
            continue

        previous_value = _parse_numeric(
            prior.get("value")
        )

        current_value = _parse_numeric(
            metric.get("value")
        )

        if (
            previous_value is None
            or current_value is None
        ):
            continue

        unit = _detect_unit(
            str(
                metric.get("name")
                or prior.get("name")
                or ""
            ),
            metric.get("value"),
        )

        if not _is_meaningful(
            previous_value,
            current_value,
            unit,
        ):
            continue

        delta = current_value - previous_value

        relative = (
            None
            if previous_value == 0
            else (delta / previous_value) * 100
        )

        direction = _direction(
            previous_value,
            current_value,
        )

        name = (
            metric.get("name")
            or prior.get("name")
            or str(metric_id)
        )

        if relative is None:
            message = (
                f"{name} moved from "
                f"{_format_value(previous_value, unit)} "
                f"to {_format_value(current_value, unit)}."
            )
        else:
            message = (
                f"{name} "
                f"{'increased' if direction == 'increase' else 'decreased'} "
                f"by {abs(relative):.1f}% "
                f"({_format_value(previous_value, unit)} → "
                f"{_format_value(current_value, unit)})."
            )

        findings.append(
            {
                "id": f"change:{metric_id}",
                "metric_id": metric_id,
                "metric_name": name,
                "direction": direction,
                "severity": _severity(
                    previous_value,
                    current_value,
                ),
                "previous_value": previous_value,
                "current_value": current_value,
                "absolute_change": delta,
                "relative_change_percent": (
                    None
                    if relative is None
                    else round(relative, 2)
                ),
                "unit": unit,
                "title": (
                    f"{name} "
                    f"{'up' if direction == 'increase' else 'down'}"
                ),
                "message": message,
            }
        )

    findings.sort(
        key=lambda item: (
            {
                "high": 0,
                "medium": 1,
                "low": 2,
            }.get(item["severity"], 3),
            -abs(item["absolute_change"]),
        )
    )

    increases = sum(
        1
        for item in findings
        if item["direction"] == "increase"
    )

    decreases = sum(
        1
        for item in findings
        if item["direction"] == "decrease"
    )

    if findings:
        overview = (
            f"Version {current_version} vs "
            f"version {previous_version}: "
            f"{len(findings)} meaningful metric "
            f"change{'s' if len(findings) != 1 else ''} "
            f"({increases} up, {decreases} down)."
        )
    else:
        overview = (
            f"Version {current_version} vs "
            f"version {previous_version}: "
            f"no meaningful metric changes detected."
        )

    return {
        "previous_version": previous_version,
        "current_version": current_version,
        "has_meaningful_changes": bool(findings),
        "overview": overview,
        "finding_count": len(findings),
        "increases": increases,
        "decreases": decreases,
        "findings": findings,
    }
