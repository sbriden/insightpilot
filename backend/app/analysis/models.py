from dataclasses import dataclass, asdict, field

from .insights.findings import CandidateFinding


@dataclass
class MetricCard:
    id: str
    title: str
    value: str
    subtitle: str | None = None


@dataclass
class Visualization:
    id: str
    title: str

    chart: str
    dataset: str

    x: str | None = None
    y: str | None = None

    description: str = ""

    takeaway: str = ""

    business_question: str = ""

    priority: str = "Medium"


@dataclass
class Insight:
    severity: str
    message: str
    title: str | None = None
    priority: str | None = None
    category: str | None = None
    what_happened: str | None = None
    why_it_matters: str | None = None
    recommended_action: str | None = None
    id: str | None = None
    rule_id: str | None = None


@dataclass
class AnalysisDashboard:
    id: str
    title: str
    summary: str

    metrics: list[MetricCard] = field(default_factory=list)
    datasets: dict = field(default_factory=dict)
    visualizations: list[Visualization] = field(
        default_factory=list
    )
    insights: list[Insight] = field(default_factory=list)
    candidate_findings: list[CandidateFinding] = field(
        default_factory=list
    )
    actions: list[str] = field(default_factory=list)

    def to_dict(self):
        payload = asdict(self)

        payload["candidate_findings"] = [
            finding.to_dict()
            if hasattr(finding, "to_dict")
            else finding
            for finding in self.candidate_findings
        ]

        return payload
