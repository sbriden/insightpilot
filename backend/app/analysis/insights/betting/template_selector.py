"""
Select the best internal Guided Market Slate template for user inputs
and live odds-bucket inventory.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.slate_template import (
    BUCKET_ORDER,
    MIN_OPTIONS_PER_BUCKET,
    SlateTemplate,
    assign_side_bucket,
    build_adaptive_buckets,
    normalize_risk,
    templates_for_ticket_count,
)


def count_bucket_inventory(
    sides: list[dict[str, Any]],
    *,
    adaptive: dict[str, Any] | None = None,
) -> dict[str, int]:
    adaptive = adaptive or build_adaptive_buckets(sides)
    counts = {bucket: 0 for bucket in BUCKET_ORDER}
    for side in sides:
        bucket = assign_side_bucket(side, adaptive)
        if bucket:
            counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _recipe_bucket_demand(template: SlateTemplate) -> dict[str, int]:
    demand = {bucket: 0 for bucket in BUCKET_ORDER}
    for recipe in template.recipes:
        for bucket in recipe.leg_buckets:
            demand[bucket] = demand.get(bucket, 0) + 1
    return demand


def score_template(
    template: SlateTemplate,
    *,
    risk: str,
    ticket_count: int,
    total_exposure: int,
    min_stake: int,
    inventory: dict[str, int],
    distinct_events: int,
) -> tuple[float, list[str]]:
    """
    Higher is better. Returns (score, soft_notes).
    """

    notes: list[str] = []
    risk_key = normalize_risk(risk)
    score = 0.0

    if risk_key in template.risk_levels:
        score += 40.0
    else:
        score -= 25.0
        notes.append("risk_mismatch")

    # Ticket count fit.
    if template.min_tickets <= ticket_count <= template.max_tickets:
        score += 25.0
    else:
        distance = min(
            abs(template.min_tickets - ticket_count),
            abs(template.max_tickets - ticket_count),
        )
        score += max(0.0, 25.0 - 8.0 * distance)
        notes.append("ticket_count_adjusted")

    n_tickets = len(template.recipes)
    if n_tickets * min_stake > total_exposure:
        score -= 50.0
        notes.append("exposure_insufficient")
    else:
        score += 15.0

    demand = _recipe_bucket_demand(template)
    missing = 0
    covered = 0
    for bucket, need in demand.items():
        have = int(inventory.get(bucket) or 0)
        if need <= 0:
            continue
        if have >= need:
            covered += need
            score += 3.0
        else:
            missing += need - have
            score -= 4.0 * (need - have)
    if missing:
        notes.append("bucket_shortfall")
    else:
        score += 10.0

    # Parlay feasibility proxy: need enough distinct events.
    max_legs = max((r.leg_count for r in template.recipes), default=1)
    if distinct_events >= max_legs:
        score += 8.0
    else:
        score -= 12.0
        notes.append("event_diversity_low")

    # Prefer templates that use inventory without larger dogs when
    # risk is low.
    if risk_key == "low" and template.allow_larger_underdog:
        score -= 6.0
    if risk_key == "high" and template.allow_larger_underdog:
        score += 4.0

    score += template.priority / 100.0
    return score, notes


def select_template(
    *,
    risk: str,
    ticket_count: int,
    total_exposure: float,
    sides: list[dict[str, Any]],
    min_stake: int = 1,
) -> dict[str, Any]:
    """
    Choose the best feasible template.

    Returns dict with template, score, notes, inventory, and any
    user-facing adjustment message (no template names).
    """

    exposure = int(round(float(total_exposure or 0)))
    if exposure < min_stake:
        raise ValueError(
            f"Total exposure must be at least {min_stake}."
        )
    count = int(ticket_count or 0)
    if count < 1:
        raise ValueError("Number of bets must be at least 1.")
    if count > 25:
        raise ValueError("Number of bets cannot exceed 25.")

    adaptive = build_adaptive_buckets(
        sides,
        min_options=MIN_OPTIONS_PER_BUCKET,
    )
    inventory = count_bucket_inventory(sides, adaptive=adaptive)
    events = {
        str(side.get("event_id") or "")
        for side in sides
        if side.get("event_id")
    }
    distinct_events = len(events)
    if not sides:
        raise ValueError(
            "No eligible markets are available for the selected "
            "sports and date."
        )

    max_by_budget = max(1, exposure // max(1, min_stake))
    requested = min(count, max_by_budget)
    candidates = templates_for_ticket_count(requested)

    ranked: list[tuple[float, SlateTemplate, list[str]]] = []
    for template in candidates:
        score, notes = score_template(
            template,
            risk=risk,
            ticket_count=requested,
            total_exposure=exposure,
            min_stake=min_stake,
            inventory=inventory,
            distinct_events=distinct_events,
        )
        ranked.append((score, template, notes))
    ranked.sort(key=lambda row: row[0], reverse=True)

    if not ranked:
        raise ValueError("No slate templates are available.")

    best_score, best, notes = ranked[0]
    # If best is still exposure-infeasible, shrink ticket count.
    adjustment = None
    while (
        len(best.recipes) * min_stake > exposure
        and requested > 1
    ):
        requested -= 1
        adjustment = (
            f"Budget supports at most {requested} bets at the "
            f"minimum stake of {min_stake}."
        )
        retry = templates_for_ticket_count(requested)
        ranked = []
        for template in retry:
            score, notes = score_template(
                template,
                risk=risk,
                ticket_count=requested,
                total_exposure=exposure,
                min_stake=min_stake,
                inventory=inventory,
                distinct_events=distinct_events,
            )
            ranked.append((score, template, notes))
        ranked.sort(key=lambda row: row[0], reverse=True)
        best_score, best, notes = ranked[0]

    if len(best.recipes) * min_stake > exposure:
        raise ValueError(
            f"Exposure of {exposure} cannot fund the minimum "
            f"stake across the requested bets. Increase the "
            f"budget or lower the number of bets "
            f"(max feasible: {max_by_budget})."
        )

    if requested != count and adjustment is None:
        adjustment = (
            f"Built a {requested}-bet slate from your request "
            f"for {count} based on available markets and budget."
        )
    elif "bucket_shortfall" in notes and adjustment is None:
        adjustment = (
            "Some preferred odds ranges are thin today; the slate "
            "uses the closest available market prices."
        )
    elif "ticket_count_adjusted" in notes and adjustment is None:
        adjustment = (
            f"Adjusted to a {len(best.recipes)}-bet composition "
            "that fits today's board."
        )

    return {
        "template": best,
        "score": best_score,
        "notes": notes,
        "inventory": inventory,
        "adaptive_buckets": adaptive,
        "requested_tickets": count,
        "effective_tickets": len(best.recipes),
        "adjustment_message": adjustment,
        "distinct_events": distinct_events,
    }
