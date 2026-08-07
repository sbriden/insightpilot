from dataclasses import dataclass, asdict, field
from datetime import datetime
import pandas as pd


@dataclass
class AnalysisContext:

    profile: dict
    metrics: dict
    classification: dict

    recommendations: list = field(default_factory=list)
    insights: list = field(default_factory=list)

    column_profiles: list = field(default_factory=list)
    visualizations: list = field(default_factory=list)

    analysis_dashboards: list = field(default_factory=list)

    executive_brief: dict | None = None
    quality: dict | None = None

    created_at: datetime | None = None
    analysis_metadata: dict | None = None

    dataframe: pd.DataFrame | None = field(
        default=None,
        repr=False,
    )


    def to_dict(self):
        """
        Complete internal representation.
        Useful for persistence and debugging.
        """
        return asdict(self)


    def to_prompt_context(self):
        """
        Lightweight context sent to the LLM.
        """
        return {
            "profile": self.profile,
            "metrics": self.metrics,
            "classification": self.classification,
            "recommendations": self.recommendations,
            "insights": self.insights,
            "analysis_dashboards": self.analysis_dashboards,
        }


    def to_api_response(self):
        """
        Public API contract.
        """
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
            "quality": self.quality,

            "created_at": self.created_at,
        }