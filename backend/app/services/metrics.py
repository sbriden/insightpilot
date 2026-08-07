import pandas as pd
from pandas.api.types import is_numeric_dtype


def calculate_dataset_metrics(df: pd.DataFrame) -> dict:
    """Calculate overall dataset metrics."""

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "duplicates": int(df.duplicated().sum()),
        "missing_cells": int(df.isnull().sum().sum()),
        "missing_percentage": round(
            (df.isnull().sum().sum() / (df.shape[0] * df.shape[1])) * 100,
            2,
        )
        if df.shape[0] * df.shape[1] > 0
        else 0,
    }


def calculate_numeric_metrics(df: pd.DataFrame) -> dict:
    """Calculate metrics for numeric columns."""

    metrics = {}

    numeric_df = df.select_dtypes(include="number")

    for column in numeric_df.columns:
        series = numeric_df[column].dropna()

        metrics[column] = {
            "count": int(series.count()),
            "sum": float(series.sum()),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "min": float(series.min()),
            "max": float(series.max()),
            "std": (
                float(series.std())
                if series.count() > 1
                else 0.0
            ),
            "missing": int(df[column].isna().sum()),
            "zeros": int((series == 0).sum()),
            "negative_values": int((series < 0).sum()),
        }

    return metrics


def calculate_categorical_metrics(df: pd.DataFrame) -> dict:
    """Calculate metrics for categorical columns."""

    metrics = {}

    categorical_df = df.select_dtypes(include=["object", "category", "bool"])

    for column in categorical_df.columns:
        series = categorical_df[column].fillna("NULL")

        metrics[column] = {
            "count": int(series.count()),
            "unique_values": int(series.nunique()),
            "missing": int(df[column].isna().sum()),
            "top_values": (
                series.value_counts()
                .head(10)
                .to_dict()
            ),
        }

    return metrics


def calculate_date_metrics(df: pd.DataFrame) -> dict:
    """Attempt to detect date columns and calculate date metrics."""

    metrics = {}

    for column in df.columns:

        # Skip numeric columns
        if is_numeric_dtype(df[column]):
            continue

        try:
            dates = pd.to_datetime(
                df[column],
                format="mixed",
                errors="coerce",
            ).dropna()

            if dates.empty:
                continue

            metrics[column] = {
                "earliest": str(dates.min()),
                "latest": str(dates.max()),
                "unique_dates": int(dates.nunique()),
                "timespan_days": int(
                    (dates.max() - dates.min()).days
                ),
            }

        except Exception:
            # Not a date column
            continue

    return metrics


def generate_metrics(df: pd.DataFrame) -> dict:
    """
    Generate business metrics for a dataset.
    This becomes the structured analytical layer used by
    the dashboard, recommendations engine, and AI.
    """

    return {
        "dataset": calculate_dataset_metrics(df),
        "numeric": calculate_numeric_metrics(df),
        "categorical": calculate_categorical_metrics(df),
        "dates": calculate_date_metrics(df),
    }