"""
Position-specific injury impact model.

Replaces generic "starter out → flat points" with impacts that
vary dramatically by position and depth role.

At minimum we model:
  QB, RB, WR, TE, OL, DL, LB, CB, S

QB1 Out should move a projection far more than a rotational LB.

Future hooks (defaults today, ready to learn):
  starter_quality, replacement_quality, snap_expectation,
  team_dependency, backup_performance, scheme_impact
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.analysis.insights.betting.pricing import num


# Canonical positions used in betting injury modeling.
CANONICAL_POSITIONS = (
    "QB",
    "RB",
    "WR",
    "TE",
    "OL",
    "DL",
    "LB",
    "CB",
    "S",
)

# Side of ball for score application.
# offense → reduce injured team's projected points
# defense → increase opponent's projected points
POSITION_SIDE: dict[str, str] = {
    "QB": "offense",
    "RB": "offense",
    "WR": "offense",
    "TE": "offense",
    "OL": "offense",
    "DL": "defense",
    "LB": "defense",
    "CB": "defense",
    "S": "defense",
}

# Absolute team-point impact for a full-snap starter listed Out.
# Tuned so QB dwarfs rotational defenders.
POSITION_BASE_IMPACT: dict[str, float] = {
    "QB": 5.5,
    "RB": 1.4,
    "WR": 1.1,
    "TE": 0.7,
    "OL": 1.2,
    "DL": 0.9,
    "LB": 0.55,
    "CB": 0.85,
    "S": 0.5,
}

# Mean probability the player does NOT play (drives expected impact).
_STATUS_OUT_PROB = {
    "out": 1.0,
    "doubtful": 0.75,
    "questionable": 0.35,
}

# Legacy alias used by callers / tests.
_STATUS_WEIGHT = {
    "out": 1.0,
    "doubtful": 0.65,
    "questionable": 0.25,
}

# Base market-priced fraction by position (known outs often in the line).
_POSITION_MARKET_PRICED: dict[str, float] = {
    "QB": 0.70,
    "RB": 0.55,
    "WR": 0.55,
    "TE": 0.50,
    "OL": 0.45,
    "DL": 0.45,
    "LB": 0.40,
    "CB": 0.50,
    "S": 0.40,
}

# Uncertainty (points SD) for a full starter out by position.
_POSITION_IMPACT_SIGMA: dict[str, float] = {
    "QB": 3.5,
    "RB": 1.4,
    "WR": 1.2,
    "TE": 0.9,
    "OL": 1.5,
    "DL": 1.1,
    "LB": 0.8,
    "CB": 1.0,
    "S": 0.7,
}

# Map raw roster / depth labels → canonical position.
_POSITION_ALIASES: dict[str, str] = {
    "QB": "QB",
    "RB": "RB",
    "HB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "OL": "OL",
    "OT": "OL",
    "OG": "OL",
    "C": "OL",
    "T": "OL",
    "G": "OL",
    "LT": "OL",
    "LG": "OL",
    "RG": "OL",
    "RT": "OL",
    "DL": "DL",
    "DE": "DL",
    "DT": "DL",
    "NT": "DL",
    "EDGE": "DL",
    "LB": "LB",
    "ILB": "LB",
    "OLB": "LB",
    "MLB": "LB",
    "WLB": "LB",
    "CB": "CB",
    "DB": "CB",
    "S": "S",
    "FS": "S",
    "SS": "S",
    "SAF": "S",
}

DEPTH_CHART_POSITIONS = frozenset(CANONICAL_POSITIONS) | frozenset(
    _POSITION_ALIASES.keys()
)


@dataclass(frozen=True)
class InjuryQualityFactors:
    """
    Extensible quality / usage multipliers.

    All default to 1.0 (neutral). Wire learned values later:
      starter_quality > 1 for elite starters
      replacement_quality > 1 when backup is strong → less impact
      snap_expectation in [0, 1+] for expected lost snaps share
      team_dependency for scheme-critical players
      backup_performance empirical replacement delta
      scheme_impact for system-specific sensitivity
    """

    starter_quality: float = 1.0
    replacement_quality: float = 1.0
    snap_expectation: float = 1.0
    team_dependency: float = 1.0
    backup_performance: float = 1.0
    scheme_impact: float = 1.0

    def combined(self) -> float:
        # Better replacement → dampen impact.
        replacement_dampen = 1.0 / max(
            0.35, float(self.replacement_quality)
        )
        backup_dampen = 1.0 / max(0.35, float(self.backup_performance))
        return (
            max(0.0, float(self.starter_quality))
            * replacement_dampen
            * max(0.0, float(self.snap_expectation))
            * max(0.0, float(self.team_dependency))
            * backup_dampen
            * max(0.0, float(self.scheme_impact))
        )


def canonicalize_position(position: str | None) -> str | None:
    if not position:
        return None
    raw = str(position).strip().upper()
    if not raw:
        return None
    if raw in _POSITION_ALIASES:
        return _POSITION_ALIASES[raw]
    # Handle labels like "LWR", "RDE", "NB".
    for alias, canonical in _POSITION_ALIASES.items():
        if raw.endswith(alias) or raw.startswith(alias):
            return canonical
    return None


def depth_role_multiplier(
    *,
    position: str | None,
    depth_order: int | None,
    is_starter: bool,
) -> float:
    """
    How much of the base position impact this roster slot carries.

    QB1 ≈ full; rotational LB ≈ a fraction; deep bench ≈ near zero.
    """

    pos = canonicalize_position(position) or (position or "").upper()
    order = int(depth_order) if depth_order is not None else None

    if pos == "QB":
        if is_starter or order == 1:
            return 1.0
        if order == 2:
            return 0.08  # backup QB out while starter healthy
        return 0.02

    if is_starter or order == 1:
        return 1.0

    if order == 2:
        # Primary backup / rotational — still material for OL/DL/CB.
        if pos in {"OL", "DL", "CB"}:
            return 0.45
        if pos in {"LB", "S", "WR", "RB", "TE"}:
            return 0.30
        return 0.25

    if order == 3:
        if pos in {"OL", "DL", "WR", "CB"}:
            return 0.18
        return 0.10

    if order is not None and order >= 4:
        return 0.05

    # Unknown depth: treat offense skill as starter-ish only when flagged.
    return 1.0 if is_starter else 0.15


def estimate_injury_impact(
    *,
    position: str | None,
    status: str | None,
    depth_order: int | None = None,
    is_starter: bool = False,
    factors: InjuryQualityFactors | None = None,
    is_expected_to_play: bool | None = None,
    market_priced_fraction: float | None = None,
    spread_move: float | None = None,
    total_move: float | None = None,
    injured_team_is_home: bool | None = None,
) -> dict[str, Any]:
    """
    Return a structured predictive injury impact.

    ``own_score_delta`` / ``opponent_score_delta`` are full score
    impacts (expected points). ``edge_*`` are residualized for
    betting after the market-priced fraction.
    """

    pos = canonicalize_position(position)
    status_key = str(status or "").strip().lower()
    play_prob_out = float(_STATUS_OUT_PROB.get(status_key) or 0.0)
    if is_expected_to_play is False and play_prob_out < 1.0:
        play_prob_out = max(play_prob_out, 0.85)
    if is_expected_to_play is True and status_key == "questionable":
        play_prob_out = min(play_prob_out, 0.20)
    # Legacy status_weight kept for compatibility / reporting.
    status_w = float(_STATUS_WEIGHT.get(status_key) or 0.0)
    quality = factors or InjuryQualityFactors()

    if pos is None or play_prob_out <= 0:
        return _empty_impact(position=position, status=status_key)

    base = float(POSITION_BASE_IMPACT.get(pos) or 0.0)
    role = depth_role_multiplier(
        position=pos,
        depth_order=depth_order,
        is_starter=is_starter,
    )
    # Skip near-zero rotational noise unless out/doubtful starter path.
    if role < 0.05 and not is_starter:
        return _empty_impact(
            position=pos,
            status=status_key,
            role=role,
        )

    quality_mult = float(quality.combined())
    magnitude = abs(base) * play_prob_out * role * quality_mult
    side = POSITION_SIDE.get(pos, "offense")
    if side == "defense":
        own_delta = 0.0
        opp_delta = round(magnitude, 3)
    else:
        own_delta = round(-magnitude, 3)
        opp_delta = 0.0

    # Efficiency / volume proxies (dimensionless, for features).
    efficiency_delta = round(
        -0.08 * play_prob_out * role * quality_mult
        if side == "offense"
        else 0.05 * play_prob_out * role * quality_mult,
        4,
    )
    volume_delta = round(
        -float(quality.snap_expectation) * play_prob_out * role,
        4,
    )

    base_sigma = float(_POSITION_IMPACT_SIGMA.get(pos) or 1.0)
    # Questionable → more uncertainty; out → lower relative σ.
    status_sigma_scale = {
        "out": 0.85,
        "doubtful": 1.15,
        "questionable": 1.55,
    }.get(status_key, 1.0)
    impact_sigma = round(
        base_sigma * role * status_sigma_scale * max(0.5, quality_mult ** 0.5),
        3,
    )

    priced = market_priced_fraction
    if priced is None:
        priced = market_priced_fraction_for_injury(
            position=pos,
            status=status_key,
            spread_move=spread_move,
            total_move=total_move,
            own_score_delta=own_delta,
            opponent_score_delta=opp_delta,
            injured_team_is_home=injured_team_is_home,
        )
    priced = float(max(0.0, min(0.95, float(priced))))
    edge_scale = 1.0 - priced
    edge_own = round(own_delta * edge_scale, 3)
    edge_opp = round(opp_delta * edge_scale, 3)

    return {
        "position": pos,
        "side": side,
        "status": status_key,
        "base_impact": base,
        "status_weight": status_w,
        "play_prob": round(play_prob_out, 3),
        "role_multiplier": round(role, 3),
        "quality_factors": asdict(quality),
        "quality_multiplier": round(quality_mult, 3),
        "raw_magnitude": round(magnitude, 3),
        "own_score_delta": own_delta,
        "opponent_score_delta": opp_delta,
        "efficiency_delta": efficiency_delta,
        "volume_delta": volume_delta,
        "impact_sigma": impact_sigma,
        "market_priced_fraction": round(priced, 3),
        "edge_own_delta": edge_own,
        "edge_opponent_delta": edge_opp,
        "raw_delta": own_delta if side == "offense" else 0.0,
        "applies": magnitude > 0,
    }


def market_priced_fraction_for_injury(
    *,
    position: str | None,
    status: str | None = None,
    spread_move: float | None = None,
    total_move: float | None = None,
    own_score_delta: float = 0.0,
    opponent_score_delta: float = 0.0,
    injured_team_is_home: bool | None = None,
) -> float:
    """
    Estimate how much of the injury score impact is already in the line.

    Raises priced fraction when market movement already leans the
    injury-implied direction (home/away spread convention).
    """

    pos = canonicalize_position(position) or (position or "").upper()
    base = float(_POSITION_MARKET_PRICED.get(pos) or 0.50)
    status_key = str(status or "").strip().lower()
    # Late-breaking questionable less fully priced than known outs.
    if status_key == "questionable":
        base *= 0.75
    elif status_key == "doubtful":
        base *= 0.90

    # Spread convention: away − home. Home offense out → expect
    # spread_move > 0; away offense out → expect spread_move < 0.
    move = num(spread_move)
    if move is not None and injured_team_is_home is not None:
        material = (
            own_score_delta < -0.2 or opponent_score_delta > 0.2
        )
        if material and injured_team_is_home:
            if float(move) >= 0.5:
                base = min(0.95, base + 0.15)
            elif float(move) <= -0.5:
                base = max(0.15, base - 0.12)
        elif material and not injured_team_is_home:
            if float(move) <= -0.5:
                base = min(0.95, base + 0.15)
            elif float(move) >= 0.5:
                base = max(0.15, base - 0.12)

    total_m = num(total_move)
    if (
        total_m is not None
        and abs(own_score_delta) + abs(opponent_score_delta) > 1.0
    ):
        if own_score_delta < -0.5 and float(total_m) <= -0.5:
            base = min(0.95, base + 0.08)
        if opponent_score_delta > 0.5 and float(total_m) >= 0.5:
            base = min(0.95, base + 0.05)

    return float(max(0.1, min(0.95, base)))


def material_injury(
    impact: dict[str, Any],
    *,
    min_magnitude: float = 0.15,
) -> bool:
    return float(impact.get("raw_magnitude") or 0.0) >= min_magnitude


def _empty_impact(
    *,
    position: str | None,
    status: str | None,
    role: float = 0.0,
) -> dict[str, Any]:
    return {
        "position": canonicalize_position(position),
        "side": POSITION_SIDE.get(
            canonicalize_position(position) or "", "offense"
        ),
        "status": status,
        "base_impact": 0.0,
        "status_weight": 0.0,
        "play_prob": 0.0,
        "role_multiplier": round(role, 3),
        "quality_factors": asdict(InjuryQualityFactors()),
        "quality_multiplier": 1.0,
        "raw_magnitude": 0.0,
        "own_score_delta": 0.0,
        "opponent_score_delta": 0.0,
        "efficiency_delta": 0.0,
        "volume_delta": 0.0,
        "impact_sigma": 0.0,
        "market_priced_fraction": 0.0,
        "edge_own_delta": 0.0,
        "edge_opponent_delta": 0.0,
        "raw_delta": 0.0,
        "applies": False,
    }
