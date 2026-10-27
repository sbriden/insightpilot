"""fact_game_market — CFB betting lines from sportsdataverse."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.cfb._common import (
    coerce_float,
    coerce_int,
    first_present,
    normalize_text,
    sql_null_if_missing,
    to_pandas,
)
from app.canonical.cfb.dim_game import (
    game_id_lookup_from_dim,
    get_dim_game,
)
from app.canonical.cfb.schema import (
    COLLEGE_SCHEMA,
    ensure_college_schema,
)
from app.database import engine


_CACHE: pd.DataFrame | None = None

FACT_COLUMNS = [
    "game_id",
    "timestamp",
    "source",
    "spread",
    "over_under",
    "home_implied_total",
    "away_implied_total",
    "home_moneyline",
    "away_moneyline",
    "opening_spread",
    "opening_over_under",
    "opening_home_implied_total",
    "opening_away_implied_total",
    "opening_captured_at",
    "season",
    "week",
    "season_type",
    "source_ids",
]


def _call_betting_loader(seasons: list[int]) -> pd.DataFrame:
    from sportsdataverse import cfb as cfb_mod

    for name in (
        "load_cfb_betting",
        "load_cfb_betting_lines",
        "load_cfb_lines",
    ):
        loader = getattr(cfb_mod, name, None)
        if loader is None:
            continue
        try:
            return to_pandas(
                loader(seasons=seasons, return_as_pandas=True)
            )
        except TypeError:
            return to_pandas(loader(seasons=seasons))
    raise AttributeError(
        "No CFB betting loader found in sportsdataverse.cfb"
    )


def _load_source_frames(
    seasons: list[int],
) -> dict[str, pd.DataFrame]:
    return {"betting": _call_betting_loader(seasons)}


def build_fact_game_market(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    raw = source_frames or _load_source_frames(seasons)
    betting = raw.get("betting", pd.DataFrame()).copy()
    if betting.empty:
        raise ValueError(
            "Unable to build CFB fact_game_market: empty betting."
        )

    game_lookup = game_id_lookup_from_dim(
        get_dim_game(
            seasons=seasons,
            force_refresh=False,
            persist=False,
        )
    )

    records: list[dict[str, Any]] = []
    for row in betting.to_dict(orient="records"):
        external_game = normalize_text(
            first_present(row, "game_id", "espn_game_id", "id")
        )
        game_id = (
            game_lookup.get(external_game)
            if external_game
            else None
        )
        if not game_id:
            continue

        spread = coerce_float(
            first_present(
                row,
                "home_team_spread",
                "game_spread",
                "spread",
                "home_spread",
                "spread_line",
                "provider_spread",
            )
        )
        total = coerce_float(
            first_present(
                row,
                "over_under",
                "total",
                "total_line",
                "provider_ou",
            )
        )
        home_ml = coerce_float(
            first_present(
                row,
                "home_moneyline",
                "home_ml",
                "homeMoneyline",
            )
        )
        away_ml = coerce_float(
            first_present(
                row,
                "away_moneyline",
                "away_ml",
                "awayMoneyline",
            )
        )

        home_implied = None
        away_implied = None
        if spread is not None and total is not None:
            home_implied = (total - spread) / 2.0
            away_implied = (total + spread) / 2.0

        source = normalize_text(
            first_present(
                row,
                "provider",
                "source",
                "book",
                "line_provider",
            )
        ) or "sportsdataverse"

        season = coerce_int(first_present(row, "season", "year"))
        week = coerce_int(first_present(row, "week"))
        resolution_key = f"{game_id}:{source}"

        records.append(
            {
                "game_id": game_id,
                "timestamp": normalize_text(
                    first_present(
                        row,
                        "timestamp",
                        "updated",
                        "start_date",
                    )
                ),
                "source": source,
                "spread": spread,
                "over_under": total,
                "home_implied_total": home_implied,
                "away_implied_total": away_implied,
                "home_moneyline": home_ml,
                "away_moneyline": away_ml,
                # sportsdataverse CFB lines are current-only;
                # leave opening NULL (ScoresAndOdds can fill later).
                "opening_spread": None,
                "opening_over_under": None,
                "opening_home_implied_total": None,
                "opening_away_implied_total": None,
                "opening_captured_at": None,
                "season": season,
                "week": week,
                "season_type": normalize_text(
                    first_present(row, "season_type", "game_type")
                ),
                "source_ids": {
                    "cfb_game_id": external_game,
                    "provider": source,
                },
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build CFB fact_game_market: no joined rows."
        )

    fact = pd.DataFrame.from_records(records)
    fact = fact.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    if persist:
        upsert_fact_game_market(fact)

    output = fact[FACT_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    global _CACHE
    _CACHE = output.copy()
    return output


def get_fact_game_market(
    seasons: list[int],
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _CACHE
    if (
        not force_refresh
        and _CACHE is not None
        and not _CACHE.empty
    ):
        allowed = {int(s) for s in seasons}
        cached = _CACHE[
            _CACHE["season"].map(
                lambda value: (
                    int(value) in allowed
                    if value is not None
                    else False
                )
            )
        ]
        if not cached.empty:
            return cached.copy()

    if not force_refresh:
        frame = load_fact_game_market_from_db(seasons)
        if not frame.empty:
            return frame

    return build_fact_game_market(seasons, persist=persist)


def load_fact_game_market_from_db(
    seasons: list[int],
) -> pd.DataFrame:
    ensure_college_schema()
    cols = (
        ", ".join(FACT_COLUMNS[:-1])
        + ", source_ids::text AS source_ids"
    )
    query = text(
        f"""
        SELECT {cols}
        FROM {COLLEGE_SCHEMA}.fact_game_market
        WHERE season = ANY(:seasons)
        """
    )
    with engine.connect() as connection:
        return pd.read_sql(
            query,
            connection,
            params={"seasons": [int(s) for s in seasons]},
        )


def upsert_fact_game_market(fact: pd.DataFrame) -> None:
    if fact.empty:
        return

    ensure_college_schema()
    statement = text(
        f"""
        INSERT INTO {COLLEGE_SCHEMA}.fact_game_market (
            game_id, timestamp, source, spread, over_under,
            home_implied_total, away_implied_total,
            home_moneyline, away_moneyline,
            opening_spread, opening_over_under,
            opening_home_implied_total, opening_away_implied_total,
            opening_captured_at,
            season, week, season_type,
            source_ids, resolution_key, updated_at
        ) VALUES (
            :game_id, CAST(:timestamp AS TIMESTAMP), :source,
            :spread, :over_under,
            :home_implied_total, :away_implied_total,
            :home_moneyline, :away_moneyline,
            :opening_spread, :opening_over_under,
            :opening_home_implied_total, :opening_away_implied_total,
            CAST(NULLIF(:opening_captured_at, '') AS TIMESTAMP),
            :season, :week, :season_type,
            CAST(:source_ids AS JSONB), :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            game_id = EXCLUDED.game_id,
            timestamp = EXCLUDED.timestamp,
            source = EXCLUDED.source,
            spread = EXCLUDED.spread,
            over_under = EXCLUDED.over_under,
            home_implied_total = EXCLUDED.home_implied_total,
            away_implied_total = EXCLUDED.away_implied_total,
            home_moneyline = EXCLUDED.home_moneyline,
            away_moneyline = EXCLUDED.away_moneyline,
            opening_spread = COALESCE(
                EXCLUDED.opening_spread,
                {COLLEGE_SCHEMA}.fact_game_market.opening_spread
            ),
            opening_over_under = COALESCE(
                EXCLUDED.opening_over_under,
                {COLLEGE_SCHEMA}.fact_game_market.opening_over_under
            ),
            opening_home_implied_total = COALESCE(
                EXCLUDED.opening_home_implied_total,
                {COLLEGE_SCHEMA}.fact_game_market.opening_home_implied_total
            ),
            opening_away_implied_total = COALESCE(
                EXCLUDED.opening_away_implied_total,
                {COLLEGE_SCHEMA}.fact_game_market.opening_away_implied_total
            ),
            opening_captured_at = COALESCE(
                EXCLUDED.opening_captured_at,
                {COLLEGE_SCHEMA}.fact_game_market.opening_captured_at
            ),
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
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
                key: sql_null_if_missing(record.get(key))
                for key in (
                    "game_id",
                    "timestamp",
                    "source",
                    "spread",
                    "over_under",
                    "home_implied_total",
                    "away_implied_total",
                    "home_moneyline",
                    "away_moneyline",
                    "opening_spread",
                    "opening_over_under",
                    "opening_home_implied_total",
                    "opening_away_implied_total",
                    "opening_captured_at",
                    "season",
                    "week",
                    "season_type",
                )
            }
            | {
                "source_ids": source_ids,
                "resolution_key": record["resolution_key"],
            }
        )

    batch_size = 500
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def clear_fact_game_market_cache() -> None:
    global _CACHE
    _CACHE = None
