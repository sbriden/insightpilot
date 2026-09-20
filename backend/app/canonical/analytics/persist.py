"""Generic analytics table persistence helpers."""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from app.canonical.analytics.common import (
    sql_null_if_missing,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_JSON_COLUMNS = frozenset({"source_ids", "supporting_metrics"})


def _serialize_json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _serialize_json_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame
    for column in _JSON_COLUMNS:
        if column not in output.columns:
            continue
        output[column] = output[column].map(_serialize_json_value)
    return output


def count_rows(table_name: str) -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.{table_name}"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def load_rows(
    table_name: str,
    columns: list[str],
    *,
    seasons: list[int] | None = None,
    player_id: str | None = None,
    order_by: str,
) -> pd.DataFrame:
    column_sql = ", ".join(columns)
    params: dict[str, Any] = {}
    clauses: list[str] = []

    if seasons:
        placeholders = []
        for index, season in enumerate(sorted({int(s) for s in seasons})):
            key = f"season_{index}"
            placeholders.append(f":{key}")
            params[key] = season
        clauses.append(
            f"season IN ({', '.join(placeholders)})"
        )

    if player_id:
        params["player_id"] = str(player_id)
        clauses.append("player_id = :player_id")

    where_clause = ""
    if clauses:
        where_clause = " WHERE " + " AND ".join(clauses)

    query = f"""
        SELECT {column_sql}
        FROM {FANTASY_SCHEMA}.{table_name}
        {where_clause}
        ORDER BY {order_by}
    """
    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(query),
            connection,
            params=params or None,
        )

    return _serialize_json_columns(frame)


def upsert_rows(
    table_name: str,
    columns: list[str],
    frame: pd.DataFrame,
    *,
    batch_size: int = 1000,
    immutable_on_conflict: list[str] | None = None,
) -> None:
    if frame.empty:
        return

    json_cols = [
        column for column in columns if column in _JSON_COLUMNS
    ]
    value_cols = [
        column
        for column in columns
        if column not in _JSON_COLUMNS
    ] + json_cols + ["resolution_key"]

    placeholders = []
    for column in value_cols:
        if column in _JSON_COLUMNS:
            placeholders.append(f"CAST(:{column} AS JSONB)")
        else:
            placeholders.append(f":{column}")
    placeholders.append("CURRENT_TIMESTAMP")

    skip_update = set(immutable_on_conflict or [])
    update_assignments = ",\n            ".join(
        f"{column} = EXCLUDED.{column}"
        for column in columns
        if column not in skip_update
    )

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.{table_name} (
            {", ".join(columns)},
            resolution_key,
            updated_at
        ) VALUES (
            {", ".join(placeholders)}
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            {update_assignments},
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        row: dict[str, Any] = {
            "resolution_key": record["resolution_key"],
        }
        for column in columns:
            value = record.get(column)
            if column in _JSON_COLUMNS:
                if value is None:
                    value = {}
                row[column] = _serialize_json_value(value)
            else:
                row[column] = sql_null_if_missing(value)
        rows.append(row)

    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def finalize_output(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    sort_cols: list[str],
    serialize_source_ids: bool = True,
) -> pd.DataFrame:
    del serialize_source_ids  # kept for call-site compatibility
    output = frame[columns].copy()
    output = _serialize_json_columns(output)
    return output.sort_values(
        sort_cols,
        kind="mergesort",
    ).reset_index(drop=True)


def get_or_build(
    *,
    seasons: list[int] | None,
    force_refresh: bool,
    persist: bool,
    cache: pd.DataFrame | None,
    cache_seasons: tuple[int, ...] | None,
    set_cache: Callable[[pd.DataFrame, tuple[int, ...]], None],
    count_fn: Callable[[], int],
    load_fn: Callable[[list[int]], pd.DataFrame],
    build_fn: Callable[..., pd.DataFrame],
) -> pd.DataFrame:
    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})
    key = tuple(resolved)

    if (
        not force_refresh
        and cache is not None
        and not cache.empty
        and cache_seasons == key
    ):
        return cache.copy()

    if not force_refresh and count_fn() > 0:
        frame = load_fn(resolved)
        if not frame.empty:
            set_cache(frame.copy(), key)
            return frame

    return build_fn(resolved, persist=persist)
