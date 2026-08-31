from .models import InsightRule


CATEGORY = "Product Performance"


RULES = [

    InsightRule(
        id="negative_products",
        severity="medium",
        title="Loss-Making Products",
        condition=lambda f: (
            f.get("negative_products", 0) > 0
        ),
        message=lambda f: (
            f"{f['negative_products']:,} products "
            f"({f['negative_product_pct']:.1%} "
            "of products) generated negative profit, "
            f"contributing "
            f"${abs(f['negative_product_profit']):,.0f} "
            "in aggregate losses."
        ),
        category=CATEGORY,
        recommended_action=(
            "Review pricing, discounts, and cost structure "
            "for loss-making products."
        ),
    ),

    InsightRule(
        id="high_negative_product_rate",
        severity="high",
        title="High Product Loss Rate",
        condition=lambda f: (
            f.get("negative_product_pct", 0) >= 0.20
        ),
        message=lambda f: (
            f"{f['negative_product_pct']:.1%} of products "
            "generated negative profit, suggesting a "
            "broader pricing or cost-structure issue."
        ),
        category=CATEGORY,
        recommended_action=(
            "Escalate portfolio review for products with "
            "sustained negative economics."
        ),
    ),

    InsightRule(
        id="low_margin_products",
        severity="medium",
        title="Low-Margin Products",
        condition=lambda f: (
            f.get("low_margin_product_pct", 0) >= 0.20
        ),
        message=lambda f: (
            f"{f['low_margin_product_pct']:.1%} of products "
            "have profit margins below 10%, indicating "
            "potential pricing or cost optimization "
            "opportunities."
        ),
        category=CATEGORY,
        recommended_action=(
            "Identify low-margin SKUs and test price "
            "or cost improvements."
        ),
    ),

    InsightRule(
        id="product_concentration",
        severity="medium",
        title="Product Revenue Concentration",
        condition=lambda f: (
            f.get("top10_revenue_share", 0) >= 0.50
        ),
        message=lambda f: (
            f"The top 10 products generate "
            f"{f['top10_revenue_share']:.1%} "
            "of total revenue, indicating significant "
            "product concentration."
        ),
        category=CATEGORY,
        recommended_action=(
            "Reduce reliance on top products by "
            "investing in broader portfolio growth."
        ),
    ),

    InsightRule(
        id="product_diversification",
        severity="low",
        title="Diversified Product Revenue",
        condition=lambda f: (
            f.get("top10_revenue_share", 0) < 0.25
        ),
        message=lambda f: (
            f"The top 10 products generate only "
            f"{f['top10_revenue_share']:.1%} "
            "of total revenue, indicating a diversified "
            "product mix."
        ),
        category=CATEGORY,
        recommended_action=(
            "Maintain portfolio balance while tracking "
            "emerging concentration trends."
        ),
    ),

]
