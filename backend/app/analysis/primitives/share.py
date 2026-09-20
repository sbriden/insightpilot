"""
Contribution / share and concentration primitives.
"""

from __future__ import annotations

import pandas as pd

from .change import safe_ratio


def add_share(
    df: pd.DataFrame,
    value_col: str,
    *,
    out_col: str = "share",
    total: float | None = None,
) -> pd.DataFrame:
    """
    Append a row-level share column (fraction of total).

    Does not mutate the input frame.
    """

    if value_col not in df.columns:
        raise KeyError(
            f"Column '{value_col}' not found"
        )

    result = df.copy()

    values = pd.to_numeric(
        result[value_col],
        errors="coerce",
    ).fillna(0.0)

    total_value = (
        float(total)
        if total is not None
        else float(values.sum())
    )

    result[out_col] = safe_ratio(
        values,
        total_value,
        fill=0.0,
    )

    return result


def top_n_share(
    df: pd.DataFrame,
    value_col: str,
    *,
    n: int = 10,
    already_sorted: bool = False,
) -> float:
    """
    Share of total held by the top ``n`` rows by value.

    Expects larger values first when ``already_sorted`` is True.
    """

    if n < 1:
        raise ValueError("n must be >= 1")

    if df.empty or value_col not in df.columns:
        return 0.0

    values = pd.to_numeric(
        df[value_col],
        errors="coerce",
    ).fillna(0.0)

    total = float(values.sum())

    if total == 0:
        return 0.0

    if already_sorted:
        top = values.head(n)
    else:
        top = values.nlargest(n)

    return float(safe_ratio(float(top.sum()), total))


def top_1_share(
    df: pd.DataFrame,
    value_col: str,
    *,
    already_sorted: bool = False,
) -> float:
    """Share of total held by the single largest row."""

    return top_n_share(
        df,
        value_col,
        n=1,
        already_sorted=already_sorted,
    )


def concentration_summary(
    df: pd.DataFrame,
    value_col: str,
    *,
    n: int = 10,
    already_sorted: bool = False,
) -> dict:
    """
    Structured concentration facts for insight / metric use.

    Returns fractions (0–1) for shares.
    """

    if df.empty or value_col not in df.columns:
        return {
            "entity_count": 0,
            "total": 0.0,
            "top_n": n,
            "top_n_share": 0.0,
            "top_1_share": 0.0,
            "top_n_value": 0.0,
            "top_1_value": 0.0,
        }

    values = pd.to_numeric(
        df[value_col],
        errors="coerce",
    ).fillna(0.0)

    if already_sorted:
        ordered = values
    else:
        ordered = values.sort_values(ascending=False)

    total = float(ordered.sum())
    top_n_value = float(ordered.head(n).sum())
    top_1_value = float(ordered.iloc[0]) if len(ordered) else 0.0

    return {
        "entity_count": int(len(ordered)),
        "total": total,
        "top_n": n,
        "top_n_share": float(
            safe_ratio(top_n_value, total)
        ),
        "top_1_share": float(
            safe_ratio(top_1_value, total)
        ),
        "top_n_value": top_n_value,
        "top_1_value": top_1_value,
    }
