"""
fact_dfs_salary — persisted DraftKings / FanDuel salaries.

Grain: one row per site × contest_type × season × week × player.
Uploaded slate CSVs upsert into this table so optimizers can
reuse real prices instead of synthetic estimates.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


FACT_DFS_SALARY_COLUMNS = [
    "player_id",
    "site",
    "contest_type",
    "season",
    "week",
    "team",
    "position",
    "player_name",
    "salary",
    "match_score",
    "source_name",
    "source_ids",
    "resolution_key",
]


def salary_resolution_key(
    *,
    site: str,
    contest_type: str,
    season: int,
    week: int,
    player_id: str,
) -> str:
    return (
        f"{str(site).strip().lower()}:"
        f"{str(contest_type).strip().lower()}:"
        f"{int(season)}:{int(week)}:"
        f"{str(player_id).strip()}"
    )


def fact_dfs_salary_count() -> int:
    with engine.connect() as connection:
        result = connection.execute(
            text(
                f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_dfs_salary"
            )
        )
        return int(result.scalar() or 0)


def load_dfs_salary_map(
    *,
    site: str,
    contest_type: str,
    season: int,
    week: int,
) -> dict[str, int]:
    """player_id → salary for one site/format/week."""

    frame = load_fact_dfs_salary(
        site=site,
        contest_type=contest_type,
        season=season,
        week=week,
    )
    if frame.empty:
        return {}
    mapping: dict[str, int] = {}
    for record in frame.to_dict(orient="records"):
        player_id = str(record.get("player_id") or "").strip()
        salary = record.get("salary")
        if not player_id or salary is None:
            continue
        try:
            mapping[player_id] = int(salary)
        except (TypeError, ValueError):
            continue
    return mapping


def load_fact_dfs_salary(
    *,
    site: str | None = None,
    contest_type: str | None = None,
    season: int | None = None,
    week: int | None = None,
) -> pd.DataFrame:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if site:
        clauses.append("site = :site")
        params["site"] = str(site).strip().lower()
    if contest_type:
        clauses.append("contest_type = :contest_type")
        params["contest_type"] = str(contest_type).strip().lower()
    if season is not None:
        clauses.append("season = :season")
        params["season"] = int(season)
    if week is not None:
        clauses.append("week = :week")
        params["week"] = int(week)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(
                f"""
                SELECT
                    player_id,
                    site,
                    contest_type,
                    season,
                    week,
                    team,
                    position,
                    player_name,
                    salary,
                    match_score,
                    source_name,
                    source_ids,
                    resolution_key,
                    updated_at
                FROM {FANTASY_SCHEMA}.fact_dfs_salary
                {where}
                ORDER BY site, contest_type, season, week, player_id
                """
            ),
            connection,
            params=params,
        )
    if "source_ids" in frame.columns:
        frame["source_ids"] = frame["source_ids"].map(
            lambda value: (
                json.dumps(value, sort_keys=True)
                if isinstance(value, dict)
                else value
            )
        )
    return frame


def latest_salary_upload_timestamp(
    *,
    site: str,
    contest_type: str,
    season: int,
    week: int,
) -> str | None:
    with engine.connect() as connection:
        result = connection.execute(
            text(
                f"""
                SELECT MAX(updated_at)
                FROM {FANTASY_SCHEMA}.fact_dfs_salary
                WHERE site = :site
                  AND contest_type = :contest_type
                  AND season = :season
                  AND week = :week
                """
            ),
            {
                "site": str(site).strip().lower(),
                "contest_type": str(contest_type).strip().lower(),
                "season": int(season),
                "week": int(week),
            },
        )
        value = result.scalar()
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def upsert_fact_dfs_salary(fact: pd.DataFrame) -> int:
    if fact.empty:
        return 0

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_dfs_salary (
            player_id,
            site,
            contest_type,
            season,
            week,
            team,
            position,
            player_name,
            salary,
            match_score,
            source_name,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :player_id,
            :site,
            :contest_type,
            :season,
            :week,
            :team,
            :position,
            :player_name,
            :salary,
            :match_score,
            :source_name,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            player_id = EXCLUDED.player_id,
            team = EXCLUDED.team,
            position = EXCLUDED.position,
            player_name = EXCLUDED.player_name,
            salary = EXCLUDED.salary,
            match_score = EXCLUDED.match_score,
            source_name = EXCLUDED.source_name,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in fact.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(source_ids, sort_keys=True)
        rows.append(
            {
                "player_id": str(record["player_id"]),
                "site": str(record["site"]).strip().lower(),
                "contest_type": str(
                    record["contest_type"]
                ).strip().lower(),
                "season": int(record["season"]),
                "week": int(record["week"]),
                "team": record.get("team"),
                "position": record.get("position"),
                "player_name": record.get("player_name"),
                "salary": int(record["salary"]),
                "match_score": record.get("match_score"),
                "source_name": record.get("source_name"),
                "source_ids": source_ids,
                "resolution_key": record["resolution_key"],
            }
        )

    with engine.begin() as connection:
        connection.execute(statement, rows)
    return len(rows)
