"""
Team Stats — season leaders and depth chart by franchise.
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
        teams.append(
            {
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
            }
        )
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
                    "team": {
                        "team_id": team_id,
                        "abbreviation": abbr,
                        "name": (
                            str(team_row.get("team_name")).strip()
                            if team_row.get("team_name") is not None
                            else abbr
                        ),
                        "conference": (
                            str(team_row.get("conference")).strip()
                            if team_row.get("conference") is not None
                            else None
                        ),
                        "division": (
                            str(team_row.get("division")).strip()
                            if team_row.get("division") is not None
                            else None
                        ),
                    },
                    "season": None,
                    "depth_season": None,
                    "depth_week": None,
                    "depth_as_of": None,
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

    return {
        "team": {
            "team_id": team_id,
            "abbreviation": abbr,
            "name": (
                str(team_row.get("team_name")).strip()
                if team_row.get("team_name") is not None
                else abbr
            ),
            "conference": (
                str(team_row.get("conference")).strip()
                if team_row.get("conference") is not None
                else None
            ),
            "division": (
                str(team_row.get("division")).strip()
                if team_row.get("division") is not None
                else None
            ),
        },
        "season": int(season) if season is not None else None,
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
