"""Shared helpers for the analytical layer."""

from __future__ import annotations

from typing import Any

import pandas as pd


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def normalize_float(value: Any) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_int(value: Any) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def sql_null_if_missing(value: Any) -> Any:
    if is_missing(value):
        return None
    return value


def clip(
    value: float | None,
    low: float = 0.0,
    high: float = 100.0,
) -> float | None:
    if value is None:
        return None
    return max(low, min(high, value))


def score_from_rate(
    rate: float | None,
    *,
    scale: float = 100.0,
) -> float | None:
    value = normalize_float(rate)
    if value is None:
        return None
    return clip(value * scale)


def weighted_mean(
    values: list[float | None],
    weights: list[float] | None = None,
) -> float | None:
    pairs: list[tuple[float, float]] = []
    for index, value in enumerate(values):
        number = normalize_float(value)
        if number is None:
            continue
        weight = 1.0
        if weights is not None and index < len(weights):
            weight = float(weights[index])
        pairs.append((number, weight))
    if not pairs:
        return None
    total_weight = sum(weight for _, weight in pairs)
    if total_weight == 0:
        return None
    return (
        sum(number * weight for number, weight in pairs)
        / total_weight
    )


def rolling_mean_by_player(
    frame: pd.DataFrame,
    *,
    value_col: str,
    window: int = 3,
    player_col: str = "player_id",
    order_cols: list[str] | None = None,
) -> pd.Series:
    if frame.empty or value_col not in frame.columns:
        return pd.Series(
            [None] * len(frame),
            index=frame.index,
        )

    order = order_cols or ["season", "week"]
    working = frame.copy()
    working["_value"] = pd.to_numeric(
        working[value_col],
        errors="coerce",
    )
    working = working.sort_values(
        [player_col] + order,
        kind="mergesort",
    )
    rolled = working.groupby(player_col, sort=False)[
        "_value"
    ].transform(
        lambda series: series.rolling(
            window=window,
            min_periods=1,
        ).mean()
    )
    return rolled.reindex(frame.index)


def prior_value_by_player(
    frame: pd.DataFrame,
    *,
    value_col: str,
    player_col: str = "player_id",
    order_cols: list[str] | None = None,
) -> pd.Series:
    if frame.empty or value_col not in frame.columns:
        return pd.Series(
            [None] * len(frame),
            index=frame.index,
        )

    order = order_cols or ["season", "week"]
    working = frame.copy()
    working["_value"] = pd.to_numeric(
        working[value_col],
        errors="coerce",
    )
    working = working.sort_values(
        [player_col] + order,
        kind="mergesort",
    )
    prior = working.groupby(player_col, sort=False)[
        "_value"
    ].shift(1)
    return prior.reindex(frame.index)


def nullify_object_frame(
    frame: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    for column in columns:
        if column not in output.columns or column == "source_ids":
            continue
        output[column] = output[column].astype("object")
        output[column] = output[column].where(
            output[column].notna(),
            None,
        )
    return output
