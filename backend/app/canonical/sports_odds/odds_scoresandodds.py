"""
Ingest ScoresAndOdds (Action Network) slate-league lines into
sports_odds.fact_game_market.

Leagues: nba, nhl, mlb, ncaab. Rows are keyed by provider game id
(no dim_game join yet).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.canonical.sports_odds.fact_game_market import (
    FACT_COLUMNS,
    clear_fact_game_market_cache,
    upsert_fact_game_market,
)
from app.sources import scoresandodds as sao


def ingest_scoresandodds_markets(
    league: str,
    *,
    season: int | None = None,
    dates: list[str] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Pull live/upcoming odds for a slate league and upsert rows.
    """

    config = sao.get_league(league)
    if config.schedule_mode != "slate":
        raise ValueError(
            f"League {config.id!r} is week-based; use the NFL/NCAAF "
            "ingest paths instead."
        )

    rows, meta = sao.fetch_odds_rows(
        config.id,
        season=season,
        dates=dates,
    )
    resolved_season = int(
        season
        or meta.get("season")
        or datetime.now(timezone.utc).year
    )
    if not rows:
        return {
            "source": sao.SOURCE_LABEL,
            "league": config.id,
            "homepage": config.homepage,
            "season": resolved_season,
            "dates": dates or [],
            "fetched": 0,
            "matched": 0,
            "persisted": False,
            "note": "No odds rows returned from ScoresAndOdds feed.",
            "meta": meta,
        }

    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for row in rows:
        provider_game_id = str(row.get("provider_game_id") or "").strip()
        home = row.get("home_abbr")
        away = row.get("away_abbr")
        if not provider_game_id or not home or not away:
            skipped.append(row)
            continue

        game_id = f"sao:{config.id}:{provider_game_id}"
        timestamp = (
            row.get("line_inserted_at")
            or row.get("start_time")
            or datetime.now(timezone.utc).isoformat()
        )
        start_time = row.get("start_time")
        game_date = _game_date(start_time)
        season_type = str(row.get("season_type") or "reg").lower()

        records.append(
            {
                "league": config.id,
                "game_id": game_id,
                "game_date": game_date,
                "timestamp": timestamp,
                "source": sao.SOURCE_LABEL,
                "spread": row.get("spread"),
                "over_under": row.get("over_under"),
                "home_implied_total": row.get("home_implied_total"),
                "away_implied_total": row.get("away_implied_total"),
                "home_moneyline": row.get("home_moneyline"),
                "away_moneyline": row.get("away_moneyline"),
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
                "week": row.get("week"),
                "season_type": season_type,
                "home_abbr": home,
                "away_abbr": away,
                "home_name": row.get("home_name"),
                "away_name": row.get("away_name"),
                "start_time": start_time,
                "status": row.get("status"),
                "source_ids": {
                    "scoresandodds_game_id": provider_game_id,
                    "action_network_game_id": provider_game_id,
                    "sao_game_id": row.get("sao_game_id"),
                    "book_id": row.get("book_id"),
                    "home_abbr": home,
                    "away_abbr": away,
                    "league": config.id,
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
        "league": config.id,
        "homepage": config.homepage,
        "season": resolved_season,
        "dates": [
            d
            for d in (meta.get("dates") or [])
            if isinstance(d, dict) and d.get("date")
        ]
        or (dates or []),
        "fetched": len(rows),
        "matched": int(len(fact)),
        "skipped": len(skipped),
        "persisted": bool(persist and not fact.empty),
        "sample_skipped": [
            {
                "away": item.get("away_abbr"),
                "home": item.get("home_abbr"),
                "spread": item.get("spread"),
                "total": item.get("over_under"),
            }
            for item in skipped[:8]
        ],
        "meta": meta,
        "columns": list(FACT_COLUMNS),
    }


def _game_date(start_time: Any) -> str | None:
    if not start_time:
        return None
    text = str(start_time).strip()
    if not text:
        return None
    # ISO timestamps: keep calendar date portion.
    if "T" in text:
        return text.split("T", 1)[0][:10]
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None
