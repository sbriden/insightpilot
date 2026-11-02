"""
Guided Market Slate — internal template definitions.

Templates describe slate *composition* (ticket types, odds buckets,
stake mix). They are never shown to the user by name/id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# American odds buckets for pick requirements.
ODDS_BUCKETS: dict[str, dict[str, Any]] = {
    "strong_favorite": {
        "id": "strong_favorite",
        "label": "stronger favorite",
        "min_odds": -220,
        "max_odds": -150,
        "description": "Higher implied probability",
    },
    "moderate_favorite": {
        "id": "moderate_favorite",
        "label": "moderate favorite",
        "min_odds": -149,
        "max_odds": -110,
        "description": "Moderate favorite",
    },
    "near_even": {
        "id": "near_even",
        "label": "near-even market",
        "min_odds": -109,
        "max_odds": 110,
        "description": "Closely priced market",
    },
    "moderate_underdog": {
        "id": "moderate_underdog",
        "label": "moderate underdog",
        "min_odds": 111,
        "max_odds": 175,
        "description": "Moderate underdog",
    },
    "larger_underdog": {
        "id": "larger_underdog",
        "label": "larger underdog",
        "min_odds": 176,
        "max_odds": 250,
        "description": "Lower implied probability",
    },
}

BUCKET_ORDER = (
    "strong_favorite",
    "moderate_favorite",
    "near_even",
    "moderate_underdog",
    "larger_underdog",
)

# Flexible substitutes when primary inventory is thin.
BUCKET_FALLBACKS: dict[str, tuple[str, ...]] = {
    "strong_favorite": ("moderate_favorite", "near_even"),
    "moderate_favorite": ("strong_favorite", "near_even"),
    "near_even": ("moderate_favorite", "moderate_underdog"),
    "moderate_underdog": ("near_even", "larger_underdog"),
    "larger_underdog": ("moderate_underdog", "near_even"),
}


# Minimum distinct sides each adaptive requirement should offer.
MIN_OPTIONS_PER_BUCKET = 4

# Hard semantic envelopes — adaptive ranges may tighten inside these
# walls but must not cross them (keeps "favorite" / "dog" labels honest).
BUCKET_SEMANTIC_BOUNDS: dict[str, dict[str, float]] = {
    "strong_favorite": {"min_odds": -1000.0, "max_odds": -150.0},
    "moderate_favorite": {"min_odds": -149.0, "max_odds": -110.0},
    "near_even": {"min_odds": -109.0, "max_odds": 110.0},
    "moderate_underdog": {"min_odds": 111.0, "max_odds": 175.0},
    "larger_underdog": {"min_odds": 176.0, "max_odds": 1000.0},
}


def _valid_american(value: float) -> bool:
    return not (-100.0 < value < 100.0)


def clamp_odds_to_bucket(
    american_odds: float | int | None,
    bucket_id: str,
) -> float | None:
    """Clamp a price into the bucket's semantic envelope."""

    if american_odds is None or bucket_id not in BUCKET_SEMANTIC_BOUNDS:
        return None
    try:
        value = float(american_odds)
    except (TypeError, ValueError):
        return None
    if not _valid_american(value):
        return None
    bounds = BUCKET_SEMANTIC_BOUNDS[bucket_id]
    return max(
        float(bounds["min_odds"]),
        min(float(bounds["max_odds"]), value),
    )


def semantic_odds_allowed(
    american_odds: float | int | None,
    bucket_id: str,
) -> bool:
    """True when odds belong in this role's meaning (hard wall)."""

    if american_odds is None or bucket_id not in BUCKET_SEMANTIC_BOUNDS:
        return False
    try:
        value = float(american_odds)
    except (TypeError, ValueError):
        return False
    if not _valid_american(value):
        return False
    bounds = BUCKET_SEMANTIC_BOUNDS[bucket_id]
    return float(bounds["min_odds"]) <= value <= float(bounds["max_odds"])


def odds_in_range(
    american_odds: float | int | None,
    *,
    min_odds: float | int | None,
    max_odds: float | int | None,
) -> bool:
    """Inclusive American-odds membership for a concrete min/max range."""

    if american_odds is None or min_odds is None or max_odds is None:
        return False
    try:
        value = float(american_odds)
        lo = float(min_odds)
        hi = float(max_odds)
    except (TypeError, ValueError):
        return False
    if not _valid_american(value):
        return False
    if lo > hi:
        lo, hi = hi, lo
    return lo <= value <= hi


def odds_in_bucket(
    american_odds: float | int | None,
    bucket_id: str,
    *,
    adaptive: dict[str, Any] | None = None,
) -> bool:
    """True when offered American odds fall in the bucket (inclusive)."""

    if american_odds is None:
        return False
    if adaptive and bucket_id in adaptive:
        spec = adaptive[bucket_id]
        return odds_in_range(
            american_odds,
            min_odds=spec.get("min_odds"),
            max_odds=spec.get("max_odds"),
        )
    if bucket_id not in ODDS_BUCKETS:
        return False
    try:
        value = float(american_odds)
    except (TypeError, ValueError):
        return False
    if not _valid_american(value):
        return False
    spec = ODDS_BUCKETS[bucket_id]
    return odds_in_range(
        value,
        min_odds=spec["min_odds"],
        max_odds=spec["max_odds"],
    )


def fair_in_bucket(
    fair_probability: float | int | None,
    bucket_id: str,
    adaptive: dict[str, Any],
) -> bool:
    """Membership by adaptive fair-probability window (preferred)."""

    if fair_probability is None or bucket_id not in adaptive:
        return False
    try:
        value = float(fair_probability)
    except (TypeError, ValueError):
        return False
    spec = adaptive[bucket_id]
    lo = float(spec.get("min_fair") or 0.0)
    hi = float(spec.get("max_fair") or 1.0)
    if lo > hi:
        lo, hi = hi, lo
    return lo <= value <= hi


def bucket_for_odds(
    american_odds: float | int | None,
    *,
    adaptive: dict[str, Any] | None = None,
) -> str | None:
    for bucket_id in BUCKET_ORDER:
        if odds_in_bucket(american_odds, bucket_id, adaptive=adaptive):
            return bucket_id
    return None


def _side_fair(side: dict[str, Any]) -> float | None:
    for key in ("fair_probability", "raw_implied_probability"):
        raw = side.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if 0.0 < value < 1.0:
            return value
    price = side.get("price")
    if price is None:
        price = side.get("offered_odds")
    try:
        from app.analysis.insights.betting.pricing import (
            american_to_implied_prob,
        )

        return american_to_implied_prob(price)
    except Exception:
        return None


def _side_price(side: dict[str, Any]) -> float | None:
    price = side.get("price")
    if price is None:
        price = side.get("offered_odds")
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    if not _valid_american(value):
        return None
    return value


def _format_odds_bound(value: float) -> str:
    rounded = int(round(value))
    return f"{rounded:+d}" if rounded > 0 else str(rounded)


def _clip_extreme_prices(prices: list[float]) -> list[float]:
    """Drop one-off juice outliers that blow out displayed ranges."""

    if len(prices) < 3:
        return list(prices)
    ordered = sorted(prices)
    # Keep central mass; American favorites are more negative.
    lo_i = max(0, int(len(ordered) * 0.05))
    hi_i = min(len(ordered) - 1, int(len(ordered) * 0.95))
    if hi_i <= lo_i:
        return list(prices)
    lo = ordered[lo_i]
    hi = ordered[hi_i]
    clipped = [p for p in prices if lo <= p <= hi]
    return clipped or list(prices)


def build_adaptive_buckets(
    sides: list[dict[str, Any]],
    *,
    min_options: int = MIN_OPTIONS_PER_BUCKET,
) -> dict[str, dict[str, Any]]:
    """
    Build day-specific odds ranges from available sides.

    Each role keeps its semantic meaning (strong favorites stay ≤ -150,
    larger underdogs stay ≥ +176). Ranges tighten to today's inventory
    inside those walls. Thin buckets borrow adjacent inventory for the
    candidate pool count, but displayed odds text stays inside the wall.
    """

    by_bucket: dict[str, list[tuple[float, float, dict[str, Any]]]] = {
        bucket_id: [] for bucket_id in BUCKET_ORDER
    }
    for side in sides:
        fair = _side_fair(side)
        price = _side_price(side)
        if fair is None or price is None:
            continue
        # Prefer static semantic assignment so roles stay honest.
        assigned = None
        for bucket_id in BUCKET_ORDER:
            if semantic_odds_allowed(price, bucket_id):
                assigned = bucket_id
                break
        if assigned is None:
            continue
        by_bucket[assigned].append((fair, price, side))

    target = max(2, int(min_options))
    adaptive: dict[str, dict[str, Any]] = {}
    for bucket_id in BUCKET_ORDER:
        base = ODDS_BUCKETS[bucket_id]
        bounds = BUCKET_SEMANTIC_BOUNDS[bucket_id]
        primary = list(by_bucket[bucket_id])
        # Candidate-pool inventory may include adjacent fallbacks.
        pool = list(primary)
        if len(pool) < target:
            for alt in BUCKET_FALLBACKS.get(bucket_id, ()):
                pool.extend(by_bucket.get(alt) or [])
                if len(pool) >= target:
                    break

        # Display / filter core range uses primary prices only when
        # available; otherwise the semantic static envelope.
        display_rows = primary if primary else pool
        if display_rows:
            prices = _clip_extreme_prices([row[1] for row in display_rows])
            fairs = [row[0] for row in display_rows]
            # Always clamp into the role wall so labels stay true.
            min_odds = max(float(bounds["min_odds"]), min(prices))
            max_odds = min(float(bounds["max_odds"]), max(prices))
            if min_odds > max_odds:
                min_odds = float(bounds["min_odds"])
                max_odds = float(bounds["max_odds"])
            min_fair = min(fairs)
            max_fair = max(fairs)
        else:
            min_odds = float(bounds["min_odds"])
            max_odds = float(bounds["max_odds"])
            min_fair = None
            max_fair = None

        adaptive[bucket_id] = {
            "id": bucket_id,
            "label": base["label"],
            "description": base["description"],
            "min_odds": min_odds,
            "max_odds": max_odds,
            "min_fair": min_fair,
            "max_fair": max_fair,
            "count": len(pool),
            "primary_count": len(primary),
            "adaptive": True,
            "odds_text": (
                f"{_format_odds_bound(min_odds)} to "
                f"{_format_odds_bound(max_odds)}"
            ),
        }
    return adaptive


def assign_side_bucket(
    side: dict[str, Any],
    adaptive: dict[str, Any],
) -> str | None:
    """
    Assign a side to its semantic odds role.

    Adaptive fair windows are only a tie-break inside overlapping
    adaptive ranges; hard American-odds walls stay authoritative.
    """

    price = _side_price(side)
    if price is None:
        return None
    for bucket_id in BUCKET_ORDER:
        if semantic_odds_allowed(price, bucket_id):
            return bucket_id
    # Fall back to adaptive odds envelopes if somehow outside walls.
    for bucket_id in BUCKET_ORDER:
        if odds_in_bucket(price, bucket_id, adaptive=adaptive):
            return bucket_id
    return None


def normalize_risk(risk: str | None) -> str:
    key = str(risk or "balanced").strip().lower()
    aliases = {
        "low": "low",
        "conservative": "low",
        "medium": "medium",
        "balanced": "medium",
        "high": "high",
        "aggressive": "high",
    }
    return aliases.get(key, "medium")


@dataclass(frozen=True)
class TicketRecipe:
    """One wager recipe: single or N-leg parlay with per-leg buckets."""

    ticket_type: str  # "single" | "parlay"
    leg_buckets: tuple[str, ...]
    weight: float = 1.0  # relative stake weight within category

    @property
    def leg_count(self) -> int:
        return len(self.leg_buckets)


@dataclass(frozen=True)
class SlateTemplate:
    id: str
    name: str
    version: str
    risk_levels: tuple[str, ...]
    min_tickets: int
    max_tickets: int
    single_pct: float
    parlay_pct: float
    stake_exponent: float
    recipes: tuple[TicketRecipe, ...]
    priority: int = 100
    allow_larger_underdog: bool = False
    notes: str = ""

    def validate(self) -> None:
        if self.min_tickets < 1 or self.max_tickets < self.min_tickets:
            raise ValueError(f"Invalid ticket range on {self.id}")
        if abs(self.single_pct + self.parlay_pct - 1.0) > 1e-6:
            raise ValueError(f"Stake mix must sum to 1.0 on {self.id}")
        if not self.recipes:
            raise ValueError(f"Template {self.id} has no recipes")
        for recipe in self.recipes:
            if recipe.ticket_type not in {"single", "parlay"}:
                raise ValueError(f"Bad ticket_type on {self.id}")
            if recipe.ticket_type == "single" and recipe.leg_count != 1:
                raise ValueError(f"Single must have 1 leg on {self.id}")
            if recipe.ticket_type == "parlay" and recipe.leg_count < 2:
                raise ValueError(f"Parlay needs >=2 legs on {self.id}")
            for bucket in recipe.leg_buckets:
                if bucket not in ODDS_BUCKETS:
                    raise ValueError(
                        f"Unknown bucket {bucket} on {self.id}"
                    )


def _recipes_for_count(
    *,
    n_singles: int,
    n_two_leg: int,
    n_three_leg: int,
    single_buckets: tuple[str, ...],
    two_leg_patterns: tuple[tuple[str, str], ...],
    three_leg_patterns: tuple[tuple[str, str, str], ...] = (),
) -> tuple[TicketRecipe, ...]:
    recipes: list[TicketRecipe] = []
    for i in range(n_singles):
        bucket = single_buckets[i % len(single_buckets)]
        recipes.append(
            TicketRecipe(
                ticket_type="single",
                leg_buckets=(bucket,),
                weight=1.0,
            )
        )
    for i in range(n_two_leg):
        pattern = two_leg_patterns[i % len(two_leg_patterns)]
        recipes.append(
            TicketRecipe(
                ticket_type="parlay",
                leg_buckets=pattern,
                weight=0.85,
            )
        )
    for i in range(n_three_leg):
        if not three_leg_patterns:
            break
        pattern = three_leg_patterns[i % len(three_leg_patterns)]
        recipes.append(
            TicketRecipe(
                ticket_type="parlay",
                leg_buckets=pattern,
                weight=0.75,
            )
        )
    return tuple(recipes)


def _scale_composition(
    ticket_count: int,
    *,
    single_share: float,
    two_leg_share: float,
    three_leg_share: float = 0.0,
) -> tuple[int, int, int]:
    """Scale an 8-ticket reference mix to an arbitrary ticket count."""

    n = max(1, int(ticket_count))
    n_singles = max(0, int(round(n * single_share)))
    remaining = n - n_singles
    if three_leg_share <= 0 or remaining == 0:
        return n_singles, remaining, 0
    parlay_total = remaining
    n_three = max(
        0,
        int(
            round(
                parlay_total
                * (
                    three_leg_share
                    / max(two_leg_share + three_leg_share, 1e-9)
                )
            )
        ),
    )
    n_three = min(n_three, remaining)
    n_two = remaining - n_three
    # Prefer at least one single when count allows.
    if n >= 2 and n_singles == 0:
        n_singles = 1
        if n_two > 0:
            n_two -= 1
        elif n_three > 0:
            n_three -= 1
    return n_singles, n_two, n_three


def build_low_template(ticket_count: int) -> SlateTemplate:
    n_singles, n_two, _ = _scale_composition(
        ticket_count,
        single_share=0.75,
        two_leg_share=0.25,
    )
    return SlateTemplate(
        id=f"low_core_{ticket_count}",
        name="Low Core",
        version="1",
        risk_levels=("low",),
        min_tickets=ticket_count,
        max_tickets=ticket_count,
        single_pct=0.82,
        parlay_pct=0.18,
        stake_exponent=2.5,
        priority=100,
        allow_larger_underdog=False,
        recipes=_recipes_for_count(
            n_singles=n_singles,
            n_two_leg=n_two,
            n_three_leg=0,
            single_buckets=(
                "strong_favorite",
                "moderate_favorite",
                "near_even",
                "strong_favorite",
                "moderate_favorite",
                "near_even",
            ),
            two_leg_patterns=(
                ("moderate_favorite", "near_even"),
                ("strong_favorite", "moderate_favorite"),
            ),
        ),
        notes="Conservative singles-heavy slate",
    )


def build_medium_template(ticket_count: int) -> SlateTemplate:
    n_singles, n_two, n_three = _scale_composition(
        ticket_count,
        single_share=0.625,
        two_leg_share=0.25,
        three_leg_share=0.125,
    )
    return SlateTemplate(
        id=f"medium_core_{ticket_count}",
        name="Medium Core",
        version="1",
        risk_levels=("medium",),
        min_tickets=ticket_count,
        max_tickets=ticket_count,
        single_pct=0.65,
        parlay_pct=0.35,
        stake_exponent=1.5,
        priority=100,
        allow_larger_underdog=False,
        recipes=_recipes_for_count(
            n_singles=n_singles,
            n_two_leg=n_two,
            n_three_leg=n_three,
            single_buckets=(
                "strong_favorite",
                "moderate_favorite",
                "near_even",
                "moderate_underdog",
                "near_even",
            ),
            two_leg_patterns=(
                ("moderate_favorite", "moderate_underdog"),
                ("near_even", "moderate_underdog"),
            ),
            three_leg_patterns=(
                (
                    "strong_favorite",
                    "near_even",
                    "moderate_underdog",
                ),
            ),
        ),
        notes="Balanced singles and parlays",
    )


def build_high_template(ticket_count: int) -> SlateTemplate:
    n_singles, n_two, n_three = _scale_composition(
        ticket_count,
        single_share=0.375,
        two_leg_share=0.375,
        three_leg_share=0.25,
    )
    return SlateTemplate(
        id=f"high_core_{ticket_count}",
        name="High Core",
        version="1",
        risk_levels=("high",),
        min_tickets=ticket_count,
        max_tickets=ticket_count,
        single_pct=0.45,
        parlay_pct=0.55,
        stake_exponent=0.85,
        priority=100,
        allow_larger_underdog=True,
        recipes=_recipes_for_count(
            n_singles=n_singles,
            n_two_leg=n_two,
            n_three_leg=n_three,
            single_buckets=(
                "strong_favorite",
                "moderate_favorite",
                "near_even",
                "moderate_underdog",
                "larger_underdog",
            ),
            two_leg_patterns=(
                ("near_even", "moderate_underdog"),
                ("moderate_favorite", "larger_underdog"),
                ("moderate_underdog", "moderate_underdog"),
            ),
            three_leg_patterns=(
                (
                    "moderate_favorite",
                    "near_even",
                    "moderate_underdog",
                ),
                (
                    "near_even",
                    "moderate_underdog",
                    "larger_underdog",
                ),
            ),
        ),
        notes="Parlay-heavy higher-variance slate",
    )


def templates_for_ticket_count(ticket_count: int) -> list[SlateTemplate]:
    n = max(1, min(int(ticket_count), 25))
    templates = [
        build_low_template(n),
        build_medium_template(n),
        build_high_template(n),
    ]
    # Nearby counts as fallback variants.
    for delta in (-1, 1, -2, 2):
        alt = n + delta
        if alt < 1 or alt > 25 or alt == n:
            continue
        templates.extend(
            [
                build_low_template(alt),
                build_medium_template(alt),
                build_high_template(alt),
            ]
        )
    for template in templates:
        template.validate()
    return templates


def all_core_templates() -> list[SlateTemplate]:
    out: list[SlateTemplate] = []
    for n in range(3, 13):
        out.extend(
            [
                build_low_template(n),
                build_medium_template(n),
                build_high_template(n),
            ]
        )
    for template in out:
        template.validate()
    return out


def bucket_label(
    bucket_id: str,
    *,
    adaptive: dict[str, Any] | None = None,
) -> str:
    if adaptive and bucket_id in adaptive:
        return str(
            adaptive[bucket_id].get("label")
            or bucket_id.replace("_", " ")
        )
    spec = ODDS_BUCKETS.get(bucket_id) or {}
    return str(spec.get("label") or bucket_id.replace("_", " "))


def bucket_odds_text(
    bucket_id: str,
    *,
    adaptive: dict[str, Any] | None = None,
) -> str:
    if adaptive and bucket_id in adaptive:
        text = adaptive[bucket_id].get("odds_text")
        if text:
            return str(text)
        lo = adaptive[bucket_id].get("min_odds")
        hi = adaptive[bucket_id].get("max_odds")
        if lo is not None and hi is not None:
            return (
                f"{_format_odds_bound(float(lo))} to "
                f"{_format_odds_bound(float(hi))}"
            )
    spec = ODDS_BUCKETS.get(bucket_id)
    if not spec:
        return ""
    lo = int(spec["min_odds"])
    hi = int(spec["max_odds"])
    return f"{_format_odds_bound(float(lo))} to {_format_odds_bound(float(hi))}"
