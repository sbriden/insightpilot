"""
Ingest ScoresAndOdds (Action Network) NFL lines into
fantasy_football.fact_game_market.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.dim_game import get_dim_game
from app.canonical.dim_team import get_dim_team, normalize_team_abbreviation
from app.canonical.fact_game_market import (
    FACT_GAME_MARKET_COLUMNS,
    upsert_fact_game_market,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine
from app.sources import scoresandodds as sao


def ingest_nfl_scoresandodds_markets(
    *,
    season: int | None = None,
    weeks: list[int] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Pull live/upcoming NFL odds and upsert matched games.

    Matching is by season + week + home/away abbreviations against
    fantasy_football.dim_game / dim_team.
    """

    league = sao.get_league("nfl")
    rows, meta = sao.fetch_nfl_odds_rows(
        weeks=weeks,
        season=season,
    )
    resolved_season = int(
        season
        or meta.get("season")
        or datetime.now(timezone.utc).year
    )
    if not rows:
        return {
            "source": sao.SOURCE_LABEL,
            "league": league.id,
            "homepage": league.homepage,
            "season": resolved_season,
            "weeks": weeks or [meta.get("week")],
            "fetched": 0,
            "matched": 0,
            "persisted": False,
            "note": "No odds rows returned from ScoresAndOdds feed.",
            "meta": meta,
        }

    matchup_lookup = _matchup_lookup_for_season(resolved_season)
    records: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for row in rows:
        home = normalize_team_abbreviation(row.get("home_abbr"))
        away = normalize_team_abbreviation(row.get("away_abbr"))
        week = row.get("week")
        if not home or not away or week is None:
            unmatched.append(row)
            continue

        key = (int(week), home, away)
        game_id = matchup_lookup.get(key)
        if not game_id:
            game_id = matchup_lookup.get((int(week), away, home))
            if game_id:
                row = _flip_home_away(row)
                home, away = away, home

        if not game_id:
            unmatched.append(row)
            continue

        timestamp = (
            row.get("line_inserted_at")
            or row.get("start_time")
            or datetime.now(timezone.utc).isoformat()
        )
        season_type = str(row.get("season_type") or "reg").upper()
        if season_type == "REG":
            season_type = "REG"
        elif season_type in {"POST", "POSTSEASON", "PLAYOFFS"}:
            season_type = "POST"
        else:
            season_type = season_type.upper()

        records.append(
            {
                "game_id": game_id,
                "timestamp": timestamp,
                "source": sao.SOURCE_LABEL,
                "spread": row.get("spread"),
                "over_under": row.get("over_under"),
                "home_implied_total": row.get("home_implied_total"),
                "away_implied_total": row.get("away_implied_total"),
                "opening_spread": row.get("opening_spread"),
                "opening_over_under": row.get("opening_over_under"),
                "opening_home_implied_total": row.get(
                    "opening_home_implied_total"
                ),
                "opening_away_implied_total": row.get(
                    "opening_away_implied_total"
                ),
                "opening_captured_at": row.get("opening_captured_at"),
                "season": int(row.get("season") or resolved_season),
                "week": int(week),
                "season_type": season_type,
                "source_ids": {
                    "scoresandodds_game_id": row.get("provider_game_id"),
                    "action_network_game_id": row.get("provider_game_id"),
                    "sao_game_id": row.get("sao_game_id"),
                    "book_id": row.get("book_id"),
                    "home_abbr": home,
                    "away_abbr": away,
                    "league": league.id,
                    "opening_source": row.get("opening_source"),
                },
                "resolution_key": f"{game_id}:{sao.SOURCE_LABEL}",
            }
        )

    fact = pd.DataFrame.from_records(records)
    if not fact.empty:
        fact = fact.drop_duplicates(
            subset=["resolution_key"],
            keep="last",
        ).reset_index(drop=True)

    if persist and not fact.empty:
        upsert_fact_game_market(fact)
        clear_fact_game_market_cache()

    return {
        "source": sao.SOURCE_LABEL,
        "league": league.id,
        "homepage": league.homepage,
        "season": resolved_season,
        "weeks": sorted(
            {
                int(r["week"])
                for r in records
                if r.get("week") is not None
            }
            or {int(w) for w in (weeks or []) if w is not None}
        ),
        "fetched": len(rows),
        "matched": int(len(fact)),
        "unmatched": len(unmatched),
        "persisted": bool(persist and not fact.empty),
        "sample_unmatched": [
            {
                "week": u.get("week"),
                "away": u.get("away_abbr"),
                "home": u.get("home_abbr"),
                "spread": u.get("spread"),
                "total": u.get("over_under"),
            }
            for u in unmatched[:8]
        ],
        "meta": meta,
        "columns": list(FACT_GAME_MARKET_COLUMNS),
    }


def clear_fact_game_market_cache() -> None:
    import app.canonical.fact_game_market as market_mod

    market_mod._FACT_GAME_MARKET_CACHE = None
    market_mod._FACT_GAME_MARKET_CACHE_WITH_KEYS = None
    market_mod._FACT_GAME_MARKET_CACHE_SEASONS = None


def _matchup_lookup_for_season(
    season: int,
) -> dict[tuple[int, str, str], str]:
    """Map (week, home_abbr, away_abbr) → InsightPilot game_id."""

    games = get_dim_game(
        seasons=[int(season)],
        force_refresh=False,
        persist=False,
    )
    teams = get_dim_team(force_refresh=False, persist=False)
    if games is None or games.empty or teams is None or teams.empty:
        return {}

    abbr_by_id: dict[str, str] = {}
    for row in teams.to_dict(orient="records"):
        team_id = str(row.get("team_id") or "").strip()
        abbr = normalize_team_abbreviation(row.get("team_abbreviation"))
        if team_id and abbr:
            abbr_by_id[team_id] = abbr

    lookup: dict[tuple[int, str, str], str] = {}
    for row in games.to_dict(orient="records"):
        game_id = str(row.get("game_id") or "").strip()
        week = row.get("week")
        home_id = str(row.get("home_team_id") or "").strip()
        away_id = str(row.get("away_team_id") or "").strip()
        if not game_id or week is None or not home_id or not away_id:
            continue
        home_abbr = abbr_by_id.get(home_id)
        away_abbr = abbr_by_id.get(away_id)
        if not home_abbr or not away_abbr:
            continue
        lookup[(int(week), home_abbr, away_abbr)] = game_id
    return lookup


def _flip_home_away(row: dict[str, Any]) -> dict[str, Any]:
    flipped = dict(row)
    flipped["home_abbr"], flipped["away_abbr"] = (
        row.get("away_abbr"),
        row.get("home_abbr"),
    )
    flipped["home_name"], flipped["away_name"] = (
        row.get("away_name"),
        row.get("home_name"),
    )
    spread = row.get("spread")
    if spread is not None:
        flipped["spread"] = -float(spread)
    opening_spread = row.get("opening_spread")
    if opening_spread is not None:
        flipped["opening_spread"] = -float(opening_spread)
    flipped["home_moneyline"], flipped["away_moneyline"] = (
        row.get("away_moneyline"),
        row.get("home_moneyline"),
    )
    flipped["home_implied_total"], flipped["away_implied_total"] = (
        row.get("away_implied_total"),
        row.get("home_implied_total"),
    )
    flipped["opening_home_implied_total"], flipped[
        "opening_away_implied_total"
    ] = (
        row.get("opening_away_implied_total"),
        row.get("opening_home_implied_total"),
    )
    return flipped


def markets_from_scoresandodds_count(
    *,
    season: int | None = None,
    week: int | None = None,
) -> int:
    clauses = ["source = :source"]
    params: dict[str, Any] = {"source": sao.SOURCE_LABEL}
    if season is not None:
        clauses.append("season = :season")
        params["season"] = int(season)
    if week is not None:
        clauses.append("week = :week")
        params["week"] = int(week)
    where = " AND ".join(clauses)
    try:
        with engine.connect() as connection:
            return int(
                connection.execute(
                    text(
                        f"""
                        SELECT COUNT(*)
                        FROM {FANTASY_SCHEMA}.fact_game_market
                        WHERE {where}
                        """
                    ),
                    params,
                ).scalar()
                or 0
            )
    except Exception:
        return 0
