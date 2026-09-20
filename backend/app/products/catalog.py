from .models import (
    DataProductDefinition,
    FieldOpportunity,
    PRODUCT_TYPE_NATIVE,
    PRODUCT_TYPE_USER_CREATED,
    _LEGACY_PRE_CANNED,
)


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
            "customer_performance",
        ],

        field_opportunities=[

            FieldOpportunity(
                field="customer_id",
                description=(
                    "Identifies each customer so "
                    "concentration, growth, and "
                    "performance can be attributed."
                ),
                analyses=[
                    "customer_concentration",
                    "customer_growth",
                    "cross_sell",
                    "customer_performance",
                ],
                metrics=[
                    "Customer count",
                    "Revenue by customer",
                    "Concentration risk",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="revenue",
                description=(
                    "Provides the value measure for "
                    "customer ranking and growth."
                ),
                analyses=[
                    "customer_concentration",
                    "customer_growth",
                    "customer_performance",
                ],
                metrics=[
                    "Total revenue",
                    "Average revenue per customer",
                    "Growth rate",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="product_id",
                description=(
                    "Enables product mix and "
                    "cross-sell pairing by customer."
                ),
                analyses=[
                    "cross_sell",
                    "customer_performance",
                ],
                metrics=[
                    "Products per customer",
                    "Cross-sell opportunities",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="transaction_date",
                description=(
                    "Supports trend and growth "
                    "analysis over time."
                ),
                analyses=[
                    "customer_growth",
                ],
                metrics=[
                    "Period-over-period growth",
                    "Revenue trend",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="customer_name",
                description=(
                    "Replaces opaque IDs with "
                    "readable customer labels."
                ),
                analyses=[
                    "customer_concentration",
                    "customer_performance",
                ],
                metrics=[
                    "Named customer leaderboard",
                ],
                priority="low",
            ),

            FieldOpportunity(
                field="customer_segment",
                description=(
                    "Unlocks segment-level "
                    "comparisons and targeting."
                ),
                analyses=[
                    "customer_performance",
                    "customer_concentration",
                ],
                metrics=[
                    "Revenue by segment",
                    "Segment concentration",
                ],
                priority="medium",
            ),

            FieldOpportunity(
                field="cost",
                description=(
                    "Enables margin and "
                    "profitability by customer."
                ),
                analyses=[
                    "customer_performance",
                ],
                metrics=[
                    "Gross margin",
                    "Profit by customer",
                ],
                priority="high",
            ),

            FieldOpportunity(
                field="sales_rep",
                description=(
                    "Attributes customer results "
                    "to sales ownership."
                ),
                analyses=[
                    "customer_performance",
                ],
                metrics=[
                    "Revenue by sales rep",
                    "Customer ownership",
                ],
                priority="medium",
            ),

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
            "customer_product",
            "profitability",
        ],

        field_opportunities=[

            FieldOpportunity(
                field="product_id",
                description=(
                    "Required to measure performance "
                    "at the product level."
                ),
                analyses=[
                    "product_performance",
                    "customer_product",
                    "profitability",
                ],
                metrics=[
                    "Revenue by product",
                    "Product ranking",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="revenue",
                description=(
                    "Core value measure for product "
                    "and profitability analysis."
                ),
                analyses=[
                    "product_performance",
                    "profitability",
                ],
                metrics=[
                    "Total revenue",
                    "Revenue mix",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="transaction_date",
                description=(
                    "Unlocks product growth and "
                    "trend views over time."
                ),
                analyses=[
                    "product_performance",
                ],
                metrics=[
                    "Product growth",
                    "Period trends",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="product_name",
                description=(
                    "Makes product reports readable "
                    "without relying on IDs."
                ),
                analyses=[
                    "product_performance",
                ],
                metrics=[
                    "Named product leaderboard",
                ],
                priority="low",
            ),

            FieldOpportunity(
                field="product_category",
                description=(
                    "Unlocks category mix and "
                    "category profitability."
                ),
                analyses=[
                    "product_performance",
                    "profitability",
                ],
                metrics=[
                    "Revenue by category",
                    "Category margin",
                ],
                priority="medium",
            ),

            FieldOpportunity(
                field="quantity",
                description=(
                    "Adds volume metrics alongside "
                    "revenue."
                ),
                analyses=[
                    "product_performance",
                ],
                metrics=[
                    "Units sold",
                    "Average selling price",
                ],
                priority="medium",
            ),

            FieldOpportunity(
                field="cost",
                description=(
                    "Unlocks profitability and "
                    "margin analysis."
                ),
                analyses=[
                    "profitability",
                ],
                metrics=[
                    "Gross profit",
                    "Margin %",
                ],
                priority="high",
            ),

            FieldOpportunity(
                field="customer_id",
                description=(
                    "Unlocks customer × product "
                    "relationship analysis."
                ),
                analyses=[
                    "customer_product",
                ],
                metrics=[
                    "Customers per product",
                    "Product attachment",
                ],
                priority="high",
            ),

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
            "revenue_trends",
            "profit_improvement",
        ],

        field_opportunities=[

            FieldOpportunity(
                field="transaction_date",
                description=(
                    "Required for revenue trend "
                    "and period comparisons."
                ),
                analyses=[
                    "revenue_trends",
                ],
                metrics=[
                    "Revenue over time",
                    "Period growth",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="revenue",
                description=(
                    "Core sales value measure for "
                    "trends and opportunity sizing."
                ),
                analyses=[
                    "revenue_trends",
                    "profit_improvement",
                ],
                metrics=[
                    "Total revenue",
                    "Trend slope",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="customer_id",
                description=(
                    "Adds customer dimension to "
                    "sales activity views."
                ),
                analyses=[
                    "revenue_trends",
                ],
                metrics=[
                    "Active customers",
                    "Revenue by customer",
                ],
                priority="medium",
            ),

            FieldOpportunity(
                field="product_id",
                description=(
                    "Unlocks product-level sales "
                    "and profit improvement views."
                ),
                analyses=[
                    "profit_improvement",
                    "revenue_trends",
                ],
                metrics=[
                    "Revenue by product",
                    "Improvement opportunities",
                ],
                priority="high",
            ),

            FieldOpportunity(
                field="sales_rep",
                description=(
                    "Attributes sales performance "
                    "to individual reps."
                ),
                analyses=[
                    "revenue_trends",
                ],
                metrics=[
                    "Revenue by sales rep",
                    "Rep productivity",
                ],
                priority="medium",
            ),

            FieldOpportunity(
                field="region",
                description=(
                    "Unlocks geographic sales "
                    "breakdowns."
                ),
                analyses=[
                    "revenue_trends",
                ],
                metrics=[
                    "Revenue by region",
                    "Regional growth",
                ],
                priority="medium",
            ),

            FieldOpportunity(
                field="quantity",
                description=(
                    "Adds volume context to "
                    "revenue trends."
                ),
                analyses=[
                    "revenue_trends",
                ],
                metrics=[
                    "Units sold",
                    "Average order size",
                ],
                priority="low",
            ),

            FieldOpportunity(
                field="cost",
                description=(
                    "Unlocks profit improvement "
                    "and margin opportunity sizing."
                ),
                analyses=[
                    "profit_improvement",
                ],
                metrics=[
                    "Gross profit",
                    "Margin opportunity",
                ],
                priority="high",
            ),

        ],

    ),

    # -----------------------------------------------------------------------
    # Fantasy Football
    # -----------------------------------------------------------------------

    DataProductDefinition(

        id="fantasy_football",

        name="Fantasy Football",

        description=(
            "Actionable fantasy football insights from "
            "nflverse-backed signals — breakout candidates, "
            "buy-low / sell-high, start/sit, and opportunity shifts."
        ),

        product_type=PRODUCT_TYPE_NATIVE,

        dataset_types=[
            "fantasy_football",
        ],

        grain=(
            "Player × Week (fantasy signal)"
        ),

        required_fields=[
            "player_id",
            "season",
            "week",
            "signal_type",
            "signal_strength",
        ],

        optional_fields=[
            "confidence",
            "direction",
            "player_name",
            "position",
            "team_id",
        ],

        analyses=[
            "player_overview",
            "daily_fantasy",
        ],

        field_opportunities=[

            FieldOpportunity(
                field="player_id",
                description=(
                    "Identifies each player so signals "
                    "and insights can be attributed."
                ),
                analyses=[
                    "player_overview",
                ],
                metrics=[
                    "Eligible signals",
                    "Findings by player",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="season",
                description=(
                    "Scopes signals to an NFL season."
                ),
                analyses=[
                    "player_overview",
                ],
                metrics=[
                    "Season coverage",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="week",
                description=(
                    "Anchors weekly start/sit and "
                    "waiver decisions."
                ),
                analyses=[
                    "player_overview",
                ],
                metrics=[
                    "Week coverage",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="signal_type",
                description=(
                    "SME signal taxonomy (breakout, "
                    "buy-low, start/sit, etc.)."
                ),
                analyses=[
                    "player_overview",
                ],
                metrics=[
                    "Signals by type",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="signal_strength",
                description=(
                    "Strength score used for materiality "
                    "and ranking of fantasy insights."
                ),
                analyses=[
                    "player_overview",
                ],
                metrics=[
                    "Top signal strength",
                    "Eligible signals",
                ],
                priority="high",
                required=True,
            ),

            FieldOpportunity(
                field="confidence",
                description=(
                    "Confidence gate for promoting "
                    "signals to insights."
                ),
                analyses=[
                    "player_overview",
                ],
                metrics=[
                    "Average confidence",
                ],
                priority="medium",
                required=False,
            ),

        ],

    ),

]


# Product-facing analysis id → executable analysis module ids.
PRODUCT_ANALYSIS_MODULES: dict[str, tuple[str, ...]] = {
    "player_overview": ("fantasy_signals",),
    # UI/API-driven; no executable dashboard module yet.
    "daily_fantasy": (),
}

PRODUCT_ANALYSIS_META: dict[str, dict[str, str]] = {
    "player_overview": {
        "title": "Player Overview",
        "description": (
            "Analyze a player's performance, usage, "
            "trends and fantasy outlook."
        ),
    },
    "daily_fantasy": {
        "title": "Daily Fantasy",
        "description": (
            "Analyze today's slate, identify the strongest "
            "DFS opportunities, and build optimized lineups."
        ),
    },
}


def expand_to_module_ids(
    analysis_ids: list[str] | tuple[str, ...] | set[str],
) -> set[str]:
    """
    Expand product-facing analysis ids to executable
    module ids. Unknown ids pass through unchanged.
    """

    modules: set[str] = set()

    for analysis_id in analysis_ids:
        if analysis_id in PRODUCT_ANALYSIS_MODULES:
            modules.update(
                PRODUCT_ANALYSIS_MODULES[analysis_id]
            )
        else:
            modules.add(analysis_id)

    return modules


def product_analysis_title(
    analysis_id: str,
) -> str:
    meta = PRODUCT_ANALYSIS_META.get(analysis_id)
    if meta and meta.get("title"):
        return meta["title"]
    return analysis_id.replace("_", " ").title()


def product_analysis_description(
    analysis_id: str,
) -> str:
    meta = PRODUCT_ANALYSIS_META.get(analysis_id)
    if meta:
        return meta.get("description", "")
    return ""


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


def resolve_product_type(
    definition_id: str | None,
    stored: str | None = None,
) -> str:
    """
    Resolve product_type for an instance.

    Prefer a persisted value; otherwise look up
    the catalog definition; default to user_created.
    """

    if stored in (
        PRODUCT_TYPE_USER_CREATED,
        PRODUCT_TYPE_NATIVE,
    ):
        return stored

    if stored == _LEGACY_PRE_CANNED:
        return PRODUCT_TYPE_NATIVE

    if definition_id:
        definition = get_product_definition(
            definition_id
        )
        if definition is not None:
            return (
                definition.product_type
                or PRODUCT_TYPE_USER_CREATED
            )

    return PRODUCT_TYPE_USER_CREATED


def get_analysis_ids_for_products(
    product_ids: list[str] | None,
) -> set[str] | None:
    """
    Return the analysis module IDs owned by the
    selected products.

    None means no selection was supplied and
    every registered module may run.
    """

    if product_ids is None:
        return None

    analysis_ids: set[str] = set()

    for product_id in product_ids:

        definition = get_product_definition(
            str(product_id).strip()
        )

        if definition is None:
            continue

        analysis_ids.update(
            expand_to_module_ids(
                definition.analyses or []
            )
        )

    return analysis_ids


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


def serialize_field_opportunity(
    opportunity: FieldOpportunity,
) -> dict:

    return {
        "field": opportunity.field,

        "description": (
            opportunity.description
        ),

        "analyses": list(
            opportunity.analyses or []
        ),

        "metrics": list(
            opportunity.metrics or []
        ),

        "priority": opportunity.priority,

        "required": opportunity.required,
    }


def serialize_product_definition(
    product: DataProductDefinition,
) -> dict:
    """
    Serialize a catalog definition for API clients.
    """

    return {
        "id": product.id,

        "name": product.name,

        "description": product.description,

        "business_purpose": (
            product.business_purpose
        ),

        "product_type": (
            product.product_type
            or PRODUCT_TYPE_USER_CREATED
        ),

        "dataset_types": list(
            product.dataset_types or []
        ),

        "grain": product.grain,

        "required_fields": list(
            product.required_fields or []
        ),

        "optional_fields": list(
            product.optional_fields or []
        ),

        "analyses": list(
            product.analyses or []
        ),

        "field_opportunities": [
            serialize_field_opportunity(
                opportunity
            )
            for opportunity
            in (
                product.field_opportunities
                or []
            )
        ],
    }


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
