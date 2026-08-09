from .models import InsightRule


RULES = [

    InsightRule(
        id="low_margin",
        severity="high",
        title="Low Profit Margin",
        condition=lambda f: f["margin"] < 0.10,
        message=lambda f: (
            f"Profit margin is {f['margin']:.1%}, "
            "which is below the recommended 10% threshold."
        ),
    ),

    InsightRule(
        id="negative_customers",
        severity="medium",
        title="Loss-Making Customers",
        condition=lambda f: (
            f["negative_customers"] > 0
        ),
        message=lambda f: (
            f"{f['negative_customers']:,} customers "
            f"({f['negative_customer_pct']:.1%} of the "
            "customer base) generated negative profit, "
            f"contributing ${abs(f['negative_customer_profit']):,.0f} "
            "in aggregate losses."
        ),
    ),

    InsightRule(
        id="high_customer_loss_rate",
        severity="high",
        title="High Customer Loss Rate",
        condition=lambda f: (
            f["negative_customer_pct"] >= 0.20
        ),
        message=lambda f: (
            f"{f['negative_customer_pct']:.1%} of customers "
            "generated negative profit, indicating a meaningful "
            "portion of the customer base may require review "
            "of pricing, discounts, or account economics."
        ),
    ),

    InsightRule(
        id="negative_products",
        severity="medium",
        title="Loss-Making Products",
        condition=lambda f: (
            f["negative_products"] > 0
        ),
        message=lambda f: (
            f"{f['negative_products']:,} products "
            f"({f['negative_product_pct']:.1%} of products) "
            "generated negative profit, "
            f"contributing ${abs(f['negative_product_profit']):,.0f} "
            "in aggregate losses."
        ),
    ),

    InsightRule(
        id="high_product_loss_rate",
        severity="high",
        title="High Product Loss Rate",
        condition=lambda f: (
            f["negative_product_pct"] >= 0.20
        ),
        message=lambda f: (
            f"{f['negative_product_pct']:.1%} of products "
            "generated negative profit, suggesting a broader "
            "pricing, discount, or cost-structure issue."
        ),
    ),

]