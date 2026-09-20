"""
Generate analytical candidates from semantic capabilities.

Maps supported capabilities (and dataset archetype) to applicable
analyses so the engine does not hardcode a sales-only suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisDefinition:
    """Declarative description of an analysis the engine may propose."""

    id: str
    title: str
    description: str
    required_capabilities: tuple[str, ...]
    # When non-empty, the dataset's primary archetype must match.
    archetypes: tuple[str, ...] = ()
    # Domain tag for debugging / UI grouping.
    domain: str = "general"
    # True when a runnable AnalysisModule exists for this id.
    executable: bool = True


# Catalog of analyses the semantic layer may propose.
# Sales modules remain here as definitions — they are not assumed
# by the main pipeline unless capabilities + archetype match.
ANALYSIS_DEFINITIONS: list[AnalysisDefinition] = [

    # ------------------------------------------------------------------
    # Sales / revenue
    # ------------------------------------------------------------------

    AnalysisDefinition(
        id="revenue_trends",
        title="Revenue Trends",
        description=(
            "Analyze revenue performance and trends over time."
        ),
        required_capabilities=(
            "trend_analysis",
            "aggregation",
        ),
        archetypes=(
            "sales_revenue",
            "finance",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="customer_concentration",
        title="Customer Concentration",
        description=(
            "Analyze revenue concentration across customers."
        ),
        required_capabilities=(
            "customer_analysis",
            "aggregation",
        ),
        archetypes=(
            "sales_revenue",
            "customer",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="customer_growth",
        title="Customer Growth",
        description=(
            "Measure customer revenue growth across periods."
        ),
        required_capabilities=(
            "customer_analysis",
            "trend_analysis",
        ),
        archetypes=(
            "sales_revenue",
            "customer",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="customer_performance",
        title="Customer Performance",
        description=(
            "Rank and compare customers by revenue contribution."
        ),
        required_capabilities=(
            "customer_analysis",
            "aggregation",
        ),
        archetypes=(
            "sales_revenue",
            "customer",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="product_performance",
        title="Product Performance",
        description=(
            "Evaluate product revenue and contribution."
        ),
        required_capabilities=(
            "product_analysis",
            "aggregation",
        ),
        archetypes=(
            "sales_revenue",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="customer_product",
        title="Customer Product Affinity",
        description=(
            "Analyze which products customers purchase together."
        ),
        required_capabilities=(
            "customer_analysis",
            "product_analysis",
            "relationship_analysis",
        ),
        archetypes=(
            "sales_revenue",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="cross_sell",
        title="Cross-Sell Opportunities",
        description=(
            "Identify products customers are likely to purchase together."
        ),
        required_capabilities=(
            "customer_analysis",
            "product_analysis",
            "relationship_analysis",
        ),
        archetypes=(
            "sales_revenue",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="profitability",
        title="Profitability",
        description=(
            "Analyze profit and margin across the business."
        ),
        required_capabilities=(
            "aggregation",
        ),
        archetypes=(
            "sales_revenue",
            "finance",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="profit_improvement",
        title="Profit Improvement",
        description=(
            "Surface products and segments with margin upside."
        ),
        required_capabilities=(
            "product_analysis",
            "aggregation",
        ),
        archetypes=(
            "sales_revenue",
        ),
        domain="sales",
    ),

    AnalysisDefinition(
        id="opportunity_summary",
        title="Opportunity Summary",
        description=(
            "Prioritize the highest-value opportunities "
            "identified across analyses."
        ),
        # Meta-analysis: applicable when sales/customer work is in play.
        required_capabilities=(),
        archetypes=(
            "sales_revenue",
            "customer",
        ),
        domain="sales",
    ),

    # ------------------------------------------------------------------
    # Workforce
    # ------------------------------------------------------------------

    AnalysisDefinition(
        id="workforce_composition",
        title="Workforce Composition",
        description=(
            "Summarize headcount mix across departments, "
            "roles, or other workforce categories."
        ),
        required_capabilities=(
            "category_comparison",
        ),
        archetypes=(
            "workforce",
        ),
        domain="workforce",
        executable=False,
    ),

    AnalysisDefinition(
        id="compensation_analysis",
        title="Compensation Analysis",
        description=(
            "Analyze compensation distribution, levels, "
            "and outliers across the workforce."
        ),
        required_capabilities=(
            "aggregation",
            "distribution_outlier_analysis",
        ),
        archetypes=(
            "workforce",
        ),
        domain="workforce",
        executable=False,
    ),

    AnalysisDefinition(
        id="department_comparison",
        title="Department Comparison",
        description=(
            "Compare workforce measures such as compensation "
            "or headcount across departments."
        ),
        required_capabilities=(
            "category_comparison",
            "aggregation",
        ),
        archetypes=(
            "workforce",
        ),
        domain="workforce",
        executable=False,
    ),

    AnalysisDefinition(
        id="workforce_segmentation",
        title="Workforce Segmentation",
        description=(
            "Segment employees by category or measure "
            "to reveal workforce structure."
        ),
        required_capabilities=(
            "segmentation",
        ),
        archetypes=(
            "workforce",
        ),
        domain="workforce",
        executable=False,
    ),

    AnalysisDefinition(
        id="headcount_trends",
        title="Headcount Trends",
        description=(
            "Track workforce size and related measures over time."
        ),
        required_capabilities=(
            "trend_analysis",
        ),
        archetypes=(
            "workforce",
        ),
        domain="workforce",
        executable=False,
    ),

    # ------------------------------------------------------------------
    # Fantasy sports
    # ------------------------------------------------------------------

    AnalysisDefinition(
        id="player_overview",
        title="Player Overview",
        description=(
            "Analyze a player's performance, usage, "
            "trends and fantasy outlook."
        ),
        required_capabilities=(
            "fantasy_signal_analysis",
        ),
        archetypes=(
            "fantasy_sports",
        ),
        domain="fantasy",
        executable=True,
    ),

    AnalysisDefinition(
        id="fantasy_signals",
        title="Fantasy Signals",
        description=(
            "Promote actionable fantasy football signals "
            "(breakout, buy-low, start/sit, waiver, regression) "
            "into structured insights."
        ),
        required_capabilities=(
            "fantasy_signal_analysis",
        ),
        archetypes=(
            "fantasy_sports",
        ),
        domain="fantasy",
        executable=True,
    ),
]


def _definition_by_id() -> dict[str, AnalysisDefinition]:
    return {
        definition.id: definition
        for definition in ANALYSIS_DEFINITIONS
    }


def _supported_capability_map(
    capabilities: list[dict] | None,
) -> dict[str, dict]:
    supported: dict[str, dict] = {}

    for item in capabilities or []:
        if not isinstance(item, dict):
            continue

        if not item.get("supported"):
            continue

        capability = item.get("capability")

        if not capability:
            continue

        supported[str(capability)] = item

    return supported


def _primary_archetype(
    dataset_archetype: dict | str | None,
) -> str | None:
    if dataset_archetype is None:
        return None

    if isinstance(dataset_archetype, str):
        value = dataset_archetype.strip()
        return value or None

    if not isinstance(dataset_archetype, dict):
        return None

    primary = (
        dataset_archetype.get("primary")
        or dataset_archetype.get("primary_archetype")
    )

    if primary is None:
        return None

    value = str(primary).strip()
    return value or None


def _candidate_confidence(
    definition: AnalysisDefinition,
    supported: dict[str, dict],
) -> float:
    if not definition.required_capabilities:
        return 1.0

    confidences = [
        float(
            supported[capability].get(
                "confidence",
                0,
            )
            or 0
        )
        for capability in definition.required_capabilities
        if capability in supported
    ]

    if not confidences:
        return 0.0

    return round(min(confidences), 2)


def _candidate_explanation(
    definition: AnalysisDefinition,
    supported: dict[str, dict],
    archetype: str | None,
) -> str:
    capability_labels = []

    for capability in definition.required_capabilities:
        item = supported.get(capability)

        if not item:
            continue

        label = item.get("label") or capability
        capability_labels.append(str(label))

    parts = []

    if capability_labels:
        parts.append(
            "Supported by "
            + ", ".join(capability_labels)
        )
    elif not definition.required_capabilities:
        parts.append(
            "Applicable as a summary over related analyses"
        )

    if archetype:
        parts.append(
            f"for the '{archetype}' dataset archetype"
        )

    if not parts:
        return definition.description

    return ". ".join(parts) + "."


def generate_analytical_candidates(
    capabilities: list[dict] | None = None,
    dataset_archetype: dict | str | None = None,
    definitions: list[AnalysisDefinition] | None = None,
) -> dict[str, Any]:
    """
    Determine which analyses are applicable from semantic capabilities.

    Returns a structured candidate list. Sales analyses appear only when
    sales/revenue (or related) capabilities and archetypes match;
    workforce datasets yield workforce-relevant candidates instead.
    """

    catalog = definitions or ANALYSIS_DEFINITIONS
    supported = _supported_capability_map(capabilities)
    archetype = _primary_archetype(dataset_archetype)

    candidates: list[dict[str, Any]] = []

    for definition in catalog:
        missing = [
            capability
            for capability in definition.required_capabilities
            if capability not in supported
        ]

        if missing:
            continue

        if definition.archetypes and archetype not in definition.archetypes:
            continue

        # Opportunity summary only when sibling domain analyses qualify.
        if definition.id == "opportunity_summary":
            has_sibling = any(
                item.id != "opportunity_summary"
                and item.domain == definition.domain
                and (
                    not item.archetypes
                    or archetype in item.archetypes
                )
                and all(
                    capability in supported
                    for capability in item.required_capabilities
                )
                for item in catalog
            )

            if not has_sibling:
                continue

        matched_capabilities = list(
            definition.required_capabilities
        )

        candidates.append(
            {
                "id": definition.id,
                "title": definition.title,
                "description": definition.description,
                "domain": definition.domain,
                "executable": definition.executable,
                "required_capabilities": list(
                    definition.required_capabilities
                ),
                "matched_capabilities": matched_capabilities,
                "archetypes": list(definition.archetypes),
                "confidence": _candidate_confidence(
                    definition,
                    supported,
                ),
                "explanation": _candidate_explanation(
                    definition,
                    supported,
                    archetype,
                ),
            }
        )

    return {
        "candidates": candidates,
        "candidate_count": len(candidates),
        "archetype": archetype,
        "supported_capabilities": sorted(
            supported.keys()
        ),
    }


def get_analysis_definition(
    analysis_id: str,
) -> AnalysisDefinition | None:
    return _definition_by_id().get(analysis_id)


def analysis_supported(
    analysis_id: str,
    context: Any,
) -> bool:
    """
    Whether an analysis module is applicable for this context.

    Prefers precomputed ``analytical_candidates`` on the context;
    otherwise evaluates capabilities + archetype on the fly.
    """

    precomputed = getattr(
        context,
        "analytical_candidates",
        None,
    )

    if isinstance(precomputed, list):
        return any(
            isinstance(item, dict)
            and item.get("id") == analysis_id
            for item in precomputed
        )

    if isinstance(precomputed, dict):
        items = precomputed.get("candidates") or []
        return any(
            isinstance(item, dict)
            and item.get("id") == analysis_id
            for item in items
        )

    result = generate_analytical_candidates(
        capabilities=getattr(
            context,
            "capabilities",
            None,
        ),
        dataset_archetype=getattr(
            context,
            "dataset_archetype",
            None,
        ),
    )

    return any(
        item.get("id") == analysis_id
        for item in result["candidates"]
    )


def candidate_analysis_ids(
    candidate_result: dict[str, Any] | list | None,
    *,
    executable_only: bool = False,
) -> set[str]:
    """Extract analysis ids from a candidate generation result."""

    if candidate_result is None:
        return set()

    if isinstance(candidate_result, list):
        items = candidate_result
    else:
        items = candidate_result.get("candidates") or []

    ids: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        analysis_id = item.get("id")

        if not analysis_id:
            continue

        if executable_only and not item.get(
            "executable",
            True,
        ):
            continue

        ids.add(str(analysis_id))

    return ids
