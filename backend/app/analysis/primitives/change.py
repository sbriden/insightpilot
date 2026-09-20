"""
Period-over-period and ratio change primitives.
"""

from __future__ import annotations

from typing import Union

import numpy as np
import pandas as pd


NumberOrSeries = Union[float, int, pd.Series]


def safe_ratio(
    numerator: NumberOrSeries,
    denominator: NumberOrSeries,
    *,
    fill: float = 0.0,
) -> NumberOrSeries:
    """
    Divide with zero / non-finite protection.

    Returns ``fill`` where the denominator is zero or the
    quotient would be non-finite.
    """

    num_is_series = isinstance(numerator, pd.Series)
    den_is_series = isinstance(denominator, pd.Series)

    if num_is_series or den_is_series:

        if num_is_series and den_is_series:
            num = numerator.astype("float64")
            den = denominator.astype("float64")
            num, den = num.align(den, fill_value=np.nan)

        elif num_is_series:
            num = numerator.astype("float64")
            den_value = float(denominator)

            if den_value == 0:
                return pd.Series(
                    fill,
                    index=num.index,
                    dtype="float64",
                )

            result = num / den_value
            result = result.replace(
                [np.inf, -np.inf],
                np.nan,
            )
            return result.fillna(fill)

        else:
            den = denominator.astype("float64")
            num = pd.Series(
                float(numerator),
                index=den.index,
                dtype="float64",
            )

            result = num / den.replace(0, np.nan)
            result = result.replace(
                [np.inf, -np.inf],
                np.nan,
            )
            return result.fillna(fill)

        result = num / den.replace(0, np.nan)
        result = result.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        return result.fillna(fill)

    den_value = float(denominator)

    if den_value == 0:
        return fill

    value = float(numerator) / den_value

    if not np.isfinite(value):
        return fill

    return value


def percent_change(
    current: NumberOrSeries,
    previous: NumberOrSeries,
    *,
    fill: float = 0.0,
) -> NumberOrSeries:
    """
    Relative change: (current - previous) / previous.

    Returns a fraction (0.1 == +10%), not a percentage point.
    """

    if isinstance(current, pd.Series) or isinstance(
        previous,
        pd.Series,
    ):

        cur = pd.Series(current, dtype="float64")
        prev = pd.Series(previous, dtype="float64")

        if isinstance(current, pd.Series) and isinstance(
            previous,
            pd.Series,
        ):
            cur, prev = cur.align(prev, fill_value=np.nan)

        return safe_ratio(
            cur - prev,
            prev,
            fill=fill,
        )

    return safe_ratio(
        float(current) - float(previous),
        previous,
        fill=fill,
    )


def period_over_period(
    series: pd.Series,
    *,
    periods: int = 1,
    fill: float | None = None,
) -> pd.Series:
    """
    Lagged percent change along a Series.

    Matches pandas ``pct_change`` semantics. When ``fill`` is
    provided, non-finite values are replaced with that fill.
    """

    if periods < 1:
        raise ValueError("periods must be >= 1")

    cleaned = pd.to_numeric(
        series,
        errors="coerce",
    )

    result = cleaned.pct_change(periods=periods)
    result = result.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    if fill is not None:
        return result.fillna(fill)

    return result


def overall_change(
    series: pd.Series,
    *,
    fill: float = 0.0,
) -> float:
    """
    First-to-last relative change for a time-ordered series.
    """

    cleaned = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if len(cleaned) < 2:
        return fill

    first = float(cleaned.iloc[0])
    last = float(cleaned.iloc[-1])

    return float(
        percent_change(
            last,
            first,
            fill=fill,
        )
    )
