"""
Multi-model disagreement / ensemble diagnostics.

A single blended projection (e.g. -4.7) hides whether the
underlying views agree. Run independent estimates, then report:

  projection_mean
  projection_stddev
  model_agreement

Tight clusters (low stddev) support confidence; wide disagreement
should dampen High/Moderate even when the mean looks attractive.
"""

from __future__ import annotations

import statistics
from typing import Any

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.team_strength import (
    POINTS_PER_MATCHUP_UNIT,
    PACE_POINTS_PER_SD,
    DEFAULT_LEAGUE_AVG_PPG,
    project_strength_scores,
)


# Stddev (points) at which agreement ≈ 0.5.
SPREAD_DISAGREEMENT_SCALE = 1.5
TOTAL_DISAGREEMENT_SCALE = 2.5

# Floor so extreme disagreement still allows Moderate with huge edges.
AGREEMENT_EDGE_FLOOR = 0.4


def build_model_disagreement(
    *,
    market_home: float | None = None,
    market_away: float | None = None,
    market_spread: float | None = None,
    market_total: float | None = None,
    home_team_id: str | None = None,
    away_team_id: str | None = None,
    strength_context: dict[str, Any] | None = None,
    recent_ppg: dict[str, float] | None = None,
    home_injury_adj: float = 0.0,
    away_injury_adj: float = 0.0,
    strength_home: float | None = None,
    strength_away: float | None = None,
    strength_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build independent spread/total estimates and disagreement stats.
    """

    # Resolve market implied scores if only spread/total given.
    m_home, m_away, m_spread, m_total = _resolve_market_baseline(
        market_home=market_home,
        market_away=market_away,
        market_spread=market_spread,
        market_total=market_total,
    )

    # Prefer caller-supplied strength; else compute once.
    s_home = strength_home
    s_away = strength_away
    detail = dict(strength_detail or {})
    if (
        (s_home is None or s_away is None)
        and home_team_id
        and away_team_id
        and strength_context
    ):
        s_home, s_away, detail = project_strength_scores(
            home_team_id=str(home_team_id),
            away_team_id=str(away_team_id),
            context=strength_context,
        )

    profiles = (strength_context or {}).get("profiles") or {}
    home_prof = profiles.get(str(home_team_id or "")) or {}
    away_prof = profiles.get(str(away_team_id or "")) or {}
    league_avg = float(
        (strength_context or {}).get("league_avg_ppg")
        or detail.get("league_avg_ppg")
        or DEFAULT_LEAGUE_AVG_PPG
    )

    spread_estimates: dict[str, float] = {}
    total_estimates: dict[str, float] = {}

    # 1) Market model
    if m_spread is not None:
        spread_estimates["market"] = round(float(m_spread), 2)
    if m_total is not None:
        total_estimates["market"] = round(float(m_total), 2)

    # 2) Team strength model (full strength projection)
    if s_home is not None and s_away is not None:
        spread_estimates["team_strength"] = round(
            float(s_away) - float(s_home), 2
        )
        total_estimates["team_strength"] = round(
            float(s_home) + float(s_away), 2
        )

    # 3) Efficiency model — offense/defense efficiency only (no pace).
    eff_home, eff_away = _efficiency_scores(
        home_prof=home_prof,
        away_prof=away_prof,
        league_avg=league_avg,
        include_pace=False,
        matchup_override=None,
    )
    if eff_home is not None and eff_away is not None:
        spread_estimates["efficiency"] = round(
            float(eff_away) - float(eff_home), 2
        )
        total_estimates["efficiency"] = round(
            float(eff_home) + float(eff_away), 2
        )

    # 4) Recent form — opponent-adjusted PPG when available, else PPG map.
    form_home, form_away = _recent_form_scores(
        home_prof=home_prof,
        away_prof=away_prof,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        recent_ppg=recent_ppg,
        league_avg=league_avg,
    )
    if form_home is not None and form_away is not None:
        spread_estimates["recent_form"] = round(
            float(form_away) - float(form_home), 2
        )
        total_estimates["recent_form"] = round(
            float(form_home) + float(form_away), 2
        )

    # 5) Injury model — market + injury residual only.
    if m_home is not None and m_away is not None:
        inj_home = float(m_home) + float(home_injury_adj or 0.0)
        inj_away = float(m_away) + float(away_injury_adj or 0.0)
        spread_estimates["injury"] = round(inj_away - inj_home, 2)
        total_estimates["injury"] = round(inj_home + inj_away, 2)
    elif m_spread is not None or m_total is not None:
        # Spread-only injury shift: home injuries raise spread (worse for home).
        delta = float(home_injury_adj or 0.0) - float(away_injury_adj or 0.0)
        if m_spread is not None:
            spread_estimates["injury"] = round(
                float(m_spread) - delta, 2
            )
        if m_total is not None:
            total_estimates["injury"] = round(
                float(m_total)
                + float(home_injury_adj or 0.0)
                + float(away_injury_adj or 0.0),
                2,
            )

    # 6) Matchup model — matchup differential + pace (no efficiency z blend).
    match_home, match_away = _matchup_scores(
        detail=detail,
        home_prof=home_prof,
        away_prof=away_prof,
        league_avg=league_avg,
    )
    if match_home is not None and match_away is not None:
        spread_estimates["matchup"] = round(
            float(match_away) - float(match_home), 2
        )
        total_estimates["matchup"] = round(
            float(match_home) + float(match_away), 2
        )

    spread = summarize_estimates(
        spread_estimates, scale=SPREAD_DISAGREEMENT_SCALE, unit="points"
    )
    total = summarize_estimates(
        total_estimates, scale=TOTAL_DISAGREEMENT_SCALE, unit="points"
    )

    return {
        "spread": spread,
        "total": total,
        "models_available": sorted(
            set(spread_estimates) | set(total_estimates)
        ),
        "note": (
            "Independent estimates: market, team_strength, efficiency, "
            "recent_form, injury, matchup. Low stddev ⇒ high agreement; "
            "wide disagreement dampens confidence even when the mean "
            "looks attractive."
        ),
    }


def summarize_estimates(
    estimates: dict[str, float],
    *,
    scale: float,
    unit: str = "points",
) -> dict[str, Any]:
    """Mean / stddev / agreement for one metric family."""

    clean = {
        key: float(value)
        for key, value in (estimates or {}).items()
        if num(value) is not None
    }
    values = list(clean.values())
    n = len(values)
    if n == 0:
        return {
            "estimates": {},
            "projection_mean": None,
            "projection_stddev": None,
            "model_agreement": None,
            "n_models": 0,
            "unit": unit,
            "label": "unavailable",
        }

    mean = round(statistics.fmean(values), 2)
    if n == 1:
        stddev = 0.0
    else:
        stddev = round(float(statistics.pstdev(values)), 2)

    agreement = agreement_from_stddev(stddev, scale=scale)
    label = agreement_label(agreement)

    return {
        "estimates": {k: round(v, 2) for k, v in clean.items()},
        "projection_mean": mean,
        "projection_stddev": stddev,
        "model_agreement": agreement,
        "n_models": n,
        "unit": unit,
        "label": label,
        "range": round(max(values) - min(values), 2) if n > 1 else 0.0,
    }


def agreement_from_stddev(
    stddev: float | None,
    *,
    scale: float,
) -> float | None:
    """
    Map stddev → agreement in (0, 1].

    agreement = 1 / (1 + stddev / scale)
    stddev 0 → 1.0; stddev == scale → 0.5; large → → 0.
    """

    if stddev is None:
        return None
    s = max(0.0, float(stddev))
    scale_v = max(1e-6, float(scale))
    return round(1.0 / (1.0 + s / scale_v), 3)


def agreement_label(agreement: float | None) -> str:
    if agreement is None:
        return "unavailable"
    if agreement >= 0.75:
        return "high"
    if agreement >= 0.55:
        return "moderate"
    return "low"


def agreement_edge_factor(agreement: float | None) -> float:
    """
    Scale edge magnitude before confidence thresholds.

    High agreement keeps full edge; low agreement shrinks it so
    High/Moderate are harder to reach.
    """

    if agreement is None:
        return 1.0
    return max(AGREEMENT_EDGE_FLOOR, min(1.0, float(agreement)))


def disagreement_for_market(
    ensemble: dict[str, Any] | None,
    market_type: str | None,
) -> dict[str, Any] | None:
    """Pick spread or total block for a priced market."""

    if not ensemble:
        return None
    mtype = str(market_type or "").lower()
    if mtype == "total":
        return ensemble.get("total")
    if mtype in {"spread", "moneyline"}:
        # ML borrows spread-ensemble agreement as game-winner consensus.
        return ensemble.get("spread")
    return None


def _resolve_market_baseline(
    *,
    market_home: float | None,
    market_away: float | None,
    market_spread: float | None,
    market_total: float | None,
) -> tuple[
    float | None,
    float | None,
    float | None,
    float | None,
]:
    home = num(market_home)
    away = num(market_away)
    spread = num(market_spread)
    total = num(market_total)

    if home is not None and away is not None:
        if spread is None:
            spread = float(away) - float(home)
        if total is None:
            total = float(home) + float(away)
    elif total is not None and spread is not None:
        # total = home + away, spread = away - home
        home = (float(total) - float(spread)) / 2.0
        away = (float(total) + float(spread)) / 2.0

    return (
        None if home is None else float(home),
        None if away is None else float(away),
        None if spread is None else float(spread),
        None if total is None else float(total),
    )


def _efficiency_scores(
    *,
    home_prof: dict[str, Any],
    away_prof: dict[str, Any],
    league_avg: float,
    include_pace: bool,
    matchup_override: tuple[float, float] | None,
) -> tuple[float | None, float | None]:
    if not home_prof or not away_prof:
        return None, None

    if matchup_override is not None:
        home_m, away_m = matchup_override
    else:
        home_off = num(home_prof.get("offensive_efficiency"))
        home_def = num(home_prof.get("defensive_efficiency"))
        away_off = num(away_prof.get("offensive_efficiency"))
        away_def = num(away_prof.get("defensive_efficiency"))
        if None in (home_off, home_def, away_off, away_def):
            return None, None
        home_m = float(home_off) - float(away_def)
        away_m = float(away_off) - float(home_def)

    pace = 0.0
    if include_pace:
        home_pace = num(home_prof.get("pace_z")) or 0.0
        away_pace = num(away_prof.get("pace_z")) or 0.0
        pace = (float(home_pace) + float(away_pace)) / 2.0

    home = (
        league_avg
        + POINTS_PER_MATCHUP_UNIT * float(home_m)
        + (PACE_POINTS_PER_SD * pace if include_pace else 0.0)
    )
    away = (
        league_avg
        + POINTS_PER_MATCHUP_UNIT * float(away_m)
        + (PACE_POINTS_PER_SD * pace if include_pace else 0.0)
    )
    home = max(10.0, min(42.0, home))
    away = max(10.0, min(42.0, away))
    return round(home, 1), round(away, 1)


def _matchup_scores(
    *,
    detail: dict[str, Any],
    home_prof: dict[str, Any],
    away_prof: dict[str, Any],
    league_avg: float,
) -> tuple[float | None, float | None]:
    home_m = num(detail.get("home_matchup"))
    away_m = num(detail.get("away_matchup"))
    if home_m is None or away_m is None:
        # Rebuild from profiles if detail missing.
        return _efficiency_scores(
            home_prof=home_prof,
            away_prof=away_prof,
            league_avg=league_avg,
            include_pace=True,
            matchup_override=None,
        )
    return _efficiency_scores(
        home_prof=home_prof or {"offensive_efficiency": 0},
        away_prof=away_prof or {"offensive_efficiency": 0},
        league_avg=league_avg,
        include_pace=True,
        matchup_override=(float(home_m), float(away_m)),
    )


def _recent_form_scores(
    *,
    home_prof: dict[str, Any],
    away_prof: dict[str, Any],
    home_team_id: str | None,
    away_team_id: str | None,
    recent_ppg: dict[str, float] | None,
    league_avg: float,
) -> tuple[float | None, float | None]:
    home_ppg = num(home_prof.get("points_per_game_adj"))
    away_ppg = num(away_prof.get("points_per_game_adj"))
    home_allowed = num(home_prof.get("points_allowed_adj"))
    away_allowed = num(away_prof.get("points_allowed_adj"))

    if home_ppg is not None and away_ppg is not None:
        # Blend own scoring form with opponent points allowed.
        home = float(home_ppg)
        away = float(away_ppg)
        if away_allowed is not None:
            home = 0.6 * home + 0.4 * float(away_allowed)
        if home_allowed is not None:
            away = 0.6 * away + 0.4 * float(home_allowed)
        return round(home, 1), round(away, 1)

    if recent_ppg:
        h = recent_ppg.get(str(home_team_id or ""))
        a = recent_ppg.get(str(away_team_id or ""))
        if h is not None and a is not None:
            return round(float(h), 1), round(float(a), 1)

    if home_ppg is not None or away_ppg is not None:
        return (
            round(float(home_ppg), 1)
            if home_ppg is not None
            else round(league_avg, 1),
            round(float(away_ppg), 1)
            if away_ppg is not None
            else round(league_avg, 1),
        )
    return None, None
