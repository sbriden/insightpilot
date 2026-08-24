from .models import DataProductDefinition


DATA_PRODUCT_DEFINITIONS = [

    # -----------------------------------------------------------------------
    # Customer Intelligence
    # -----------------------------------------------------------------------

    DataProductDefinition(

        id="customer_intelligence",

        name="Customer Intelligence",

        description=(
            "Understand customer concentration, "
            "growth, profitability, retention, "
            "and cross-sell opportunities."
        ),

        dataset_types=[
            "sales",
        ],

        grain=(
            "Customer × Product × Date"
        ),

        required_fields=[
            "customer_id",
            "revenue",
            "product_id",
            "transaction_date",
        ],

        optional_fields=[
            "customer_name",
            "customer_segment",
            "cost",
            "sales_rep",
        ],

        analyses=[
            "customer_concentration",
            "customer_growth",
            "cross_sell",
            "customer_profitability",
            "sales_rep_performance",
        ],

    ),


    # -----------------------------------------------------------------------
    # Product Performance
    # -----------------------------------------------------------------------

    DataProductDefinition(

        id="product_performance",

        name="Product Performance",

        description=(
            "Understand product revenue, "
            "volume, growth, profitability, "
            "and product mix."
        ),

        dataset_types=[
            "sales",
        ],

        grain=(
            "Product × Date"
        ),

        required_fields=[
            "product_id",
            "revenue",
            "transaction_date",
        ],

        optional_fields=[
            "product_name",
            "product_category",
            "quantity",
            "cost",
            "customer_id",
        ],

        analyses=[
            "product_performance",
            "product_growth",
            "product_mix",
            "product_profitability",
            "customer_product_mix",
        ],

    ),


    # -----------------------------------------------------------------------
    # Sales Performance
    # -----------------------------------------------------------------------

    DataProductDefinition(

        id="sales_performance",

        name="Sales Performance",

        description=(
            "Analyze revenue trends, sales activity, "
            "sales representatives, regions, "
            "and overall sales performance."
        ),

        dataset_types=[
            "sales",
        ],

        grain=(
            "Transaction"
        ),

        required_fields=[
            "transaction_date",
            "revenue",
        ],

        optional_fields=[
            "customer_id",
            "product_id",
            "sales_rep",
            "region",
            "quantity",
            "cost",
        ],

        analyses=[
            "sales_trends",
            "sales_performance",
            "sales_rep_performance",
            "regional_performance",
            "sales_profitability",
        ],

    ),

]


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

DATA_PRODUCT_CATALOG = DATA_PRODUCT_DEFINITIONS


# ---------------------------------------------------------------------------
# Product lookup functions
# ---------------------------------------------------------------------------

def get_product_definitions():
    """
    Return all available data product definitions.
    """

    return DATA_PRODUCT_DEFINITIONS


def get_product_definition(
    product_id: str,
):
    """
    Return a single product definition by ID.
    """

    for product in DATA_PRODUCT_DEFINITIONS:

        if product.id == product_id:
            return product

    return None


def get_products_for_dataset_type(
    dataset_type_id: str,
):
    """
    Return all data products supported by
    a given dataset type.
    """

    return [
        product
        for product in DATA_PRODUCT_DEFINITIONS
        if dataset_type_id in product.dataset_types
    ]


# ---------------------------------------------------------------------------
# Semantic field catalog
# ---------------------------------------------------------------------------

def get_fields_for_dataset_type(
    dataset_type_id: str,
):
    """
    Return the complete set of semantic fields
    used by all data products associated with
    the specified dataset type.

    Fields are returned once only, even when the
    same field is used by multiple products.

    Required fields are returned before optional
    fields.
    """

    products = get_products_for_dataset_type(
        dataset_type_id
    )

    required_fields = []
    optional_fields = []

    for product in products:

        for field in (
            product.required_fields or []
        ):

            if field not in required_fields:
                required_fields.append(
                    field
                )

        for field in (
            product.optional_fields or []
        ):

            if (
                field not in required_fields
                and field not in optional_fields
            ):

                optional_fields.append(
                    field
                )

    return (
        required_fields
        + optional_fields
    )