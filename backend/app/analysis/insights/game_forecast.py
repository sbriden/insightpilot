"""
Shared NFL game forecast.

Betting projections are the source of truth for a game's scoring
environment. This module turns projected team points into the
volume and scoring events player models consume:

    team points ← drives, plays, efficiency, turnovers
                   reconciled to touchdowns and field goals

Score distributions and game-script mixes are reserved for a
later phase. They are described on the forecast and are not
applied to player projections.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any


GAME_FORECAST_MODEL_VERSION = "game_forecast_v1"

# Neutral per-team NFL environment. Plays stay on this pace
# unless a pace input is supplied, so a high total shows up as
# scoring opportunities rather than a second generic boost.
LEAGUE_POINTS = 22.0
LEAGUE_PLAYS = 63.0
LEAGUE_DRIVES = 11.0
LEAGUE_PASS_RATE = 0.58
SACK_RATE = 0.065
LEAGUE_YPA = 7.1
LEAGUE_YPC = 4.3

MARGIN_SD = 13.5
TOTAL_SD = 13.0
TEAM_POINTS_SD = 10.0


def build_game_forecast(
    *,
    projected_home_points: float,
    projected_away_points: float,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: str | None = None,
    season: int | None = None,
    week: int | None = None,
    source: str = "insightpilot_game_model",
    upstream_model_version: str | None = None,
    timestamp: str | None = None,
    pace_z: float | None = None,
    score_distribution_preview: dict[str, Any] | None = None,
    game_scripts_preview: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build one game's shared forecast from projected scores.

    Team points are an output of the game model. Plays, drives,
    passing and rushing volume, turnovers, and scoring events are
    the decomposition that explains those points. Scoring events
    are scaled so touchdowns and field goals reproduce the
    projected team total. That total is not applied again downstream.
    """

    home_points = float(projected_home_points)
    away_points = float(projected_away_points)
    home_name = _abbr(home_team, fallback="HOME")
    away_name = _abbr(away_team, fallback="AWAY")
    pace_factor = _pace_factor(pace_z)
    captured_at = timestamp or datetime.now(timezone.utc).isoformat()

    meta = {
        "event_id": event_id,
        "season": season,
        "week": week,
        "source": source,
        "model_version": GAME_FORECAST_MODEL_VERSION,
        "upstream_model_version": upstream_model_version,
        "timestamp": captured_at,
        "uncertainty": _uncertainty(),
        "pace_factor": round(pace_factor, 3),
        "pace_z": pace_z,
    }
    home = _team_environment(
        team=home_name,
        opponent=away_name,
        side="home",
        points=home_points,
        opponent_points=away_points,
        pace_factor=pace_factor,
        meta=meta,
    )
    away = _team_environment(
        team=away_name,
        opponent=home_name,
        side="away",
        points=away_points,
        opponent_points=home_points,
        pace_factor=pace_factor,
        meta=meta,
    )
    _link_opponents(home, away)
    _link_opponents(away, home)

    total = home_points + away_points
    margin = home_points - away_points
    return {
        "event_id": event_id,
        "sport": "NFL",
        "season": season,
        "week": week,
        "home_team": home_name,
        "away_team": away_name,
        "source": source,
        "model_version": GAME_FORECAST_MODEL_VERSION,
        "upstream_model_version": upstream_model_version,
        "timestamp": captured_at,
        "uncertainty": _uncertainty(),
        "projected_home_points": round(home_points, 1),
        "projected_away_points": round(away_points, 1),
        "projected_total": round(total, 1),
        "projected_margin": round(margin, 1),
        "teams": [home, away],
        "points_identity": {
            "home": _identity_check(home),
            "away": _identity_check(away),
            "formula": "offensive_touchdowns * 7 + field_goals * 3",
        },
        "score_distribution": _deferred_distribution(
            score_distribution_preview
        ),
        "game_scripts": _deferred_scripts(game_scripts_preview),
        "drivers": [
            (
                f"{away_name} {away_points:.1f} at {home_name} "
                f"{home_points:.1f} (total {total:.1f}, "
                f"home margin {margin:+.1f})."
            ),
            (
                "Team points are reconciled to offensive touchdowns "
                "and field goals. Plays follow pace; scoring "
                "opportunities follow the projected total."
            ),
            (
                "Score distribution and game scripts are not applied "
                "to player projections in this phase."
            ),
        ],
        "environment_embedded": True,
    }


def index_team_environments(
    forecast: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Map team abbreviation → that side's environment."""

    indexed: dict[str, dict[str, Any]] = {}
    if not isinstance(forecast, dict):
        return indexed
    for side in forecast.get("teams") or []:
        if not isinstance(side, dict):
            continue
        team = _abbr(side.get("team"), fallback="")
        if team:
            indexed[team] = side
    return indexed


@lru_cache(maxsize=1)
def league_team_environment() -> dict[str, Any]:
    """Neutral team environment used as the player-model baseline."""

    forecast = build_game_forecast(
        event_id="league_prior",
        home_team="HOME",
        away_team="AWAY",
        projected_home_points=LEAGUE_POINTS,
        projected_away_points=LEAGUE_POINTS,
        source="league_prior",
        timestamp="1970-01-01T00:00:00+00:00",
    )
    return dict(forecast["teams"][0])


def forecast_from_snapshot_payload(
    payload: Any,
) -> dict[str, Any] | None:
    """Return a stored game forecast from a snapshot payload."""

    parsed = payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError):
            return None
    if not isinstance(parsed, dict):
        return None
    forecast = parsed.get("game_forecast")
    if isinstance(forecast, dict) and forecast.get("teams"):
        return forecast
    return None


def load_week_game_forecasts(
    *,
    season: int,
    week: int,
) -> dict[str, dict[str, Any]]:
    """
    Team abbreviation → environment for one NFL week.

    Prefers a stored InsightPilot forecast, then rebuilds one from
    published model scores, then from market implied totals.
    Returns an empty dict when the database is unavailable.
    """

    try:
        snapshots = _load_snapshot_rows(season=season, week=week)
        markets = _load_market_rows(season=season, week=week)
    except Exception:
        return {}

    by_game: dict[str, dict[str, Any]] = {}
    for row in markets:
        game_id = str(row.get("game_id") or "").strip()
        home = _num(row.get("home_implied_total"))
        away = _num(row.get("away_implied_total"))
        if not game_id or home is None or away is None:
            continue
        by_game[game_id] = {
            "kind": "market",
            "row": row,
            "home": float(home),
            "away": float(away),
        }
    for row in snapshots:
        game_id = str(row.get("game_id") or "").strip()
        if not game_id:
            continue
        stored = forecast_from_snapshot_payload(row.get("payload"))
        home = _num(row.get("projected_home_score"))
        away = _num(row.get("projected_away_score"))
        if stored is None and (home is None or away is None):
            continue
        by_game[game_id] = {
            "kind": "model",
            "row": row,
            "stored": stored,
            "home": None if home is None else float(home),
            "away": None if away is None else float(away),
        }

    indexed: dict[str, dict[str, Any]] = {}
    for game_id, item in by_game.items():
        row = item["row"]
        stored = item.get("stored")
        if isinstance(stored, dict):
            forecast = stored
        elif item["home"] is None or item["away"] is None:
            continue
        else:
            captured = row.get("captured_at") or row.get("timestamp")
            forecast = build_game_forecast(
                event_id=game_id,
                season=_as_int(row.get("season")) or int(season),
                week=_as_int(row.get("week")) or int(week),
                home_team=row.get("home_team"),
                away_team=row.get("away_team"),
                projected_home_points=float(item["home"]),
                projected_away_points=float(item["away"]),
                source=(
                    "insightpilot_game_model"
                    if item["kind"] == "model"
                    else "market"
                ),
                upstream_model_version=(
                    str(row.get("model_version"))
                    if row.get("model_version")
                    else None
                ),
                timestamp=_iso(captured),
            )
        for team, env in index_team_environments(forecast).items():
            indexed[team] = env
    return indexed


def _team_environment(
    *,
    team: str,
    opponent: str,
    side: str,
    points: float,
    opponent_points: float,
    pace_factor: float,
    meta: dict[str, Any],
) -> dict[str, Any]:
    margin = points - opponent_points
    points_ratio = points / LEAGUE_POINTS if LEAGUE_POINTS else 1.0
    plays = LEAGUE_PLAYS * pace_factor
    drives = LEAGUE_DRIVES * pace_factor

    turnover_rate = _clamp(
        0.105 * (1.08 - 0.08 * points_ratio),
        0.06,
        0.16,
    )
    turnovers = drives * turnover_rate
    interceptions = turnovers * 0.62
    fumbles_lost = max(0.0, turnovers - interceptions)

    opportunity_rate = _clamp(
        0.382 * (0.45 + 0.55 * points_ratio),
        0.20,
        0.65,
    )
    scoring_opportunities = drives * opportunity_rate
    td_share = _clamp(0.57 + 0.05 * (points_ratio - 1.0), 0.42, 0.72)
    fg_share = _clamp(0.36 - 0.03 * (points_ratio - 1.0), 0.18, 0.48)
    if td_share + fg_share > 0.92:
        fg_share = max(0.0, 0.92 - td_share)

    offensive_tds = scoring_opportunities * td_share
    field_goals = scoring_opportunities * fg_share
    component_points = offensive_tds * 7.0 + field_goals * 3.0
    if component_points > 0.0 and points >= 0.0:
        scale = points / component_points
        offensive_tds *= scale
        field_goals *= scale
        scoring_opportunities *= scale
    component_points = offensive_tds * 7.0 + field_goals * 3.0

    pass_rate = _clamp(
        LEAGUE_PASS_RATE - 0.004 * margin,
        0.48,
        0.68,
    )
    pass_attempts = plays * pass_rate * (1.0 - SACK_RATE)
    rush_attempts = plays * (1.0 - pass_rate)
    pass_td_share = _clamp(
        0.63 + (pass_rate - LEAGUE_PASS_RATE) * 1.6,
        0.45,
        0.80,
    )
    pass_tds = offensive_tds * pass_td_share
    rush_tds = max(0.0, offensive_tds - pass_tds)
    ypa = LEAGUE_YPA * (0.94 + 0.06 * points_ratio)
    ypc = LEAGUE_YPC * (0.96 + 0.04 * points_ratio)

    return {
        "team": team,
        "opponent": opponent,
        "side": side,
        "event_id": meta.get("event_id"),
        "season": meta.get("season"),
        "week": meta.get("week"),
        "source": meta.get("source"),
        "model_version": meta.get("model_version"),
        "upstream_model_version": meta.get("upstream_model_version"),
        "timestamp": meta.get("timestamp"),
        "uncertainty": meta.get("uncertainty"),
        "projected_points": round(points, 2),
        "opponent_points": round(opponent_points, 2),
        "projected_total": round(points + opponent_points, 2),
        "projected_margin": round(margin, 2),
        "expected_plays": round(plays, 2),
        "expected_possessions": round(drives, 2),
        "expected_drives": round(drives, 2),
        "expected_scoring_opportunities": round(scoring_opportunities, 2),
        "expected_pass_attempts": round(pass_attempts, 2),
        "expected_rush_attempts": round(rush_attempts, 2),
        "expected_pass_yards": round(pass_attempts * ypa, 1),
        "expected_rush_yards": round(rush_attempts * ypc, 1),
        "expected_pass_tds": round(pass_tds, 3),
        "expected_rush_tds": round(rush_tds, 3),
        "expected_offensive_tds": round(offensive_tds, 3),
        "expected_field_goals": round(field_goals, 3),
        "expected_turnovers": round(turnovers, 3),
        "expected_interceptions": round(interceptions, 3),
        "expected_fumbles_lost": round(fumbles_lost, 3),
        "pass_rate": round(pass_rate, 3),
        "yards_per_pass_attempt": round(ypa, 3),
        "yards_per_rush": round(ypc, 3),
        "points_from_components": round(component_points, 2),
        "points_identity": "offensive_touchdowns * 7 + field_goals * 3",
        "environment_embedded": True,
        "pace_factor": meta.get("pace_factor"),
    }


def _link_opponents(
    side: dict[str, Any],
    opponent: dict[str, Any],
) -> None:
    side["opponent_pass_yards"] = opponent.get("expected_pass_yards")
    side["opponent_rush_yards"] = opponent.get("expected_rush_yards")
    side["opponent_pass_attempts"] = opponent.get("expected_pass_attempts")
    side["opponent_rush_attempts"] = opponent.get("expected_rush_attempts")
    side["opponent_scoring_opportunities"] = opponent.get(
        "expected_scoring_opportunities"
    )
    side["opponent_turnovers"] = opponent.get("expected_turnovers")
    side["opponent_plays"] = opponent.get("expected_plays")
    side["opponent_points"] = opponent.get("projected_points")


def _identity_check(side: dict[str, Any]) -> dict[str, Any]:
    projected = float(side.get("projected_points") or 0.0)
    component = float(side.get("points_from_components") or 0.0)
    return {
        "projected_points": round(projected, 2),
        "component_points": round(component, 2),
        "gap": round(component - projected, 3),
    }


def _deferred_distribution(
    preview: dict[str, Any] | None,
) -> dict[str, Any]:
    slot: dict[str, Any] = {
        "status": "deferred",
        "phase": "later",
        "applied_to_players": False,
        "note": (
            "A distribution of plausible scores is not an input "
            "to player projections yet."
        ),
    }
    if isinstance(preview, dict):
        slot["preview_available"] = bool(preview.get("available"))
        version = preview.get("model_version")
        if version:
            slot["preview_model_version"] = version
    return slot


def _deferred_scripts(
    preview: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    count = len(preview) if isinstance(preview, list) else 0
    return {
        "status": "deferred",
        "phase": "later",
        "applied_to_players": False,
        "preview_count": count,
        "note": (
            "Game-script probabilities are not applied to player "
            "opportunity yet."
        ),
    }


def _uncertainty() -> dict[str, Any]:
    return {
        "margin_sd": MARGIN_SD,
        "total_sd": TOTAL_SD,
        "team_points_sd": TEAM_POINTS_SD,
        "method": "nfl_residual_prior",
    }


def _pace_factor(pace_z: float | None) -> float:
    if pace_z is None:
        return 1.0
    try:
        value = float(pace_z)
    except (TypeError, ValueError):
        return 1.0
    if value != value:
        return 1.0
    return _clamp(1.0 + 0.04 * value, 0.88, 1.12)


def _load_snapshot_rows(
    *,
    season: int,
    week: int,
) -> list[dict[str, Any]]:
    from sqlalchemy import text

    from app.canonical.schema import FANTASY_SCHEMA
    from app.database import engine

    sql = f"""
        SELECT
          game_id,
          season,
          week,
          home_team,
          away_team,
          projected_home_score,
          projected_away_score,
          model_version,
          captured_at,
          payload
        FROM {FANTASY_SCHEMA}.fact_betting_projection_snapshot
        WHERE season = :season
          AND week = :week
    """
    with engine.connect() as connection:
        rows = connection.execute(
            text(sql),
            {"season": int(season), "week": int(week)},
        ).mappings()
        return [dict(row) for row in rows]


def _load_market_rows(
    *,
    season: int,
    week: int,
) -> list[dict[str, Any]]:
    from sqlalchemy import text

    from app.canonical.schema import FANTASY_SCHEMA
    from app.database import engine

    sql = f"""
        SELECT DISTINCT ON (m.game_id)
          m.game_id,
          m.season,
          m.week,
          m.home_implied_total,
          m.away_implied_total,
          m.timestamp,
          m.source,
          ht.team_abbreviation AS home_team,
          at.team_abbreviation AS away_team
        FROM {FANTASY_SCHEMA}.fact_game_market m
        JOIN {FANTASY_SCHEMA}.dim_game g
          ON g.game_id = m.game_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team ht
          ON ht.team_id = g.home_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team at
          ON at.team_id = g.away_team_id
        WHERE m.season = :season
          AND m.week = :week
        ORDER BY m.game_id, m.timestamp DESC NULLS LAST
    """
    with engine.connect() as connection:
        rows = connection.execute(
            text(sql),
            {"season": int(season), "week": int(week)},
        ).mappings()
        return [dict(row) for row in rows]


def _abbr(value: Any, *, fallback: str) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return fallback
    try:
        from app.canonical.ids import canonicalize_team_abbreviation

        canonical = canonicalize_team_abbreviation(text)
        if canonical:
            return str(canonical)
    except Exception:
        pass
    return text


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _as_int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(number)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    text = str(value).strip()
    return text or None
