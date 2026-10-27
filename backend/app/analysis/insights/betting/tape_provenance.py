"""
Prediction-tape provenance and bet/close quote resolution.

Contract:
  - Decision-time (bet) quotes and closing quotes are independent.
  - Missing decision-time quotes stay missing — never copy close → bet.
  - Provenance labels distinguish verified sources from unverified /
    legacy inference. Do not invent historical prices.
"""

from __future__ import annotations

from typing import Any, Literal

from app.analysis.insights.betting.pricing import num

TapeSource = Literal[
    "live",
    "first_publish",
    "opening",
    "opening_fallback",
    "snapshot",
    "market_row",
    "unavailable",
    "unverified_legacy",
]

QuoteSource = Literal[
    "snapshot",
    "opening",
    "closing",
    "market_row",
    "offered",
    "unavailable",
    "unverified_legacy",
]


def normalize_tape_source(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unverified_legacy"
    return raw


def resolve_bet_market_lines(
    *,
    snap_spread: float | None,
    snap_total: float | None,
    opening_spread: float | None,
    opening_total: float | None,
    tape_source: str | None = None,
) -> dict[str, Any]:
    """
    Resolve event-level bet-time market spread/total.

    Order: frozen snapshot → opening quote → unavailable.
    Closing / current lines are never used.
    """

    source = normalize_tape_source(tape_source)
    if snap_spread is not None:
        bet_spread = float(snap_spread)
        spread_source: str = (
            "opening"
            if source in {"opening_fallback", "opening"}
            else "snapshot"
        )
    elif opening_spread is not None:
        bet_spread = float(opening_spread)
        spread_source = "opening"
    else:
        bet_spread = None
        spread_source = "unavailable"

    if snap_total is not None:
        bet_total = float(snap_total)
        total_source: str = (
            "opening"
            if source in {"opening_fallback", "opening"}
            else "snapshot"
        )
    elif opening_total is not None:
        bet_total = float(opening_total)
        total_source = "opening"
    else:
        bet_total = None
        total_source = "unavailable"

    resolved_tape = source
    if resolved_tape in {"", "unverified_legacy", "live"}:
        if spread_source == "snapshot" or total_source == "snapshot":
            resolved_tape = "snapshot"
        elif spread_source == "opening" or total_source == "opening":
            resolved_tape = "opening"
        else:
            resolved_tape = "unavailable"

    return {
        "bet_market_spread": bet_spread,
        "bet_market_total": bet_total,
        "bet_spread_source": spread_source,
        "bet_total_source": total_source,
        "tape_source": resolved_tape,
        "bet_quote_available": (
            bet_spread is not None or bet_total is not None
        ),
    }


def independent_quotes_for_clv(
    *,
    bet_line: float | None = None,
    closing_line: float | None = None,
    bet_price: float | None = None,
    closing_price: float | None = None,
    bet_source: str | None = None,
    closing_source: str | None = None,
    require_provenance: bool = False,
) -> bool:
    """
    True when bet and close look independently observed.

    Rejects unavailable sides and cases where close was fabricated
    from the bet quote (or vice versa).

    When ``require_provenance`` is True (settled-tape eligibility),
    missing source metadata is treated as unverified — not as a
    verified independent quote pair.
    """

    if require_provenance and (bet_source is None or closing_source is None):
        return False

    bet_src = str(bet_source or "").strip().lower()
    close_src = str(closing_source or "").strip().lower()
    if require_provenance:
        if not bet_src:
            bet_src = "unverified_legacy"
        if not close_src:
            close_src = "unverified_legacy"
    if bet_src in {"unavailable", "unverified_legacy"}:
        return False
    if close_src in {"unavailable", "unverified_legacy"}:
        return False
    if close_src in {"bet", "bet_line", "copied_from_bet"}:
        return False
    if bet_src in {"closing", "copied_from_close"}:
        return False

    has_lines = num(bet_line) is not None and num(closing_line) is not None
    has_prices = num(bet_price) is not None and num(closing_price) is not None
    return has_lines or has_prices


def opening_or_none(
    opening: float | None,
    current: float | None,
) -> tuple[float | None, str]:
    """Return opening without substituting current when missing."""

    del current  # explicit: never fall back to current
    if opening is None:
        return None, "unavailable"
    return float(opening), "opening"
