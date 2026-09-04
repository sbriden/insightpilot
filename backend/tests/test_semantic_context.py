"""
Tests for the semantic analysis context / semantic layer builder.
"""

from __future__ import annotations

import pandas as pd

from app.core.analysis_context import AnalysisContext
from app.datasets.semantic_context import (
    build_semantic_layer,
    build_semantic_layer_from_dataframe,
    build_semantic_understanding,
    empty_semantic_layer,
    log_semantic_understanding,
)
from app.services.analysis import analyze_dataframe


REQUIRED_SEMANTIC_MODEL_KEYS = {
    "concepts",
    "dimensions",
    "measures",
    "entities",
    "dates",
    "identifiers",
    "statuses",
    "geography",
    "grain",
}

REQUIRED_SEMANTIC_UNDERSTANDING_KEYS = {
    "detected_concepts",
    "source_columns",
    "inferred_grain",
    "detected_measures",
    "detected_dimensions",
    "detected_dates",
    "detected_entities",
    "detected_capabilities",
    "archetype_classification",
}


def test_empty_semantic_layer_shape():
    layer = empty_semantic_layer()

    assert set(layer.keys()) == {
        "semantic_model",
        "capabilities",
        "dataset_archetype",
    }
    assert set(layer["semantic_model"].keys()) >= REQUIRED_SEMANTIC_MODEL_KEYS
    assert layer["dataset_archetype"]["primary"] is None
    assert layer["capabilities"] == []


def test_build_semantic_layer_sales_shape():
    layer = build_semantic_layer(
        [
            {"name": "Order ID"},
            {"name": "Order Date"},
            {"name": "Revenue"},
            {"name": "Product"},
            {"name": "Customer"},
            {"name": "Region"},
            {"name": "Status"},
        ]
    )

    assert set(layer.keys()) == {
        "semantic_model",
        "capabilities",
        "dataset_archetype",
    }

    model = layer["semantic_model"]
    assert set(model.keys()) >= REQUIRED_SEMANTIC_MODEL_KEYS
    assert len(model["concepts"]) == 7
    assert len(model["entities"]) >= 1
    assert len(model["measures"]) >= 1
    assert len(model["dates"]) >= 1
    assert isinstance(model["grain"], dict)
    assert "grain" in model["grain"]

    assert isinstance(layer["capabilities"], list)
    assert len(layer["capabilities"]) > 0
    assert all(
        "capability" in item and "supported" in item
        for item in layer["capabilities"]
    )

    archetype = layer["dataset_archetype"]
    assert "primary" in archetype
    assert "confidence" in archetype
    assert "alternatives" in archetype
    assert archetype["primary"] == "sales_revenue"
    assert archetype["confidence"] > 0


def test_build_semantic_understanding_maps_acceptance_fields():
    layer = build_semantic_layer(
        [
            {"name": "Order ID"},
            {"name": "Order Date"},
            {"name": "Revenue"},
            {"name": "Product"},
            {"name": "Customer"},
            {"name": "Region"},
            {"name": "Status"},
        ]
    )

    understanding = build_semantic_understanding(layer)

    assert set(understanding.keys()) == REQUIRED_SEMANTIC_UNDERSTANDING_KEYS
    assert understanding["detected_concepts"] == layer["semantic_model"]["concepts"]
    assert understanding["source_columns"] == [
        concept["sourceColumn"]
        for concept in layer["semantic_model"]["concepts"]
    ]
    assert all(
        "confidence" in concept
        for concept in understanding["detected_concepts"]
    )
    assert understanding["inferred_grain"] == layer["semantic_model"]["grain"]
    assert understanding["detected_measures"] == layer["semantic_model"]["measures"]
    assert understanding["detected_dimensions"] == layer["semantic_model"]["dimensions"]
    assert understanding["detected_dates"] == layer["semantic_model"]["dates"]
    assert understanding["detected_entities"] == layer["semantic_model"]["entities"]
    assert understanding["detected_capabilities"] == layer["capabilities"]
    assert (
        understanding["archetype_classification"]
        == layer["dataset_archetype"]
    )
    assert understanding["archetype_classification"]["primary"] == "sales_revenue"


def test_log_semantic_understanding_returns_payload(capsys):
    layer = build_semantic_layer(
        [
            {"name": "Customer"},
            {"name": "Revenue"},
            {"name": "Order Date"},
        ]
    )

    payload = log_semantic_understanding(layer)
    captured = capsys.readouterr()

    assert set(payload.keys()) == REQUIRED_SEMANTIC_UNDERSTANDING_KEYS
    assert "Semantic understanding (debug)" in captured.out
    assert "Archetype:" in captured.out
    assert "Grain:" in captured.out
    assert "Concepts" in captured.out


def test_build_semantic_layer_from_dataframe():
    df = pd.DataFrame(
        {
            "Customer": ["A", "B", "C"],
            "Order Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "Revenue": [100.0, 200.0, 150.0],
            "Product": ["X", "Y", "X"],
        }
    )

    column_profiles = [
        {
            "name": name,
            "unique_count": int(df[name].nunique()),
            "null_count": 0,
            "data_type": str(df[name].dtype),
            "role": "dimension",
        }
        for name in df.columns
    ]

    layer = build_semantic_layer_from_dataframe(
        df,
        column_profiles,
    )

    assert layer["dataset_archetype"]["primary"] == "sales_revenue"
    assert any(
        item["capability"] == "customer_analysis"
        and item["supported"]
        for item in layer["capabilities"]
    )
    assert layer["semantic_model"]["grain"]["grain"] in {
        "transaction",
        "customer",
        "product",
        "unknown",
    }


def test_analysis_context_exposes_semantic_layer():
    context = AnalysisContext(
        profile={},
        metrics={},
        classification={"type": "Sales & Revenue", "confidence": 1},
        semantic_model={"concepts": [], "grain": {"grain": "unknown"}},
        capabilities=[{"capability": "trend_analysis", "supported": True}],
        dataset_archetype={
            "primary": "sales_revenue",
            "confidence": 0.9,
            "alternatives": [],
        },
    )

    api = context.to_api_response()
    prompt = context.to_prompt_context()

    assert "semantic_model" in api
    assert "capabilities" in api
    assert "dataset_archetype" in api
    assert "semantic_understanding" in api
    assert set(api["semantic_understanding"].keys()) == (
        REQUIRED_SEMANTIC_UNDERSTANDING_KEYS
    )
    assert api["dataset_archetype"]["primary"] == "sales_revenue"
    assert (
        api["semantic_understanding"]["archetype_classification"]["primary"]
        == "sales_revenue"
    )

    assert "semantic_model" in prompt
    assert "capabilities" in prompt
    assert "dataset_archetype" in prompt
    assert "narrative_constraints" in prompt
    assert prompt["narrative_constraints"]["may_invent_numbers"] is False
    assert "dataframe" not in prompt


def test_analyze_dataframe_attaches_semantic_layer():
    df = pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3"],
            "order_date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "revenue": [10.0, 20.0, 30.0],
            "product": ["p1", "p2", "p1"],
        }
    )

    context = analyze_dataframe(df)

    assert isinstance(context.semantic_model, dict)
    assert set(context.semantic_model.keys()) >= REQUIRED_SEMANTIC_MODEL_KEYS
    assert isinstance(context.capabilities, list)
    assert isinstance(context.dataset_archetype, dict)
    assert "primary" in context.dataset_archetype
    assert "confidence" in context.dataset_archetype
    assert "alternatives" in context.dataset_archetype

    api = context.to_api_response()
    understanding = api["semantic_understanding"]
    assert set(understanding.keys()) == REQUIRED_SEMANTIC_UNDERSTANDING_KEYS
    assert isinstance(understanding["detected_concepts"], list)
    assert isinstance(understanding["source_columns"], list)
    assert "grain" in understanding["inferred_grain"]
    assert isinstance(understanding["detected_capabilities"], list)
    assert "primary" in understanding["archetype_classification"]

    # Legacy classification remains for existing modules.
    assert "type" in context.classification
