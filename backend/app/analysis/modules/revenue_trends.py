import numpy as np

from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..models import AnalysisDashboard
from ..column_resolver import ColumnResolver
from ..dataset_builder import DatasetBuilder

from ..insights.engine import InsightEngine
from ..insights.revenue_trends import RULES


class RevenueTrendsModule(AnalysisModule):

    id = "revenue_trends"

    title = "Revenue Trends"

    description = (
        "Analyze revenue performance and trends over time."
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

        date_column = resolver.date()

        sales_column = resolver.sales()

        if not date_column or not sales_column:

            return AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary=(
                    "Date or Sales columns "
                    "could not be identified."
                ),
            )

        dashboard = AnalysisDashboard(
            id=self.id,
            title=self.title,
            summary=(
                "Analyze revenue performance, "
                "growth and changes over time."
            ),
        )

        builder = AnalysisBuilder(
            dashboard
        )

        datasets = DatasetBuilder(
            context.dataframe
        )

        # Build datasets
        monthly_revenue = datasets.time_series(
            date_column=date_column,
            measure=sales_column,
            frequency="ME",
        )

        monthly_revenue = monthly_revenue.rename(
            columns={
                sales_column: "revenue"
            }
        )

        monthly_revenue["mom_growth"] = (
            monthly_revenue["revenue"]
            .pct_change()
        )

        monthly_revenue["mom_growth_pct"] = (
            monthly_revenue["mom_growth"] * 100
        )

        monthly_revenue["rolling_3_month"] = (
            monthly_revenue["revenue"]
            .rolling(3)
            .mean()
            .shift(1)
        )

        monthly_revenue["trend_deviation"] = (
            (
                monthly_revenue["revenue"]
                - monthly_revenue["rolling_3_month"]
            )
            / monthly_revenue["rolling_3_month"].replace(
                0,
                np.nan,
            )
        )

        monthly_revenue["trend_deviation_pct"] = (
            monthly_revenue["trend_deviation"] * 100
        )

        monthly_revenue["yoy_growth"] = (
            monthly_revenue["revenue"]
            .pct_change(periods=12)
        )

        monthly_revenue["yoy_growth_pct"] = (
            monthly_revenue["yoy_growth"] * 100
        )


        monthly_revenue = monthly_revenue.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        if len(monthly_revenue) >= 6:

            recent_3 = (
                monthly_revenue
                .tail(3)["revenue"]
                .mean()
            )

            previous_3 = (
                monthly_revenue
                .iloc[-6:-3]["revenue"]
                .mean()
            )

            trend_change = (
                (recent_3 - previous_3)
                / previous_3
                if previous_3
                else 0
            )

        else:

            recent_3 = (
                monthly_revenue["revenue"].mean()
            )

            previous_3 = recent_3

            trend_change = 0


        if trend_change > 0.05:

            trend_direction = "growing"

        elif trend_change < -0.05:

            trend_direction = "declining"

        else:

            trend_direction = "stable"

        monthly_revenue = monthly_revenue.fillna(0)

        builder.dataset(
            "monthly_revenue",
            monthly_revenue,
        )

        monthly_revenue["is_anomaly"] = (
            monthly_revenue["trend_deviation"]
            .abs()
            >= 0.20
        )

        anomalies = monthly_revenue[
            monthly_revenue["is_anomaly"]
        ].copy()

        anomalies = anomalies.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        anomalies = anomalies.fillna(0)

        builder.dataset(
            "revenue_anomalies",
            anomalies,
        )

        anomaly_count = len(anomalies)

        positive_anomalies = anomalies[
            anomalies["trend_deviation"] > 0
        ]

        negative_anomalies = anomalies[
            anomalies["trend_deviation"] < 0
        ]

        largest_positive_anomaly = (
            positive_anomalies.loc[
                positive_anomalies["trend_deviation"].idxmax()
            ]
            if not positive_anomalies.empty
            else None
        )

        largest_negative_anomaly = (
            negative_anomalies.loc[
                negative_anomalies["trend_deviation"].idxmin()
            ]
            if not negative_anomalies.empty
            else None
        )

        total_revenue = (
            monthly_revenue["revenue"]
            .sum()
        )

        average_monthly_revenue = (
            monthly_revenue["revenue"]
            .mean()
        )

        first_revenue = (
            monthly_revenue.iloc[0]["revenue"]
        )

        last_revenue = (
            monthly_revenue.iloc[-1]["revenue"]
        )

        overall_growth = (
            (last_revenue - first_revenue)
            / first_revenue
            if first_revenue
            else 0
        )

        best_month = monthly_revenue.loc[
            monthly_revenue["revenue"].idxmax()
        ]

        worst_month = monthly_revenue.loc[
            monthly_revenue["revenue"].idxmin()
        ]

        facts = {
            "overall_growth":
                overall_growth,

            "total_revenue":
                total_revenue,

            "average_monthly_revenue":
                average_monthly_revenue,

            "best_month":
                best_month["revenue"],

            "worst_month":
                worst_month["revenue"],

            "recent_3_month":
                recent_3,

            "previous_3_month":
                previous_3,

            "trend_change":
                trend_change,

            "trend_direction":
                trend_direction,

            "anomaly_count":
                anomaly_count,

            "largest_positive_anomaly":
                largest_positive_anomaly,

            "largest_negative_anomaly":
                largest_negative_anomaly,

            "date_column":
                date_column,
        }

        builder.metric(
            "total_revenue",
            "Total Revenue",
            f"${total_revenue:,.0f}",
        )

        builder.metric(
            "average_monthly_revenue",
            "Avg Monthly Revenue",
            f"${average_monthly_revenue:,.0f}",
        )

        builder.metric(
            "overall_growth",
            "Overall Growth",
            f"{overall_growth:.1%}",
        )

        builder.metric(
            "best_month",
            "Best Month",
            f"${best_month['revenue']:,.0f}",
        )

        builder.metric(
            "worst_month",
            "Worst Month",
            f"${worst_month['revenue']:,.0f}",
        )

        builder.metric(
            "trend_direction",
            "Revenue Trend",
            trend_direction.title(),
        )

        builder.visualization(
            id="revenue_over_time",
            title="Revenue Over Time",
            chart="line",
            dataset="monthly_revenue",
            x=date_column,
            y="revenue",
        )

        builder.visualization(
            id="revenue_rolling_average",
            title="Revenue vs 3-Month Average",
            chart="line",
            dataset="monthly_revenue",
            x=date_column,
            y="rolling_3_month",
        )

        builder.visualization(
            id="revenue_yoy_growth",
            title="Year-over-Year Revenue Growth",
            chart="bar",
            dataset="monthly_revenue",
            x=date_column,
            y="yoy_growth_pct",
        )

        builder.visualization(
            id="revenue_anomalies",
            title="Revenue Anomalies",
            chart="bar",
            dataset="revenue_anomalies",
            x=date_column,
            y="revenue",
        )

        dashboard.insights = InsightEngine(
            RULES
        ).evaluate(
            facts
        )

        builder.action(
            "Investigate significant changes in monthly revenue."
        )

        builder.action(
            "Review drivers of the strongest revenue periods."
        )

        builder.action(
            "Investigate causes of the weakest revenue periods."
        )

        return builder.build()