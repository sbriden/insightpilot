import pandas as pd


class DatasetBuilder:

    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe

    # ============================================================
    # GROUP OPERATIONS
    # ============================================================

    def group_metrics(
        self,
        dimension: str,
        metrics: dict,
        sort_by: str | None = None,
        ascending: bool = False,
    ):

        dataset = (
            self.df
            .groupby(dimension)
            .agg(**metrics)
            .reset_index()
        )

        if sort_by:
            dataset = dataset.sort_values(
                sort_by,
                ascending=ascending,
            )

        return dataset

    # ============================================================
    # DATASET OPERATIONS
    # ============================================================

    def filter(
        self,
        dataset: pd.DataFrame,
        predicate,
    ):

        return dataset[
            predicate(dataset)
        ].copy()

    def sort(
        self,
        dataset: pd.DataFrame,
        column: str,
        ascending=False,
    ):

        return dataset.sort_values(
            column,
            ascending=ascending,
        )

    def top_n(
        self,
        dataset: pd.DataFrame,
        n=10,
    ):

        return dataset.head(n)

    def bottom_n(
        self,
        dataset: pd.DataFrame,
        column: str,
        n=10,
    ):

        return (
            dataset
            .sort_values(
                column,
                ascending=True,
            )
            .head(n)
        )

    def select(
        self,
        dataset: pd.DataFrame,
        columns: list[str],
    ):

        return dataset[
            columns
        ].copy()

    def add_calculated_column(
        self,
        dataset: pd.DataFrame,
        column_name: str,
        calculation,
    ):

        dataset = dataset.copy()

        dataset[column_name] = calculation(dataset)

        return dataset

    # ============================================================
    # VISUALIZATION DATASETS
    # ============================================================

    def scatter(
        self,
        x: str,
        y: str,
    ):

        return self.df[
            [x, y]
        ].copy()

    def distribution(
        self,
        column: str,
    ):

        return self.df[
            [column]
        ].copy()

    def time_series(
        self,
        date_column: str,
        measure: str,
        frequency="M",
    ):

        df = self.df.copy()

        df[date_column] = pd.to_datetime(
            df[date_column]
        )

        return (
            df
            .groupby(
                pd.Grouper(
                    key=date_column,
                    freq=frequency,
                )
            )[measure]
            .sum()
            .reset_index()
        )