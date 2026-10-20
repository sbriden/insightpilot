"""
Phase-1 feature builder for the residual challenger.

Builds a leak-safe, football-plausible feature vector used to
predict market score residuals (actual − market implied).

Feature groups (existing tables only):
  strength, matchup, explosive, scoring ops, personnel,
  situational, market context, uncertainty.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.team_strength import (
    POINTS_PER_MATCHUP_UNIT,
    project_strength_scores,
)


# Stable column order for ridge design matrix.
FEATURE_NAMES: tuple[str, ...] = (
    # Strength / matchup core
    "home_off_eff",
    "away_off_eff",
    "home_def_eff",
    "away_def_eff",
    "home_matchup",
    "away_matchup",
    "pace_z",
    "home_epa",
    "away_epa",
    # Pass / rush matchup
    "pass_matchup_home",
    "rush_matchup_home",
    "pass_matchup_away",
    "rush_matchup_away",
    # Explosive proxies
    "home_explosive",
    "away_explosive",
    "home_explosive_allowed",
    "away_explosive_allowed",
    # Scoring opportunities
    "home_rz_eff",
    "away_rz_eff",
    # Personnel / injury
    "home_injury_adj",
    "away_injury_adj",
    "qb_out_home",
    "qb_out_away",
    # Situational
    "week_norm",
    "early_season",
    "home_games",
    "away_games",
    "home_rest_days",
    "away_rest_days",
    # Market context
    "market_spread",
    "market_total",
    "spread_move",
    "total_move",
    # Uncertainty
    "min_games",
    "missing_strength",
    "disagreement_spread_sd",
    "disagreement_total_sd",
)

# Cold-start prior coefficients (home residual). Away uses sign-flipped
# matchups via FEATURE_AWAY_SIGN so one home-oriented prior seeds both.
PRIOR_HOME_COEF: dict[str, float] = {
    "home_matchup": POINTS_PER_MATCHUP_UNIT * 0.55,
    "away_matchup": -POINTS_PER_MATCHUP_UNIT * 0.15,
    "pace_z": 0.4,
    "pass_matchup_home": 1.1,
    "rush_matchup_home": 0.7,
    "home_rz_eff": 0.6,
    "home_injury_adj": 1.0,
    "away_injury_adj": 0.35,
    "qb_out_home": -2.5,
    "qb_out_away": 0.8,
    "spread_move": -0.15,
    "total_move": 0.05,
    "disagreement_spread_sd": 0.0,
    "early_season": -0.2,
}


def build_residual_features(
    *,
    home_team_id: str | None,
    away_team_id: str | None,
    strength_context: dict[str, Any] | None = None,
    market_home: float | None = None,
    market_away: float | None = None,
    market_spread: float | None = None,
    market_total: float | None = None,
    spread_move: float | None = None,
    total_move: float | None = None,
    week: int | None = None,
    home_injury_adj: float = 0.0,
    away_injury_adj: float = 0.0,
    home_injury: dict[str, Any] | None = None,
    away_injury: dict[str, Any] | None = None,
    disagreement: dict[str, Any] | None = None,
    home_rest_days: float | None = None,
    away_rest_days: float | None = None,
) -> dict[str, Any]:
    """
    Build feature dict + dense vector for one game.

    Strength profiles must already be filtered with ``before_week``
    so the slate week does not leak into features.
    """

    strength_home = None
    strength_away = None
    detail: dict[str, Any] = {"available": False}
    if home_team_id and away_team_id and strength_context:
        strength_home, strength_away, detail = project_strength_scores(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            context=strength_context,
        )

    home_prof = (detail.get("home_profile") or {}) if detail else {}
    away_prof = (detail.get("away_profile") or {}) if detail else {}
    home_off = home_prof.get("offense") or {}
    away_off = away_prof.get("offense") or {}
    home_def = home_prof.get("defense") or {}
    away_def = away_prof.get("defense") or {}

    home_pass = num(home_off.get("pass_efficiency")) or 0.0
    away_pass = num(away_off.get("pass_efficiency")) or 0.0
    home_rush = num(home_off.get("rush_efficiency")) or 0.0
    away_rush = num(away_off.get("rush_efficiency")) or 0.0
    home_pass_d = num(home_def.get("pass_defense")) or 0.0
    away_pass_d = num(away_def.get("pass_defense")) or 0.0
    home_rush_d = num(home_def.get("rush_defense")) or 0.0
    away_rush_d = num(away_def.get("rush_defense")) or 0.0

    home_games = int(detail.get("home_games") or 0)
    away_games = int(detail.get("away_games") or 0)
    min_games = min(home_games, away_games) if detail.get("available") else 0
    missing = 0.0 if detail.get("available") else 1.0

    spread_block = (disagreement or {}).get("spread") or {}
    total_block = (disagreement or {}).get("total") or {}
    spread_sd = num(spread_block.get("stddev"))
    total_sd = num(total_block.get("stddev"))

    qb_home = _qb_out_flag(home_injury)
    qb_away = _qb_out_flag(away_injury)

    week_val = int(week or 0)
    features = {
        "home_off_eff": num(home_prof.get("offensive_efficiency")) or 0.0,
        "away_off_eff": num(away_prof.get("offensive_efficiency")) or 0.0,
        "home_def_eff": num(home_prof.get("defensive_efficiency")) or 0.0,
        "away_def_eff": num(away_prof.get("defensive_efficiency")) or 0.0,
        "home_matchup": float(num(detail.get("home_matchup")) or 0.0),
        "away_matchup": float(num(detail.get("away_matchup")) or 0.0),
        "pace_z": float(num(detail.get("pace_z")) or 0.0),
        "home_epa": _profile_epa(home_prof, strength_context, home_team_id),
        "away_epa": _profile_epa(away_prof, strength_context, away_team_id),
        "pass_matchup_home": home_pass - away_pass_d,
        "rush_matchup_home": home_rush - away_rush_d,
        "pass_matchup_away": away_pass - home_pass_d,
        "rush_matchup_away": away_rush - home_rush_d,
        "home_explosive": float(num(home_off.get("explosive_rate")) or 0.0),
        "away_explosive": float(num(away_off.get("explosive_rate")) or 0.0),
        "home_explosive_allowed": float(
            num(home_def.get("explosive_plays_allowed")) or 0.0
        ),
        "away_explosive_allowed": float(
            num(away_def.get("explosive_plays_allowed")) or 0.0
        ),
        "home_rz_eff": float(
            num(home_prof.get("red_zone_efficiency"))
            or num(home_off.get("red_zone_efficiency"))
            or 0.0
        ),
        "away_rz_eff": float(
            num(away_prof.get("red_zone_efficiency"))
            or num(away_off.get("red_zone_efficiency"))
            or 0.0
        ),
        "home_injury_adj": float(home_injury_adj or 0.0),
        "away_injury_adj": float(away_injury_adj or 0.0),
        "qb_out_home": qb_home,
        "qb_out_away": qb_away,
        "week_norm": (week_val / 18.0) if week_val > 0 else 0.0,
        "early_season": 1.0 if min_games < 3 else 0.0,
        "home_games": float(home_games),
        "away_games": float(away_games),
        "home_rest_days": float(
            home_rest_days if home_rest_days is not None else 7.0
        ),
        "away_rest_days": float(
            away_rest_days if away_rest_days is not None else 7.0
        ),
        "market_spread": float(num(market_spread) or 0.0),
        "market_total": float(num(market_total) or 0.0),
        "spread_move": float(num(spread_move) or 0.0),
        "total_move": float(num(total_move) or 0.0),
        "min_games": float(min_games),
        "missing_strength": missing,
        "disagreement_spread_sd": float(spread_sd or 0.0),
        "disagreement_total_sd": float(total_sd or 0.0),
    }

    vector = [float(features[name]) for name in FEATURE_NAMES]
    return {
        "available": bool(detail.get("available")),
        "feature_names": list(FEATURE_NAMES),
        "features": features,
        "vector": vector,
        "strength_home": strength_home,
        "strength_away": strength_away,
        "strength_detail": detail,
        "market_home": market_home,
        "market_away": market_away,
        "groups": {
            "strength": [
                "home_off_eff",
                "away_off_eff",
                "home_def_eff",
                "away_def_eff",
                "home_matchup",
                "away_matchup",
                "pace_z",
                "home_epa",
                "away_epa",
            ],
            "matchup": [
                "pass_matchup_home",
                "rush_matchup_home",
                "pass_matchup_away",
                "rush_matchup_away",
            ],
            "explosive": [
                "home_explosive",
                "away_explosive",
                "home_explosive_allowed",
                "away_explosive_allowed",
            ],
            "scoring": ["home_rz_eff", "away_rz_eff"],
            "personnel": [
                "home_injury_adj",
                "away_injury_adj",
                "qb_out_home",
                "qb_out_away",
            ],
            "situational": [
                "week_norm",
                "early_season",
                "home_games",
                "away_games",
                "home_rest_days",
                "away_rest_days",
            ],
            "market": [
                "market_spread",
                "market_total",
                "spread_move",
                "total_move",
            ],
            "uncertainty": [
                "min_games",
                "missing_strength",
                "disagreement_spread_sd",
                "disagreement_total_sd",
            ],
        },
    }


def features_to_vector(features: dict[str, float]) -> list[float]:
    return [float(features.get(name) or 0.0) for name in FEATURE_NAMES]


def _profile_epa(
    profile: dict[str, Any],
    context: dict[str, Any] | None,
    team_id: str | None,
) -> float:
    direct = num(profile.get("epa_per_play"))
    if direct is not None:
        return float(direct)
    if not context or not team_id:
        return 0.0
    full = (context.get("profiles") or {}).get(str(team_id)) or {}
    return float(num(full.get("epa_per_play")) or 0.0)


def _qb_out_flag(injury: dict[str, Any] | None) -> float:
    if not injury:
        return 0.0
    for row in injury.get("injuries") or []:
        pos = str(row.get("position") or row.get("canonical_position") or "")
        status = str(row.get("game_status") or row.get("status") or "").lower()
        if pos.upper() == "QB" and status in {"out", "doubtful"}:
            return 1.0
    for driver in injury.get("drivers") or []:
        text = str(driver).upper()
        if "QB" in text and ("OUT" in text or "DOUBTFUL" in text):
            return 1.0
    return 0.0
