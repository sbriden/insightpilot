"""
Player fantasy projection from a forecasted role.

The weekly question is what role the player will have, and how
that role turns into stats. Opportunities come from the depth
chart, usage, and the game forecast. Yards and catches come from
those opportunities times a shrunk efficiency rate. Touchdowns
come from goal-line and red-zone chances, not from a historical
touchdown rate.

    fantasy points = scoring rules applied to predicted stats

Matchup ratings stay on the player as an explanation. The fixed
matchup multiplier remains only when no game forecast exists.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.dfs.player_production import (
    forecast_player_production,
)
from app.analysis.insights.dfs.player_role import (
    forecast_player_role,
    production_prior_for_player,
    reference_role_shares,
)


ABSOLUTE_MAX_PROJECTION = 55.0


def project_player_from_game_forecast(
    *,
    base_projection: float,
    position: str,
    team_forecast: dict[str, Any],
    opportunity_score: float | None = None,
    depth_order: int | None = None,
    scoring: str | None = "ppr",
    current_season_games: int | None = None,
    historical_baseline: float | None = None,
    raw_projection: float | None = None,
    injury_status: str | None = None,
    roster_status: str | None = None,
    current_usage: dict[str, Any] | None = None,
    historical_usage: dict[str, Any] | None = None,
    teammates_ahead_out: int = 0,
    matchup_score: float | None = None,
    current_efficiency: dict[str, Any] | None = None,
    historical_efficiency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Forecast the role first, then score the opportunities it earns.
    """

    prior, earned_as_starter = production_prior_for_player(
        position=position,
        base_projection=base_projection,
        current_season_games=current_season_games,
        historical_baseline=historical_baseline,
        raw_projection=raw_projection,
    )
    role = forecast_player_role(
        position=position,
        team_forecast=team_forecast,
        depth_order=depth_order,
        current_season_games=int(current_season_games or 0),
        opportunity_score=opportunity_score,
        injury_status=injury_status,
        roster_status=roster_status,
        current_usage=current_usage,
        historical_usage=historical_usage,
        teammates_ahead_out=teammates_ahead_out,
        matchup_score=matchup_score,
    )
    production = forecast_player_production(
        role=role,
        team_forecast=team_forecast,
        reference_shares=reference_role_shares(
            role,
            earned_as_starter=earned_as_starter,
            current_season_games=int(current_season_games or 0),
            current_usage=current_usage,
            historical_usage=historical_usage,
            production_prior=prior,
        ),
        production_prior=prior,
        scoring=scoring,
        current_season_games=int(current_season_games or 0),
        current_efficiency=current_efficiency,
        historical_efficiency=historical_efficiency,
    )
    points = max(0.0, min(ABSOLUTE_MAX_PROJECTION, production["total"]))
    drivers = list(role.get("drivers") or [])
    if production.get("summary"):
        drivers.append(str(production["summary"]))
    drivers.append(
        "The matchup multiplier is not applied on top of the "
        "game forecast."
    )
    reason = " ".join([str(role.get("summary") or ""), *drivers]).strip()
    opportunities = role.get("opportunities") or {}
    return {
        "projection": round(points, 1),
        "adjustment_factor": None,
        "adjustment_source": "game_forecast",
        "environment_counted_once": True,
        "matchup_multiplier_applied": False,
        "drivers": drivers,
        "projection_environment_reason": reason,
        "role_forecast": role,
        "scoring_components": {
            "production_prior": round(prior, 2),
            "opportunities": opportunities,
            "shares": role.get("shares"),
            "stats": production.get("stats"),
            "points": production.get("points"),
            "components": production.get("components"),
            "rates": production.get("rates"),
            "skill_multiplier": production.get("skill_multiplier"),
        },
        "game_environment": {
            "team": team_forecast.get("team"),
            "opponent": team_forecast.get("opponent"),
            "source": team_forecast.get("source"),
            "model_version": team_forecast.get("model_version"),
            "timestamp": team_forecast.get("timestamp"),
            "projected_points": team_forecast.get("projected_points"),
            "opponent_points": team_forecast.get("opponent_points"),
            "projected_total": team_forecast.get("projected_total"),
            "projected_margin": team_forecast.get("projected_margin"),
            "expected_plays": team_forecast.get("expected_plays"),
            "expected_drives": team_forecast.get("expected_drives"),
            "expected_scoring_opportunities": team_forecast.get(
                "expected_scoring_opportunities"
            ),
            "expected_pass_attempts": team_forecast.get(
                "expected_pass_attempts"
            ),
            "expected_rush_attempts": team_forecast.get(
                "expected_rush_attempts"
            ),
            "expected_pass_tds": team_forecast.get("expected_pass_tds"),
            "expected_rush_tds": team_forecast.get("expected_rush_tds"),
            "expected_field_goals": team_forecast.get(
                "expected_field_goals"
            ),
            "expected_turnovers": team_forecast.get("expected_turnovers"),
        },
    }


def annotate_matchup_fallback(
    adjusted: dict[str, Any],
) -> dict[str, Any]:
    """Mark the legacy multiplier as a fallback, not the primary path."""

    out = dict(adjusted)
    reason = (
        "No game forecast for this team; the matchup/environment "
        "multiplier is a fallback until a game projection is available."
    )
    out["adjustment_source"] = "matchup_fallback"
    out["environment_counted_once"] = False
    out["matchup_multiplier_applied"] = out.get("adjustment_factor") is not None
    out["drivers"] = [reason]
    out["projection_environment_reason"] = reason
    out.setdefault("scoring_components", None)
    out.setdefault("game_environment", None)
    out.setdefault("role_forecast", None)
    return out
