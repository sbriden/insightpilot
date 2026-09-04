"""
Tests for grain_detection.determine_dataset_grain.
"""

from __future__ import annotations

from app.datasets.grain_detection import determine_dataset_grain


def _col(
    source_column: str,
    concept: str,
    role: str,
    confidence: float = 0.90,
    data_type: str = "string",
) -> dict:
    return {
        "sourceColumn": source_column,
        "concept": concept,
        "role": role,
        "confidence": confidence,
        "dataType": data_type,
    }


# ── Transaction ───────────────────────────────────────────────


def test_transaction_grain_sales_fact():
    concepts = [
        _col("Order ID", "Transaction/Order", "identifier"),
        _col("Order Date", "Date", "date", data_type="date"),
        _col("Revenue", "Revenue", "measure", data_type="number"),
        _col("Product", "Product", "entity"),
        _col("Customer", "Customer", "entity"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "transaction"
    assert result["confidence"] >= 0.40
    assert result["supporting_evidence"]


def test_transaction_boosted_by_unique_order_id():
    concepts = [
        _col("Order ID", "Transaction/Order", "identifier"),
        _col("Product ID", "Product", "entity"),
        _col("Amount", "Revenue", "measure", data_type="number"),
    ]
    stats = [
        {
            "name": "Order ID",
            "unique_ratio": 0.99,
            "row_count": 1000,
            "unique_count": 990,
        }
    ]
    result = determine_dataset_grain(concepts, column_stats=stats)
    assert result["grain"] == "transaction"
    signals = [item["signal"] for item in result["supporting_evidence"]]
    assert "near_unique_identifier" in signals


# ── Invoice ───────────────────────────────────────────────────


def test_invoice_grain_from_invoice_columns():
    concepts = [
        _col("Invoice Number", "Transaction/Order", "identifier"),
        _col("Invoice Date", "Date", "date", data_type="date"),
        _col("Invoice Amount", "Revenue", "measure", data_type="number"),
        _col("Payment Date", "Date", "date", data_type="date"),
        _col("Payment Status", "Status", "status"),
        _col("Account", "Customer", "entity"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "invoice", (
        f"Expected invoice, got {result['grain']} "
        f"(confidence={result['confidence']}, all_scores={result['all_scores']})"
    )


# ── Customer / Subscription / Account ─────────────────────────


def test_customer_grain_without_lifecycle():
    concepts = [
        _col("Customer ID", "Customer", "identifier"),
        _col("Customer Name", "Customer", "entity"),
        _col("Region", "Geography", "geography"),
        _col("Signup Date", "Date", "date", data_type="date"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "customer"


def test_subscription_grain_with_plan_and_status():
    concepts = [
        _col("Customer ID", "Customer", "identifier"),
        _col("Plan", "Category", "category"),
        _col("Status", "Status", "status"),
        _col("MRR", "Revenue", "measure", data_type="number"),
        _col("Start Date", "Date", "date", data_type="date"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "subscription", (
        f"Expected subscription, got {result['grain']} "
        f"(confidence={result['confidence']}, all_scores={result['all_scores']})"
    )


def test_account_grain_from_account_naming():
    concepts = [
        _col("Account ID", "Customer", "identifier"),
        _col("Account Name", "Customer", "entity"),
        _col("Balance", "Revenue", "measure", data_type="number"),
        _col("Opened Date", "Date", "date", data_type="date"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "account", (
        f"Expected account, got {result['grain']} "
        f"(confidence={result['confidence']}, all_scores={result['all_scores']})"
    )


# ── Employee ──────────────────────────────────────────────────


def test_employee_grain():
    concepts = [
        _col("Employee ID", "Employee", "identifier"),
        _col("Department", "Category", "category"),
        _col("Salary", "Revenue", "measure", data_type="number"),
        _col("Hire Date", "Date", "date", data_type="date"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "employee"
    assert result["confidence"] > 0


# ── Product ───────────────────────────────────────────────────


def test_product_grain_catalog():
    concepts = [
        _col("Product ID", "Product", "identifier"),
        _col("SKU", "Product", "entity"),
        _col("Category", "Category", "category"),
        _col("List Price", "Revenue", "measure", data_type="number"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "product"


def test_product_not_chosen_when_transactions_present():
    concepts = [
        _col("Product ID", "Product", "entity"),
        _col("Order ID", "Transaction/Order", "identifier"),
        _col("Revenue", "Revenue", "measure", data_type="number"),
        _col("Customer ID", "Customer", "entity"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "transaction"


# ── Operational event ─────────────────────────────────────────


def test_operational_event_grain():
    concepts = [
        _col("Supplier", "Supplier", "entity"),
        _col("Order Qty", "Quantity", "measure", data_type="number"),
        _col("Delivery Status", "Status", "status"),
        _col("Ship Date", "Date", "date", data_type="date"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "operational_event", (
        f"Expected operational_event, got {result['grain']} "
        f"(confidence={result['confidence']}, all_scores={result['all_scores']})"
    )


def test_operational_event_from_event_naming():
    concepts = [
        _col("Event ID", "Transaction/Order", "identifier"),
        _col("Event Type", "Category", "category"),
        _col("Event Timestamp", "Date", "date", data_type="date"),
        _col("Status", "Status", "status"),
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "operational_event"


# ── Unknown ───────────────────────────────────────────────────


def test_unknown_when_no_signals():
    concepts = [
        {
            "sourceColumn": "col_a",
            "concept": "Unknown",
            "role": "category",
            "confidence": 0.35,
            "dataType": "string",
        },
        {
            "sourceColumn": "col_b",
            "concept": "Unknown",
            "role": "category",
            "confidence": 0.35,
            "dataType": "string",
        },
    ]
    result = determine_dataset_grain(concepts)
    assert result["grain"] == "unknown"
    assert result["confidence"] == 0.0


def test_low_uniqueness_customer_id_on_transactions_not_customer_grain():
    concepts = [
        _col("Customer ID", "Customer", "identifier"),
        _col("Order ID", "Transaction/Order", "identifier"),
        _col("Product", "Product", "entity"),
        _col("Revenue", "Revenue", "measure", data_type="number"),
    ]
    stats = [
        {
            "name": "Customer ID",
            "unique_ratio": 0.20,
            "row_count": 1000,
            "unique_count": 200,
        },
        {
            "name": "Order ID",
            "unique_ratio": 1.0,
            "row_count": 1000,
            "unique_count": 1000,
        },
    ]
    result = determine_dataset_grain(concepts, column_stats=stats)
    assert result["grain"] == "transaction"


# ── Response shape ────────────────────────────────────────────


def test_response_has_required_keys():
    concepts = [
        _col("Employee ID", "Employee", "identifier"),
        _col("Pay", "Revenue", "measure", data_type="number"),
    ]
    result = determine_dataset_grain(concepts)
    for key in (
        "grain",
        "label",
        "confidence",
        "supporting_evidence",
        "explanation",
        "alternative_grains",
        "all_scores",
    ):
        assert key in result, f"Missing key: {key}"

    assert isinstance(result["supporting_evidence"], list)
    assert isinstance(result["alternative_grains"], list)
    assert isinstance(result["all_scores"], list)
    assert len(result["all_scores"]) == 8
