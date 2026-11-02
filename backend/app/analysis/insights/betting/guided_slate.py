"""
Guided Market Slate orchestrator.

Stateless session blob: the client stores the session and posts it
back with each action. Selection uses market-implied probabilities
only — no model edges or projections.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any

from app.analysis.insights.betting.daily_slate import (
    _build_eligible_markets,
    _collect_candidates,
    _normalize_sports,
    _resolve_date,
)
from app.analysis.insights.betting.pricing import (
    american_profit_per_unit,
    american_to_implied_prob,
    num,
)
from app.analysis.insights.betting.slate_template import (
    BUCKET_FALLBACKS,
    BUCKET_SEMANTIC_BOUNDS,
    MIN_OPTIONS_PER_BUCKET,
    _format_odds_bound,
    _side_fair,
    _side_price,
    normalize_risk,
    odds_in_range,
    semantic_odds_allowed,
)
from app.analysis.insights.betting.template_builder import (
    build_requirements,
)
from app.analysis.insights.betting.template_selector import (
    select_template,
)

_MIN_STAKE = 1
_ODDS_DRIFT_ABS = 15.0  # American odds points
_MIN_STEP_OPTIONS = MIN_OPTIONS_PER_BUCKET


def _flatten_market_sides(
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sides: list[dict[str, Any]] = []
    for market in markets:
        for side in market.get("sides") or []:
            row = dict(side)
            row.setdefault("market_key", market.get("market_key"))
            row.setdefault("sport", market.get("sport"))
            row.setdefault("event_id", market.get("event_id"))
            row.setdefault("event_label", market.get("event_label"))
            row.setdefault("market_type", market.get("market_type"))
            row.setdefault("home_team", market.get("home_team"))
            row.setdefault("away_team", market.get("away_team"))
            row.setdefault("home_logo_url", market.get("home_logo_url"))
            row.setdefault("away_logo_url", market.get("away_logo_url"))
            row.setdefault("start_time", market.get("start_time"))
            sides.append(row)
    return sides


def _load_pool(
    *,
    slate_date: str | None,
    sports: list[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target = _resolve_date(slate_date)
    selected = _normalize_sports(sports)
    candidates, pool_meta = _collect_candidates(
        target,
        sports=selected,
        prefer_db=True,
        include_openings=False,
        attach_logos=False,
        parallel=True,
    )
    markets, rejected = _build_eligible_markets(candidates)
    sides = _flatten_market_sides(markets)
    meta = {
        "date": target.isoformat(),
        "sports": sorted(selected),
        "candidate_count": len(candidates),
        "eligible_markets": len(markets),
        "eligible_sides": len(sides),
        "rejected_markets": len(rejected),
        "pool": pool_meta,
    }
    return sides, meta


def _public_candidate(
    side: dict[str, Any],
    *,
    stake: int,
) -> dict[str, Any]:
    price = num(side.get("price"))
    fair = float(side.get("fair_probability") or 0.0)
    profit_pu = american_profit_per_unit(price)
    potential_profit = (
        round(float(stake) * float(profit_pu), 4)
        if profit_pu is not None
        else None
    )
    return {
        "candidate_id": side.get("candidate_id"),
        "sport": side.get("sport"),
        "event_id": side.get("event_id"),
        "event_label": side.get("event_label"),
        "market_key": side.get("market_key"),
        "market_type": side.get("market_type"),
        "selection": side.get("selection"),
        "line": side.get("line"),
        "price": price,
        "offered_odds": price,
        "fair_probability": round(fair, 6),
        "raw_implied_probability": round(
            float(
                side.get("raw_implied_probability")
                or american_to_implied_prob(price)
                or 0.0
            ),
            6,
        ),
        "home_team": side.get("home_team"),
        "away_team": side.get("away_team"),
        "home_logo_url": side.get("home_logo_url"),
        "away_logo_url": side.get("away_logo_url"),
        "start_time": side.get("start_time"),
        "quote_timestamp": side.get("quote_timestamp"),
        "potential_profit": potential_profit,
        "potential_payout": (
            round(float(stake) + float(potential_profit), 4)
            if potential_profit is not None
            else None
        ),
    }


def _used_locks(session: dict[str, Any]) -> dict[str, set[str]]:
    candidate_ids: set[str] = set()
    event_ids: set[str] = set()
    market_keys: set[str] = set()
    for ticket in session.get("tickets") or []:
        for leg in ticket.get("legs") or []:
            sel = leg.get("selection") or {}
            cid = str(sel.get("candidate_id") or "")
            if cid:
                candidate_ids.add(cid)
            eid = str(sel.get("event_id") or "")
            if eid:
                event_ids.add(eid)
            mk = str(sel.get("market_key") or "")
            if mk:
                market_keys.add(mk)
    return {
        "candidate_ids": candidate_ids,
        "event_ids": event_ids,
        "market_keys": market_keys,
    }


def _side_passes_step_range(
    side: dict[str, Any],
    *,
    fair_min: float | None,
    fair_max: float | None,
    odds_min: float | None,
    odds_max: float | None,
) -> bool:
    fair = _side_fair(side)
    if (
        fair is not None
        and fair_min is not None
        and fair_max is not None
    ):
        lo = float(fair_min)
        hi = float(fair_max)
        if lo > hi:
            lo, hi = hi, lo
        return lo <= fair <= hi
    price = _side_price(side)
    return odds_in_range(
        price,
        min_odds=odds_min,
        max_odds=odds_max,
    )


def _eligible_unlocked_sides(
    sides: list[dict[str, Any]],
    *,
    session: dict[str, Any],
    step: dict[str, Any],
    include_current: bool = False,
) -> tuple[list[dict[str, Any]], set[str], set[str], str | None]:
    locks = _used_locks(session)
    current_cid = None
    if include_current:
        ticket = _ticket_for_step(session, step)
        if ticket:
            leg = ticket["legs"][int(step["leg_index"]) - 1]
            current_cid = str(
                (leg.get("selection") or {}).get("candidate_id")
                or ""
            )

    ticket_event_ids: set[str] = set()
    ticket = _ticket_for_step(session, step)
    if ticket and ticket.get("ticket_type") == "parlay":
        for leg in ticket.get("legs") or []:
            sel = leg.get("selection") or {}
            eid = str(sel.get("event_id") or "")
            if eid:
                ticket_event_ids.add(eid)

    unlocked: list[dict[str, Any]] = []
    for side in sides:
        cid = str(side.get("candidate_id") or "")
        eid = str(side.get("event_id") or "")
        mk = str(side.get("market_key") or "")
        if cid and cid in locks["candidate_ids"] and cid != current_cid:
            continue
        if mk and mk in locks["market_keys"] and cid != current_cid:
            continue
        if (
            ticket_event_ids
            and eid in ticket_event_ids
            and cid != current_cid
        ):
            continue
        if _side_price(side) is None:
            continue
        unlocked.append(side)
    return unlocked, locks["event_ids"], ticket_event_ids, current_cid


def _clamp_displayed_odds(
    odds_min: float | None,
    odds_max: float | None,
    bucket_id: str,
) -> tuple[float | None, float | None]:
    bounds = BUCKET_SEMANTIC_BOUNDS.get(bucket_id)
    if not bounds:
        return odds_min, odds_max
    lo = float(bounds["min_odds"])
    hi = float(bounds["max_odds"])
    if odds_min is None or odds_max is None:
        return lo, hi
    clamped_lo = max(lo, min(hi, float(odds_min)))
    clamped_hi = max(lo, min(hi, float(odds_max)))
    if clamped_lo > clamped_hi:
        return lo, hi
    return clamped_lo, clamped_hi


def _side_matches_bucket_or_fallback(
    side: dict[str, Any],
    *,
    bucket_id: str,
    odds_min: float | None,
    odds_max: float | None,
    allow_fallbacks: bool,
) -> bool:
    price = _side_price(side)
    if price is None:
        return False
    if odds_in_range(price, min_odds=odds_min, max_odds=odds_max):
        return True
    if not allow_fallbacks:
        return False
    if semantic_odds_allowed(price, bucket_id):
        return True
    for alt in BUCKET_FALLBACKS.get(bucket_id, ()):
        if semantic_odds_allowed(price, alt):
            return True
    return False


def _filter_candidates_for_step(
    sides: list[dict[str, Any]],
    *,
    session: dict[str, Any],
    step: dict[str, Any],
    include_current: bool = False,
) -> list[dict[str, Any]]:
    stake = int(step.get("stake") or 1)
    unlocked, used_events_all, ticket_event_ids, _current = (
        _eligible_unlocked_sides(
            sides,
            session=session,
            step=step,
            include_current=include_current,
        )
    )

    fair_min = num(step.get("fair_min"))
    fair_max = num(step.get("fair_max"))
    odds_min = num(step.get("odds_min"))
    odds_max = num(step.get("odds_max"))
    adaptive = session.get("adaptive_buckets") or {}
    bucket = str(step.get("bucket_id") or "")
    if bucket in adaptive:
        spec = adaptive[bucket]
        if fair_min is None:
            fair_min = num(spec.get("min_fair"))
        if fair_max is None:
            fair_max = num(spec.get("max_fair"))
        if odds_min is None:
            odds_min = num(spec.get("min_odds"))
        if odds_max is None:
            odds_max = num(spec.get("max_odds"))

    # Prompt bounds stay inside the semantic wall for this role.
    display_min, display_max = _clamp_displayed_odds(
        odds_min,
        odds_max,
        bucket,
    )
    if display_min is not None and display_max is not None:
        step["odds_min"] = display_min
        step["odds_max"] = display_max
        step["odds_text"] = (
            f"{_format_odds_bound(display_min)} to "
            f"{_format_odds_bound(display_max)}"
        )
        label = step.get("bucket_label") or "market"
        step["prompt"] = f"Pick one {label} ({step['odds_text']})."
    if fair_min is not None and fair_max is not None:
        step["fair_min"] = fair_min
        step["fair_max"] = fair_max

    primary = [
        side
        for side in unlocked
        if _side_matches_bucket_or_fallback(
            side,
            bucket_id=bucket,
            odds_min=display_min,
            odds_max=display_max,
            allow_fallbacks=False,
        )
    ]
    # Borrow adjacent semantic buckets only when the primary band is thin.
    pool_sides = primary
    if len(primary) < _MIN_STEP_OPTIONS:
        pool_sides = [
            side
            for side in unlocked
            if _side_matches_bucket_or_fallback(
                side,
                bucket_id=bucket,
                odds_min=display_min,
                odds_max=display_max,
                allow_fallbacks=True,
            )
        ]

    out = [
        _public_candidate(side, stake=stake) for side in pool_sides
    ]

    used_events = used_events_all - ticket_event_ids
    preferred = [
        row
        for row in out
        if str(row.get("event_id") or "") not in used_events
    ]
    if len(preferred) >= min(_MIN_STEP_OPTIONS, len(out)):
        pool = preferred
    else:
        pool = out
    pool.sort(
        key=lambda row: float(row.get("fair_probability") or 0.0),
        reverse=True,
    )
    return pool


def _ticket_for_step(
    session: dict[str, Any],
    step: dict[str, Any],
) -> dict[str, Any] | None:
    idx = int(step.get("ticket_index") or 0)
    for ticket in session.get("tickets") or []:
        if int(ticket.get("ticket_index") or 0) == idx:
            return ticket
    return None


def _current_step(session: dict[str, Any]) -> dict[str, Any] | None:
    steps = session.get("steps") or []
    idx = int(session.get("current_step_index") or 0)
    if not steps:
        return None
    if idx < 0:
        idx = 0
    if idx >= len(steps):
        return None
    return steps[idx]


def _advance_step_index(session: dict[str, Any]) -> None:
    steps = session.get("steps") or []
    for i, step in enumerate(steps):
        if step.get("status") != "complete":
            session["current_step_index"] = i
            return
    session["current_step_index"] = len(steps)
    session["status"] = "ready_for_review"


def _parlay_combined_american(legs: list[dict[str, Any]]) -> float | None:
    decimal = 1.0
    for leg in legs:
        sel = leg.get("selection") or {}
        price = num(sel.get("price") or sel.get("offered_odds"))
        if price is None:
            return None
        if price > 0:
            decimal *= 1.0 + price / 100.0
        else:
            decimal *= 1.0 + 100.0 / abs(price)
    profit = decimal - 1.0
    if profit <= 0:
        return None
    if profit >= 1.0:
        return round(profit * 100.0, 0)
    return round(-100.0 / profit, 0)


def _refresh_ticket_totals(ticket: dict[str, Any]) -> None:
    legs = ticket.get("legs") or []
    if any(leg.get("status") != "complete" for leg in legs):
        ticket["status"] = (
            "in_progress"
            if any(leg.get("status") == "complete" for leg in legs)
            else "pending"
        )
        ticket["combined_odds"] = None
        ticket["potential_profit"] = None
        ticket["potential_payout"] = None
        return
    stake = int(ticket.get("stake") or 0)
    if ticket.get("ticket_type") == "single":
        sel = (legs[0].get("selection") or {}) if legs else {}
        price = num(sel.get("price") or sel.get("offered_odds"))
        ticket["combined_odds"] = price
        profit_pu = american_profit_per_unit(price)
        if profit_pu is None:
            ticket["potential_profit"] = None
            ticket["potential_payout"] = None
        else:
            profit = round(float(stake) * float(profit_pu), 4)
            ticket["potential_profit"] = profit
            ticket["potential_payout"] = round(stake + profit, 4)
        ticket["status"] = "complete"
        return

    combined = _parlay_combined_american(legs)
    ticket["combined_odds"] = combined
    profit_pu = american_profit_per_unit(combined)
    if profit_pu is None:
        ticket["potential_profit"] = None
        ticket["potential_payout"] = None
    else:
        profit = round(float(stake) * float(profit_pu), 4)
        ticket["potential_profit"] = profit
        ticket["potential_payout"] = round(stake + profit, 4)
    ticket["status"] = "complete"


def _public_session(session: dict[str, Any]) -> dict[str, Any]:
    """Strip internal-only fields if any; keep template id for resume."""

    tickets = session.get("tickets") or []
    singles = [t for t in tickets if t.get("ticket_type") == "single"]
    parlays = [t for t in tickets if t.get("ticket_type") == "parlay"]
    completed_steps = sum(
        1
        for s in (session.get("steps") or [])
        if s.get("status") == "complete"
    )
    total_legs = sum(int(t.get("leg_count") or 0) for t in tickets)
    out = dict(session)
    out["summary"] = {
        "ticket_count": len(tickets),
        "singles": len(singles),
        "parlays": len(parlays),
        "individual_picks": total_legs,
        "completed_steps": completed_steps,
        "total_steps": len(session.get("steps") or []),
        "total_exposure": session.get("total_exposure"),
        "single_exposure": session.get("single_exposure"),
        "parlay_exposure": session.get("parlay_exposure"),
        "risk": session.get("risk"),
        "risk_label": session.get("risk_label"),
        "status": session.get("status"),
    }
    # Never expose template name; id/version kept for persistence only.
    out.pop("template_name", None)
    return out


def start_guided_slate(
    *,
    ticket_count: int,
    total_exposure: float,
    risk: str = "balanced",
    sports: list[str] | None = None,
    slate_date: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    exposure = int(round(float(total_exposure or 0)))
    if exposure < _MIN_STAKE:
        raise ValueError(
            f"Total exposure must be a whole number >= {_MIN_STAKE}."
        )
    sides, pool_meta = _load_pool(slate_date=slate_date, sports=sports)
    selection = select_template(
        risk=risk,
        ticket_count=int(ticket_count),
        total_exposure=exposure,
        sides=sides,
        min_stake=_MIN_STAKE,
    )
    template = selection["template"]
    adaptive = selection.get("adaptive_buckets") or {}
    built = build_requirements(
        template,
        total_exposure=exposure,
        min_stake=_MIN_STAKE,
        inventory=selection["inventory"],
        adaptive_buckets=adaptive,
    )
    risk_key = normalize_risk(risk)
    risk_label = {"low": "Low", "medium": "Medium", "high": "High"}[
        risk_key
    ]
    session = {
        "session_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "guided_market_slate",
        "label": "Guided Market Slate",
        "risk": risk_key,
        "risk_label": risk_label,
        "sports": pool_meta["sports"],
        "date": pool_meta["date"],
        "seed": seed,
        "template_id": template.id,
        "template_version": template.version,
        "adjustment_message": selection.get("adjustment_message"),
        "inventory": selection["inventory"],
        "adaptive_buckets": adaptive,
        "pool_meta": {
            k: pool_meta[k]
            for k in (
                "candidate_count",
                "eligible_markets",
                "eligible_sides",
                "rejected_markets",
            )
        },
        **built,
        "confirmed": False,
        "odds_alerts": [],
    }
    return {
        "session": _public_session(session),
        "current_step": _current_step(session),
        "candidates": list_step_candidates(session),
    }


def list_step_candidates(
    session: dict[str, Any],
    *,
    sides: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    step = _current_step(session)
    if step is None:
        return []
    if sides is None:
        sides, _ = _load_pool(
            slate_date=session.get("date"),
            sports=session.get("sports"),
        )
    return _filter_candidates_for_step(
        sides,
        session=session,
        step=step,
    )


def guided_candidates_payload(
    session: dict[str, Any],
) -> dict[str, Any]:
    """Public resume helper for the candidates endpoint."""

    return {
        "session": _public_session(session),
        "current_step": _current_step(session),
        "candidates": list_step_candidates(session),
    }


def select_guided_pick(
    session: dict[str, Any],
    *,
    candidate_id: str,
    sides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    step = _current_step(session)
    if step is None:
        raise ValueError("This slate has no open requirements.")
    if sides is None:
        sides, _ = _load_pool(
            slate_date=session.get("date"),
            sports=session.get("sports"),
        )
    eligible = _filter_candidates_for_step(
        sides,
        session=session,
        step=step,
        include_current=True,
    )
    chosen = next(
        (
            row
            for row in eligible
            if str(row.get("candidate_id") or "") == str(candidate_id)
        ),
        None,
    )
    if chosen is None:
        # Fall back to raw side if still in bucket (replace path).
        raw = next(
            (
                s
                for s in sides
                if str(s.get("candidate_id") or "") == str(candidate_id)
            ),
            None,
        )
        if raw is None or not _side_passes_step_range(
            raw,
            fair_min=num(step.get("fair_min")),
            fair_max=num(step.get("fair_max")),
            odds_min=num(step.get("odds_min")),
            odds_max=num(step.get("odds_max")),
        ):
            raise ValueError(
                "That selection is not eligible for this requirement."
            )
        chosen = _public_candidate(
            raw,
            stake=int(step.get("stake") or 1),
        )

    frozen = dict(chosen)
    frozen["selected_at"] = datetime.now(timezone.utc).isoformat()
    frozen["selection_odds"] = frozen.get("price")
    frozen["selection_quote_timestamp"] = frozen.get("quote_timestamp")

    ticket = _ticket_for_step(session, step)
    if ticket is None:
        raise ValueError("Could not resolve ticket for this step.")
    leg_index = int(step["leg_index"]) - 1
    ticket["legs"][leg_index]["selection"] = frozen
    ticket["legs"][leg_index]["status"] = "complete"
    step["status"] = "complete"
    _refresh_ticket_totals(ticket)
    _advance_step_index(session)
    session["updated_at"] = datetime.now(timezone.utc).isoformat()

    return {
        "session": _public_session(session),
        "current_step": _current_step(session),
        "candidates": list_step_candidates(session, sides=sides),
    }


def replace_guided_pick(
    session: dict[str, Any],
    *,
    step_index: int,
) -> dict[str, Any]:
    steps = session.get("steps") or []
    if step_index < 0 or step_index >= len(steps):
        raise ValueError("Invalid step to replace.")
    step = steps[step_index]
    ticket = _ticket_for_step(session, step)
    if ticket is None:
        raise ValueError("Could not resolve ticket for this step.")
    leg_index = int(step["leg_index"]) - 1
    ticket["legs"][leg_index]["selection"] = None
    ticket["legs"][leg_index]["status"] = "pending"
    step["status"] = "pending"
    _refresh_ticket_totals(ticket)
    # Re-open this step and clear later completions on same ticket if needed.
    session["current_step_index"] = step_index
    session["status"] = "in_progress"
    session["confirmed"] = False
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {
        "session": _public_session(session),
        "current_step": _current_step(session),
        "candidates": list_step_candidates(session),
    }


def back_guided_step(session: dict[str, Any]) -> dict[str, Any]:
    idx = int(session.get("current_step_index") or 0)
    steps = session.get("steps") or []
    if session.get("status") == "ready_for_review":
        # Go to last step without clearing it.
        session["current_step_index"] = max(0, len(steps) - 1)
        session["status"] = "in_progress"
    elif idx > 0:
        prev = idx - 1
        # Clear previous completion so user can re-pick.
        return replace_guided_pick(session, step_index=prev)
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {
        "session": _public_session(session),
        "current_step": _current_step(session),
        "candidates": list_step_candidates(session),
    }


def review_guided_slate(
    session: dict[str, Any],
) -> dict[str, Any]:
    sides, _ = _load_pool(
        slate_date=session.get("date"),
        sports=session.get("sports"),
    )
    by_id = {
        str(s.get("candidate_id") or ""): s for s in sides
    }
    alerts: list[dict[str, Any]] = []
    for ticket in session.get("tickets") or []:
        for leg in ticket.get("legs") or []:
            sel = leg.get("selection") or {}
            cid = str(sel.get("candidate_id") or "")
            if not cid:
                continue
            live = by_id.get(cid)
            if live is None:
                alerts.append(
                    {
                        "candidate_id": cid,
                        "ticket_index": ticket.get("ticket_index"),
                        "leg_index": leg.get("leg_index"),
                        "reason": "selection_no_longer_available",
                        "selected_odds": sel.get("selection_odds")
                        or sel.get("price"),
                        "current_odds": None,
                    }
                )
                continue
            selected_odds = num(
                sel.get("selection_odds") or sel.get("price")
            )
            current_odds = num(live.get("price"))
            if (
                selected_odds is not None
                and current_odds is not None
                and abs(current_odds - selected_odds) >= _ODDS_DRIFT_ABS
            ):
                alerts.append(
                    {
                        "candidate_id": cid,
                        "ticket_index": ticket.get("ticket_index"),
                        "leg_index": leg.get("leg_index"),
                        "reason": "odds_changed",
                        "selected_odds": selected_odds,
                        "current_odds": current_odds,
                    }
                )
    session["odds_alerts"] = alerts
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    incomplete = any(
        s.get("status") != "complete" for s in (session.get("steps") or [])
    )
    if not incomplete:
        session["status"] = "ready_for_review"
    return {
        "session": _public_session(session),
        "odds_alerts": alerts,
        "current_step": _current_step(session),
        "candidates": list_step_candidates(session, sides=sides),
    }


def confirm_guided_slate(session: dict[str, Any]) -> dict[str, Any]:
    incomplete = [
        s
        for s in (session.get("steps") or [])
        if s.get("status") != "complete"
    ]
    if incomplete:
        raise ValueError(
            "Finish every pick requirement before confirming the slate."
        )
    if session.get("odds_alerts"):
        raise ValueError(
            "Review flagged odds changes before confirming the slate."
        )
    session["confirmed"] = True
    session["status"] = "confirmed"
    session["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    session["updated_at"] = session["confirmed_at"]
    return {"session": _public_session(session)}


def suggest_default_candidate(
    candidates: list[dict[str, Any]],
    *,
    seed: int | None = None,
) -> dict[str, Any] | None:
    """Probability-weighted random suggestion (optional UI hint)."""

    if not candidates:
        return None
    rng = random.Random(seed)
    weights = [
        max(float(c.get("fair_probability") or 0.0), 1e-12)
        for c in candidates
    ]
    total = sum(weights)
    u = rng.random() * total
    cumulative = 0.0
    for candidate, weight in zip(candidates, weights):
        cumulative += weight
        if u <= cumulative:
            return candidate
    return candidates[-1]
