"""
Trend, rolling baseline, and growth/decline primitives.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .change import percent_change, safe_ratio


def add_rolling_baseline(
    series: pd.Series,
    *,
    window: int = 3,
    shift: int = 1,
) -> pd.Series:
    """
    Rolling mean baseline, optionally shifted to avoid leakage.

    Matches revenue-trends behavior: rolling(window).mean().shift(1).
    """

    if window < 1:
        raise ValueError("window must be >= 1")

    cleaned = pd.to_numeric(
        series,
        errors="coerce",
    )

    baseline = cleaned.rolling(window).mean()

    if shift:
        baseline = baseline.shift(shift)

    return baseline


def relative_deviation(
    series: pd.Series,
    baseline: pd.Series,
    *,
    fill: float = 0.0,
) -> pd.Series:
    """
    (series - baseline) / baseline with non-finite cleanup.
    """

    values = pd.to_numeric(
        series,
        errors="coerce",
    )
    base = pd.to_numeric(
        baseline,
        errors="coerce",
    )

    values, base = values.align(
        base,
        fill_value=np.nan,
    )

    deviation = safe_ratio(
        values - base,
        base,
        fill=np.nan,
    )

    deviation = deviation.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    return deviation.fillna(fill)


def classify_trend_direction(
    change: float,
    *,
    up: float = 0.05,
    down: float = -0.05,
) -> str:
    """
    Map a relative change to growing / declining / stable.
    """

    value = float(change)

    if value > float(up):
        return "growing"

    if value < float(down):
        return "declining"

    return "stable"


def window_mean_change(
    series: pd.Series,
    *,
    window: int = 3,
    fill: float = 0.0,
) -> dict:
    """
    Compare the mean of the last ``window`` points to the
    prior ``window`` points (growth / decline signal).
    """

    if window < 1:
        raise ValueError("window must be >= 1")

    cleaned = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if len(cleaned) < window * 2:
        overall = (
            float(cleaned.mean())
            if not cleaned.empty
            else 0.0
        )

        return {
            "recent": overall,
            "previous": overall,
            "change": fill,
            "direction": "stable",
            "window": window,
            "sufficient_history": False,
        }

    recent = float(cleaned.tail(window).mean())
    previous = float(
        cleaned.iloc[-2 * window : -window].mean()
    )
    change = float(
        percent_change(
            recent,
            previous,
            fill=fill,
        )
    )

    return {
        "recent": recent,
        "previous": previous,
        "change": change,
        "direction": classify_trend_direction(change),
        "window": window,
        "sufficient_history": True,
    }
