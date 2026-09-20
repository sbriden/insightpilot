"""
Player Stats tab — fantasy-oriented season evidence for Snapshot.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.canonical.analytics.common import normalize_float
from app.analysis.insights.player_snapshot import (
    FANTASY_SEARCH_POSITIONS,
    _depth_chart_for_player,
    _num,
    build_team_defense_tab_payload,
)


def _reception_points(scoring: str) -> float:
    value = str(scoring or "ppr").strip().lower()
    if value in {"half", "half_ppr", "half-ppr"}:
        return 0.5
    if value in {"std", "standard", "non_ppr"}:
        return 0.0
    return 1.0


def _normalize_scoring(scoring: str | None) -> str:
    value = str(scoring or "ppr").strip().lower()
    if value in {"half", "half_ppr", "half-ppr"}:
        return "half_ppr"
    if value in {"std", "standard", "non_ppr"}:
        return "standard"
    return "ppr"


def _fantasy_points_sql(scoring: str, *, alias: str = "") -> str:
    from app.analysis.insights.fantasy_scoring import (
        fantasy_points_sql,
    )

    return fantasy_points_sql(scoring, alias=alias)


def _position_group(position: Any) -> str:
    value = str(position or "").strip().upper()
    if value in {"FB", "HB"}:
        return "RB"
    if value == "PK":
        return "K"
    if value in {"DST", "D/ST", "D-ST"}:
        return "DEF"
    if value in FANTASY_SEARCH_POSITIONS or value in {
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    }:
        return value
    return "WR"


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    top = normalize_float(numerator)
    bottom = normalize_float(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    return top / bottom


def _metric(
    key: str,
    label: str,
    value: Any,
    *,
    context: str | None = None,
    format: str = "number",
) -> dict[str, Any] | None:
    number = _num(value)
    if number is None:
        return None
    return {
        "key": key,
        "label": label,
        "value": number,
        "context": context,
        "format": format,
    }


def _int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(round(number))


def build_player_stats(
    player_id: str,
    *,
    season: int | None = None,
    scoring: str | None = "ppr",
) -> dict[str, Any] | None:
    """
    Full Stats-tab payload for one player.

    Fantasy-first: production, breakdown, volume, efficiency,
    consistency, season history, and game log.
    """

    pid = str(player_id or "").strip()
    if not pid:
        return None

    defense_payload = build_team_defense_tab_payload(
        pid,
        season=season,
        tab="stats",
    )
    if defense_payload is not None:
        return defense_payload

    scoring_key = _normalize_scoring(scoring)

    try:
        import nflreadpy as nfl
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    if season is None:
        try:
            season = int(nfl.get_current_season())
        except Exception:
            season = None

    try:
        with engine.connect() as connection:
            identity = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      p.player_id,
                      p.name,
                      p.position,
                      t.team_abbreviation AS team
                    FROM {FANTASY_SCHEMA}.dim_player p
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team t
                      ON t.team_id = p.current_team_id
                    WHERE p.player_id = :player_id
                    LIMIT 1
                    """
                ),
                connection,
                params={"player_id": pid},
            )
            if identity.empty:
                return None
            player = identity.iloc[0].to_dict()
            position = (
                str(player.get("position")).strip()
                if player.get("position") is not None
                else None
            )
            position_group = _position_group(position)

            seasons_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT DISTINCT season
                    FROM {FANTASY_SCHEMA}.fact_player_game
                    WHERE player_id = :player_id
                      AND season IS NOT NULL
                    ORDER BY season DESC
                    """
                ),
                connection,
                params={"player_id": pid},
            )
            available_seasons = [
                int(value)
                for value in seasons_frame["season"].tolist()
                if value is not None
            ]
            if season is None and available_seasons:
                season = available_seasons[0]
            if season is None:
                return None
            if (
                available_seasons
                and int(season) not in available_seasons
            ):
                season = available_seasons[0]

            points_sql = _fantasy_points_sql(scoring_key)
            games_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      g.season,
                      g.week,
                      g.season_type,
                      g.team_id,
                      g.pass_attempts,
                      g.pass_completions,
                      g.pass_yards,
                      g.pass_tds,
                      g.interceptions,
                      g.rush_attempts,
                      g.rush_yards,
                      g.rush_tds,
                      g.targets,
                      g.receptions,
                      g.receiving_yards,
                      g.receiving_tds,
                      g.fg_made,
                      g.fg_att,
                      g.fg_made_0_19,
                      g.fg_made_20_29,
                      g.fg_made_30_39,
                      g.fg_made_40_49,
                      g.fg_made_50_59,
                      g.fg_made_60_,
                      g.pat_made,
                      g.pat_att,
                      ROUND(({points_sql})::numeric, 1)
                        AS fantasy_points,
                      CASE
                        WHEN g.team_id = dg.home_team_id
                          THEN away.team_abbreviation
                        WHEN g.team_id = dg.away_team_id
                          THEN home.team_abbreviation
                        ELSE NULL
                      END AS opponent,
                      CASE
                        WHEN g.team_id = dg.home_team_id
                          THEN 'vs'
                        WHEN g.team_id = dg.away_team_id
                          THEN '@'
                        ELSE NULL
                      END AS home_away
                    FROM {FANTASY_SCHEMA}.fact_player_game g
                    LEFT JOIN {FANTASY_SCHEMA}.dim_game dg
                      ON dg.game_id = g.game_id
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team home
                      ON home.team_id = dg.home_team_id
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team away
                      ON away.team_id = dg.away_team_id
                    WHERE g.player_id = :player_id
                      AND g.season = :season
                    ORDER BY g.week ASC NULLS LAST
                    """
                ),
                connection,
                params={
                    "player_id": pid,
                    "season": int(season),
                },
            )

            usage_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      AVG(offensive_snap_share) AS snap_share,
                      AVG(target_share) AS target_share,
                      AVG(rush_share) AS rush_share,
                      AVG(route_participation_rate)
                        AS route_participation,
                      AVG(qb_rush_share) AS qb_rush_share,
                      SUM(touches) AS touches,
                      SUM(red_zone_touches) AS red_zone_touches,
                      SUM(goal_line_carries) AS goal_line_carries,
                      SUM(red_zone_targets) AS red_zone_targets,
                      SUM(end_zone_targets) AS end_zone_targets,
                      SUM(air_yards) AS air_yards,
                      SUM(dropbacks) AS dropbacks,
                      SUM(designed_rush_attempts)
                        AS designed_rush_attempts,
                      SUM(scrambles) AS scrambles
                    FROM {FANTASY_SCHEMA}.fact_player_usage
                    WHERE player_id = :player_id
                      AND season = :season
                    """
                ),
                connection,
                params={
                    "player_id": pid,
                    "season": int(season),
                },
            )

            history_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      g.season,
                      COUNT(*) AS games,
                      ROUND(SUM({points_sql})::numeric, 1)
                        AS fantasy_points,
                      SUM(g.rush_attempts) AS rush_attempts,
                      SUM(g.rush_yards) AS rush_yards,
                      SUM(g.rush_tds) AS rush_tds,
                      SUM(g.targets) AS targets,
                      SUM(g.receptions) AS receptions,
                      SUM(g.receiving_yards) AS receiving_yards,
                      SUM(g.receiving_tds) AS receiving_tds,
                      SUM(g.pass_attempts) AS pass_attempts,
                      SUM(g.pass_completions) AS pass_completions,
                      SUM(g.pass_yards) AS pass_yards,
                      SUM(g.pass_tds) AS pass_tds,
                      SUM(g.interceptions) AS interceptions,
                      SUM(g.fg_made) AS fg_made,
                      SUM(g.fg_att) AS fg_att,
                      SUM(g.fg_made_0_19) AS fg_made_0_19,
                      SUM(g.fg_made_20_29) AS fg_made_20_29,
                      SUM(g.fg_made_30_39) AS fg_made_30_39,
                      SUM(g.fg_made_40_49) AS fg_made_40_49,
                      SUM(g.fg_made_50_59) AS fg_made_50_59,
                      SUM(g.fg_made_60_) AS fg_made_60_,
                      SUM(g.pat_made) AS pat_made,
                      SUM(g.pat_att) AS pat_att
                    FROM {FANTASY_SCHEMA}.fact_player_game g
                    WHERE g.player_id = :player_id
                    GROUP BY g.season
                    ORDER BY g.season DESC
                    """
                ),
                connection,
                params={"player_id": pid},
            )

            rank_frame = pd.read_sql_query(
                text(
                    f"""
                    WITH season_points AS (
                      SELECT
                        p.player_id,
                        p.position,
                        ROUND(SUM({_fantasy_points_sql(scoring_key, alias='g')})::numeric, 1)
                          AS fantasy_points
                      FROM {FANTASY_SCHEMA}.fact_player_game g
                      INNER JOIN {FANTASY_SCHEMA}.dim_player p
                        ON p.player_id = g.player_id
                      WHERE g.season = :season
                        AND UPPER(COALESCE(p.position, '')) = :position
                      GROUP BY p.player_id, p.position
                    )
                    SELECT
                      player_id,
                      fantasy_points,
                      RANK() OVER (
                        ORDER BY fantasy_points DESC NULLS LAST
                      ) AS position_rank,
                      COUNT(*) OVER () AS position_pool_size
                    FROM season_points
                    """
                ),
                connection,
                params={
                    "season": int(season),
                    "position": position_group,
                },
            )
    except Exception:
        return None

    if games_frame.empty:
        return {
            "player_id": pid,
            "name": player.get("name"),
            "position": position,
            "position_group": position_group,
            "team": player.get("team"),
            "season": int(season),
            "scoring": scoring_key,
            "available_seasons": available_seasons,
            "fantasy_production": None,
            "production_breakdown": [],
            "volume": [],
            "efficiency": [],
            "consistency": None,
            "season_history": [],
            "game_log": [],
            "empty_message": (
                "No game statistics are available for this "
                "player/season yet."
            ),
        }

    totals = _aggregate_games(games_frame)
    usage = (
        usage_frame.iloc[0].to_dict()
        if not usage_frame.empty
        else {}
    )
    weekly_points = [
        value
        for value in (
            _num(item)
            for item in games_frame["fantasy_points"].tolist()
        )
        if value is not None
    ]
    games = len(weekly_points) or int(totals.get("games") or 0)
    fantasy_points = _num(totals.get("fantasy_points"))
    fppg = _safe_div(fantasy_points, games)

    rank_row = None
    if not rank_frame.empty:
        matched = rank_frame[
            rank_frame["player_id"].astype(str) == pid
        ]
        if not matched.empty:
            rank_row = matched.iloc[0].to_dict()

    position_rank = _int(
        rank_row.get("position_rank") if rank_row else None
    )
    depth = _depth_chart_for_player(pid, position=position)
    rank_label = None
    if position_rank is not None and position_group:
        rank_label = f"{position_group}{position_rank}"
    elif depth.get("depth_chart"):
        rank_label = depth.get("depth_chart")

    ceiling = max(weekly_points) if weekly_points else None
    floor = min(weekly_points) if weekly_points else None
    ceiling_week = None
    floor_week = None
    if weekly_points:
        for _, game in games_frame.iterrows():
            pts = _num(game.get("fantasy_points"))
            if (
                pts is not None
                and ceiling is not None
                and pts == ceiling
            ):
                ceiling_week = _int(game.get("week"))
            if (
                pts is not None
                and floor is not None
                and pts == floor
            ):
                floor_week = _int(game.get("week"))

    top_12_fpts = sum(1 for pts in weekly_points if pts >= 15)
    top_24_fpts = sum(1 for pts in weekly_points if pts >= 10)
    games_10_plus = sum(1 for pts in weekly_points if pts >= 10)

    fantasy_production = {
        "fantasy_points": fantasy_points,
        "fppg": round(fppg, 1) if fppg is not None else None,
        "games": games,
        "games_context": (
            f"{round(100.0 * games / 17.0)}% of 17"
            if games
            else None
        ),
        "position_rank": position_rank,
        "position_rank_label": rank_label,
        "weekly_ceiling": ceiling,
        "ceiling_week": ceiling_week,
        "weekly_floor": floor,
        "floor_week": floor_week,
        "top_12_finishes": top_12_fpts,
        "top_12_rate": (
            round(100.0 * top_12_fpts / games, 0)
            if games
            else None
        ),
    }

    return {
        "player_id": pid,
        "name": player.get("name"),
        "position": position,
        "position_group": position_group,
        "team": (
            str(player.get("team")).strip()
            if player.get("team") is not None
            else None
        ),
        "season": int(season),
        "scoring": scoring_key,
        "available_seasons": available_seasons,
        "fantasy_production": fantasy_production,
        "production_breakdown": _production_breakdown(
            position_group,
            totals,
        ),
        "volume": _volume_metrics(position_group, totals, usage),
        "efficiency": _efficiency_metrics(
            position_group,
            totals,
            usage,
            fantasy_points=fantasy_points,
        ),
        "consistency": _consistency_block(
            weekly_points,
            games=games,
            fppg=fppg,
            ceiling=ceiling,
            floor=floor,
            top_12=top_12_fpts,
            top_24=top_24_fpts,
            games_10_plus=games_10_plus,
        ),
        "season_history": _season_history_rows(
            history_frame,
            position_group=position_group,
        ),
        "game_log": _game_log_rows(games_frame, position_group),
        "empty_message": None,
        "data_note": (
            "Fantasy points calculated by InsightPilot · "
            f"{scoring_key.replace('_', ' ').upper()} scoring"
        ),
    }


def _aggregate_games(frame: pd.DataFrame) -> dict[str, Any]:
    columns = [
        "pass_attempts",
        "pass_completions",
        "pass_yards",
        "pass_tds",
        "interceptions",
        "rush_attempts",
        "rush_yards",
        "rush_tds",
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "fg_made",
        "fg_att",
        "fg_made_0_19",
        "fg_made_20_29",
        "fg_made_30_39",
        "fg_made_40_49",
        "fg_made_50_59",
        "fg_made_60_",
        "pat_made",
        "pat_att",
        "fantasy_points",
    ]
    totals: dict[str, Any] = {"games": len(frame)}
    for column in columns:
        if column not in frame.columns:
            totals[column] = None
            continue
        series = pd.to_numeric(frame[column], errors="coerce")
        totals[column] = (
            float(series.sum())
            if series.notna().any()
            else None
        )
    fg_50 = (
        (totals.get("fg_made_50_59") or 0.0)
        + (totals.get("fg_made_60_") or 0.0)
    )
    totals["fg_made_50_plus"] = (
        float(fg_50)
        if (
            totals.get("fg_made_50_59") is not None
            or totals.get("fg_made_60_") is not None
        )
        else None
    )
    if totals.get("fg_made") is None and any(
        totals.get(column) is not None
        for column in (
            "fg_made_0_19",
            "fg_made_20_29",
            "fg_made_30_39",
            "fg_made_40_49",
            "fg_made_50_59",
            "fg_made_60_",
        )
    ):
        totals["fg_made"] = float(
            (totals.get("fg_made_0_19") or 0.0)
            + (totals.get("fg_made_20_29") or 0.0)
            + (totals.get("fg_made_30_39") or 0.0)
            + (totals.get("fg_made_40_49") or 0.0)
            + fg_50
        )
    return totals


def _production_breakdown(
    position_group: str,
    totals: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []

    def add_group(
        title: str,
        metrics: list[dict[str, Any] | None],
    ) -> None:
        clean = [item for item in metrics if item is not None]
        if clean:
            groups.append({"title": title, "metrics": clean})

    rush_att = totals.get("rush_attempts")
    rush_yds = totals.get("rush_yards")
    rec = totals.get("receptions")
    targets = totals.get("targets")
    rec_yds = totals.get("receiving_yards")
    pass_att = totals.get("pass_attempts")
    pass_cmp = totals.get("pass_completions")
    pass_yds = totals.get("pass_yards")

    if position_group == "QB":
        add_group(
            "Passing",
            [
                _metric("pass_completions", "Completions", pass_cmp, format="integer"),
                _metric("pass_attempts", "Attempts", pass_att, format="integer"),
                _metric("pass_yards", "Passing Yards", pass_yds, format="integer"),
                _metric("pass_tds", "Passing TDs", totals.get("pass_tds"), format="integer"),
                _metric("interceptions", "INTs", totals.get("interceptions"), format="integer"),
                _metric(
                    "completion_pct",
                    "Completion %",
                    None
                    if _safe_div(pass_cmp, pass_att) is None
                    else _safe_div(pass_cmp, pass_att) * 100.0,
                    format="percent",
                ),
                _metric(
                    "yards_per_attempt",
                    "Yards / Attempt",
                    _safe_div(pass_yds, pass_att),
                ),
            ],
        )
        add_group(
            "Rushing",
            [
                _metric("rush_attempts", "Carries", rush_att, format="integer"),
                _metric("rush_yards", "Rushing Yards", rush_yds, format="integer"),
                _metric("rush_tds", "Rushing TDs", totals.get("rush_tds"), format="integer"),
            ],
        )
    elif position_group == "RB":
        add_group(
            "Rushing",
            [
                _metric("rush_attempts", "Carries", rush_att, format="integer"),
                _metric("rush_yards", "Rushing Yards", rush_yds, format="integer"),
                _metric(
                    "yards_per_carry",
                    "Yards / Carry",
                    _safe_div(rush_yds, rush_att),
                ),
                _metric("rush_tds", "Rushing TDs", totals.get("rush_tds"), format="integer"),
            ],
        )
        add_group(
            "Receiving",
            [
                _metric("targets", "Targets", targets, format="integer"),
                _metric("receptions", "Receptions", rec, format="integer"),
                _metric("receiving_yards", "Receiving Yards", rec_yds, format="integer"),
                _metric(
                    "yards_per_reception",
                    "Yards / Reception",
                    _safe_div(rec_yds, rec),
                ),
                _metric(
                    "receiving_tds",
                    "Receiving TDs",
                    totals.get("receiving_tds"),
                    format="integer",
                ),
            ],
        )
    elif position_group == "K":
        add_group(
            "Field Goals",
            [
                _metric(
                    "fg_made",
                    "FG Made",
                    totals.get("fg_made"),
                    format="integer",
                ),
                _metric(
                    "fg_att",
                    "FG Attempts",
                    totals.get("fg_att"),
                    format="integer",
                ),
                _metric(
                    "fg_pct",
                    "FG %",
                    None
                    if _safe_div(
                        totals.get("fg_made"),
                        totals.get("fg_att"),
                    )
                    is None
                    else _safe_div(
                        totals.get("fg_made"),
                        totals.get("fg_att"),
                    )
                    * 100.0,
                    format="percent",
                ),
                _metric(
                    "fg_made_40_49",
                    "Made 40-49",
                    totals.get("fg_made_40_49"),
                    format="integer",
                ),
                _metric(
                    "fg_made_50_plus",
                    "Made 50+",
                    totals.get("fg_made_50_plus"),
                    format="integer",
                ),
            ],
        )
        add_group(
            "Extra Points",
            [
                _metric(
                    "pat_made",
                    "XP Made",
                    totals.get("pat_made"),
                    format="integer",
                ),
                _metric(
                    "pat_att",
                    "XP Attempts",
                    totals.get("pat_att"),
                    format="integer",
                ),
                _metric(
                    "pat_pct",
                    "XP %",
                    None
                    if _safe_div(
                        totals.get("pat_made"),
                        totals.get("pat_att"),
                    )
                    is None
                    else _safe_div(
                        totals.get("pat_made"),
                        totals.get("pat_att"),
                    )
                    * 100.0,
                    format="percent",
                ),
            ],
        )
        add_group(
            "Scoring",
            [
                _metric(
                    "fantasy_points",
                    "Fantasy Points",
                    totals.get("fantasy_points"),
                ),
            ],
        )
        return groups
    else:
        add_group(
            "Receiving",
            [
                _metric("targets", "Targets", targets, format="integer"),
                _metric("receptions", "Receptions", rec, format="integer"),
                _metric("receiving_yards", "Receiving Yards", rec_yds, format="integer"),
                _metric(
                    "yards_per_reception",
                    "Yards / Reception",
                    _safe_div(rec_yds, rec),
                ),
                _metric(
                    "catch_rate",
                    "Catch Rate",
                    None
                    if _safe_div(rec, targets) is None
                    else _safe_div(rec, targets) * 100.0,
                    format="percent",
                ),
                _metric(
                    "receiving_tds",
                    "Receiving TDs",
                    totals.get("receiving_tds"),
                    format="integer",
                ),
            ],
        )
        add_group(
            "Rushing",
            [
                _metric("rush_attempts", "Carries", rush_att, format="integer"),
                _metric("rush_yards", "Rushing Yards", rush_yds, format="integer"),
                _metric("rush_tds", "Rushing TDs", totals.get("rush_tds"), format="integer"),
            ],
        )

    rush_tds = totals.get("rush_tds") or 0
    rec_tds = totals.get("receiving_tds") or 0
    pass_tds = totals.get("pass_tds") or 0
    add_group(
        "Scoring",
        [
            _metric(
                "total_tds",
                "Total TDs",
                (rush_tds or 0) + (rec_tds or 0) + (pass_tds or 0),
                format="integer",
            ),
            _metric(
                "fantasy_points",
                "Fantasy Points",
                totals.get("fantasy_points"),
            ),
        ],
    )
    return groups


def _volume_metrics(
    position_group: str,
    totals: dict[str, Any],
    usage: dict[str, Any],
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any] | None]
    if position_group == "QB":
        metrics = [
            _metric("dropbacks", "Dropbacks", usage.get("dropbacks"), format="integer"),
            _metric(
                "designed_rush_attempts",
                "Designed Rushes",
                usage.get("designed_rush_attempts"),
                format="integer",
            ),
            _metric("scrambles", "Scrambles", usage.get("scrambles"), format="integer"),
            _metric(
                "qb_rush_share",
                "Rush Share",
                None
                if _num(usage.get("qb_rush_share")) is None
                else _num(usage.get("qb_rush_share")) * 100.0,
                format="percent",
            ),
            _metric(
                "red_zone_touches",
                "Red Zone Touches",
                usage.get("red_zone_touches"),
                format="integer",
            ),
            _metric(
                "goal_line_carries",
                "Goal Line Carries",
                usage.get("goal_line_carries"),
                format="integer",
            ),
        ]
    elif position_group == "RB":
        touches = usage.get("touches")
        if touches is None:
            touches = (totals.get("rush_attempts") or 0) + (
                totals.get("receptions") or 0
            )
        metrics = [
            _metric("rush_attempts", "Carries", totals.get("rush_attempts"), format="integer"),
            _metric("touches", "Touches", touches, format="integer"),
            _metric("targets", "Targets", totals.get("targets"), format="integer"),
            _metric(
                "red_zone_touches",
                "Red Zone Touches",
                usage.get("red_zone_touches"),
                format="integer",
            ),
            _metric(
                "goal_line_carries",
                "Goal Line Carries",
                usage.get("goal_line_carries"),
                format="integer",
            ),
            _metric(
                "snap_share",
                "Snap Share",
                None
                if _num(usage.get("snap_share")) is None
                else _num(usage.get("snap_share")) * 100.0,
                format="percent",
            ),
        ]
    elif position_group == "K":
        metrics = [
            _metric(
                "fg_att",
                "FG Attempts",
                totals.get("fg_att"),
                format="integer",
            ),
            _metric(
                "fg_made",
                "FG Made",
                totals.get("fg_made"),
                format="integer",
            ),
            _metric(
                "fg_made_40_49",
                "Made 40-49",
                totals.get("fg_made_40_49"),
                format="integer",
            ),
            _metric(
                "fg_made_50_plus",
                "Made 50+",
                totals.get("fg_made_50_plus"),
                format="integer",
            ),
            _metric(
                "pat_att",
                "XP Attempts",
                totals.get("pat_att"),
                format="integer",
            ),
            _metric(
                "pat_made",
                "XP Made",
                totals.get("pat_made"),
                format="integer",
            ),
        ]
    else:
        metrics = [
            _metric("targets", "Targets", totals.get("targets"), format="integer"),
            _metric(
                "target_share",
                "Target Share",
                None
                if _num(usage.get("target_share")) is None
                else _num(usage.get("target_share")) * 100.0,
                format="percent",
            ),
            _metric(
                "route_participation",
                "Route Participation",
                None
                if _num(usage.get("route_participation")) is None
                else _num(usage.get("route_participation")) * 100.0,
                format="percent",
            ),
            _metric("air_yards", "Air Yards", usage.get("air_yards"), format="integer"),
            _metric(
                "red_zone_targets",
                "Red Zone Targets",
                usage.get("red_zone_targets"),
                format="integer",
            ),
            _metric(
                "end_zone_targets",
                "End Zone Targets",
                usage.get("end_zone_targets"),
                format="integer",
            ),
        ]
    return [item for item in metrics if item is not None]


def _efficiency_metrics(
    position_group: str,
    totals: dict[str, Any],
    usage: dict[str, Any],
    *,
    fantasy_points: float | None,
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any] | None]
    if position_group == "QB":
        dropbacks = usage.get("dropbacks") or totals.get("pass_attempts")
        metrics = [
            _metric(
                "completion_pct",
                "Completion %",
                None
                if _safe_div(
                    totals.get("pass_completions"),
                    totals.get("pass_attempts"),
                )
                is None
                else _safe_div(
                    totals.get("pass_completions"),
                    totals.get("pass_attempts"),
                )
                * 100.0,
                format="percent",
            ),
            _metric(
                "yards_per_attempt",
                "Yards / Attempt",
                _safe_div(
                    totals.get("pass_yards"),
                    totals.get("pass_attempts"),
                ),
            ),
            _metric(
                "td_rate",
                "TD %",
                None
                if _safe_div(
                    totals.get("pass_tds"),
                    totals.get("pass_attempts"),
                )
                is None
                else _safe_div(
                    totals.get("pass_tds"),
                    totals.get("pass_attempts"),
                )
                * 100.0,
                format="percent",
            ),
            _metric(
                "int_rate",
                "INT %",
                None
                if _safe_div(
                    totals.get("interceptions"),
                    totals.get("pass_attempts"),
                )
                is None
                else _safe_div(
                    totals.get("interceptions"),
                    totals.get("pass_attempts"),
                )
                * 100.0,
                format="percent",
            ),
            _metric(
                "fantasy_points_per_dropback",
                "FPTS / Dropback",
                _safe_div(fantasy_points, dropbacks),
            ),
        ]
    elif position_group == "RB":
        touches = usage.get("touches")
        if touches is None:
            touches = (totals.get("rush_attempts") or 0) + (
                totals.get("receptions") or 0
            )
        metrics = [
            _metric(
                "yards_per_carry",
                "Yards / Carry",
                _safe_div(
                    totals.get("rush_yards"),
                    totals.get("rush_attempts"),
                ),
            ),
            _metric(
                "catch_rate",
                "Catch Rate",
                None
                if _safe_div(
                    totals.get("receptions"),
                    totals.get("targets"),
                )
                is None
                else _safe_div(
                    totals.get("receptions"),
                    totals.get("targets"),
                )
                * 100.0,
                format="percent",
            ),
            _metric(
                "yards_per_reception",
                "Yards / Reception",
                _safe_div(
                    totals.get("receiving_yards"),
                    totals.get("receptions"),
                ),
            ),
            _metric(
                "fantasy_points_per_touch",
                "FPTS / Touch",
                _safe_div(fantasy_points, touches),
            ),
        ]
    elif position_group == "K":
        metrics = [
            _metric(
                "fg_pct",
                "FG %",
                None
                if _safe_div(
                    totals.get("fg_made"),
                    totals.get("fg_att"),
                )
                is None
                else _safe_div(
                    totals.get("fg_made"),
                    totals.get("fg_att"),
                )
                * 100.0,
                format="percent",
            ),
            _metric(
                "pat_pct",
                "XP %",
                None
                if _safe_div(
                    totals.get("pat_made"),
                    totals.get("pat_att"),
                )
                is None
                else _safe_div(
                    totals.get("pat_made"),
                    totals.get("pat_att"),
                )
                * 100.0,
                format="percent",
            ),
            _metric(
                "fantasy_points_per_fg_att",
                "FPTS / FG Att",
                _safe_div(fantasy_points, totals.get("fg_att")),
            ),
            _metric(
                "long_fg_share",
                "50+ Share of Makes",
                None
                if _safe_div(
                    totals.get("fg_made_50_plus"),
                    totals.get("fg_made"),
                )
                is None
                else _safe_div(
                    totals.get("fg_made_50_plus"),
                    totals.get("fg_made"),
                )
                * 100.0,
                format="percent",
            ),
        ]
    else:
        metrics = [
            _metric(
                "catch_rate",
                "Catch Rate",
                None
                if _safe_div(
                    totals.get("receptions"),
                    totals.get("targets"),
                )
                is None
                else _safe_div(
                    totals.get("receptions"),
                    totals.get("targets"),
                )
                * 100.0,
                format="percent",
            ),
            _metric(
                "yards_per_target",
                "Yards / Target",
                _safe_div(
                    totals.get("receiving_yards"),
                    totals.get("targets"),
                ),
            ),
            _metric(
                "yards_per_reception",
                "Yards / Reception",
                _safe_div(
                    totals.get("receiving_yards"),
                    totals.get("receptions"),
                ),
            ),
            _metric(
                "fantasy_points_per_target",
                "FPTS / Target",
                _safe_div(fantasy_points, totals.get("targets")),
            ),
        ]
    return [item for item in metrics if item is not None]


def _consistency_block(
    weekly_points: list[float],
    *,
    games: int,
    fppg: float | None,
    ceiling: float | None,
    floor: float | None,
    top_12: int,
    top_24: int,
    games_10_plus: int,
) -> dict[str, Any] | None:
    if not weekly_points:
        return None
    series = pd.Series(weekly_points, dtype="float64")
    median = float(series.median())
    stdev = float(series.std(ddof=0)) if len(series) > 1 else 0.0
    return {
        "fppg": round(fppg, 1) if fppg is not None else None,
        "median": round(median, 1),
        "stdev": round(stdev, 1),
        "ceiling": ceiling,
        "floor": floor,
        "top_12_finishes": top_12,
        "top_24_finishes": top_24,
        "games_10_plus": games_10_plus,
        "games": games,
        "weekly_points": [round(value, 1) for value in weekly_points],
    }


def _season_history_rows(
    frame: pd.DataFrame,
    *,
    position_group: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        games = _int(record.get("games")) or 0
        fantasy_points = _num(record.get("fantasy_points"))
        fppg = _safe_div(fantasy_points, games)
        rush_tds = record.get("rush_tds") or 0
        rec_tds = record.get("receiving_tds") or 0
        pass_tds = record.get("pass_tds") or 0
        rows.append(
            {
                "season": _int(record.get("season")),
                "games": games,
                "fantasy_points": fantasy_points,
                "fppg": round(fppg, 1) if fppg is not None else None,
                "rush_yards": _num(record.get("rush_yards")),
                "receptions": _num(record.get("receptions")),
                "receiving_yards": _num(record.get("receiving_yards")),
                "targets": _num(record.get("targets")),
                "pass_yards": _num(record.get("pass_yards")),
                "pass_tds": _num(record.get("pass_tds")),
                "interceptions": _num(record.get("interceptions")),
                "touchdowns": _num(
                    (rush_tds or 0) + (rec_tds or 0) + (pass_tds or 0)
                ),
                "fg_made": _num(record.get("fg_made")),
                "fg_att": _num(record.get("fg_att")),
                "fg_made_50_plus": _num(
                    (record.get("fg_made_50_59") or 0)
                    + (record.get("fg_made_60_") or 0)
                )
                if (
                    record.get("fg_made_50_59") is not None
                    or record.get("fg_made_60_") is not None
                )
                else None,
                "pat_made": _num(record.get("pat_made")),
                "position_group": position_group,
            }
        )
    return rows


def _game_log_rows(
    frame: pd.DataFrame,
    position_group: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        opp = record.get("opponent")
        home_away = record.get("home_away")
        opponent_label = None
        if opp:
            prefix = home_away or "vs"
            opponent_label = f"{prefix} {opp}"
        rush_tds = record.get("rush_tds") or 0
        rec_tds = record.get("receiving_tds") or 0
        pass_tds = record.get("pass_tds") or 0
        fg_50 = (
            (record.get("fg_made_50_59") or 0)
            + (record.get("fg_made_60_") or 0)
        )
        rows.append(
            {
                "season": _int(record.get("season")),
                "week": _int(record.get("week")),
                "opponent": (
                    str(opp).strip() if opp is not None else None
                ),
                "opponent_label": opponent_label,
                "fantasy_points": _num(record.get("fantasy_points")),
                "pass_completions": _num(record.get("pass_completions")),
                "pass_attempts": _num(record.get("pass_attempts")),
                "pass_yards": _num(record.get("pass_yards")),
                "pass_tds": _num(record.get("pass_tds")),
                "interceptions": _num(record.get("interceptions")),
                "rush_attempts": _num(record.get("rush_attempts")),
                "rush_yards": _num(record.get("rush_yards")),
                "rush_tds": _num(record.get("rush_tds")),
                "targets": _num(record.get("targets")),
                "receptions": _num(record.get("receptions")),
                "receiving_yards": _num(record.get("receiving_yards")),
                "receiving_tds": _num(record.get("receiving_tds")),
                "touchdowns": _num(
                    (rush_tds or 0) + (rec_tds or 0) + (pass_tds or 0)
                ),
                "fg_made": _num(record.get("fg_made")),
                "fg_att": _num(record.get("fg_att")),
                "fg_made_40_49": _num(record.get("fg_made_40_49")),
                "fg_made_50_plus": _num(fg_50)
                if (
                    record.get("fg_made_50_59") is not None
                    or record.get("fg_made_60_") is not None
                )
                else None,
                "pat_made": _num(record.get("pat_made")),
                "pat_att": _num(record.get("pat_att")),
                "position_group": position_group,
            }
        )
    rows.reverse()
    return rows
