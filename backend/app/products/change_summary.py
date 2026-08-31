from __future__ import annotations

from typing import Any


def merge_change_summaries(
    metric_summary: dict | None,
    data_quality_summary: dict | None,
) -> dict | None:

    if (
        not metric_summary
        and not data_quality_summary
    ):
        return None

    if (
        metric_summary
        and not data_quality_summary
    ):
        return {
            **metric_summary,

            "data_quality_overview": (
                "No prior data-quality baseline "
                "was available for comparison."
            ),

            "data_quality_finding_count": 0,

            "data_quality_findings": [],
        }

    if (
        data_quality_summary
        and not metric_summary
    ):
        return {
            "previous_version": (
                data_quality_summary[
                    "previous_version"
                ]
            ),

            "current_version": (
                data_quality_summary[
                    "current_version"
                ]
            ),

            "has_meaningful_changes": (
                data_quality_summary[
                    "has_meaningful_changes"
                ]
            ),

            "overview": (
                data_quality_summary[
                    "overview"
                ]
            ),

            "finding_count": 0,

            "increases": 0,

            "decreases": 0,

            "findings": [],

            "data_quality_overview": (
                data_quality_summary[
                    "overview"
                ]
            ),

            "data_quality_finding_count": (
                data_quality_summary[
                    "finding_count"
                ]
            ),

            "data_quality_findings": (
                data_quality_summary[
                    "findings"
                ]
            ),
        }

    metric_findings = (
        metric_summary.get("findings")
        or []
    )

    data_quality_findings = (
        data_quality_summary.get(
            "findings"
        )
        or []
    )

    has_changes = bool(
        metric_findings
        or data_quality_findings
    )

    overview_parts = []

    if metric_findings:
        overview_parts.append(
            f"{len(metric_findings)} metric "
            f"change{'s' if len(metric_findings) != 1 else ''}"
        )

    if data_quality_findings:
        overview_parts.append(
            f"{len(data_quality_findings)} data-quality "
            f"change{'s' if len(data_quality_findings) != 1 else ''}"
        )

    if overview_parts:
        overview = (
            f"Version {metric_summary['current_version']} vs "
            f"version {metric_summary['previous_version']}: "
            + " and ".join(overview_parts)
            + "."
        )
    else:
        overview = (
            f"Version {metric_summary['current_version']} vs "
            f"version {metric_summary['previous_version']}: "
            "no meaningful changes detected."
        )

    return {
        "previous_version": (
            metric_summary["previous_version"]
        ),

        "current_version": (
            metric_summary["current_version"]
        ),

        "has_meaningful_changes": has_changes,

        "overview": overview,

        "finding_count": len(metric_findings),

        "increases": metric_summary.get(
            "increases",
            0,
        ),

        "decreases": metric_summary.get(
            "decreases",
            0,
        ),

        "findings": metric_findings,

        "data_quality_overview": (
            data_quality_summary.get(
                "overview"
            )
        ),

        "data_quality_finding_count": len(
            data_quality_findings
        ),

        "data_quality_findings": (
            data_quality_findings
        ),
    }
