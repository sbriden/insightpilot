import pandas as pd


def profile_dataframe(df: pd.DataFrame):

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = df.select_dtypes(
        include="object"
    ).columns.tolist()

    missing = df.isnull().sum()

    total_cells = df.shape[0] * df.shape[1]

    missing_cells = missing.sum()

    data_quality_score = round(
        ((total_cells - missing_cells) / total_cells) * 100,
        1
    )


    return {
        "summary": {
            "rows": len(df),
            "columns": len(df.columns),
            "data_quality_score": data_quality_score
        },

        "columns": {
            "names": list(df.columns),
            "numeric": numeric_columns,
            "categorical": categorical_columns
        },

        "missing_values": missing.to_dict(),

        "statistics": (
            df[numeric_columns]
            .describe()
            .to_dict()
            if numeric_columns
            else {}
        )
    }