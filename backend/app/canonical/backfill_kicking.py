"""
One-off / on-demand backfill for kicker stats on fact_player_game.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


KICKING_COLUMNS = [
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
]


def _to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    raise TypeError("Expected a pandas or polars DataFrame.")


def _normalize_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def backfill_fact_player_game_kicking(
    seasons: list[int] | None = None,
) -> dict[str, Any]:
    """
    Populate kicking columns on existing fact_player_game rows
    from nflverse weekly player stats.
    """

    import nflreadpy as nfl

    if seasons is None:
        try:
            seasons = [int(nfl.get_current_season())]
        except Exception:
            seasons = []
    resolved = sorted({int(season) for season in seasons})
    if not resolved:
        return {"updated": 0, "seasons": []}

    stats = _to_pandas(
        nfl.load_player_stats(
            seasons=resolved,
            summary_level="week",
        )
    )
    if stats.empty:
        return {"updated": 0, "seasons": resolved}

    updates: list[dict[str, Any]] = []
    for row in stats.to_dict(orient="records"):
        gsis = str(row.get("player_id") or "").strip()
        game = str(row.get("game_id") or "").strip()
        if not gsis or not game:
            continue
        payload = {
            "gsis_id": gsis,
            "nflverse_game_id": game,
        }
        has_kick = False
        for column in KICKING_COLUMNS:
            value = _normalize_int(row.get(column))
            payload[column] = value
            if value is not None:
                has_kick = True
        if has_kick:
            updates.append(payload)

    if not updates:
        return {"updated": 0, "seasons": resolved}

    statement = text(
        f"""
        UPDATE {FANTASY_SCHEMA}.fact_player_game AS g
        SET
          fg_made = COALESCE(:fg_made, g.fg_made),
          fg_att = COALESCE(:fg_att, g.fg_att),
          fg_made_0_19 = COALESCE(:fg_made_0_19, g.fg_made_0_19),
          fg_made_20_29 = COALESCE(:fg_made_20_29, g.fg_made_20_29),
          fg_made_30_39 = COALESCE(:fg_made_30_39, g.fg_made_30_39),
          fg_made_40_49 = COALESCE(:fg_made_40_49, g.fg_made_40_49),
          fg_made_50_59 = COALESCE(:fg_made_50_59, g.fg_made_50_59),
          fg_made_60_ = COALESCE(:fg_made_60_, g.fg_made_60_),
          pat_made = COALESCE(:pat_made, g.pat_made),
          pat_att = COALESCE(:pat_att, g.pat_att),
          updated_at = CURRENT_TIMESTAMP
        WHERE g.source_ids ->> 'gsis_id' = :gsis_id
          AND g.source_ids ->> 'nflverse_game_id' = :nflverse_game_id
        """
    )

    updated = 0
    batch_size = 500
    with engine.begin() as connection:
        for start in range(0, len(updates), batch_size):
            batch = updates[start:start + batch_size]
            for payload in batch:
                result = connection.execute(statement, payload)
                updated += result.rowcount or 0

    return {
        "updated": updated,
        "candidates": len(updates),
        "seasons": resolved,
    }


if __name__ == "__main__":
    print(json.dumps(backfill_fact_player_game_kicking(), indent=2))
