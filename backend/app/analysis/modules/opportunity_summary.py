from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard


class OpportunitySummaryModule(AnalysisModule):

    id = "opportunity_summary"

    title = "Opportunity Summary"

    description = (
        "Prioritize the highest-value opportunities "
        "identified across InsightPilot analyses."
    )

    def supports(self, context):

        return (
            context.classification.get("type")
            == "Sales & Revenue"
        )

    def run(self, context):

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Prioritize the highest-value opportunities "
                "identified across the analysis."
            ),
        )

        builder = AnalysisBuilder(
            dashboard
        )

        # --------------------------------------------------
        # Collect opportunities from analysis dashboards
        # --------------------------------------------------

        opportunities = (
            self.collect_opportunities(
                context
            )
        )

        # --------------------------------------------------
        # Nothing available
        # --------------------------------------------------

        if not opportunities:

            builder.insight(
                "info",
                (
                    "No actionable opportunities were "
                    "identified across the current analysis."
                ),
            )

            return builder.build()

        # --------------------------------------------------
        # Build unified opportunity dataset
        # --------------------------------------------------

        opportunity_rows = (
            self.build_opportunity_rows(
                opportunities
            )
        )

        # --------------------------------------------------
        # Rank opportunities
        # --------------------------------------------------

        opportunity_rows = sorted(
            opportunity_rows,
            key=lambda x: x["potential"],
            reverse=True,
        )

        top_opportunities = (
            opportunity_rows[:10]
        )

        # --------------------------------------------------
        # Dataset
        # --------------------------------------------------

        builder.dataset(
            "top_opportunities",
            top_opportunities,
        )

        builder.dataset(
            "all_opportunities",
            opportunity_rows,
        )

        # --------------------------------------------------
        # Metrics
        # --------------------------------------------------

        self.build_metrics(
            builder,
            opportunity_rows,
        )

        # --------------------------------------------------
        # Visualization
        # --------------------------------------------------

        builder.visualization(
            id="opportunity_value",
            title="Top Opportunities by Value",
            chart="bar",
            dataset="top_opportunities",
            x="label",
            y="potential",
        )

        # --------------------------------------------------
        # Insights
        # --------------------------------------------------

        self.build_insights(
            builder,
            opportunity_rows,
        )

        # --------------------------------------------------
        # Actions
        # --------------------------------------------------

        builder.action(
            "Prioritize the highest-value opportunities first."
        )

        builder.action(
            "Validate opportunity assumptions with business owners."
        )

        builder.action(
            "Assign accountable owners to the highest-priority opportunities."
        )

        return builder.build()

    # ======================================================
    # COLLECT OPPORTUNITIES
    # ======================================================

    def collect_opportunities(
        self,
        context,
    ):

        results = []

        # The analysis engine can provide dashboards
        # through the context if available.

        dashboards = getattr(
            context,
            "analysis_dashboards",
            [],
        )

        for dashboard in dashboards:

            if isinstance(
                dashboard,
                dict,
            ):

                results.append(
                    dashboard
                )

            elif hasattr(
                dashboard,
                "to_dict",
            ):

                results.append(
                    dashboard.to_dict()
                )

        return results

    # ======================================================
    # BUILD UNIFIED OPPORTUNITIES
    # ======================================================

    def build_opportunity_rows(
        self,
        dashboards,
    ):

        rows = []

        for dashboard in dashboards:

            dashboard_id = dashboard.get(
                "id"
            )

            datasets = dashboard.get(
                "datasets",
                {},
            )

            # --------------------------------------------------
            # Cross-Sell
            # --------------------------------------------------

            if (
                dashboard_id
                == "cross_sell"
            ):

                data = datasets.get(
                    "cross_sell_opportunities",
                    [],
                )

                for row in data:

                    rows.append(
                        {
                            "type": "Cross-Sell",
                            "label": str(
                                row.get(
                                    "label",
                                    "Unknown",
                                )
                            ),
                            "potential": float(
                                row.get(
                                    "estimated_opportunity",
                                    0,
                                )
                                or 0
                            ),
                            "score": float(
                                row.get(
                                    "cross_sell_score",
                                    0,
                                )
                                or 0
                            ),
                        }
                    )

            # --------------------------------------------------
            # Customer Growth
            # --------------------------------------------------

            elif (
                dashboard_id
                == "customer_growth"
            ):

                data = datasets.get(
                    "customer_growth_opportunities",
                    [],
                )

                for row in data:

                    rows.append(
                        {
                            "type": "Customer Growth",
                            "label": str(
                                row.get(
                                    "label",
                                    "Unknown",
                                )
                            ),
                            "potential": float(
                                row.get(
                                    "estimated_growth_potential",
                                    0,
                                )
                                or 0
                            ),
                            "score": float(
                                row.get(
                                    "growth_score",
                                    0,
                                )
                                or 0
                            ),
                        }
                    )

            # --------------------------------------------------
            # Profit Improvement
            # --------------------------------------------------

            elif (
                dashboard_id
                == "profit_improvement"
            ):

                data = datasets.get(
                    "profit_improvement_opportunities",
                    [],
                )

                for row in data:

                    rows.append(
                        {
                            "type": "Profit Improvement",
                            "label": str(
                                row.get(
                                    "label",
                                    "Unknown",
                                )
                            ),
                            "potential": float(
                                row.get(
                                    "estimated_profit_opportunity",
                                    0,
                                )
                                or 0
                            ),
                            "score": float(
                                row.get(
                                    "priority_score",
                                    0,
                                )
                                or 0
                            ),
                        }
                    )

        return rows

    # ======================================================
    # METRICS
    # ======================================================

    def build_metrics(
        self,
        builder,
        opportunities,
    ):

        total_potential = sum(
            row["potential"]
            for row in opportunities
        )

        cross_sell = sum(
            row["potential"]
            for row in opportunities
            if row["type"]
            == "Cross-Sell"
        )

        customer_growth = sum(
            row["potential"]
            for row in opportunities
            if row["type"]
            == "Customer Growth"
        )

        profit_improvement = sum(
            row["potential"]
            for row in opportunities
            if row["type"]
            == "Profit Improvement"
        )

        high_priority = len(
            [
                row
                for row in opportunities
                if row["score"] >= 0.70
            ]
        )

        builder.metric(
            "total_opportunity",
            "Total Opportunity",
            f"${total_potential:,.0f}",
        )

        builder.metric(
            "cross_sell",
            "Cross-Sell Potential",
            f"${cross_sell:,.0f}",
        )

        builder.metric(
            "customer_growth",
            "Customer Growth Potential",
            f"${customer_growth:,.0f}",
        )

        builder.metric(
            "profit_improvement",
            "Profit Improvement Potential",
            f"${profit_improvement:,.0f}",
        )

        builder.metric(
            "high_priority",
            "High-Priority Opportunities",
            f"{high_priority:,}",
        )

    # ======================================================
    # INSIGHTS
    # ======================================================

    def build_insights(
        self,
        builder,
        opportunities,
    ):

        if not opportunities:
            return

        top = opportunities[0]

        builder.insight(
            "high",
            (
                f"{top['label']} represents the largest "
                f"identified {top['type'].lower()} opportunity "
                f"at approximately "
                f"${top['potential']:,.0f}."
            ),
        )

        opportunity_types = {}

        for row in opportunities:

            opportunity_types[
                row["type"]
            ] = (
                opportunity_types.get(
                    row["type"],
                    0,
                )
                + row["potential"]
            )

        if opportunity_types:

            largest_type = max(
                opportunity_types,
                key=opportunity_types.get,
            )

            builder.insight(
                "medium",
                (
                    f"{largest_type} represents the largest "
                    "source of identified opportunity across "
                    "the current analysis."
                ),
            )