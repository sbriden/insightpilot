"""
Validate structured semantic facts before analysis context.

Deterministic concept identification already emits structured
facts. When an LLM eventually proposes ambiguous-column
interpretations, those candidates must pass the same validation
gate before merging into the semantic layer / AnalysisContext.
"""

from __future__ import annotations

from typing import Any

from .capability_detection import CONFIDENCE_THRESHOLD


VALID_ROLES: frozenset[str] = frozenset(
    {
        "entity",
        "measure",
        "date",
        "category",
        "identifier",
        "status",
        "geography",
    }
)

VALID_DATA_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "number",
        "integer",
        "float",
        "date",
        "boolean",
        "unknown",
        # Pandas dtype strings may appear when profiles pass through.
        "object",
        "int64",
        "float64",
        "bool",
        "datetime64[ns]",
        "category",
    }
)

REQUIRED_CONCEPT_KEYS: frozenset[str] = frozenset(
    {
        "concept",
        "sourceColumn",
        "dataType",
        "confidence",
        "role",
    }
)

REQUIRED_SEMANTIC_LAYER_KEYS: frozenset[str] = frozenset(
    {
        "semantic_model",
        "capabilities",
        "dataset_archetype",
    }
)

REQUIRED_SEMANTIC_MODEL_KEYS: frozenset[str] = frozenset(
    {
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


class SemanticValidationError(ValueError):
    """Raised when a semantic candidate or layer is invalid."""


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise SemanticValidationError(
            f"confidence must be numeric, got {value!r}"
        ) from exc

    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return round(confidence, 4)


def _normalize_data_type(value: Any) -> str:
    raw = str(value or "unknown").strip()
    if not raw:
        return "unknown"

    lowered = raw.lower()
    if lowered in VALID_DATA_TYPES:
        return lowered if lowered != "float" else "number"

    # Allow opaque profile dtypes; normalize common aliases.
    if lowered in {"int", "int32", "int16"}:
        return "integer"
    if lowered in {"float", "float32", "double"}:
        return "number"
    if "datetime" in lowered or lowered.startswith("date"):
        return "date"
    if lowered in {"bool", "boolean"}:
        return "boolean"

    return raw


def validate_concept_candidate(
    candidate: dict[str, Any] | None,
    *,
    source: str = "deterministic",
) -> dict[str, Any]:
    """
    Validate one structured business-concept fact.

    ``source`` records provenance (``deterministic`` or ``llm``).
    LLM candidates must be structured and pass this gate before
    becoming part of the analysis context.
    """
    if not isinstance(candidate, dict):
        raise SemanticValidationError(
            "concept candidate must be a dict"
        )

    missing = REQUIRED_CONCEPT_KEYS - set(candidate.keys())
    if missing:
        raise SemanticValidationError(
            f"concept candidate missing keys: {sorted(missing)}"
        )

    concept_name = str(candidate.get("concept") or "").strip()
    source_column = str(
        candidate.get("sourceColumn") or ""
    ).strip()
    role = str(candidate.get("role") or "").strip().lower()

    if not concept_name:
        raise SemanticValidationError("concept must be non-empty")
    if not source_column:
        raise SemanticValidationError(
            "sourceColumn must be non-empty"
        )
    if role not in VALID_ROLES:
        raise SemanticValidationError(
            f"role must be one of {sorted(VALID_ROLES)}, got {role!r}"
        )

    confidence = _clamp_confidence(candidate.get("confidence"))
    data_type = _normalize_data_type(candidate.get("dataType"))

    return {
        "concept": concept_name,
        "sourceColumn": source_column,
        "dataType": data_type,
        "confidence": confidence,
        "role": role,
        "provenance": source,
    }


def accept_concept_candidates(
    candidates: list[dict[str, Any]] | None,
    *,
    source: str = "llm",
    min_confidence: float = CONFIDENCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Accept only structured, valid concept candidates.

    Invalid candidates are dropped (not merged into context).
    Used as the gate for future LLM semantic assistance.
    """
    accepted: list[dict[str, Any]] = []

    for candidate in candidates or []:
        try:
            validated = validate_concept_candidate(
                candidate,
                source=source,
            )
        except SemanticValidationError:
            continue

        if validated["confidence"] < min_confidence:
            continue
        if validated["concept"] == "Unknown":
            continue

        accepted.append(validated)

    return accepted


def _validate_grain(grain: Any) -> dict[str, Any]:
    if not isinstance(grain, dict):
        raise SemanticValidationError(
            "semantic_model.grain must be a dict"
        )

    name = str(grain.get("grain") or "unknown").strip() or "unknown"
    confidence = _clamp_confidence(grain.get("confidence", 0.0))

    return {
        **grain,
        "grain": name,
        "confidence": confidence,
        "label": str(grain.get("label") or name.title()),
        "supporting_evidence": list(
            grain.get("supporting_evidence") or []
        ),
        "explanation": str(grain.get("explanation") or ""),
        "alternative_grains": list(
            grain.get("alternative_grains") or []
        ),
        "all_scores": list(grain.get("all_scores") or []),
    }


def _validate_capability(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SemanticValidationError(
            "capability entry must be a dict"
        )

    capability = str(item.get("capability") or "").strip()
    if not capability:
        raise SemanticValidationError(
            "capability id must be non-empty"
        )

    return {
        **item,
        "capability": capability,
        "label": str(item.get("label") or capability),
        "supported": bool(item.get("supported")),
        "confidence": _clamp_confidence(
            item.get("confidence", 0.0)
        ),
        "required_concepts": list(
            item.get("required_concepts") or []
        ),
        "explanation": str(item.get("explanation") or ""),
        "matched_columns": list(
            item.get("matched_columns") or []
        ),
    }


def _bucket_concepts(
    concepts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "dimensions": [],
        "measures": [],
        "entities": [],
        "dates": [],
        "identifiers": [],
        "statuses": [],
        "geography": [],
    }

    for concept in concepts:
        if (
            concept.get("concept") == "Unknown"
            or float(concept.get("confidence", 0) or 0)
            < CONFIDENCE_THRESHOLD
        ):
            continue

        bucket = ROLE_BUCKETS.get(concept.get("role", ""))
        if bucket:
            buckets[bucket].append(concept)

    return buckets


def validate_semantic_layer(
    layer: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Normalize and validate a composed semantic layer.

    Ensures AnalysisContext only receives structured semantic facts
    with required keys, clamped confidence, and consistent roles.
    """
    if not isinstance(layer, dict):
        raise SemanticValidationError(
            "semantic layer must be a dict"
        )

    missing = REQUIRED_SEMANTIC_LAYER_KEYS - set(layer.keys())
    if missing:
        raise SemanticValidationError(
            f"semantic layer missing keys: {sorted(missing)}"
        )

    model = layer.get("semantic_model")
    if not isinstance(model, dict):
        raise SemanticValidationError(
            "semantic_model must be a dict"
        )

    model_missing = REQUIRED_SEMANTIC_MODEL_KEYS - set(model.keys())
    if model_missing:
        raise SemanticValidationError(
            f"semantic_model missing keys: {sorted(model_missing)}"
        )

    concepts: list[dict[str, Any]] = []
    for raw in model.get("concepts") or []:
        validated = validate_concept_candidate(
            raw,
            source=str(raw.get("provenance") or "deterministic"),
        )
        # Provenance is internal to the validation gate; public
        # semantic model keeps the established concept shape.
        concepts.append(
            {
                "concept": validated["concept"],
                "sourceColumn": validated["sourceColumn"],
                "dataType": validated["dataType"],
                "confidence": validated["confidence"],
                "role": validated["role"],
            }
        )

    role_buckets = _bucket_concepts(concepts)
    grain = _validate_grain(model.get("grain"))

    capabilities = [
        _validate_capability(item)
        for item in (layer.get("capabilities") or [])
    ]

    archetype = layer.get("dataset_archetype")
    if not isinstance(archetype, dict):
        raise SemanticValidationError(
            "dataset_archetype must be a dict"
        )

    validated_archetype = {
        **archetype,
        "primary": archetype.get("primary"),
        "confidence": _clamp_confidence(
            archetype.get("confidence", 0.0)
        ),
        "alternatives": list(
            archetype.get("alternatives") or []
        ),
        "label": str(archetype.get("label") or "Unknown"),
        "explanation": str(archetype.get("explanation") or ""),
        "supporting_concepts": list(
            archetype.get("supporting_concepts") or []
        ),
    }

    return {
        "semantic_model": {
            "concepts": concepts,
            **role_buckets,
            "grain": grain,
        },
        "capabilities": capabilities,
        "dataset_archetype": validated_archetype,
    }
