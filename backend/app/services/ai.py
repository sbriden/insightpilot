from ..core.analysis_context import AnalysisContext


def generate_fallback_brief(
    context: AnalysisContext,
) -> dict:

    classification = (
        context.classification.get("dataset_type")
        or context.classification.get("classification")
        or context.classification.get("type")
        or "unknown"
    )

    summary = context.profile.get(
        "summary",
        {}
    )

    rows = summary.get(
        "rows",
        0
    )

    columns = summary.get(
        "columns",
        0
    )

    return {
        "overview": (
            f"This appears to be a {classification} dataset "
            f"containing {rows:,} rows and {columns} columns."
        ),

        "key_findings": [
            insight["description"]
            for insight in context.insights[:3]
        ],

        "risks": [
            insight["description"]
            for insight in context.insights
            if insight["severity"] == "high"
        ],

        "opportunities": [
            recommendation
            for recommendation in context.recommendations[:3]
        ],

        "next_steps": [
            "Review high priority insights",
            "Perform deeper business analysis",
        ],
    }

def generate_executive_brief(
    context: AnalysisContext,
) -> dict:

    return generate_fallback_brief(context)