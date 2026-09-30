"""Load historical fantasy baselines for projection calibration."""

from __future__ import annotations

from typing import Any

from app.analysis.insights.fantasy_scoring import (
    fantasy_points_sql,
    normalize_scoring,
)
from app.canonical.schema import FANTASY_SCHEMA


def load_player_projection_baselines(
    *,
    season: int,
    player_ids: list[str] | None = None,
    scoring: str | None = "ppr",
) -> dict[str, dict[str, Any]]:
    """
    player_id → historical FPPG / games / p90 from prior seasons.

    Uses seasons strictly before ``season``. Returns empty dict
    on DB errors so slate build can degrade gracefully.
    """

    try:
        import pandas as pd
        from sqlalchemy import text

        from app.database import engine
    except Exception:
        return {}

    prior_seasons = [int(season) - 1, int(season) - 2]
    prior_seasons = [value for value in prior_seasons if value >= 2015]
    if not prior_seasons:
        return {}

    scoring_key = normalize_scoring(scoring)
    points_expr = fantasy_points_sql(scoring_key, alias="g")
    params: dict[str, Any] = {
        "seasons": prior_seasons,
    }
    player_filter = ""
    if player_ids:
        cleaned = [
            str(pid).strip()
            for pid in player_ids
            if str(pid).strip()
        ]
        if cleaned:
            params["player_ids"] = cleaned
            player_filter = "AND g.player_id = ANY(:player_ids)"

    sql = f"""
        WITH game_pts AS (
          SELECT
            g.player_id,
            g.season,
            g.week,
            ({points_expr}) AS fantasy_points
          FROM {FANTASY_SCHEMA}.fact_player_game g
          WHERE g.season = ANY(:seasons)
            {player_filter}
        )
        SELECT
          player_id,
          COUNT(*)::int AS historical_games,
          ROUND(AVG(fantasy_points)::numeric, 2) AS historical_fppg,
          ROUND(
            (
              percentile_cont(0.90)
              WITHIN GROUP (ORDER BY fantasy_points)
            )::numeric,
            2
          ) AS historical_p90,
          ROUND(
            (
              percentile_cont(0.10)
              WITHIN GROUP (ORDER BY fantasy_points)
            )::numeric,
            2
          ) AS historical_p10
        FROM game_pts
        GROUP BY player_id
    """

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(sql),
                connection,
                params=params,
            )
    except Exception:
        return {}

    if frame is None or frame.empty:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for row in frame.to_dict(orient="records"):
        pid = str(row.get("player_id") or "").strip()
        if not pid:
            continue
        out[pid] = {
            "historical_games": int(row.get("historical_games") or 0),
            "historical_baseline": _num(row.get("historical_fppg")),
            "historical_p90": _num(row.get("historical_p90")),
            "historical_p10": _num(row.get("historical_p10")),
        }
    return out


def load_positional_league_priors(
    *,
    season: int,
) -> dict[str, float]:
    """Optional league priors from prior season by position."""

    try:
        import pandas as pd
        from sqlalchemy import text

        from app.database import engine
    except Exception:
        return {}

    prior = int(season) - 1
    if prior < 2015:
        return {}

    points_expr = fantasy_points_sql("ppr", alias="g")
    sql = f"""
        SELECT
          UPPER(COALESCE(p.position, '')) AS position,
          ROUND(
            (
              SUM({points_expr}) / NULLIF(COUNT(*), 0)
            )::numeric,
            2
          ) AS fppg
        FROM {FANTASY_SCHEMA}.fact_player_game g
        INNER JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = g.player_id
        WHERE g.season = :season
        GROUP BY UPPER(COALESCE(p.position, ''))
        HAVING COUNT(*) >= 50
    """
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(sql),
                connection,
                params={"season": prior},
            )
    except Exception:
        return {}

    if frame is None or frame.empty:
        return {}

    out: dict[str, float] = {}
    for row in frame.to_dict(orient="records"):
        pos = str(row.get("position") or "").strip().upper()
        value = _num(row.get("fppg"))
        if pos and value is not None:
            if pos in {"DST", "D/ST"}:
                pos = "DEF"
            out[pos] = float(value)
    return out


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
