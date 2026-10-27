"""
Opponent-strength performance tendency layer (NFL + CFB).

Measures whether a team outperforms pregame expectation against
strong/weak opponents — not whether it merely beat good teams.

Two residual families are kept separate:
  - vs_model: actual − InsightPilot pregame projection
  - vs_market: actual − betting-market implied line

NFL: leak-safe strength contexts with before_week = game week.
CFB: one strength snapshot per season year (slate stays responsive
with ~230 teams); market residuals remain exact.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

from app.analysis.insights.betting.betting_sport import (
    BettingSportConfig,
    resolve_betting_sport,
)
from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.team_strength import (
    load_team_strength_context,
    project_strength_scores,
)

TIERS = ("elite", "above_avg", "average", "below_avg")
SHRINK_K_MARGIN = 12.0
SHRINK_K_MATCHUP = 16.0
MIN_N_ELITE_SOFT = 6
MIN_N_MATCHUP = 8
MIN_SITUATIONAL_PTS = 0.5
MAX_SITUATIONAL_PTS = 1.5
# Strip most shared total inflation so tier signals act as margin leans.
TENDENCY_TOTAL_STRIP = 0.85
# Default dampen when caller omits projection shrink.
TENDENCY_DEFAULT_WEIGHT = 0.30
CONSISTENCY_BAND = 3.0

# Process cache so CFB/NFL slate reloads do not rebuild from scratch.
_TENDENCY_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_TENDENCY_CACHE_MAX = 24


def load_opponent_tendency_context(
    *,
    season: int,
    before_week: int | None = None,
    include_prior_season: bool = True,
    sport: str | BettingSportConfig | None = "NFL",
) -> dict[str, Any]:
    """
    Build per-team tendency profiles for a betting sport.

    Includes completed games with week < before_week (current season)
    plus the full prior season when ``include_prior_season``.
    """

    sport_config = (
        sport
        if isinstance(sport, BettingSportConfig)
        else resolve_betting_sport(sport)
    )
    cache_key = (
        sport_config.id,
        int(season),
        before_week,
        bool(include_prior_season),
    )
    cached = _TENDENCY_CACHE.get(cache_key)
    if cached is not None:
        return cached

    game_rows = _collect_game_residual_rows(
        season=int(season),
        before_week=before_week,
        include_prior_season=include_prior_season,
        sport_config=sport_config,
    )
    profiles = _aggregate_team_profiles(game_rows)
    result = {
        "profiles": profiles,
        "season": int(season),
        "before_week": before_week,
        "games_used": len(game_rows),
        "sport": sport_config.id,
        "strength_mode": (
            "season_snapshot"
            if sport_config.id == "CFB"
            else "week_leak_safe"
        ),
    }
    if len(_TENDENCY_CACHE) >= _TENDENCY_CACHE_MAX:
        # Drop oldest insertion (CPython 3.7+ dict order).
        _TENDENCY_CACHE.pop(next(iter(_TENDENCY_CACHE)))
    _TENDENCY_CACHE[cache_key] = result
    return result


def tendency_feature_values(
    profile: dict[str, Any] | None,
) -> dict[str, float]:
    """Flatten a team profile into challenger feature scalars."""

    p = profile or {}
    return {
        "elite_margin_resid_mkt": float(
            p.get("elite_margin_resid_mkt") or 0.0
        ),
        "soft_margin_resid_mkt": float(
            p.get("soft_margin_resid_mkt") or 0.0
        ),
        "elite_margin_resid_model": float(
            p.get("elite_margin_resid_model") or 0.0
        ),
        "soft_margin_resid_model": float(
            p.get("soft_margin_resid_model") or 0.0
        ),
        "resid_vol_mkt": float(p.get("resid_vol_mkt") or 0.0),
        "pass_d_tier_resid_mkt": float(
            p.get("pass_d_tier_resid_mkt") or 0.0
        ),
    }


def tendency_situational_adjustments(
    *,
    home_team_id: str | None,
    away_team_id: str | None,
    strength_context: dict[str, Any] | None,
    tendency_context: dict[str, Any] | None,
    shrink: float | None = None,
) -> tuple[float, float, dict[str, Any]]:
    """
    Gated champion situational residual from market tier tendencies.

    Applies only when sample/CI-style gates pass and magnitude ≥ 0.5.
    CFB diagnostics stay on; champion apply stays NFL-only until the
    CFB tendency signals are mean-centered / calibrated.

    Applied points are margin-focused (shared total stripped), weighted
    by projection shrink, and capped so they cannot dominate the slate.
    """

    meta: dict[str, Any] = {
        "applied": False,
        "home_pts": 0.0,
        "away_pts": 0.0,
        "home_tier": None,
        "away_tier": None,
        "reason": "unavailable",
    }
    sport = str(
        (tendency_context or {}).get("sport")
        or (strength_context or {}).get("sport")
        or "NFL"
    ).upper()
    if sport == "CFB":
        meta["reason"] = "cfb_diagnostics_only"
        return 0.0, 0.0, meta
    if not home_team_id or not away_team_id:
        return 0.0, 0.0, meta
    profiles = (tendency_context or {}).get("profiles") or {}
    strength_profiles = (strength_context or {}).get("profiles") or {}
    home_prof = profiles.get(str(home_team_id)) or {}
    away_prof = profiles.get(str(away_team_id)) or {}
    if not home_prof.get("available") or not away_prof.get("available"):
        meta["reason"] = "sample_gate"
        return 0.0, 0.0, meta

    # Opponent tier from this week's league-relative strength pool.
    tier_map = _tier_map_for_profiles(strength_profiles)
    away_tier = tier_map.get(str(away_team_id)) or _tier_from_strength_profile(
        strength_profiles.get(str(away_team_id))
    )
    home_tier = tier_map.get(str(home_team_id)) or _tier_from_strength_profile(
        strength_profiles.get(str(home_team_id))
    )
    meta["home_tier"] = home_tier  # tier of home as opp for away
    meta["away_tier"] = away_tier  # tier of away as opp for home

    home_raw = _tier_signal_points(home_prof, opponent_tier=away_tier)
    away_raw = _tier_signal_points(away_prof, opponent_tier=home_tier)

    if (
        abs(home_raw) < MIN_SITUATIONAL_PTS
        and abs(away_raw) < MIN_SITUATIONAL_PTS
    ):
        meta["reason"] = "below_threshold"
        return 0.0, 0.0, meta

    # Margin-focused: remove most shared total inflation (over bias).
    shared = 0.5 * (home_raw + away_raw)
    home_pts = home_raw - TENDENCY_TOTAL_STRIP * shared
    away_pts = away_raw - TENDENCY_TOTAL_STRIP * shared
    weight = (
        float(shrink)
        if shrink is not None
        else TENDENCY_DEFAULT_WEIGHT
    )
    weight = max(0.05, min(1.0, weight))
    home_pts *= weight
    away_pts *= weight
    home_pts = max(
        -MAX_SITUATIONAL_PTS, min(MAX_SITUATIONAL_PTS, home_pts)
    )
    away_pts = max(
        -MAX_SITUATIONAL_PTS, min(MAX_SITUATIONAL_PTS, away_pts)
    )

    meta["applied"] = True
    meta["reason"] = "gates_passed"
    meta["home_pts_raw"] = round(home_raw, 3)
    meta["away_pts_raw"] = round(away_raw, 3)
    meta["weight"] = round(weight, 4)
    meta["home_pts"] = round(home_pts, 3)
    meta["away_pts"] = round(away_pts, 3)
    return round(home_pts, 3), round(away_pts, 3), meta


def event_tendency_payload(
    *,
    home_team_id: str | None,
    away_team_id: str | None,
    tendency_context: dict[str, Any] | None,
    situational_meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Structured block for slate events / Market Detail UI."""

    profiles = (tendency_context or {}).get("profiles") or {}
    if not profiles:
        return None
    home = profiles.get(str(home_team_id or "")) or {}
    away = profiles.get(str(away_team_id or "")) or {}
    if not home and not away:
        return None
    sit = situational_meta or {}
    return {
        "available": bool(home.get("available") or away.get("available")),
        "home": _public_profile(home),
        "away": _public_profile(away),
        "situational": {
            "applied": bool(sit.get("applied")),
            "home_pts": sit.get("home_pts"),
            "away_pts": sit.get("away_pts"),
            "home_faces_tier": sit.get("away_tier"),
            "away_faces_tier": sit.get("home_tier"),
            "reason": sit.get("reason"),
        },
        "games_used": (tendency_context or {}).get("games_used"),
        "before_week": (tendency_context or {}).get("before_week"),
    }


# --- internals ---------------------------------------------------------


def _collect_game_residual_rows(
    *,
    season: int,
    before_week: int | None,
    include_prior_season: bool,
    sport_config: BettingSportConfig,
) -> list[dict[str, Any]]:
    seasons = [int(season)]
    if include_prior_season:
        seasons.insert(0, int(season) - 1)

    # Lazy import avoids cycle with residual_challenger_dataset.
    from app.analysis.insights.betting.residual_challenger_dataset import (
        _load_completed_market_games,
    )

    # CFB: one strength snapshot per season year. Per-week rebuilds
    # make the betting slate hang (230 teams × many weeks).
    coarse = sport_config.id == "CFB"
    rows: list[dict[str, Any]] = []
    for season_year in seasons:
        through = (
            None
            if season_year < int(season)
            else (
                (int(before_week) - 1)
                if before_week is not None
                else None
            )
        )
        if through is not None and through < 1:
            continue
        games = _load_completed_market_games(
            season=season_year,
            through_week=through,
            schema=sport_config.schema,
        )
        if not games:
            continue

        season_context: dict[str, Any] | None = None
        if coarse:
            season_context = load_team_strength_context(
                season=season_year,
                before_week=(
                    None
                    if season_year < int(season)
                    else before_week
                ),
                sport=sport_config,
            )

        context_by_week: dict[int, dict[str, Any]] = {}
        for game in games:
            week = int(game.get("week") or 0)
            if week <= 0:
                continue
            if (
                season_year == int(season)
                and before_week is not None
                and week >= int(before_week)
            ):
                continue
            if coarse:
                context = season_context or {"profiles": {}}
            else:
                if week not in context_by_week:
                    context_by_week[week] = load_team_strength_context(
                        season=season_year,
                        before_week=week,
                        sport=sport_config,
                    )
                context = context_by_week[week]
            rows.extend(
                _game_to_team_rows(game, strength_context=context)
            )
    return rows


def _game_to_team_rows(
    game: dict[str, Any],
    *,
    strength_context: dict[str, Any],
) -> list[dict[str, Any]]:
    home_id = str(game.get("home_team_id") or "")
    away_id = str(game.get("away_team_id") or "")
    market_home = num(game.get("home_implied_total"))
    market_away = num(game.get("away_implied_total"))
    actual_home = num(game.get("home_score"))
    actual_away = num(game.get("away_score"))
    if (
        not home_id
        or not away_id
        or market_home is None
        or market_away is None
        or actual_home is None
        or actual_away is None
    ):
        return []

    model_home, model_away, detail = project_strength_scores(
        home_team_id=home_id,
        away_team_id=away_id,
        context=strength_context,
    )
    if model_home is None or model_away is None:
        # Fall back to market-only model residual = 0 vs market.
        model_home = float(market_home)
        model_away = float(market_away)

    actual_margin_home = float(actual_home) - float(actual_away)
    market_margin_home = float(market_home) - float(market_away)
    model_margin_home = float(model_home) - float(model_away)
    actual_total = float(actual_home) + float(actual_away)
    market_total = float(market_home) + float(market_away)
    model_total = float(model_home) + float(model_away)

    profiles = strength_context.get("profiles") or {}
    tier_map = _tier_map_for_profiles(profiles)

    home_row = _team_game_row(
        team_id=home_id,
        opponent_id=away_id,
        is_home=True,
        margin_resid_market=actual_margin_home - market_margin_home,
        margin_resid_model=actual_margin_home - model_margin_home,
        total_resid_market=actual_total - market_total,
        total_resid_model=actual_total - model_total,
        opponent_tier=tier_map.get(away_id, "average"),
        opponent_profile=profiles.get(away_id) or {},
        detail=detail,
    )
    away_row = _team_game_row(
        team_id=away_id,
        opponent_id=home_id,
        is_home=False,
        margin_resid_market=-(actual_margin_home - market_margin_home),
        margin_resid_model=-(actual_margin_home - model_margin_home),
        total_resid_market=actual_total - market_total,
        total_resid_model=actual_total - model_total,
        opponent_tier=tier_map.get(home_id, "average"),
        opponent_profile=profiles.get(home_id) or {},
        detail=detail,
    )
    return [home_row, away_row]


def _team_game_row(
    *,
    team_id: str,
    opponent_id: str,
    is_home: bool,
    margin_resid_market: float,
    margin_resid_model: float,
    total_resid_market: float,
    total_resid_model: float,
    opponent_tier: str,
    opponent_profile: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    opp_def = opponent_profile.get("defense") or {}
    return {
        "team_id": team_id,
        "opponent_id": opponent_id,
        "is_home": is_home,
        "margin_resid_market": float(margin_resid_market),
        "margin_resid_model": float(margin_resid_model),
        "total_resid_market": float(total_resid_market),
        "total_resid_model": float(total_resid_model),
        "opponent_tier": opponent_tier,
        "opp_pass_d": float(num(opp_def.get("pass_defense")) or 0.0),
        "opp_rush_d": float(num(opp_def.get("rush_defense")) or 0.0),
        "opp_explosive_d": float(
            num(opp_def.get("explosive_plays_allowed")) or 0.0
        ),
        "strength_available": bool(detail.get("available")),
    }


def _tier_map_for_profiles(
    profiles: dict[str, dict[str, Any]],
) -> dict[str, str]:
    scores: dict[str, float] = {}
    for tid, prof in profiles.items():
        off = float(num(prof.get("offensive_efficiency")) or 0.0)
        deff = float(num(prof.get("defensive_efficiency")) or 0.0)
        scores[str(tid)] = off + deff
    if not scores:
        return {}
    values = sorted(scores.values())
    n = len(values)
    q1 = values[max(0, n // 4 - 1)] if n >= 4 else values[0]
    q2 = values[n // 2]
    q3 = values[min(n - 1, (3 * n) // 4)] if n >= 4 else values[-1]
    out: dict[str, str] = {}
    for tid, score in scores.items():
        if score >= q3:
            out[tid] = "elite"
        elif score >= q2:
            out[tid] = "above_avg"
        elif score >= q1:
            out[tid] = "average"
        else:
            out[tid] = "below_avg"
    return out


def _tier_from_strength_profile(
    profile: dict[str, Any] | None,
) -> str:
    if not profile:
        return "average"
    # Single-profile fallback: use efficiency magnitudes.
    off = float(num(profile.get("offensive_efficiency")) or 0.0)
    deff = float(num(profile.get("defensive_efficiency")) or 0.0)
    score = off + deff
    if score >= 1.0:
        return "elite"
    if score >= 0.25:
        return "above_avg"
    if score <= -1.0:
        return "below_avg"
    if score <= -0.25:
        return "average"
    return "average"


def _aggregate_team_profiles(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tid = str(row.get("team_id") or "")
        if tid:
            by_team[tid].append(row)

    # Global pass-D terciles for matchup buckets.
    pass_d_values = [
        float(r.get("opp_pass_d") or 0.0) for r in rows
    ]
    pass_cut_hi, pass_cut_lo = _tercile_cuts(pass_d_values)

    profiles: dict[str, dict[str, Any]] = {}
    for tid, games in by_team.items():
        mkt_all = [float(g["margin_resid_market"]) for g in games]
        model_all = [float(g["margin_resid_model"]) for g in games]
        elite_mkt = [
            float(g["margin_resid_market"])
            for g in games
            if g.get("opponent_tier") in {"elite", "above_avg"}
        ]
        elite_model = [
            float(g["margin_resid_model"])
            for g in games
            if g.get("opponent_tier") in {"elite", "above_avg"}
        ]
        soft_mkt = [
            float(g["margin_resid_market"])
            for g in games
            if g.get("opponent_tier") == "below_avg"
        ]
        soft_model = [
            float(g["margin_resid_model"])
            for g in games
            if g.get("opponent_tier") == "below_avg"
        ]
        # Top tercile pass defense (higher pass_d = better D in our z).
        pass_hi_mkt = [
            float(g["margin_resid_market"])
            for g in games
            if float(g.get("opp_pass_d") or 0.0) >= pass_cut_hi
        ]

        elite_n = len(elite_mkt)
        soft_n = len(soft_mkt)
        pass_n = len(pass_hi_mkt)

        elite_mkt_s = _shrink_mean(
            elite_mkt, k=SHRINK_K_MARGIN, min_n=MIN_N_ELITE_SOFT
        )
        soft_mkt_s = _shrink_mean(
            soft_mkt, k=SHRINK_K_MARGIN, min_n=MIN_N_ELITE_SOFT
        )
        elite_model_s = _shrink_mean(
            elite_model, k=SHRINK_K_MARGIN, min_n=MIN_N_ELITE_SOFT
        )
        soft_model_s = _shrink_mean(
            soft_model, k=SHRINK_K_MARGIN, min_n=MIN_N_ELITE_SOFT
        )
        pass_mkt_s = _shrink_mean(
            pass_hi_mkt, k=SHRINK_K_MATCHUP, min_n=MIN_N_MATCHUP
        )

        vol = pstdev(mkt_all) if len(mkt_all) >= 2 else 0.0
        consistency = (
            sum(1 for v in mkt_all if abs(v) <= CONSISTENCY_BAND)
            / len(mkt_all)
            if mkt_all
            else 0.0
        )

        # Market edge beyond model: residual of market residual after
        # regressing out model residual (simple difference of means).
        market_edge_elite = elite_mkt_s - elite_model_s
        market_edge_soft = soft_mkt_s - soft_model_s

        by_tier: dict[str, dict[str, Any]] = {}
        for tier in TIERS:
            tier_mkt = [
                float(g["margin_resid_market"])
                for g in games
                if g.get("opponent_tier") == tier
            ]
            tier_model = [
                float(g["margin_resid_model"])
                for g in games
                if g.get("opponent_tier") == tier
            ]
            by_tier[tier] = {
                "n": len(tier_mkt),
                "margin_resid_market": _round(
                    mean(tier_mkt) if tier_mkt else 0.0
                ),
                "margin_resid_model": _round(
                    mean(tier_model) if tier_model else 0.0
                ),
            }

        available = (
            elite_n >= MIN_N_ELITE_SOFT or soft_n >= MIN_N_ELITE_SOFT
        )
        profiles[tid] = {
            "team_id": tid,
            "available": available,
            "games": len(games),
            "elite_n": elite_n,
            "soft_n": soft_n,
            "pass_d_tier_n": pass_n,
            "elite_margin_resid_mkt": _round(elite_mkt_s),
            "soft_margin_resid_mkt": _round(soft_mkt_s),
            "elite_margin_resid_model": _round(elite_model_s),
            "soft_margin_resid_model": _round(soft_model_s),
            "pass_d_tier_resid_mkt": _round(pass_mkt_s),
            "resid_vol_mkt": _round(vol),
            "consistency_mkt": _round(consistency),
            "market_edge_elite": _round(market_edge_elite),
            "market_edge_soft": _round(market_edge_soft),
            "by_tier": by_tier,
            "mean_margin_resid_mkt": _round(
                mean(mkt_all) if mkt_all else 0.0
            ),
            "mean_margin_resid_model": _round(
                mean(model_all) if model_all else 0.0
            ),
        }
    return profiles


def _tier_signal_points(
    profile: dict[str, Any],
    *,
    opponent_tier: str,
) -> float:
    if not profile or not profile.get("available"):
        return 0.0
    if opponent_tier in {"elite", "above_avg"}:
        if int(profile.get("elite_n") or 0) < MIN_N_ELITE_SOFT:
            return 0.0
        return float(profile.get("elite_margin_resid_mkt") or 0.0)
    if opponent_tier == "below_avg":
        if int(profile.get("soft_n") or 0) < MIN_N_ELITE_SOFT:
            return 0.0
        return float(profile.get("soft_margin_resid_mkt") or 0.0)
    return 0.0


def _shrink_mean(
    values: list[float],
    *,
    k: float,
    min_n: int,
) -> float:
    if len(values) < min_n:
        return 0.0
    raw = mean(values)
    weight = len(values) / (len(values) + k)
    return float(raw) * weight


def _tercile_cuts(values: list[float]) -> tuple[float, float]:
    if len(values) < 3:
        return 0.5, -0.5
    ordered = sorted(values)
    n = len(ordered)
    hi = ordered[min(n - 1, (2 * n) // 3)]
    lo = ordered[max(0, n // 3)]
    return float(hi), float(lo)


def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not profile:
        return {"available": False}
    return {
        "available": bool(profile.get("available")),
        "games": profile.get("games"),
        "elite_n": profile.get("elite_n"),
        "soft_n": profile.get("soft_n"),
        "elite_margin_resid_mkt": profile.get("elite_margin_resid_mkt"),
        "soft_margin_resid_mkt": profile.get("soft_margin_resid_mkt"),
        "elite_margin_resid_model": profile.get(
            "elite_margin_resid_model"
        ),
        "soft_margin_resid_model": profile.get(
            "soft_margin_resid_model"
        ),
        "pass_d_tier_resid_mkt": profile.get("pass_d_tier_resid_mkt"),
        "resid_vol_mkt": profile.get("resid_vol_mkt"),
        "consistency_mkt": profile.get("consistency_mkt"),
        "market_edge_elite": profile.get("market_edge_elite"),
        "market_edge_soft": profile.get("market_edge_soft"),
        "by_tier": profile.get("by_tier"),
    }


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


# Test helpers (pure functions, no DB).
def assign_opponent_tiers(
    strength_scores: dict[str, float],
) -> dict[str, str]:
    """Public wrapper for quartile tier assignment (tests)."""

    fake_profiles = {
        tid: {
            "offensive_efficiency": score / 2.0,
            "defensive_efficiency": score / 2.0,
        }
        for tid, score in strength_scores.items()
    }
    return _tier_map_for_profiles(fake_profiles)


def shrink_mean(
    values: list[float],
    *,
    k: float = SHRINK_K_MARGIN,
    min_n: int = MIN_N_ELITE_SOFT,
) -> float:
    return _shrink_mean(values, k=k, min_n=min_n)
