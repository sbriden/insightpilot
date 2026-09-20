"""
Outlier detection primitives.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .change import safe_ratio


def flag_threshold(
    series: pd.Series,
    *,
    abs_threshold: float,
) -> pd.Series:
    """
    Boolean flags where ``abs(value) >= abs_threshold``.

    Useful for relative deviation series (e.g. trend anomalies).
    """

    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    return values.abs() >= float(abs_threshold)


def flag_iqr(
    series: pd.Series,
    *,
    k: float = 1.5,
) -> pd.Series:
    """
    Tukey IQR outlier flags.

    Values below Q1 - k*IQR or above Q3 + k*IQR are True.
    """

    values = pd.to_numeric(
        series,
        errors="coerce",
    )
    valid = values.dropna()

    if len(valid) < 4:
        return pd.Series(
            False,
            index=series.index,
        )

    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1

    if iqr == 0:
        return pd.Series(
            False,
            index=series.index,
        )

    lower = q1 - float(k) * iqr
    upper = q3 + float(k) * iqr

    return (values < lower) | (values > upper)


def flag_zscore(
    series: pd.Series,
    *,
    z: float = 3.0,
) -> pd.Series:
    """
    Absolute z-score outlier flags (|z| >= threshold).
    """

    values = pd.to_numeric(
        series,
        errors="coerce",
    )
    valid = values.dropna()

    if len(valid) < 2:
        return pd.Series(
            False,
            index=series.index,
        )

    mean = float(valid.mean())
    std = float(valid.std())

    if std == 0 or not np.isfinite(std):
        return pd.Series(
            False,
            index=series.index,
        )

    scores = safe_ratio(
        values - mean,
        std,
        fill=0.0,
    )

    return scores.abs() >= float(z)


def outlier_summary(
    series: pd.Series,
    flags: pd.Series,
) -> dict:
    """
    Compact outlier facts given a boolean flag series.
    """

    values = pd.to_numeric(
        series,
        errors="coerce",
    )
    boolean_flags = pd.Series(
        flags,
        index=series.index,
    ).fillna(False).astype(bool)

    flagged = values[boolean_flags].dropna()

    return {
        "count": int(boolean_flags.sum()),
        "rate": float(
            safe_ratio(
                float(boolean_flags.sum()),
                float(len(series)),
            )
        ),
        "min_flagged": (
            float(flagged.min())
            if not flagged.empty
            else None
        ),
        "max_flagged": (
            float(flagged.max())
            if not flagged.empty
            else None
        ),
    }
