from .models import InsightRule


CATEGORY = "Customer Concentration"


RULES = [

    InsightRule(
        id="high_concentration",
        severity="high",
        title="High Revenue Concentration",
        condition=lambda f: (
            f["top10_share"] >= 0.40
        ),
        message=lambda f: (
            f"The top 10 customers generate "
            f"{f['top10_share']:.1%} of total revenue, "
            "indicating significant customer concentration risk."
        ),
        category=CATEGORY,
        recommended_action=(
            "Review dependency on top customers with "
            "sales leadership and develop a diversification plan."
        ),
    ),

    InsightRule(
        id="moderate_concentration",
        severity="medium",
        title="Moderate Revenue Concentration",
        condition=lambda f: (
            0.25 <= f["top10_share"] < 0.40
        ),
        message=lambda f: (
            f"The top 10 customers generate "
            f"{f['top10_share']:.1%} of total revenue. "
            "Customer concentration should be monitored."
        ),
        category=CATEGORY,
        recommended_action=(
            "Track concentration trends monthly and "
            "identify accounts to expand or replace."
        ),
    ),

    InsightRule(
        id="low_concentration",
        severity="low",
        title="Diversified Revenue Base",
        condition=lambda f: (
            f["top10_share"] < 0.25
        ),
        message=lambda f: (
            f"The top 10 customers generate "
            f"{f['top10_share']:.1%} of total revenue, "
            "indicating a relatively diversified customer base."
        ),
        category=CATEGORY,
        recommended_action=(
            "Maintain current diversification while "
            "monitoring for emerging concentration."
        ),
    ),

    InsightRule(
        id="single_customer_concentration",
        severity="high",
        title="Single Customer Concentration",
        condition=lambda f: (
            f["top_customer_share"] >= 0.10
        ),
        message=lambda f: (
            f"The largest customer represents "
            f"{f['top_customer_share']:.1%} of total revenue, "
            "creating potential exposure to customer-specific risk."
        ),
        category=CATEGORY,
        recommended_action=(
            "Assess retention risk for the largest customer "
            "and build contingency plans for revenue exposure."
        ),
    ),

]
