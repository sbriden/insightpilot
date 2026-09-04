"""
Classify a dataset into a semantic archetype based on its identified
business concepts.

Classification is driven by concept roles, relationships between concepts,
presence of measures, dates, identifiers, and categorical dimensions —
not by column-name matching.  This makes it schema-agnostic: a dataset
with columns like 'Account', 'Invoice Date', 'Invoice Amount', and
'Payment Status' will be recognised as Finance / Receivables even though
none of those columns are named 'revenue' or 'customer'.

Supported archetypes (in priority order when confidence is tied):
    sales_revenue       – Sales / Revenue
    customer            – Customer / Subscription
    operations          – Operations
    finance             – Finance
    workforce           – Workforce
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .capability_detection import SemanticInventory

# ──────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────

ArchetypeId = Literal[
    "sales_revenue",
    "customer",
    "operations",
    "finance",
    "workforce",
]

ARCHETYPE_LABELS: dict[ArchetypeId, str] = {
    "sales_revenue": "Sales / Revenue",
    "customer": "Customer / Subscription",
    "operations": "Operations",
    "finance": "Finance",
    "workforce": "Workforce",
}


@dataclass
class _Score:
    archetype: ArchetypeId
    score: float
    supporting_concepts: list[str] = field(default_factory=list)
    explanation: str = ""


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _concept_names(matches: list[dict]) -> list[str]:
    """Return unique source column names from a list of concept matches."""
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        col = m.get("sourceColumn", "")
        if col and col not in seen:
            seen.add(col)
            result.append(col)
    return result


def _avg(*values: float) -> float:
    pos = [v for v in values if v > 0]
    return round(sum(pos) / len(pos), 3) if pos else 0.0


# ──────────────────────────────────────────────────────────────
# Per-archetype scorers
# ──────────────────────────────────────────────────────────────

def _score_sales_revenue(inv: SemanticInventory) -> _Score:
    """
    Sales / Revenue datasets typically have:
      - A revenue/amount measure
      - A transaction or order entity OR a product entity
      - A date dimension (optional but strongly supportive)
      - A customer or geography dimension (optional)

    They are distinguished from Finance by having direct sales
    transactions rather than receivables / payables / ledger entries.
    """
    signals: list[float] = []
    supporting: list[str] = []

    # Core: revenue measure
    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf)
        supporting.extend(_concept_names(rev_matches))

    # Core: transaction / order entity
    has_txn, txn_conf, txn_matches = inv.has_concept("Transaction/Order")
    if has_txn:
        signals.append(txn_conf)
        supporting.extend(_concept_names(txn_matches))

    # Supportive: product
    has_prod, prod_conf, prod_matches = inv.has_concept("Product")
    if has_prod:
        signals.append(prod_conf * 0.6)
        supporting.extend(_concept_names(prod_matches))

    # Supportive: date
    has_date, date_conf, date_matches = inv.has_role("date")
    if has_date:
        signals.append(date_conf * 0.5)
        supporting.extend(_concept_names(date_matches))

    # Supportive: customer
    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    if has_cust:
        signals.append(cust_conf * 0.4)
        supporting.extend(_concept_names(cust_matches))

    # Must have at least revenue OR transaction to be a valid candidate
    if not has_rev and not has_txn:
        return _Score("sales_revenue", 0.0)

    # Classic sales grain: transactions with customer + product + revenue
    # should outrank adjacent archetypes like finance.
    sales_like = has_txn and has_prod and has_rev
    if sales_like:
        signals.append(0.95)
        if has_cust:
            signals.append(0.85)

    # Penalise heavily when dataset is clearly workforce-oriented
    # (employee entities present, no transaction/order focus)
    has_emp, _, _ = inv.has_concept("Employee")
    if has_emp and not has_txn:
        signals = [s * 0.3 for s in signals]

    # Penalise when dataset looks like a subscription/customer list:
    # has a Customer entity + Status but no Transaction entity
    has_cust_check, _, _ = inv.has_concept("Customer")
    has_status_check, _, _ = inv.has_role("status")
    if has_cust_check and has_status_check and not has_txn:
        signals = [s * 0.5 for s in signals]

    score = _avg(*signals) if signals else 0.0

    return _Score(
        archetype="sales_revenue",
        score=score,
        supporting_concepts=list(dict.fromkeys(supporting)),
        explanation=(
            "Dataset shows sales/revenue characteristics: "
            + ", ".join(
                f for f in [
                    "revenue measures" if has_rev else "",
                    "transaction/order entities" if has_txn else "",
                    "product references" if has_prod else "",
                ]
                if f
            )
            + "."
        ),
    )


def _score_customer(inv: SemanticInventory) -> _Score:
    """
    Customer / Subscription datasets typically have:
      - A customer entity as the grain
      - Subscription, status, or lifecycle concepts
      - Revenue or quantity measures (optional)
      - Minimal transaction-level data (single row per customer)
    """
    signals: list[float] = []
    supporting: list[str] = []

    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    if has_cust:
        signals.append(cust_conf)
        supporting.extend(_concept_names(cust_matches))

    has_status, status_conf, status_matches = inv.has_role("status")
    if has_status:
        signals.append(status_conf * 0.9)  # status is a very strong customer signal
        supporting.extend(_concept_names(status_matches))

    has_cat, cat_conf, cat_matches = inv.has_role("category")
    if has_cat:
        signals.append(cat_conf * 0.7)  # plan/segment dimension
        supporting.extend(_concept_names(cat_matches))

    has_date, date_conf, date_matches = inv.has_role("date")
    if has_date:
        signals.append(date_conf * 0.4)
        supporting.extend(_concept_names(date_matches))

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf * 0.3)
        supporting.extend(_concept_names(rev_matches))

    if not has_cust:
        return _Score("customer", 0.0)

    # Penalise if there are strong transaction signals — those push to sales
    has_txn, _, _ = inv.has_concept("Transaction/Order")
    if has_txn:
        signals = [s * 0.7 for s in signals]

    score = _avg(*signals) if signals else 0.0

    return _Score(
        archetype="customer",
        score=score,
        supporting_concepts=list(dict.fromkeys(supporting)),
        explanation=(
            "Dataset shows customer/subscription characteristics: "
            + ", ".join(
                f for f in [
                    "customer entities" if has_cust else "",
                    "status/lifecycle columns" if has_status else "",
                ]
                if f
            )
            + "."
        ),
    )


def _score_operations(inv: SemanticInventory) -> _Score:
    """
    Operations datasets typically have:
      - Quantity measures (units, volume, count)
      - Status columns (pipeline, stage, phase)
      - Transaction or order entities
      - Date dimensions
      - No strong revenue or customer focus
    """
    signals: list[float] = []
    supporting: list[str] = []

    has_qty, qty_conf, qty_matches = inv.has_concept("Quantity")
    if has_qty:
        signals.append(qty_conf)
        supporting.extend(_concept_names(qty_matches))

    has_status, status_conf, status_matches = inv.has_role("status")
    if has_status:
        signals.append(status_conf * 0.8)
        supporting.extend(_concept_names(status_matches))

    has_txn, txn_conf, txn_matches = inv.has_concept("Transaction/Order")
    if has_txn:
        signals.append(txn_conf * 0.6)
        supporting.extend(_concept_names(txn_matches))

    has_supplier, sup_conf, sup_matches = inv.has_concept("Supplier")
    if has_supplier:
        signals.append(sup_conf * 0.7)
        supporting.extend(_concept_names(sup_matches))

    has_date, date_conf, date_matches = inv.has_role("date")
    if has_date:
        signals.append(date_conf * 0.4)
        supporting.extend(_concept_names(date_matches))

    if not (has_qty or has_status or has_supplier):
        return _Score("operations", 0.0)

    score = _avg(*signals) if signals else 0.0

    return _Score(
        archetype="operations",
        score=score,
        supporting_concepts=list(dict.fromkeys(supporting)),
        explanation=(
            "Dataset shows operational characteristics: "
            + ", ".join(
                f for f in [
                    "quantity/volume measures" if has_qty else "",
                    "status/stage columns" if has_status else "",
                    "supplier/vendor references" if has_supplier else "",
                ]
                if f
            )
            + "."
        ),
    )


def _score_finance(inv: SemanticInventory) -> _Score:
    """
    Finance datasets typically have:
      - Revenue / amount measures (invoices, payments, balances)
      - Date pairs (invoice date + payment date, period dates)
      - Status columns (payment status, approval status)
      - Account / customer entities
      - No strong product or transaction-item focus

    The key differentiator from Sales is the presence of financial
    process concepts: paired dates (issue + due/payment), status of
    monetary transactions, and account-level (not item-level) grain.
    """
    signals: list[float] = []
    supporting: list[str] = []

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        signals.append(rev_conf)
        supporting.extend(_concept_names(rev_matches))

    has_status, status_conf, status_matches = inv.has_role("status")
    if has_status:
        signals.append(status_conf * 0.9)
        supporting.extend(_concept_names(status_matches))

    # Count date columns — finance often has multiple (invoice date, payment
    # date, due date, period start/end).  Two or more is a strong signal.
    date_matches = inv.by_role("date")
    has_date = bool(date_matches)
    if has_date:
        date_conf = min(m["confidence"] for m in date_matches)
        multi_date_bonus = 0.15 if len(date_matches) >= 2 else 0.0
        signals.append(min(1.0, date_conf * 0.7 + multi_date_bonus))
        supporting.extend(_concept_names(date_matches))

    has_cust, cust_conf, cust_matches = inv.has_concept("Customer")
    if has_cust:
        signals.append(cust_conf * 0.5)
        supporting.extend(_concept_names(cust_matches))

    has_txn, _, _ = inv.has_concept("Transaction/Order")
    has_prod, _, _ = inv.has_concept("Product")

    # Sales-like grain (product + transaction + revenue) should not be
    # treated as finance just because there are multiple dates or a
    # generic status column (e.g. order status, ship date).
    sales_like = has_rev and has_txn and has_prod

    # Finance needs revenue plus financial-process evidence:
    #   - two or more dates (invoice + payment/due), or
    #   - status + date without a sales product/transaction grain
    multi_date = len(date_matches) >= 2
    has_cust_entity = bool(inv.by_concept("Customer"))
    has_cat = bool(inv.by_role("category"))
    subscription_like = has_cust_entity and has_cat

    finance_qualified = (
        (multi_date and not sales_like)
        or (has_status and has_date and not subscription_like and not sales_like)
    )
    if not has_rev or not finance_qualified:
        return _Score("finance", 0.0)

    # Even when finance qualifies, soft-penalise residual sales signals
    if has_txn or has_prod:
        signals = [s * 0.75 for s in signals]

    score = _avg(*signals) if signals else 0.0

    return _Score(
        archetype="finance",
        score=score,
        supporting_concepts=list(dict.fromkeys(supporting)),
        explanation=(
            "Dataset shows finance/receivables characteristics: "
            + ", ".join(
                f for f in [
                    "monetary measures" if has_rev else "",
                    "payment/approval status" if has_status else "",
                    f"{len(date_matches)} date columns" if has_date else "",
                ]
                if f
            )
            + "."
        ),
    )


def _score_workforce(inv: SemanticInventory) -> _Score:
    """
    Workforce datasets typically have:
      - Employee entities
      - Revenue/salary measures (compensation, pay, wage)
      - Category dimensions (department, division, role)
      - Date dimensions (hire date, termination date)
    """
    signals: list[float] = []
    supporting: list[str] = []

    has_emp, emp_conf, emp_matches = inv.has_concept("Employee")
    if has_emp:
        signals.append(emp_conf)
        supporting.extend(_concept_names(emp_matches))

    has_rev, rev_conf, rev_matches = inv.has_concept("Revenue")
    if has_rev:
        # Revenue in a workforce context = compensation
        signals.append(rev_conf * 0.8)
        supporting.extend(_concept_names(rev_matches))

    has_cat, cat_conf, cat_matches = inv.has_role("category")
    if has_cat:
        signals.append(cat_conf * 0.5)
        supporting.extend(_concept_names(cat_matches))

    has_date, date_conf, date_matches = inv.has_role("date")
    if has_date:
        signals.append(date_conf * 0.4)
        supporting.extend(_concept_names(date_matches))

    if not has_emp:
        return _Score("workforce", 0.0)

    score = _avg(*signals) if signals else 0.0

    return _Score(
        archetype="workforce",
        score=score,
        supporting_concepts=list(dict.fromkeys(supporting)),
        explanation=(
            "Dataset shows workforce characteristics: "
            + ", ".join(
                f for f in [
                    "employee entities" if has_emp else "",
                    "compensation measures" if has_rev else "",
                    "department/role dimensions" if has_cat else "",
                ]
                if f
            )
            + "."
        ),
    )


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

_SCORERS = [
    _score_sales_revenue,
    _score_customer,
    _score_operations,
    _score_finance,
    _score_workforce,
]

_MINIMUM_CONFIDENCE = 0.30
_ALTERNATIVE_THRESHOLD = 0.60   # fraction of primary score


def classify_dataset(concepts: list[dict]) -> dict:
    """
    Classify a dataset from its list of identified business concepts.

    Parameters
    ----------
    concepts:
        Output of ``identify_business_concepts``  — each item must have
        ``concept``, ``role``, ``confidence``, and ``sourceColumn`` keys.

    Returns
    -------
    dict with keys:
        primary_archetype   – archetype id string
        label               – human-readable archetype name
        confidence          – float 0–1
        supporting_concepts – list of source column names that drove the decision
        explanation         – prose explanation
        alternative_archetypes – list of {archetype, label, confidence} dicts
        all_scores          – full score table for debugging
    """
    inventory = SemanticInventory(concepts)

    scores: list[_Score] = [scorer(inventory) for scorer in _SCORERS]
    scores.sort(key=lambda s: s.score, reverse=True)

    best = scores[0]

    if best.score < _MINIMUM_CONFIDENCE:
        return {
            "primary_archetype": None,
            "label": "Unknown",
            "confidence": 0.0,
            "supporting_concepts": [],
            "explanation": (
                "Could not determine a dataset archetype with sufficient "
                "confidence.  The dataset may require more columns or "
                "clearer column naming."
            ),
            "alternative_archetypes": [],
            "all_scores": _format_all_scores(scores),
        }

    # Alternatives: any runner-up whose score is at least X% of the best
    threshold = best.score * _ALTERNATIVE_THRESHOLD
    alternatives = [
        {
            "archetype": s.archetype,
            "label": ARCHETYPE_LABELS[s.archetype],
            "confidence": round(s.score, 3),
        }
        for s in scores[1:]
        if s.score >= threshold and s.score >= _MINIMUM_CONFIDENCE
    ]

    return {
        "primary_archetype": best.archetype,
        "label": ARCHETYPE_LABELS[best.archetype],
        "confidence": round(best.score, 3),
        "supporting_concepts": best.supporting_concepts,
        "explanation": best.explanation,
        "alternative_archetypes": alternatives,
        "all_scores": _format_all_scores(scores),
    }


def _format_all_scores(scores: list[_Score]) -> list[dict]:
    return [
        {
            "archetype": s.archetype,
            "label": ARCHETYPE_LABELS[s.archetype],
            "score": round(s.score, 3),
        }
        for s in scores
    ]
