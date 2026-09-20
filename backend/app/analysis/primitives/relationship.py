"""
Relationship / correlation primitives.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def pearson_corr(
    x: pd.Series,
    y: pd.Series,
    *,
    min_periods: int = 3,
) -> float | None:
    """
    Pearson correlation between two series.

    Returns ``None`` when there are fewer than ``min_periods``
    overlapping finite pairs or when correlation is undefined.
    """

    left = pd.to_numeric(x, errors="coerce")
    right = pd.to_numeric(y, errors="coerce")

    left, right = left.align(right, join="inner")

    paired = pd.DataFrame(
        {
            "x": left,
            "y": right,
        }
    ).dropna()

    if len(paired) < min_periods:
        return None

    if paired["x"].nunique() < 2 or paired["y"].nunique() < 2:
        return None

    value = float(paired["x"].corr(paired["y"]))

    if not np.isfinite(value):
        return None

    return value


def corr_matrix(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    *,
    min_periods: int = 3,
) -> pd.DataFrame:
    """
    Pairwise Pearson correlation matrix for numeric columns.
    """

    if columns is None:
        numeric = df.select_dtypes(include="number")
    else:
        missing = [
            column
            for column in columns
            if column not in df.columns
        ]

        if missing:
            raise KeyError(
                f"Columns not found: {missing}"
            )

        numeric = df[columns].apply(
            pd.to_numeric,
            errors="coerce",
        )

    if numeric.empty:
        return pd.DataFrame()

    matrix = numeric.corr(
        method="pearson",
        min_periods=min_periods,
    )

    return matrix.replace(
        [np.inf, -np.inf],
        np.nan,
    )
