from typing import List, Dict


def generate_recommendations(
    classification: dict,
    metrics: dict,
) -> List[Dict]:
    """
    Generate business recommendations based on
    the detected dataset type.
    """

    dataset_type = classification.get("type", "General")

    recommendations = []

    if dataset_type == "Sales & Revenue":

        recommendations.extend([
            {
                "id": "customer_concentration",
                "title": "Customer Concentration",
                "description": "Determine whether a small number of customers contribute most of the revenue.",
                "priority": "High",
                "category": "Revenue",
                "analysis_type": "contribution",
                "dimension_keywords": [
                    "customer",
                    "account",
                    "client",
                ],
                "measure_keywords": [
                    "sales",
                    "revenue",
                    "amount",
                ],
            },
            {
                "id": "profitability",
                "title": "Profitability Analysis",
                "description": "Compare profit margins across products or services.",
                "priority": "High",
                "category": "Finance",
                "analysis_type": "relationship",
                "dimension_keywords": [
                    "product",
                    "service",
                    "category",
                ],
                "measure_keywords": [
                    "profit",
                    "margin",
                    "sales",
                    "revenue",
                ],
            },
            {
                "id": "revenue_trends",
                "title": "Revenue Trends",
                "description": "Analyze revenue over time and identify seasonal patterns.",
                "priority": "Medium",
                "category": "Time Series",
                "analysis_type": "time_series",
                "dimension_keywords": [
                    "date",
                    "time",
                    "month",
                    "year",
                ],
                "measure_keywords": [
                    "sales",
                    "revenue",
                    "amount",
                ],
            },
            {
                "id": "outliers",
                "title": "Revenue Outliers",
                "description": "Identify unusually large or unusually small transactions.",
                "priority": "Medium",
                "category": "Quality",
                "analysis_type": "outlier_detection",
                "measure_keywords": [
                    "sales",
                    "revenue",
                    "amount",
                    "price",
                ],
            },
        ])

    elif dataset_type == "Healthcare Claims":

        recommendations.extend([
            {
                "id": "claims_distribution",
                "title": "Claims Distribution",
                "description": "Review claim counts and costs by diagnosis and procedure.",
                "priority": "High",
                "category": "Claims",
            },
            {
                "id": "provider_analysis",
                "title": "Provider Performance",
                "description": "Compare providers by claim volume and average cost.",
                "priority": "Medium",
                "category": "Providers",
            },
        ])

    elif dataset_type == "Human Resources":

        recommendations.extend([
            {
                "id": "headcount",
                "title": "Headcount Analysis",
                "description": "Review employee counts by department and location.",
                "priority": "High",
                "category": "Workforce",
            },
            {
                "id": "turnover",
                "title": "Turnover Analysis",
                "description": "Analyze hiring and termination trends over time.",
                "priority": "Medium",
                "category": "Workforce",
            },
        ])

    else:

        recommendations.extend([
            {
                "id": "data_quality",
                "title": "Data Quality Review",
                "description": "Review missing values, duplicates, and inconsistencies.",
                "priority": "High",
                "category": "Quality",
            },
            {
                "id": "distribution",
                "title": "Distribution Analysis",
                "description": "Review distributions for numeric and categorical fields.",
                "priority": "Medium",
                "category": "Exploration",
            },
        ])

    return recommendations