import pandas as pd

from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..column_resolver import ColumnResolver
from ..dataset_builder import DatasetBuilder
from ..models import AnalysisDashboard


class CustomerConcentrationModule(AnalysisModule):

    id = "customer_concentration"
    title = "Customer Concentration"
    description = "Analyze revenue concentration across customers."

    def supports(self, context):

        return (
            context.classification.get("type")
            == "Sales & Revenue"
        )

    def run(self, context):

        resolver = ColumnResolver(
            context.column_profiles
        )

        customer_column = resolver.customer()
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

        self.build_insights(
            builder,
            customer_summary,
            customer_column,
        )

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

        top10_share = (
            customer_summary
            .head(10)["revenue"]
            .sum()
            / total_revenue
        )

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

    def build_insights(
        self,
        builder,
        customer_summary,
        customer_column,
    ):

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

        top10_share = (
            customer_summary
            .head(10)["revenue"]
            .sum()
            / total_revenue
        )

        builder.info(
            (
                f"The top 10 customers "
                f"represent {top10_share:.1%} "
                f"of total revenue."
            )
        )

        builder.info(
            (
                f"Average revenue per "
                f"customer is "
                f"${average_revenue:,.0f}."
            )
        )

        builder.info(
            (
                f"{top_customer[customer_column]} "
                f"is the highest revenue "
                f"customer with "
                f"${top_customer['revenue']:,.0f}."
            )
        )

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