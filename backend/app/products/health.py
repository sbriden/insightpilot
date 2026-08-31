from __future__ import annotations

from typing import Any


HEALTHY = "healthy"
WARNING = "warning"
CRITICAL = "critical"


def _count_insights_by_priority(
    insights: list[Any],
    priorities: set[str],
) -> int:

    count = 0

    for insight in insights:

        if isinstance(
            insight,
            dict,
        ):
            priority = (
                str(
                    insight.get("priority")
                    or insight.get("severity")
                    or "low"
                )
                .strip()
                .lower()
            )
        else:
            priority = (
                str(
                    getattr(
                        insight,
                        "priority",
                        None,
                    )
                    or getattr(
                        insight,
                        "severity",
                        None,
                    )
                    or "low"
                )
                .strip()
                .lower()
            )

        if priority in priorities:
            count += 1

    return count


def _change_has_high_severity(
    change_summary: dict | None,
) -> bool:

    if not isinstance(
        change_summary,
        dict,
    ):
        return False

    for finding in (
        change_summary.get("findings")
        or []
    ):

        if not isinstance(
            finding,
            dict,
        ):
            continue

        severity = (
            str(
                finding.get("severity")
                or "low"
            )
            .strip()
            .lower()
        )

        if severity == "high":
            return True

    return False


def assess_product_health(
    *,
    can_analyze: bool,
    required_coverage: float,
    overall_coverage: float,
    data_quality_score: float | None,
    missing_percentage: float | None,
    status: str,
    analysis_count: int,
    expected_analysis_count: int,
    insights: list[Any] | None = None,
    change_summary: dict | None = None,
) -> dict[str, Any]:

    insights = insights or []

    quality_score = (
        float(data_quality_score)
        if data_quality_score is not None
        else None
    )

    missing_pct = (
        float(missing_percentage)
        if missing_percentage is not None
        else None
    )

    high_insights = _count_insights_by_priority(
        insights,
        {"high", "critical"},
    )

    notable_insights = _count_insights_by_priority(
        insights,
        {"high", "critical", "medium", "warning"},
    )

    required_fields_present = (
        can_analyze
        and required_coverage >= 100
    )

    data_quality_acceptable = (
        quality_score is None
        or quality_score >= 70
    ) and (
        missing_pct is None
        or missing_pct < 15
    )

    no_major_anomalies = (
        high_insights == 0
        and not _change_has_high_severity(
            change_summary
        )
    )

    product_generated_successfully = (
        can_analyze
        and analysis_count > 0
        and status != "limited"
    )

    reasons: list[str] = []
    status_level = HEALTHY

    if not required_fields_present:

        status_level = CRITICAL

        reasons.append(
            "Required fields are missing for "
            "this product."
        )

    if (
        quality_score is not None
        and quality_score < 50
    ):

        status_level = CRITICAL

        reasons.append(
            "Dataset quality score indicates a "
            "major data-quality failure."
        )

    if (
        missing_pct is not None
        and missing_pct >= 30
    ):

        status_level = CRITICAL

        reasons.append(
            "Missing data exceeds acceptable "
            "limits for reliable analysis."
        )

    if (
        can_analyze
        and expected_analysis_count > 0
        and analysis_count == 0
    ):

        status_level = CRITICAL

        reasons.append(
            "The product could not generate "
            "its supporting analyses."
        )

    if status_level != CRITICAL:

        if (
            quality_score is not None
            and 50 <= quality_score < 70
        ):

            status_level = WARNING

            reasons.append(
                "Data quality has degraded below "
                "the preferred threshold."
            )

        if (
            missing_pct is not None
            and 15 <= missing_pct < 30
        ):

            status_level = WARNING

            reasons.append(
                "Missing values may affect "
                "analysis reliability."
            )

        if (
            isinstance(
                change_summary,
                dict,
            )
            and change_summary.get(
                "has_meaningful_changes"
            )
        ):

            finding_count = int(
                change_summary.get(
                    "finding_count"
                )
                or 0
            )

            if (
                finding_count >= 2
                or _change_has_high_severity(
                    change_summary
                )
            ):

                status_level = WARNING

                reasons.append(
                    "Significant metric changes "
                    "were detected since the "
                    "previous version."
                )

        if (
            required_fields_present
            and overall_coverage < 80
        ):

            status_level = WARNING

            reasons.append(
                "Optional fields are missing, "
                "limiting product coverage."
            )

        if (
            high_insights > 0
            or notable_insights >= 3
        ):

            status_level = WARNING

            reasons.append(
                "Notable anomalies were "
                "identified in product insights."
            )

        if (
            expected_analysis_count > 0
            and 0 < analysis_count < expected_analysis_count
        ):

            status_level = WARNING

            reasons.append(
                "Some expected analyses did not "
                "complete for this product."
            )

        if status == "partial":

            if status_level != WARNING:
                status_level = WARNING

            reasons.append(
                "Field coverage is only partial "
                "for this product."
            )

    if (
        status_level == HEALTHY
        and required_fields_present
        and data_quality_acceptable
        and no_major_anomalies
        and product_generated_successfully
    ):

        reasons = [
            "Required fields are present.",

            "Data quality is acceptable.",

            "No major anomalies were detected.",

            "The product was generated successfully.",
        ]

    labels = {
        HEALTHY: "Healthy",
        WARNING: "Warning",
        CRITICAL: "Critical",
    }

    summaries = {
        HEALTHY: (
            "This product is ready to use with "
            "acceptable data quality."
        ),
        WARNING: (
            "This product is usable, but review "
            "the flagged issues before acting "
            "on results."
        ),
        CRITICAL: (
            "This product cannot be relied on "
            "until the underlying data issues "
            "are resolved."
        ),
    }

    return {
        "status": status_level,

        "label": labels[status_level],

        "summary": summaries[status_level],

        "reasons": reasons[:6],

        "checks": {
            "required_fields_present": (
                required_fields_present
            ),

            "data_quality_acceptable": (
                data_quality_acceptable
            ),

            "no_major_anomalies": (
                no_major_anomalies
            ),

            "product_generated_successfully": (
                product_generated_successfully
            ),
        },
    }
