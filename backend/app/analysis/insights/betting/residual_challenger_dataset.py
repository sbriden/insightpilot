"""
Historical market-error rows for fitting the residual challenger.

Label: y = actual_score − market_implied_score
Features: leak-safe strength context with before_week = game week.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.player_context import (
    combined_score_adjustments,
    load_week_player_context,
    refine_injury_with_market_move,
    team_injury_context,
)
from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.opponent_tendency import (
    load_opponent_tendency_context,
)
from app.analysis.insights.betting.residual_features import (
    build_residual_features,
)
from app.analysis.insights.betting.team_strength import (
    load_team_strength_context,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


def build_challenger_training_rows(
    *,
    season: int,
    through_week: int | None = None,
) -> list[dict[str, Any]]:
    """
    Reconstruct (features, y_home, y_away) for completed games.

    Uses opening/current market implied totals when available.
    Strength profiles exclude the game week (before_week=week).
    Injury context is leak-safe (report week ≤ game week).
    """

    games = _load_completed_market_games(
        season=season,
        through_week=through_week,
    )
    if not games:
        return []

    # Cache strength + injury + tendency context by week.
    context_by_week: dict[int, dict[str, Any]] = {}
    injury_by_week: dict[int, dict[str, Any]] = {}
    tendency_by_week: dict[int, dict[str, Any]] = {}
    rest_by_team = rest_days_by_game(season=season)
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
        if week not in tendency_by_week:
            try:
                tendency_by_week[week] = load_opponent_tendency_context(
                    season=season,
                    before_week=week,
                    sport="NFL",
                )
            except Exception:
                tendency_by_week[week] = {"profiles": {}}
        if week not in injury_by_week:
            try:
                injury_by_week[week] = load_week_player_context(
                    season=season,
                    week=week,
                )
            except Exception:
                injury_by_week[week] = {"by_team": {}}
        context = context_by_week[week]
        tendency_context = tendency_by_week[week]
        player_context = injury_by_week[week]
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

        opening_home = num(game.get("opening_home_implied_total"))
        opening_away = num(game.get("opening_away_implied_total"))
        opening_spread_raw = num(game.get("opening_spread"))
        current_spread = float(market_away) - float(market_home)
        if opening_home is not None and opening_away is not None:
            opening_spread = float(opening_away) - float(opening_home)
        elif opening_spread_raw is not None:
            # nflverse spread_line: positive = home favored → negate.
            opening_spread = -float(opening_spread_raw)
        else:
            opening_spread = current_spread
        opening_total = num(game.get("opening_over_under"))
        current_total = num(game.get("over_under"))
        spread_move = round(
            float(current_spread) - float(opening_spread), 1
        )
        total_move = None
        if opening_total is not None and current_total is not None:
            total_move = float(current_total) - float(opening_total)

        game_id = str(game.get("game_id") or "")
        rest_home, rest_away = rest_by_team.get(game_id, (7.0, 7.0))

        home_injury = refine_injury_with_market_move(
            team_injury_context(player_context, home_id),
            spread_move=spread_move,
            total_move=total_move,
            is_home=True,
        )
        away_injury = refine_injury_with_market_move(
            team_injury_context(player_context, away_id),
            spread_move=spread_move,
            total_move=total_move,
            is_home=False,
        )
        home_adj, away_adj = combined_score_adjustments(
            home_injury=home_injury,
            away_injury=away_injury,
        )

        payload = build_residual_features(
            home_team_id=home_id,
            away_team_id=away_id,
            strength_context=context,
            market_home=float(market_home),
            market_away=float(market_away),
            market_spread=(
                float(market_away) - float(market_home)
                if market_home is not None and market_away is not None
                else num(game.get("spread"))
            ),
            market_total=num(game.get("over_under")),
            spread_move=spread_move,
            total_move=total_move,
            week=week,
            home_rest_days=rest_home,
            away_rest_days=rest_away,
            home_injury_adj=home_adj,
            away_injury_adj=away_adj,
            home_injury=home_injury,
            away_injury=away_injury,
            tendency_context=tendency_context,
        )
        rows.append(
            {
                "game_id": game_id,
                "season": season,
                "week": week,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "market_home": float(market_home),
                "market_away": float(market_away),
                "actual_home": float(actual_home),
                "actual_away": float(actual_away),
                "y_home": float(actual_home) - float(market_home),
                "y_away": float(actual_away) - float(market_away),
                "features": payload.get("features"),
                "vector": payload.get("vector"),
                "available": payload.get("available"),
                "home_injury_adj": home_adj,
                "away_injury_adj": away_adj,
                "home_rest_days": rest_home,
                "away_rest_days": rest_away,
                "spread_move": spread_move,
                "total_move": total_move,
                "qb_out_home": (payload.get("features") or {}).get(
                    "qb_out_home"
                ),
                "qb_out_away": (payload.get("features") or {}).get(
                    "qb_out_away"
                ),
            }
        )
    return rows


def _load_completed_market_games(
    *,
    season: int,
    through_week: int | None = None,
    schema: str | None = None,
) -> list[dict[str, Any]]:
    db_schema = schema or FANTASY_SCHEMA
    clauses = [
        "g.season = :season",
        "g.home_score IS NOT NULL",
        "g.away_score IS NOT NULL",
        "m.home_implied_total IS NOT NULL",
        "m.away_implied_total IS NOT NULL",
    ]
    params: dict[str, Any] = {"season": int(season)}
    if through_week is not None:
        clauses.append("g.week <= :through_week")
        params["through_week"] = int(through_week)

    sql = f"""
        SELECT DISTINCT ON (g.game_id)
          g.game_id,
          g.season,
          g.week,
          g.home_team_id,
          g.away_team_id,
          g.home_score,
          g.away_score,
          g.game_date,
          m.spread,
          m.over_under,
          m.home_implied_total,
          m.away_implied_total,
          m.opening_spread,
          m.opening_over_under,
          m.opening_home_implied_total,
          m.opening_away_implied_total
        FROM {db_schema}.dim_game g
        JOIN {db_schema}.fact_game_market m
          ON m.game_id = g.game_id
        WHERE {' AND '.join(clauses)}
        ORDER BY g.game_id, m.timestamp DESC NULLS LAST
    """
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(sql), params).mappings()
            return [dict(row) for row in rows]
    except Exception:
        return []


def rest_days_by_game(
    *,
    season: int,
) -> dict[str, tuple[float, float]]:
    """Days since each team's previous game (default 7)."""

    sql = f"""
        SELECT
          game_id,
          home_team_id,
          away_team_id,
          game_date,
          week
        FROM {FANTASY_SCHEMA}.dim_game
        WHERE season = :season
          AND game_date IS NOT NULL
        ORDER BY game_date ASC NULLS LAST, week ASC
    """
    try:
        with engine.connect() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    text(sql), {"season": int(season)}
                ).mappings()
            ]
    except Exception:
        return {}

    last_date: dict[str, Any] = {}
    out: dict[str, tuple[float, float]] = {}
    for row in rows:
        game_id = str(row.get("game_id") or "")
        home = str(row.get("home_team_id") or "")
        away = str(row.get("away_team_id") or "")
        game_date = row.get("game_date")
        home_rest = 7.0
        away_rest = 7.0
        if game_date is not None:
            if home in last_date and last_date[home] is not None:
                try:
                    home_rest = float(
                        (game_date - last_date[home]).days
                    )
                except Exception:
                    home_rest = 7.0
            if away in last_date and last_date[away] is not None:
                try:
                    away_rest = float(
                        (game_date - last_date[away]).days
                    )
                except Exception:
                    away_rest = 7.0
            if home:
                last_date[home] = game_date
            if away:
                last_date[away] = game_date
        if game_id:
            out[game_id] = (
                max(3.0, min(14.0, home_rest)),
                max(3.0, min(14.0, away_rest)),
            )
    return out


def _rest_days_by_game(
    *,
    season: int,
) -> dict[str, tuple[float, float]]:
    return rest_days_by_game(season=season)
