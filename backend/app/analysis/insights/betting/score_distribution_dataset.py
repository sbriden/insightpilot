"""
Historical residuals for fitting the score-distribution model.

Label residuals against market-implied means (leak-safe):
  resid = actual − market_implied
Features for σ scaling use strength context with before_week=W.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.residual_challenger_dataset import (
    _load_completed_market_games,
)
from app.analysis.insights.betting.score_distribution import (
    build_distribution_features,
)
from app.analysis.insights.betting.team_strength import (
    load_team_strength_context,
    project_strength_scores,
)


def build_score_distribution_rows(
    *,
    season: int,
    through_week: int | None = None,
) -> list[dict[str, Any]]:
    """
    Rows for ``fit_score_distribution``:
    resid_home/away + dist_features (pace, turnover, sample depth).
    """

    games = _load_completed_market_games(
        season=season,
        through_week=through_week,
    )
    if not games:
        return []

    context_by_week: dict[int, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    for game in games:
        week = int(game.get("week") or 0)
        if week <= 0:
            continue
        if week not in context_by_week:
            context_by_week[week] = load_team_strength_context(
                season=season,
                before_week=week,
            )
        context = context_by_week[week]
        home_id = str(game.get("home_team_id") or "")
        away_id = str(game.get("away_team_id") or "")
        market_home = num(game.get("home_implied_total"))
        market_away = num(game.get("away_implied_total"))
        actual_home = num(game.get("home_score"))
        actual_away = num(game.get("away_score"))
        if (
            not home_id
            or not away_id
            or market_home is None
            or market_away is None
            or actual_home is None
            or actual_away is None
        ):
            continue

        _, _, detail = project_strength_scores(
            home_team_id=home_id,
            away_team_id=away_id,
            context=context,
        )
        home_prof = (detail.get("home_profile") or {}) if detail else {}
        away_prof = (detail.get("away_profile") or {}) if detail else {}
        home_off = home_prof.get("offense") or {}
        away_off = away_prof.get("offense") or {}
        min_games = float(
            min(
                int(detail.get("home_games") or 0),
                int(detail.get("away_games") or 0),
            )
            if detail.get("available")
            else 0
        )
        dist_features = build_distribution_features(
            week=week,
            min_games=min_games,
            pace_z=num(detail.get("pace_z")),
            home_turnover_rate=num(home_off.get("turnover_rate")),
            away_turnover_rate=num(away_off.get("turnover_rate")),
            missing_strength=0.0 if detail.get("available") else 1.0,
        )
        rows.append(
            {
                "game_id": str(game.get("game_id") or ""),
                "season": season,
                "week": week,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "market_home": float(market_home),
                "market_away": float(market_away),
                "actual_home": float(actual_home),
                "actual_away": float(actual_away),
                "resid_home": float(actual_home) - float(market_home),
                "resid_away": float(actual_away) - float(market_away),
                "features": dist_features,
                "dist_features": dist_features,
                "market_spread": float(market_away) - float(market_home),
                "market_total": (
                    float(market_home) + float(market_away)
                ),
            }
        )
    return rows
