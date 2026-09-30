"""
Sports Betting portfolio analytics.

Positions are recorded by the client (entry price / exposure / notes).
This module refreshes them against the current betting slate and
derives exposure, correlation, assumptions, and health signals —
an investment-style portfolio layer, not a bet slip.
"""

from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.slate import build_betting_slate


_RISK_PROFILES: dict[str, dict[str, Any]] = {
    "conservative": {
        "min_edge": 3.0,
        "min_confidence": {"High"},
        "max_positions": 8,
        "max_per_game": 2,
        "max_position_pct": 0.18,
        "single_pct": 0.80,
        "parlay_pct": 0.20,
        "max_parlays": 2,
        "parlay_sizes": {
            "small": 0.85,
            "medium": 0.15,
            "large": 0.0,
        },
    },
    "balanced": {
        "min_edge": 1.5,
        "min_confidence": {"High", "Moderate"},
        "max_positions": 12,
        "max_per_game": 3,
        "max_position_pct": 0.28,
        "single_pct": 0.55,
        "parlay_pct": 0.45,
        "max_parlays": 4,
        "parlay_sizes": {
            "small": 0.45,
            "medium": 0.40,
            "large": 0.15,
        },
    },
    "aggressive": {
        "min_edge": 0.5,
        "min_confidence": {"High", "Moderate", "Low"},
        "max_positions": 16,
        "max_per_game": 4,
        "max_position_pct": 0.40,
        "single_pct": 0.30,
        "parlay_pct": 0.70,
        "max_parlays": 6,
        "parlay_sizes": {
            "small": 0.25,
            "medium": 0.40,
            "large": 0.35,
        },
    },
}

_PARLAY_LEG_COUNTS: dict[str, int] = {
    "small": 2,
    "medium": 3,
    "large": 5,
}


def generate_betting_portfolio(
    *,
    total_exposure: float,
    risk_exposure: float,
    season: int | None = None,
    week: int | None = None,
    risk: str = "balanced",
    market_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a diversified open-position portfolio from the current slate.

    ``total_exposure`` is the full stake budget to allocate.
    ``risk_exposure`` caps how much can sit in any single game
    environment (concentration / correlated risk budget).

    Selection stance controls singles vs parlay mix and the
    small / medium / large parlay size distribution.
    """

    budget = max(0.0, float(total_exposure or 0.0))
    game_cap = max(0.0, float(risk_exposure or 0.0))
    if budget <= 0:
        raise ValueError("total_exposure must be greater than 0.")
    if game_cap <= 0:
        raise ValueError("risk_exposure must be greater than 0.")
    game_cap = min(game_cap, budget)

    risk_key = str(risk or "balanced").strip().lower()
    if risk_key not in _RISK_PROFILES:
        risk_key = "balanced"
    profile = dict(_RISK_PROFILES[risk_key])

    # Tighter per-game caps relative to budget imply more diversification.
    concentration = game_cap / budget
    if concentration <= 0.2:
        profile = {**profile, **_RISK_PROFILES["conservative"]}
        risk_key = "conservative"
    elif concentration >= 0.55:
        profile = {
            **profile,
            "max_per_game": max(int(profile["max_per_game"]), 4),
        }

    slate = build_betting_slate(season=season, week=week)
    markets = list(slate.get("markets") or [])
    allowed_types = {
        str(item).lower()
        for item in (market_types or ["spread", "total", "moneyline"])
    }

    candidates = _rank_market_candidates(
        markets,
        profile=profile,
        allowed_types=allowed_types,
    )
    if not candidates:
        raise ValueError(
            "No eligible markets with model edge for the current "
            "slate and risk settings."
        )

    single_budget = budget * float(profile["single_pct"])
    parlay_budget = budget * float(profile["parlay_pct"])

    singles = _select_markets_for_budget(
        candidates,
        total_exposure=single_budget,
        risk_exposure=game_cap,
        profile=profile,
    )
    used_market_ids = {
        str(item["market"].get("market_id") or "")
        for item in singles
    }
    game_exposure: Counter[str] = Counter()
    for item in singles:
        event_id = str(item.get("event_id") or "unknown")
        game_exposure[event_id] += float(item.get("exposure") or 0.0)

    remaining_for_parlays = [
        row
        for row in candidates
        if str(row["market"].get("market_id") or "")
        not in used_market_ids
    ]
    if len(remaining_for_parlays) < 4:
        remaining_for_parlays = list(candidates)

    parlays = _build_parlay_positions(
        remaining_for_parlays,
        parlay_budget=parlay_budget,
        risk_exposure=game_cap,
        profile=profile,
        game_exposure=game_exposure,
        risk_key=risk_key,
    )

    parlay_allocated = sum(
        float(row.get("exposure") or 0.0) for row in parlays
    )
    leftover = max(
        0.0,
        budget
        - (
            sum(float(row.get("exposure") or 0.0) for row in singles)
            + parlay_allocated
        ),
    )
    if leftover >= 1.0 and singles:
        for item in sorted(
            singles, key=lambda row: -float(row["score"])
        ):
            if leftover < 1.0:
                break
            event_id = str(item.get("event_id") or "unknown")
            room = game_cap - float(game_exposure.get(event_id, 0.0))
            max_position = min(
                game_cap,
                budget * float(profile["max_position_pct"]),
            )
            room = min(
                room,
                max_position - float(item.get("exposure") or 0.0),
            )
            if room < 1.0:
                continue
            add = min(leftover, room)
            item["exposure"] = float(item["exposure"]) + add
            game_exposure[event_id] += add
            leftover -= add

    positions: list[dict[str, Any]] = []
    for item in singles:
        market = item["market"]
        stake = float(item["exposure"])
        if stake < 1.0:
            continue
        positions.append(
            create_position_from_market(
                market,
                exposure=round(stake, 2),
                notes=(
                    f"Generated single · {risk_key} · "
                    f"score {item['score']:.1f}"
                ),
            )
        )
    positions.extend(parlays)

    if not positions:
        raise ValueError(
            "Unable to allocate a portfolio under the given "
            "total and risk exposure limits."
        )

    analyzed = analyze_betting_portfolio(
        positions,
        season=slate.get("season"),
        week=slate.get("week"),
        status_filter="open",
    )
    allocated = sum(
        float(row.get("exposure") or 0.0) for row in positions
    )
    single_count = sum(
        1
        for row in positions
        if str(row.get("bet_type") or "single") == "single"
    )
    parlay_count = len(positions) - single_count
    size_counts = Counter(
        str(row.get("parlay_size") or "")
        for row in positions
        if str(row.get("bet_type") or "") == "parlay"
    )
    return {
        **analyzed,
        "generation": {
            "total_exposure": round(budget, 2),
            "risk_exposure": round(game_cap, 2),
            "risk": risk_key,
            "allocated_exposure": round(allocated, 2),
            "position_count": len(positions),
            "single_count": single_count,
            "parlay_count": parlay_count,
            "parlay_size_counts": {
                "small": int(size_counts.get("small", 0)),
                "medium": int(size_counts.get("medium", 0)),
                "large": int(size_counts.get("large", 0)),
            },
            "target_single_pct": float(profile["single_pct"]),
            "target_parlay_pct": float(profile["parlay_pct"]),
            "candidates_considered": len(candidates),
            "max_positions": profile["max_positions"],
            "max_per_game": profile["max_per_game"],
            "note": (
                "Stance sets the singles vs parlay mix and the "
                "small/medium/large parlay distribution. Stakes "
                "follow model edge while capping per-game risk "
                "exposure. Allocated amount may land below total "
                "when risk caps bind."
            ),
        },
    }


def _rank_market_candidates(
    markets: list[dict[str, Any]],
    *,
    profile: dict[str, Any],
    allowed_types: set[str],
) -> list[dict[str, Any]]:
    min_edge = float(profile["min_edge"])
    allowed_confidence = set(profile["min_confidence"])
    scored: list[dict[str, Any]] = []
    for market in markets:
        market_type = str(market.get("market_type") or "").lower()
        if market_type and allowed_types and market_type not in allowed_types:
            continue
        edge = num(market.get("edge_probability"))
        if edge is None:
            edge = num(market.get("edge"))
        if edge is None or edge < min_edge:
            continue
        confidence = str(market.get("confidence") or "Low")
        if confidence not in allowed_confidence:
            continue
        ev = num(market.get("expected_value")) or 0.0
        confidence_weight = {
            "High": 1.35,
            "Moderate": 1.0,
            "Low": 0.65,
        }.get(confidence, 0.65)
        score = float(edge) * confidence_weight + max(0.0, float(ev)) * 0.25
        scored.append(
            {
                "market": market,
                "event_id": str(market.get("event_id") or ""),
                "market_type": market_type,
                "edge": float(edge),
                "confidence": confidence,
                "score": score,
            }
        )
    scored.sort(
        key=lambda row: (
            -row["score"],
            -row["edge"],
            str(row["market"].get("market_id") or ""),
        )
    )
    # Keep the best selection per market_id.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in scored:
        mid = str(row["market"].get("market_id") or "")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        unique.append(row)
    return unique


def _select_markets_for_budget(
    candidates: list[dict[str, Any]],
    *,
    total_exposure: float,
    risk_exposure: float,
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    max_positions = int(profile["max_positions"])
    max_per_game = int(profile["max_per_game"])
    max_position = min(
        risk_exposure,
        total_exposure * float(profile["max_position_pct"]),
    )
    max_position = max(1.0, max_position)

    picked: list[dict[str, Any]] = []
    game_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()

    for candidate in candidates:
        if len(picked) >= max_positions:
            break
        event_id = candidate["event_id"] or "unknown"
        market_type = candidate["market_type"] or "other"
        if game_counts[event_id] >= max_per_game:
            continue
        # Soft market-type diversification for conservative/balanced.
        if (
            len(picked) >= 3
            and type_counts[market_type] >= max(2, max_positions // 3)
            and len(type_counts) < 2
        ):
            continue
        picked.append(dict(candidate))
        game_counts[event_id] += 1
        type_counts[market_type] += 1

    if not picked:
        return []

    # Initial proportional stakes from score.
    raw_scores = [max(0.1, float(row["score"])) for row in picked]
    score_total = sum(raw_scores) or 1.0
    for row, score in zip(picked, raw_scores):
        row["exposure"] = total_exposure * (score / score_total)

    def _enforce_caps() -> None:
        for row in picked:
            row["exposure"] = min(
                float(row["exposure"]), max_position
            )
        by_game: dict[str, list[dict[str, Any]]] = {}
        for row in picked:
            by_game.setdefault(
                row["event_id"] or "unknown", []
            ).append(row)
        for rows in by_game.values():
            game_total = sum(float(row["exposure"]) for row in rows)
            if game_total <= risk_exposure + 1e-9:
                continue
            scale = risk_exposure / game_total
            for row in rows:
                row["exposure"] = float(row["exposure"]) * scale

    # Enforce position and per-game caps, then renormalize.
    for _ in range(10):
        _enforce_caps()
        allocated = sum(float(row["exposure"]) for row in picked)
        if allocated <= 0:
            break
        if abs(allocated - total_exposure) / total_exposure < 0.02:
            break
        # Scale toward budget, then re-apply caps next loop.
        scale = total_exposure / allocated
        for row in picked:
            row["exposure"] = float(row["exposure"]) * scale

    _enforce_caps()

    # Drop tiny leftovers under $1.
    picked = [
        row for row in picked if float(row.get("exposure") or 0.0) >= 1.0
    ]
    allocated = sum(float(row["exposure"]) for row in picked)
    if allocated > 0 and abs(allocated - total_exposure) > 0.5:
        # Final cents adjustment on the top score when room remains.
        delta = total_exposure - allocated
        ordered = sorted(
            picked, key=lambda row: -float(row["score"])
        )
        for top in ordered:
            if delta <= 0.01:
                break
            event_id = top["event_id"] or "unknown"
            game_total = sum(
                float(row["exposure"])
                for row in picked
                if (row["event_id"] or "unknown") == event_id
            )
            room = min(
                max_position - float(top["exposure"]),
                risk_exposure - game_total,
            )
            if room <= 0:
                continue
            add = min(delta, room)
            top["exposure"] = float(top["exposure"]) + add
            delta -= add

    _enforce_caps()
    for row in picked:
        row["exposure"] = round(float(row["exposure"]), 2)
    return picked


def _build_parlay_positions(
    candidates: list[dict[str, Any]],
    *,
    parlay_budget: float,
    risk_exposure: float,
    profile: dict[str, Any],
    game_exposure: Counter[str],
    risk_key: str,
) -> list[dict[str, Any]]:
    if parlay_budget < 1.0 or not candidates:
        return []

    size_weights = {
        key: float(value)
        for key, value in (profile.get("parlay_sizes") or {}).items()
        if float(value or 0.0) > 0
    }
    if not size_weights:
        return []

    weight_total = sum(size_weights.values()) or 1.0
    max_parlays = int(profile.get("max_parlays") or 2)
    max_position = max(
        1.0,
        min(
            risk_exposure,
            parlay_budget
            * float(profile.get("max_position_pct") or 0.28),
        ),
    )

    # Plan how many parlays of each size from weights.
    planned: list[str] = []
    for size, weight in sorted(
        size_weights.items(),
        key=lambda item: -item[1],
    ):
        share = weight / weight_total
        count = max(1, round(max_parlays * share)) if share >= 0.2 else (
            1 if share > 0 and max_parlays >= 3 else 0
        )
        if size == "large" and share <= 0:
            count = 0
        planned.extend([size] * count)
    planned = planned[:max_parlays]
    if not planned:
        # At least one small parlay when budget exists.
        planned = ["small"]

    # Equal stake per parlay from size-bucket budgets.
    size_budgets = {
        size: parlay_budget * (weight / weight_total)
        for size, weight in size_weights.items()
    }
    size_counts = Counter(planned)
    stake_by_size = {
        size: (
            size_budgets.get(size, 0.0) / count
            if count > 0
            else 0.0
        )
        for size, count in size_counts.items()
    }

    pool = list(candidates)
    used_in_parlays: set[str] = set()
    positions: list[dict[str, Any]] = []

    for size in planned:
        leg_count = _PARLAY_LEG_COUNTS.get(size, 2)
        legs = _pick_parlay_legs(
            pool,
            leg_count=leg_count,
            used_market_ids=used_in_parlays,
            prefer_unique_games=True,
        )
        if len(legs) < min(2, leg_count):
            continue
        stake = min(max_position, float(stake_by_size.get(size, 0.0)))
        if stake < 1.0:
            continue

        # Charge full stake against each leg's game for risk accounting.
        event_ids = [
            str(leg.get("event_id") or "unknown") for leg in legs
        ]
        if any(
            float(game_exposure.get(eid, 0.0)) + stake
            > risk_exposure + 1e-9
            for eid in event_ids
        ):
            # Try a smaller stake that fits.
            rooms = [
                risk_exposure - float(game_exposure.get(eid, 0.0))
                for eid in event_ids
            ]
            stake = min([stake, *rooms])
            if stake < 1.0:
                continue

        position = create_parlay_position(
            [leg["market"] for leg in legs],
            exposure=round(stake, 2),
            parlay_size=size,
            notes=(
                f"Generated {size} parlay · {risk_key} · "
                f"{len(legs)} legs"
            ),
        )
        positions.append(position)
        for leg in legs:
            mid = str(leg["market"].get("market_id") or "")
            if mid:
                used_in_parlays.add(mid)
            eid = str(leg.get("event_id") or "unknown")
            game_exposure[eid] += stake

    return positions


def _pick_parlay_legs(
    candidates: list[dict[str, Any]],
    *,
    leg_count: int,
    used_market_ids: set[str],
    prefer_unique_games: bool,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    used_events: set[str] = set()
    used_markets: set[str] = set(used_market_ids)

    def _try_pick(*, unique_games: bool) -> None:
        for candidate in candidates:
            if len(picked) >= leg_count:
                return
            mid = str(candidate["market"].get("market_id") or "")
            if not mid or mid in used_markets:
                continue
            event_id = str(candidate.get("event_id") or "")
            if unique_games and event_id and event_id in used_events:
                continue
            picked.append(candidate)
            used_markets.add(mid)
            if event_id:
                used_events.add(event_id)

    _try_pick(unique_games=prefer_unique_games)
    if len(picked) < leg_count:
        _try_pick(unique_games=False)
    return picked


def create_parlay_position(
    markets: list[dict[str, Any]],
    *,
    exposure: float,
    parlay_size: str = "small",
    notes: str | None = None,
    sportsbook: str | None = None,
) -> dict[str, Any]:
    """Build a multi-leg parlay portfolio position."""

    now = datetime.now(timezone.utc).isoformat()
    legs: list[dict[str, Any]] = []
    model_p = 1.0
    decimal_odds = 1.0
    confidences: list[str] = []

    for market in markets:
        price = num(market.get("price"))
        if price is None:
            price = -110.0
        leg_model = num(market.get("model_probability"))
        if leg_model is None:
            leg_model = 0.5
        model_p *= float(leg_model)
        decimal_odds *= _american_to_decimal(float(price))
        confidences.append(str(market.get("confidence") or "Low"))
        legs.append(
            {
                "market_id": str(market.get("market_id") or ""),
                "event_id": str(market.get("event_id") or ""),
                "event_label": market.get("event_label"),
                "home_team": market.get("home_team"),
                "away_team": market.get("away_team"),
                "market_type": market.get("market_type"),
                "selection": market.get("selection"),
                "line": num(market.get("line")),
                "price": price,
                "model_probability": leg_model,
                "market_probability": num(
                    market.get("market_probability")
                ),
                "confidence": market.get("confidence"),
            }
        )

    market_p = (1.0 / decimal_odds) if decimal_odds > 0 else None
    edge = None
    if market_p is not None:
        edge = round((float(model_p) - float(market_p)) * 100.0, 1)
    selection = " + ".join(
        str(leg.get("selection") or "Leg") for leg in legs
    )
    event_labels = []
    for leg in legs:
        label = leg.get("event_label")
        if label and label not in event_labels:
            event_labels.append(str(label))
    confidence = _majority_label(confidences) if confidences else "Low"
    size_key = str(parlay_size or "small").lower()
    if size_key not in _PARLAY_LEG_COUNTS:
        size_key = "small"

    return {
        "position_id": f"pos-{uuid.uuid4().hex[:12]}",
        "market_id": (
            "parlay:"
            + "|".join(
                str(leg.get("market_id") or "") for leg in legs
            )
        ),
        "event_id": legs[0].get("event_id") if legs else "",
        "event_label": " · ".join(event_labels[:3]) or "Parlay",
        "sport": "NFL",
        "home_team": None,
        "away_team": None,
        "market_type": "parlay",
        "selection": selection,
        "entry_price": _decimal_to_american(decimal_odds),
        "entry_line": None,
        "entry_timestamp": now,
        "current_price": _decimal_to_american(decimal_odds),
        "current_line": None,
        "model_probability": round(float(model_p), 4),
        "market_probability": (
            round(float(market_p), 4) if market_p is not None else None
        ),
        "edge": edge,
        "expected_value": None,
        "confidence": confidence,
        "exposure": float(exposure or 0.0),
        "status": "open",
        "sportsbook": sportsbook,
        "notes": notes,
        "closing_price": None,
        "closing_line": None,
        "result": None,
        "clv": None,
        "entry_model_probability": round(float(model_p), 4),
        "bet_type": "parlay",
        "parlay_size": size_key,
        "leg_count": len(legs),
        "legs": legs,
        "created_at": now,
        "updated_at": now,
    }


def _american_to_decimal(price: float) -> float:
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    # Treat missing / short prices as -110.
    return 1.0 + 100.0 / 110.0


def _decimal_to_american(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        return -110.0
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1.0) * 100.0, 1)
    return round(-100.0 / (decimal_odds - 1.0), 1)


def analyze_betting_portfolio(
    positions: list[dict[str, Any]],
    *,
    season: int | None = None,
    week: int | None = None,
    status_filter: str = "open",
) -> dict[str, Any]:
    """
    Refresh positions against the current slate and return
    portfolio analytics.
    """

    slate = build_betting_slate(season=season, week=week)
    markets_by_id = {
        str(market.get("market_id")): market
        for market in (slate.get("markets") or [])
        if market.get("market_id")
    }
    events_by_id = {
        str(event.get("event_id")): event
        for event in (slate.get("events") or [])
        if event.get("event_id")
    }

    refreshed: list[dict[str, Any]] = []
    for raw in positions or []:
        position = _normalize_position(raw)
        if str(position.get("bet_type") or "single") == "parlay":
            position = _refresh_parlay_position(
                position, markets_by_id=markets_by_id
            )
        else:
            market = markets_by_id.get(position["market_id"])
            event = events_by_id.get(position["event_id"])
            if market:
                position = _apply_market_snapshot(
                    position, market, event
                )
        refreshed.append(position)

    # Auto-apply final game outcomes to open singles.
    settled_by_market = _load_settled_market_map(
        season=slate.get("season"),
        week=slate.get("week"),
    )
    if settled_by_market:
        for position in refreshed:
            if str(position.get("status") or "open").lower() != "open":
                continue
            if str(position.get("bet_type") or "single") == "parlay":
                continue
            settled = settled_by_market.get(
                str(position.get("market_id") or "")
            )
            if not settled:
                continue
            position["status"] = settled.get("result") or position["status"]
            position["result"] = settled.get("result")
            position["closing_line"] = settled.get("closing_line")
            position["closing_price"] = position.get("current_price")
            position["clv"] = _position_clv(position)
            position["notes"] = (
                (position.get("notes") or "")
                + (
                    " · Auto-settled from final score"
                    if "Auto-settled" not in str(position.get("notes") or "")
                    else ""
                )
            ).strip(" ·")

    if status_filter and status_filter != "all":
        visible = [
            row
            for row in refreshed
            if str(row.get("status") or "open").lower()
            == status_filter.lower()
        ]
    else:
        visible = list(refreshed)

    open_rows = [
        row
        for row in refreshed
        if str(row.get("status") or "open").lower() == "open"
    ]
    settled_rows = [
        row
        for row in refreshed
        if str(row.get("status") or "").lower()
        in {"won", "lost", "push", "void", "cancelled"}
    ]

    analytics = _build_analytics(visible)
    results = _build_results_summary(settled_rows)

    return {
        "portfolio_id": f"bp-{slate.get('slate_id') or 'local'}",
        "season": slate.get("season"),
        "week": slate.get("week"),
        "slate_id": slate.get("slate_id"),
        "status_filter": status_filter,
        "positions": refreshed,
        "visible_positions": visible,
        "analytics": analytics,
        "results": results,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_settled_market_map(
    *,
    season: int | None,
    week: int | None,
) -> dict[str, dict[str, Any]]:
    try:
        from app.canonical.fact_betting_results import (
            load_market_results,
        )

        rows = load_market_results(season=season, week=week)
    except Exception:
        return {}
    return {
        str(row.get("market_id")): row
        for row in rows
        if row.get("market_id") and row.get("result")
    }


def create_position_from_market(
    market: dict[str, Any],
    *,
    exposure: float = 25.0,
    notes: str | None = None,
    sportsbook: str | None = None,
    entry_price: float | None = None,
    entry_line: float | None = None,
) -> dict[str, Any]:
    """Build a portfolio position from a canonical betting market."""

    now = datetime.now(timezone.utc).isoformat()
    price = (
        float(entry_price)
        if entry_price is not None
        else num(market.get("price"))
    )
    line = (
        float(entry_line)
        if entry_line is not None
        else num(market.get("line"))
    )
    return {
        "position_id": f"pos-{uuid.uuid4().hex[:12]}",
        "market_id": str(market.get("market_id") or ""),
        "event_id": str(market.get("event_id") or ""),
        "event_label": market.get("event_label"),
        "sport": market.get("sport") or "NFL",
        "home_team": market.get("home_team"),
        "away_team": market.get("away_team"),
        "market_type": market.get("market_type"),
        "selection": market.get("selection"),
        "entry_price": price,
        "entry_line": line,
        "entry_timestamp": now,
        "current_price": num(market.get("price")),
        "current_line": num(market.get("line")),
        "model_probability": num(market.get("model_probability")),
        "market_probability": num(market.get("market_probability")),
        "edge": num(market.get("edge_probability"))
        if market.get("edge_probability") is not None
        else num(market.get("edge")),
        "expected_value": num(market.get("expected_value")),
        "confidence": market.get("confidence") or "Low",
        "exposure": float(exposure or 0.0),
        "status": "open",
        "sportsbook": sportsbook,
        "notes": notes,
        "closing_price": None,
        "closing_line": None,
        "result": None,
        "clv": None,
        "entry_model_probability": num(
            market.get("model_probability")
        ),
        "bet_type": "single",
        "parlay_size": None,
        "leg_count": 1,
        "legs": [],
        "created_at": now,
        "updated_at": now,
    }


def _normalize_position(raw: dict[str, Any]) -> dict[str, Any]:
    position_id = str(
        raw.get("position_id") or f"pos-{uuid.uuid4().hex[:12]}"
    )
    now = datetime.now(timezone.utc).isoformat()
    return {
        "position_id": position_id,
        "market_id": str(raw.get("market_id") or ""),
        "event_id": str(raw.get("event_id") or ""),
        "event_label": raw.get("event_label"),
        "sport": raw.get("sport") or "NFL",
        "home_team": raw.get("home_team"),
        "away_team": raw.get("away_team"),
        "market_type": raw.get("market_type"),
        "selection": raw.get("selection"),
        "entry_price": num(raw.get("entry_price")),
        "entry_line": num(raw.get("entry_line")),
        "entry_timestamp": raw.get("entry_timestamp") or now,
        "current_price": num(raw.get("current_price")),
        "current_line": num(raw.get("current_line")),
        "model_probability": num(raw.get("model_probability")),
        "market_probability": num(raw.get("market_probability")),
        "edge": num(raw.get("edge")),
        "expected_value": num(raw.get("expected_value")),
        "confidence": raw.get("confidence") or "Low",
        "exposure": float(num(raw.get("exposure")) or 0.0),
        "status": str(raw.get("status") or "open").lower(),
        "sportsbook": raw.get("sportsbook"),
        "notes": raw.get("notes"),
        "closing_price": num(raw.get("closing_price")),
        "closing_line": num(raw.get("closing_line")),
        "result": raw.get("result"),
        "clv": num(raw.get("clv")),
        "entry_model_probability": num(
            raw.get("entry_model_probability")
        ),
        "bet_type": str(raw.get("bet_type") or "single").lower(),
        "parlay_size": raw.get("parlay_size"),
        "leg_count": int(raw.get("leg_count") or 1),
        "legs": list(raw.get("legs") or []),
        "created_at": raw.get("created_at") or now,
        "updated_at": now,
        "price_movement": None,
        "model_change": None,
        "assumption_tags": [],
    }


def _apply_market_snapshot(
    position: dict[str, Any],
    market: dict[str, Any],
    event: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(position)
    out["event_label"] = (
        market.get("event_label")
        or out.get("event_label")
        or (event or {}).get("label")
    )
    out["home_team"] = market.get("home_team") or out.get("home_team")
    out["away_team"] = market.get("away_team") or out.get("away_team")
    out["market_type"] = (
        market.get("market_type") or out.get("market_type")
    )
    out["selection"] = market.get("selection") or out.get("selection")
    out["current_price"] = num(market.get("price"))
    out["current_line"] = num(market.get("line"))
    out["model_probability"] = num(market.get("model_probability"))
    out["market_probability"] = num(market.get("market_probability"))
    edge = num(market.get("edge_probability"))
    if edge is None:
        edge = num(market.get("edge"))
    out["edge"] = edge
    out["expected_value"] = num(market.get("expected_value"))
    out["confidence"] = market.get("confidence") or out.get(
        "confidence"
    )

    entry_price = num(out.get("entry_price"))
    current_price = num(out.get("current_price"))
    if entry_price is not None and current_price is not None:
        out["price_movement"] = round(current_price - entry_price, 1)

    entry_model = num(out.get("entry_model_probability"))
    current_model = num(out.get("model_probability"))
    if entry_model is not None and current_model is not None:
        delta = round((current_model - entry_model) * 100.0, 1)
        out["model_change"] = delta

    out["assumption_tags"] = _assumption_tags(out, event)
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out


def _refresh_parlay_position(
    position: dict[str, Any],
    *,
    markets_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    legs = list(position.get("legs") or [])
    if not legs:
        position["assumption_tags"] = _assumption_tags(position, None)
        return position

    refreshed_legs: list[dict[str, Any]] = []
    model_p = 1.0
    decimal_odds = 1.0
    confidences: list[str] = []
    for leg in legs:
        market = markets_by_id.get(str(leg.get("market_id") or ""))
        row = dict(leg)
        if market:
            row["price"] = num(market.get("price"))
            row["line"] = num(market.get("line"))
            row["model_probability"] = num(
                market.get("model_probability")
            )
            row["market_probability"] = num(
                market.get("market_probability")
            )
            row["confidence"] = market.get("confidence")
            row["selection"] = market.get("selection") or row.get(
                "selection"
            )
            row["event_label"] = market.get("event_label") or row.get(
                "event_label"
            )
        price = num(row.get("price"))
        if price is None:
            price = -110.0
        leg_model = num(row.get("model_probability"))
        if leg_model is None:
            leg_model = 0.5
        model_p *= float(leg_model)
        decimal_odds *= _american_to_decimal(float(price))
        confidences.append(str(row.get("confidence") or "Low"))
        refreshed_legs.append(row)

    market_p = (1.0 / decimal_odds) if decimal_odds > 0 else None
    out = dict(position)
    out["legs"] = refreshed_legs
    out["leg_count"] = len(refreshed_legs)
    out["current_price"] = _decimal_to_american(decimal_odds)
    out["model_probability"] = round(float(model_p), 4)
    out["market_probability"] = (
        round(float(market_p), 4) if market_p is not None else None
    )
    if market_p is not None:
        out["edge"] = round(
            (float(model_p) - float(market_p)) * 100.0, 1
        )
    out["confidence"] = (
        _majority_label(confidences) if confidences else "Low"
    )
    out["selection"] = " + ".join(
        str(leg.get("selection") or "Leg") for leg in refreshed_legs
    )
    entry_price = num(out.get("entry_price"))
    current_price = num(out.get("current_price"))
    if entry_price is not None and current_price is not None:
        out["price_movement"] = round(
            current_price - entry_price, 1
        )
    entry_model = num(out.get("entry_model_probability"))
    current_model = num(out.get("model_probability"))
    if entry_model is not None and current_model is not None:
        out["model_change"] = round(
            (current_model - entry_model) * 100.0, 1
        )
    out["assumption_tags"] = _assumption_tags(out, None)
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out


def _assumption_tags(
    position: dict[str, Any],
    event: dict[str, Any] | None,
) -> list[str]:
    if str(position.get("bet_type") or "single") == "parlay":
        tags: list[str] = [
            f"{position.get('parlay_size') or 'small'} parlay"
        ]
        for leg in position.get("legs") or []:
            tags.extend(
                _assumption_tags(
                    {**leg, "bet_type": "single", "legs": []},
                    None,
                )
            )
        seen: set[str] = set()
        unique: list[str] = []
        for tag in tags:
            if tag in seen:
                continue
            seen.add(tag)
            unique.append(tag)
        return unique[:10]

    tags = []
    market_type = str(position.get("market_type") or "").lower()
    selection = str(position.get("selection") or "").upper()
    home = str(position.get("home_team") or "").upper()
    away = str(position.get("away_team") or "").upper()

    # Team lean from selection.
    team = None
    if home and selection.startswith(home):
        team = home
    elif away and selection.startswith(away):
        team = away

    if market_type == "spread" and team:
        tags.append(f"{team} covers / wins outright")
        tags.append(f"{team} offensive efficiency")
    elif market_type == "moneyline" and team:
        tags.append(f"{team} wins outright")
        tags.append(f"{team} offensive efficiency")
    elif market_type == "total":
        if "OVER" in selection or selection.startswith("O"):
            tags.append("High-scoring game")
            if home:
                tags.append(f"{home} scoring volume")
            if away:
                tags.append(f"{away} scoring volume")
        elif "UNDER" in selection or selection.startswith("U"):
            tags.append("Low-scoring game")
            tags.append("Defensive / field-position game")
        else:
            tags.append("Game total environment")
    else:
        if team:
            tags.append(f"{team} game environment")
        tags.append("Player / prop outcome")

    if event:
        label = (
            f"{event.get('away_team') or away} @ "
            f"{event.get('home_team') or home}"
        ).strip(" @")
        if label and label != "@":
            tags.append(f"{label} game environment")

    # De-dupe preserving order.
    seen = set()
    unique = []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        unique.append(tag)
    return unique


def _build_analytics(positions: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(positions)
    total_exposure = sum(
        float(row.get("exposure") or 0.0) for row in positions
    )
    edges = [
        float(row["edge"])
        for row in positions
        if num(row.get("edge")) is not None
    ]
    avg_edge = (
        round(sum(edges) / len(edges), 2) if edges else None
    )
    confidences = [
        str(row.get("confidence") or "Low") for row in positions
    ]
    avg_confidence = _majority_label(confidences) if confidences else None

    team_exposure = _team_exposure(positions, total_exposure)
    game_exposure = _game_exposure(positions, total_exposure)
    market_exposure = _market_exposure(positions, total_exposure)
    sport_exposure = _sport_exposure(positions, total_exposure)
    correlations = _correlation_pairs(positions)
    assumptions = _portfolio_assumptions(positions)
    alerts = _portfolio_alerts(
        positions,
        team_exposure=team_exposure,
        game_exposure=game_exposure,
        market_exposure=market_exposure,
        correlations=correlations,
    )
    health = _portfolio_health(
        positions,
        team_exposure=team_exposure,
        game_exposure=game_exposure,
        market_exposure=market_exposure,
        correlations=correlations,
        avg_edge=avg_edge,
    )
    model_vs_market = _model_vs_market(positions)
    edge_distribution = _edge_distribution(edges)
    confidence_distribution = _confidence_distribution(confidences)
    price_movements = [
        {
            "position_id": row["position_id"],
            "selection": row.get("selection"),
            "entry_price": row.get("entry_price"),
            "current_price": row.get("current_price"),
            "movement": row.get("price_movement"),
        }
        for row in positions
        if row.get("price_movement") is not None
    ]

    games_represented = len(
        {
            game["event_id"]
            for row in positions
            for game in _position_games(row)
            if game.get("event_id")
        }
    )
    correlation_label = _correlation_label(correlations, n)

    return {
        "summary": {
            "open_positions": n,
            "total_exposure": round(total_exposure, 2),
            "average_model_edge": avg_edge,
            "average_confidence": avg_confidence,
            "games_represented": games_represented,
            "correlation": correlation_label,
        },
        "health": health,
        "alerts": alerts,
        "exposure": {
            "team": team_exposure,
            "game": game_exposure,
            "sport": sport_exposure,
            "market": market_exposure,
        },
        "correlations": correlations,
        "assumptions": assumptions,
        "model_vs_market": model_vs_market,
        "edge_distribution": edge_distribution,
        "confidence_distribution": confidence_distribution,
        "price_movements": price_movements,
        "signals": [alert["signal_id"] for alert in alerts],
    }


def _team_exposure(
    positions: list[dict[str, Any]],
    total_exposure: float,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in positions:
        teams = _position_teams(row)
        share = float(row.get("exposure") or 0.0) / max(
            len(teams), 1
        )
        for team in teams:
            bucket = buckets.setdefault(
                team,
                {"team": team, "positions": 0, "exposure": 0.0},
            )
            bucket["positions"] += 1
            bucket["exposure"] += share
    return _pct_rows(list(buckets.values()), total_exposure, "team")


def _game_exposure(
    positions: list[dict[str, Any]],
    total_exposure: float,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in positions:
        games = _position_games(row)
        share = float(row.get("exposure") or 0.0) / max(
            len(games), 1
        )
        for game in games:
            key = str(game["event_id"] or "unknown")
            bucket = buckets.setdefault(
                key,
                {
                    "event_id": key,
                    "game": game["label"],
                    "positions": 0,
                    "exposure": 0.0,
                },
            )
            bucket["positions"] += 1
            bucket["exposure"] += share
    return _pct_rows(list(buckets.values()), total_exposure, "game")


def _market_exposure(
    positions: list[dict[str, Any]],
    total_exposure: float,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in positions:
        if str(row.get("bet_type") or "single") == "parlay":
            key = "parlay"
        else:
            key = str(row.get("market_type") or "other").lower()
        bucket = buckets.setdefault(
            key,
            {"market": key, "positions": 0, "exposure": 0.0},
        )
        bucket["positions"] += 1
        bucket["exposure"] += float(row.get("exposure") or 0.0)
    return _pct_rows(list(buckets.values()), total_exposure, "market")


def _sport_exposure(
    positions: list[dict[str, Any]],
    total_exposure: float,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in positions:
        key = str(row.get("sport") or "NFL").upper()
        bucket = buckets.setdefault(
            key,
            {"sport": key, "positions": 0, "exposure": 0.0},
        )
        bucket["positions"] += 1
        bucket["exposure"] += float(row.get("exposure") or 0.0)
    return _pct_rows(list(buckets.values()), total_exposure, "sport")


def _pct_rows(
    rows: list[dict[str, Any]],
    total_exposure: float,
    sort_key: str,
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        exposure = float(row.get("exposure") or 0.0)
        pct = (
            round(100.0 * exposure / total_exposure, 1)
            if total_exposure > 0
            else 0.0
        )
        out.append(
            {
                **row,
                "exposure": round(exposure, 2),
                "exposure_pct": pct,
            }
        )
    out.sort(
        key=lambda item: (
            -float(item.get("exposure_pct") or 0.0),
            str(item.get(sort_key) or ""),
        )
    )
    return out


def _position_teams(position: dict[str, Any]) -> list[str]:
    if str(position.get("bet_type") or "single") == "parlay":
        teams: list[str] = []
        for leg in position.get("legs") or []:
            for team in _position_teams(
                {
                    **leg,
                    "bet_type": "single",
                    "legs": [],
                }
            ):
                if team not in teams:
                    teams.append(team)
        return teams

    home = str(position.get("home_team") or "").upper()
    away = str(position.get("away_team") or "").upper()
    selection = str(position.get("selection") or "").upper()
    market_type = str(position.get("market_type") or "").lower()

    if market_type == "total":
        return [team for team in (away, home) if team]

    if home and selection.startswith(home):
        return [home]
    if away and selection.startswith(away):
        return [away]
    return [team for team in (away, home) if team]


def _position_games(position: dict[str, Any]) -> list[dict[str, str]]:
    if str(position.get("bet_type") or "single") == "parlay":
        games: list[dict[str, str]] = []
        seen: set[str] = set()
        for leg in position.get("legs") or []:
            key = str(
                leg.get("event_id")
                or leg.get("event_label")
                or "unknown"
            )
            if key in seen:
                continue
            seen.add(key)
            label = str(
                leg.get("event_label")
                or f"{leg.get('away_team') or '?'} @ "
                f"{leg.get('home_team') or '?'}"
            )
            games.append({"event_id": key, "label": label})
        return games or [
            {
                "event_id": str(position.get("event_id") or "unknown"),
                "label": str(position.get("event_label") or "Parlay"),
            }
        ]

    key = str(
        position.get("event_id")
        or position.get("event_label")
        or "unknown"
    )
    label = str(
        position.get("event_label")
        or f"{position.get('away_team') or '?'} @ "
        f"{position.get('home_team') or '?'}"
    )
    return [{"event_id": key, "label": label}]


def _correlation_pairs(
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for index, left in enumerate(positions):
        for right in positions[index + 1 :]:
            score, reasons = _pair_correlation(left, right)
            if score < 0.35:
                continue
            pairs.append(
                {
                    "left_position_id": left["position_id"],
                    "right_position_id": right["position_id"],
                    "left_selection": left.get("selection"),
                    "right_selection": right.get("selection"),
                    "score": round(score, 2),
                    "label": _score_label(score),
                    "reasons": reasons,
                }
            )
    pairs.sort(key=lambda row: (-row["score"], row["left_selection"] or ""))
    return pairs[:24]


def _pair_correlation(
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    same_event = (
        left.get("event_id")
        and left.get("event_id") == right.get("event_id")
    )
    if same_event:
        score += 0.45
        reasons.append("Same game environment")

    left_teams = set(_position_teams(left))
    right_teams = set(_position_teams(right))
    shared_teams = left_teams & right_teams
    if shared_teams:
        score += 0.25
        reasons.append(
            f"Shared team exposure ({', '.join(sorted(shared_teams))})"
        )

    left_tags = set(left.get("assumption_tags") or [])
    right_tags = set(right.get("assumption_tags") or [])
    shared_tags = left_tags & right_tags
    # Ignore generic game-environment tag for assumption overlap.
    shared_tags = {
        tag
        for tag in shared_tags
        if "game environment" not in tag.lower()
        or "offensive" in tag.lower()
        or "scoring" in tag.lower()
    }
    if shared_tags:
        score += min(0.35, 0.12 * len(shared_tags))
        reasons.append(
            "Shared assumption: " + "; ".join(sorted(shared_tags)[:2])
        )

    if (
        left.get("market_type")
        and left.get("market_type") == right.get("market_type")
        and same_event
    ):
        score += 0.1
        reasons.append(
            f"Same market type ({left.get('market_type')})"
        )

    return min(1.0, score), reasons


def _portfolio_assumptions(
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in positions:
        for tag in row.get("assumption_tags") or []:
            if "game environment" in tag.lower() and "offensive" not in tag.lower():
                # Prefer more specific assumptions in the panel.
                continue
            counts[tag] += 1
    rows = [
        {
            "assumption": name,
            "positions": count,
        }
        for name, count in counts.most_common(12)
        if count >= 1
    ]
    return rows


def _portfolio_alerts(
    positions: list[dict[str, Any]],
    *,
    team_exposure: list[dict[str, Any]],
    game_exposure: list[dict[str, Any]],
    market_exposure: list[dict[str, Any]],
    correlations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    n = len(positions)
    if n == 0:
        return alerts

    if game_exposure:
        top = game_exposure[0]
        if (
            top.get("exposure_pct", 0) >= 40
            or top.get("positions", 0) >= max(3, math.ceil(n * 0.5))
        ):
            alerts.append(
                {
                    "signal_id": "HIGH_GAME_CONCENTRATION",
                    "title": "Portfolio Concentration",
                    "body": (
                        f"{top.get('positions')} of your {n} positions "
                        f"are connected to {top.get('game')} "
                        f"({top.get('exposure_pct')}% exposure)."
                    ),
                    "severity": "View Exposure",
                }
            )

    if team_exposure:
        top = team_exposure[0]
        if top.get("exposure_pct", 0) >= 35:
            alerts.append(
                {
                    "signal_id": "HIGH_TEAM_CONCENTRATION",
                    "title": "Team Concentration",
                    "body": (
                        f"{top.get('exposure_pct')}% of portfolio "
                        f"exposure is connected to {top.get('team')}."
                    ),
                    "cta": "View Exposure",
                }
            )

    if market_exposure:
        top = market_exposure[0]
        if top.get("exposure_pct", 0) >= 60:
            alerts.append(
                {
                    "signal_id": "MARKET_CONCENTRATION",
                    "title": "Market Concentration",
                    "body": (
                        f"{top.get('exposure_pct')}% of exposure is in "
                        f"{top.get('market')} markets."
                    ),
                    "cta": "View Exposure",
                }
            )

    high_corr = [
        row for row in correlations if row.get("score", 0) >= 0.7
    ]
    if len(high_corr) >= 2:
        alerts.append(
            {
                "signal_id": "HIGH_CORRELATION",
                "title": "Correlation",
                "body": (
                    f"{len(high_corr)} position pairs share similar "
                    "game-environment drivers."
                ),
                "cta": "View Correlation",
            }
        )

    moved = [
        row
        for row in positions
        if abs(float(row.get("price_movement") or 0.0)) >= 15
    ]
    if moved:
        alerts.append(
            {
                "signal_id": "PRICE_MOVEMENT",
                "title": "Price Change",
                "body": (
                    f"{len(moved)} position"
                    f"{'' if len(moved) == 1 else 's'} moved "
                    "materially since entry."
                ),
                "cta": "View Movement",
            }
        )

    model_changed = [
        row
        for row in positions
        if abs(float(row.get("model_change") or 0.0)) >= 3.0
    ]
    if model_changed:
        alerts.append(
            {
                "signal_id": "MODEL_CHANGE",
                "title": "Model Update",
                "body": (
                    f"InsightPilot probability moved by ≥3 pts on "
                    f"{len(model_changed)} position"
                    f"{'' if len(model_changed) == 1 else 's'}."
                ),
                "cta": "Review Positions",
            }
        )

    if (
        n >= 4
        and (game_exposure[0].get("exposure_pct") if game_exposure else 100)
        < 35
        and (team_exposure[0].get("exposure_pct") if team_exposure else 100)
        < 35
    ):
        alerts.append(
            {
                "signal_id": "DIVERSE_EXPOSURE",
                "title": "Diverse Exposure",
                "body": (
                    "Portfolio positions span multiple games and "
                    "are not dominated by one team."
                ),
                "cta": None,
            }
        )

    return alerts


def _portfolio_health(
    positions: list[dict[str, Any]],
    *,
    team_exposure: list[dict[str, Any]],
    game_exposure: list[dict[str, Any]],
    market_exposure: list[dict[str, Any]],
    correlations: list[dict[str, Any]],
    avg_edge: float | None,
) -> list[dict[str, Any]]:
    n = max(len(positions), 1)
    top_team = (
        float(team_exposure[0]["exposure_pct"]) if team_exposure else 0.0
    )
    top_game = (
        float(game_exposure[0]["exposure_pct"]) if game_exposure else 0.0
    )
    top_market = (
        float(market_exposure[0]["exposure_pct"])
        if market_exposure
        else 0.0
    )
    high_corr = sum(
        1 for row in correlations if row.get("score", 0) >= 0.7
    )

    return [
        {
            "id": "market_diversification",
            "label": "Market Diversification",
            "value": _invert_concentration(top_market),
            "detail": f"Top market type is {top_market:.0f}% of exposure.",
        },
        {
            "id": "game_diversification",
            "label": "Game Diversification",
            "value": _invert_concentration(top_game),
            "detail": f"Top game is {top_game:.0f}% of exposure.",
        },
        {
            "id": "team_concentration",
            "label": "Team Concentration",
            "value": _concentration_label(top_team),
            "detail": f"Top team is {top_team:.0f}% of exposure.",
        },
        {
            "id": "sport_diversification",
            "label": "Sport Diversification",
            "value": "Low" if n else "—",
            "detail": "NFL-only MVP portfolio.",
        },
        {
            "id": "correlation",
            "label": "Correlation",
            "value": _correlation_label(correlations, n),
            "detail": (
                f"{high_corr} highly correlated pair"
                f"{'' if high_corr == 1 else 's'}."
            ),
        },
        {
            "id": "model_edge",
            "label": "Model Edge",
            "value": (
                "Positive"
                if avg_edge is not None and avg_edge > 0.5
                else "Neutral"
                if avg_edge is not None and abs(avg_edge) <= 0.5
                else "Negative"
                if avg_edge is not None
                else "—"
            ),
            "detail": (
                f"Average model edge {avg_edge:+.1f} pts."
                if avg_edge is not None
                else "No edge available."
            ),
        },
    ]


def _model_vs_market(positions: list[dict[str, Any]]) -> dict[str, Any]:
    model = [
        float(row["model_probability"]) * 100.0
        for row in positions
        if num(row.get("model_probability")) is not None
    ]
    market = [
        float(row["market_probability"]) * 100.0
        for row in positions
        if num(row.get("market_probability")) is not None
    ]
    edges = [
        float(row["edge"])
        for row in positions
        if num(row.get("edge")) is not None
    ]
    avg_model = round(sum(model) / len(model), 1) if model else None
    avg_market = round(sum(market) / len(market), 1) if market else None
    return {
        "average_market_probability": avg_market,
        "average_model_probability": avg_model,
        "average_difference": (
            round(avg_model - avg_market, 1)
            if avg_model is not None and avg_market is not None
            else None
        ),
        "average_edge": (
            round(sum(edges) / len(edges), 2) if edges else None
        ),
    }


def _edge_distribution(edges: list[float]) -> list[dict[str, Any]]:
    buckets = [
        ("0–2%", 0.0, 2.0),
        ("2–4%", 2.0, 4.0),
        ("4–6%", 4.0, 6.0),
        ("6–8%", 6.0, 8.0),
        ("8%+", 8.0, None),
    ]
    out = []
    for label, low, high in buckets:
        count = 0
        for edge in edges:
            value = abs(float(edge))
            if high is None:
                if value >= low:
                    count += 1
            elif low <= value < high:
                count += 1
        out.append({"bucket": label, "count": count})
    return out


def _confidence_distribution(
    confidences: list[str],
) -> list[dict[str, Any]]:
    total = max(len(confidences), 1)
    counts = Counter(confidences)
    order = ["High", "Moderate", "Low"]
    return [
        {
            "confidence": label,
            "count": counts.get(label, 0),
            "pct": round(100.0 * counts.get(label, 0) / total, 1),
        }
        for label in order
    ]


def _build_results_summary(
    settled: list[dict[str, Any]],
) -> dict[str, Any]:
    note = (
        "Historical results are descriptive and subject to "
        "sample size and variance."
    )
    if not settled:
        return {
            "total_positions": 0,
            "won": 0,
            "lost": 0,
            "push": 0,
            "void": 0,
            "win_rate": None,
            "total_exposure": 0.0,
            "profit_loss": 0.0,
            "roi_pct": None,
            "average_odds": None,
            "average_model_edge": None,
            "average_clv": None,
            "by_market": [],
            "by_confidence": [],
            "by_bet_type": [],
            "calibration": [],
            "settled_positions": [],
            "note": (
                "Settled results will appear here once positions "
                "are marked Won / Lost / Push on the Portfolio tab."
            ),
        }

    enriched: list[dict[str, Any]] = []
    for row in settled:
        item = dict(row)
        item["profit_loss"] = _position_pnl(row)
        item["clv_points"] = _position_clv(row)
        enriched.append(item)

    won = sum(1 for row in enriched if row.get("status") == "won")
    lost = sum(1 for row in enriched if row.get("status") == "lost")
    push = sum(1 for row in enriched if row.get("status") == "push")
    voided = sum(
        1
        for row in enriched
        if row.get("status") in {"void", "cancelled"}
    )
    decided = won + lost
    total_exposure = sum(
        float(row.get("exposure") or 0.0) for row in enriched
    )
    profit_loss = round(
        sum(float(row.get("profit_loss") or 0.0) for row in enriched),
        2,
    )
    edges = [
        float(row["edge"])
        for row in enriched
        if num(row.get("edge")) is not None
    ]
    odds = [
        float(row["entry_price"])
        for row in enriched
        if num(row.get("entry_price")) is not None
    ]
    clvs = [
        float(row["clv_points"])
        for row in enriched
        if num(row.get("clv_points")) is not None
    ]

    return {
        "total_positions": len(enriched),
        "won": won,
        "lost": lost,
        "push": push,
        "void": voided,
        "win_rate": (
            round(100.0 * won / decided, 1) if decided else None
        ),
        "total_exposure": round(total_exposure, 2),
        "profit_loss": profit_loss,
        "roi_pct": (
            round(100.0 * profit_loss / total_exposure, 1)
            if total_exposure > 0
            else None
        ),
        "average_odds": (
            round(sum(odds) / len(odds), 1) if odds else None
        ),
        "average_model_edge": (
            round(sum(edges) / len(edges), 2) if edges else None
        ),
        "average_clv": (
            round(sum(clvs) / len(clvs), 2) if clvs else None
        ),
        "by_market": _results_breakdown(
            enriched, key_fn=_results_market_key
        ),
        "by_confidence": _results_breakdown(
            enriched,
            key_fn=lambda row: str(row.get("confidence") or "Low"),
        ),
        "by_bet_type": _results_breakdown(
            enriched,
            key_fn=lambda row: str(row.get("bet_type") or "single"),
        ),
        "calibration": _calibration_buckets(enriched),
        "settled_positions": sorted(
            enriched,
            key=lambda row: str(
                row.get("updated_at") or row.get("created_at") or ""
            ),
            reverse=True,
        ),
        "note": note,
    }


def _results_market_key(row: dict[str, Any]) -> str:
    if str(row.get("bet_type") or "single") == "parlay":
        return "parlay"
    return str(row.get("market_type") or "other").lower()


def _results_breakdown(
    rows: list[dict[str, Any]],
    *,
    key_fn,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[key_fn(row)].append(row)
    out: list[dict[str, Any]] = []
    for key, items in buckets.items():
        won = sum(1 for row in items if row.get("status") == "won")
        lost = sum(1 for row in items if row.get("status") == "lost")
        decided = won + lost
        exposure = sum(float(row.get("exposure") or 0.0) for row in items)
        pnl = sum(float(row.get("profit_loss") or 0.0) for row in items)
        edges = [
            float(row["edge"])
            for row in items
            if num(row.get("edge")) is not None
        ]
        out.append(
            {
                "key": key,
                "bets": len(items),
                "won": won,
                "lost": lost,
                "win_rate": (
                    round(100.0 * won / decided, 1)
                    if decided
                    else None
                ),
                "exposure": round(exposure, 2),
                "profit_loss": round(pnl, 2),
                "roi_pct": (
                    round(100.0 * pnl / exposure, 1)
                    if exposure > 0
                    else None
                ),
                "average_edge": (
                    round(sum(edges) / len(edges), 2)
                    if edges
                    else None
                ),
            }
        )
    out.sort(key=lambda row: (-row["bets"], row["key"]))
    return out


def _calibration_buckets(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Predicted probability bands vs observed win rate."""

    bands = [
        ("50–55%", 0.50, 0.55),
        ("55–60%", 0.55, 0.60),
        ("60–65%", 0.60, 0.65),
        ("65–70%", 0.65, 0.70),
        ("70%+", 0.70, 1.01),
    ]
    out: list[dict[str, Any]] = []
    for label, low, high in bands:
        bucket = [
            row
            for row in rows
            if row.get("status") in {"won", "lost"}
            and num(row.get("model_probability")) is not None
            and low
            <= float(row["model_probability"])
            < high
        ]
        if not bucket:
            out.append(
                {
                    "bucket": label,
                    "bets": 0,
                    "predicted_midpoint": round(
                        100.0 * ((low + min(high, 1.0)) / 2.0), 1
                    ),
                    "actual_win_rate": None,
                }
            )
            continue
        won = sum(1 for row in bucket if row.get("status") == "won")
        out.append(
            {
                "bucket": label,
                "bets": len(bucket),
                "predicted_midpoint": round(
                    100.0 * ((low + min(high, 1.0)) / 2.0), 1
                ),
                "actual_win_rate": round(
                    100.0 * won / len(bucket), 1
                ),
            }
        )
    return out


def _position_pnl(row: dict[str, Any]) -> float:
    status = str(row.get("status") or "").lower()
    stake = float(row.get("exposure") or 0.0)
    if status in {"push", "void", "cancelled"}:
        return 0.0
    if status == "lost":
        return round(-stake, 2)
    if status != "won":
        return 0.0
    price = num(row.get("entry_price"))
    if price is None:
        price = -110.0
    price = float(price)
    if price >= 100:
        return round(stake * (price / 100.0), 2)
    if price <= -100:
        return round(stake * (100.0 / abs(price)), 2)
    return round(stake * (100.0 / 110.0), 2)


def _position_clv(row: dict[str, Any]) -> float | None:
    """
    Closing-line value proxy:
    - spreads/totals: entry_line vs closing_line (points)
    - otherwise: entry_price vs closing_price (American cents)
    Stored ``clv`` wins when already present.
    """

    stored = num(row.get("clv"))
    if stored is not None:
        return float(stored)
    entry_line = num(row.get("entry_line"))
    closing_line = num(row.get("closing_line"))
    if entry_line is not None and closing_line is not None:
        # Favorable CLV if closing moves toward the bet.
        return round(float(closing_line) - float(entry_line), 2)
    entry_price = num(row.get("entry_price"))
    closing_price = num(row.get("closing_price"))
    if entry_price is not None and closing_price is not None:
        return round(float(closing_price) - float(entry_price), 1)
    return None


def _majority_label(values: list[str]) -> str:
    if not values:
        return "—"
    return Counter(values).most_common(1)[0][0]


def _invert_concentration(top_pct: float) -> str:
    if top_pct >= 70:
        return "Low"
    if top_pct >= 45:
        return "Moderate"
    return "High"


def _concentration_label(top_pct: float) -> str:
    if top_pct >= 45:
        return "High"
    if top_pct >= 25:
        return "Moderate"
    return "Low"


def _correlation_label(
    correlations: list[dict[str, Any]],
    position_count: int,
) -> str:
    if position_count < 2:
        return "—"
    high = sum(1 for row in correlations if row.get("score", 0) >= 0.7)
    moderate = sum(
        1 for row in correlations if 0.45 <= row.get("score", 0) < 0.7
    )
    if high >= 2 or (high >= 1 and position_count <= 4):
        return "High"
    if high >= 1 or moderate >= 2:
        return "Moderate"
    return "Low"


def _score_label(score: float) -> str:
    if score >= 0.7:
        return "High"
    if score >= 0.45:
        return "Moderate"
    return "Low"
