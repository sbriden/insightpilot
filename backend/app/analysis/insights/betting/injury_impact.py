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

_STATUS_WEIGHT = {
    "out": 1.0,
    "doubtful": 0.65,
    "questionable": 0.25,
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
) -> dict[str, Any]:
    """
    Return a structured raw (pre-market-weight) injury impact.

    ``own_score_delta`` is applied to the injured team's projection.
    ``opponent_score_delta`` is applied to the opponent (defense outs).
    """

    pos = canonicalize_position(position)
    status_key = str(status or "").strip().lower()
    status_w = float(_STATUS_WEIGHT.get(status_key) or 0.0)
    quality = factors or InjuryQualityFactors()

    if pos is None or status_w <= 0:
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

    magnitude = (
        abs(base) * status_w * role * float(quality.combined())
    )
    side = POSITION_SIDE.get(pos, "offense")
    if side == "defense":
        own_delta = 0.0
        opp_delta = round(magnitude, 3)  # opponent scores more
    else:
        own_delta = round(-magnitude, 3)  # we score less
        opp_delta = 0.0

    return {
        "position": pos,
        "side": side,
        "status": status_key,
        "base_impact": base,
        "status_weight": status_w,
        "role_multiplier": round(role, 3),
        "quality_factors": asdict(quality),
        "quality_multiplier": round(float(quality.combined()), 3),
        "raw_magnitude": round(magnitude, 3),
        "own_score_delta": own_delta,
        "opponent_score_delta": opp_delta,
        # Legacy single-field convenience for offense-only callers.
        "raw_delta": own_delta if side == "offense" else 0.0,
        "applies": magnitude > 0,
    }


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
        "role_multiplier": round(role, 3),
        "quality_factors": asdict(InjuryQualityFactors()),
        "quality_multiplier": 1.0,
        "raw_magnitude": 0.0,
        "own_score_delta": 0.0,
        "opponent_score_delta": 0.0,
        "raw_delta": 0.0,
        "applies": False,
    }
