def generate_recommendations(
    classification: dict,
    metrics: dict,
) -> list[dict]:
    """
    Generate business recommendations based on
    dataset classification and available metrics.
    """

    recommendations = []

    dataset_type = classification.get("type")

    if dataset_type == "Sales & Revenue":

        recommendations.extend([
            {
                "title": "Customer Concentration Analysis",
                "description": (
                    "Analyze whether revenue is concentrated "
                    "among a small number of customers."
                ),
                "priority": "High",
            },
            {
                "title": "Revenue Distribution",
                "description": (
                    "Identify top revenue drivers and "
                    "underperforming segments."
                ),
                "priority": "Medium",
            },
            {
                "title": "Profitability Review",
                "description": (
                    "Analyze profit margins across products "
                    "or categories."
                ),
                "priority": "High",
            },
        ])


    elif dataset_type == "Healthcare Claims":

        recommendations.extend([
            {
                "title": "Claims Distribution Analysis",
                "description": (
                    "Analyze claim volume and cost patterns."
                ),
                "priority": "High",
            },
            {
                "title": "Provider Analysis",
                "description": (
                    "Identify provider-level trends and outliers."
                ),
                "priority": "Medium",
            },
        ])


    else:

        recommendations.append({
            "title": "Explore Dataset Structure",
            "description": (
                "Review key fields, distributions, and "
                "data quality indicators."
            ),
            "priority": "Medium",
        })


    return recommendations