import re
from difflib import SequenceMatcher


def normalize_field_name(value: str) -> str:
    """
    Normalize field names so that common variations
    can be compared.

    Examples:

        Customer ID
        customer_id
        CUSTOMER-ID

    all become:

        customerid
    """

    if not value:
        return ""

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower(),
    )


def similarity(
    left: str,
    right: str,
) -> float:

    return SequenceMatcher(
        None,
        normalize_field_name(left),
        normalize_field_name(right),
    ).ratio()


def suggest_field_mapping(
    uploaded_fields: list[str],
    required_fields: list[str],
    optional_fields: list[str],
) -> dict:

    mappings = []

    all_required = set(required_fields)
    all_optional = set(optional_fields)

    for required_field in required_fields:

        best_field = None
        best_score = 0.0
        match_type = "unmapped"

        for uploaded_field in uploaded_fields:

            normalized_required = normalize_field_name(
                required_field
            )

            normalized_uploaded = normalize_field_name(
                uploaded_field
            )

            if (
                normalized_required
                == normalized_uploaded
            ):

                best_field = uploaded_field
                best_score = 1.0
                match_type = "exact"

                break

            score = similarity(
                required_field,
                uploaded_field,
            )

            if score > best_score:
                best_score = score
                best_field = uploaded_field

                if score >= 0.90:
                    match_type = "normalized"

                elif score >= 0.70:
                    match_type = "fuzzy"

                else:
                    match_type = "unmapped"

        valid = (
            best_field is not None
            and best_score >= 0.70
        )

        if not valid:
            best_field = None
            match_type = "unmapped"

        mappings.append(
            {
                "requiredField": required_field,
                "uploadedField": best_field,
                "matchType": match_type,
                "confidence": round(
                    best_score,
                    3,
                ),
                "required": True,
                "valid": valid,
            }
        )

    for optional_field in optional_fields:

        best_field = None
        best_score = 0.0
        match_type = "unmapped"

        for uploaded_field in uploaded_fields:

            normalized_optional = normalize_field_name(
                optional_field
            )

            normalized_uploaded = normalize_field_name(
                uploaded_field
            )

            if (
                normalized_optional
                == normalized_uploaded
            ):

                best_field = uploaded_field
                best_score = 1.0
                match_type = "exact"

                break

            score = similarity(
                optional_field,
                uploaded_field,
            )

            if score > best_score:
                best_score = score
                best_field = uploaded_field

                if score >= 0.90:
                    match_type = "normalized"

                elif score >= 0.70:
                    match_type = "fuzzy"

                else:
                    match_type = "unmapped"

        valid = (
            best_field is not None
            and best_score >= 0.70
        )

        if not valid:
            best_field = None
            match_type = "unmapped"

        mappings.append(
            {
                "requiredField": optional_field,
                "uploadedField": best_field,
                "matchType": match_type,
                "confidence": round(
                    best_score,
                    3,
                ),
                "required": False,
                "valid": valid,
            }
        )

    matched_required = [
        mapping["requiredField"]
        for mapping in mappings
        if (
            mapping["required"]
            and mapping["valid"]
        )
    ]

    matched_optional = [
        mapping["requiredField"]
        for mapping in mappings
        if (
            not mapping["required"]
            and mapping["valid"]
        )
    ]

    missing_required = [
        field
        for field in required_fields
        if field not in matched_required
    ]

    available_optional = [
        field
        for field in optional_fields
        if field in matched_optional
    ]

    required_coverage = (
        (
            len(matched_required)
            / len(required_fields)
        )
        * 100
        if required_fields
        else 100
    )

    total_fields = (
        len(required_fields)
        + len(optional_fields)
    )

    matched_fields = (
        len(matched_required)
        + len(matched_optional)
    )

    overall_coverage = (
        (
            matched_fields
            / total_fields
        )
        * 100
        if total_fields
        else 100
    )

    return {
        "mappings": mappings,

        "requiredFields": required_fields,

        "optionalFields": optional_fields,

        "matchedRequiredFields":
            matched_required,

        "matchedOptionalFields":
            matched_optional,

        "missingRequiredFields":
            missing_required,

        "availableOptionalFields":
            available_optional,

        "requiredCoverage":
            round(required_coverage),

        "overallCoverage":
            round(overall_coverage),

        "canAnalyze":
            len(missing_required) == 0,
    }