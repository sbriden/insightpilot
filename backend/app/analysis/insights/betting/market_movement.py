"""
Market movement: opening vs current lines.

Answers a different question than residual projection:

  residual  → where is the market wrong right now?
  movement  → has the market already started moving that way?

Structure:
  opening_* / current_*
  derived moves
  eventual: velocity, time since move, consensus (stubs)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.analysis.insights.betting.pricing import (
    implied_prob_to_american,
    num,
)


def spread_to_home_moneyline(spread: float | None) -> int | None:
    """
    Synthetic home American ML from event spread.

    Event spread convention: away − home (negative = home favored),
    matching slate moneyline pricing.
    """

    if spread is None:
        return None
    home_win_p = 1.0 / (1.0 + math.exp(float(spread) / 7.0))
    price = implied_prob_to_american(home_win_p)
    if price is None:
        return None
    return int(price)


def build_market_movement(
    *,
    opening_spread: float | None = None,
    current_spread: float | None = None,
    opening_total: float | None = None,
    current_total: float | None = None,
    opening_moneyline: int | float | None = None,
    current_moneyline: int | float | None = None,
    opening_captured_at: str | None = None,
    line_moved_at: str | None = None,
    residual_home: float | None = None,
    residual_away: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Build opening/current/move payload for a game.

    Moneyline fields are home-team American odds. When omitted they
    are derived from the corresponding spread.
    """

    open_spread = num(opening_spread)
    cur_spread = num(current_spread)
    open_total = num(opening_total)
    cur_total = num(current_total)

    # Fall back: no distinct opening → treat current as opening.
    if open_spread is None:
        open_spread = cur_spread
    if open_total is None:
        open_total = cur_total

    open_ml = (
        int(opening_moneyline)
        if opening_moneyline is not None
        else spread_to_home_moneyline(open_spread)
    )
    cur_ml = (
        int(current_moneyline)
        if current_moneyline is not None
        else spread_to_home_moneyline(cur_spread)
    )

    spread_move = (
        round(float(cur_spread) - float(open_spread), 1)
        if open_spread is not None and cur_spread is not None
        else None
    )
    total_move = (
        round(float(cur_total) - float(open_total), 1)
        if open_total is not None and cur_total is not None
        else None
    )
    moneyline_move = (
        int(cur_ml) - int(open_ml)
        if open_ml is not None and cur_ml is not None
        else None
    )

    moved = bool(
        (spread_move is not None and abs(spread_move) >= 0.5)
        or (total_move is not None and abs(total_move) >= 0.5)
        or (moneyline_move is not None and abs(moneyline_move) >= 5)
    )

    seconds_since_move = _seconds_since(line_moved_at, now=now)
    # Velocity stubs — require richer snapshot history later.
    spread_velocity = None
    total_velocity = None
    consensus_move = None

    vs_model = classify_move_vs_model(
        spread_move=spread_move,
        residual_home=residual_home,
        residual_away=residual_away,
    )

    return {
        "opening_spread": open_spread,
        "current_spread": cur_spread,
        "opening_total": open_total,
        "current_total": cur_total,
        "opening_moneyline": open_ml,
        "current_moneyline": cur_ml,
        "spread_move": spread_move,
        "total_move": total_move,
        "moneyline_move": moneyline_move,
        "moved": moved,
        "opening_captured_at": opening_captured_at,
        "line_moved_at": line_moved_at,
        "seconds_since_move": seconds_since_move,
        "spread_velocity": spread_velocity,
        "total_velocity": total_velocity,
        "consensus_move": consensus_move,
        "vs_model": vs_model,
        "note": (
            "Movement asks whether the market has started "
            "incorporating what the residual model sees."
        ),
    }


def classify_move_vs_model(
    *,
    spread_move: float | None,
    residual_home: float | None = None,
    residual_away: float | None = None,
) -> dict[str, Any]:
    """
    Compare spread move direction to model residual.

    InsightPilot event spread convention: away − home
    (negative = home favored). Negative spread_move means the
    market moved toward the home team. Positive residual_home
    means the model likes home more than the market.
    """

    residual = num(residual_home)
    if residual is None and residual_away is not None:
        residual = -float(residual_away)

    if spread_move is None or residual is None:
        return {
            "label": "unknown",
            "aligned": None,
            "explanation": (
                "Need both a line move and a model residual "
                "to judge market incorporation."
            ),
        }

    if abs(float(spread_move)) < 0.5 or abs(float(residual)) < 0.35:
        return {
            "label": "stable",
            "aligned": None,
            "explanation": (
                "No material line move and/or residual to compare."
            ),
        }

    # Toward home: spread_move < 0, residual_home > 0.
    move_toward_home = float(spread_move) < 0
    model_likes_home = float(residual) > 0
    aligned = move_toward_home == model_likes_home
    if aligned:
        return {
            "label": "line_toward_model",
            "aligned": True,
            "explanation": (
                "Line has moved in the same direction as the "
                "model residual — market may already be "
                "incorporating the edge."
            ),
        }
    return {
        "label": "line_away_from_model",
        "aligned": False,
        "explanation": (
            "Line moved opposite the model residual — possible "
            "that the market has not fully incorporated the "
            "InsightPilot view yet."
        ),
    }


def _seconds_since(
    timestamp: str | None,
    *,
    now: datetime | None = None,
) -> float | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(
            str(timestamp).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, (current - parsed).total_seconds())
