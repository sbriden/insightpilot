from typing import Any, Dict, List


def _product_value(
    product: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Read a product attribute whether the
    product is a dict or a dataclass.
    """

    if isinstance(product, dict):
        return product.get(key, default)

    return getattr(product, key, default)


def normalize_field_name(
    value: str,
) -> str:

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def _mapped_semantic_fields(
    mappings: List[Dict[str, Any]],
) -> List[str]:
    """
    Return unique semantic fields that have
    an uploaded column mapped.
    """

    mapped: List[str] = []

    for mapping in mappings or []:

        required_field = mapping.get(
            "requiredField"
        )

        uploaded_field = mapping.get(
            "uploadedField"
        )

        if (
            required_field
            and uploaded_field
        ):

            if required_field not in mapped:
                mapped.append(
                    required_field
                )

    return mapped


def _serialize_opportunity(
    opportunity: Any,
) -> Dict[str, Any]:

    if isinstance(opportunity, dict):

        return {
            "field": opportunity.get(
                "field",
                "",
            ),

            "description": opportunity.get(
                "description",
                "",
            ),

            "analyses": list(
                opportunity.get(
                    "analyses",
                    [],
                )
                or []
            ),

            "metrics": list(
                opportunity.get(
                    "metrics",
                    [],
                )
                or []
            ),

            "priority": opportunity.get(
                "priority",
                "medium",
            ),

            "required": bool(
                opportunity.get(
                    "required",
                    False,
                )
            ),
        }

    return {
        "field": getattr(
            opportunity,
            "field",
            "",
        ),

        "description": getattr(
            opportunity,
            "description",
            "",
        ),

        "analyses": list(
            getattr(
                opportunity,
                "analyses",
                [],
            )
            or []
        ),

        "metrics": list(
            getattr(
                opportunity,
                "metrics",
                [],
            )
            or []
        ),

        "priority": getattr(
            opportunity,
            "priority",
            "medium",
        ),

        "required": bool(
            getattr(
                opportunity,
                "required",
                False,
            )
        ),
    }


def build_opportunities(
    product: Any,
    missing_fields: List[str],
) -> List[Dict[str, Any]]:
    """
    Return unlock context for missing fields.

    Opportunities explain which analyses and
    metrics become available when a field is added.
    """

    definitions = (
        _product_value(
            product,
            "field_opportunities",
            [],
        )
        or []
    )

    definition_by_field = {
        _serialize_opportunity(
            item
        )["field"]: _serialize_opportunity(
            item
        )
        for item in definitions
    }

    opportunities: List[Dict[str, Any]] = []

    for field in missing_fields:

        definition = definition_by_field.get(
            field
        )

        if definition is None:

            # Still surface a useful default so
            # missing fields are never silent.
            opportunities.append({
                "field": field,

                "description": (
                    "Adding this field improves "
                    "support for this data product."
                ),

                "analyses": [],

                "metrics": [],

                "priority": "medium",

                "required": field in (
                    _product_value(
                        product,
                        "required_fields",
                        [],
                    )
                    or []
                ),
            })

            continue

        opportunities.append(definition)

    return opportunities


def calculate_data_coverage(
    product: Any,
    uploaded_fields: List[str],
    mappings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Measure how completely a dataset supports
    a specific data product.

    Coverage is field readiness:
    - required fields gate analysis
    - optional fields deepen the product
    - opportunities explain what missing fields unlock
    """

    required_fields = list(
        _product_value(
            product,
            "required_fields",
            [],
        )
        or []
    )

    optional_fields = list(
        _product_value(
            product,
            "optional_fields",
            [],
        )
        or []
    )

    mapped_fields = _mapped_semantic_fields(
        mappings
    )

    mapped_field_set = set(mapped_fields)

    # Fall back to uploaded column names when
    # mappings omit an optional that already
    # matches a semantic field name.
    uploaded_field_set = {
        normalize_field_name(field)
        for field in (uploaded_fields or [])
    }

    mapped_required_fields = [
        field
        for field in required_fields
        if field in mapped_field_set
        or normalize_field_name(field)
        in uploaded_field_set
    ]

    missing_required_fields = [
        field
        for field in required_fields
        if field not in mapped_required_fields
    ]

    available_optional_fields = [
        field
        for field in optional_fields
        if field in mapped_field_set
        or normalize_field_name(field)
        in uploaded_field_set
    ]

    missing_optional_fields = [
        field
        for field in optional_fields
        if field not in available_optional_fields
    ]

    required_field_count = len(
        required_fields
    )

    mapped_required_count = len(
        mapped_required_fields
    )

    optional_field_count = len(
        optional_fields
    )

    available_optional_count = len(
        available_optional_fields
    )

    required_coverage_percent = (
        100
        if required_field_count == 0
        else round(
            (
                mapped_required_count
                / required_field_count
            )
            * 100
        )
    )

    total_fields = (
        required_field_count
        + optional_field_count
    )

    available_fields = (
        mapped_required_count
        + available_optional_count
    )

    # Product coverage = share of this product's
    # field contract that the dataset satisfies.
    coverage_percent = (
        100
        if total_fields == 0
        else round(
            (
                available_fields
                / total_fields
            )
            * 100
        )
    )

    missing_fields = (
        missing_required_fields
        + missing_optional_fields
    )

    opportunities = build_opportunities(
        product,
        missing_fields,
    )

    return {

        "product_id": _product_value(
            product,
            "id",
        ),

        "product_name": _product_value(
            product,
            "name",
        ),

        "coverage_percent":
            coverage_percent,

        "required_coverage_percent":
            required_coverage_percent,

        "required_fields":
            required_fields,

        "mapped_required_fields":
            mapped_required_fields,

        "missing_required_fields":
            missing_required_fields,

        "available_optional_fields":
            available_optional_fields,

        "missing_optional_fields":
            missing_optional_fields,

        "opportunities":
            opportunities,

        "can_analyze":
            len(missing_required_fields) == 0,

        "metadata": {

            "required_field_count":
                required_field_count,

            "mapped_required_count":
                mapped_required_count,

            "optional_field_count":
                optional_field_count,

            "available_optional_count":
                available_optional_count,

            "opportunity_count":
                len(opportunities),

            "total_field_count":
                total_fields,

            "available_field_count":
                available_fields,

        },

    }
