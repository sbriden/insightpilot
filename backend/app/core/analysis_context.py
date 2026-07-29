from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class AnalysisContext:
    profile: dict
    metrics: dict
    classification: dict
    recommendations: list
    insights: list
    executive_brief: str | None = None
    quality: dict | None = None
    created_at: datetime | None = None

    def to_dict(self):
        return asdict(self)

    def to_prompt_context(self):
        return {
            "profile": self.profile,
            "metrics": self.metrics,
            "classification": self.classification,
            "recommendations": self.recommendations,
            "insights": self.insights,
    }