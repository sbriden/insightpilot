"""
Eligibility rules for betting analytical datasets.

Separate populations — never mix Pass / unknown into qualified-bet ROI
or selection-learning targets that mean “placed bet.”
"""

from __future__ import annotations

from typing import Any, Literal

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.tape_provenance import (
    independent_quotes_for_clv,
)

Purpose = Literal[
    "forecast_quality",
    "qualified_bet_roi",
    "clv",
    "selection_learning",
    "calibration",
]

ACTIONABLE = frozenset({"strong_bet", "lean"})
PASS_STATUSES = frozenset({"pass", "no_bet"})


def qualification_status(row: dict[str, Any]) -> str:
    """
    Normalize bet qualification.

    Missing / blank → ``unknown`` (legacy gap), never inferred Pass.
    """

    raw = row.get("bet_status")
    if raw is None:
        return "unknown"
    status = str(raw).strip().lower()
    if not status:
        return "unknown"
    if status in {"no_bet", "nobet"}:
        return "pass"
    return status


def is_settled_outcome(row: dict[str, Any]) -> bool:
    return str(row.get("result") or "").lower() in {
        "won",
        "lost",
        "push",
    }


def is_decided_outcome(row: dict[str, Any]) -> bool:
    return str(row.get("result") or "").lower() in {"won", "lost"}


def has_valid_forecast(row: dict[str, Any]) -> bool:
    return num(row.get("model_probability")) is not None or num(
        row.get("raw_model_probability")
    ) is not None


def has_decision_time_price(row: dict[str, Any]) -> bool:
    if num(row.get("bet_price")) is not None:
        return True
    if num(row.get("bet_line")) is not None:
        src = str(row.get("bet_line_source") or "").lower()
        return src not in {"unavailable", "unverified_legacy", ""}
    return False


def clv_eligible(row: dict[str, Any]) -> bool:
    if row.get("clv_available") is False:
        return False
    if row.get("clv_available") is True and num(row.get("clv")) is not None:
        # Still require provenance on settled tape — do not trust a
        # legacy zero-CLV flag without source metadata.
        bet_src = row.get("bet_line_source") or row.get("bet_price_source")
        close_src = (
            row.get("closing_line_source")
            or row.get("closing_price_source")
        )
        if bet_src is None or close_src is None:
            return False
        if str(bet_src).lower() in {"unavailable", "unverified_legacy"}:
            return False
        if str(close_src).lower() in {"unavailable", "unverified_legacy"}:
            return False
        return True
    return independent_quotes_for_clv(
        bet_line=row.get("bet_line"),
        closing_line=row.get("closing_line"),
        bet_price=row.get("bet_price"),
        closing_price=row.get("closing_price"),
        bet_source=row.get("bet_line_source") or row.get("bet_price_source"),
        closing_source=(
            row.get("closing_line_source")
            or row.get("closing_price_source")
        ),
        require_provenance=True,
    )


def row_eligible(
    row: dict[str, Any],
    purpose: Purpose,
) -> bool:
    status = qualification_status(row)

    if purpose == "forecast_quality":
        # Pass forecasts stay eligible; need forecast + settlement.
        return (
            has_valid_forecast(row)
            and is_settled_outcome(row)
            and bool(row.get("market_type"))
            and bool(row.get("selection"))
        )

    if purpose == "qualified_bet_roi":
        return (
            status in ACTIONABLE
            and is_decided_outcome(row)
            and has_decision_time_price(row)
        )

    if purpose == "clv":
        return clv_eligible(row)

    if purpose == "selection_learning":
        # Explicit qualification only — never Pass or unknown.
        return status in ACTIONABLE and is_settled_outcome(row)

    if purpose == "calibration":
        return (
            has_valid_forecast(row)
            and is_decided_outcome(row)
            and status != "unknown"
        )

    return False


def filter_rows(
    rows: list[dict[str, Any]] | None,
    purpose: Purpose,
) -> list[dict[str, Any]]:
    return [row for row in (rows or []) if row_eligible(row, purpose)]


def eligibility_counts(
    rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    all_rows = list(rows or [])
    by_status: dict[str, int] = {}
    for row in all_rows:
        key = qualification_status(row)
        by_status[key] = by_status.get(key, 0) + 1
    return {
        "n": len(all_rows),
        "by_qualification": by_status,
        "forecast_quality": len(filter_rows(all_rows, "forecast_quality")),
        "qualified_bet_roi": len(filter_rows(all_rows, "qualified_bet_roi")),
        "clv": len(filter_rows(all_rows, "clv")),
        "selection_learning": len(
            filter_rows(all_rows, "selection_learning")
        ),
        "calibration": len(filter_rows(all_rows, "calibration")),
    }
