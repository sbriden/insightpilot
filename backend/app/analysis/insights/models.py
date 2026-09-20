from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class InsightRule:
    id: str
    severity: str
    title: str
    condition: Callable[[dict], bool]
    message: Callable[[dict], str]
    category: str = "Analysis"
    recommended_action: str = ""

    # Structured candidate-finding projectors (optional).
    # When ``metric`` and ``observed`` are set, the InsightEngine
    # emits a CandidateFinding alongside the narrative Insight.
    metric: str | None = None
    observed: Callable[[dict], Any] | None = None
    baseline: Callable[[dict], Any] | Any | None = None
    comparison: str | None = None
    magnitude: Callable[[dict], Any] | None = None
    magnitude_unit: str | None = None
    confidence: Callable[[dict], Any] | float | None = None
    # Business importance (high|medium|low). Independent of confidence.
    # When omitted, severity is treated as the importance signal.
    importance: Callable[[dict], Any] | str | None = None
    dimensions: Callable[[dict], list] | list | None = None

    # Provenance projectors — answer "what data produced this?"
    filters: Callable[[dict], list] | list | None = None
    calculations: Callable[[dict], list] | list | None = None
    # Structured recipe for reproducing the analytical result.
    calculation: Callable[[dict], dict] | dict | None = None
    row_scope: Callable[[dict], str] | str | None = None
    input_values: Callable[[dict], dict] | dict | None = None
    # Machine-readable evidence metrics ("why this finding?").
    evidence_metrics: Callable[[dict], list] | list | None = None

    # Materiality: skip technically true but uninteresting stats.
    require_material: bool = True
    min_abs_magnitude: float | None = None

    # Insight eligibility override for the finding this rule emits.
    # None → use validation heuristics; True/False → explicit.
    # Does not rank findings — only gates Insight promotion.
    insight_eligible: bool | None = None
