"""
Identify business concepts represented by dataset columns.

This module provides a schema-agnostic semantic understanding layer
that operates independently of product-specific field mappings.
"""

from __future__ import annotations

import re
from typing import Literal


ConceptRole = Literal[
    "entity",
    "measure",
    "date",
    "category",
    "identifier",
    "status",
    "geography",
]


CONCEPT_DEFINITIONS: list[dict] = [
    {
        "concept": "Customer",
        "default_role": "entity",
        "keywords": [
            "customer",
            "client",
            "account",
            "buyer",
            "subscriber",
            "patron",
            "member",
            "consumer",
            "user",
        ],
    },
    {
        "concept": "Transaction/Order",
        "default_role": "entity",
        "keywords": [
            "order",
            "transaction",
            "invoice",
            "purchase",
            "sale",
            "booking",
            "receipt",
            "payment",
        ],
    },
    {
        "concept": "Product",
        "default_role": "entity",
        "keywords": [
            "product",
            "item",
            "sku",
            "merchandise",
            "service",
            "goods",
            "article",
        ],
    },
    {
        "concept": "Revenue",
        "default_role": "measure",
        "keywords": [
            "revenue",
            "sales",
            "amount",
            "income",
            "total",
            "price",
            "cost",
            "profit",
            "margin",
            "value",
            "spend",
            "fee",
            "salary",
            "wage",
            "compensation",
            "pay",
        ],
    },
    {
        "concept": "Quantity",
        "default_role": "measure",
        "keywords": [
            "quantity",
            "qty",
            "units",
            "count",
            "volume",
            "unitsold",
        ],
    },
    {
        "concept": "Geography",
        "default_role": "geography",
        "keywords": [
            "region",
            "country",
            "state",
            "city",
            "territory",
            "location",
            "geo",
            "zip",
            "postal",
            "province",
            "market",
            "area",
        ],
    },
    {
        "concept": "Date",
        "default_role": "date",
        "keywords": [
            "date",
            "time",
            "timestamp",
            "datetime",
            "month",
            "year",
            "week",
            "period",
            "day",
        ],
    },
    {
        "concept": "Status",
        "default_role": "status",
        "keywords": [
            "status",
            "stage",
            "phase",
            "condition",
        ],
    },
    {
        "concept": "Category",
        "default_role": "category",
        "keywords": [
            "category",
            "type",
            "class",
            "segment",
            "group",
            "department",
            "division",
            "channel",
            "brand",
        ],
    },
    {
        "concept": "Employee",
        "default_role": "entity",
        "keywords": [
            "employee",
            "staff",
            "worker",
            "associate",
            "rep",
            "representative",
            "agent",
        ],
    },
    {
        "concept": "Supplier",
        "default_role": "entity",
        "keywords": [
            "supplier",
            "vendor",
            "provider",
            "manufacturer",
        ],
    },
]


IDENTIFIER_TOKENS = [
    "id",
    "key",
    "code",
    "number",
    "num",
    "no",
    "uuid",
    "guid",
]

DATE_TOKENS = [
    "date",
    "time",
    "timestamp",
    "datetime",
    "month",
    "year",
    "week",
    "period",
    "day",
]

MEASURE_TOKENS = [
    "revenue",
    "amount",
    "price",
    "cost",
    "profit",
    "margin",
    "value",
    "sales",
    "income",
    "total",
    "quantity",
    "qty",
    "units",
    "count",
    "volume",
    "spend",
    "fee",
    "salary",
    "wage",
    "compensation",
    "pay",
]

GEOGRAPHY_TOKENS = [
    "region",
    "country",
    "state",
    "city",
    "territory",
    "location",
    "geo",
    "zip",
    "postal",
    "province",
    "market",
    "area",
]

STATUS_TOKENS = [
    "status",
    "stage",
    "phase",
    "condition",
]

CATEGORY_TOKENS = [
    "category",
    "type",
    "class",
    "segment",
    "group",
    "department",
    "division",
    "channel",
    "brand",
]


DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}"),
    re.compile(r"^\d{4}/\d{2}/\d{2}"),
]

INTEGER_PATTERN = re.compile(r"^-?\d+$")
DECIMAL_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")
BOOLEAN_VALUES = {
    "true",
    "false",
    "yes",
    "no",
    "0",
    "1",
}


def normalize_field_name(
    value: str,
) -> str:

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value or "").lower(),
    )


def tokenize_column_name(
    normalized_name: str,
) -> list[str]:

    spaced = re.sub(
        r"([a-z])([0-9])",
        r"\1 \2",
        normalized_name,
    )

    spaced = re.sub(
        r"([0-9])([a-z])",
        r"\1 \2",
        spaced,
    )

    return [
        token
        for token in re.split(
            r"[^a-z0-9]+",
            spaced,
        )
        if token
    ]


def contains_token(
    tokens: list[str],
    candidates: list[str],
) -> bool:

    for candidate in candidates:

        if candidate in tokens:
            return True

        for token in tokens:

            if (
                token.endswith(candidate)
                or token.startswith(candidate)
            ):
                return True

    return False


def infer_column_data_type(
    column_name: str,
    sample_value: str | None = None,
) -> str:

    normalized_name = str(
        column_name or ""
    ).lower()

    trimmed_sample = str(
        sample_value or ""
    ).strip()

    if trimmed_sample:

        if any(
            pattern.match(trimmed_sample)
            for pattern in DATE_PATTERNS
        ):
            return "date"

        lowered = trimmed_sample.lower()

        if lowered in BOOLEAN_VALUES:
            return "boolean"

        if INTEGER_PATTERN.match(
            trimmed_sample
        ):
            return "integer"

        if DECIMAL_PATTERN.match(
            trimmed_sample
        ):
            return "number"

        return "string"

    if re.search(
        r"date|time|timestamp|datetime|month|year|week|period",
        normalized_name,
    ):
        return "date"

    if re.search(
        r"revenue|amount|price|cost|profit|margin|value|sales|income|total",
        normalized_name,
    ):
        return "number"

    if re.search(
        r"quantity|qty|count|units|volume|number|num",
        normalized_name,
    ):
        return "number"

    if re.search(
        r"id|key|code|sku|uuid|guid",
        normalized_name,
    ):
        return "string"

    if re.search(
        r"status|flag|active|enabled",
        normalized_name,
    ):
        return "string"

    return "string"


def score_concept_match(
    normalized_name: str,
    tokens: list[str],
    definition: dict,
) -> float:

    best_score = 0.0

    for keyword in definition["keywords"]:

        normalized_keyword = normalize_field_name(
            keyword
        )

        if (
            normalized_name
            == normalized_keyword
        ):
            best_score = max(
                best_score,
                0.98,
            )
            continue

        if (
            normalized_keyword
            in tokens
        ):
            best_score = max(
                best_score,
                0.92,
            )
            continue

        if (
            normalized_keyword
            in normalized_name
        ):
            best_score = max(
                best_score,
                0.82,
            )

    return best_score


def resolve_role(
    tokens: list[str],
    concept: str,
    default_role: ConceptRole,
) -> ConceptRole:

    has_date_token = contains_token(
        tokens,
        DATE_TOKENS,
    )

    has_identifier_token = contains_token(
        tokens,
        IDENTIFIER_TOKENS,
    )

    has_measure_token = contains_token(
        tokens,
        MEASURE_TOKENS,
    )

    has_geography_token = contains_token(
        tokens,
        GEOGRAPHY_TOKENS,
    )

    has_status_token = contains_token(
        tokens,
        STATUS_TOKENS,
    )

    has_category_token = contains_token(
        tokens,
        CATEGORY_TOKENS,
    )

    if has_date_token:
        return "date"

    if has_geography_token:
        return "geography"

    if has_status_token:
        return "status"

    if (
        has_identifier_token
        and not has_measure_token
    ):
        return "identifier"

    if has_measure_token:
        return "measure"

    if has_category_token:
        return "category"

    if concept == "Date":
        return "date"

    if concept == "Geography":
        return "geography"

    if concept == "Status":
        return "status"

    if concept == "Category":
        return "category"

    if concept in {
        "Revenue",
        "Quantity",
    }:
        return "measure"

    return default_role


def _definition_for_concept(
    concept: str,
) -> dict:

    for definition in CONCEPT_DEFINITIONS:

        if definition["concept"] == concept:
            return definition

    raise ValueError(
        f"Unknown concept: {concept}"
    )


def pick_best_concept(
    normalized_name: str,
    tokens: list[str],
) -> dict:

    best_match = {
        "concept": "Unknown",
        "default_role": "category",
        "confidence": 0.35,
    }

    for definition in CONCEPT_DEFINITIONS:

        score = score_concept_match(
            normalized_name,
            tokens,
            definition,
        )

        if score > best_match["confidence"]:

            best_match = {
                "concept": definition["concept"],
                "default_role": definition["default_role"],
                "confidence": score,
            }

    date_definition = _definition_for_concept(
        "Date"
    )

    transaction_definition = _definition_for_concept(
        "Transaction/Order"
    )

    date_score = score_concept_match(
        normalized_name,
        tokens,
        date_definition,
    )

    transaction_score = score_concept_match(
        normalized_name,
        tokens,
        transaction_definition,
    )

    if (
        date_score >= 0.82
        and transaction_score >= 0.82
        and contains_token(
            tokens,
            DATE_TOKENS,
        )
    ):

        best_match = {
            "concept": "Date",
            "default_role": "date",
            "confidence": max(
                date_score,
                transaction_score,
            ),
        }

    if (
        transaction_score >= 0.82
        and contains_token(
            tokens,
            IDENTIFIER_TOKENS,
        )
        and not contains_token(
            tokens,
            DATE_TOKENS,
        )
    ):

        best_match = {
            "concept": "Transaction/Order",
            "default_role": "entity",
            "confidence": transaction_score,
        }

    return best_match


def identify_column_concept(
    column_name: str,
    sample_value: str | None = None,
    declared_data_type: str | None = None,
) -> dict:

    normalized_name = normalize_field_name(
        column_name
    )

    tokens = tokenize_column_name(
        normalized_name
    )

    match = pick_best_concept(
        normalized_name,
        tokens,
    )

    role = resolve_role(
        tokens,
        match["concept"],
        match["default_role"],
    )

    data_type = (
        declared_data_type
        or infer_column_data_type(
            column_name,
            sample_value,
        )
    )

    return {
        "concept": match["concept"],
        "sourceColumn": column_name,
        "dataType": data_type,
        "confidence": round(
            match["confidence"],
            2,
        ),
        "role": role,
    }


def identify_business_concepts(
    columns: list[dict],
) -> dict:

    concepts = []

    for column in columns:

        concepts.append(
            identify_column_concept(
                column.get("name", ""),
                column.get("sampleValue"),
                column.get("dataType"),
            )
        )

    identified_count = sum(
        1
        for concept in concepts
        if (
            concept["concept"] != "Unknown"
            and concept["confidence"] >= 0.65
        )
    )

    return {
        "concepts": concepts,
        "columnCount": len(columns),
        "identifiedCount": identified_count,
    }
