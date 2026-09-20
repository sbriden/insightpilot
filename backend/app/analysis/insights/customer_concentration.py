from .models import InsightRule


CATEGORY = "Customer Concentration"


def _concentration_evidence(facts: dict) -> list[dict]:
    """Machine-readable support for concentration findings."""

    return [
        {
            "key": "top10_revenue",
            "label": "Top 10 revenue",
            "value": facts.get("top10_revenue"),
            "unit": "currency",
        },
        {
            "key": "total_revenue",
            "label": "Total revenue",
            "value": facts.get("total_revenue"),
            "unit": "currency",
        },
        {
            "key": "total_customers",
            "label": "Customer population",
            "value": facts.get("total_customers"),
            "unit": "count",
        },
        {
            "key": "top10_share",
            "label": "Top 10 customer share",
            "value": facts.get("top10_share"),
            "unit": "ratio",
        },
    ]


def _concentration_inputs(facts: dict) -> dict:
    return {
        "top10_revenue": facts.get("top10_revenue"),
        "total_revenue": facts.get("total_revenue"),
        "total_customers": facts.get("total_customers"),
        "top10_share": facts.get("top10_share"),
    }


def _top_n_concentration_calculation(
    *,
    top_n: int = 10,
    measure: str = "revenue",
    grouping: str = "customer_id",
) -> dict:
    """
    Reproducible recipe for top-N customer concentration.

    Matches the engine contract:

        Analysis type / Measure / Dimension / Aggregation /
        Grouping / Ranking / Top N / Comparison
    """

    return {
        "analysis_type": "customer_concentration",
        "measure": measure,
        "dimension": "customer",
        "aggregation": "SUM",
        "grouping": grouping,
        "ranking": f"descending {measure}",
        "top_n": top_n,
        "comparison": f"top {top_n} / total",
        "parameters": {
            "share_formula": f"sum(top_{top_n}_{measure}) / sum({measure})",
        },
    }


def _top_1_concentration_calculation(
    *,
    measure: str = "revenue",
    grouping: str = "customer_id",
) -> dict:
    return {
        "analysis_type": "customer_concentration",
        "measure": measure,
        "dimension": "customer",
        "aggregation": "SUM",
        "grouping": grouping,
        "ranking": f"descending {measure}",
        "top_n": 1,
        "comparison": "top 1 / total",
        "parameters": {
            "share_formula": f"max({measure}_by_customer) / sum({measure})",
        },
    }


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
        metric="top10_revenue_share",
        observed=lambda f: f["top10_share"],
        baseline=0.40,
        comparison="vs_threshold",
        magnitude=lambda f: f["top10_share"] - 0.40,
        magnitude_unit="ratio",
        dimensions=["customer"],
        filters=lambda f: [
            {
                "field": "top10_share",
                "op": ">=",
                "value": 0.40,
                "label": "top 10 revenue share >= 40%",
            }
        ],
        calculations=[
            "rank customers by revenue descending",
            "top10_revenue = sum(revenue of top 10 customers)",
            "total_revenue = sum(revenue of all customers)",
            "top10_share = top10_revenue / total_revenue",
            "magnitude = top10_share - 0.40",
        ],
        calculation=_top_n_concentration_calculation(),
        row_scope=(
            "all customers aggregated by revenue; "
            "top 10 share of total"
        ),
        input_values=lambda f: {
            **_concentration_inputs(f),
            "threshold": 0.40,
        },
        evidence_metrics=_concentration_evidence,
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
        metric="top10_revenue_share",
        observed=lambda f: f["top10_share"],
        baseline=0.25,
        comparison="vs_threshold",
        magnitude=lambda f: f["top10_share"] - 0.25,
        magnitude_unit="ratio",
        dimensions=["customer"],
        filters=lambda f: [
            {
                "field": "top10_share",
                "op": ">=",
                "value": 0.25,
            },
            {
                "field": "top10_share",
                "op": "<",
                "value": 0.40,
            },
        ],
        calculations=[
            "rank customers by revenue descending",
            "top10_share = sum(top 10 revenue) / total_revenue",
            "magnitude = top10_share - 0.25",
        ],
        calculation=_top_n_concentration_calculation(),
        row_scope=(
            "all customers aggregated by revenue; "
            "top 10 share of total"
        ),
        input_values=lambda f: {
            **_concentration_inputs(f),
            "lower_threshold": 0.25,
            "upper_threshold": 0.40,
        },
        evidence_metrics=_concentration_evidence,
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
        metric="top10_revenue_share",
        observed=lambda f: f["top10_share"],
        baseline=0.25,
        comparison="vs_threshold",
        magnitude=lambda f: f["top10_share"] - 0.25,
        magnitude_unit="ratio",
        dimensions=["customer"],
        filters=lambda f: [
            {
                "field": "top10_share",
                "op": "<",
                "value": 0.25,
            }
        ],
        calculations=[
            "rank customers by revenue descending",
            "top10_share = sum(top 10 revenue) / total_revenue",
            "magnitude = top10_share - 0.25",
        ],
        calculation=_top_n_concentration_calculation(),
        row_scope=(
            "all customers aggregated by revenue; "
            "top 10 share of total"
        ),
        input_values=lambda f: {
            **_concentration_inputs(f),
            "threshold": 0.25,
        },
        evidence_metrics=_concentration_evidence,
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
        metric="top_customer_revenue_share",
        observed=lambda f: f["top_customer_share"],
        baseline=0.10,
        comparison="vs_threshold",
        magnitude=lambda f: f["top_customer_share"] - 0.10,
        magnitude_unit="ratio",
        dimensions=["customer"],
        filters=lambda f: [
            {
                "field": "top_customer_share",
                "op": ">=",
                "value": 0.10,
            }
        ],
        calculations=[
            "rank customers by revenue descending",
            "top_customer_revenue = revenue of rank-1 customer",
            "top_customer_share = top_customer_revenue / total_revenue",
            "magnitude = top_customer_share - 0.10",
        ],
        calculation=_top_1_concentration_calculation(),
        row_scope=(
            "all customers aggregated by revenue; "
            "largest customer share of total"
        ),
        input_values=lambda f: {
            "top_customer_share": f["top_customer_share"],
            "top_customer_revenue": f.get("top_customer_revenue"),
            "total_revenue": f.get("total_revenue"),
            "total_customers": f.get("total_customers"),
            "threshold": 0.10,
        },
        evidence_metrics=lambda f: [
            {
                "key": "top_customer_revenue",
                "label": "Top customer revenue",
                "value": f.get("top_customer_revenue"),
                "unit": "currency",
            },
            {
                "key": "total_revenue",
                "label": "Total revenue",
                "value": f.get("total_revenue"),
                "unit": "currency",
            },
            {
                "key": "total_customers",
                "label": "Customer population",
                "value": f.get("total_customers"),
                "unit": "count",
            },
            {
                "key": "top_customer_share",
                "label": "Top customer share",
                "value": f["top_customer_share"],
                "unit": "ratio",
            },
        ],
    ),

]
