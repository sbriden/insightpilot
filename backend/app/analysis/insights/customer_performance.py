from .models import InsightRule


CATEGORY = "Customer Performance"


RULES = [

    InsightRule(
        id="negative_customers",
        severity="medium",
        title="Loss-Making Customers",
        condition=lambda f: (
            f.get("negative_customers", 0) > 0
        ),
        message=lambda f: (
            f"{f['negative_customers']:,} customers "
            f"({f['negative_customer_pct']:.1%} "
            "of customers) generated negative profit, "
            f"contributing "
            f"${abs(f['negative_customer_profit']):,.0f} "
            "in aggregate losses."
        ),
        category=CATEGORY,
        recommended_action=(
            "Review pricing, discounts, and service costs "
            "for loss-making customer accounts."
        ),
        metric="negative_customer_count",
        observed=lambda f: f["negative_customers"],
        baseline=0,
        comparison="vs_threshold",
        magnitude=lambda f: float(f["negative_customers"]),
        magnitude_unit="count",
        dimensions=["customer"],
    ),

    InsightRule(
        id="high_negative_customer_rate",
        severity="high",
        title="High Customer Loss Rate",
        condition=lambda f: (
            f.get("negative_customer_pct", 0) >= 0.20
        ),
        message=lambda f: (
            f"{f['negative_customer_pct']:.1%} of customers "
            "generated negative profit, suggesting a "
            "potential pricing, servicing, or cost issue."
        ),
        category=CATEGORY,
        recommended_action=(
            "Escalate account economics review and define "
            "remediation plans for unprofitable segments."
        ),
        metric="negative_customer_rate",
        observed=lambda f: f["negative_customer_pct"],
        baseline=0.20,
        comparison="vs_threshold",
        magnitude=lambda f: f["negative_customer_pct"] - 0.20,
        magnitude_unit="ratio",
        dimensions=["customer"],
    ),

    InsightRule(
        id="low_margin_customers",
        severity="medium",
        title="Low-Margin Customers",
        condition=lambda f: (
            f.get("low_margin_customer_pct", 0) >= 0.20
        ),
        message=lambda f: (
            f"{f['low_margin_customer_pct']:.1%} of customers "
            "have margins below 10%, indicating potential "
            "pricing or cost optimization opportunities."
        ),
        category=CATEGORY,
        recommended_action=(
            "Identify low-margin accounts and test pricing "
            "or cost-to-serve improvements."
        ),
        metric="low_margin_customer_rate",
        observed=lambda f: f["low_margin_customer_pct"],
        baseline=0.20,
        comparison="vs_threshold",
        magnitude=lambda f: f["low_margin_customer_pct"] - 0.20,
        magnitude_unit="ratio",
        dimensions=["customer"],
    ),

    InsightRule(
        id="customer_concentration",
        severity="medium",
        title="Customer Revenue Concentration",
        condition=lambda f: (
            f.get("top10_revenue_share", 0) >= 0.50
        ),
        message=lambda f: (
            f"The top 10 customers generate "
            f"{f['top10_revenue_share']:.1%} "
            "of total revenue, indicating significant "
            "customer concentration."
        ),
        category=CATEGORY,
        recommended_action=(
            "Monitor top-account retention and pursue "
            "diversification in the customer base."
        ),
        metric="top10_revenue_share",
        observed=lambda f: f["top10_revenue_share"],
        baseline=0.50,
        comparison="vs_threshold",
        magnitude=lambda f: f["top10_revenue_share"] - 0.50,
        magnitude_unit="ratio",
        dimensions=["customer"],
    ),

    InsightRule(
        id="customer_diversification",
        severity="low",
        title="Diversified Customer Revenue",
        condition=lambda f: (
            f.get("top10_revenue_share", 0) < 0.25
        ),
        message=lambda f: (
            f"The top 10 customers generate only "
            f"{f['top10_revenue_share']:.1%} "
            "of total revenue, indicating a diversified "
            "customer base."
        ),
        category=CATEGORY,
        recommended_action=(
            "Continue monitoring concentration while "
            "supporting balanced growth across accounts."
        ),
        metric="top10_revenue_share",
        observed=lambda f: f["top10_revenue_share"],
        baseline=0.25,
        comparison="vs_threshold",
        magnitude=lambda f: f["top10_revenue_share"] - 0.25,
        magnitude_unit="ratio",
        dimensions=["customer"],
    ),

]
