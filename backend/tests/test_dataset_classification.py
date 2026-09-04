"""
Tests for dataset_classification.classify_dataset.

Each test builds a list of identified concepts (the same shape that
identify_business_concepts returns) and asserts on the primary archetype
and that confidence is non-zero.
"""

from __future__ import annotations

import pytest

from app.datasets.dataset_classification import classify_dataset


# ── helpers ──────────────────────────────────────────────────


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


# ── Sales / Revenue ──────────────────────────────────────────


def test_sales_revenue_basic():
    concepts = [
        _col("Order ID", "Transaction/Order", "entity"),
        _col("Order Date", "Date", "date", data_type="date"),
        _col("Revenue", "Revenue", "measure", data_type="number"),
        _col("Product", "Product", "entity"),
        _col("Customer", "Customer", "entity"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "sales_revenue"
    assert result["confidence"] > 0


def test_sales_not_finance_with_customer_product_and_dates():
    """
    Sales datasets often have multiple dates (order + ship) plus customer,
    product, and revenue. Those must not be classified as Finance.
    """
    concepts = [
        _col("Customer ID", "Customer", "entity"),
        _col("Product ID", "Product", "entity"),
        _col("Order ID", "Transaction/Order", "entity"),
        _col("Order Date", "Date", "date", data_type="date"),
        _col("Ship Date", "Date", "date", data_type="date"),
        _col("Revenue", "Revenue", "measure", data_type="number"),
        _col("Quantity", "Quantity", "measure", data_type="number"),
        _col("Order Status", "Status", "status"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "sales_revenue", (
        f"Expected sales_revenue, got {result['primary_archetype']} "
        f"(confidence={result['confidence']}, all_scores={result['all_scores']})"
    )


def test_sales_revenue_without_customer():
    """Transaction + Revenue alone is enough for sales."""
    concepts = [
        _col("Invoice #", "Transaction/Order", "entity"),
        _col("Amount", "Revenue", "measure", data_type="number"),
        _col("Sale Date", "Date", "date", data_type="date"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "sales_revenue"


# ── Finance ──────────────────────────────────────────────────


def test_finance_receivables():
    """
    Acceptance-criteria example: Account, Invoice Date, Invoice Amount,
    Payment Date, Payment Status → Finance / Receivables.
    """
    concepts = [
        _col("Account", "Customer", "entity"),
        _col("Invoice Date", "Date", "date", data_type="date"),
        _col("Invoice Amount", "Revenue", "measure", data_type="number"),
        _col("Payment Date", "Date", "date", data_type="date"),
        _col("Payment Status", "Status", "status"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "finance", (
        f"Expected finance, got {result['primary_archetype']} "
        f"(confidence={result['confidence']}, all_scores={result['all_scores']})"
    )
    assert result["confidence"] > 0


def test_finance_requires_status_or_multi_date():
    """Revenue alone with a single date should NOT be classified as Finance."""
    concepts = [
        _col("Amount", "Revenue", "measure", data_type="number"),
        _col("Date", "Date", "date", data_type="date"),
    ]
    result = classify_dataset(concepts)
    # Should NOT be finance (no status, no multi-date)
    assert result["primary_archetype"] != "finance"


# ── Customer / Subscription ───────────────────────────────────


def test_customer_subscription():
    concepts = [
        _col("Customer ID", "Customer", "entity"),
        _col("Plan", "Category", "category"),
        _col("Status", "Status", "status"),
        _col("MRR", "Revenue", "measure", data_type="number"),
        _col("Start Date", "Date", "date", data_type="date"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "customer"
    assert result["confidence"] > 0


def test_customer_no_transaction_required():
    """A customer dataset without any Transaction/Order concept."""
    concepts = [
        _col("Account", "Customer", "entity"),
        _col("Subscription Status", "Status", "status"),
        _col("Renewal Date", "Date", "date", data_type="date"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "customer"


# ── Operations ────────────────────────────────────────────────


def test_operations_with_supplier():
    concepts = [
        _col("Supplier", "Supplier", "entity"),
        _col("Order Qty", "Quantity", "measure", data_type="number"),
        _col("Delivery Status", "Status", "status"),
        _col("Ship Date", "Date", "date", data_type="date"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "operations"
    assert result["confidence"] > 0


def test_operations_units_and_status():
    concepts = [
        _col("Units Produced", "Quantity", "measure", data_type="number"),
        _col("Stage", "Status", "status"),
        _col("Week", "Date", "date", data_type="date"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "operations"


# ── Workforce ─────────────────────────────────────────────────


def test_workforce_basic():
    concepts = [
        _col("Employee ID", "Employee", "entity"),
        _col("Department", "Category", "category"),
        _col("Salary", "Revenue", "measure", data_type="number"),
        _col("Hire Date", "Date", "date", data_type="date"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] == "workforce"
    assert result["confidence"] > 0


def test_workforce_requires_employee():
    """Without an Employee concept the dataset should not be workforce."""
    concepts = [
        _col("Salary", "Revenue", "measure", data_type="number"),
        _col("Department", "Category", "category"),
    ]
    result = classify_dataset(concepts)
    assert result["primary_archetype"] != "workforce"


# ── Unknown ───────────────────────────────────────────────────


def test_unknown_when_no_signals():
    """A dataset with only low-signal Unknown concepts returns no archetype."""
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
    result = classify_dataset(concepts)
    assert result["primary_archetype"] is None
    assert result["label"] == "Unknown"


# ── Alternative archetypes ────────────────────────────────────


def test_alternatives_present_when_ambiguous():
    """
    A dataset that could be Finance or Sales should surface the runner-up
    as an alternative.
    """
    concepts = [
        _col("Account", "Customer", "entity"),
        _col("Invoice Date", "Date", "date", data_type="date"),
        _col("Invoice Amount", "Revenue", "measure", data_type="number"),
        _col("Payment Date", "Date", "date", data_type="date"),
        _col("Payment Status", "Status", "status"),
        _col("Product", "Product", "entity"),
        _col("Order ID", "Transaction/Order", "entity"),
    ]
    result = classify_dataset(concepts)
    # Primary should exist
    assert result["primary_archetype"] is not None
    # Some alternative should be present (sales or finance as runner-up)
    alt_archetypes = [a["archetype"] for a in result["alternative_archetypes"]]
    assert len(alt_archetypes) > 0


# ── Response shape ────────────────────────────────────────────


def test_response_has_required_keys():
    concepts = [
        _col("Employee", "Employee", "entity"),
        _col("Pay", "Revenue", "measure", data_type="number"),
    ]
    result = classify_dataset(concepts)
    for key in (
        "primary_archetype",
        "label",
        "confidence",
        "supporting_concepts",
        "explanation",
        "alternative_archetypes",
        "all_scores",
    ):
        assert key in result, f"Missing key: {key}"

    assert isinstance(result["supporting_concepts"], list)
    assert isinstance(result["alternative_archetypes"], list)
    assert isinstance(result["all_scores"], list)
    assert len(result["all_scores"]) == 5  # one per archetype
