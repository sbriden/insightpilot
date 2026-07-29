from typing import Dict, List


def generate_insights(metrics: Dict) -> List[Dict]:
    """
    Generate actionable insights from dataset metrics.

    These are deterministic observations that become the
    foundation for executive summaries and AI narratives.
    """

    insights = []

    dataset = metrics.get("dataset", {})
    numeric = metrics.get("numeric", {})
    categorical = metrics.get("categorical", {})
    dates = metrics.get("dates", {})

    # --------------------------------------------------
    # Dataset-level insights
    # --------------------------------------------------

    duplicates = dataset.get("duplicates", 0)
    if duplicates > 0:
        insights.append({
            "severity": "high",
            "category": "Data Quality",
            "title": "Duplicate Records Detected",
            "description": f"The dataset contains {duplicates:,} duplicate rows.",
        })

    missing_pct = dataset.get("missing_percentage", 0)

    if missing_pct >= 20:
        severity = "high"
    elif missing_pct >= 10:
        severity = "medium"
    elif missing_pct > 0:
        severity = "low"
    else:
        severity = None

    if severity:
        insights.append({
            "severity": severity,
            "category": "Data Quality",
            "title": "Missing Data",
            "description": f"{missing_pct:.1f}% of all dataset values are missing.",
        })

    # --------------------------------------------------
    # Numeric columns
    # --------------------------------------------------

    for column, values in numeric.items():

        count = values.get("count", 0)

        if count == 0:
            continue

        mean = values.get("mean", 0)
        std = values.get("std", 0)

        if mean != 0:
            coefficient_variation = abs(std / mean)

            if coefficient_variation > 1.0:
                insights.append({
                    "severity": "medium",
                    "category": "Distribution",
                    "title": f"{column} shows high variability",
                    "description": (
                        f"{column} has a coefficient of variation of "
                        f"{coefficient_variation:.2f}, indicating significant spread."
                    ),
                })

        negative = values.get("negative_values", 0)

        if negative > 0:
            insights.append({
                "severity": "low",
                "category": "Values",
                "title": f"Negative values in {column}",
                "description": (
                    f"{negative:,} records contain negative values."
                ),
            })

        zeros = values.get("zeros", 0)

        if zeros > 0:
            insights.append({
                "severity": "low",
                "category": "Values",
                "title": f"Zero values in {column}",
                "description": (
                    f"{zeros:,} records contain zero values."
                ),
            })

    # --------------------------------------------------
    # Categorical columns
    # --------------------------------------------------

    for column, values in categorical.items():

        unique = values.get("unique_values", 0)

        if unique == 1:
            insights.append({
                "severity": "medium",
                "category": "Data Quality",
                "title": f"{column} contains only one value",
                "description": (
                    "This field may provide little analytical value."
                ),
            })

        missing = values.get("missing", 0)

        if missing > 0:
            insights.append({
                "severity": "low",
                "category": "Data Quality",
                "title": f"Missing values in {column}",
                "description": (
                    f"{missing:,} values are missing."
                ),
            })

    # --------------------------------------------------
    # Date columns
    # --------------------------------------------------

    for column, values in dates.items():

        span = values.get("timespan_days", 0)

        if span > 365 * 5:
            insights.append({
                "severity": "low",
                "category": "Time",
                "title": f"{column} spans more than five years",
                "description": (
                    f"The dataset covers approximately {span:,} days."
                ),
            })

    # --------------------------------------------------
    # Sort insights by severity
    # --------------------------------------------------

    severity_order = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }

    insights.sort(
        key=lambda x: severity_order.get(
            x["severity"],
            99,
        )
    )

    return insights