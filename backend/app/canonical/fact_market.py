"""
fact_market — external fantasy market, separate from performance.

Captures ranks, projections, ADP, and ownership from market
sources (FantasyPros via nflverse). Grain: player × season ×
week × source (week nullable for draft ADP snapshots).
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.dim_player import (
    get_dim_player,
    player_id_lookup_from_dim,
)
from app.canonical.ids import (
    make_player_id,
    player_resolution_key,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_FACT_MARKET_CACHE: pd.DataFrame | None = None
_FACT_MARKET_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_MARKET_CACHE_SEASONS: tuple[int, ...] | None = None

FACT_MARKET_COLUMNS = [
    "player_id",
    "season",
    "week",
    "source",
    "rank",
    "projection",
    "adp",
    "ownership",
    "source_ids",
]

_WEEKLY_PAGES = {
    "qb",
    "ppr-rb",
    "ppr-wr",
    "ppr-te",
    "rb",
    "wr",
    "te",
}


def _to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    raise TypeError("Expected a pandas or polars DataFrame.")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _normalize_text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text_value = str(value).strip()
    if not text_value or text_value.lower() in {
        "nan",
        "none",
        "nat",
        "<na>",
    }:
        return None
    return text_value


def _sql_null_if_missing(value: Any) -> Any:
    if _is_missing(value):
        return None
    return value


def _normalize_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_ff_playerids() -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_ff_playerids())


def _load_weekly_rankings() -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_ff_rankings(type="week"))


def _load_draft_rankings() -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_ff_rankings(type="draft"))


def _fantasypros_to_gsis(
    ff_ids: pd.DataFrame,
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if ff_ids.empty:
        return lookup
    if (
        "fantasypros_id" not in ff_ids.columns
        or "gsis_id" not in ff_ids.columns
    ):
        return lookup
    for record in ff_ids.to_dict(orient="records"):
        fp_id = _normalize_text(record.get("fantasypros_id"))
        gsis_id = _normalize_text(record.get("gsis_id"))
        if fp_id and gsis_id:
            # FantasyPros IDs often arrive as floats in CSV.
            if fp_id.endswith(".0"):
                fp_id = fp_id[:-2]
            lookup[fp_id] = gsis_id
    return lookup


def _fantasypros_from_dim(
    dim: pd.DataFrame,
) -> dict[str, str]:
    """Map fantasypros_id -> InsightPilot player_id when present."""

    lookup: dict[str, str] = {}
    if dim.empty:
        return lookup
    for record in dim.to_dict(orient="records"):
        player_id = record.get("player_id")
        source_ids = record.get("source_ids") or {}
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except json.JSONDecodeError:
                source_ids = {}
        if not isinstance(source_ids, dict) or not player_id:
            continue
        fp_id = _normalize_text(source_ids.get("fantasypros_id"))
        if fp_id:
            if fp_id.endswith(".0"):
                fp_id = fp_id[:-2]
            lookup[fp_id] = str(player_id)
    return lookup


def _normalize_fp_id(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def build_fact_market(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
    player_id_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    import nflreadpy as nfl

    resolved_seasons = sorted({int(season) for season in seasons})
    current_season = int(nfl.get_current_season())
    current_week = int(nfl.get_current_week())

    if current_season not in resolved_seasons:
        raise ValueError(
            "fact_market currently loads live FantasyPros "
            f"snapshots for season {current_season} only."
        )

    raw = source_frames or {}

    weekly = raw.get("weekly_rankings")
    if weekly is None:
        if source_frames is None:
            weekly = _load_weekly_rankings()
        else:
            weekly = pd.DataFrame()
    else:
        weekly = weekly.copy()

    draft = raw.get("draft_rankings")
    if draft is None:
        if source_frames is None:
            draft = _load_draft_rankings()
        else:
            draft = pd.DataFrame()
    else:
        draft = draft.copy()

    ff_ids = raw.get("ff_playerids")
    if ff_ids is None:
        if source_frames is None:
            ff_ids = _load_ff_playerids()
        else:
            ff_ids = pd.DataFrame()
    else:
        ff_ids = ff_ids.copy()

    fp_to_gsis = _fantasypros_to_gsis(ff_ids)

    if player_id_lookup is None:
        dim_player = get_dim_player(
            force_refresh=False,
            persist=persist,
        )
        gsis_lookup = player_id_lookup_from_dim(dim_player)
        fp_to_player = _fantasypros_from_dim(dim_player)
    else:
        gsis_lookup = player_id_lookup
        fp_to_player = {}

    records: list[dict[str, Any]] = []

    if not weekly.empty:
        working = weekly.copy()
        if "page" in working.columns:
            working = working[
                working["page"]
                .astype("string")
                .str.lower()
                .isin(_WEEKLY_PAGES)
            ]
        for row in working.to_dict(orient="records"):
            fp_id = _normalize_fp_id(
                row.get("fantasypros_id") or row.get("id")
            )
            if not fp_id:
                continue

            player_id = fp_to_player.get(fp_id)
            gsis_id = fp_to_gsis.get(fp_id)
            if player_id is None and gsis_id:
                player_id = gsis_lookup.get(gsis_id)
                if player_id is None:
                    try:
                        player_id = make_player_id(
                            player_resolution_key(
                                gsis_id=gsis_id
                            )
                        )
                    except ValueError:
                        continue
            if player_id is None:
                continue

            page = _normalize_text(row.get("page")) or "weekly"
            source = "fantasypros_weekly"
            rank = _normalize_float(
                row.get("rank")
                if not _is_missing(row.get("rank"))
                else row.get("ecr")
            )
            projection = _normalize_float(row.get("r2p_pts"))
            ownership = _normalize_float(
                row.get("player_owned_avg")
            )

            source_ids: dict[str, str] = {
                "fantasypros_id": fp_id,
                "market_page": page,
            }
            if gsis_id:
                source_ids["gsis_id"] = gsis_id

            records.append(
                {
                    "player_id": player_id,
                    "season": current_season,
                    "week": current_week,
                    "source": source,
                    "rank": rank,
                    "projection": projection,
                    "adp": None,
                    "ownership": ownership,
                    "source_ids": source_ids,
                    "resolution_key": (
                        f"{fp_id}:{source}:{current_season}:"
                        f"{current_week}:{page}"
                    ),
                }
            )

    if not draft.empty:
        working = draft.copy()
        if "page_type" in working.columns:
            working = working[
                working["page_type"]
                .astype("string")
                .str.lower()
                .isin({"redraft-overall", "redraft-ppr"})
                | working["page_type"]
                .astype("string")
                .str.lower()
                .str.startswith("redraft-")
            ]
            # Prefer overall PPR/redraft board when present.
            overall = working[
                working["page_type"]
                .astype("string")
                .str.lower()
                .isin({"redraft-overall", "redraft-ppr"})
            ]
            if not overall.empty:
                working = overall

        for row in working.to_dict(orient="records"):
            fp_id = _normalize_fp_id(
                row.get("id") or row.get("fantasypros_id")
            )
            if not fp_id:
                continue

            player_id = fp_to_player.get(fp_id)
            gsis_id = fp_to_gsis.get(fp_id)
            if player_id is None and gsis_id:
                player_id = gsis_lookup.get(gsis_id)
                if player_id is None:
                    try:
                        player_id = make_player_id(
                            player_resolution_key(
                                gsis_id=gsis_id
                            )
                        )
                    except ValueError:
                        continue
            if player_id is None:
                continue

            page_type = (
                _normalize_text(row.get("page_type"))
                or "redraft"
            )
            source = "fantasypros_draft"
            adp = _normalize_float(row.get("ecr"))
            ownership = _normalize_float(
                row.get("player_owned_avg")
            )

            source_ids = {
                "fantasypros_id": fp_id,
                "market_page": page_type,
            }
            if gsis_id:
                source_ids["gsis_id"] = gsis_id

            records.append(
                {
                    "player_id": player_id,
                    "season": current_season,
                    "week": None,
                    "source": source,
                    "rank": adp,
                    "projection": None,
                    "adp": adp,
                    "ownership": ownership,
                    "source_ids": source_ids,
                    "resolution_key": (
                        f"{fp_id}:{source}:{current_season}:"
                        f"na:{page_type}"
                    ),
                }
            )

    if not records:
        raise ValueError(
            "Unable to build fact_market: no resolvable market "
            "rows were available."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_MARKET_COLUMNS + ["resolution_key"]:
        if column == "source_ids" or column not in fact.columns:
            continue
        fact[column] = fact[column].astype("object")
        fact[column] = fact[column].where(
            fact[column].notna(),
            None,
        )

    fact = fact.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_MARKET_CACHE
    global _FACT_MARKET_CACHE_WITH_KEYS
    global _FACT_MARKET_CACHE_SEASONS
    _FACT_MARKET_CACHE_WITH_KEYS = fact.copy()
    _FACT_MARKET_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_market(fact)

    output = fact[FACT_MARKET_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "source", "rank", "player_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_MARKET_CACHE = output.copy()
    return output


def fact_market_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_market"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_market(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_MARKET_CACHE
    global _FACT_MARKET_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_MARKET_CACHE is not None
        and not _FACT_MARKET_CACHE.empty
        and _FACT_MARKET_CACHE_SEASONS == tuple(resolved)
    ):
        return _FACT_MARKET_CACHE.copy()

    if not force_refresh and fact_market_count() > 0:
        frame = load_fact_market_from_db(seasons=resolved)
        if not frame.empty:
            _FACT_MARKET_CACHE = frame.copy()
            _FACT_MARKET_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_fact_market(
        resolved,
        persist=persist,
    )


def upsert_fact_market(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_market (
            player_id,
            season,
            week,
            source,
            rank,
            projection,
            adp,
            ownership,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :player_id,
            :season,
            :week,
            :source,
            :rank,
            :projection,
            :adp,
            :ownership,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            player_id = EXCLUDED.player_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            source = EXCLUDED.source,
            rank = EXCLUDED.rank,
            projection = EXCLUDED.projection,
            adp = EXCLUDED.adp,
            ownership = EXCLUDED.ownership,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in fact.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(
                source_ids,
                sort_keys=True,
            )
        rows.append(
            {
                "player_id": record["player_id"],
                "season": _sql_null_if_missing(
                    record.get("season")
                ),
                "week": _sql_null_if_missing(
                    record.get("week")
                ),
                "source": _sql_null_if_missing(
                    record.get("source")
                ),
                "rank": _sql_null_if_missing(
                    record.get("rank")
                ),
                "projection": _sql_null_if_missing(
                    record.get("projection")
                ),
                "adp": _sql_null_if_missing(
                    record.get("adp")
                ),
                "ownership": _sql_null_if_missing(
                    record.get("ownership")
                ),
                "source_ids": source_ids,
                "resolution_key": record["resolution_key"],
            }
        )

    batch_size = 1000
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def load_fact_market_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_MARKET_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_market
        ORDER BY season, week, source, rank, player_id
    """

    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(query),
            connection,
        )

    if seasons and not frame.empty and "season" in frame.columns:
        allowed = {int(season) for season in seasons}
        frame = frame[
            frame["season"].map(
                lambda value: (
                    int(value) in allowed
                    if not _is_missing(value)
                    else False
                )
            )
        ].reset_index(drop=True)

    if "source_ids" in frame.columns:
        frame["source_ids"] = frame["source_ids"].map(
            lambda value: (
                json.dumps(value, sort_keys=True)
                if isinstance(value, dict)
                else value
            )
        )
    return frame
