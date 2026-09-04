"""
Determine the likely grain of a dataset — what each row represents.

Grain inference is driven by identified business concepts, identifier
roles, column-name cues within those concepts, optional uniqueness
statistics, and relationships between entities.  When evidence is
weak or conflicting, the result is ``unknown`` rather than an
unsupported assumption.

Supported grains:
    transaction
    customer
    subscription
    employee
    invoice
    operational_event
    product
    account
    unknown
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .capability_detection import SemanticInventory

# ──────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────

GrainId = Literal[
    "transaction",
    "customer",
    "subscription",
    "employee",
    "invoice",
    "operational_event",
    "product",
    "account",
    "unknown",
]

GRAIN_LABELS: dict[GrainId, str] = {
    "transaction": "Transaction",
    "customer": "Customer",
    "subscription": "Subscription",
    "employee": "Employee",
    "invoice": "Invoice",
    "operational_event": "Operational event",
    "product": "Product",
    "account": "Account",
    "unknown": "Unknown",
}

_INVOICE_TOKENS = ("invoice", "invoices")
_ACCOUNT_TOKENS = ("account", "accounts", "acct")
_SUBSCRIPTION_TOKENS = (
    "subscription",
    "subscriber",
    "plan",
    "mrr",
    "arr",
    "renewal",
    "churn",
    "seat",
)
_TRANSACTION_TOKENS = (
    "transaction",
    "order",
    "purchase",
    "sale",
    "booking",
    "receipt",
)
_EVENT_TOKENS = (
    "event",
    "log",
    "activity",
    "incident",
    "ticket",
    "alert",
    "operation",
)
_PRODUCT_TOKENS = ("product", "sku", "item", "merchandise")
_EMPLOYEE_TOKENS = (
    "employee",
    "staff",
    "worker",
    "personnel",
    "hire",
)


@dataclass
class _Evidence:
    signal: str
    columns: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class _Score:
    grain: GrainId
    score: float
    evidence: list[_Evidence] = field(default_factory=list)
    explanation: str = ""


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _concept_names(matches: list[dict]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in matches:
        col = match.get("sourceColumn", "")
        if col and col not in seen:
            seen.add(col)
            result.append(col)
    return result


def _avg(*values: float) -> float:
    positive = [value for value in values if value > 0]
    return round(sum(positive) / len(positive), 3) if positive else 0.0


def _column_has_token(column_name: str, tokens: tuple[str, ...]) -> bool:
    normalized = _normalize(column_name)
    parts = set(normalized.split())
    compact = normalized.replace(" ", "")
    for token in tokens:
        if " " in token:
            if token in normalized:
                return True
        elif token in parts or token in compact:
            return True
    return False


def _matches_with_tokens(
    matches: list[dict],
    tokens: tuple[str, ...],
) -> list[dict]:
    return [
        match
        for match in matches
        if _column_has_token(
            str(match.get("sourceColumn", "")),
            tokens,
        )
    ]


def _stats_by_name(
    column_stats: list[dict] | None,
) -> dict[str, dict]:
    if not column_stats:
        return {}
    return {
        str(stat.get("name", "")).strip(): stat
        for stat in column_stats
        if stat.get("name")
    }


def _unique_ratio_for(
    columns: list[str],
    stats_index: dict[str, dict],
) -> float | None:
    ratios: list[float] = []
    for column in columns:
        stat = stats_index.get(column)
        if not stat:
            continue
        if "unique_ratio" in stat and stat["unique_ratio"] is not None:
            ratios.append(float(stat["unique_ratio"]))
            continue
        unique_count = stat.get("unique_count")
        row_count = stat.get("row_count")
        if (
            unique_count is not None
            and row_count
            and float(row_count) > 0
        ):
            ratios.append(float(unique_count) / float(row_count))
    if not ratios:
        return None
    return max(ratios)


def _uniqueness_boost(
    columns: list[str],
    stats_index: dict[str, dict],
    *,
    high: float = 0.90,
    low: float = 0.50,
) -> tuple[float, _Evidence | None]:
    """
    Near-unique identifiers support the claim that each row *is* that
    entity.  Low uniqueness suggests the entity is a foreign key on
    another grain and should not claim the row.
    """
    ratio = _unique_ratio_for(columns, stats_index)
    if ratio is None:
        return 0.0, None

    if ratio >= high:
        return (
            0.20,
            _Evidence(
                signal="near_unique_identifier",
                columns=columns,
                detail=(
                    f"Identifier uniqueness ({ratio:.0%}) supports "
                    "this entity as the row grain."
                ),
            ),
        )

    if ratio <= low:
        return (
            -0.25,
            _Evidence(
                signal="low_uniqueness_identifier",
                columns=columns,
                detail=(
                    f"Identifier uniqueness ({ratio:.0%}) is low, "
                    "so this entity is unlikely to be the row grain."
                ),
            ),
        )

    return 0.0, None


def _identifier_columns_for_concept(
    inv: SemanticInventory,
    concept: str,
) -> list[str]:
    """Return identifier-role columns whose concept matches, else entity cols."""
    identifiers = [
        match
        for match in inv.by_concept(concept)
        if match.get("role") == "identifier"
    ]
    if identifiers:
        return _concept_names(identifiers)
    return _concept_names(inv.by_concept(concept))


# ──────────────────────────────────────────────────────────────
# Per-grain scorers
# ──────────────────────────────────────────────────────────────

def _score_transaction(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_txn, txn_conf, txn_matches = inv.has_concept("Transaction/Order")
    invoice_matches = _matches_with_tokens(txn_matches, _INVOICE_TOKENS)
    txn_named = _matches_with_tokens(txn_matches, _TRANSACTION_TOKENS)

    # Invoice-named transaction columns should not claim transaction grain.
    if has_txn and invoice_matches and not txn_named:
        return _Score("transaction", 0.0)

    if has_txn:
        signals.append(txn_conf)
        evidence.append(
            _Evidence(
                signal="transaction_entity",
                columns=_concept_names(txn_matches),
                detail="Transaction/Order concept present.",
            )
        )
        if txn_named:
            signals.append(0.85)
            evidence.append(
                _Evidence(
                    signal="transaction_column_naming",
                    columns=_concept_names(txn_named),
                    detail="Column names explicitly reference transactions/orders.",
                )
            )

    has_prod, prod_conf, prod_matches = inv.has_concept("Product")
    if has_prod:
        signals.append(prod_conf * 0.55)
        evidence.append(
            _Evidence(
                signal="product_dimension",
                columns=_concept_names(prod_matches),
                detail="Product references support an item/transaction grain.",
            )
        )

    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    if has_cust:
        signals.append(cust_conf * 0.45)
        evidence.append(
            _Evidence(
                signal="customer_dimension",
                columns=_concept_names(cust_matches),
                detail="Customer is present as a related dimension.",
            )
        )

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf * 0.5)
        evidence.append(
            _Evidence(
                signal="monetary_measure",
                columns=_concept_names(rev_matches),
                detail="Monetary measures commonly appear on transaction rows.",
            )
        )

    has_qty, qty_conf, qty_matches = inv.has_concept("Quantity")
    if has_qty:
        signals.append(qty_conf * 0.4)

    has_date, date_conf, date_matches = inv.has_role("date")
    if has_date:
        signals.append(date_conf * 0.35)

    if not has_txn:
        return _Score("transaction", 0.0)

    # Classic fact-table relationships: txn + product (+ customer/revenue)
    if has_txn and has_prod and (has_cust or has_rev):
        signals.append(0.95)
        evidence.append(
            _Evidence(
                signal="fact_table_relationships",
                columns=_concept_names(
                    txn_matches + prod_matches + cust_matches + rev_matches
                ),
                detail=(
                    "Transaction linked to product and customer/revenue "
                    "indicates transaction-level grain."
                ),
            )
        )

    id_cols = _identifier_columns_for_concept(inv, "Transaction/Order")
    boost, boost_evidence = _uniqueness_boost(id_cols, stats_index)
    if boost_evidence:
        evidence.append(boost_evidence)
        if boost:
            signals.append(min(1.0, max(0.0, txn_conf + boost)))

    # Prefer invoice grain when invoice naming dominates.
    if invoice_matches and len(invoice_matches) >= len(txn_named):
        signals = [signal * 0.45 for signal in signals]

    # Event/log naming should yield to operational_event, not transaction.
    event_named = _matches_with_tokens(inv.concepts, _EVENT_TOKENS)
    if event_named and not txn_named:
        signals = [signal * 0.35 for signal in signals]

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="transaction",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent a transaction or order "
            "based on transaction identifiers and related dimensions."
        ),
    )


def _score_invoice(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_txn, txn_conf, txn_matches = inv.has_concept("Transaction/Order")
    invoice_matches = _matches_with_tokens(
        inv.concepts,
        _INVOICE_TOKENS,
    )
    txn_named = _matches_with_tokens(txn_matches, _TRANSACTION_TOKENS)

    if invoice_matches:
        signals.append(0.95)
        evidence.append(
            _Evidence(
                signal="invoice_column_naming",
                columns=_concept_names(invoice_matches),
                detail="Column names explicitly reference invoices.",
            )
        )

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf * 0.8)
        evidence.append(
            _Evidence(
                signal="monetary_measure",
                columns=_concept_names(rev_matches),
                detail="Invoice grain typically carries amount measures.",
            )
        )

    date_matches = inv.by_role("date")
    if len(date_matches) >= 2:
        signals.append(0.75)
        evidence.append(
            _Evidence(
                signal="paired_financial_dates",
                columns=_concept_names(date_matches),
                detail=(
                    "Multiple dates (e.g. invoice + payment/due) support "
                    "invoice grain."
                ),
            )
        )
    elif date_matches:
        signals.append(0.35)

    has_status, status_conf, status_matches = inv.has_role("status")
    if has_status:
        signals.append(status_conf * 0.7)
        evidence.append(
            _Evidence(
                signal="payment_or_approval_status",
                columns=_concept_names(status_matches),
                detail="Status columns often track invoice payment/approval.",
            )
        )

    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    if has_cust:
        signals.append(cust_conf * 0.45)

    has_prod, _, _ = inv.has_concept("Product")

    # Need invoice naming OR (transaction-like + finance process signals)
    finance_like = has_rev and (
        len(date_matches) >= 2 or (has_status and bool(date_matches))
    )
    if not invoice_matches and not (has_txn and finance_like and not has_prod):
        return _Score("invoice", 0.0)

    if has_txn and invoice_matches:
        signals.append(txn_conf)

    # Strong product + order naming pushes away from invoice toward transaction
    if has_prod and txn_named and not invoice_matches:
        return _Score("invoice", 0.0)

    if has_prod and not invoice_matches:
        signals = [signal * 0.5 for signal in signals]

    id_cols = _concept_names(invoice_matches) or _identifier_columns_for_concept(
        inv, "Transaction/Order"
    )
    boost, boost_evidence = _uniqueness_boost(id_cols, stats_index)
    if boost_evidence:
        evidence.append(boost_evidence)
        if boost > 0:
            signals.append(0.9)

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="invoice",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent an invoice based on invoice "
            "identifiers and financial process signals."
        ),
    )


def _score_customer(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    if not has_cust:
        return _Score("customer", 0.0)

    account_named = _matches_with_tokens(cust_matches, _ACCOUNT_TOKENS)
    subscription_named = _matches_with_tokens(
        inv.concepts,
        _SUBSCRIPTION_TOKENS,
    )

    signals.append(cust_conf)
    evidence.append(
        _Evidence(
            signal="customer_entity",
            columns=_concept_names(cust_matches),
            detail="Customer entity is present.",
        )
    )

    has_status, status_conf, status_matches = inv.has_role("status")
    has_cat, cat_conf, cat_matches = inv.has_role("category")
    has_txn, _, _ = inv.has_concept("Transaction/Order")
    has_emp, _, _ = inv.has_concept("Employee")

    # Subscription-like signals should yield to subscription grain.
    if (has_status and has_cat) or subscription_named:
        signals = [signal * 0.55 for signal in signals]

    # Account-named customer columns prefer account grain when no other
    # customer-lifecycle evidence exists.
    if account_named and not has_status and not subscription_named:
        signals = [signal * 0.5 for signal in signals]

    if has_txn:
        signals = [signal * 0.55 for signal in signals]
        evidence.append(
            _Evidence(
                signal="transaction_present",
                columns=[],
                detail=(
                    "Transaction entities reduce confidence that each row "
                    "is a customer."
                ),
            )
        )

    if has_emp:
        signals = [signal * 0.4 for signal in signals]

    has_date, date_conf, date_matches = inv.has_role("date")
    if has_date:
        signals.append(date_conf * 0.3)

    if has_status and not has_cat and not subscription_named:
        signals.append(status_conf * 0.4)

    id_cols = _identifier_columns_for_concept(inv, "Customer")
    boost, boost_evidence = _uniqueness_boost(id_cols, stats_index)
    if boost_evidence:
        evidence.append(boost_evidence)
        if boost:
            signals.append(min(1.0, max(0.0, cust_conf + boost)))
        elif boost < 0:
            signals = [signal * 0.6 for signal in signals]

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="customer",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent a customer based on customer "
            "identifiers and the absence of a stronger event/entity grain."
        ),
    )


def _score_subscription(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    if not has_cust:
        return _Score("subscription", 0.0)

    subscription_named = _matches_with_tokens(
        inv.concepts,
        _SUBSCRIPTION_TOKENS,
    )
    has_status, status_conf, status_matches = inv.has_role("status")
    has_cat, cat_conf, cat_matches = inv.has_role("category")
    has_txn, _, _ = inv.has_concept("Transaction/Order")

    if not (
        subscription_named
        or (has_status and has_cat)
        or (has_status and subscription_named)
    ):
        # Status alone with customer can still be subscription-ish,
        # but requires explicit subscription naming or plan/category.
        if not (has_status and subscription_named):
            if not (has_status and has_cat):
                return _Score("subscription", 0.0)

    signals.append(cust_conf)
    evidence.append(
        _Evidence(
            signal="customer_entity",
            columns=_concept_names(cust_matches),
            detail="Customer/subscriber entity present.",
        )
    )

    if subscription_named:
        signals.append(0.95)
        evidence.append(
            _Evidence(
                signal="subscription_column_naming",
                columns=_concept_names(subscription_named),
                detail="Column names reference subscriptions, plans, or MRR.",
            )
        )

    if has_status:
        signals.append(status_conf * 0.9)
        evidence.append(
            _Evidence(
                signal="lifecycle_status",
                columns=_concept_names(status_matches),
                detail="Status/lifecycle columns support subscription grain.",
            )
        )

    if has_cat:
        signals.append(cat_conf * 0.75)
        evidence.append(
            _Evidence(
                signal="plan_or_segment",
                columns=_concept_names(cat_matches),
                detail="Plan/segment categories support subscription grain.",
            )
        )

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf * 0.35)

    if has_txn:
        signals = [signal * 0.5 for signal in signals]

    id_cols = _identifier_columns_for_concept(inv, "Customer")
    boost, boost_evidence = _uniqueness_boost(id_cols, stats_index)
    if boost_evidence:
        evidence.append(boost_evidence)
        if boost:
            signals.append(0.85)

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="subscription",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent a subscription based on "
            "customer entities with plan/status lifecycle signals."
        ),
    )


def _score_employee(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_emp, emp_conf, emp_matches = inv.has_concept("Employee")
    if not has_emp:
        return _Score("employee", 0.0)

    signals.append(emp_conf)
    evidence.append(
        _Evidence(
            signal="employee_entity",
            columns=_concept_names(emp_matches),
            detail="Employee entity is present.",
        )
    )

    employee_named = _matches_with_tokens(emp_matches, _EMPLOYEE_TOKENS)
    if employee_named:
        signals.append(0.85)

    has_cat, cat_conf, cat_matches = inv.has_role("category")
    if has_cat:
        signals.append(cat_conf * 0.5)
        evidence.append(
            _Evidence(
                signal="org_dimension",
                columns=_concept_names(cat_matches),
                detail="Department/role dimensions support employee grain.",
            )
        )

    has_date, date_conf, date_matches = inv.has_role("date")
    if has_date:
        signals.append(date_conf * 0.35)

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf * 0.4)
        evidence.append(
            _Evidence(
                signal="compensation_measure",
                columns=_concept_names(rev_matches),
                detail="Compensation-like measures support employee rows.",
            )
        )

    has_txn, _, _ = inv.has_concept("Transaction/Order")
    if has_txn:
        signals = [signal * 0.45 for signal in signals]

    id_cols = _identifier_columns_for_concept(inv, "Employee")
    boost, boost_evidence = _uniqueness_boost(id_cols, stats_index)
    if boost_evidence:
        evidence.append(boost_evidence)
        if boost:
            signals.append(min(1.0, max(0.0, emp_conf + boost)))

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="employee",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent an employee based on employee "
            "identifiers and workforce attributes."
        ),
    )


def _score_product(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_prod, prod_conf, prod_matches = inv.has_concept("Product")
    if not has_prod:
        return _Score("product", 0.0)

    has_txn, _, txn_matches = inv.has_concept("Transaction/Order")
    has_cust, _, _ = inv.has_concept("Customer")
    has_emp, _, _ = inv.has_concept("Employee")

    # Product on a transaction fact table is a dimension, not the grain.
    if has_txn:
        return _Score("product", 0.0)

    signals.append(prod_conf)
    evidence.append(
        _Evidence(
            signal="product_entity",
            columns=_concept_names(prod_matches),
            detail="Product entity is present without a transaction grain.",
        )
    )

    product_named = _matches_with_tokens(prod_matches, _PRODUCT_TOKENS)
    if product_named:
        signals.append(0.8)

    has_cat, cat_conf, cat_matches = inv.has_role("category")
    if has_cat:
        signals.append(cat_conf * 0.55)
        evidence.append(
            _Evidence(
                signal="product_category",
                columns=_concept_names(cat_matches),
                detail="Category dimensions commonly describe products.",
            )
        )

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf * 0.35)

    if has_cust:
        signals = [signal * 0.7 for signal in signals]

    if has_emp:
        signals = [signal * 0.4 for signal in signals]

    id_cols = _identifier_columns_for_concept(inv, "Product")
    boost, boost_evidence = _uniqueness_boost(id_cols, stats_index)
    if boost_evidence:
        evidence.append(boost_evidence)
        if boost:
            signals.append(min(1.0, max(0.0, prod_conf + boost)))
        elif boost < 0:
            signals = [signal * 0.55 for signal in signals]

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="product",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent a product based on product "
            "identifiers without transaction-level entities."
        ),
    )


def _score_account(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    account_named = _matches_with_tokens(
        inv.concepts,
        _ACCOUNT_TOKENS,
    )

    if not account_named:
        return _Score("account", 0.0)

    signals.append(0.9 if has_cust else 0.75)
    evidence.append(
        _Evidence(
            signal="account_column_naming",
            columns=_concept_names(account_named),
            detail="Column names explicitly reference accounts.",
        )
    )

    if has_cust:
        signals.append(cust_conf * 0.7)

    has_status, _, _ = inv.has_role("status")
    has_cat, _, _ = inv.has_role("category")
    subscription_named = _matches_with_tokens(
        inv.concepts,
        _SUBSCRIPTION_TOKENS,
    )
    has_txn, _, _ = inv.has_concept("Transaction/Order")

    # Subscription lifecycle evidence should win over bare account naming.
    if subscription_named or (has_status and has_cat):
        signals = [signal * 0.45 for signal in signals]

    if has_txn:
        # Account on a ledger/invoice set can still be a dimension;
        # only keep modest score when invoice-like.
        invoice_matches = _matches_with_tokens(
            inv.concepts,
            _INVOICE_TOKENS,
        )
        if invoice_matches:
            signals = [signal * 0.4 for signal in signals]
        else:
            signals = [signal * 0.35 for signal in signals]

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev and not has_txn:
        signals.append(rev_conf * 0.3)

    id_cols = _concept_names(account_named)
    boost, boost_evidence = _uniqueness_boost(id_cols, stats_index)
    if boost_evidence:
        evidence.append(boost_evidence)
        if boost:
            signals.append(0.9)

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="account",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent an account based on account "
            "identifiers and related attributes."
        ),
    )


def _score_operational_event(
    inv: SemanticInventory,
    stats_index: dict[str, dict],
) -> _Score:
    evidence: list[_Evidence] = []
    signals: list[float] = []

    has_qty, qty_conf, qty_matches = inv.has_concept("Quantity")
    has_status, status_conf, status_matches = inv.has_role("status")
    has_supplier, sup_conf, sup_matches = inv.has_concept("Supplier")
    has_txn, txn_conf, txn_matches = inv.has_concept("Transaction/Order")
    has_date, date_conf, date_matches = inv.has_role("date")
    has_rev, _, _ = inv.has_concept("Revenue")
    has_cust, _, _ = inv.has_concept("Customer")
    has_emp, _, _ = inv.has_concept("Employee")
    has_prod, _, _ = inv.has_concept("Product")

    event_named = _matches_with_tokens(inv.concepts, _EVENT_TOKENS)

    if not (
        event_named
        or has_qty
        or has_supplier
        or (has_status and has_date and not has_cust)
    ):
        return _Score("operational_event", 0.0)

    # Strong sales fact tables are not operational events.
    if has_txn and has_prod and has_rev:
        return _Score("operational_event", 0.0)

    if event_named:
        signals.append(0.98)
        signals.append(0.92)
        evidence.append(
            _Evidence(
                signal="event_column_naming",
                columns=_concept_names(event_named),
                detail="Column names reference events, logs, or tickets.",
            )
        )

    if has_qty:
        signals.append(qty_conf)
        evidence.append(
            _Evidence(
                signal="quantity_measure",
                columns=_concept_names(qty_matches),
                detail="Quantity/volume measures support operational events.",
            )
        )

    if has_status:
        signals.append(status_conf * 0.85)
        evidence.append(
            _Evidence(
                signal="process_status",
                columns=_concept_names(status_matches),
                detail="Status/stage columns support operational event grain.",
            )
        )

    if has_supplier:
        signals.append(sup_conf * 0.8)
        evidence.append(
            _Evidence(
                signal="supplier_entity",
                columns=_concept_names(sup_matches),
                detail="Supplier references support operational processes.",
            )
        )

    if has_txn and not has_rev:
        signals.append(txn_conf * 0.45)

    if has_date:
        signals.append(date_conf * 0.5)
        evidence.append(
            _Evidence(
                signal="event_timestamp",
                columns=_concept_names(date_matches),
                detail="Date/time columns commonly mark operational events.",
            )
        )

    if has_cust and has_rev:
        signals = [signal * 0.55 for signal in signals]

    if has_emp:
        signals = [signal * 0.4 for signal in signals]

    # Without a clear operational core, do not invent this grain.
    if not (event_named or has_qty or has_supplier or has_status):
        return _Score("operational_event", 0.0)

    score = _avg(*signals) if signals else 0.0
    return _Score(
        grain="operational_event",
        score=score,
        evidence=evidence,
        explanation=(
            "Each row appears to represent an operational event based on "
            "quantity, status, supplier, or event-oriented signals."
        ),
    )


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

_SCORERS = [
    _score_transaction,
    _score_invoice,
    _score_customer,
    _score_subscription,
    _score_employee,
    _score_product,
    _score_account,
    _score_operational_event,
]

_MINIMUM_CONFIDENCE = 0.40
_AMBIGUITY_GAP = 0.08
_ALTERNATIVE_THRESHOLD = 0.60


def determine_dataset_grain(
    concepts: list[dict],
    column_stats: list[dict] | None = None,
) -> dict:
    """
    Infer the likely grain of a dataset from identified business concepts.

    Parameters
    ----------
    concepts:
        Output of ``identify_business_concepts`` — each item should include
        ``concept``, ``role``, ``confidence``, and ``sourceColumn``.
    column_stats:
        Optional per-column uniqueness stats used to strengthen or weaken
        identifier-as-grain claims.  Each item may include ``name``,
        ``unique_ratio``, and/or ``unique_count`` + ``row_count``.

    Returns
    -------
    dict with keys:
        grain                 – grain id (or ``unknown``)
        label                 – human-readable label
        confidence            – float 0–1
        supporting_evidence   – list of {signal, columns, detail}
        explanation           – prose explanation
        alternative_grains    – list of {grain, label, confidence}
        all_scores            – full score table for debugging
    """
    inventory = SemanticInventory(concepts)
    stats_index = _stats_by_name(column_stats)

    scores: list[_Score] = [
        scorer(inventory, stats_index) for scorer in _SCORERS
    ]
    scores.sort(key=lambda item: item.score, reverse=True)

    best = scores[0]
    runner_up = scores[1] if len(scores) > 1 else None

    ambiguous = (
        runner_up is not None
        and best.score >= _MINIMUM_CONFIDENCE
        and runner_up.score >= _MINIMUM_CONFIDENCE
        and (best.score - runner_up.score) < _AMBIGUITY_GAP
    )

    if best.score < _MINIMUM_CONFIDENCE or ambiguous:
        reason = (
            "Top grain candidates are too close to distinguish confidently."
            if ambiguous
            else (
                "Could not determine dataset grain with sufficient "
                "confidence from available identifiers and relationships."
            )
        )
        ambiguous_evidence: list[dict] = []
        if ambiguous and runner_up is not None:
            ambiguous_evidence = [
                {
                    "signal": "ambiguous_candidates",
                    "columns": [],
                    "detail": (
                        f"{GRAIN_LABELS[best.grain]} "
                        f"({best.score:.0%}) vs "
                        f"{GRAIN_LABELS[runner_up.grain]} "
                        f"({runner_up.score:.0%})."
                    ),
                }
            ]
        return {
            "grain": "unknown",
            "label": GRAIN_LABELS["unknown"],
            "confidence": 0.0,
            "supporting_evidence": ambiguous_evidence,
            "explanation": reason,
            "alternative_grains": [],
            "all_scores": _format_all_scores(scores),
        }

    threshold = best.score * _ALTERNATIVE_THRESHOLD
    alternatives = [
        {
            "grain": item.grain,
            "label": GRAIN_LABELS[item.grain],
            "confidence": round(item.score, 3),
        }
        for item in scores[1:]
        if item.score >= threshold and item.score >= _MINIMUM_CONFIDENCE
    ]

    return {
        "grain": best.grain,
        "label": GRAIN_LABELS[best.grain],
        "confidence": round(best.score, 3),
        "supporting_evidence": [
            {
                "signal": item.signal,
                "columns": item.columns,
                "detail": item.detail,
            }
            for item in best.evidence
        ],
        "explanation": best.explanation,
        "alternative_grains": alternatives,
        "all_scores": _format_all_scores(scores),
    }


def _format_all_scores(scores: list[_Score]) -> list[dict]:
    return [
        {
            "grain": item.grain,
            "label": GRAIN_LABELS[item.grain],
            "score": round(item.score, 3),
        }
        for item in scores
    ]
