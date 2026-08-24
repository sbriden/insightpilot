from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard
from ..column_resolver import ColumnResolver
from ..dataset_builder import DatasetBuilder

from ..insights.engine import InsightEngine
from ..insights.customer_product import RULES


class CustomerProductModule(AnalysisModule):

    id = "customer_product"

    title = "Customer & Product Analysis"

    description = (
        "Analyze customer and product relationships, "
        "product mix, profitability, and cross-sell opportunities."
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
        product_column = resolver.product()
        sales_column = resolver.sales()
        profit_column = resolver.profit()

        if (
            not customer_column
            or not product_column
            or not sales_column
        ):

            return AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary=(
                    "Customer, Product, or Sales columns "
                    "could not be identified."
                ),
            )

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Analyze relationships between customers "
                "and products."
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

        # --------------------------------------------------
        # Customer × Product
        # --------------------------------------------------

        customer_product = (
            datasets.group_metrics(
                dimension=[
                    customer_column,
                    product_column,
                ],
                metrics=metrics,
                sort_by="revenue",
                ascending=False,
            )
        )

        if profit_column:

            customer_product["margin"] = (
                customer_product["profit"]
                / customer_product["revenue"]
                .replace(0, float("nan"))
            )

            customer_product["margin"] = (
                customer_product["margin"]
                .fillna(0)
            )

        else:

            customer_product["margin"] = 0

        builder.dataset(
            "customer_product",
            customer_product,
        )

        # --------------------------------------------------
        # Top Customer/Product combinations
        # --------------------------------------------------

        top_combinations = (
            customer_product
            .sort_values(
                "revenue",
                ascending=False,
            )
            .head(20)
        )

        top_combinations = (
            top_combinations.copy()
        )

        top_combinations["customer_product"] = (
            top_combinations[
                customer_column
            ].astype(str)
            + " / "
            + top_combinations[
                product_column
            ].astype(str)
        )

        builder.dataset(
            "top_combinations",
            top_combinations,
        )

        # --------------------------------------------------
        # Customer product counts
        # --------------------------------------------------

        customer_product_counts = (
            customer_product
            .groupby(customer_column)
            .agg(
                products=(
                    product_column,
                    "nunique",
                ),

                revenue=(
                    "revenue",
                    "sum",
                ),
            )
            .reset_index()
        )

        builder.dataset(
            "customer_product_counts",
            customer_product_counts,
        )

        # --------------------------------------------------
        # Product customer counts
        # --------------------------------------------------

        product_customer_counts = (
            customer_product
            .groupby(product_column)
            .agg(
                customers=(
                    customer_column,
                    "nunique",
                ),

                revenue=(
                    "revenue",
                    "sum",
                ),
            )
            .reset_index()
        )

        builder.dataset(
            "product_customer_counts",
            product_customer_counts,
        )

        # --------------------------------------------------
        # Product penetration
        # --------------------------------------------------

        total_customers = (
            customer_product[customer_column]
            .nunique()
        )

        product_customer_counts[
            "penetration"
        ] = (
            product_customer_counts["customers"]
            / total_customers
            if total_customers
            else 0
        )

        penetration_chart = (
            product_customer_counts
            .sort_values(
                "penetration",
                ascending=True,
            )
            .head(15)
        )

        builder.dataset(
            "product_penetration",
            penetration_chart,
        )

        # --------------------------------------------------
        # Cross-sell candidates
        # --------------------------------------------------

        cross_sell = (
            product_customer_counts[
                (
                    product_customer_counts[
                        "penetration"
                    ] < 0.25
                )
                &
                (
                    product_customer_counts[
                        "customers"
                    ] > 1
                )
            ]
            .sort_values(
                "revenue",
                ascending=False,
            )
            .head(20)
        )

        builder.dataset(
            "cross_sell_candidates",
            cross_sell,
        )

        # --------------------------------------------------
        # Metrics
        # --------------------------------------------------

        self.build_metrics(
            builder,
            customer_product,
            customer_product_counts,
            product_customer_counts,
            customer_column,
            product_column,
            profit_column,
        )

        # --------------------------------------------------
        # Visualizations
        # --------------------------------------------------

        self.build_visualizations(
            builder,
            top_combinations,
            customer_column,
            product_column,
            profit_column,
        )

        # --------------------------------------------------
        # Insight facts
        # --------------------------------------------------

        facts = self.build_facts(
            customer_product,
            customer_product_counts,
            product_customer_counts,
            total_customers,
            profit_column,
        )

        insights = InsightEngine(
            RULES
        ).evaluate(
            facts
        )

        dashboard.insights.extend(
            insights
        )

        # --------------------------------------------------
        # Recommended actions
        # --------------------------------------------------

        builder.action(
            "Review the highest-value customer/product combinations."
        )

        builder.action(
            "Identify products with low customer penetration."
        )

        builder.action(
            "Evaluate cross-sell opportunities among existing customers."
        )

        return builder.build()

    # ======================================================
    # METRICS
    # ======================================================

    def build_metrics(
        self,
        builder,
        customer_product,
        customer_product_counts,
        product_customer_counts,
        customer_column,
        product_column,
        profit_column,
    ):

        total_customers = (
            customer_product[
                customer_column
            ].nunique()
        )

        total_products = (
            customer_product[
                product_column
            ].nunique()
        )

        total_revenue = (
            customer_product["revenue"]
            .sum()
        )

        total_combinations = (
            len(customer_product)
        )

        average_products_per_customer = (
            total_combinations
            / total_customers
            if total_customers
            else 0
        )

        average_customers_per_product = (
            total_combinations
            / total_products
            if total_products
            else 0
        )

        builder.metric(
            "customer_count",
            "Customers",
            f"{total_customers:,}",
        )

        builder.metric(
            "product_count",
            "Products",
            f"{total_products:,}",
        )

        builder.metric(
            "customer_product_combinations",
            "Customer/Product Combinations",
            f"{total_combinations:,}",
        )

        builder.metric(
            "products_per_customer",
            "Products / Customer",
            f"{average_products_per_customer:.1f}",
        )

        builder.metric(
            "customers_per_product",
            "Customers / Product",
            f"{average_customers_per_product:.1f}",
        )

        builder.metric(
            "revenue",
            "Total Revenue",
            f"${total_revenue:,.0f}",
        )

        if profit_column:

            total_profit = (
                customer_product["profit"]
                .sum()
            )

            margin = (
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
                "Overall Margin",
                f"{margin:.1%}",
            )

    # ======================================================
    # VISUALIZATIONS
    # ======================================================

    def build_visualizations(
        self,
        builder,
        top_combinations,
        customer_column,
        product_column,
        profit_column,
    ):

        # Top combinations

        builder.visualization(
            id="top_customer_products",
            title="Top Customer/Product Combinations",
            chart="bar",
            dataset="top_combinations",
            x="customer_product",
            y="revenue",
        )

        # Product penetration

        builder.visualization(
            id="product_penetration",
            title="Product Customer Penetration",
            chart="bar",
            dataset="product_penetration",
            x=product_column,
            y="penetration",
        )

        if profit_column:

            builder.visualization(
                id="customer_product_profit",
                title="Top Customer/Product Combinations by Profit",
                chart="bar",
                dataset="top_combinations",
                x="customer_product",
                y="profit",
            )

    # ======================================================
    # FACTS
    # ======================================================

    def build_facts(
        self,
        customer_product,
        customer_product_counts,
        product_customer_counts,
        total_customers,
        profit_column,
    ):

        total_products = len(
            product_customer_counts
        )

        low_penetration_products = (
            product_customer_counts[
                product_customer_counts[
                    "penetration"
                ] < 0.25
            ]
        )

        facts = {

            "total_customers":
                total_customers,

            "total_products":
                total_products,

            "total_combinations":
                len(customer_product),

            "low_penetration_products":
                len(low_penetration_products),

            "low_penetration_product_pct": (
                len(low_penetration_products)
                / total_products
                if total_products
                else 0
            ),
        }

        if profit_column:

            negative_combinations = (
                customer_product[
                    customer_product["profit"] < 0
                ]
            )

            facts.update({

                "negative_combinations":
                    len(negative_combinations),

                "negative_combination_pct": (
                    len(negative_combinations)
                    / len(customer_product)
                    if len(customer_product)
                    else 0
                ),

                "negative_combination_profit":
                    negative_combinations[
                        "profit"
                    ].sum(),
            })

        return facts