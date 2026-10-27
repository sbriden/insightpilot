"""
Repeatable prediction-tape and probability/pricing audits.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.analysis.insights.betting.dataset_eligibility import (
    eligibility_counts,
    qualification_status,
)
from app.analysis.insights.betting.pricing import num


def build_tape_quality_report(
    rows: list[dict[str, Any]] | None,
    *,
    snapshots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Counts for missing quotes, fallbacks, provenance, qualification."""

    settled = list(rows or [])
    snaps = list(snapshots or [])

    missing_bet_line = 0
    missing_closing_line = 0
    missing_bet_price = 0
    missing_closing_price = 0
    clv_unavailable = 0
    clv_zero = 0
    clv_positive = 0
    bet_equals_close = 0
    unverified_provenance = 0
    substituted_close_as_bet = 0
    invalid_timestamp_order = 0
    bet_source_counts: Counter[str] = Counter()
    tape_source_counts: Counter[str] = Counter()
    qual_counts: Counter[str] = Counter()

    for row in settled:
        qual_counts[qualification_status(row)] += 1
        bet_src = str(
            row.get("bet_line_source")
            or row.get("bet_price_source")
            or "unverified_legacy"
        ).lower()
        tape_src = str(row.get("tape_source") or "unverified_legacy").lower()
        bet_source_counts[bet_src] += 1
        tape_source_counts[tape_src] += 1

        if bet_src in {"unavailable", "unverified_legacy"}:
            unverified_provenance += 1
        if bet_src in {"closing", "copied_from_close"}:
            substituted_close_as_bet += 1

        mtype = str(row.get("market_type") or "").lower()
        if mtype in {"spread", "total"}:
            if num(row.get("bet_line")) is None:
                missing_bet_line += 1
            if num(row.get("closing_line")) is None:
                missing_closing_line += 1
            bet_l = num(row.get("bet_line"))
            close_l = num(row.get("closing_line"))
            if (
                bet_l is not None
                and close_l is not None
                and abs(float(bet_l) - float(close_l)) < 1e-9
            ):
                bet_equals_close += 1
        if mtype == "moneyline":
            if num(row.get("bet_price")) is None:
                missing_bet_price += 1
            if num(row.get("closing_price")) is None:
                missing_closing_price += 1

        if row.get("clv_available") is False or (
            num(row.get("clv")) is None
            and row.get("beat_close") is None
        ):
            clv_unavailable += 1
        elif num(row.get("clv")) == 0:
            clv_zero += 1
        elif num(row.get("clv")) is not None and float(row["clv"]) > 0:
            clv_positive += 1

        decision_at = row.get("decision_at") or row.get(
            "projection_captured_at"
        )
        settled_at = row.get("settled_at")
        if decision_at and settled_at and str(decision_at) > str(settled_at):
            invalid_timestamp_order += 1

    snap_unset_source = 0
    snap_ids: Counter[str] = Counter()
    for snap in snaps:
        src = snap.get("tape_source")
        if src is None or str(src).strip() == "":
            snap_unset_source += 1
        gid = str(snap.get("game_id") or "")
        if gid:
            snap_ids[gid] += 1
    duplicate_snapshots = sum(1 for n in snap_ids.values() if n > 1)

    return {
        "title": "Prediction tape quality audit",
        "n_settled": len(settled),
        "n_snapshots": len(snaps),
        "missing_bet_line": missing_bet_line,
        "missing_closing_line": missing_closing_line,
        "missing_bet_price": missing_bet_price,
        "missing_closing_price": missing_closing_price,
        "clv_unavailable": clv_unavailable,
        "clv_zero": clv_zero,
        "clv_positive": clv_positive,
        "bet_equals_close": bet_equals_close,
        "unverified_provenance": unverified_provenance,
        "substituted_close_as_bet": substituted_close_as_bet,
        "invalid_timestamp_order": invalid_timestamp_order,
        "missing_qualification_unknown": qual_counts.get("unknown", 0),
        "pass_rows": qual_counts.get("pass", 0),
        "snapshot_unset_tape_source": snap_unset_source,
        "duplicate_snapshots": duplicate_snapshots,
        "bet_line_source_counts": dict(bet_source_counts),
        "tape_source_counts": dict(tape_source_counts),
        "qualification_counts": dict(qual_counts),
        "eligibility": eligibility_counts(settled),
        "note": (
            "Missing decision-time quotes stay missing; CLV is counted "
            "unavailable rather than zero when quotes are incomparable."
        ),
    }


def build_pricing_semantics_audit(
    rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Audit market vs reference probability labeling on market rows."""

    markets = list(rows or [])
    source_counts: Counter[str] = Counter()
    synthetic_market_p = 0
    reference_labeled = 0
    real_market_p = 0
    missing_market_p = 0
    ml_from_spread = 0
    market_edge_available = 0
    price_ev_available = 0
    assumed_ev = 0

    for row in markets:
        src = str(
            row.get("market_probability_source") or "unverified_legacy"
        ).lower()
        source_counts[src] += 1
        mtype = str(row.get("market_type") or "").lower()
        mp = num(row.get("market_probability"))
        ref = num(row.get("reference_probability"))

        if src in {"two_way_american", "single_side_american"}:
            real_market_p += 1
        elif src == "unavailable" or mp is None:
            missing_market_p += 1
        elif src in {
            "synthetic_minus_110",
            "spread_logistic",
            "unverified_legacy",
        }:
            synthetic_market_p += 1

        if ref is not None and abs(float(ref) - 0.5) < 1e-9:
            reference_labeled += 1
        if src == "spread_logistic" and mtype == "moneyline":
            ml_from_spread += 1
        if num(row.get("market_edge_probability")) is not None:
            market_edge_available += 1
        basis = str(row.get("expected_value_basis") or "").lower()
        if basis == "offered_price" and num(row.get("expected_value")) is not None:
            price_ev_available += 1
        if basis == "assumed_minus_110":
            assumed_ev += 1

    return {
        "title": "Probability / pricing semantics audit",
        "n_markets": len(markets),
        "market_probability_source_counts": dict(source_counts),
        "real_book_market_probability": real_market_p,
        "missing_market_probability": missing_market_p,
        "synthetic_or_legacy_market_probability": synthetic_market_p,
        "reference_probability_present": reference_labeled,
        "moneyline_from_spread_logistic": ml_from_spread,
        "market_edge_available": market_edge_available,
        "price_based_ev_available": price_ev_available,
        "assumed_minus_110_ev": assumed_ev,
        "note": (
            "market_probability must come from real quotes; "
            "reference_probability=0.5 is diagnostic only."
        ),
    }


def run_tape_and_pricing_audits(
    *,
    settled_rows: list[dict[str, Any]] | None = None,
    market_rows: list[dict[str, Any]] | None = None,
    snapshots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "tape_quality": build_tape_quality_report(
            settled_rows, snapshots=snapshots
        ),
        "pricing_semantics": build_pricing_semantics_audit(
            market_rows if market_rows is not None else settled_rows
        ),
    }
