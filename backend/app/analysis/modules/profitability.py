from ..base import AnalysisModule

from ..builder import AnalysisBuilder

from ..models import AnalysisDashboard

from ..column_resolver import ColumnResolver

from ..dataset_builder import DatasetBuilder


class ProfitabilityModule(AnalysisModule):

    id = "profitability"

    title = "Profitability"

    description = "Analyze profit and margin across the business."

    def supports(self, context):

        return (
            context.classification["type"]
            == "Sales & Revenue"
        )

    def run(self, context):

        dashboard = AnalysisDashboard(

            id=self.id,

            title=self.title,

            summary="Evaluate profitability across customers, products and categories.",

        )

        builder = AnalysisBuilder(
            dashboard
        )

        datasets = DatasetBuilder(
            context.dataframe
        )

        resolver = ColumnResolver(
            context.column_profiles
        )

        # Build analysis here

        sales = resolver.sales()

        profit = resolver.profit()

        customer = resolver.customer()

        category = resolver.category()

        product = resolver.product()

        category_profit = datasets.group_sum(
            dimension=category,
            measure=profit,
            output_name="profit",
        )

        customer_profit = datasets.group_sum(
            dimension=customer,
            measure=profit,
            output_name="profit",
        )

        product_profit = datasets.group_sum(
            dimension=product,
            measure=profit,
            output_name="profit",
        )

        loss_customers = datasets.bottom_n(
            customer_profit,
            sort_column="profit",
        )

        loss_products = datasets.bottom_n(
            product_profit,
            sort_column="profit",
        )

        builder.dataset(
            "category_profit",
            category_profit.to_dict(
                orient="records"
            ),
        )

        builder.dataset(
            "loss_customers",
            loss_customers.to_dict(
                orient="records"
            ),
        )

        builder.dataset(
            "loss_products",
            loss_products.to_dict(
                orient="records"
            ),
        )

        overall_profit = (
            context.dataframe[profit].sum()
        )

        overall_sales = (
            context.dataframe[sales].sum()
        )

        margin = (
            overall_profit
            / overall_sales
        )

        builder.metric(
            "profit",
            "Overall Profit",
            f"${overall_profit:,.0f}",
        )

        builder.metric(
            "margin",
            "Profit Margin",
            f"{margin:.1%}",
        )

        builder.metric(
            "loss_customers",
            "Loss Customers",
            str(
                len(
                    customer_profit[
                        customer_profit.profit < 0
                    ]
                )
            ),
        )

        builder.visualization(
            id="category_profit",
            title="Profit by Category",
            chart="bar",
            dataset="category_profit",
            x=category,
            y="profit",
        )

        if margin < .10:
            builder.insight(
                "high",
                "Overall margin is below 10%."
            )

        if len(loss_customers):
            builder.insight(
                "medium",
                f"{len(loss_customers)} customers generated losses."
            )

        if len(loss_products):
            builder.insight(
                "medium",
                f"{len(loss_products)} products generated losses."
            )

        builder.action(
            "Review pricing strategy."
        )

        builder.action(
            "Review discount policies."
        )

        builder.action(
            "Investigate loss-making customers."
        )

        builder.action(
            "Investigate loss-making products."
        )

        return builder.build()