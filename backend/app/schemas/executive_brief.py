from typing import List

from pydantic import BaseModel


class ExecutiveBriefRequest(BaseModel):
    profile: dict
    metrics: dict
    classification: dict
    recommendations: list
    insights: list


class Opportunity(BaseModel):
    id: str
    title: str | None = None
    category: str | None = None


class ExecutiveBriefResponse(BaseModel):
    overview: str
    key_findings: List[str]
    risks: List[str]
    opportunities: List[Opportunity]
    next_steps: List[str]