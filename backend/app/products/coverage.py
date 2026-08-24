from typing import Dict, List, Any


def calculate_data_coverage(
    product: Dict[str, Any],
    uploaded_fields: List[str],
    mappings: List[Dict[str, Any]],
) -> Dict[str, Any]:

    required_fields = (
        product.get("required_fields", [])
        or []
    )

    optional_fields = (
        product.get("optional_fields", [])
        or []
    )

    uploaded_field_set = {
        normalize_field_name(field)
        for field in uploaded_fields
    }

    mapped_required_fields = []

    for mapping in mappings:

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

            mapped_required_fields.append(
                required_field
            )

    mapped_required_fields = list(
        dict.fromkeys(
            mapped_required_fields
        )
    )

    missing_required_fields = [
        field
        for field in required_fields
        if field not in mapped_required_fields
    ]

    coverage_percent = (
        100
        if not required_fields
        else round(
            (
                len(
                    mapped_required_fields
                )
                /
                len(required_fields)
            )
            * 100
        )
    )

    available_optional_fields = []

    missing_optional_fields = []

    for field in optional_fields:

        normalized_field = (
            normalize_field_name(field)
        )

        if normalized_field in uploaded_field_set:

            available_optional_fields.append(
                field
            )

        else:

            missing_optional_fields.append(
                field
            )

    opportunities = (
        build_opportunities(
            product,
            missing_optional_fields
        )
    )

    return {

        "product_id":
            product.get("id"),

        "product_name":
            product.get("name"),

        "coverage_percent":
            coverage_percent,

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
            len(
                missing_required_fields
            ) == 0,

        "metadata": {

            "required_field_count":
                len(required_fields),

            "mapped_required_count":
                len(
                    mapped_required_fields
                ),

            "optional_field_count":
                len(optional_fields),

            "available_optional_count":
                len(
                    available_optional_fields
                ),

            "opportunity_count":
                len(opportunities),

        },

    }


def build_opportunities(
    product: Dict[str, Any],
    missing_optional_fields: List[str],
) -> List[Dict[str, Any]]:

    definitions = (
        product.get(
            "field_opportunities",
            []
        )
        or []
    )

    opportunities = []

    for field in missing_optional_fields:

        definition = next(
            (
                item
                for item in definitions
                if item.get("field") == field
            ),
            None,
        )

        if not definition:

            continue

        opportunities.append({

            "field":
                field,

            "description":
                definition.get(
                    "description",
                    ""
                ),

            "analyses":
                definition.get(
                    "analyses",
                    []
                ),

            "priority":
                definition.get(
                    "priority",
                    "medium"
                ),

        })

    return opportunities


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