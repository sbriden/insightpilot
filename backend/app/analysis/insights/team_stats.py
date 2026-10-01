"""
Team Stats — season leaders, team totals, and depth chart.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import normalize_float
from app.canonical.dim_team import (
    NON_TEAM_ABBREVIATIONS,
    TEAM_ABBREVIATION_ALIASES,
)


LEADER_LIMIT = 8

# Canonical abbreviations that ESPN's logo CDN spells differently.
_ESPN_LOGO_ABBREVIATIONS = {
    "LA": "lar",
    "WAS": "wsh",
}

DEPTH_POSITION_ORDER = (
    "QB",
    "RB",
    "FB",
    "WR",
    "TE",
    "LT",
    "LG",
    "C",
    "RG",
    "RT",
)


def _num(value: Any) -> float | None:
    return normalize_float(value)


def _int(value: Any) -> int | None:
    number = normalize_float(value)
    if number is None:
        return None
    return int(round(number))


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    num = _num(numerator)
    den = _num(denominator)
    if num is None or den is None or den == 0:
        return None
    return num / den


def _round(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _compact(values: dict[str, Any]) -> dict[str, Any] | None:
    cleaned = {
        key: value
        for key, value in values.items()
        if value is not None
    }
    return cleaned or None


def _sum_stat(
    players: list[dict[str, Any]],
    key: str,
) -> float | None:
    total = 0.0
    seen = False
    for player in players:
        value = _num(player.get(key))
        if value is None:
            continue
        total += value
        seen = True
    return total if seen else None


def team_logo_url(abbreviation: str | None) -> str | None:
    """ESPN NFL logo for a canonical team abbreviation."""

    abbr = str(abbreviation or "").strip().upper()
    if not abbr:
        return None
    espn = _ESPN_LOGO_ABBREVIATIONS.get(abbr, abbr).lower()
    return (
        "https://a.espncdn.com/i/teamlogos/nfl/500/"
        f"{espn}.png"
    )


def build_team_totals(
    environment: dict[str, Any] | None,
    players: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """
    Season team totals plus derived efficiency.

    ``environment`` is one aggregated offense/defense row.
    Skill rates come from summed player season stats.
    """

    env = environment or {}
    games = _int(env.get("games")) or 0
    defense_games = _int(env.get("defense_games")) or 0
    rate_games = defense_games or games

    points = _num(env.get("points"))
    yards = _num(env.get("yards"))
    plays = _num(env.get("offensive_plays"))
    pass_attempts = _num(env.get("pass_attempts"))
    rush_attempts = _num(env.get("rush_attempts"))
    points_allowed = _num(env.get("points_allowed"))

    offense = None
    if games > 0:
        offense = _compact(
            {
                "points": _int(points),
                "points_per_game": _round(
                    _safe_div(points, games), 1
                ),
                "yards": _int(yards),
                "yards_per_game": _round(
                    _safe_div(yards, games), 1
                ),
                "yards_per_play": _round(
                    _safe_div(yards, plays), 2
                ),
                "epa_per_play": _round(
                    _safe_div(env.get("offensive_epa"), plays),
                    3,
                ),
                "pass_epa_per_attempt": _round(
                    _safe_div(
                        env.get("pass_epa"),
                        pass_attempts,
                    ),
                    3,
                ),
                "rush_epa_per_attempt": _round(
                    _safe_div(
                        env.get("rush_epa"),
                        rush_attempts,
                    ),
                    3,
                ),
                "pass_rate": _round(
                    _safe_div(pass_attempts, plays),
                    4,
                ),
                "seconds_per_play": _round(
                    _num(env.get("pace")),
                    1,
                ),
                "red_zone_td_rate": _round(
                    _safe_div(
                        env.get("red_zone_tds"),
                        env.get("red_zone_trips"),
                    ),
                    4,
                ),
                "turnovers": _int(env.get("turnovers")),
                "turnovers_per_game": _round(
                    _safe_div(env.get("turnovers"), games),
                    2,
                ),
            }
        )

    defense = None
    if rate_games > 0 and (
        points_allowed is not None
        or _num(env.get("yards_allowed")) is not None
    ):
        defense = _compact(
            {
                "points_allowed": _int(points_allowed),
                "points_allowed_per_game": _round(
                    _safe_div(points_allowed, rate_games),
                    1,
                ),
                "yards_allowed": _int(env.get("yards_allowed")),
                "yards_allowed_per_game": _round(
                    _safe_div(env.get("yards_allowed"), rate_games),
                    1,
                ),
                "pass_yards_allowed_per_game": _round(
                    _safe_div(
                        env.get("pass_yards_allowed"),
                        rate_games,
                    ),
                    1,
                ),
                "rush_yards_allowed_per_game": _round(
                    _safe_div(
                        env.get("rush_yards_allowed"),
                        rate_games,
                    ),
                    1,
                ),
                "pass_epa_allowed_per_game": _round(
                    _safe_div(
                        env.get("pass_epa_allowed"),
                        rate_games,
                    ),
                    3,
                ),
                "rush_epa_allowed_per_game": _round(
                    _safe_div(
                        env.get("rush_epa_allowed"),
                        rate_games,
                    ),
                    3,
                ),
                "sack_rate": _round(
                    _num(env.get("sack_rate")),
                    4,
                ),
                "pressure_rate": _round(
                    _num(env.get("pressure_rate")),
                    4,
                ),
            }
        )

    wins = _int(env.get("wins")) or 0
    losses = _int(env.get("losses")) or 0
    ties = _int(env.get("ties")) or 0
    record = None
    if wins + losses + ties > 0:
        record = {
            "wins": wins,
            "losses": losses,
            "ties": ties,
        }
        if points is not None and points_allowed is not None:
            record["point_differential"] = int(
                round(points - points_allowed)
            )

    roster = players or []
    completions = _sum_stat(roster, "pass_completions")
    attempts = _sum_stat(roster, "pass_attempts")
    pass_yards = _sum_stat(roster, "pass_yards")
    rush_yards = _sum_stat(roster, "rush_yards")
    carries = _sum_stat(roster, "rush_attempts")
    receptions = _sum_stat(roster, "receptions")
    targets = _sum_stat(roster, "targets")
    receiving_yards = _sum_stat(roster, "receiving_yards")
    efficiency = _compact(
        {
            "completion_pct": _round(
                _safe_div(completions, attempts),
                4,
            ),
            "yards_per_attempt": _round(
                _safe_div(pass_yards, attempts),
                2,
            ),
            "yards_per_carry": _round(
                _safe_div(rush_yards, carries),
                2,
            ),
            "catch_rate": _round(
                _safe_div(receptions, targets),
                4,
            ),
            "yards_per_target": _round(
                _safe_div(receiving_yards, targets),
                2,
            ),
            "yards_per_reception": _round(
                _safe_div(receiving_yards, receptions),
                2,
            ),
        }
    )

    if (
        offense is None
        and defense is None
        and record is None
        and efficiency is None
    ):
        return None

    return {
        "games": games or defense_games or None,
        "record": record,
        "offense": offense,
        "defense": defense,
        "efficiency": efficiency,
    }


def _team_identity(row: dict[str, Any], abbr: str) -> dict[str, Any]:
    return {
        "team_id": str(row.get("team_id") or ""),
        "abbreviation": abbr,
        "name": (
            str(row.get("team_name")).strip()
            if row.get("team_name") is not None
            else abbr
        ),
        "conference": (
            str(row.get("conference")).strip()
            if row.get("conference") is not None
            else None
        ),
        "division": (
            str(row.get("division")).strip()
            if row.get("division") is not None
            else None
        ),
        "logo_url": team_logo_url(abbr),
    }


def list_fantasy_teams() -> list[dict[str, Any]]:
    """Active NFL franchises for the team picker."""

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return []

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      team_id,
                      team_abbreviation,
                      team_name,
                      conference,
                      division
                    FROM {FANTASY_SCHEMA}.dim_team
                    WHERE team_abbreviation IS NOT NULL
                    ORDER BY team_abbreviation
                    """
                ),
                connection,
            )
    except Exception:
        return []

    teams: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        abbr = str(row.get("team_abbreviation") or "").strip().upper()
        if (
            not abbr
            or abbr in NON_TEAM_ABBREVIATIONS
            or abbr in TEAM_ABBREVIATION_ALIASES
        ):
            continue
        teams.append(_team_identity(row, abbr))
    return teams


def get_team_stats(
    team: str,
    *,
    season: int | None = None,
) -> dict[str, Any] | None:
    """
    Season-to-date player leaders and latest depth chart for a team.
    """

    abbr = str(team or "").strip().upper()
    if not abbr or abbr in NON_TEAM_ABBREVIATIONS:
        return None

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    if season is None:
        try:
            import nflreadpy as nfl

            season = int(nfl.get_current_season())
        except Exception:
            season = None

    params: dict[str, Any] = {"team": abbr}

    try:
        with engine.connect() as connection:
            team_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      team_id,
                      team_abbreviation,
                      team_name,
                      conference,
                      division
                    FROM {FANTASY_SCHEMA}.dim_team
                    WHERE UPPER(team_abbreviation) = :team
                    LIMIT 1
                    """
                ),
                connection,
                params=params,
            )
            if team_frame.empty:
                return None

            team_row = team_frame.iloc[0].to_dict()
            team_id = str(team_row.get("team_id") or "")

            if season is None:
                season_row = connection.execute(
                    text(
                        f"""
                        SELECT MAX(season) AS season
                        FROM {FANTASY_SCHEMA}.fact_player_game
                        """
                    )
                ).mappings().first()
                season = (
                    int(season_row["season"])
                    if season_row and season_row["season"] is not None
                    else None
                )

            if season is None:
                return {
                    "team": _team_identity(team_row, abbr),
                    "season": None,
                    "depth_season": None,
                    "depth_week": None,
                    "depth_as_of": None,
                    "team_totals": None,
                    "players": [],
                    "passing_leaders": [],
                    "rushing_leaders": [],
                    "receiving_leaders": [],
                    "depth_chart": [],
                }

            query_params = {
                "team_id": team_id,
                "season": int(season),
            }

            players_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      p.player_id,
                      p.name,
                      p.position,
                      p.status,
                      SUM(g.pass_attempts) AS pass_attempts,
                      SUM(g.pass_completions) AS pass_completions,
                      SUM(g.pass_yards) AS pass_yards,
                      SUM(g.pass_tds) AS pass_tds,
                      SUM(g.interceptions) AS interceptions,
                      SUM(g.rush_attempts) AS rush_attempts,
                      SUM(g.rush_yards) AS rush_yards,
                      SUM(g.rush_tds) AS rush_tds,
                      SUM(g.targets) AS targets,
                      SUM(g.receptions) AS receptions,
                      SUM(g.receiving_yards) AS receiving_yards,
                      SUM(g.receiving_tds) AS receiving_tds,
                      COUNT(*) AS games
                    FROM {FANTASY_SCHEMA}.fact_player_game g
                    INNER JOIN {FANTASY_SCHEMA}.dim_player p
                      ON p.player_id = g.player_id
                    WHERE g.team_id = :team_id
                      AND g.season = :season
                    GROUP BY
                      p.player_id,
                      p.name,
                      p.position,
                      p.status
                    ORDER BY p.position, p.name
                    """
                ),
                connection,
                params=query_params,
            )

            depth_frame = pd.read_sql_query(
                text(
                    f"""
                    WITH latest_season AS (
                      SELECT COALESCE(
                        (
                          SELECT MAX(season)
                          FROM {FANTASY_SCHEMA}.fact_depth_chart
                          WHERE team_id = :team_id
                            AND season = :season
                        ),
                        (
                          SELECT MAX(season)
                          FROM {FANTASY_SCHEMA}.fact_depth_chart
                          WHERE team_id = :team_id
                            AND season IS NOT NULL
                        )
                      ) AS season
                    ),
                    bounds AS (
                      SELECT
                        MAX(d.week) AS week,
                        MAX(d.effective_date) AS effective_date
                      FROM {FANTASY_SCHEMA}.fact_depth_chart d
                      INNER JOIN latest_season ls
                        ON d.season = ls.season
                      WHERE d.team_id = :team_id
                    )
                    SELECT DISTINCT ON (d.position, d.player_id)
                      d.position,
                      d.depth_order,
                      d.role,
                      d.season,
                      d.week,
                      d.effective_date,
                      p.player_id,
                      p.name
                    FROM {FANTASY_SCHEMA}.fact_depth_chart d
                    INNER JOIN latest_season ls
                      ON d.season = ls.season
                    INNER JOIN bounds b
                      ON TRUE
                    INNER JOIN {FANTASY_SCHEMA}.dim_player p
                      ON p.player_id = d.player_id
                    WHERE d.team_id = :team_id
                      AND (
                        (
                          b.week IS NOT NULL
                          AND d.week = b.week
                        )
                        OR (
                          b.week IS NULL
                          AND (
                            b.effective_date IS NULL
                            OR d.effective_date = b.effective_date
                          )
                        )
                      )
                    ORDER BY
                      d.position,
                      d.player_id,
                      d.depth_order ASC NULLS LAST
                    """
                ),
                connection,
                params={
                    "team_id": team_id,
                    "season": int(season),
                },
            )
    except Exception:
        return None

    players = [
        _player_row(row)
        for row in players_frame.to_dict(orient="records")
    ]

    passing_leaders = _rank_leaders(
        players,
        metric="pass_yards",
        require=("pass_attempts",),
    )
    rushing_leaders = _rank_leaders(
        players,
        metric="rush_yards",
        require=("rush_attempts",),
    )
    receiving_leaders = _rank_leaders(
        players,
        metric="receiving_yards",
        require=("targets", "receptions"),
    )

    depth_chart = _group_depth_chart(depth_frame)
    depth_season = None
    depth_week = None
    if not depth_frame.empty:
        depth_season = _int(depth_frame.iloc[0].get("season"))
        depth_week = _int(depth_frame.iloc[0].get("week"))

    environment = _load_team_environment(
        team_id,
        int(season),
    )

    return {
        "team": _team_identity(team_row, abbr),
        "season": int(season) if season is not None else None,
        "team_totals": build_team_totals(environment, players),
        "depth_season": depth_season,
        "depth_week": depth_week,
        "depth_as_of": (
            None
            if depth_frame.empty
            else (
                str(depth_frame.iloc[0].get("effective_date"))
                if depth_frame.iloc[0].get("effective_date")
                is not None
                else None
            )
        ),
        "players": players,
        "passing_leaders": passing_leaders,
        "rushing_leaders": rushing_leaders,
        "receiving_leaders": receiving_leaders,
        "depth_chart": depth_chart,
    }


def _load_team_environment(
    team_id: str,
    season: int,
) -> dict[str, Any] | None:
    """
    Season offense and defense aggregates for one franchise.

    Regular-season games only. A missing defense table still
    returns the offense row.
    """

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    offense_sql = f"""
        SELECT
          COUNT(*) AS games,
          SUM(points) AS points,
          SUM(yards) AS yards,
          SUM(offensive_plays) AS offensive_plays,
          SUM(pass_attempts) AS pass_attempts,
          SUM(rush_attempts) AS rush_attempts,
          SUM(offensive_epa) AS offensive_epa,
          SUM(pass_epa) AS pass_epa,
          SUM(rush_epa) AS rush_epa,
          SUM(red_zone_trips) AS red_zone_trips,
          SUM(red_zone_td_rate * red_zone_trips) AS red_zone_tds,
          SUM(turnovers) AS turnovers,
          AVG(pace) AS pace
        FROM {FANTASY_SCHEMA}.fact_team_game
        WHERE team_id = :team_id
          AND season = :season
          AND (
            season_type IS NULL
            OR UPPER(season_type) IN ('REG', 'REGULAR')
          )
    """
    joined_sql = f"""
        SELECT
          COUNT(*) AS games,
          SUM(tg.points) AS points,
          SUM(tg.yards) AS yards,
          SUM(tg.offensive_plays) AS offensive_plays,
          SUM(tg.pass_attempts) AS pass_attempts,
          SUM(tg.rush_attempts) AS rush_attempts,
          SUM(tg.offensive_epa) AS offensive_epa,
          SUM(tg.pass_epa) AS pass_epa,
          SUM(tg.rush_epa) AS rush_epa,
          SUM(tg.red_zone_trips) AS red_zone_trips,
          SUM(tg.red_zone_td_rate * tg.red_zone_trips)
            AS red_zone_tds,
          SUM(tg.turnovers) AS turnovers,
          AVG(tg.pace) AS pace,
          SUM(
            CASE
              WHEN tg.points IS NOT NULL
                AND dg.points_allowed IS NOT NULL
                AND tg.points > dg.points_allowed
              THEN 1 ELSE 0
            END
          ) AS wins,
          SUM(
            CASE
              WHEN tg.points IS NOT NULL
                AND dg.points_allowed IS NOT NULL
                AND tg.points < dg.points_allowed
              THEN 1 ELSE 0
            END
          ) AS losses,
          SUM(
            CASE
              WHEN tg.points IS NOT NULL
                AND dg.points_allowed IS NOT NULL
                AND tg.points = dg.points_allowed
              THEN 1 ELSE 0
            END
          ) AS ties,
          SUM(dg.points_allowed) AS points_allowed,
          SUM(dg.yards_allowed) AS yards_allowed,
          SUM(dg.pass_yards_allowed) AS pass_yards_allowed,
          SUM(dg.rush_yards_allowed) AS rush_yards_allowed,
          SUM(dg.pass_epa_allowed) AS pass_epa_allowed,
          SUM(dg.rush_epa_allowed) AS rush_epa_allowed,
          AVG(dg.sack_rate) AS sack_rate,
          AVG(dg.pressure_rate) AS pressure_rate,
          COUNT(dg.game_id) AS defense_games
        FROM {FANTASY_SCHEMA}.fact_team_game tg
        LEFT JOIN {FANTASY_SCHEMA}.fact_defensive_game dg
          ON dg.defensive_team_id = tg.team_id
         AND dg.game_id = tg.game_id
        WHERE tg.team_id = :team_id
          AND tg.season = :season
          AND (
            tg.season_type IS NULL
            OR UPPER(tg.season_type) IN ('REG', 'REGULAR')
          )
    """
    params = {"team_id": team_id, "season": int(season)}

    def _read(statement: str) -> dict[str, Any] | None:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(statement),
                connection,
                params=params,
            )
        if frame.empty:
            return None
        row = frame.iloc[0].to_dict()
        if (_int(row.get("games")) or 0) <= 0:
            return None
        return row

    try:
        return _read(joined_sql)
    except Exception:
        pass

    try:
        return _read(offense_sql)
    except Exception:
        return None


def _player_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": str(row.get("player_id") or ""),
        "name": str(row.get("name") or "").strip() or None,
        "position": (
            str(row.get("position")).strip()
            if row.get("position") is not None
            else None
        ),
        "status": (
            str(row.get("status")).strip()
            if row.get("status") is not None
            else None
        ),
        "games": _int(row.get("games")),
        "pass_attempts": _int(row.get("pass_attempts")),
        "pass_completions": _int(row.get("pass_completions")),
        "pass_yards": _int(row.get("pass_yards")),
        "pass_tds": _int(row.get("pass_tds")),
        "interceptions": _int(row.get("interceptions")),
        "rush_attempts": _int(row.get("rush_attempts")),
        "rush_yards": _int(row.get("rush_yards")),
        "rush_tds": _int(row.get("rush_tds")),
        "targets": _int(row.get("targets")),
        "receptions": _int(row.get("receptions")),
        "receiving_yards": _int(row.get("receiving_yards")),
        "receiving_tds": _int(row.get("receiving_tds")),
    }


def _rank_leaders(
    players: list[dict[str, Any]],
    *,
    metric: str,
    require: tuple[str, ...],
    limit: int = LEADER_LIMIT,
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for player in players:
        value = player.get(metric)
        if value is None or float(value) <= 0:
            continue
        if not any(
            (player.get(key) or 0) > 0 for key in require
        ):
            continue
        eligible.append(player)

    eligible.sort(
        key=lambda row: float(row.get(metric) or 0),
        reverse=True,
    )
    return eligible[:limit]


def _group_depth_chart(
    frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    by_position: dict[str, list[dict[str, Any]]] = {}
    for row in frame.to_dict(orient="records"):
        position = (
            str(row.get("position") or "").strip().upper()
            or "UNK"
        )
        entry = {
            "player_id": str(row.get("player_id") or ""),
            "name": (
                str(row.get("name")).strip()
                if row.get("name") is not None
                else None
            ),
            "depth_order": _int(row.get("depth_order")),
            "role": (
                str(row.get("role")).strip()
                if row.get("role") is not None
                else None
            ),
        }
        bucket = by_position.setdefault(position, [])
        # Prefer the first DISTINCT ON row per player/position.
        if any(
            item["player_id"] == entry["player_id"]
            for item in bucket
        ):
            continue
        bucket.append(entry)

    for entries in by_position.values():
        entries.sort(
            key=lambda item: (
                item["depth_order"]
                if item["depth_order"] is not None
                else 99,
                item["name"] or "",
            )
        )

    ordered_positions = [
        *DEPTH_POSITION_ORDER,
        *[
            position
            for position in sorted(by_position.keys())
            if position not in DEPTH_POSITION_ORDER
        ],
    ]

    groups: list[dict[str, Any]] = []
    for position in ordered_positions:
        entries = by_position.get(position)
        if not entries:
            continue
        groups.append(
            {
                "position": position,
                "players": entries,
            }
        )
    return groups
