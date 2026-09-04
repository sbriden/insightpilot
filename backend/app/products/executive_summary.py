from __future__ import annotations

from typing import Any


PRIORITY_WEIGHT = {
    "high": 3,
    "medium": 2,
    "low": 1,
}


def _normalize_priority(
    value: str | None,
) -> str:

    if not value:
        return "low"

    normalized = (
        str(value)
        .strip()
        .lower()
    )

    if normalized in {
        "high",
        "critical",
    }:
        return "high"

    if normalized in {
        "medium",
        "warning",
    }:
        return "medium"

    return "low"


def _sort_insights(
    insights: list[Any],
) -> list[Any]:

    def sort_key(
        insight: Any,
    ) -> int:

        if isinstance(
            insight,
            dict,
        ):
            priority = _normalize_priority(
                insight.get("priority")
                or insight.get("severity")
            )
        else:
            priority = _normalize_priority(
                getattr(
                    insight,
                    "priority",
                    None,
                )
                or getattr(
                    insight,
                    "severity",
                    None,
                )
            )

        return PRIORITY_WEIGHT[priority]

    return sorted(
        insights,
        key=sort_key,
        reverse=True,
    )


def _insight_field(
    insight: Any,
    field: str,
    fallback: str = "",
) -> str:

    if isinstance(
        insight,
        dict,
    ):
        value = insight.get(field)
    else:
        value = getattr(
            insight,
            field,
            None,
        )

    return (
        str(value or "")
        .strip()
        or fallback
    )


def _analysis_title(
    analysis: Any,
) -> str:

    if isinstance(
        analysis,
        dict,
    ):
        return (
            str(
                analysis.get("title")
                or analysis.get("id")
                or ""
            ).strip()
        )

    return (
        str(
            getattr(
                analysis,
                "title",
                None,
            )
            or getattr(
                analysis,
                "id",
                None,
            )
            or ""
        ).strip()
    )


def _join_titles(
    titles: list[str],
) -> str:

    cleaned = [
        title
        for title in titles
        if title
    ]

    if not cleaned:
        return ""

    if len(cleaned) == 1:
        return cleaned[0]

    if len(cleaned) == 2:
        return (
            f"{cleaned[0]} and {cleaned[1]}"
        )

    return (
        ", ".join(cleaned[:-1])
        + f", and {cleaned[-1]}"
    )


def _build_what_we_found(
    *,
    product_name: str,
    business_purpose: str,
    analyses: list[Any],
    dashboards: list[dict],
    metrics: list[Any],
    insights: list[Any],
    change_summary: dict | None,
) -> str:

    sentences: list[str] = []

    analysis_titles = [
        _analysis_title(analysis)
        for analysis in analyses
    ]

    analysis_phrase = _join_titles(
        analysis_titles[:3]
    )

    if analysis_phrase:
        sentences.append(
            f"{product_name} combines "
            f"{analysis_phrase} to assess "
            "performance in this business area."
        )
    elif business_purpose:
        sentences.append(
            f"{product_name} focuses on "
            f"{business_purpose.rstrip('.')}."
        )
    else:
        sentences.append(
            f"{product_name} summarizes the "
            "most important patterns in this "
            "business area."
        )

    for dashboard in dashboards:

        summary = (
            str(
                dashboard.get("summary")
                or ""
            ).strip()
        )

        if not summary:
            continue

        if summary not in sentences:
            sentences.append(summary)

        if len(sentences) >= 4:
            break

    prioritized = _sort_insights(
        insights
    )

    for insight in prioritized:

        detail = (
            _insight_field(
                insight,
                "why_it_matters",
            )
            or _insight_field(
                insight,
                "message",
            )
        )

        if (
            detail
            and detail not in sentences
        ):
            sentences.append(detail)

        if len(sentences) >= 4:
            break

    if (
        isinstance(
            change_summary,
            dict,
        )
        and change_summary.get(
            "has_meaningful_changes"
        )
    ):

        overview = (
            str(
                change_summary.get(
                    "overview"
                )
                or ""
            ).strip()
        )

        if (
            overview
            and overview not in sentences
            and len(sentences) < 4
        ):
            sentences.append(overview)

    if (
        len(sentences) < 2
        and metrics
    ):

        metric = metrics[0]

        if isinstance(
            metric,
            dict,
        ):
            metric_name = (
                metric.get("name")
                or metric.get("title")
                or "Key metric"
            )
            metric_value = (
                metric.get("value")
            )
        else:
            metric_name = (
                getattr(
                    metric,
                    "name",
                    None,
                )
                or "Key metric"
            )
            metric_value = (
                getattr(
                    metric,
                    "value",
                    None,
                )
            )

        if metric_value is not None:
            sentences.append(
                f"The headline measure is "
                f"{metric_name} at "
                f"{metric_value}."
            )

    while len(sentences) < 2:

        sentences.append(
            "Review the prioritized insights "
            "below to understand the business "
            "impact for this product."
        )

    return " ".join(
        sentences[:4]
    )


def _build_what_matters(
    insights: list[Any],
) -> list[dict[str, str]]:

    prioritized = _sort_insights(
        insights
    )

    items: list[dict[str, str]] = []

    for insight in prioritized:

        priority = _normalize_priority(
            _insight_field(
                insight,
                "priority",
            )
            or _insight_field(
                insight,
                "severity",
            )
        )

        headline = (
            _insight_field(
                insight,
                "what_happened",
            )
            or _insight_field(
                insight,
                "title",
            )
        )

        detail = (
            _insight_field(
                insight,
                "why_it_matters",
            )
            or _insight_field(
                insight,
                "message",
            )
        )

        if (
            detail
            and headline
            and detail.strip() == headline.strip()
        ):
            detail = ""

        if not headline:
            continue

        items.append(
            {
                "priority": priority,

                "category": (
                    _insight_field(
                        insight,
                        "category",
                    )
                    or "Analysis"
                ),

                "headline": headline,

                "detail": detail,
            }
        )

        if len(items) >= 5:
            break

    return items


def _collect_dashboard_actions(
    dashboards: list[dict],
) -> list[str]:

    actions: list[str] = []

    for dashboard in dashboards:

        for action in (
            dashboard.get("actions")
            or []
        ):

            text = (
                str(action)
                .strip()
            )

            if (
                text
                and text not in actions
            ):
                actions.append(text)

    return actions


def _build_what_to_do_next(
    insights: list[Any],
    dashboards: list[dict],
) -> list[str]:

    actions: list[str] = []

    for insight in _sort_insights(
        insights
    ):

        action = _insight_field(
            insight,
            "recommended_action",
        )

        if (
            action
            and action not in actions
        ):
            actions.append(action)

        if len(actions) >= 4:
            return actions[:4]

    for action in _collect_dashboard_actions(
        dashboards
    ):

        if action not in actions:
            actions.append(action)

        if len(actions) >= 4:
            break

    while len(actions) < 2:

        fallback = (
            "Review the supporting analyses "
            "and confirm ownership for the "
            "highest-priority insight."
        )

        if fallback not in actions:
            actions.append(fallback)
        else:
            actions.append(
                "Schedule a follow-up to track "
                "progress on the recommended actions."
            )

    return actions[:4]


def build_product_executive_summary(
    *,
    product_name: str,
    business_purpose: str = "",
    description: str = "",
    analyses: list[Any] | None = None,
    dashboards: list[dict] | None = None,
    metrics: list[Any] | None = None,
    insights: list[Any] | None = None,
    change_summary: dict | None = None,
) -> dict[str, Any]:

    analyses = analyses or []
    dashboards = dashboards or []
    metrics = metrics or []
    insights = insights or []

    return {
        "what_we_found": _build_what_we_found(
            product_name=product_name,
            business_purpose=business_purpose,
            analyses=analyses,
            dashboards=dashboards,
            metrics=metrics,
            insights=insights,
            change_summary=change_summary,
        ),

        "what_matters": _build_what_matters(
            insights
        ),

        "what_to_do_next": _build_what_to_do_next(
            insights,
            dashboards,
        ),
    }
