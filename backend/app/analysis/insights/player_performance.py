"""
Recent Performance & Opportunity for Player Overview.

Joins fact_player_game (production) with fact_player_usage
(opportunity) for the player's latest games. Fantasy points
use the same PPR formula as the proprietary profile layer.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import normalize_float
from app.canonical.analytics.player_fantasy_profile import (
    _ppr_points,
)


RECENT_GAME_COUNT = 5


PRODUCTION_FIELDS_BY_POSITION: dict[str, tuple[tuple[str, str], ...]] = {
    "RB": (
        ("fantasy_points", "Fantasy points"),
        ("rush_attempts", "Rush attempts"),
        ("rush_yards", "Rush yards"),
        ("targets", "Targets"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving yards"),
        ("total_tds", "TDs"),
    ),
    "WR": (
        ("fantasy_points", "Fantasy points"),
        ("targets", "Targets"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving yards"),
        ("air_yards", "Air yards"),
        ("total_tds", "TDs"),
    ),
    "TE": (
        ("fantasy_points", "Fantasy points"),
        ("targets", "Targets"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving yards"),
        ("air_yards", "Air yards"),
        ("total_tds", "TDs"),
    ),
    "QB": (
        ("fantasy_points", "Fantasy points"),
        ("pass_attempts", "Pass attempts"),
        ("pass_yards", "Pass yards"),
        ("pass_tds", "Pass TDs"),
        ("interceptions", "INTs"),
        ("rush_attempts", "Rush attempts"),
        ("rush_yards", "Rush yards"),
    ),
    "FB": (
        ("fantasy_points", "Fantasy points"),
        ("rush_attempts", "Rush attempts"),
        ("rush_yards", "Rush yards"),
        ("targets", "Targets"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving yards"),
        ("total_tds", "TDs"),
    ),
    "HB": (
        ("fantasy_points", "Fantasy points"),
        ("rush_attempts", "Rush attempts"),
        ("rush_yards", "Rush yards"),
        ("targets", "Targets"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving yards"),
        ("total_tds", "TDs"),
    ),
    "K": (
        ("fg_made", "FG made"),
        ("fg_att", "FG attempts"),
        ("fg_made_40_49", "40-49"),
        ("fg_made_50_plus", "50+"),
        ("pat_made", "XP made"),
        ("fantasy_points", "Fantasy points"),
    ),
    "DEF": (
        ("points_allowed", "Pts allowed"),
        ("sacks", "Sacks"),
        ("interceptions", "INTs"),
        ("fumbles_recovered", "Fum rec"),
        ("fantasy_points", "Fantasy points"),
    ),
}

OPPORTUNITY_FIELDS_BY_POSITION: dict[str, tuple[tuple[str, str], ...]] = {
    "RB": (
        ("snap_pct", "Snap %"),
        ("rush_share", "Rush share"),
        ("target_share", "Target share"),
        ("touches", "Touches"),
        ("red_zone_opportunities", "Red-zone opportunities"),
        ("goal_line_opportunities", "Goal-line opportunities"),
    ),
    "WR": (
        ("snap_pct", "Snap %"),
        ("route_participation", "Route participation"),
        ("target_share", "Target share"),
        ("air_yards", "Air yards"),
        ("red_zone_opportunities", "Red-zone opportunities"),
        ("goal_line_opportunities", "Goal-line / end-zone targets"),
    ),
    "TE": (
        ("snap_pct", "Snap %"),
        ("route_participation", "Route participation"),
        ("target_share", "Target share"),
        ("air_yards", "Air yards"),
        ("red_zone_opportunities", "Red-zone opportunities"),
        ("goal_line_opportunities", "Goal-line / end-zone targets"),
    ),
    "QB": (
        ("snap_pct", "Snap %"),
        ("dropbacks", "Dropbacks"),
        ("qb_rush_share", "Rush share"),
        ("designed_rush_attempts", "Designed rushes"),
        ("red_zone_opportunities", "Red-zone opportunities"),
        ("goal_line_opportunities", "Goal-line opportunities"),
    ),
    "FB": (
        ("snap_pct", "Snap %"),
        ("rush_share", "Rush share"),
        ("target_share", "Target share"),
        ("touches", "Touches"),
        ("red_zone_opportunities", "Red-zone opportunities"),
        ("goal_line_opportunities", "Goal-line opportunities"),
    ),
    "HB": (
        ("snap_pct", "Snap %"),
        ("rush_share", "Rush share"),
        ("target_share", "Target share"),
        ("touches", "Touches"),
        ("red_zone_opportunities", "Red-zone opportunities"),
        ("goal_line_opportunities", "Goal-line opportunities"),
    ),
    "K": (),
    "DEF": (),
}


def _position_group(position: Any) -> str:
    value = str(position or "").strip().upper()
    if not value:
        return "WR"
    token = value.replace("-", "/").split("/")[0].strip()
    if token in PRODUCTION_FIELDS_BY_POSITION:
        return token
    if token in {"PK"}:
        return "K"
    if token in {"DST", "D/ST", "D-ST"}:
        return "DEF"
    return "WR"


def _round_metric(value: Any, *, digits: int = 1) -> float | int | None:
    number = normalize_float(value)
    if number is None:
        return None
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return round(number, digits)


def _pct(value: Any) -> float | None:
    number = normalize_float(value)
    if number is None:
        return None
    # Shares may already be 0–1 or 0–100.
    if 0 <= number <= 1.5:
        return round(number * 100.0, 1)
    return round(number, 1)


def production_fields_for_position(
    position: Any,
) -> list[dict[str, str]]:
    group = _position_group(position)
    return [
        {"key": key, "label": label}
        for key, label in PRODUCTION_FIELDS_BY_POSITION[group]
    ]


def opportunity_fields_for_position(
    position: Any,
) -> list[dict[str, str]]:
    group = _position_group(position)
    fields = OPPORTUNITY_FIELDS_BY_POSITION.get(group, ())
    return [
        {"key": key, "label": label}
        for key, label in fields
    ]


def _game_production(row: dict[str, Any]) -> dict[str, Any]:
    rush_tds = normalize_float(row.get("rush_tds")) or 0.0
    receiving_tds = normalize_float(row.get("receiving_tds")) or 0.0
    pass_tds = normalize_float(row.get("pass_tds")) or 0.0
    fg_50 = (
        (normalize_float(row.get("fg_made_50_59")) or 0.0)
        + (normalize_float(row.get("fg_made_60_")) or 0.0)
    )
    fg_made = normalize_float(row.get("fg_made"))
    if fg_made is None:
        fg_made = (
            (normalize_float(row.get("fg_made_0_19")) or 0.0)
            + (normalize_float(row.get("fg_made_20_29")) or 0.0)
            + (normalize_float(row.get("fg_made_30_39")) or 0.0)
            + (normalize_float(row.get("fg_made_40_49")) or 0.0)
            + fg_50
        )
    return {
        "fantasy_points": _round_metric(_ppr_points(row), digits=1),
        "rush_attempts": _round_metric(row.get("rush_attempts"), digits=0),
        "rush_yards": _round_metric(row.get("rush_yards"), digits=0),
        "targets": _round_metric(row.get("targets"), digits=0),
        "receptions": _round_metric(row.get("receptions"), digits=0),
        "receiving_yards": _round_metric(
            row.get("receiving_yards"),
            digits=0,
        ),
        "total_tds": _round_metric(
            rush_tds + receiving_tds + pass_tds,
            digits=0,
        ),
        "pass_attempts": _round_metric(row.get("pass_attempts"), digits=0),
        "pass_yards": _round_metric(row.get("pass_yards"), digits=0),
        "pass_tds": _round_metric(row.get("pass_tds"), digits=0),
        "interceptions": _round_metric(row.get("interceptions"), digits=0),
        "fg_made": _round_metric(fg_made, digits=0),
        "fg_att": _round_metric(row.get("fg_att"), digits=0),
        "fg_made_40_49": _round_metric(
            row.get("fg_made_40_49"),
            digits=0,
        ),
        "fg_made_50_plus": _round_metric(fg_50, digits=0),
        "pat_made": _round_metric(row.get("pat_made"), digits=0),
        "pat_att": _round_metric(row.get("pat_att"), digits=0),
        "points_allowed": _round_metric(
            row.get("points_allowed"),
            digits=0,
        ),
        "sacks": _round_metric(row.get("sacks"), digits=1),
        "fumbles_recovered": _round_metric(
            row.get("fumbles_recovered"),
            digits=0,
        ),
    }


def _game_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    red_zone = (
        (normalize_float(row.get("red_zone_touches")) or 0.0)
        + (normalize_float(row.get("red_zone_targets")) or 0.0)
    )
    goal_line = (
        (normalize_float(row.get("goal_line_carries")) or 0.0)
        + (normalize_float(row.get("end_zone_targets")) or 0.0)
    )
    snap_pct = _pct(row.get("offensive_snap_share"))
    route_participation = _pct(
        row.get("route_participation_rate")
    )
    # Avoid showing two identical participation rates.
    if (
        route_participation is not None
        and snap_pct is not None
        and abs(float(route_participation) - float(snap_pct))
        < 0.05
    ):
        route_participation = None

    return {
        "snap_pct": snap_pct,
        "route_participation": route_participation,
        "target_share": _pct(row.get("target_share")),
        "rush_share": _pct(
            row.get("rush_share")
            if row.get("rush_share") is not None
            else row.get("qb_rush_share")
        ),
        "touches": _round_metric(row.get("touches"), digits=0),
        "air_yards": _round_metric(row.get("air_yards"), digits=0),
        "red_zone_opportunities": _round_metric(red_zone, digits=0),
        "goal_line_opportunities": _round_metric(goal_line, digits=0),
        "dropbacks": _round_metric(row.get("dropbacks"), digits=0),
        "designed_rush_attempts": _round_metric(
            row.get("designed_rush_attempts"),
            digits=0,
        ),
        "qb_rush_share": _pct(row.get("qb_rush_share")),
    }


def _opponent_lookup_for_games(
    game_rows: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, str | None]]:
    """
    Map (game_id, team_id) -> opponent / opponent_label / home_away.
    """

    pairs: list[tuple[str, str]] = []
    game_ids: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_games: set[str] = set()
    for row in game_rows:
        game_id = str(row.get("game_id") or "").strip()
        team_id = str(row.get("team_id") or "").strip()
        if not game_id or not team_id:
            continue
        key = (game_id, team_id)
        if key not in seen_pairs:
            seen_pairs.add(key)
            pairs.append(key)
        if game_id not in seen_games:
            seen_games.add(game_id)
            game_ids.append(game_id)

    if not pairs or not game_ids:
        return {}

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return {}

    game_params = {
        f"game_{index}": game_id
        for index, game_id in enumerate(game_ids)
    }
    game_sql = ", ".join(
        f":game_{index}" for index in range(len(game_ids))
    )

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      dg.game_id,
                      dg.home_team_id,
                      dg.away_team_id,
                      home.team_abbreviation AS home_abbr,
                      away.team_abbreviation AS away_abbr
                    FROM {FANTASY_SCHEMA}.dim_game dg
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team home
                      ON home.team_id = dg.home_team_id
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team away
                      ON away.team_id = dg.away_team_id
                    WHERE dg.game_id IN ({game_sql})
                    """
                ),
                connection,
                params=game_params,
            )
    except Exception:
        return {}

    games_by_id: dict[str, dict[str, Any]] = {}
    for record in frame.to_dict(orient="records"):
        game_id = str(record.get("game_id") or "").strip()
        if game_id:
            games_by_id[game_id] = record

    lookup: dict[tuple[str, str], dict[str, str | None]] = {}
    for game_id, team_id in pairs:
        record = games_by_id.get(game_id)
        if not record:
            continue
        home_id = str(record.get("home_team_id") or "").strip()
        away_id = str(record.get("away_team_id") or "").strip()
        home_abbr = record.get("home_abbr")
        away_abbr = record.get("away_abbr")
        opponent = None
        home_away = None
        if team_id and team_id == home_id:
            opponent = away_abbr
            home_away = "vs"
        elif team_id and team_id == away_id:
            opponent = home_abbr
            home_away = "@"
        opponent_text = (
            str(opponent).strip() if opponent is not None else None
        )
        if not opponent_text or opponent_text.lower() == "nan":
            opponent_text = None
        opponent_label = None
        if opponent_text:
            opponent_label = f"{home_away or 'vs'} {opponent_text}"
        lookup[(game_id, team_id)] = {
            "opponent": opponent_text,
            "opponent_label": opponent_label,
            "home_away": home_away,
        }
    return lookup


def build_performance_and_opportunity(
    player_id: str,
    *,
    position: str | None = None,
    season: int | None = None,
    week: int | None = None,
    game_count: int = RECENT_GAME_COUNT,
) -> dict[str, Any]:
    """
    Recent 4–5 game production + opportunity trend for a player.
    """

    pid = str(player_id or "").strip()
    empty = {
        "position_group": _position_group(position),
        "production_fields": production_fields_for_position(position),
        "opportunity_fields": opportunity_fields_for_position(position),
        "recent_games": [],
        "framing": (
            "Production tells us what happened. "
            "Opportunity helps tell us what might happen next."
        ),
    }
    if not pid:
        return empty

    seasons = [season] if season is not None else None
    try:
        from app.canonical.fact_player_game import (
            FACT_PLAYER_GAME_COLUMNS,
        )
        from app.canonical.fact_player_usage import (
            FACT_PLAYER_USAGE_COLUMNS,
        )
        from app.canonical.analytics.persist import load_rows
        import nflreadpy as nfl

        if seasons is None:
            seasons = [int(nfl.get_current_season())]

        games = load_rows(
            "fact_player_game",
            FACT_PLAYER_GAME_COLUMNS,
            seasons=seasons,
            player_id=pid,
            order_by="season, week, game_id",
        )
        usage = load_rows(
            "fact_player_usage",
            FACT_PLAYER_USAGE_COLUMNS,
            seasons=seasons,
            player_id=pid,
            order_by="season, week, game_id",
        )
    except Exception:
        return empty

    player_games = (
        games.to_dict(orient="records")
        if games is not None and not games.empty
        else []
    )

    if not player_games:
        return empty

    def sort_key(row: dict[str, Any]) -> tuple[int, int]:
        try:
            return (int(row.get("season") or 0), int(row.get("week") or 0))
        except (TypeError, ValueError):
            return (0, 0)

    if season is not None and week is not None:
        filtered = []
        for row in player_games:
            try:
                s = int(row.get("season"))
                w = int(row.get("week"))
            except (TypeError, ValueError):
                continue
            if (s, w) <= (int(season), int(week)):
                filtered.append(row)
        if filtered:
            player_games = filtered

    player_games.sort(key=sort_key, reverse=True)
    recent = player_games[: max(1, int(game_count))]
    opponent_lookup = _opponent_lookup_for_games(recent)

    usage_lookup: dict[tuple[int, int], dict[str, Any]] = {}
    if usage is not None and not usage.empty:
        for row in usage.to_dict(orient="records"):
            try:
                key = (int(row.get("season")), int(row.get("week")))
            except (TypeError, ValueError):
                continue
            usage_lookup[key] = row

    recent_games: list[dict[str, Any]] = []
    for row in recent:
        try:
            s = int(row.get("season"))
            w = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        usage_row = usage_lookup.get((s, w), {})
        production = _game_production(row)
        opportunity = _game_opportunity(usage_row)
        if production.get("air_yards") is None:
            production["air_yards"] = opportunity.get("air_yards")

        game_id = str(row.get("game_id") or "").strip()
        team_id = str(row.get("team_id") or "").strip()
        opponent_info = opponent_lookup.get((game_id, team_id), {})

        recent_games.append(
            {
                "season": s,
                "week": w,
                "label": f"W{w}",
                "opponent": opponent_info.get("opponent"),
                "opponent_label": opponent_info.get(
                    "opponent_label"
                ),
                "home_away": opponent_info.get("home_away"),
                "production": production,
                "opportunity": opportunity,
            }
        )

    recent_games.reverse()

    opportunity_fields = opportunity_fields_for_position(
        position
    )
    opportunity_fields = [
        field
        for field in opportunity_fields
        if any(
            game.get("opportunity", {}).get(field["key"])
            is not None
            for game in recent_games
        )
    ]

    # Drop route participation when it merely duplicates snap %
    # (or would after a missing-routes fallback).
    if any(
        field["key"] == "route_participation"
        for field in opportunity_fields
    ) and any(
        field["key"] == "snap_pct"
        for field in opportunity_fields
    ):
        routes = [
            game.get("opportunity", {}).get("route_participation")
            for game in recent_games
        ]
        snaps = [
            game.get("opportunity", {}).get("snap_pct")
            for game in recent_games
        ]
        paired = [
            (route, snap)
            for route, snap in zip(routes, snaps)
            if route is not None and snap is not None
        ]
        if paired and all(
            abs(float(route) - float(snap)) < 0.05
            for route, snap in paired
        ):
            opportunity_fields = [
                field
                for field in opportunity_fields
                if field["key"] != "route_participation"
            ]

    return {
        "position_group": _position_group(position),
        "production_fields": production_fields_for_position(position),
        "opportunity_fields": opportunity_fields,
        "recent_games": recent_games,
        "framing": (
            "Production tells us what happened. "
            "Opportunity helps tell us what might happen next."
        ),
    }
