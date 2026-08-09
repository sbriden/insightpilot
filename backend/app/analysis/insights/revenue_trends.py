from .models import InsightRule


RULES = [

    InsightRule(
        id="revenue_growth",
        severity="low",
        title="Revenue Growth",
        condition=lambda f: (
            f["overall_growth"] > 0
        ),
        message=lambda f: (
            f"Revenue increased by "
            f"{f['overall_growth']:.1%} "
            "between the first and latest periods."
        ),
    ),

    InsightRule(
        id="revenue_decline",
        severity="medium",
        title="Revenue Decline",
        condition=lambda f: (
            f["overall_growth"] < 0
        ),
        message=lambda f: (
            f"Revenue declined by "
            f"{abs(f['overall_growth']):.1%} "
            "between the first and latest periods."
        ),
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
    ),

]