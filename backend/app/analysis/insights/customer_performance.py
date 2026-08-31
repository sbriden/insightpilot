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
    ),

]
