from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard
from ..column_resolver import ColumnResolver
from ..dataset_builder import DatasetBuilder

from ..insights.engine import InsightEngine
from ..insights.customer_performance import RULES


class CustomerPerformanceModule(AnalysisModule):

    id = "customer_performance"

    title = "Customer Performance"

    description = (
        "Analyze customer revenue, profitability, "
        "order behavior, and value."
    )

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

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Analyze customer revenue, profitability, "
                "and purchasing behavior."
            ),
        )

        builder = AnalysisBuilder(
            dashboard
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
            metrics=metrics,
            sort_by="revenue",
            ascending=False,
        )

        # Profit per customer

        if profit_column:

            customer_summary["margin"] = (
                customer_summary["profit"]
                / customer_summary["revenue"]
                .replace(0, float("nan"))
            )

            customer_summary["margin"] = (
                customer_summary["margin"]
                .fillna(0)
            )

        else:

            customer_summary["profit_per_customer"] = 0

            customer_summary["margin"] = 0

        # Average order value

        customer_summary["average_order_value"] = (
            customer_summary["revenue"]
            / customer_summary["orders"]
            .replace(0, float("nan"))
        )

        customer_summary["average_order_value"] = (
            customer_summary["average_order_value"]
            .fillna(0)
        )

        customer_summary = (
            customer_summary
            .fillna(0)
        )

        # Store complete dataset

        builder.dataset(
            "customer_summary",
            customer_summary,
        )

        # Top customers by revenue

        top_customers = (
            customer_summary
            .sort_values(
                "revenue",
                ascending=False,
            )
            .head(10)
        )

        builder.dataset(
            "top_customers",
            top_customers,
        )

        # Bottom customers by revenue

        bottom_customers = (
            customer_summary
            .sort_values(
                "revenue",
                ascending=True,
            )
            .head(10)
        )

        builder.dataset(
            "bottom_customers",
            bottom_customers,
        )

        # Top customers by profit

        if profit_column:

            top_profit_customers = (
                customer_summary
                .sort_values(
                    "profit",
                    ascending=False,
                )
                .head(10)
            )

            builder.dataset(
                "top_profit_customers",
                top_profit_customers,
            )

            # Top customers by margin

            top_margin_customers = (
                customer_summary[
                    customer_summary["revenue"] > 0
                ]
                .sort_values(
                    "margin",
                    ascending=False,
                )
                .head(10)
            )

            builder.dataset(
                "top_margin_customers",
                top_margin_customers,
            )

        self.build_metrics(
            builder,
            customer_summary,
            customer_column,
            profit_column,
        )

        self.build_visualizations(
            builder,
            customer_column,
            profit_column,
        )

        facts = self.build_facts(
            customer_summary,
            profit_column,
        )

        insights = InsightEngine(
            RULES
        ).evaluate(
            facts
        )

        for insight in insights:

            dashboard.insights.append(
                insight
            )

        builder.action(
            "Review the highest-value customers."
        )

        builder.action(
            "Investigate customers generating negative profit."
        )

        builder.action(
            "Review low-margin customers for pricing "
            "or service-cost opportunities."
        )

        return builder.build()

    def build_metrics(
        self,
        builder,
        customer_summary,
        customer_column,
        profit_column,
    ):

        total_customers = len(
            customer_summary
        )

        total_revenue = (
            customer_summary["revenue"]
            .sum()
        )

        average_revenue = (
            customer_summary["revenue"]
            .mean()
        )

        total_orders = (
            customer_summary["orders"]
            .sum()
        )

        average_order_value = (
            total_revenue / total_orders
            if total_orders
            else 0
        )

        top_customer = (
            customer_summary
            .sort_values(
                "revenue",
                ascending=False,
            )
            .iloc[0]
        )

        builder.metric(
            "customers",
            "Customers",
            f"{total_customers:,}",
        )

        builder.metric(
            "revenue",
            "Total Revenue",
            f"${total_revenue:,.0f}",
        )

        builder.metric(
            "revenue_per_customer",
            "Revenue / Customer",
            f"${average_revenue:,.0f}",
        )

        builder.metric(
            "average_order_value",
            "Average Order Value",
            f"${average_order_value:,.0f}",
        )

        builder.metric(
            "top_customer",
            "Top Customer",
            str(
                top_customer[
                    customer_column
                ]
            ),
            subtitle=(
                f"${top_customer['revenue']:,.0f}"
            ),
        )

        if profit_column:

            total_profit = (
                customer_summary["profit"]
                .sum()
            )

            overall_margin = (
                total_profit / total_revenue
                if total_revenue
                else 0
            )

            builder.metric(
                "profit",
                "Total Profit",
                f"${total_profit:,.0f}",
            )

            builder.metric(
                "margin",
                "Customer Margin",
                f"{overall_margin:.1%}",
            )

    def build_visualizations(
        self,
        builder,
        customer_column,
        profit_column,
    ):

        builder.visualization(
            id="top_customers",
            title="Top 10 Customers by Revenue",
            chart="bar",
            dataset="top_customers",
            x=customer_column,
            y="revenue",
        )

        builder.visualization(
            id="bottom_customers",
            title="Bottom 10 Customers by Revenue",
            chart="bar",
            dataset="bottom_customers",
            x=customer_column,
            y="revenue",
        )

        if profit_column:

            builder.visualization(
                id="top_profit_customers",
                title="Top 10 Customers by Profit",
                chart="bar",
                dataset="top_profit_customers",
                x=customer_column,
                y="profit",
            )

            builder.visualization(
                id="top_margin_customers",
                title="Top 10 Customers by Margin",
                chart="bar",
                dataset="top_margin_customers",
                x=customer_column,
                y="margin",
            )

    def build_facts(
        self,
        customer_summary,
        profit_column,
    ):

        total_revenue = (
            customer_summary["revenue"]
            .sum()
        )

        total_customers = len(
            customer_summary
        )

        facts = {

            "total_customers":
                total_customers,

            "total_revenue":
                total_revenue,

            "top_customer_revenue": (
                customer_summary
                .sort_values(
                    "revenue",
                    ascending=False,
                )
                .iloc[0]["revenue"]
            ),

            "top10_revenue_share": (
                customer_summary
                .sort_values(
                    "revenue",
                    ascending=False,
                )
                .head(10)["revenue"]
                .sum()
                / total_revenue
                if total_revenue
                else 0
            ),
        }

        if profit_column:

            negative_customers = (
                customer_summary[
                    customer_summary["profit"] < 0
                ]
            )

            low_margin_customers = (
                customer_summary[
                    customer_summary["margin"] < 0.10
                ]
            )

            facts.update({

                "total_profit":
                    customer_summary["profit"].sum(),

                "negative_customers":
                    len(negative_customers),

                "negative_customer_pct": (
                    len(negative_customers)
                    / total_customers
                    if total_customers
                    else 0
                ),

                "negative_customer_profit":
                    negative_customers["profit"].sum(),

                "low_margin_customers":
                    len(low_margin_customers),

                "low_margin_customer_pct": (
                    len(low_margin_customers)
                    / total_customers
                    if total_customers
                    else 0
                ),
            })

        return facts