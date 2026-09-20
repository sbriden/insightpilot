"""
Distribution summary primitives.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def numeric_summary(
    series: pd.Series,
) -> dict[str, float | int]:
    """
    Deterministic distribution summary for a numeric series.

    Aligns with upload-path metric keys where practical
    (count, sum, mean, median, min, max, std).
    """

    cleaned = pd.to_numeric(
        series,
        errors="coerce",
    )
    valid = cleaned.dropna()

    if valid.empty:
        return {
            "count": 0,
            "sum": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std": 0.0,
            "missing": int(cleaned.isna().sum()),
            "zeros": 0,
            "negative_values": 0,
        }

    return {
        "count": int(valid.count()),
        "sum": float(valid.sum()),
        "mean": float(valid.mean()),
        "median": float(valid.median()),
        "min": float(valid.min()),
        "max": float(valid.max()),
        "std": (
            float(valid.std())
            if valid.count() > 1
            else 0.0
        ),
        "missing": int(cleaned.isna().sum()),
        "zeros": int((valid == 0).sum()),
        "negative_values": int((valid < 0).sum()),
    }


def percentile_table(
    series: pd.Series,
    quantiles: Iterable[float] = (
        0.1,
        0.25,
        0.5,
        0.75,
        0.9,
    ),
) -> dict[str, float]:
    """
    Percentile / quantile table for a numeric series.

    Keys are formatted as ``p10``, ``p25``, ``p50``, etc.
    """

    cleaned = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    result: dict[str, float] = {}

    qs = list(quantiles)

    if cleaned.empty:
        for q in qs:
            key = f"p{int(round(float(q) * 100))}"
            result[key] = 0.0
        return result

    for q in qs:
        q_value = float(q)

        if q_value < 0 or q_value > 1:
            raise ValueError(
                "quantiles must be between 0 and 1"
            )

        key = f"p{int(round(q_value * 100))}"
        value = float(
            np.nanpercentile(
                cleaned.to_numpy(),
                q_value * 100,
            )
        )
        result[key] = value

    return result
