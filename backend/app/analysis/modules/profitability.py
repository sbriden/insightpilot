from ..base import AnalysisModule

from ..builder import AnalysisBuilder

from ..models import AnalysisDashboard

from ..column_resolver import ColumnResolver

from ..dataset_builder import DatasetBuilder

from ..insights.engine import InsightEngine

from ..insights.profitability import RULES


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

        category_profit = datasets.group_metrics(
            dimension=category,
            metrics={
                "profit": (
                    profit,
                    "sum",
                ),
                "sales": (
                    sales,
                    "sum",
                ),
            },
            sort_by="profit",
        )

        customer_profit = datasets.group_metrics(
            dimension=customer,
            metrics={
                "profit": (
                    profit,
                    "sum",
                ),
                "sales": (
                    sales,
                    "sum",
                ),
            },
            sort_by="profit",
        )

        product_profit = datasets.group_metrics(
            dimension=product,
            metrics={
                "profit": (
                    profit,
                    "sum",
                ),
                "sales": (
                    sales,
                    "sum",
                ),
            },
            sort_by="profit",
        )

        negative_customers = datasets.filter(
            customer_profit,
            lambda df: df["profit"] < 0,
        )

        loss_customers = datasets.bottom_n(
            negative_customers,
            column="profit",
        )

        negative_customer_profit = (
            negative_customers["profit"].sum()
        )

        negative_products = datasets.filter(
            product_profit,
            lambda df: df["profit"] < 0,
        )

        loss_products = datasets.bottom_n(
            negative_products,
            column="profit",
        )

        negative_product_profit = (
            negative_products["profit"].sum()
        )

        builder.dataset(
            "category_profit",
            category_profit,
        )

        builder.dataset(
            "loss_customers",
            loss_customers,
        )

        builder.dataset(
            "loss_products",
            loss_products,
        )

        overall_profit = (
            context.dataframe[profit].sum()
        )

        overall_sales = (
            context.dataframe[sales].sum()
        )

        margin = (
            overall_profit / overall_sales
            if overall_sales
            else 0
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
            str(len(negative_customers)),
        )

        builder.metric(
            "loss_products",
            "Loss Products",
            str(len(negative_products)),
        )

        builder.visualization(
            id="category_profit",
            title="Profit by Category",
            chart="bar",
            dataset="category_profit",
            x=category,
            y="profit",
        )

        facts = {
            "margin": margin,

            "overall_profit": overall_profit,

            "overall_sales": overall_sales,

            "negative_customers": len(
                negative_customers
            ),

            "negative_customer_pct": (
                len(negative_customers) / len(customer_profit)
                if len(customer_profit)
                else 0
            ),

            "negative_customer_profit": (
                negative_customer_profit
            ),

            "negative_products": len(
                negative_products
            ),

            "negative_product_pct": (
                len(negative_products) / len(product_profit)
                if len(product_profit)
                else 0
            ),

            "negative_product_profit": (
                negative_product_profit
            ),
        }

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

        engine = InsightEngine(
            RULES
        )

        dashboard.insights = (
            engine.evaluate(
                facts
            )
        )

        return builder.build()