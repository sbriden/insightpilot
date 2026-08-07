from datetime import datetime

import pandas as pd

from ..core.analysis_context import AnalysisContext

from .classifier import classify_dataset
from .insights import generate_insights
from .metrics import generate_metrics
from .profiler import profile_dataframe
from .recommendations import generate_recommendations
from .visualizations import recommend_visualizations
from .column_profiler import profile_columns
from ..analysis.engine import generate_analysis_dashboards
from .ai import generate_executive_brief


def analyze_dataframe(df) -> AnalysisContext:
    """
    Runs the complete InsightPilot analysis pipeline.
    """

    profile = profile_dataframe(df)

    column_profiles = profile_columns(df)

    metrics = generate_metrics(df)

    classification = classify_dataset(
        df.columns.tolist()
    )

    recommendations = generate_recommendations(
        classification,
        metrics,
    )

    insights = generate_insights(metrics)

    visualizations = recommend_visualizations(
        df,
        recommendations,
        column_profiles,
    )

    context = AnalysisContext(
        dataframe=df,
        profile=profile,
        metrics=metrics,
        classification=classification,
        recommendations=recommendations,
        insights=insights,
        column_profiles=column_profiles,
        visualizations=visualizations,
        created_at=datetime.utcnow(),
    )

    context.analysis_dashboards = (
        generate_analysis_dashboards(context)
    )

    context.executive_brief = (
        generate_executive_brief(context)
    )

    return context


def to_api_response(self) -> dict:
    return {
        "profile": self.profile,
        "metrics": self.metrics,
        "classification": self.classification,
        "recommendations": self.recommendations,
        "insights": self.insights,
        "column_profiles": self.column_profiles,
        "visualizations": self.visualizations,
        "analysis_dashboards": self.analysis_dashboards,
        "executive_brief": self.executive_brief,
        "created_at": self.created_at,
    }