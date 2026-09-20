from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard
from ..column_resolver import (
    ColumnResolver,
    apply_entity_labels,
    build_entity_label_map,
    format_entity_label,
)
from ..dataset_builder import DatasetBuilder


class CustomerGrowthModule(AnalysisModule):

    id = "customer_growth"

    title = "Customer Growth Opportunities"

    description = (
        "Identify valuable customers with potential "
        "for product expansion."
    )

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
        product_column = resolver.product_key()
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
                    "Customer, Product, or Sales "
                    "columns could not be identified."
                ),
            )

        customer_labels = build_entity_label_map(
            context.dataframe,
            customer_column,
            customer_label_column,
        )

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Identify valuable customers with "
                "potential for product expansion."
            ),
        )

        builder = AnalysisBuilder(
            dashboard
        )

        datasets = DatasetBuilder(
            context.dataframe
        )

        # --------------------------------------------------
        # Customer revenue
        # --------------------------------------------------

        customer_metrics = {
            "revenue": (
                sales_column,
                "sum",
            ),

            "orders": (
                sales_column,
                "count",
            ),
        }

        # --------------------------------------------------
        # Add profit when available
        # --------------------------------------------------

        if profit_column:

            customer_metrics["profit"] = (
                profit_column,
                "sum",
            )

        customer_summary = (
            datasets.group_metrics(
                dimension=customer_column,
                metrics=customer_metrics,
                sort_by="revenue",
                ascending=False,
            )
        )

        # --------------------------------------------------
        # Product penetration
        # --------------------------------------------------

        penetration = (
            datasets.customer_product_penetration(
                customer_column=customer_column,
                product_column=product_column,
            )
        )

        if penetration.empty:

            return builder.build()

        # --------------------------------------------------
        # Merge customer metrics + penetration
        # --------------------------------------------------

        customer_summary = (
            customer_summary.merge(
                penetration,
                on=customer_column,
                how="left",
            )
        )

        # --------------------------------------------------
        # Profit margin
        # --------------------------------------------------

        if profit_column:

            customer_summary["margin"] = (
                customer_summary["profit"]
                / customer_summary["revenue"]
                .replace(0, 1)
            )

        else:

            customer_summary["margin"] = 0

        # --------------------------------------------------
        # Customers missing products
        # --------------------------------------------------

        customer_summary["products_not_purchased"] = (
            customer_summary["total_products"]
            - customer_summary["products_purchased"]
        )

        # --------------------------------------------------
        # Potential revenue
        #
        # Estimate using average revenue per product
        # purchased by the customer.
        # --------------------------------------------------

        customer_summary[
            "revenue_per_product"
        ] = (
            customer_summary["revenue"]
            / customer_summary[
                "products_purchased"
            ].replace(0, 1)
        )

        customer_summary[
            "estimated_growth_potential"
        ] = (
            customer_summary[
                "products_not_purchased"
            ]
            * customer_summary[
                "revenue_per_product"
            ]
            * 0.25
        )

        # --------------------------------------------------
        # Growth score
        # --------------------------------------------------

        revenue_rank = (
            customer_summary["revenue"]
            .rank(pct=True)
        )

        penetration_gap = (
            1
            - customer_summary[
                "product_penetration"
            ]
        )

        margin_score = (
            customer_summary["margin"]
            .clip(
                lower=0,
                upper=1,
            )
        )

        customer_summary[
            "growth_score"
        ] = (
            revenue_rank
            * 0.45
            +
            penetration_gap
            * 0.35
            +
            margin_score
            * 0.20
        )

        # --------------------------------------------------
        # Candidate filter
        # --------------------------------------------------

        opportunities = customer_summary[
            (
                customer_summary[
                    "products_not_purchased"
                ] > 0
            )
            &
            (
                customer_summary[
                    "estimated_growth_potential"
                ] > 0
            )
        ].copy()

        opportunities = (
            opportunities
            .sort_values(
                "growth_score",
                ascending=False,
            )
        )

        top_opportunities = (
            opportunities
            .head(20)
            .copy()
        )

        top_opportunities = apply_entity_labels(
            top_opportunities,
            key_column=customer_column,
            label_map=customer_labels,
        )

        top_opportunities["label"] = (
            top_opportunities[
                customer_column
            ].astype(str)
        )

        # --------------------------------------------------
        # Dataset
        # --------------------------------------------------

        builder.dataset(
            "customer_growth_analysis",
            customer_summary.to_dict(
                orient="records"
            ),
        )

        builder.dataset(
            "customer_growth_opportunities",
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
        )

        # --------------------------------------------------
        # Visualizations
        # --------------------------------------------------

        self.build_visualizations(
            builder,
            customer_column,
            customer_labels,
        )

        # --------------------------------------------------
        # Insights
        # --------------------------------------------------

        self.build_insights(
            builder,
            opportunities,
            customer_column,
            customer_labels,
        )

        # --------------------------------------------------
        # Actions
        # --------------------------------------------------

        builder.action(
            "Prioritize high-value customers with low product penetration."
        )

        builder.action(
            "Identify products that could expand existing customer relationships."
        )

        builder.action(
            "Validate expansion opportunities with account teams."
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

        total_potential = (
            opportunities[
                "estimated_growth_potential"
            ].sum()
            if opportunity_count
            else 0
        )

        average_penetration = (
            opportunities[
                "product_penetration"
            ].mean()
            if opportunity_count
            else 0
        )

        high_value_customers = (
            len(
                opportunities[
                    opportunities[
                        "growth_score"
                    ] >= 0.70
                ]
            )
        )

        builder.metric(
            "growth_opportunities",
            "Growth Opportunities",
            f"{opportunity_count:,}",
        )

        builder.metric(
            "growth_potential",
            "Estimated Revenue Potential",
            f"${total_potential:,.0f}",
        )

        builder.metric(
            "average_penetration",
            "Average Product Penetration",
            f"{average_penetration:.1%}",
        )

        builder.metric(
            "high_value_customers",
            "High-Priority Customers",
            f"{high_value_customers:,}",
        )

    # ======================================================
    # VISUALIZATIONS
    # ======================================================

    def build_visualizations(
        self,
        builder,
        customer_column,
        customer_labels=None,
    ):

        builder.visualization(
            id="customer_growth",
            title="Top Customer Growth Opportunities",
            chart="bar",
            dataset="customer_growth_opportunities",
            x=customer_column,
            y="estimated_growth_potential",
        )

        builder.visualization(
            id="customer_penetration",
            title="Customer Product Penetration",
            chart="bar",
            dataset="customer_growth_opportunities",
            x=customer_column,
            y="product_penetration",
        )

    # ======================================================
    # INSIGHTS
    # ======================================================

    def build_insights(
        self,
        builder,
        opportunities,
        customer_column,
        customer_labels=None,
    ):

        if opportunities.empty:

            builder.insight(
                "info",
                (
                    "No customer growth opportunities "
                    "were identified."
                ),
            )

            return

        total_potential = (
            opportunities[
                "estimated_growth_potential"
            ].sum()
        )

        high_priority = (
            opportunities[
                opportunities[
                    "growth_score"
                ] >= 0.70
            ]
        )

        evidence = (
            f"{len(opportunities):,} customers have "
            "identifiable product expansion potential, "
            f"representing approximately "
            f"${total_potential:,.0f} in estimated "
            "revenue potential."
        )

        builder.insight(
            "medium",
            evidence,
        )

        builder.candidate_finding(
            metric="growth_opportunity_count",
            observed_value=int(len(opportunities)),
            baseline=0,
            comparison="vs_threshold",
            magnitude=float(len(opportunities)),
            magnitude_unit="count",
            evidence=evidence,
            confidence=0.85,
            relevant_dimensions=["customer"],
            source_columns=[
                col for col in [customer_column]
                if col
            ],
            rule_id="growth_opportunities",
            severity="medium",
            title="Customer Growth Opportunities",
        )

        if not high_priority.empty:

            top_customer = (
                high_priority.iloc[0]
            )

            customer_name = format_entity_label(
                top_customer[customer_column],
                customer_labels,
            )

            top_evidence = (
                f"{customer_name} has a strong combination "
                "of customer value and product expansion "
                "potential."
            )

            builder.insight(
                "high",
                top_evidence,
            )

            builder.candidate_finding(
                metric="growth_score",
                observed_value=float(
                    top_customer["growth_score"]
                ),
                baseline=0.70,
                comparison="vs_threshold",
                magnitude=float(
                    top_customer["growth_score"] - 0.70
                ),
                magnitude_unit="ratio",
                evidence=top_evidence,
                confidence=0.8,
                relevant_dimensions=["customer"],
                source_columns=[
                    col for col in [customer_column]
                    if col
                ],
                rule_id="top_growth_customer",
                severity="high",
                title=(
                    f"Top Growth Opportunity: {customer_name}"
                ),
            )
