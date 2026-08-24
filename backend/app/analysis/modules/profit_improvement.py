from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard
from ..column_resolver import ColumnResolver
from ..dataset_builder import DatasetBuilder


class ProfitImprovementModule(AnalysisModule):

    id = "profit_improvement"

    title = "Profit Improvement Opportunities"

    description = (
        "Identify products with meaningful revenue "
        "and opportunities to improve profitability."
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

        if (
            not product_column
            or not sales_column
            or not profit_column
        ):

            return AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary=(
                    "Product, Sales, or Profit columns "
                    "could not be identified."
                ),
            )

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Identify products with meaningful revenue "
                "and opportunities to improve profitability."
            ),
        )

        builder = AnalysisBuilder(
            dashboard
        )

        datasets = DatasetBuilder(
            context.dataframe
        )

        # --------------------------------------------------
        # Product financial performance
        # --------------------------------------------------

        product_summary = datasets.group_metrics(
            dimension=product_column,
            metrics={
                "revenue": (
                    sales_column,
                    "sum",
                ),
                "profit": (
                    profit_column,
                    "sum",
                ),
                "transactions": (
                    sales_column,
                    "count",
                ),
            },
            sort_by="revenue",
            ascending=False,
        )

        if product_summary.empty:

            builder.insight(
                "info",
                "No product profitability data was available.",
            )

            return builder.build()

        # --------------------------------------------------
        # Margin
        # --------------------------------------------------

        product_summary["margin"] = (
            product_summary["profit"]
            / product_summary["revenue"]
            .replace(0, 1)
        )

        # --------------------------------------------------
        # Overall benchmark
        # --------------------------------------------------

        total_revenue = (
            product_summary["revenue"]
            .sum()
        )

        total_profit = (
            product_summary["profit"]
            .sum()
        )

        overall_margin = (
            total_profit
            / total_revenue
            if total_revenue
            else 0
        )

        # --------------------------------------------------
        # Only products below benchmark are candidates
        # --------------------------------------------------

        product_summary["margin_gap"] = (
            overall_margin
            - product_summary["margin"]
        )

        opportunities = product_summary[
            product_summary["margin_gap"] > 0
        ].copy()

        # --------------------------------------------------
        # Estimated profit opportunity
        #
        # We use 50% of the theoretical margin gap as a
        # conservative realization assumption.
        # --------------------------------------------------

        opportunities[
            "theoretical_profit_opportunity"
        ] = (
            opportunities["revenue"]
            * opportunities["margin_gap"]
        )

        opportunities[
            "estimated_profit_opportunity"
        ] = (
            opportunities[
                "theoretical_profit_opportunity"
            ]
            * 0.50
        )

        # --------------------------------------------------
        # Revenue importance
        # --------------------------------------------------

        if total_revenue > 0:

            opportunities[
                "revenue_share"
            ] = (
                opportunities["revenue"]
                / total_revenue
            )

        else:

            opportunities[
                "revenue_share"
            ] = 0

        # --------------------------------------------------
        # Priority score
        #
        # 50% = financial opportunity
        # 30% = revenue importance
        # 20% = margin gap
        # --------------------------------------------------

        opportunity_rank = (
            opportunities[
                "estimated_profit_opportunity"
            ]
            .rank(pct=True)
        )

        revenue_rank = (
            opportunities[
                "revenue_share"
            ]
            .rank(pct=True)
        )

        margin_gap_rank = (
            opportunities[
                "margin_gap"
            ]
            .rank(pct=True)
        )

        opportunities[
            "priority_score"
        ] = (
            opportunity_rank * 0.50
            +
            revenue_rank * 0.30
            +
            margin_gap_rank * 0.20
        )

        # --------------------------------------------------
        # Rank opportunities
        # --------------------------------------------------

        opportunities = (
            opportunities
            .sort_values(
                "priority_score",
                ascending=False,
            )
        )

        top_opportunities = (
            opportunities
            .head(20)
            .copy()
        )

        top_opportunities["label"] = (
            top_opportunities[
                product_column
            ].astype(str)
        )

        # --------------------------------------------------
        # Datasets
        # --------------------------------------------------

        builder.dataset(
            "profit_improvement_analysis",
            product_summary.to_dict(
                orient="records"
            ),
        )

        builder.dataset(
            "profit_improvement_opportunities",
            top_opportunities.to_dict(
                orient="records"
            ),
        )

        # --------------------------------------------------
        # Metrics
        # --------------------------------------------------

        self.build_metrics(
            builder,
            opportunities,
            overall_margin,
        )

        # --------------------------------------------------
        # Visualizations
        # --------------------------------------------------

        self.build_visualizations(
            builder,
            product_column,
        )

        # --------------------------------------------------
        # Insights
        # --------------------------------------------------

        self.build_insights(
            builder,
            opportunities,
            product_column,
        )

        # --------------------------------------------------
        # Actions
        # --------------------------------------------------

        builder.action(
            "Prioritize high-revenue products with the largest profit improvement opportunities."
        )

        builder.action(
            "Investigate pricing, discounting, and cost drivers for low-margin products."
        )

        builder.action(
            "Validate margin improvement opportunities with product and finance teams."
        )

        return builder.build()

    # ======================================================
    # METRICS
    # ======================================================

    def build_metrics(
        self,
        builder,
        opportunities,
        overall_margin,
    ):

        opportunity_count = len(
            opportunities
        )

        total_profit_opportunity = (
            opportunities[
                "estimated_profit_opportunity"
            ].sum()
            if opportunity_count
            else 0
        )

        high_priority = (
            len(
                opportunities[
                    opportunities[
                        "priority_score"
                    ] >= 0.70
                ]
            )
        )

        average_margin = (
            opportunities[
                "margin"
            ].mean()
            if opportunity_count
            else 0
        )

        builder.metric(
            "profit_opportunities",
            "Profit Opportunities",
            f"{opportunity_count:,}",
        )

        builder.metric(
            "profit_potential",
            "Estimated Profit Potential",
            f"${total_profit_opportunity:,.0f}",
        )

        builder.metric(
            "average_margin",
            "Average Opportunity Margin",
            f"{average_margin:.1%}",
        )

        builder.metric(
            "high_priority",
            "High-Priority Products",
            f"{high_priority:,}",
        )

        builder.metric(
            "benchmark_margin",
            "Overall Margin Benchmark",
            f"{overall_margin:.1%}",
        )

    # ======================================================
    # VISUALIZATIONS
    # ======================================================

    def build_visualizations(
        self,
        builder,
        product_column,
    ):

        builder.visualization(
            id="profit_opportunity",
            title="Top Profit Improvement Opportunities",
            chart="bar",
            dataset="profit_improvement_opportunities",
            x=product_column,
            y="estimated_profit_opportunity",
        )

        builder.visualization(
            id="margin_gap",
            title="Product Margin vs Benchmark",
            chart="bar",
            dataset="profit_improvement_opportunities",
            x=product_column,
            y="margin_gap",
        )

    # ======================================================
    # INSIGHTS
    # ======================================================

    def build_insights(
        self,
        builder,
        opportunities,
        product_column,
    ):

        if opportunities.empty:

            builder.insight(
                "info",
                (
                    "No products were identified with a "
                    "margin below the overall benchmark."
                ),
            )

            return

        total_opportunity = (
            opportunities[
                "estimated_profit_opportunity"
            ].sum()
        )

        builder.insight(
            "medium",
            (
                f"{len(opportunities):,} products have "
                "profit improvement potential, representing "
                f"approximately ${total_opportunity:,.0f} "
                "in estimated additional profit."
            ),
        )

        high_priority = (
            opportunities[
                opportunities[
                    "priority_score"
                ] >= 0.70
            ]
        )

        if not high_priority.empty:

            top_product = (
                high_priority.iloc[0]
            )

            product_name = (
                top_product[
                    product_column
                ]
            )

            builder.insight(
                "high",
                (
                    f"{product_name} represents the strongest "
                    "profit improvement opportunity based on "
                    "revenue, margin gap, and estimated "
                    "profit potential."
                ),
            )