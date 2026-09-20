from .models import InsightRule


CATEGORY = "Revenue Trends"


RULES = [

    InsightRule(
        id="revenue_growth",
        severity="low",
        title="Revenue Growth",
        condition=lambda f: (
            f["overall_growth"] >= 0.05
        ),
        message=lambda f: (
            f"Revenue increased by "
            f"{f['overall_growth']:.1%} "
            "between the first and latest periods."
        ),
        category=CATEGORY,
        recommended_action=(
            "Identify growth drivers and reinforce "
            "what is working in the current period."
        ),
        metric="overall_revenue_growth",
        observed=lambda f: f["overall_growth"],
        baseline=0.0,
        comparison="vs_prior_period",
        magnitude=lambda f: f["overall_growth"],
        magnitude_unit="ratio",
        dimensions=["date"],
        min_abs_magnitude=0.05,
    ),

    InsightRule(
        id="revenue_decline",
        severity="medium",
        title="Revenue Decline",
        condition=lambda f: (
            f["overall_growth"] <= -0.05
        ),
        message=lambda f: (
            f"Revenue declined by "
            f"{abs(f['overall_growth']):.1%} "
            "between the first and latest periods."
        ),
        category=CATEGORY,
        recommended_action=(
            "Investigate decline drivers and define "
            "recovery actions with sales leadership."
        ),
        metric="overall_revenue_growth",
        observed=lambda f: f["overall_growth"],
        baseline=0.0,
        comparison="vs_prior_period",
        magnitude=lambda f: f["overall_growth"],
        magnitude_unit="ratio",
        dimensions=["date"],
        min_abs_magnitude=0.05,
    ),

    InsightRule(
        id="accelerating_trend",
        severity="low",
        title="Positive Revenue Trend",
        condition=lambda f: (
            f["trend_direction"] == "growing"
        ),
        message=lambda f: (
            "Revenue is trending upward, with the "
            "most recent three-month average "
            f"{f['trend_change']:.1%} above the "
            "preceding three-month period."
        ),
        category=CATEGORY,
        recommended_action=(
            "Monitor momentum and allocate resources "
            "to sustain the positive trend."
        ),
        metric="trend_change",
        observed=lambda f: f["trend_change"],
        baseline=0.05,
        comparison="vs_threshold",
        magnitude=lambda f: f["trend_change"] - 0.05,
        magnitude_unit="ratio",
        dimensions=["date"],
    ),

    InsightRule(
        id="declining_trend",
        severity="medium",
        title="Declining Revenue Trend",
        condition=lambda f: (
            f["trend_direction"] == "declining"
        ),
        message=lambda f: (
            "Revenue is trending downward, with the "
            "most recent three-month average "
            f"{abs(f['trend_change']):.1%} below the "
            "preceding three-month period."
        ),
        category=CATEGORY,
        recommended_action=(
            "Review pipeline, pricing, and demand "
            "signals to reverse the downward trend."
        ),
        metric="trend_change",
        observed=lambda f: f["trend_change"],
        baseline=-0.05,
        comparison="vs_threshold",
        magnitude=lambda f: f["trend_change"] - (-0.05),
        magnitude_unit="ratio",
        dimensions=["date"],
    ),

    InsightRule(
        id="stable_trend",
        severity="low",
        title="Stable Revenue Trend",
        condition=lambda f: (
            f["trend_direction"] == "stable"
        ),
        message=lambda f: (
            "Revenue has remained relatively stable, "
            "with the most recent three-month average "
            f"changing by only {abs(f['trend_change']):.1%} "
            "from the preceding three-month period."
        ),
        category=CATEGORY,
        recommended_action=(
            "Look for growth pockets while maintaining "
            "current performance levels."
        ),
        metric="trend_change",
        observed=lambda f: f["trend_change"],
        baseline=0.0,
        comparison="vs_threshold",
        magnitude=lambda f: f["trend_change"],
        magnitude_unit="ratio",
        dimensions=["date"],
    ),

    InsightRule(
        id="revenue_anomaly",
        severity="medium",
        title="Revenue Anomaly Detected",
        condition=lambda f: (
            f["anomaly_count"] > 0
        ),
        message=lambda f: (
            f"{f['anomaly_count']} revenue periods "
            "showed significant deviation from the "
            "recent trend, exceeding 20%."
        ),
        category=CATEGORY,
        recommended_action=(
            "Validate whether anomalies reflect one-time "
            "events or a shift in underlying demand."
        ),
        metric="anomaly_count",
        observed=lambda f: f["anomaly_count"],
        baseline=0,
        comparison="vs_threshold",
        magnitude=lambda f: float(f["anomaly_count"]),
        magnitude_unit="count",
        dimensions=["date"],
    ),

    InsightRule(
        id="revenue_spike",
        severity="low",
        title="Revenue Spike",
        condition=lambda f: (
            f["largest_positive_anomaly"] is not None
        ),
        message=lambda f: (
            f"Revenue was unusually high during "
            f"{f['largest_positive_anomaly'][f['date_column']]:%B %Y}, "
            f"running "
            f"{f['largest_positive_anomaly']['trend_deviation']:.1%} "
            "above the recent trend."
        ),
        category=CATEGORY,
        recommended_action=(
            "Determine whether the spike is repeatable "
            "and how to capture similar upside."
        ),
        metric="trend_deviation",
        observed=lambda f: (
            f["largest_positive_anomaly"]["trend_deviation"]
        ),
        baseline=0.20,
        comparison="vs_threshold",
        magnitude=lambda f: (
            f["largest_positive_anomaly"]["trend_deviation"] - 0.20
        ),
        magnitude_unit="ratio",
        dimensions=["date"],
    ),

    InsightRule(
        id="revenue_drop",
        severity="medium",
        title="Revenue Drop",
        condition=lambda f: (
            f["largest_negative_anomaly"] is not None
        ),
        message=lambda f: (
            f"Revenue was unusually low during "
            f"{f['largest_negative_anomaly'][f['date_column']]:%B %Y}, "
            f"running "
            f"{abs(f['largest_negative_anomaly']['trend_deviation']):.1%} "
            "below the recent trend."
        ),
        category=CATEGORY,
        recommended_action=(
            "Investigate root cause of the drop and "
            "mitigate risk of recurrence."
        ),
        metric="trend_deviation",
        observed=lambda f: (
            f["largest_negative_anomaly"]["trend_deviation"]
        ),
        baseline=-0.20,
        comparison="vs_threshold",
        magnitude=lambda f: (
            f["largest_negative_anomaly"]["trend_deviation"] - (-0.20)
        ),
        magnitude_unit="ratio",
        dimensions=["date"],
    ),

]
