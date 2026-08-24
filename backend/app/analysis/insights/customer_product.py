from .models import InsightRule


RULES = [

    InsightRule(
        id="low_product_penetration",
        severity="medium",
        title="Low Product Penetration",
        condition=lambda f: (
            f.get(
                "low_penetration_product_pct",
                0,
            ) >= 0.25
        ),
        message=lambda f: (
            f"{f['low_penetration_product_pct']:.1%} "
            "of products are purchased by fewer than "
            "25% of customers, indicating potential "
            "cross-sell opportunities."
        ),
    ),

    InsightRule(
        id="high_product_penetration",
        severity="low",
        title="Broad Product Adoption",
        condition=lambda f: (
            f.get(
                "low_penetration_product_pct",
                0,
            ) < 0.10
        ),
        message=lambda f: (
            "Most products have broad customer adoption, "
            "suggesting a relatively diversified product mix."
        ),
    ),

    InsightRule(
        id="negative_customer_product_combinations",
        severity="medium",
        title="Unprofitable Customer/Product Combinations",
        condition=lambda f: (
            f.get(
                "negative_combinations",
                0,
            ) > 0
        ),
        message=lambda f: (
            f"{f['negative_combinations']:,} "
            "customer/product combinations generated "
            "negative profit, representing "
            f"{f['negative_combination_pct']:.1%} "
            "of all combinations."
        ),
    ),

    InsightRule(
        id="high_negative_combination_rate",
        severity="high",
        title="Widespread Combination Losses",
        condition=lambda f: (
            f.get(
                "negative_combination_pct",
                0,
            ) >= 0.20
        ),
        message=lambda f: (
            f"{f['negative_combination_pct']:.1%} "
            "of customer/product combinations generate "
            "negative profit, indicating potential "
            "pricing or servicing issues."
        ),
    ),

]