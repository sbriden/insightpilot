from __future__ import annotations

from typing import Any


RELATIVE_THRESHOLD = 0.05
MISSING_POINTS_THRESHOLD = 2.0
QUALITY_POINTS_THRESHOLD = 3.0
DUPLICATE_RATE_THRESHOLD = 0.5


def _severity_from_relative(
    relative: float,
) -> str:

    magnitude = abs(relative)

    if magnitude >= 0.25:
        return "high"

    if magnitude >= 0.10:
        return "medium"

    return "low"


def _format_count(
    value: int,
) -> str:

    return f"{value:,}"


def _format_percent(
    value: float,
) -> str:

    return f"{value:.1f}%"


def _meaningful_relative_change(
    previous: float,
    current: float,
) -> bool:

    if previous == current:
        return False

    if previous == 0:
        return abs(current) > 0

    return abs(
        (current - previous) / previous
    ) >= RELATIVE_THRESHOLD


def _append_finding(
    findings: list[dict[str, Any]],
    *,
    finding_id: str,
    severity: str,
    title: str,
    message: str,
    direction: str,
) -> None:

    findings.append(
        {
            "id": finding_id,

            "category": "data_quality",

            "severity": severity,

            "title": title,

            "message": message,

            "direction": direction,
        }
    )


def compare_data_quality(
    *,
    previous_snapshot: dict | None,
    current_snapshot: dict,
    previous_version: int,
    current_version: int,
) -> dict[str, Any] | None:

    if not previous_snapshot:
        return None

    findings: list[dict[str, Any]] = []

    previous_rows = int(
        previous_snapshot.get("row_count")
        or 0
    )

    current_rows = int(
        current_snapshot.get("row_count")
        or 0
    )

    if (
        previous_rows != current_rows
        and _meaningful_relative_change(
            float(previous_rows),
            float(current_rows),
        )
    ):

        delta = current_rows - previous_rows

        relative = (
            None
            if previous_rows == 0
            else (delta / previous_rows) * 100
        )

        direction = (
            "increase"
            if delta > 0
            else "decrease"
        )

        if relative is None:
            message = (
                f"Row count changed from "
                f"{_format_count(previous_rows)} "
                f"to {_format_count(current_rows)}."
            )
        else:
            message = (
                f"Row count "
                f"{'increased' if delta > 0 else 'decreased'} "
                f"from {_format_count(previous_rows)} "
                f"to {_format_count(current_rows)} "
                f"({relative:+.1f}%). This may shift "
                "aggregate metrics and trend comparisons."
            )

        _append_finding(
            findings,

            finding_id="dq:row_count",

            severity=_severity_from_relative(
                0 if relative is None else relative / 100
            ),

            title=(
                "Dataset size "
                f"{'grew' if delta > 0 else 'shrank'}"
            ),

            message=message,

            direction=direction,
        )

    previous_columns = int(
        previous_snapshot.get(
            "column_count"
        )
        or 0
    )

    current_columns = int(
        current_snapshot.get(
            "column_count"
        )
        or 0
    )

    if previous_columns != current_columns:

        delta = (
            current_columns
            - previous_columns
        )

        _append_finding(
            findings,

            finding_id="dq:column_count",

            severity=(
                "medium"
                if abs(delta) == 1
                else "high"
            ),

            title=(
                "Column count changed"
            ),

            message=(
                f"The dataset now has "
                f"{current_columns} columns "
                f"instead of {previous_columns}, "
                "which changes the available "
                "analysis surface."
            ),

            direction=(
                "increase"
                if delta > 0
                else "decrease"
            ),
        )

    previous_missing = float(
        previous_snapshot.get(
            "missing_percentage"
        )
        or 0
    )

    current_missing = float(
        current_snapshot.get(
            "missing_percentage"
        )
        or 0
    )

    missing_delta = (
        current_missing - previous_missing
    )

    if abs(missing_delta) >= (
        MISSING_POINTS_THRESHOLD
    ) or (
        previous_missing > 0
        and abs(
            missing_delta / previous_missing
        )
        >= 0.10
    ):

        direction = (
            "increase"
            if missing_delta > 0
            else "decrease"
        )

        _append_finding(
            findings,

            finding_id="dq:missing_percentage",

            severity=(
                "high"
                if missing_delta >= 5
                else "medium"
                if missing_delta >= 2
                else "low"
            ),

            title=(
                "Missing values "
                f"{'increased' if missing_delta > 0 else 'decreased'}"
            ),

            message=(
                f"Null rate moved from "
                f"{_format_percent(previous_missing)} "
                f"to {_format_percent(current_missing)}. "
                + (
                    "More incomplete records may "
                    "reduce analysis reliability."
                    if missing_delta > 0
                    else "Fewer missing values should "
                    "improve analysis reliability."
                )
            ),

            direction=direction,
        )

    previous_dup_rate = float(
        previous_snapshot.get(
            "duplicate_rate"
        )
        or 0
    )

    current_dup_rate = float(
        current_snapshot.get(
            "duplicate_rate"
        )
        or 0
    )

    dup_delta = (
        current_dup_rate - previous_dup_rate
    )

    if abs(dup_delta) >= (
        DUPLICATE_RATE_THRESHOLD
    ) or (
        previous_dup_rate > 0
        and abs(
            dup_delta / previous_dup_rate
        )
        >= 0.25
    ):

        direction = (
            "increase"
            if dup_delta > 0
            else "decrease"
        )

        _append_finding(
            findings,

            finding_id="dq:duplicate_rate",

            severity=(
                "high"
                if current_dup_rate >= 5
                and dup_delta > 0
                else "medium"
            ),

            title=(
                "Duplicate rate "
                f"{'rose' if dup_delta > 0 else 'fell'}"
            ),

            message=(
                f"Duplicate rows now represent "
                f"{_format_percent(current_dup_rate)} "
                f"of the dataset, up from "
                f"{_format_percent(previous_dup_rate)}."
                if dup_delta > 0
                else (
                    f"Duplicate rows now represent "
                    f"{_format_percent(current_dup_rate)} "
                    f"of the dataset, down from "
                    f"{_format_percent(previous_dup_rate)}."
                )
            ),

            direction=direction,
        )

    previous_quality = previous_snapshot.get(
        "data_quality_score"
    )

    current_quality = current_snapshot.get(
        "data_quality_score"
    )

    if (
        previous_quality is not None
        and current_quality is not None
    ):

        previous_quality = float(
            previous_quality
        )

        current_quality = float(
            current_quality
        )

        quality_delta = (
            current_quality
            - previous_quality
        )

        if abs(quality_delta) >= (
            QUALITY_POINTS_THRESHOLD
        ):

            direction = (
                "increase"
                if quality_delta > 0
                else "decrease"
            )

            _append_finding(
                findings,

                finding_id="dq:data_quality_score",

                severity=(
                    "high"
                    if quality_delta <= -10
                    else "medium"
                    if quality_delta <= -3
                    else "low"
                ),

                title=(
                    "Data quality score "
                    f"{'improved' if quality_delta > 0 else 'declined'}"
                ),

                message=(
                    f"Overall data-quality score moved "
                    f"from {previous_quality:.1f} "
                    f"to {current_quality:.1f}. "
                    + (
                        "Review source data before "
                        "trusting downstream insights."
                        if quality_delta < 0
                        else "Source data quality looks stronger "
                        "than the prior version."
                    )
                ),

                direction=direction,
            )

    previous_required = float(
        previous_snapshot.get(
            "required_coverage"
        )
        or 0
    )

    current_required = float(
        current_snapshot.get(
            "required_coverage"
        )
        or 0
    )

    if current_required < previous_required:

        _append_finding(
            findings,

            finding_id="dq:required_coverage",

            severity=(
                "critical"
                if current_required < 100
                else "medium"
            ),

            title=(
                "Required-field readiness declined"
            ),

            message=(
                f"Required-field availability fell "
                f"from {previous_required:.0f}% "
                f"to {current_required:.0f}%, "
                "which may block or weaken product "
                "generation."
            ),

            direction="decrease",
        )

    elif (
        current_required == 100
        and previous_required < 100
    ):

        _append_finding(
            findings,

            finding_id="dq:required_coverage",

            severity="medium",

            title=(
                "Required fields are now complete"
            ),

            message=(
                "All required fields are now mapped, "
                "unlocking full product analysis "
                "compared with the prior version."
            ),

            direction="increase",
        )

    previous_missing_required = set(
        previous_snapshot.get(
            "missing_required_fields"
        )
        or []
    )

    current_missing_required = set(
        current_snapshot.get(
            "missing_required_fields"
        )
        or []
    )

    newly_missing = sorted(
        current_missing_required
        - previous_missing_required
    )

    restored_required = sorted(
        previous_missing_required
        - current_missing_required
    )

    if newly_missing:

        _append_finding(
            findings,

            finding_id="dq:missing_required_fields",

            severity="critical",

            title=(
                "Required fields became unavailable"
            ),

            message=(
                "Required fields missing in this "
                f"version: {', '.join(newly_missing)}."
            ),

            direction="decrease",
        )

    if restored_required:

        _append_finding(
            findings,

            finding_id="dq:restored_required_fields",

            severity="medium",

            title=(
                "Required fields restored"
            ),

            message=(
                "Previously missing required fields "
                f"are now available: "
                f"{', '.join(restored_required)}."
            ),

            direction="increase",
        )

    previous_names = set(
        previous_snapshot.get(
            "column_names"
        )
        or []
    )

    current_names = set(
        current_snapshot.get(
            "column_names"
        )
        or []
    )

    added_columns = sorted(
        current_names - previous_names
    )

    removed_columns = sorted(
        previous_names - current_names
    )

    if added_columns:

        preview = ", ".join(
            added_columns[:5]
        )

        suffix = (
            ""
            if len(added_columns) <= 5
            else f" and {len(added_columns) - 5} more"
        )

        _append_finding(
            findings,

            finding_id="dq:new_columns",

            severity="medium",

            title="New columns detected",

            message=(
                f"New source columns appeared: "
                f"{preview}{suffix}. "
                "Review whether they should be mapped "
                "to unlock additional analyses."
            ),

            direction="increase",
        )

    if removed_columns:

        preview = ", ".join(
            removed_columns[:5]
        )

        suffix = (
            ""
            if len(removed_columns) <= 5
            else f" and {len(removed_columns) - 5} more"
        )

        _append_finding(
            findings,

            finding_id="dq:removed_columns",

            severity=(
                "high"
                if removed_columns
                else "medium"
            ),

            title="Columns removed",

            message=(
                f"Source columns no longer present: "
                f"{preview}{suffix}. "
                "Mapped analyses may lose coverage."
            ),

            direction="decrease",
        )

    findings.sort(
        key=lambda item: (
            {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 3,
            }.get(
                item["severity"],
                4,
            ),
            item["title"],
        )
    )

    if findings:
        overview = (
            f"Version {current_version} vs "
            f"version {previous_version}: "
            f"{len(findings)} meaningful data-quality "
            f"change{'s' if len(findings) != 1 else ''} "
            "detected."
        )
    else:
        overview = (
            f"Version {current_version} vs "
            f"version {previous_version}: "
            "no meaningful data-quality changes detected."
        )

    return {
        "previous_version": previous_version,

        "current_version": current_version,

        "has_meaningful_changes": bool(
            findings
        ),

        "overview": overview,

        "finding_count": len(findings),

        "findings": findings,
    }
