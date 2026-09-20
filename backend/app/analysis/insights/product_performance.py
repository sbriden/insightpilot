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
        metric="negative_product_count",
        observed=lambda f: f["negative_products"],
        baseline=0,
        comparison="vs_threshold",
        magnitude=lambda f: float(f["negative_products"]),
        magnitude_unit="count",
        dimensions=["product"],
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
        metric="negative_product_rate",
        observed=lambda f: f["negative_product_pct"],
        baseline=0.20,
        comparison="vs_threshold",
        magnitude=lambda f: f["negative_product_pct"] - 0.20,
        magnitude_unit="ratio",
        dimensions=["product"],
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
        metric="low_margin_product_rate",
        observed=lambda f: f["low_margin_product_pct"],
        baseline=0.20,
        comparison="vs_threshold",
        magnitude=lambda f: f["low_margin_product_pct"] - 0.20,
        magnitude_unit="ratio",
        dimensions=["product"],
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
        metric="top10_revenue_share",
        observed=lambda f: f["top10_revenue_share"],
        baseline=0.50,
        comparison="vs_threshold",
        magnitude=lambda f: f["top10_revenue_share"] - 0.50,
        magnitude_unit="ratio",
        dimensions=["product"],
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
        metric="top10_revenue_share",
        observed=lambda f: f["top10_revenue_share"],
        baseline=0.25,
        comparison="vs_threshold",
        magnitude=lambda f: f["top10_revenue_share"] - 0.25,
        magnitude_unit="ratio",
        dimensions=["product"],
    ),

]
