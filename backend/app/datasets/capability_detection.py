"""
Detect analytical capabilities supported by a dataset's semantic model.

Consumes identified business concepts and returns a structured capability
map the analysis engine can use to select appropriate analyses dynamically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


CONFIDENCE_THRESHOLD = 0.65

ENTITY_CONCEPTS = {
    "Customer",
    "Product",
    "Employee",
    "Supplier",
    "Transaction/Order",
}

MEASURE_CONCEPTS = {
    "Revenue",
    "Quantity",
}


@dataclass(frozen=True)
class CapabilityDefinition:
    capability: str
    label: str
    required_concepts: list[str]
    evaluate: Callable[["SemanticInventory"], "_EvaluationResult"]


@dataclass
class _EvaluationResult:
    supported: bool
    confidence: float
    matched_columns: list[dict]
    explanation: str


class SemanticInventory:
    """Indexed view of high-confidence business concepts."""

    def __init__(
        self,
        concepts: list[dict],
    ) -> None:

        self.concepts = [
            concept
            for concept in concepts
            if concept.get(
                "confidence",
                0,
            )
            >= CONFIDENCE_THRESHOLD
            and concept.get(
                "concept",
            )
            != "Unknown"
        ]

    def by_concept(
        self,
        concept: str,
    ) -> list[dict]:

        return [
            item
            for item in self.concepts
            if item.get("concept") == concept
        ]

    def by_role(
        self,
        role: str,
    ) -> list[dict]:

        return [
            item
            for item in self.concepts
            if item.get("role") == role
        ]

    def has_concept(
        self,
        concept: str,
    ) -> tuple[bool, float, list[dict]]:

        matches = self.by_concept(
            concept
        )

        if not matches:
            return (
                False,
                0.0,
                [],
            )

        confidence = min(
            match["confidence"]
            for match in matches
        )

        return (
            True,
            confidence,
            matches,
        )

    def has_role(
        self,
        role: str,
    ) -> tuple[bool, float, list[dict]]:

        matches = self.by_role(
            role
        )

        if not matches:
            return (
                False,
                0.0,
                [],
            )

        confidence = min(
            match["confidence"]
            for match in matches
        )

        return (
            True,
            confidence,
            matches,
        )

    def has_any_concept(
        self,
        concepts: list[str],
    ) -> tuple[bool, float, list[dict]]:

        all_matches: list[dict] = []

        for concept in concepts:

            (
                found,
                _,
                matches,
            ) = self.has_concept(
                concept
            )

            if found:
                all_matches.extend(
                    matches
                )

        if not all_matches:
            return (
                False,
                0.0,
                [],
            )

        confidence = min(
            match["confidence"]
            for match in all_matches
        )

        return (
            True,
            confidence,
            all_matches,
        )

    def entity_concepts(
        self,
    ) -> list[dict]:

        return [
            item
            for item in self.concepts
            if item.get("concept")
            in ENTITY_CONCEPTS
        ]

    def distinct_entity_concept_names(
        self,
    ) -> set[str]:

        return {
            item["concept"]
            for item in self.entity_concepts()
        }


def _format_columns(
    matches: list[dict],
) -> str:

    if not matches:
        return ""

    labels = []

    for match in matches:

        labels.append(
            f"'{match['sourceColumn']}' "
            f"({match['concept']})"
        )

    return ", ".join(
        labels
    )


def _combine_confidence(
    *values: float,
) -> float:

    positive = [
        value
        for value in values
        if value > 0
    ]

    if not positive:
        return 0.0

    return round(
        min(positive),
        2,
    )


def _evaluate_time_series(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    (
        has_date,
        date_confidence,
        date_matches,
    ) = inventory.has_role(
        "date"
    )

    (
        has_measure,
        measure_confidence,
        measure_matches,
    ) = inventory.has_role(
        "measure"
    )

    matched = (
        date_matches
        + measure_matches
    )

    if has_date and has_measure:

        return _EvaluationResult(
            supported=True,
            confidence=_combine_confidence(
                date_confidence,
                measure_confidence,
            ),
            matched_columns=matched,
            explanation=(
                "Supported because the dataset includes "
                f"a date column ({_format_columns(date_matches)}) "
                "and a numeric measure "
                f"({_format_columns(measure_matches)}), "
                "enabling analysis over time."
            ),
        )

    missing = []

    if not has_date:
        missing.append(
            "a date or time column"
        )

    if not has_measure:
        missing.append(
            "a numeric measure such as revenue or quantity"
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=matched,
        explanation=(
            "Requires "
            + " and ".join(missing)
            + "."
            + (
                f" Found {_format_columns(matched)}."
                if matched
                else ""
            )
        ),
    )


def _evaluate_trend_analysis(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    result = _evaluate_time_series(
        inventory
    )

    if result.supported:

        result.explanation = (
            "Supported because trend analysis needs a time "
            "dimension and a measure; "
            + result.explanation[
                result.explanation.find(
                    "the dataset"
                ):
            ]
        )

    else:

        result.explanation = (
            "Trend analysis requires a date column and a "
            "numeric measure to compare values across periods."
            + (
                f" Found {_format_columns(result.matched_columns)}."
                if result.matched_columns
                else ""
            )
        )

    return result


def _evaluate_category_comparison(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    (
        has_category,
        category_confidence,
        category_matches,
    ) = inventory.has_role(
        "category"
    )

    (
        has_measure,
        measure_confidence,
        measure_matches,
    ) = inventory.has_role(
        "measure"
    )

    matched = (
        category_matches
        + measure_matches
    )

    if has_category and has_measure:

        return _EvaluationResult(
            supported=True,
            confidence=_combine_confidence(
                category_confidence,
                measure_confidence,
            ),
            matched_columns=matched,
            explanation=(
                "Supported because the dataset includes "
                f"a categorical dimension ({_format_columns(category_matches)}) "
                "and a measure "
                f"({_format_columns(measure_matches)}) "
                "for comparing groups."
            ),
        )

    missing = []

    if not has_category:
        missing.append(
            "a categorical column such as department, segment, or type"
        )

    if not has_measure:
        missing.append(
            "a numeric measure"
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=matched,
        explanation=(
            "Requires "
            + " and ".join(missing)
            + "."
            + (
                f" Found {_format_columns(matched)}."
                if matched
                else ""
            )
        ),
    )


def _evaluate_segmentation(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    (
        has_entity,
        entity_confidence,
        entity_matches,
    ) = inventory.has_role(
        "entity"
    )

    (
        has_category,
        category_confidence,
        category_matches,
    ) = inventory.has_role(
        "category"
    )

    (
        has_measure,
        measure_confidence,
        measure_matches,
    ) = inventory.has_role(
        "measure"
    )

    has_segment_dimension = (
        has_category
        or has_measure
    )

    matched = (
        entity_matches
        + category_matches
        + measure_matches
    )

    if has_entity and has_segment_dimension:

        dimension_matches = (
            category_matches
            if has_category
            else measure_matches
        )

        dimension_label = (
            "category"
            if has_category
            else "measure"
        )

        return _EvaluationResult(
            supported=True,
            confidence=_combine_confidence(
                entity_confidence,
                category_confidence
                if has_category
                else measure_confidence,
            ),
            matched_columns=matched,
            explanation=(
                "Supported because the dataset includes "
                f"an entity ({_format_columns(entity_matches)}) "
                f"and a {dimension_label} "
                f"({_format_columns(dimension_matches)}) "
                "for grouping or segmenting records."
            ),
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=matched,
        explanation=(
            "Segmentation requires an entity column and either "
            "a category or measure to define segments."
            + (
                f" Found {_format_columns(matched)}."
                if matched
                else ""
            )
        ),
    )


def _evaluate_concept_analysis(
    inventory: SemanticInventory,
    concept: str,
    label: str,
) -> _EvaluationResult:

    (
        found,
        confidence,
        matches,
    ) = inventory.has_concept(
        concept
    )

    if found:

        return _EvaluationResult(
            supported=True,
            confidence=confidence,
            matched_columns=matches,
            explanation=(
                f"Supported because {_format_columns(matches)} "
                f"identifies {concept.lower()} data suitable "
                f"for {label}."
            ),
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=[],
        explanation=(
            f"{label.capitalize()} requires a column that "
            f"represents {concept.lower()} information, "
            "which was not identified in this dataset."
        ),
    )


def _evaluate_geographic_analysis(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    (
        found_concept,
        concept_confidence,
        concept_matches,
    ) = inventory.has_concept(
        "Geography"
    )

    (
        found_role,
        role_confidence,
        role_matches,
    ) = inventory.has_role(
        "geography"
    )

    matches = (
        concept_matches
        or role_matches
    )

    if found_concept or found_role:

        return _EvaluationResult(
            supported=True,
            confidence=_combine_confidence(
                concept_confidence,
                role_confidence,
            ),
            matched_columns=matches,
            explanation=(
                "Supported because the dataset includes "
                f"geographic columns ({_format_columns(matches)})."
            ),
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=[],
        explanation=(
            "Geographic analysis requires location columns "
            "such as region, country, city, or territory."
        ),
    )


def _evaluate_aggregation(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    (
        found,
        confidence,
        matches,
    ) = inventory.has_role(
        "measure"
    )

    if found:

        return _EvaluationResult(
            supported=True,
            confidence=confidence,
            matched_columns=matches,
            explanation=(
                "Supported because the dataset includes "
                f"numeric measures ({_format_columns(matches)}) "
                "that can be summed, averaged, or counted."
            ),
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=[],
        explanation=(
            "Aggregation requires at least one numeric measure "
            "column such as revenue, amount, or quantity."
        ),
    )


def _evaluate_distribution_outlier_analysis(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    result = _evaluate_aggregation(
        inventory
    )

    if result.supported:

        result.explanation = (
            "Supported because distribution and outlier analysis "
            "needs numeric measures; found "
            f"{_format_columns(result.matched_columns)}."
        )

    else:

        result.explanation = (
            "Distribution and outlier analysis requires numeric "
            "measure columns to analyze spread and extremes."
        )

    return result


def _evaluate_status_analysis(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    (
        found_concept,
        concept_confidence,
        concept_matches,
    ) = inventory.has_concept(
        "Status"
    )

    (
        found_role,
        role_confidence,
        role_matches,
    ) = inventory.has_role(
        "status"
    )

    matches = (
        concept_matches
        or role_matches
    )

    if found_concept or found_role:

        return _EvaluationResult(
            supported=True,
            confidence=_combine_confidence(
                concept_confidence,
                role_confidence,
            ),
            matched_columns=matches,
            explanation=(
                "Supported because the dataset includes "
                f"status columns ({_format_columns(matches)}) "
                "for pipeline or lifecycle analysis."
            ),
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=[],
        explanation=(
            "Status analysis requires columns representing "
            "state, stage, or condition."
        ),
    )


def _evaluate_relationship_analysis(
    inventory: SemanticInventory,
) -> _EvaluationResult:

    entity_names = (
        inventory.distinct_entity_concept_names()
    )

    entity_matches = (
        inventory.entity_concepts()
    )

    (
        has_measure,
        measure_confidence,
        measure_matches,
    ) = inventory.has_role(
        "measure"
    )

    has_multiple_entities = (
        len(entity_names) >= 2
    )

    has_entity_with_dimension = (
        len(entity_names) >= 1
        and (
            bool(
                inventory.by_role(
                    "category"
                )
            )
            or bool(
                inventory.by_role(
                    "date"
                )
            )
            or bool(
                inventory.by_role(
                    "geography"
                )
            )
            or has_measure
        )
    )

    matched = (
        entity_matches
        + measure_matches
    )

    if has_multiple_entities:

        return _EvaluationResult(
            supported=True,
            confidence=min(
                match["confidence"]
                for match in entity_matches
            ),
            matched_columns=entity_matches,
            explanation=(
                "Supported because the dataset links multiple "
                f"entity types ({_format_columns(entity_matches)}), "
                "enabling relationship analysis."
            ),
        )

    if has_entity_with_dimension:

        dimension_matches = (
            inventory.by_role(
                "category"
            )
            + inventory.by_role(
                "date"
            )
            + inventory.by_role(
                "geography"
            )
            + measure_matches
        )

        return _EvaluationResult(
            supported=True,
            confidence=_combine_confidence(
                min(
                    match["confidence"]
                    for match in entity_matches
                ),
                measure_confidence,
            ),
            matched_columns=(
                entity_matches
                + dimension_matches
            ),
            explanation=(
                "Supported because the dataset combines "
                f"entities ({_format_columns(entity_matches)}) "
                "with additional dimensions for "
                "cross-dimensional analysis."
            ),
        )

    return _EvaluationResult(
        supported=False,
        confidence=0.0,
        matched_columns=matched,
        explanation=(
            "Relationship analysis requires multiple related "
            "entities or an entity paired with a category, "
            "date, geography, or measure."
            + (
                f" Found {_format_columns(matched)}."
                if matched
                else ""
            )
        ),
    )


CAPABILITY_DEFINITIONS: list[CapabilityDefinition] = [
    CapabilityDefinition(
        capability="time_series_analysis",
        label="Time-series analysis",
        required_concepts=["Date", "Revenue"],
        evaluate=_evaluate_time_series,
    ),
    CapabilityDefinition(
        capability="trend_analysis",
        label="Trend analysis",
        required_concepts=["Date", "Revenue"],
        evaluate=_evaluate_trend_analysis,
    ),
    CapabilityDefinition(
        capability="category_comparison",
        label="Category comparison",
        required_concepts=["Category", "Revenue"],
        evaluate=_evaluate_category_comparison,
    ),
    CapabilityDefinition(
        capability="segmentation",
        label="Segmentation",
        required_concepts=["Customer", "Category"],
        evaluate=_evaluate_segmentation,
    ),
    CapabilityDefinition(
        capability="customer_analysis",
        label="Customer analysis",
        required_concepts=["Customer"],
        evaluate=lambda inventory: _evaluate_concept_analysis(
            inventory,
            "Customer",
            "customer analysis",
        ),
    ),
    CapabilityDefinition(
        capability="product_analysis",
        label="Product analysis",
        required_concepts=["Product"],
        evaluate=lambda inventory: _evaluate_concept_analysis(
            inventory,
            "Product",
            "product analysis",
        ),
    ),
    CapabilityDefinition(
        capability="geographic_analysis",
        label="Geographic analysis",
        required_concepts=["Geography"],
        evaluate=_evaluate_geographic_analysis,
    ),
    CapabilityDefinition(
        capability="transaction_analysis",
        label="Transaction analysis",
        required_concepts=["Transaction/Order"],
        evaluate=lambda inventory: _evaluate_concept_analysis(
            inventory,
            "Transaction/Order",
            "transaction analysis",
        ),
    ),
    CapabilityDefinition(
        capability="aggregation",
        label="Aggregation",
        required_concepts=["Revenue"],
        evaluate=_evaluate_aggregation,
    ),
    CapabilityDefinition(
        capability="distribution_outlier_analysis",
        label="Distribution/outlier analysis",
        required_concepts=["Revenue"],
        evaluate=_evaluate_distribution_outlier_analysis,
    ),
    CapabilityDefinition(
        capability="status_analysis",
        label="Status analysis",
        required_concepts=["Status"],
        evaluate=_evaluate_status_analysis,
    ),
    CapabilityDefinition(
        capability="relationship_analysis",
        label="Relationship analysis",
        required_concepts=["Customer", "Product"],
        evaluate=_evaluate_relationship_analysis,
    ),
]


def detect_analytical_capabilities(
    concepts: list[dict],
) -> dict:

    inventory = SemanticInventory(
        concepts
    )

    capabilities = []

    supported_count = 0

    for definition in CAPABILITY_DEFINITIONS:

        result = definition.evaluate(
            inventory
        )

        if result.supported:
            supported_count += 1

        capabilities.append(
            {
                "capability": definition.capability,
                "label": definition.label,
                "supported": result.supported,
                "confidence": result.confidence,
                "required_concepts": definition.required_concepts,
                "explanation": result.explanation,
                "matched_columns": [
                    match["sourceColumn"]
                    for match in result.matched_columns
                ],
            }
        )

    return {
        "capabilities": capabilities,
        "supported_count": supported_count,
        "total_count": len(
            capabilities
        ),
    }
