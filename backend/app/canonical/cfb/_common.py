"""Shared helpers for college_football canonical builders."""

from __future__ import annotations

from typing import Any

import pandas as pd


def to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    if hasattr(frame, "to_dicts"):
        return pd.DataFrame(frame.to_dicts())
    raise TypeError(
        "Expected a pandas or polars DataFrame."
    )


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def normalize_text(value: Any) -> str | None:
    if is_missing(value):
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


def sql_null_if_missing(value: Any) -> Any:
    if is_missing(value):
        return None
    return value


def first_present(
    row: dict[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        if key in row and not is_missing(row.get(key)):
            return row.get(key)
    return None


def coerce_int(value: Any) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pick_column(
    frame: pd.DataFrame,
    *candidates: str,
) -> str | None:
    lower_map = {
        str(col).lower(): str(col) for col in frame.columns
    }
    for candidate in candidates:
        hit = lower_map.get(candidate.lower())
        if hit is not None:
            return hit
    return None
