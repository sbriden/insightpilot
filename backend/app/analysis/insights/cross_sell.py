from .models import InsightRule


CATEGORY = "Cross-Sell"


RULES = [

    InsightRule(
        id="cross_sell_opportunities",
        severity="medium",
        title="Cross-Sell Opportunities",
        condition=lambda f: (
            f.get("opportunity_count", 0) > 0
        ),
        message=lambda f: (
            f"{f['opportunity_count']:,} potential "
            "cross-sell opportunities were identified, "
            "representing approximately "
            f"${f['estimated_revenue']:,.0f} "
            "in estimated revenue potential."
        ),
        category=CATEGORY,
        recommended_action=(
            "Prioritize the highest-value product pairs "
            "and brief account teams on cross-sell targets."
        ),
        metric="opportunity_count",
        observed=lambda f: f["opportunity_count"],
        baseline=0,
        comparison="vs_threshold",
        magnitude=lambda f: float(f["opportunity_count"]),
        magnitude_unit="count",
        dimensions=["customer", "product"],
    ),

    InsightRule(
        id="high_confidence_cross_sell",
        severity="high",
        title="High-Confidence Cross-Sell",
        condition=lambda f: (
            f.get("high_confidence_count", 0) > 0
        ),
        message=lambda f: (
            f"{f['high_confidence_count']:,} cross-sell "
            "relationships have at least 50% customer "
            "adoption from the source product."
        ),
        category=CATEGORY,
        recommended_action=(
            "Launch targeted outreach for high-confidence "
            "cross-sell pairs with the highest revenue upside."
        ),
        metric="high_confidence_count",
        observed=lambda f: f["high_confidence_count"],
        baseline=0,
        comparison="vs_threshold",
        magnitude=lambda f: float(f["high_confidence_count"]),
        magnitude_unit="count",
        dimensions=["customer", "product"],
    ),

]
