from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard
from ..column_resolver import ColumnResolver
from ..dataset_builder import DatasetBuilder

from ..insights.engine import InsightEngine
from ..insights.cross_sell import RULES


class CrossSellModule(AnalysisModule):

    id = "cross_sell"

    title = "Cross-Sell Opportunities"

    description = (
        "Identify products that customers are likely "
        "to purchase together and rank potential "
        "cross-sell opportunities."
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

        if (
            not customer_column
            or not product_column
            or not sales_column
        ):

            return AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary=(
                    "Customer, Product, or Sales "
                    "columns could not be identified."
                ),
            )

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Identify products with strong "
                "cross-sell potential."
            ),
        )

        builder = AnalysisBuilder(
            dashboard
        )

        datasets = DatasetBuilder(
            context.dataframe
        )

        product_revenue = datasets.group_metrics(
            dimension=product_column,
            metrics={
                "revenue": (
                    sales_column,
                    "sum",
                )
            },
            sort_by="revenue",
            ascending=False,
        )

        affinity = datasets.product_affinity(
            customer_column=customer_column,
            product_column=product_column,
            min_customers=5,
        )

        # --------------------------------------------------
        # Product revenue
        # --------------------------------------------------

        product_revenue = datasets.group_metrics(
            dimension=product_column,
            metrics={
                "revenue": (
                    sales_column,
                    "sum",
                )
            },
            sort_by="revenue",
            ascending=False,
        )

        # --------------------------------------------------
        # Product affinity
        # --------------------------------------------------

        affinity = datasets.product_affinity(
            customer_column=customer_column,
            product_column=product_column,
            min_customers=5,
        )

        if affinity.empty:

            return builder.build()

        # --------------------------------------------------
        # Add product revenue
        # --------------------------------------------------

        revenue_lookup = (
            product_revenue
            .set_index(product_column)["revenue"]
            .to_dict()
        )

        affinity["revenue_a"] = (
            affinity["product_a"]
            .map(revenue_lookup)
            .fillna(0)
        )

        affinity["revenue_b"] = (
            affinity["product_b"]
            .map(revenue_lookup)
            .fillna(0)
        )

        # --------------------------------------------------
        # Calculate cross-sell opportunity
        # --------------------------------------------------

        affinity["customers_not_buying_b"] = (
            affinity["customers_a"]
            - affinity["overlap_customers"]
        )

        affinity["customers_not_buying_a"] = (
            affinity["customers_b"]
            - affinity["overlap_customers"]
        )

        # Average revenue per B customer

        affinity["revenue_per_b_customer"] = (
            affinity["revenue_b"]
            / affinity["customers_b"]
            .replace(0, float("nan"))
        )

        affinity["revenue_per_b_customer"] = (
            affinity[
                "revenue_per_b_customer"
            ]
            .fillna(0)
        )

        # Estimated revenue opportunity

        affinity["estimated_opportunity"] = (
            affinity[
                "customers_not_buying_b"
            ]
            * affinity[
                "revenue_per_b_customer"
            ]
        )

        # --------------------------------------------------
        # Cross-sell score
        # --------------------------------------------------

        affinity["cross_sell_score"] = (
            affinity["confidence_a_to_b"]
            * affinity["estimated_opportunity"]
        )

        # --------------------------------------------------
        # Remove weak relationships
        # --------------------------------------------------

        opportunities = (
            affinity[
                (
                    affinity[
                        "confidence_a_to_b"
                    ] >= 0.20
                )
                &
                (
                    affinity[
                        "customers_not_buying_b"
                    ] > 0
                )
                &
                (
                    affinity[
                        "estimated_opportunity"
                    ] >= 1000
                )
            ]
            .sort_values(
                "cross_sell_score",
                ascending=False,
            )
        )

        # --------------------------------------------------
        # Top opportunities
        # --------------------------------------------------

        top_opportunities = (
            opportunities
            .head(20)
            .copy()
        )

        top_opportunities[
            "product_pair"
        ] = (
            top_opportunities[
                "product_a"
            ].astype(str)
            + " → "
            + top_opportunities[
                "product_b"
            ].astype(str)
        )

        top_opportunities["label"] = (
            top_opportunities["product_a"].astype(str)
            + " → "
            + top_opportunities["product_b"].astype(str)
        )

        builder.dataset(
            "cross_sell_opportunities",
            top_opportunities,
        )

        # --------------------------------------------------
        # Metrics
        # --------------------------------------------------

        self.build_metrics(
            builder,
            opportunities,
        )

        # --------------------------------------------------
        # Visualization
        # --------------------------------------------------

        self.build_visualizations(
            builder,
        )

        # --------------------------------------------------
        # Insights
        # --------------------------------------------------

        facts = self.build_facts(
            opportunities,
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
        # Actions
        # --------------------------------------------------

        builder.action(
            "Prioritize the highest-scoring cross-sell opportunities."
        )

        builder.action(
            "Review customers who purchase the source product "
            "but not the target product."
        )

        builder.action(
            "Validate cross-sell candidates with sales teams "
            "before launching campaigns."
        )

        return builder.build()

    # ======================================================
    # METRICS
    # ======================================================

    def build_metrics(
        self,
        builder,
        opportunities,
    ):

        opportunity_count = len(
            opportunities
        )

        total_opportunity = (
            opportunities[
                "estimated_opportunity"
            ]
            .sum()
        )

        average_confidence = (
            opportunities[
                "confidence_a_to_b"
            ]
            .mean()
            if opportunity_count
            else 0
        )

        total_customers = (
            opportunities[
                "customers_not_buying_b"
            ]
            .sum()
        )

        builder.metric(
            "opportunities",
            "Cross-Sell Opportunities",
            f"{opportunity_count:,}",
        )

        builder.metric(
            "opportunity_revenue",
            "Estimated Revenue Potential",
            f"${total_opportunity:,.0f}",
        )

        builder.metric(
            "average_confidence",
            "Average Confidence",
            f"{average_confidence:.1%}",
        )

        builder.metric(
            "customers",
            "Potential Customers",
            f"{total_customers:,}",
        )

    # ======================================================
    # VISUALIZATIONS
    # ======================================================

    def build_visualizations(
        self,
        builder,
    ):

        builder.visualization(
            id="cross_sell_revenue",
            title="Top Cross-Sell Opportunities",
            chart="bar",
            dataset="cross_sell_opportunities",
            x="product_pair",
            y="estimated_opportunity",
        )

        builder.visualization(
            id="cross_sell_confidence",
            title="Product Pair Confidence",
            chart="bar",
            dataset="cross_sell_opportunities",
            x="product_pair",
            y="confidence_a_to_b",
        )

    # ======================================================
    # FACTS
    # ======================================================

    def build_facts(
        self,
        opportunities,
    ):

        if opportunities.empty:

            return {
                "opportunity_count": 0,
                "estimated_revenue": 0,
                "average_confidence": 0,
            }

        return {

            "opportunity_count":
                len(opportunities),

            "estimated_revenue":
                opportunities[
                    "estimated_opportunity"
                ].sum(),

            "average_confidence":
                opportunities[
                    "confidence_a_to_b"
                ].mean(),

            "high_confidence_count":
                len(
                    opportunities[
                        opportunities[
                            "confidence_a_to_b"
                        ] >= 0.50
                    ]
                ),
        }