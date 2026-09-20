"""
Group and segment comparison primitives.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .change import percent_change, safe_ratio


def group_delta(
    left: float,
    right: float,
    *,
    fill: float = 0.0,
) -> dict[str, float]:
    """
    Absolute and relative difference between two group values.

    ``relative`` is (left - right) / right as a fraction.
    """

    left_value = float(left)
    right_value = float(right)

    absolute = left_value - right_value
    relative = float(
        percent_change(
            left_value,
            right_value,
            fill=fill,
        )
    )

    return {
        "left": left_value,
        "right": right_value,
        "absolute": absolute,
        "relative": relative,
    }


def vs_benchmark(
    series: pd.Series,
    benchmark: float,
    *,
    out_col: str | None = None,
) -> pd.Series:
    """
    Per-row gap versus a scalar benchmark (series - benchmark).
    """

    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    gaps = values - float(benchmark)

    if out_col is not None:
        gaps = gaps.rename(out_col)

    return gaps


def segment_vs_rest(
    df: pd.DataFrame,
    mask: pd.Series | Any,
    value_col: str,
    *,
    aggregation: str = "sum",
) -> dict[str, float]:
    """
    Compare a segment aggregate against the complementary rows.

    ``aggregation`` supports ``sum``, ``mean``, ``median``, ``count``.
    """

    if value_col not in df.columns:
        raise KeyError(
            f"Column '{value_col}' not found"
        )

    boolean_mask = pd.Series(
        mask,
        index=df.index,
    ).astype(bool)

    values = pd.to_numeric(
        df[value_col],
        errors="coerce",
    )

    segment = values[boolean_mask]
    rest = values[~boolean_mask]

    def _aggregate(series: pd.Series) -> float:
        if series.empty or series.dropna().empty:
            return 0.0

        if aggregation == "sum":
            return float(series.sum())

        if aggregation == "mean":
            return float(series.mean())

        if aggregation == "median":
            return float(series.median())

        if aggregation == "count":
            return float(series.count())

        raise ValueError(
            f"Unsupported aggregation '{aggregation}'"
        )

    segment_value = _aggregate(segment)
    rest_value = _aggregate(rest)
    overall_value = _aggregate(values)

    delta = group_delta(
        segment_value,
        rest_value,
    )

    share_of_overall = float(
        safe_ratio(
            segment_value,
            overall_value,
        )
    )

    return {
        "segment_value": segment_value,
        "rest_value": rest_value,
        "overall_value": overall_value,
        "segment_count": int(boolean_mask.sum()),
        "rest_count": int((~boolean_mask).sum()),
        "absolute_difference": delta["absolute"],
        "relative_difference": delta["relative"],
        "segment_share_of_overall": share_of_overall,
        "aggregation": aggregation,
    }
