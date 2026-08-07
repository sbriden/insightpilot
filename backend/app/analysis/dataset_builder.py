import pandas as pd


class DatasetBuilder:

    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe

    def group_sum(
        self,
        dimension: str,
        measure: str,
        output_name="value",
    ):

        return (
            self.df
            .groupby(dimension)
            .agg(**{
                output_name: (
                    measure,
                    "sum",
                )
            })
            .reset_index()
            .sort_values(
                output_name,
                ascending=False,
            )
        )

    def group_count(
        self,
        dimension: str,
        output_name="count",
    ):

        return (
            self.df
            .groupby(dimension)
            .size()
            .reset_index(name=output_name)
            .sort_values(
                output_name,
                ascending=False,
            )
        )

    def group_metrics(
        self,
        dimension,
        metrics,
        sort_by=None,
        ascending=False,
    ):
        result = (
            self.df
            .groupby(dimension)
            .agg(**metrics)
            .reset_index()
        )

        if sort_by:
            result = result.sort_values(
                sort_by,
                ascending=ascending,
            )

        return result

    def group_average(
        self,
        dimension,
        measure,
        output_name="average",
    ):

        return (
            self.df
            .groupby(dimension)[measure]
            .mean()
            .reset_index(name=output_name)
        )


    def top_n(
        self,
        dataset: pd.DataFrame,
        n=10,
    ):

        return dataset.head(n)

    def bottom_n(
        self,
        df,
        n=10,
        sort_column="value",
    ):

        return (
            df
            .sort_values(
                sort_column,
                ascending=True,
            )
            .head(n)
        )

    def distribution(
        self,
        column: str,
    ):

        return self.df[[column]].copy()

    def scatter(
        self,
        x: str,
        y: str,
    ):

        return self.df[[x, y]].copy()

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
            df.groupby(
                pd.Grouper(
                    key=date_column,
                    freq=frequency,
                )
            )[measure]
            .sum()
            .reset_index()
        )