import pandas as pd


class DatasetBuilder:

    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe

    # ============================================================
    # GROUP OPERATIONS
    # ============================================================

    def group_metrics(
        self,
        dimension,
        metrics,
        sort_by=None,
        ascending=False,
    ):
        """
        Group the dataframe by one or more dimensions
        and calculate the requested metrics.

        dimension can be either:

            "customer"

        or:

            ["customer", "product"]

        metrics should be a dictionary such as:

            {
                "revenue": ("sales", "sum"),
                "orders": ("sales", "count"),
            }
        """

        # --------------------------------------------------
        # Normalize dimensions
        # --------------------------------------------------

        if isinstance(dimension, str):
            dimensions = [dimension]

        elif isinstance(dimension, (list, tuple)):
            dimensions = list(dimension)

        else:
            dimensions = [dimension]


        # --------------------------------------------------
        # Validate dimensions
        # --------------------------------------------------

        dimensions = [
            column
            for column in dimensions
            if isinstance(column, str)
            and column in self.df.columns
        ]


        if not dimensions:
            return pd.DataFrame()


        # --------------------------------------------------
        # Build aggregation dictionary
        # --------------------------------------------------

        aggregations = {}

        for metric_name, metric_definition in metrics.items():

            if not metric_definition:
                continue

            column, operation = metric_definition

            if column not in self.df.columns:
                continue

            aggregations[metric_name] = (
                column,
                operation,
            )


        # --------------------------------------------------
        # Nothing to aggregate
        # --------------------------------------------------

        if not aggregations:

            return (
                self.df[
                    dimensions
                ]
                .drop_duplicates()
                .reset_index(drop=True)
            )


        # --------------------------------------------------
        # Group and aggregate
        # --------------------------------------------------

        result = (
            self.df
            .groupby(
                dimensions,
                dropna=False,
            )
            .agg(**aggregations)
            .reset_index()
        )


        # --------------------------------------------------
        # Sort
        # --------------------------------------------------

        if (
            sort_by
            and sort_by in result.columns
        ):

            result = (
                result
                .sort_values(
                    by=sort_by,
                    ascending=ascending,
                )
                .reset_index(drop=True)
            )


        return result

    # ============================================================
    # DATASET OPERATIONS
    # ============================================================

    def filter(
        self,
        dataset: pd.DataFrame,
        predicate,
    ):

        if dataset.empty:
            return dataset.copy()

        return dataset[
            predicate(dataset)
        ].copy()

    def sort(
        self,
        dataset: pd.DataFrame,
        column: str,
        ascending=False,
    ):

        if (
            dataset.empty
            or column not in dataset.columns
        ):
            return dataset.copy()

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

        if (
            dataset.empty
            or column not in dataset.columns
        ):
            return dataset.copy()

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

        valid_columns = [
            column
            for column in columns
            if column in dataset.columns
        ]

        return dataset[
            valid_columns
        ].copy()

    def add_calculated_column(
        self,
        dataset: pd.DataFrame,
        column_name: str,
        calculation,
    ):

        dataset = dataset.copy()

        dataset[column_name] = calculation(
            dataset
        )

        return dataset

    # ============================================================
    # VISUALIZATION DATASETS
    # ============================================================

    def scatter(
        self,
        x: str,
        y: str,
    ):

        if (
            x not in self.df.columns
            or y not in self.df.columns
        ):
            return pd.DataFrame()

        return self.df[
            [x, y]
        ].copy()

    def distribution(
        self,
        column: str,
    ):

        if column not in self.df.columns:
            return pd.DataFrame()

        return self.df[
            [column]
        ].copy()

    def time_series(
        self,
        date_column: str,
        measure: str,
        frequency="M",
    ):

        if (
            date_column not in self.df.columns
            or measure not in self.df.columns
        ):
            return pd.DataFrame()

        df = self.df.copy()

        df[date_column] = pd.to_datetime(
            df[date_column],
            errors="coerce",
        )

        df = df.dropna(
            subset=[date_column]
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

    # ============================================================
    # CUSTOMER / PRODUCT ANALYSIS
    # ============================================================

    def product_affinity(
        self,
        customer_column: str,
        product_column: str,
        min_customers: int = 2,
    ):

        customer_products = (
            self.df[
                [
                    customer_column,
                    product_column,
                ]
            ]
            .dropna()
            .drop_duplicates()
        )

        if customer_products.empty:
            return pd.DataFrame(
                columns=[
                    "product_a",
                    "product_b",
                    "customers_a",
                    "customers_b",
                    "overlap_customers",
                    "support",
                    "confidence_a_to_b",
                    "confidence_b_to_a",
                ]
            )

        total_customers = (
            customer_products[
                customer_column
            ]
            .nunique()
        )

        if total_customers == 0:
            return pd.DataFrame()

        product_customers = (
            customer_products
            .groupby(product_column)[customer_column]
            .apply(set)
            .to_dict()
        )

        products = list(
            product_customers.keys()
        )

        results = []

        for i, product_a in enumerate(products):

            customers_a = (
                product_customers[
                    product_a
                ]
            )

            if len(customers_a) < min_customers:
                continue

            for product_b in products[i + 1:]:

                customers_b = (
                    product_customers[
                        product_b
                    ]
                )

                if len(customers_b) < min_customers:
                    continue

                overlap = (
                    customers_a
                    & customers_b
                )

                overlap_count = len(
                    overlap
                )

                if overlap_count == 0:
                    continue

                support = (
                    overlap_count
                    / total_customers
                )

                confidence_a_to_b = (
                    overlap_count
                    / len(customers_a)
                )

                confidence_b_to_a = (
                    overlap_count
                    / len(customers_b)
                )

                results.append(
                    {
                        "product_a": product_a,
                        "product_b": product_b,
                        "customers_a": len(customers_a),
                        "customers_b": len(customers_b),
                        "overlap_customers": overlap_count,
                        "support": support,
                        "confidence_a_to_b": confidence_a_to_b,
                        "confidence_b_to_a": confidence_b_to_a,
                    }
                )

        columns = [
            "product_a",
            "product_b",
            "customers_a",
            "customers_b",
            "overlap_customers",
            "support",
            "confidence_a_to_b",
            "confidence_b_to_a",
        ]

        return pd.DataFrame(
            results,
            columns=columns,
        )

    def customer_product_penetration(
        self,
        customer_column: str,
        product_column: str,
    ):

        customer_product = (
            self.df[
                [
                    customer_column,
                    product_column,
                ]
            ]
            .dropna()
            .drop_duplicates()
        )

        total_products = (
            customer_product[
                product_column
            ]
            .nunique()
        )

        if total_products == 0:
            return pd.DataFrame()

        result = (
            customer_product
            .groupby(customer_column)
            [product_column]
            .nunique()
            .reset_index(
                name="products_purchased"
            )
        )

        result["total_products"] = (
            total_products
        )

        result["product_penetration"] = (
            result["products_purchased"]
            / total_products
        )

        return result