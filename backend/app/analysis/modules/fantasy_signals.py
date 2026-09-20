"""
Fantasy Signals analysis module.

Promotes SME fantasy_signal rows into CandidateFindings
through the shared InsightEngine path.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..base import AnalysisModule
from ..builder import AnalysisBuilder
from ..column_resolver import ColumnResolver
from ..insights.engine import InsightEngine
from ..insights.fantasy_signals import (
    CONFIDENCE_FLOOR,
    RULES,
    STRENGTH_FLOORS,
)
from ..insights.player_snapshot import (
    build_player_snapshots_for_frame,
)
from ..models import AnalysisDashboard


_RULES_BY_TYPE = {
    signal_type: next(
        (
            rule
            for rule in RULES
            if rule.id
            == f"fantasy_signal_{signal_type.lower()}"
        ),
        None,
    )
    for signal_type in STRENGTH_FLOORS
}


class FantasySignalsModule(AnalysisModule):

    id = "fantasy_signals"
    title = "Fantasy Signals"
    description = (
        "Promote actionable fantasy football signals "
        "(breakout, buy-low, start/sit, and related) "
        "into InsightPilot findings."
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
        df = context.dataframe

        player_column = resolver.player_key()
        signal_type_column = resolver.signal_type()
        strength_column = resolver.signal_strength()
        confidence_column = resolver.signal_confidence()
        season_column = resolver.season()
        week_column = resolver.week()
        player_label_column = resolver.player_label()

        if (
            df is None
            or df.empty
            or not player_column
            or not signal_type_column
            or not strength_column
        ):
            return AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary=(
                    "Fantasy signal columns "
                    "(player, signal_type, signal_strength) "
                    "could not be identified."
                ),
            )

        working = df.copy()
        working["_signal_type"] = (
            working[signal_type_column]
            .astype(str)
            .str.upper()
            .str.strip()
        )
        working["_strength"] = pd.to_numeric(
            working[strength_column],
            errors="coerce",
        )
        if confidence_column:
            working["_confidence"] = pd.to_numeric(
                working[confidence_column],
                errors="coerce",
            )
        else:
            working["_confidence"] = 60.0

        # Prefer the latest season/week when broader history slipped in.
        if season_column and week_column:
            season_num = pd.to_numeric(
                working[season_column],
                errors="coerce",
            )
            week_num = pd.to_numeric(
                working[week_column],
                errors="coerce",
            )
            latest_season = season_num.max()
            latest_week = week_num[
                season_num == latest_season
            ].max()
            working = working[
                (season_num == latest_season)
                & (week_num == latest_week)
            ]

        floors = working["_signal_type"].map(
            lambda value: STRENGTH_FLOORS.get(value, 55.0)
        )
        eligible = working[
            working["_signal_type"].isin(STRENGTH_FLOORS)
            & working["_strength"].notna()
            & (working["_strength"] >= floors)
            & (working["_confidence"].fillna(0) >= CONFIDENCE_FLOOR)
        ].copy()

        eligible = eligible.sort_values(
            by=["_strength", "_confidence"],
            ascending=False,
        )

        # Cap create-flow latency: enough signals for ranking,
        # without evaluating hundreds of rows.
        max_signals = 12
        eligible = eligible.head(max_signals)

        all_insights: list[Any] = []
        all_findings: list[Any] = []
        source_columns = [
            column
            for column in [
                player_column,
                signal_type_column,
                strength_column,
                confidence_column,
                season_column,
                week_column,
            ]
            if column
        ]

        for row in eligible.to_dict(orient="records"):
            signal_type = str(
                row.get("_signal_type") or ""
            ).upper()
            rule = _RULES_BY_TYPE.get(signal_type)
            if rule is None:
                continue

            player_id = row.get(player_column)
            player_label = (
                row.get(player_label_column)
                if player_label_column
                else None
            ) or player_id
            facts = {
                "player_id": player_id,
                "player_label": player_label,
                "signal_type": signal_type,
                "signal_strength": float(
                    row.get("_strength") or 0
                ),
                "confidence": float(
                    row.get("_confidence") or 0
                ),
                "season": (
                    row.get(season_column)
                    if season_column
                    else None
                ),
                "week": (
                    row.get(week_column)
                    if week_column
                    else None
                ),
                "direction": row.get("direction"),
            }
            insights, findings = InsightEngine(
                [rule]
            ).evaluate_with_findings(
                facts,
                analysis_type=self.id,
                source_columns=source_columns,
                relevant_dimensions=["player", "week"],
                default_filters=[
                    {
                        "field": player_column,
                        "op": "=",
                        "value": player_id,
                    }
                ],
                dataset_id=getattr(
                    context,
                    "dataset_id",
                    None,
                ),
                dataset_version=getattr(
                    context,
                    "dataset_version",
                    None,
                ),
                dataset_identity=getattr(
                    context,
                    "dataset_identity",
                    None,
                ),
                dataset_label=getattr(
                    context,
                    "source_dataset",
                    None,
                ),
            )
            all_insights.extend(insights)
            all_findings.extend(findings)

        builder = AnalysisBuilder(
            AnalysisDashboard(
                id=self.id,
                title=self.title,
                summary="",
            )
        )

        type_counts = (
            eligible["_signal_type"]
            .value_counts()
            .head(8)
            .reset_index()
        )
        type_counts.columns = ["signal_type", "count"]
        builder.dataset(
            "signal_type_counts",
            type_counts,
        )

        top_rows = eligible.head(15).copy()
        display = pd.DataFrame(
            {
                "player": top_rows.apply(
                    lambda row: (
                        row.get(player_label_column)
                        if player_label_column
                        else row.get(player_column)
                    ),
                    axis=1,
                ),
                "signal_type": top_rows["_signal_type"],
                "signal_strength": top_rows["_strength"],
                "confidence": top_rows["_confidence"],
                "season": (
                    top_rows[season_column]
                    if season_column
                    else None
                ),
                "week": (
                    top_rows[week_column]
                    if week_column
                    else None
                ),
            }
        )
        builder.dataset(
            "top_signals",
            display,
        )

        snapshot_season = None
        snapshot_week = None
        if season_column and week_column and not eligible.empty:
            try:
                snapshot_season = int(
                    eligible.iloc[0].get(season_column)
                )
                snapshot_week = int(
                    eligible.iloc[0].get(week_column)
                )
            except (TypeError, ValueError):
                snapshot_season = None
                snapshot_week = None

        snapshots = build_player_snapshots_for_frame(
            eligible.to_dict(orient="records"),
            player_id_key=player_column,
            season=snapshot_season,
            week=snapshot_week,
            max_players=8,
        )
        if snapshots:
            builder.dataset(
                "player_snapshots",
                pd.DataFrame(snapshots),
            )

        builder.integer_metric(
            id="eligible_signals",
            title="Eligible signals",
            value=int(len(eligible)),
        )
        builder.integer_metric(
            id="promoted_findings",
            title="Findings",
            value=int(len(all_findings)),
        )
        if not eligible.empty:
            builder.metric(
                id="top_signal",
                title="Top signal",
                value=str(
                    eligible.iloc[0].get("_signal_type")
                ),
                subtitle=(
                    f"{eligible.iloc[0].get(player_column)} · "
                    f"strength "
                    f"{float(eligible.iloc[0].get('_strength') or 0):.0f}"
                ),
            )

        if not type_counts.empty:
            builder.bar_chart(
                id="signals_by_type",
                title="Eligible signals by type",
                dataset="signal_type_counts",
                x="signal_type",
                y="count",
                description=(
                    "SME-thresholded fantasy signals in scope."
                ),
                takeaway=(
                    "Signal mix shows where the framework "
                    "found actionable fantasy insights."
                ),
                business_question=(
                    "Which fantasy signal types dominate "
                    "this period?"
                ),
                priority="High",
            )

        dashboard = builder.build()
        dashboard.insights = all_insights
        dashboard.candidate_findings = all_findings
        dashboard.summary = (
            f"Promoted {len(all_findings)} fantasy signal "
            f"finding(s) from {len(eligible)} eligible "
            "signal row(s)."
            if all_findings
            else (
                "No fantasy signals met SME strength and "
                "confidence floors."
            )
        )
        return dashboard
