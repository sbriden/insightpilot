import pandas as pd

from .models import (
    AnalysisDashboard,
    MetricCard,
    Visualization,
    Insight,
)


class AnalysisBuilder:

    def __init__(
        self,
        dashboard: AnalysisDashboard,
    ):
        self.dashboard = dashboard

    #
    # DATASETS
    #

    def dataset(
        self,
        name: str,
        data,
    ):

        if hasattr(
            data,
            "to_dict",
        ):
            data = data.to_dict(
                orient="records"
            )

        self.dashboard.datasets[
            name
        ] = data

    #
    # METRICS
    #

    def metric(
        self,
        id,
        title,
        value,
        subtitle=None,
    ):

        self.dashboard.metrics.append(
            MetricCard(
                id=id,
                title=title,
                value=str(value),
                subtitle=subtitle,
            )
        )

    def currency_metric(
        self,
        id,
        title,
        value,
        subtitle=None,
    ):

        self.metric(
            id=id,
            title=title,
            value=f"${value:,.0f}",
            subtitle=subtitle,
        )

    def percent_metric(
        self,
        id,
        title,
        value,
        subtitle=None,
    ):

        self.metric(
            id=id,
            title=title,
            value=f"{value:.1%}",
            subtitle=subtitle,
        )

    def integer_metric(
        self,
        id,
        title,
        value,
        subtitle=None,
    ):

        self.metric(
            id=id,
            title=title,
            value=f"{value:,}",
            subtitle=subtitle,
        )

    #
    # VISUALIZATIONS
    #

    def visualization(
        self,
        **kwargs,
    ):

        self.dashboard.visualizations.append(
            Visualization(**kwargs)
        )

    def bar_chart(
        self,
        **kwargs,
    ):

        kwargs["chart"] = "bar"

        self.visualization(**kwargs)

    def line_chart(
        self,
        **kwargs,
    ):

        kwargs["chart"] = "line"

        self.visualization(**kwargs)

    def scatter_chart(
        self,
        **kwargs,
    ):

        kwargs["chart"] = "scatter"

        self.visualization(**kwargs)

    def histogram(
        self,
        **kwargs,
    ):

        kwargs["chart"] = "histogram"

        self.visualization(**kwargs)

    #
    # INSIGHTS
    #

    def insight(
        self,
        severity,
        message,
        title=None,
        category=None,
        what_happened=None,
        why_it_matters=None,
        recommended_action=None,
    ):

        from app.analysis.insights.normalize import (
            DEFAULT_RECOMMENDED_ACTIONS,
            first_sentence,
            normalize_priority,
        )

        priority = normalize_priority(
            severity
        )

        resolved_title = (
            title
            or what_happened
            or first_sentence(message)
            or "Analysis finding identified"
        )

        if (
            not title
            and not what_happened
            and message
            and resolved_title.strip()
            == message.strip()
        ):
            resolved_title = (
                category
                or self.dashboard.title
                or "Key finding"
            )

        resolved_why = (
            why_it_matters
            or message
            or resolved_title
        )

        self.dashboard.insights.append(
            Insight(
                severity=priority,

                priority=priority,

                title=resolved_title,

                message=resolved_why,

                category=(
                    category
                    or self.dashboard.title
                ),

                what_happened=(
                    what_happened
                    or resolved_title
                ),

                why_it_matters=resolved_why,

                recommended_action=(
                    recommended_action
                    or DEFAULT_RECOMMENDED_ACTIONS[
                        priority
                    ]
                ),
            )
        )

    def info(
        self,
        message,
    ):

        self.insight(
            "info",
            message,
        )

    def warning(
        self,
        message,
    ):

        self.insight(
            "warning",
            message,
        )

    def success(
        self,
        message,
    ):

        self.insight(
            "success",
            message,
        )

    #
    # ACTIONS
    #

    def action(
        self,
        message,
    ):

        self.dashboard.actions.append(
            message
        )

    def build(self):

        return self.dashboard