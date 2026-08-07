import pandas as pd


IDENTIFIER_KEYWORDS = [
    "id",
    "key",
    "number",
    "code",
]


DATE_KEYWORDS = [
    "date",
    "time",
    "month",
    "year",
]


def profile_columns(
    df: pd.DataFrame,
) -> list[dict]:

    profiles = []

    for column in df.columns:

        series = df[column]

        profiles.append(
            {
                "name": column,
                "role": classify_column(
                    column,
                    series,
                ),
                "unique_count": int(
                    series.nunique()
                ),
                "null_count": int(
                    series.isna().sum()
                ),
                "data_type": str(
                    series.dtype
                ),
            }
        )

    return profiles



def classify_column(column, series):

    name = column.lower()

    if any(k in name for k in IDENTIFIER_KEYWORDS):
        return "identifier"

    if any(k in name for k in DATE_KEYWORDS):
        return "date"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    if pd.api.types.is_numeric_dtype(series):

        unique_ratio = series.nunique() / max(len(series), 1)

        if unique_ratio > 0.95:
            return "identifier"

        return "measure"

    if (
        pd.api.types.is_object_dtype(series)
        or
        pd.api.types.is_string_dtype(series)
    ):
        return "dimension"

    return "text"