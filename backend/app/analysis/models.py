from dataclasses import dataclass, asdict, field


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


@dataclass
class AnalysisDashboard:
    id: str
    title: str
    summary: str

    metrics: list[MetricCard] = field(default_factory=list)
    datasets: dict = field(default_factory=dict)
    visualizations: list[Visualization] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)