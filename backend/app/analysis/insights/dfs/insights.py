"""Structured DFS lineup insights and signals."""

from __future__ import annotations

from typing import Any


def build_lineup_insights(
    lineup: dict[str, Any],
    *,
    slate: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    players = list(lineup.get("players") or [])
    insights: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    if not players:
        insights.append(
            {
                "id": "empty",
                "tone": "warning",
                "text": "No lineup players selected yet.",
            }
        )
        return insights, signals

    teams = [
        str(player.get("team") or "").upper()
        for player in players
        if player.get("team")
    ]
    team_counts: dict[str, int] = {}
    for team in teams:
        team_counts[team] = team_counts.get(team, 0) + 1

    qb = next(
        (
            player
            for player in players
            if str(player.get("position") or "").upper() == "QB"
        ),
        None,
    )
    if qb and qb.get("team"):
        qb_team = str(qb["team"]).upper()
        stacked = [
            player
            for player in players
            if str(player.get("team") or "").upper() == qb_team
            and str(player.get("position") or "").upper()
            in {"WR", "TE"}
        ]
        if stacked:
            names = ", ".join(
                str(player.get("name")) for player in stacked[:2]
            )
            insights.append(
                {
                    "id": "qb_stack",
                    "tone": "positive",
                    "text": (
                        f"Strong QB–pass-catcher correlation "
                        f"({qb.get('name')} with {names})."
                    ),
                }
            )
            signals.append(
                {
                    "id": "strong_game_stack",
                    "label": "Strong Game Stack",
                    "body": (
                        "QB and pass catcher(s) are correlated "
                        "within the same projected game script."
                    ),
                }
            )

    favorable = [
        player
        for player in players
        if str(player.get("matchup_label") or "")
        in {"Very Favorable", "Favorable"}
    ]
    if favorable:
        insights.append(
            {
                "id": "matchups",
                "tone": "positive",
                "text": (
                    f"{len(favorable)} of {len(players)} players "
                    "have favorable matchup signals."
                ),
            }
        )

    low_owned = [
        player
        for player in players
        if (player.get("projected_ownership") or 1) <= 0.08
    ]
    if low_owned:
        insights.append(
            {
                "id": "leverage",
                "tone": "positive",
                "text": (
                    f"{len(low_owned)} lower-owned player"
                    f"{'s' if len(low_owned) != 1 else ''} "
                    "provide differentiation."
                ),
            }
        )
        signals.append(
            {
                "id": "leverage_opportunity",
                "label": "Leverage Opportunity",
                "body": (
                    "One or more lineup spots combine solid "
                    "projected production with below-average "
                    "ownership."
                ),
            }
        )

    high_ceiling = [
        player
        for player in players
        if (player.get("ceiling") or 0)
        >= (player.get("projection") or 0) * 1.35
    ]
    if len(high_ceiling) >= max(3, len(players) // 2):
        insights.append(
            {
                "id": "ceilings",
                "tone": "positive",
                "text": (
                    f"{len(high_ceiling)} players have elevated "
                    "projected ceilings relative to projection."
                ),
            }
        )

    salary_cap = float(lineup.get("salary_cap") or 0)
    salary_used = float(lineup.get("salary_used") or 0)
    if salary_cap > 0:
        utilization = salary_used / salary_cap
        if utilization >= 0.97:
            insights.append(
                {
                    "id": "salary_use",
                    "tone": "positive",
                    "text": (
                        "Salary utilization is near the cap, "
                        "preserving projected upside."
                    ),
                }
            )
        elif utilization < 0.90:
            insights.append(
                {
                    "id": "salary_left",
                    "tone": "warning",
                    "text": (
                        "Meaningful salary remains unused — "
                        "consider upgrading a flex or stack piece."
                    ),
                }
            )

    value = lineup.get("value")
    if value is not None and float(value) >= 2.7:
        signals.append(
            {
                "id": "salary_efficiency",
                "label": "Salary Efficiency",
                "body": (
                    "Overall lineup projection is strong relative "
                    "to total salary spent."
                ),
            }
        )

    concentrated = [
        team
        for team, count in team_counts.items()
        if count >= 3
    ]
    if concentrated:
        insights.append(
            {
                "id": "team_concentration",
                "tone": "neutral",
                "text": (
                    f"Concentrated exposure to "
                    f"{', '.join(concentrated)}."
                ),
            }
        )
        signals.append(
            {
                "id": "concentrated_opportunity",
                "label": "Concentrated Opportunity",
                "body": (
                    "Multiple lineup players benefit from the "
                    "same team environment."
                ),
            }
        )

    volatile = [
        player
        for player in players
        if str(player.get("position") or "").upper() in {"WR", "TE"}
        and (player.get("projection") or 0) >= 12
    ]
    if len(volatile) >= 4 and lineup.get("contest_type") == "gpp":
        signals.append(
            {
                "id": "volatility_warning",
                "label": "Volatility Warning",
                "body": (
                    "Several pass-catcher projections depend on "
                    "volatile touchdown outcomes."
                ),
            }
        )

    if not insights:
        insights.append(
            {
                "id": "baseline",
                "tone": "neutral",
                "text": (
                    "Lineup constructed from InsightPilot "
                    "projection, value, and contest strategy."
                ),
            }
        )

    del slate  # reserved for future slate-level comparisons
    return insights, signals
