from datetime import datetime

from ..core.analysis_context import AnalysisContext

from .classifier import classify_dataset
from .insights import generate_insights
from .metrics import generate_metrics
from .profiler import profile_dataframe
from .recommendations import generate_recommendations


def analyze_dataframe(df) -> AnalysisContext:
    """
    Runs the complete InsightPilot analysis pipeline.
    """

    profile = profile_dataframe(df)

    metrics = generate_metrics(df)

    classification = classify_dataset(
        df.columns.tolist()
    )

    recommendations = generate_recommendations(
        classification,
        metrics,
    )

    insights = generate_insights(metrics)

    return AnalysisContext(
        profile=profile,
        metrics=metrics,
        classification=classification,
        recommendations=recommendations,
        insights=insights,
        created_at=datetime.utcnow(),
    )