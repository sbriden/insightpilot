from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard
from ..column_resolver import ColumnResolver
from ..dataset_builder import DatasetBuilder

from ..insights.engine import InsightEngine
from ..insights.product_performance import RULES


class ProductPerformanceModule(AnalysisModule):

    id = "product_performance"

    title = "Product Performance"

    description = (
        "Analyze product revenue, profitability, "
        "volume, and performance."
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

        product_column = resolver.product()

        sales_column = resolver.sales()

        profit_column = resolver.profit()

        if not product_column or not sales_column:

            return AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary=(
                    "Product or Sales columns "
                    "could not be identified."
                ),
            )

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Analyze product revenue, profitability, "
                "and sales performance."
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

        product_summary = datasets.group_metrics(
            dimension=product_column,
            metrics=metrics,
            sort_by="revenue",
            ascending=False,
        )

        if profit_column:

            product_summary["margin"] = (
                product_summary["profit"]
                / product_summary["revenue"]
            )

        else:

            product_summary["margin"] = 0

        builder.dataset(
            "product_summary",
            product_summary,
        )

        builder.dataset(
            "top_products",
            product_summary.head(10),
        )

        bottom_products = (
            product_summary
            .sort_values(
                "revenue",
                ascending=True,
            )
            .head(10)
        )

        builder.dataset(
            "bottom_products",
            bottom_products,
        )


        if profit_column:

            top_profit_products = (
                product_summary
                .sort_values(
                    "profit",
                    ascending=False,
                )
                .head(10)
            )

            builder.dataset(
                "top_profit_products",
                top_profit_products,
            )

            top_margin_products = (
                product_summary[
                    product_summary["revenue"] > 0
                ]
                .sort_values(
                    "margin",
                    ascending=False,
                )
                .head(10)
            )

            builder.dataset(
                "top_margin_products",
                top_margin_products,
            )

        self.build_metrics(
            builder,
            product_summary,
            product_column,
            profit_column,
        )

        self.build_visualizations(
            builder,
            product_column,
            profit_column,
        )

        facts = self.build_facts(
            product_summary,
            profit_column,
        )

        dashboard.insights = InsightEngine(
            RULES
        ).evaluate(
            facts
        )

        builder.action(
            "Review the highest-revenue products."
        )

        builder.action(
            "Investigate products with negative profit."
        )

        builder.action(
            "Review low-margin products for pricing "
            "or cost opportunities."
        )

        return builder.build()

    def build_metrics(
        self,
        builder,
        product_summary,
        product_column,
        profit_column,
    ):

        total_products = len(
            product_summary
        )

        total_revenue = (
            product_summary["revenue"]
            .sum()
        )

        average_revenue = (
            product_summary["revenue"]
            .mean()
        )

        top_product = (
            product_summary.iloc[0]
        )

        builder.metric(
            "products",
            "Products",
            f"{total_products:,}",
        )

        builder.metric(
            "revenue",
            "Total Revenue",
            f"${total_revenue:,.0f}",
        )

        builder.metric(
            "average_revenue",
            "Avg Product Revenue",
            f"${average_revenue:,.0f}",
        )

        builder.metric(
            "top_product",
            "Top Product",
            str(
                top_product[
                    product_column
                ]
            ),
            subtitle=(
                f"${top_product['revenue']:,.0f}"
            ),
        )

        if profit_column:

            total_profit = (
                product_summary["profit"]
                .sum()
            )

            margin = (
                total_profit
                / total_revenue
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
                "Overall Margin",
                f"{margin:.1%}",
            )

    def build_visualizations(
        self,
        builder,
        product_column,
        profit_column,
    ):

        builder.visualization(
            id="top_products",
            title="Top 10 Products by Revenue",
            chart="bar",
            dataset="top_products",
            x=product_column,
            y="revenue",
        )

        builder.visualization(
            id="bottom_products",
            title="Bottom 10 Products by Revenue",
            chart="bar",
            dataset="bottom_products",
            x=product_column,
            y="revenue",
        )

        if profit_column:

            builder.visualization(
                id="product_profit",
                title="Top 10 Products by Profit",
                chart="bar",
                dataset="top_profit_products",
                x=product_column,
                y="profit",
            )

            builder.visualization(
                id="product_margin",
                title="Top Products by Margin",
                chart="bar",
                dataset="top_margin_products",
                x=product_column,
                y="margin",
            )

    def build_facts(
        self,
        product_summary,
        profit_column,
    ):

        total_revenue = (
            product_summary["revenue"]
            .sum()
        )

        top10_revenue = (
            product_summary
            .head(10)["revenue"]
            .sum()
        )

        product_revenue_share = (
            top10_revenue / total_revenue
            if total_revenue
            else 0
        )

        facts = {
            "total_products":
                len(product_summary),

            "total_revenue":
                total_revenue,

            "top_product_revenue":
                product_summary.iloc[0]["revenue"],

            "top10_revenue_share":
                product_revenue_share,
        }

        if profit_column:

            negative_products = (
                product_summary[
                    product_summary["profit"] < 0
                ]
            )

            low_margin_products = (
                product_summary[
                    product_summary["margin"] < 0.10
                ]
            )

            facts.update({

                "total_profit":
                    product_summary["profit"].sum(),

                "negative_products":
                    len(negative_products),

                "negative_product_pct": (
                    len(negative_products)
                    / len(product_summary)
                    if len(product_summary)
                    else 0
                ),

                "negative_product_profit":
                    negative_products[
                        "profit"
                    ].sum(),

                "low_margin_products":
                    len(low_margin_products),

                "low_margin_product_pct": (
                    len(low_margin_products)
                    / len(product_summary)
                    if len(product_summary)
                    else 0
                ),
            })

        return facts