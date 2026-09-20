from .models import InsightRule


CATEGORY = "Customer & Product"


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
        category=CATEGORY,
        recommended_action=(
            "Target under-penetrated products in "
            "existing customer campaigns."
        ),
        metric="low_penetration_product_rate",
        observed=lambda f: f["low_penetration_product_pct"],
        baseline=0.25,
        comparison="vs_threshold",
        magnitude=lambda f: (
            f["low_penetration_product_pct"] - 0.25
        ),
        magnitude_unit="ratio",
        dimensions=["customer", "product"],
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
        category=CATEGORY,
        recommended_action=(
            "Maintain current mix and look for "
            "incremental expansion opportunities."
        ),
        metric="low_penetration_product_rate",
        observed=lambda f: f["low_penetration_product_pct"],
        baseline=0.10,
        comparison="vs_threshold",
        magnitude=lambda f: (
            f["low_penetration_product_pct"] - 0.10
        ),
        magnitude_unit="ratio",
        dimensions=["customer", "product"],
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
        category=CATEGORY,
        recommended_action=(
            "Review pricing and fulfillment economics "
            "for unprofitable combinations."
        ),
        metric="negative_combination_count",
        observed=lambda f: f["negative_combinations"],
        baseline=0,
        comparison="vs_threshold",
        magnitude=lambda f: float(f["negative_combinations"]),
        magnitude_unit="count",
        dimensions=["customer", "product"],
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
        category=CATEGORY,
        recommended_action=(
            "Prioritize remediation for the highest-loss "
            "customer/product pairings."
        ),
        metric="negative_combination_rate",
        observed=lambda f: f["negative_combination_pct"],
        baseline=0.20,
        comparison="vs_threshold",
        magnitude=lambda f: (
            f["negative_combination_pct"] - 0.20
        ),
        magnitude_unit="ratio",
        dimensions=["customer", "product"],
    ),

]
