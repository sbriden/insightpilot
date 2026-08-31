from __future__ import annotations


DEFAULT_RECOMMENDED_ACTIONS = {
    "high": (
        "Treat this as an immediate priority and "
        "assign an owner to respond."
    ),
    "medium": (
        "Review this finding and define a "
        "follow-up action in the current "
        "planning cycle."
    ),
    "low": (
        "Monitor this pattern and revisit if "
        "the trend continues."
    ),
}


def normalize_priority(
    value: str | None,
) -> str:

    if not value:
        return "low"

    normalized = (
        str(value)
        .strip()
        .lower()
    )

    aliases = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "critical": "high",
        "warning": "medium",
        "info": "low",
        "success": "low",
    }

    return aliases.get(
        normalized,
        "low",
    )


def first_sentence(
    value: str,
) -> str:

    text = (
        str(value)
        .strip()
    )

    if not text:
        return ""

    for separator in (
        ". ",
        "! ",
        "? ",
    ):

        if separator in text:

            return (
                text.split(
                    separator,
                    1,
                )[0]
                + separator.strip()
            )

    return text


def normalize_insight_record(
    insight: dict,
    *,
    default_category: str = "Analysis",
) -> dict:

    priority = normalize_priority(
        insight.get("priority")
        or insight.get("severity")
    )

    message = (
        str(
            insight.get("message")
            or insight.get(
                "description"
            )
            or ""
        ).strip()
    )

    title = (
        str(
            insight.get("title")
            or ""
        ).strip()
    )

    what_happened = (
        str(
            insight.get(
                "what_happened"
            )
            or ""
        ).strip()
        or title
        or first_sentence(message)
        or "Analysis finding identified"
    )

    why_it_matters = (
        str(
            insight.get(
                "why_it_matters"
            )
            or ""
        ).strip()
        or message
        or what_happened
    )

    category = (
        str(
            insight.get("category")
            or default_category
        ).strip()
        or default_category
    )

    recommended_action = (
        str(
            insight.get(
                "recommended_action"
            )
            or ""
        ).strip()
        or DEFAULT_RECOMMENDED_ACTIONS[
            priority
        ]
    )

    return {
        "priority": priority,

        "severity": priority,

        "category": category,

        "what_happened":
            what_happened,

        "why_it_matters":
            why_it_matters,

        "recommended_action":
            recommended_action,

        "title":
            title or what_happened,

        "message":
            message or why_it_matters,
    }
