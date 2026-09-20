import pandas as pd

from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..column_resolver import (
    ColumnResolver,
    apply_entity_labels,
    build_entity_label_map,
)
from ..dataset_builder import DatasetBuilder
from ..models import AnalysisDashboard
from ..insights.engine import InsightEngine
from ..insights.customer_concentration import RULES
from ..primitives import concentration_summary


class CustomerConcentrationModule(AnalysisModule):

    id = "customer_concentration"
    title = "Customer Concentration"
    description = "Analyze revenue concentration across customers."

    def supports(self, context):

        from app.analysis.candidates import (
            analysis_supported,
        )

        return analysis_supported(
            self.id,
            context,
        )

    def run(self, context):

        resolver = ColumnResolver(
            context.column_profiles
        )

        customer_column = resolver.customer_key()
        customer_label_column = resolver.customer_label()
        sales_column = resolver.sales()
        profit_column = resolver.profit()

        if not customer_column or not sales_column:

            return AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary=(
                    "Customer or Sales columns "
                    "could not be identified."
                ),
            )

        customer_labels = build_entity_label_map(
            context.dataframe,
            customer_column,
            customer_label_column,
        )

        datasets = DatasetBuilder(
            context.dataframe
        )

        metrics = {
            "revenue": (
                sales_column,
                "sum",
            ),
            "orders": (
                sales_column,
                "count",
            ),
        }

        if profit_column:
            metrics["profit"] = (
                profit_column,
                "sum",
            )

        customer_summary = datasets.group_metrics(
            dimension=customer_column,
            metrics={
                "revenue": (
                    sales_column,
                    "sum",
                ),
                "orders": (
                    sales_column,
                    "count",
                ),
                "profit": (
                    profit_column,
                    "sum",
                ) if profit_column else (
                    sales_column,
                    "count",
                ),
            },
            sort_by="revenue",
        )

        customer_summary = apply_entity_labels(
            customer_summary,
            key_column=customer_column,
            label_map=customer_labels,
        )

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Evaluate revenue concentration "
                "across customers."
            ),
        )

        builder = AnalysisBuilder(
            dashboard
        )

        builder.dataset(
            "customer_summary",
            customer_summary,
        )

        builder.dataset(
            "top_customers",
            customer_summary.head(10),
        )

        self.build_metrics(
            builder,
            customer_summary,
            customer_column,
        )

        self.build_visualizations(
            builder,
            customer_column,
        )

        facts = self.build_facts(
            customer_summary
        )

        source_columns = [
            col for col in [
                customer_column,
                sales_column,
                profit_column,
            ]
            if col
        ]

        insights, findings = InsightEngine(
            RULES
        ).evaluate_with_findings(
            facts,
            analysis_type=self.id,
            source_columns=source_columns,
            relevant_dimensions=["customer"],
        )

        dashboard.insights = insights
        dashboard.candidate_findings = findings

        self.build_actions(
            builder
        )

        return builder.build()

    def build_metrics(
        self,
        builder,
        customer_summary,
        customer_column,
    ):

        total_customers = len(
            customer_summary
        )

        total_revenue = (
            customer_summary[
                "revenue"
            ].sum()
        )

        average_revenue = (
            customer_summary[
                "revenue"
            ].mean()
        )

        top_customer = (
            customer_summary.iloc[0]
        )

        concentration = concentration_summary(
            customer_summary,
            "revenue",
            n=10,
            already_sorted=True,
        )

        top10_share = concentration[
            "top_n_share"
        ]

        builder.integer_metric(
            id="customers",
            title="Customers",
            value=total_customers,
        )

        builder.currency_metric(
            id="revenue",
            title="Revenue",
            value=total_revenue,
        )

        builder.currency_metric(
            id="average_revenue",
            title="Average Revenue",
            value=average_revenue,
        )

        builder.metric(
            id="top_customer",
            title="Top Customer",
            value=str(
                top_customer[
                    customer_column
                ]
            ),
            subtitle=(
                f"${top_customer['revenue']:,.0f}"
            ),
        )

        builder.percent_metric(
            id="top10_share",
            title="Top 10 Revenue Share",
            value=top10_share,
        )

    def build_visualizations(
        self,
        builder,
        customer_column,
    ):

        builder.bar_chart(
            id="top_customers",
            title="Top 10 Customers by Revenue",
            dataset="top_customers",
            x=customer_column,
            y="revenue",
            description=(
                "Highest revenue customers."
            ),
            takeaway=(
                "Identify concentration."
            ),
            business_question=(
                "Are we dependent on "
                "a handful of customers?"
            ),
            priority="High",
        )

    def build_facts(
        self,
        customer_summary,
    ):

        concentration = concentration_summary(
            customer_summary,
            "revenue",
            n=10,
            already_sorted=True,
        )

        return {
            "total_customers":
                concentration["entity_count"],

            "top10_share":
                concentration["top_n_share"],

            "top10_revenue":
                concentration["top_n_value"],

            "total_revenue":
                concentration["total"],

            "top_customer_revenue":
                concentration["top_1_value"],

            "top_customer_share":
                concentration["top_1_share"],
        }

    def build_actions(
        self,
        builder,
    ):

        builder.action(
            "Review customer concentration risk."
        )

        builder.action(
            "Develop growth plans for mid-tier customers."
        )

        builder.action(
            "Protect relationships with top customers."
        )