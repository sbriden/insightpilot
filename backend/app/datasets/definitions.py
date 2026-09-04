from .models import DatasetTypeDefinition


DATASET_TYPES = [

    DatasetTypeDefinition(
        id="sales",
        name="Sales",
        description=(
            "Revenue, transactions, customers, "
            "products and sales performance."
        ),
        keywords=[
            "sale",
            "sales",
            "transaction",
            "order",
            "revenue",
            "invoice",
            "customer",
            "product",
        ],
        example_fields=[
            "customer_id",
            "product_id",
            "transaction_date",
            "order_date",
            "revenue",
            "sales_amount",
            "quantity",
        ],
        product_ids=[
            "customer_intelligence",
        ],
    ),

    DatasetTypeDefinition(
        id="customer",
        name="Customer",
        description=(
            "Customer attributes, value, behavior, "
            "retention and engagement."
        ),
        keywords=[
            "customer",
            "client",
            "account",
            "member",
            "subscriber",
            "customer_id",
        ],
        example_fields=[
            "customer_id",
            "customer_name",
            "customer_type",
            "segment",
            "created_date",
            "status",
            "lifetime_value",
        ],
        product_ids=[
            "customer_intelligence",
        ],
    ),

    DatasetTypeDefinition(
        id="finance",
        name="Finance",
        description=(
            "Revenue, expenses, profitability and "
            "financial performance."
        ),
        keywords=[
            "revenue",
            "expense",
            "cost",
            "profit",
            "margin",
            "budget",
            "actual",
            "financial",
        ],
        example_fields=[
            "account_id",
            "account",
            "date",
            "revenue",
            "expense",
            "cost",
            "profit",
            "margin",
        ],
        product_ids=[],
    ),

    DatasetTypeDefinition(
        id="marketing",
        name="Marketing",
        description=(
            "Campaigns, leads, conversions and "
            "marketing performance."
        ),
        keywords=[
            "campaign",
            "lead",
            "marketing",
            "conversion",
            "impression",
            "click",
            "channel",
        ],
        example_fields=[
            "campaign_id",
            "campaign_name",
            "lead_id",
            "channel",
            "impressions",
            "clicks",
            "conversions",
            "spend",
        ],
        product_ids=[],
    ),

    DatasetTypeDefinition(
        id="operations",
        name="Operations",
        description=(
            "Operational activity, productivity, "
            "processes and performance."
        ),
        keywords=[
            "operation",
            "operations",
            "process",
            "activity",
            "production",
            "productivity",
            "work_order",
        ],
        example_fields=[
            "transaction_id",
            "activity_date",
            "process",
            "status",
            "duration",
            "quantity",
            "employee_id",
        ],
        product_ids=[],
    ),

    DatasetTypeDefinition(
        id="workforce",
        name="Workforce",
        description=(
            "Employees, compensation, departments, "
            "roles and workforce performance."
        ),
        keywords=[
            "employee",
            "staff",
            "workforce",
            "salary",
            "wage",
            "compensation",
            "department",
            "hire",
            "hr",
        ],
        example_fields=[
            "employee_id",
            "employee_name",
            "department",
            "role",
            "hire_date",
            "salary",
            "status",
        ],
        product_ids=[],
    ),

]