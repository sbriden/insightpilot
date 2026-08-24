import pandas as pd

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
            summary=(
                "Evaluate profitability across "
                "customers, products and categories."
            ),
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

        # ------------------------------------------------------------
        # Resolve available columns
        # ------------------------------------------------------------

        sales = resolver.sales()
        profit = resolver.profit()

        customer = resolver.customer()
        category = resolver.category()
        product = resolver.product()

        # ------------------------------------------------------------
        # Normalize invalid resolver results
        # ------------------------------------------------------------

        def valid_column(column):

            return (
                isinstance(column, str)
                and column in context.dataframe.columns
            )

        sales = (
            sales
            if valid_column(sales)
            else None
        )

        profit = (
            profit
            if valid_column(profit)
            else None
        )

        customer = (
            customer
            if valid_column(customer)
            else None
        )

        category = (
            category
            if valid_column(category)
            else None
        )

        product = (
            product
            if valid_column(product)
            else None
        )

        # ------------------------------------------------------------
        # If profitability cannot be calculated,
        # return a valid dashboard rather than crashing.
        # ------------------------------------------------------------

        if sales is None or profit is None:

            builder.metric(
                "profitability_available",
                "Profitability Analysis",
                "Not available",
            )

            builder.action(
                "Add revenue and cost/profit fields "
                "to enable profitability analysis."
            )

            return builder.build()

        # ------------------------------------------------------------
        # Category profitability
        # ------------------------------------------------------------

        category_profit = pd.DataFrame()

        if category is not None:

            category_profit = (
                datasets.group_metrics(
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
            )

        # ------------------------------------------------------------
        # Customer profitability
        # ------------------------------------------------------------

        customer_profit = pd.DataFrame()

        if customer is not None:

            customer_profit = (
                datasets.group_metrics(
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
            )

        # ------------------------------------------------------------
        # Product profitability
        # ------------------------------------------------------------

        product_profit = pd.DataFrame()

        if product is not None:

            product_profit = (
                datasets.group_metrics(
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
            )

        # ------------------------------------------------------------
        # Loss-making customers
        # ------------------------------------------------------------

        negative_customers = (
            datasets.filter(
                customer_profit,
                lambda df: df["profit"] < 0,
            )
            if not customer_profit.empty
            else pd.DataFrame()
        )

        loss_customers = (
            datasets.bottom_n(
                negative_customers,
                column="profit",
            )
            if not negative_customers.empty
            else pd.DataFrame()
        )

        negative_customer_profit = (
            negative_customers["profit"].sum()
            if not negative_customers.empty
            else 0
        )

        # ------------------------------------------------------------
        # Loss-making products
        # ------------------------------------------------------------

        negative_products = (
            datasets.filter(
                product_profit,
                lambda df: df["profit"] < 0,
            )
            if not product_profit.empty
            else pd.DataFrame()
        )

        loss_products = (
            datasets.bottom_n(
                negative_products,
                column="profit",
            )
            if not negative_products.empty
            else pd.DataFrame()
        )

        negative_product_profit = (
            negative_products["profit"].sum()
            if not negative_products.empty
            else 0
        )

        # ------------------------------------------------------------
        # Add datasets only when available
        # ------------------------------------------------------------

        if not category_profit.empty:

            builder.dataset(
                "category_profit",
                category_profit,
            )

        if not loss_customers.empty:

            builder.dataset(
                "loss_customers",
                loss_customers,
            )

        if not loss_products.empty:

            builder.dataset(
                "loss_products",
                loss_products,
            )

        # ------------------------------------------------------------
        # Overall profitability
        # ------------------------------------------------------------

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

        # ------------------------------------------------------------
        # Metrics
        # ------------------------------------------------------------

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

        # ------------------------------------------------------------
        # Visualization
        # ------------------------------------------------------------

        if not category_profit.empty:

            builder.visualization(
                id="category_profit",
                title="Profit by Category",
                chart="bar",
                dataset="category_profit",
                x=category,
                y="profit",
            )

        # ------------------------------------------------------------
        # Insight facts
        # ------------------------------------------------------------

        facts = {
            "margin": margin,

            "overall_profit": overall_profit,

            "overall_sales": overall_sales,

            "negative_customers": len(
                negative_customers
            ),

            "negative_customer_pct": (
                len(negative_customers)
                / len(customer_profit)
                if len(customer_profit)
                else 0
            ),

            "negative_customer_profit":
                negative_customer_profit,

            "negative_products": len(
                negative_products
            ),

            "negative_product_pct": (
                len(negative_products)
                / len(product_profit)
                if len(product_profit)
                else 0
            ),

            "negative_product_profit":
                negative_product_profit,
        }

        # ------------------------------------------------------------
        # Actions
        # ------------------------------------------------------------

        builder.action(
            "Review pricing strategy."
        )

        builder.action(
            "Review discount policies."
        )

        if customer is not None:

            builder.action(
                "Investigate loss-making customers."
            )

        if product is not None:

            builder.action(
                "Investigate loss-making products."
            )

        # ------------------------------------------------------------
        # Insights
        # ------------------------------------------------------------

        engine = InsightEngine(
            RULES
        )

        dashboard.insights = (
            engine.evaluate(
                facts
            )
        )

        return builder.build()