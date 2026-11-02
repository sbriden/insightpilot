"""
Expand a selected Guided Market Slate template into ticket/leg
requirements with stake amounts that sum to total exposure.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.slate_template import (
    BUCKET_FALLBACKS,
    ODDS_BUCKETS,
    SlateTemplate,
    TicketRecipe,
    bucket_label,
    bucket_odds_text,
)


def _allocate_stakes(
    recipes: tuple[TicketRecipe, ...] | list[TicketRecipe],
    *,
    total_exposure: int,
    single_pct: float,
    exponent: float,
    min_stake: int = 1,
) -> list[int]:
    """
    Allocate whole-unit stakes. Singles and parlays get separate
    budget pools; weights^exponent drive variation within each pool.
    """

    total = int(total_exposure)
    n = len(recipes)
    if n == 0:
        return []
    if min_stake * n > total:
        raise ValueError(
            f"Budget of {total} cannot fund {n} bets at "
            f"minimum stake {min_stake}."
        )

    single_idx = [
        i for i, r in enumerate(recipes) if r.ticket_type == "single"
    ]
    parlay_idx = [
        i for i, r in enumerate(recipes) if r.ticket_type == "parlay"
    ]

    single_budget = int(round(total * float(single_pct)))
    parlay_budget = total - single_budget
    if single_idx and single_budget < min_stake * len(single_idx):
        single_budget = min_stake * len(single_idx)
        parlay_budget = total - single_budget
    if parlay_idx and parlay_budget < min_stake * len(parlay_idx):
        parlay_budget = min_stake * len(parlay_idx)
        single_budget = total - parlay_budget
    if not single_idx:
        single_budget = 0
        parlay_budget = total
    if not parlay_idx:
        parlay_budget = 0
        single_budget = total

    stakes = [0] * n

    def fill(indices: list[int], budget: int) -> None:
        if not indices or budget <= 0:
            return
        k = len(indices)
        floor = min_stake * k
        if floor > budget:
            base = budget // k
            rem = budget - base * k
            for j, idx in enumerate(indices):
                stakes[idx] = base + (1 if j < rem else 0)
            return
        weights = [
            max(float(recipes[i].weight), 1e-9) ** float(exponent)
            for i in indices
        ]
        for idx in indices:
            stakes[idx] = min_stake
        remaining = budget - floor
        if remaining <= 0:
            return
        wsum = sum(weights)
        exact = [remaining * (w / wsum) for w in weights]
        floors = [int(v) for v in exact]
        used = sum(floors)
        leftover = remaining - used
        order = sorted(
            range(k),
            key=lambda j: (exact[j] - floors[j], -j),
            reverse=True,
        )
        extras = list(floors)
        for j in order:
            if leftover <= 0:
                break
            extras[j] += 1
            leftover -= 1
        for j, idx in enumerate(indices):
            stakes[idx] += extras[j]

    fill(single_idx, single_budget)
    fill(parlay_idx, parlay_budget)

    allocated = sum(stakes)
    rem = total - allocated
    if rem != 0 and stakes:
        target = 0
        if single_idx:
            target = max(single_idx, key=lambda i: stakes[i])
        stakes[target] = max(min_stake, stakes[target] + rem)
        allocated = sum(stakes)
        rem = total - allocated
        if rem != 0:
            for i in range(n):
                if rem == 0:
                    break
                if rem > 0:
                    stakes[i] += rem
                    rem = 0
                elif stakes[i] > min_stake:
                    take = min(stakes[i] - min_stake, -rem)
                    stakes[i] -= take
                    rem += take

    assert sum(stakes) == total
    return stakes


def _bucket_bounds(
    bucket_id: str,
    adaptive: dict[str, Any] | None,
) -> tuple[Any, Any, str, str]:
    label = bucket_label(bucket_id, adaptive=adaptive)
    odds_text = bucket_odds_text(bucket_id, adaptive=adaptive)
    if adaptive and bucket_id in adaptive:
        spec = adaptive[bucket_id]
        return (
            spec.get("min_odds"),
            spec.get("max_odds"),
            label,
            odds_text,
        )
    static = ODDS_BUCKETS[bucket_id]
    return (
        static["min_odds"],
        static["max_odds"],
        label,
        odds_text,
    )


def _requirement_prompt(label: str, odds_text: str) -> str:
    if odds_text:
        return f"Pick one {label} ({odds_text})."
    return f"Pick one {label}."


def build_requirements(
    template: SlateTemplate,
    *,
    total_exposure: int,
    min_stake: int = 1,
    inventory: dict[str, int] | None = None,
    adaptive_buckets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Expand template recipes into ordered ticket/leg requirements.
    """

    exposure = int(total_exposure)
    inventory = inventory or {}
    adaptive = adaptive_buckets or {}
    recipes = list(template.recipes)
    # Soft-relax buckets with zero inventory using fallbacks.
    relaxed: list[str] = []
    adjusted_recipes: list[TicketRecipe] = []
    for recipe in recipes:
        new_legs: list[str] = []
        for bucket in recipe.leg_buckets:
            if int(inventory.get(bucket) or 0) > 0:
                new_legs.append(bucket)
                continue
            replaced = False
            for alt in BUCKET_FALLBACKS.get(bucket, ()):
                if int(inventory.get(alt) or 0) > 0:
                    new_legs.append(alt)
                    relaxed.append(f"{bucket}->{alt}")
                    replaced = True
                    break
            if not replaced:
                # Prefer any adaptive role that still has inventory.
                for alt in (
                    "moderate_favorite",
                    "near_even",
                    "moderate_underdog",
                    "strong_favorite",
                    "larger_underdog",
                ):
                    if (
                        alt != bucket
                        and int(inventory.get(alt) or 0) > 0
                    ):
                        new_legs.append(alt)
                        relaxed.append(f"{bucket}->{alt}")
                        replaced = True
                        break
            if not replaced:
                new_legs.append(bucket)
        adjusted_recipes.append(
            TicketRecipe(
                ticket_type=recipe.ticket_type,
                leg_buckets=tuple(new_legs),
                weight=recipe.weight,
            )
        )

    stakes = _allocate_stakes(
        adjusted_recipes,
        total_exposure=exposure,
        single_pct=float(template.single_pct),
        exponent=float(template.stake_exponent),
        min_stake=min_stake,
    )

    tickets: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    step_index = 0
    for ticket_i, (recipe, stake) in enumerate(
        zip(adjusted_recipes, stakes),
        start=1,
    ):
        legs: list[dict[str, Any]] = []
        for leg_i, bucket in enumerate(recipe.leg_buckets, start=1):
            min_odds, max_odds, label, odds_text = _bucket_bounds(
                bucket,
                adaptive,
            )
            fair_min = None
            fair_max = None
            if adaptive and bucket in adaptive:
                fair_min = adaptive[bucket].get("min_fair")
                fair_max = adaptive[bucket].get("max_fair")
            prompt = _requirement_prompt(label, odds_text)
            leg = {
                "leg_index": leg_i,
                "bucket_id": bucket,
                "bucket_label": label,
                "odds_text": odds_text,
                "odds_min": min_odds,
                "odds_max": max_odds,
                "fair_min": fair_min,
                "fair_max": fair_max,
                "prompt": prompt,
                "status": "pending",
                "selection": None,
            }
            legs.append(leg)
            steps.append(
                {
                    "step_index": step_index,
                    "ticket_index": ticket_i,
                    "leg_index": leg_i,
                    "ticket_type": recipe.ticket_type,
                    "leg_count": recipe.leg_count,
                    "stake": int(stake),
                    "bucket_id": bucket,
                    "bucket_label": label,
                    "odds_text": odds_text,
                    "odds_min": min_odds,
                    "odds_max": max_odds,
                    "fair_min": fair_min,
                    "fair_max": fair_max,
                    "prompt": prompt,
                    "status": "pending",
                    "skippable": False,
                }
            )
            step_index += 1

        tickets.append(
            {
                "ticket_index": ticket_i,
                "ticket_type": recipe.ticket_type,
                "leg_count": recipe.leg_count,
                "stake": int(stake),
                "status": "pending",
                "legs": legs,
                "combined_odds": None,
                "potential_profit": None,
                "potential_payout": None,
            }
        )

    singles = [t for t in tickets if t["ticket_type"] == "single"]
    parlays = [t for t in tickets if t["ticket_type"] == "parlay"]
    return {
        "template_id": template.id,
        "template_version": template.version,
        "ticket_count": len(tickets),
        "total_exposure": exposure,
        "single_exposure": sum(int(t["stake"]) for t in singles),
        "parlay_exposure": sum(int(t["stake"]) for t in parlays),
        "tickets": tickets,
        "steps": steps,
        "current_step_index": 0,
        "bucket_relaxations": relaxed,
        "adaptive_buckets": adaptive,
        "status": "in_progress",
    }
