"""
User Story 8 — Deterministic vs AI responsibilities.

Ensures semantic detection and analytical facts stay separated
from narrative generation so AI cannot invent analytical results.
"""

from __future__ import annotations

import pytest

from app.core.analysis_context import AnalysisContext
from app.core.responsibilities import (
    AI_ALLOWED_RESPONSIBILITIES,
    DETERMINISTIC_RESPONSIBILITIES,
    NARRATIVE_PROMPT_FACT_KEYS,
    assert_ai_not_calculation_engine,
    is_ai_allowed_responsibility,
    is_deterministic_responsibility,
)
from app.datasets.semantic_context import build_semantic_layer
from app.datasets.semantic_validation import (
    SemanticValidationError,
    accept_concept_candidates,
    validate_concept_candidate,
    validate_semantic_layer,
)
from app.services.ai import generate_executive_brief
from app.services.prompts import build_executive_brief_prompt


def test_deterministic_responsibilities_cover_acceptance_criteria():
    required = {
        "data_types",
        "counts",
        "aggregations",
        "distributions",
        "comparisons",
        "trends",
        "anomalies",
        "statistical_calculations",
        "confidence_calculations",
    }
    assert required <= DETERMINISTIC_RESPONSIBILITIES
    assert "narrative_generation" in AI_ALLOWED_RESPONSIBILITIES
    assert "ambiguous_column_semantics" in AI_ALLOWED_RESPONSIBILITIES

    for name in required:
        assert is_deterministic_responsibility(name)
        assert not is_ai_allowed_responsibility(name)


def test_ai_must_not_be_calculation_engine():
    for name in DETERMINISTIC_RESPONSIBILITIES:
        with pytest.raises(ValueError, match="calculation engine"):
            assert_ai_not_calculation_engine(name)

    assert_ai_not_calculation_engine("narrative_generation")
    assert_ai_not_calculation_engine("ambiguous_column_semantics")


def test_semantic_layer_produces_structured_validated_facts():
    layer = build_semantic_layer(
        [
            {"name": "Order ID"},
            {"name": "Order Date"},
            {"name": "Revenue"},
            {"name": "Product"},
            {"name": "Customer"},
        ]
    )

    validated = validate_semantic_layer(layer)
    model = validated["semantic_model"]

    assert isinstance(model["concepts"], list)
    assert len(model["concepts"]) == 5
    for concept in model["concepts"]:
        assert set(concept.keys()) >= {
            "concept",
            "sourceColumn",
            "dataType",
            "confidence",
            "role",
        }
        assert 0.0 <= concept["confidence"] <= 1.0

    assert isinstance(validated["capabilities"], list)
    assert "primary" in validated["dataset_archetype"]
    assert isinstance(model["grain"], dict)


def test_llm_concept_candidates_require_validation_before_merge():
    # Ambiguous column that deterministic heuristics may miss.
    columns = [
        {"name": "cust_ref_x"},
        {"name": "Revenue"},
        {"name": "Order Date"},
    ]

    invalid = [
        {"concept": "Customer"},  # missing required keys
        {
            "concept": "Customer",
            "sourceColumn": "cust_ref_x",
            "dataType": "string",
            "confidence": 0.2,  # below threshold
            "role": "entity",
        },
        {
            "concept": "Customer",
            "sourceColumn": "cust_ref_x",
            "dataType": "string",
            "confidence": 0.91,
            "role": "not_a_role",
        },
    ]
    assert accept_concept_candidates(invalid) == []

    valid = [
        {
            "concept": "Customer",
            "sourceColumn": "cust_ref_x",
            "dataType": "string",
            "confidence": 0.91,
            "role": "entity",
        }
    ]
    accepted = accept_concept_candidates(valid, source="llm")
    assert len(accepted) == 1
    assert accepted[0]["provenance"] == "llm"

    layer = build_semantic_layer(
        columns,
        llm_concept_candidates=valid + invalid,
    )
    concepts_by_column = {
        item["sourceColumn"]: item
        for item in layer["semantic_model"]["concepts"]
    }
    assert concepts_by_column["cust_ref_x"]["concept"] == "Customer"
    assert concepts_by_column["cust_ref_x"]["role"] == "entity"
    # Public semantic facts do not leak internal provenance.
    assert "provenance" not in concepts_by_column["cust_ref_x"]


def test_validate_concept_candidate_rejects_malformed():
    with pytest.raises(SemanticValidationError):
        validate_concept_candidate({"concept": "Revenue"})

    with pytest.raises(SemanticValidationError):
        validate_concept_candidate(
            {
                "concept": "Revenue",
                "sourceColumn": "rev",
                "dataType": "number",
                "confidence": "high",
                "role": "measure",
            }
        )


def test_prompt_context_is_narrative_only_precomputed_facts():
    context = AnalysisContext(
        profile={"summary": {"rows": 10, "columns": 3}},
        metrics={"dataset": {"rows": 10}},
        classification={"type": "Sales & Revenue", "confidence": 1},
        semantic_model={
            "concepts": [],
            "dimensions": [],
            "measures": [],
            "entities": [],
            "dates": [],
            "identifiers": [],
            "statuses": [],
            "geography": [],
            "grain": {"grain": "unknown", "confidence": 0.0},
        },
        capabilities=[],
        dataset_archetype={
            "primary": "sales_revenue",
            "confidence": 0.9,
            "alternatives": [],
        },
        insights=[
            {
                "severity": "high",
                "description": "Duplicates found",
            }
        ],
        recommendations=["Review quality"],
    )

    prompt = context.to_prompt_context()
    facts = context.analytical_facts()

    assert set(prompt.keys()) <= NARRATIVE_PROMPT_FACT_KEYS
    assert "dataframe" not in prompt
    assert prompt["narrative_constraints"]["may_invent_numbers"] is False
    assert prompt["narrative_constraints"]["must_use_only_provided_facts"] is True
    assert "metrics" in facts
    assert "insights" in facts

    text = build_executive_brief_prompt(context)
    assert "must NOT invent numbers" in text
    assert "precomputed" in text.lower()


def test_executive_brief_does_not_invent_analytical_results():
    context = AnalysisContext(
        profile={"summary": {"rows": 42, "columns": 4}},
        metrics={},
        classification={"type": "Sales & Revenue"},
        insights=[
            {
                "severity": "high",
                "description": "Missing values exceed 20%.",
            }
        ],
        recommendations=["Investigate missingness"],
    )

    brief = generate_executive_brief(context)

    assert "42" in brief["overview"]
    assert brief["key_findings"] == ["Missing values exceed 20%."]
    assert brief["risks"] == ["Missing values exceed 20%."]
    assert brief["opportunities"] == ["Investigate missingness"]
