"""
Build a standardized semantic analysis context for the analysis engine.

Composes concept identification, capability detection, archetype
classification, and grain determination into a single structure that
attaches to AnalysisContext — without creating a parallel pipeline.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .capability_detection import (
    CONFIDENCE_THRESHOLD,
    detect_analytical_capabilities,
)
from .concept_identification import identify_business_concepts
from .dataset_classification import classify_dataset as classify_archetype
from .grain_detection import determine_dataset_grain
from .semantic_validation import (
    accept_concept_candidates,
    validate_semantic_layer,
)


ROLE_BUCKETS: dict[str, str] = {
    "category": "dimensions",
    "measure": "measures",
    "entity": "entities",
    "date": "dates",
    "identifier": "identifiers",
    "status": "statuses",
    "geography": "geography",
}


def _empty_semantic_model() -> dict[str, Any]:
    return {
        "concepts": [],
        "dimensions": [],
        "measures": [],
        "entities": [],
        "dates": [],
        "identifiers": [],
        "statuses": [],
        "geography": [],
        "grain": {
            "grain": "unknown",
            "label": "Unknown",
            "confidence": 0.0,
            "supporting_evidence": [],
            "explanation": "",
            "alternative_grains": [],
            "all_scores": [],
        },
    }


def empty_semantic_layer() -> dict[str, Any]:
    """Default semantic layer when no dataset is available."""

    return {
        "semantic_model": _empty_semantic_model(),
        "capabilities": [],
        "dataset_archetype": {
            "primary": None,
            "confidence": 0.0,
            "alternatives": [],
        },
    }


def _is_identified(concept: dict) -> bool:
    return (
        concept.get("concept") != "Unknown"
        and float(concept.get("confidence", 0) or 0)
        >= CONFIDENCE_THRESHOLD
    )


def _bucket_concepts_by_role(
    concepts: list[dict],
) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {
        "dimensions": [],
        "measures": [],
        "entities": [],
        "dates": [],
        "identifiers": [],
        "statuses": [],
        "geography": [],
    }

    for concept in concepts:
        if not _is_identified(concept):
            continue

        bucket = ROLE_BUCKETS.get(
            concept.get("role", ""),
        )

        if bucket:
            buckets[bucket].append(concept)

    return buckets


def _columns_from_dataframe(
    df: pd.DataFrame,
    column_profiles: list[dict] | None = None,
) -> list[dict]:
    profile_by_name = {
        profile.get("name"): profile
        for profile in (column_profiles or [])
        if profile.get("name")
    }

    columns: list[dict] = []

    for column_name in df.columns:
        name = str(column_name)
        profile = profile_by_name.get(name, {})

        sample_value = None
        if len(df) > 0:
            raw = df[column_name].dropna()
            if len(raw) > 0:
                sample_value = str(raw.iloc[0])

        columns.append(
            {
                "name": name,
                "dataType": profile.get("data_type"),
                "sampleValue": sample_value,
            }
        )

    return columns


def _column_stats_from_profiles(
    df: pd.DataFrame,
    column_profiles: list[dict] | None = None,
) -> list[dict]:
    row_count = len(df)
    stats: list[dict] = []

    for profile in column_profiles or []:
        name = profile.get("name")
        if not name:
            continue

        unique_count = profile.get("unique_count")
        entry: dict[str, Any] = {
            "name": name,
            "row_count": row_count,
        }

        if unique_count is not None:
            entry["unique_count"] = int(unique_count)
            if row_count > 0:
                entry["unique_ratio"] = (
                    float(unique_count) / float(row_count)
                )

        stats.append(entry)

    return stats


def _format_dataset_archetype(
    classification: dict,
) -> dict[str, Any]:
    return {
        "primary": classification.get("primary_archetype"),
        "confidence": classification.get("confidence", 0.0),
        "alternatives": classification.get(
            "alternative_archetypes",
            [],
        ),
        "label": classification.get("label", "Unknown"),
        "explanation": classification.get("explanation", ""),
        "supporting_concepts": classification.get(
            "supporting_concepts",
            [],
        ),
    }


def _merge_llm_concepts(
    concepts: list[dict],
    llm_concepts: list[dict],
) -> list[dict]:
    """
    Overlay validated LLM concepts onto deterministic results.

    Only replaces Unknown / low-confidence entries for the same
    source column. Never invents analytical metrics.
    """
    if not llm_concepts:
        return concepts

    by_column = {
        item["sourceColumn"]: item
        for item in llm_concepts
        if item.get("sourceColumn")
    }

    merged: list[dict] = []
    for concept in concepts:
        column = concept.get("sourceColumn")
        replacement = by_column.get(column) if column else None

        if replacement and (
            concept.get("concept") == "Unknown"
            or float(concept.get("confidence", 0) or 0)
            < CONFIDENCE_THRESHOLD
        ):
            merged.append(
                {
                    "concept": replacement["concept"],
                    "sourceColumn": replacement["sourceColumn"],
                    "dataType": replacement["dataType"],
                    "confidence": replacement["confidence"],
                    "role": replacement["role"],
                }
            )
            by_column.pop(column, None)
        else:
            merged.append(concept)

    return merged


def build_semantic_layer(
    columns: list[dict],
    column_stats: list[dict] | None = None,
    llm_concept_candidates: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Build the semantic layer from column descriptors.

    Parameters
    ----------
    columns:
        Column descriptors with ``name`` and optional ``dataType`` /
        ``sampleValue`` — same shape as identify_business_concepts.
    column_stats:
        Optional uniqueness stats for grain detection.
    llm_concept_candidates:
        Optional structured concept proposals (e.g. from an LLM
        interpreting ambiguous columns). Validated before merge.

    Returns
    -------
    dict with keys ``semantic_model``, ``capabilities``,
    ``dataset_archetype``.

    The layer is validated so only structured semantic facts
    enter AnalysisContext. Optional ``llm_concept_candidates``
    (ambiguous-column proposals) are accepted only after the
    same validation gate.
    """
    if not columns:
        return validate_semantic_layer(empty_semantic_layer())

    identified = identify_business_concepts(columns)
    concepts = list(identified.get("concepts", []))

    # Future LLM semantic assistance: structured candidates only,
    # validated before they become part of the analysis context.
    if llm_concept_candidates:
        accepted = accept_concept_candidates(
            llm_concept_candidates,
            source="llm",
        )
        concepts = _merge_llm_concepts(concepts, accepted)

    capabilities_result = detect_analytical_capabilities(concepts)
    archetype_result = classify_archetype(concepts)
    grain_result = determine_dataset_grain(
        concepts,
        column_stats=column_stats,
    )

    role_buckets = _bucket_concepts_by_role(concepts)

    semantic_model = {
        "concepts": concepts,
        **role_buckets,
        "grain": grain_result,
    }

    return validate_semantic_layer(
        {
            "semantic_model": semantic_model,
            "capabilities": capabilities_result.get(
                "capabilities",
                [],
            ),
            "dataset_archetype": _format_dataset_archetype(
                archetype_result
            ),
        }
    )


def build_semantic_layer_from_dataframe(
    df: pd.DataFrame,
    column_profiles: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Build the semantic layer from an analysis dataframe.

    Uses column profiles (when available) for declared types and
    uniqueness statistics that strengthen grain detection.
    """
    columns = _columns_from_dataframe(
        df,
        column_profiles,
    )
    column_stats = _column_stats_from_profiles(
        df,
        column_profiles,
    )

    return build_semantic_layer(
        columns,
        column_stats=column_stats,
    )


def build_semantic_understanding(
    layer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Developer-facing view of semantic understanding.

    Maps the composed semantic layer onto the inspection fields
    needed to evaluate whether the semantic engine interpreted
    the dataset correctly (concepts, source columns, confidence,
    grain, measures, dimensions, dates, entities, capabilities,
    archetype).
    """
    layer = layer or empty_semantic_layer()
    model = layer.get("semantic_model") or _empty_semantic_model()
    concepts = list(model.get("concepts") or [])

    return {
        "detected_concepts": concepts,
        "source_columns": [
            concept.get("sourceColumn")
            for concept in concepts
            if concept.get("sourceColumn")
        ],
        "inferred_grain": model.get("grain")
        or _empty_semantic_model()["grain"],
        "detected_measures": list(model.get("measures") or []),
        "detected_dimensions": list(model.get("dimensions") or []),
        "detected_dates": list(model.get("dates") or []),
        "detected_entities": list(model.get("entities") or []),
        "detected_capabilities": list(
            layer.get("capabilities") or []
        ),
        "archetype_classification": dict(
            layer.get("dataset_archetype")
            or empty_semantic_layer()["dataset_archetype"]
        ),
    }


def _concept_debug_line(concept: dict) -> str:
    name = concept.get("concept", "Unknown")
    column = concept.get("sourceColumn", "?")
    confidence = float(concept.get("confidence", 0) or 0)
    role = concept.get("role", "?")
    return (
        f"  - {name} <- {column} "
        f"(role={role}, confidence={confidence:.2f})"
    )


def log_semantic_understanding(
    layer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Print a compact semantic understanding summary for developers.

    Returns the same structured payload attached to analysis
    API responses under ``semantic_understanding``.
    """
    understanding = build_semantic_understanding(layer)
    grain = understanding["inferred_grain"] or {}
    archetype = understanding["archetype_classification"] or {}
    supported_capabilities = [
        item
        for item in understanding["detected_capabilities"]
        if item.get("supported")
    ]

    print("=== Semantic understanding (debug) ===")
    print(
        f"Archetype: "
        f"{archetype.get('primary') or 'unknown'} "
        f"(confidence="
        f"{float(archetype.get('confidence', 0) or 0):.2f})"
    )
    print(
        f"Grain: "
        f"{grain.get('grain') or 'unknown'} "
        f"(confidence="
        f"{float(grain.get('confidence', 0) or 0):.2f})"
    )
    print(
        "Concepts "
        f"({len(understanding['detected_concepts'])}):"
    )
    for concept in understanding["detected_concepts"]:
        print(_concept_debug_line(concept))

    print(
        "Role buckets — "
        f"measures={len(understanding['detected_measures'])}, "
        f"dimensions={len(understanding['detected_dimensions'])}, "
        f"dates={len(understanding['detected_dates'])}, "
        f"entities={len(understanding['detected_entities'])}"
    )
    print(
        "Supported capabilities "
        f"({len(supported_capabilities)}/"
        f"{len(understanding['detected_capabilities'])}): "
        + (
            ", ".join(
                item.get("capability", "?")
                for item in supported_capabilities
            )
            or "(none)"
        )
    )
    print("=== End semantic understanding ===")

    return understanding
