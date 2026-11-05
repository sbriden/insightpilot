"""
Team Power Rankings engine (NFL + CFB).

Opponent-adjusted, recency-weighted team strength ratings expressed
in points above/below league average. Independent of sportsbook odds.

Reuses canonical ``fact_team_game`` / ``fact_defensive_game`` loaders
from ``team_strength`` — does not invent a parallel team model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.betting_sport import (
    BettingSportConfig,
    SPORT_CFB,
    SPORT_NFL,
    resolve_betting_sport,
)
from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.slate import _sport_team_logo_url
from app.analysis.insights.betting.team_strength import (
    DEFAULT_LEAGUE_AVG_PPG,
    _defense_game_metrics,
    _group_by_team,
    _load_defense_games,
    _load_offense_games,
    _mean_metrics,
    _offense_game_metrics,
    _resolve_league_avg_ppg,
    _team_defense_baselines,
    _team_offense_baselines,
)
from app.database import engine

CALCULATION_VERSION = "power_rankings.v1.6"
DEFAULT_HALF_LIFE_WEEKS = 5.0
DEFAULT_PRIOR_K = 5.0
DEFAULT_HFA_POINTS = 2.0
DEFAULT_CFB_HFA_POINTS = 2.5
MAX_OPP_ADJ_ITERATIONS = 4
POINTS_PER_OFFENSE_Z = 2.4
POINTS_PER_DEFENSE_Z = 2.4
POINTS_PER_ST_Z = 0.6
# Live ranking nudge from recent scoring form (pts vs league avg).
# Kept out of baseline so season-long strength stays separable.
FORM_RATING_SCALE = 0.15
# SOS adjustment: NFL uses z-scores; CFB uses raw SOS points so mildly
# soft G5 slates are not "above average" just because FCS padding is common.
NFL_SOS_RATING_SCALE = 0.75
# Direct SOS is lighter than the off/def multiplier — avoid double-counting.
CFB_SOS_DIRECT_SCALE = 0.55  # rating pts per SOS point (opp strength units)
# Cap so schedule cannot overwhelm observed play (e.g. 1-win P4 sides).
SOS_ADJUSTMENT_CAP = 4.0
# CFB form nudge is smaller — recent scoring is noisy vs soft G5/FCS foes.
CFB_FORM_RATING_SCALE = 0.08
# Extra CFB schedule multiplier on off/def (soft slate discounts production).
# Asymmetric: soft schedules are penalized harder than hard schedules are boosted.
CFB_SOS_MULT_PER_POINT = 0.06  # used for positive SOS
CFB_SOS_MULT_PER_POINT_SOFT = 0.14  # used when SOS < 0
CFB_SOS_MULT_FLOOR = 0.60
CFB_SOS_MULT_CEIL = 1.18
# CFB SOS blend: opponent win% separates G5 padding from P4 gauntlets
# better than efficiency composites alone (cupcakes pad yards on each other).
CFB_SOS_STRENGTH_WEIGHT = 0.35
CFB_SOS_WINPCT_WEIGHT = 0.65
CFB_SOS_WINPCT_SCALE = 12.0  # (win_pct - 0.5) * scale → ±6 at extremes
# W/L record component (centered at .500). Undefeated ≈ +scale.
NFL_RECORD_RATING_SCALE = 3.5
CFB_RECORD_RATING_SCALE = 6.0
# Blend: share of record signal from win% vs opponent-quality weighted results.
# CFB leans harder on quality so G5 padding cannot buy elite record credit.
RECORD_WIN_PCT_WEIGHT = 0.60
RECORD_QUALITY_WEIGHT = 0.40
CFB_RECORD_WIN_PCT_WEIGHT = 0.35
CFB_RECORD_QUALITY_WEIGHT = 0.65
# Soft-opponent win coefficient (higher → cupcake wins count less).
RECORD_OPP_QUALITY_COEF = 0.08
CFB_RECORD_OPP_QUALITY_COEF = 0.14

# Primary efficiency composites — avoid stacking correlated EPA proxies.
# fact_team_game stores EPA but not true PBP success rate; yards/play is
# the independent secondary signal. Scoring residual carries opponent-
# adjusted results (quality wins / bad losses).
OFFENSE_SIGNAL_WEIGHTS = {
    "epa_per_play": 0.45,
    "explosive_rate": 0.20,
    "scoring_margin_proxy": 0.35,
}
# CFB facts lack EPA — lean on yards/play + opponent-adjusted scoring.
CFB_OFFENSE_SIGNAL_WEIGHTS = {
    "epa_per_play": 0.0,
    "explosive_rate": 0.35,
    "scoring_margin_proxy": 0.65,
}
DEFENSE_SIGNAL_WEIGHTS = {
    "epa_allowed_per_play": 0.45,
    "explosive_allowed": 0.20,
    "points_allowed": 0.35,
}
CFB_DEFENSE_SIGNAL_WEIGHTS = {
    "epa_allowed_per_play": 0.0,
    "explosive_allowed": 0.35,
    "points_allowed": 0.65,
}
# Normalize yards/play toward an EPA-ish scale for composites.
YARDS_PER_PLAY_BASELINE = 5.5
YARDS_PER_PLAY_SCALE = 2.0


def build_nfl_power_rankings(
    *,
    season: int,
    week: int | None = None,
    half_life_weeks: float = DEFAULT_HALF_LIFE_WEEKS,
    prior_k: float = DEFAULT_PRIOR_K,
    home_field_advantage: float = DEFAULT_HFA_POINTS,
    persist: bool = False,
    include_personnel: bool = True,
    compare_previous: bool = True,
) -> dict[str, Any]:
    """NFL wrapper around ``build_power_rankings``."""

    return build_power_rankings(
        sport=SPORT_NFL,
        season=season,
        week=week,
        half_life_weeks=half_life_weeks,
        prior_k=prior_k,
        home_field_advantage=home_field_advantage,
        persist=persist,
        include_personnel=include_personnel,
        compare_previous=compare_previous,
    )


def build_cfb_power_rankings(
    *,
    season: int,
    week: int | None = None,
    half_life_weeks: float = DEFAULT_HALF_LIFE_WEEKS,
    prior_k: float = DEFAULT_PRIOR_K,
    home_field_advantage: float = DEFAULT_CFB_HFA_POINTS,
    persist: bool = False,
    include_personnel: bool = False,
    compare_previous: bool = True,
) -> dict[str, Any]:
    """CFB wrapper around ``build_power_rankings``."""

    return build_power_rankings(
        sport=SPORT_CFB,
        season=season,
        week=week,
        half_life_weeks=half_life_weeks,
        prior_k=prior_k,
        home_field_advantage=home_field_advantage,
        persist=persist,
        include_personnel=include_personnel,
        compare_previous=compare_previous,
    )


def build_power_rankings(
    *,
    sport: str = SPORT_NFL,
    season: int,
    week: int | None = None,
    half_life_weeks: float = DEFAULT_HALF_LIFE_WEEKS,
    prior_k: float = DEFAULT_PRIOR_K,
    home_field_advantage: float | None = None,
    persist: bool = False,
    include_personnel: bool | None = None,
    compare_previous: bool = True,
) -> dict[str, Any]:
    """
    Build power rankings using only games completed before ``week``.

    When ``week`` is None, uses all completed games in ``season``.
    A Week N snapshot never includes Week N (or later) results.

    ``compare_previous`` loads/rebuilds the prior week's ranks for
    week-over-week rank movement (``rank_change`` / ``rating_trend``).
    Set False when rebuilding a comparison baseline to avoid recursion.
    """

    sport_config = resolve_betting_sport(sport)
    if home_field_advantage is None:
        home_field_advantage = (
            DEFAULT_CFB_HFA_POINTS
            if sport_config.id == SPORT_CFB
            else DEFAULT_HFA_POINTS
        )
    if include_personnel is None:
        include_personnel = bool(sport_config.has_injury_context)

    before_week = int(week) if week is not None else None
    snapshot_week = _resolve_snapshot_week(
        season=season,
        before_week=before_week,
        sport_config=sport_config,
    )

    offense_rows = _load_offense_games(
        season=season,
        before_week=before_week,
        sport_config=sport_config,
    )
    defense_rows = _load_defense_games(
        season=season,
        before_week=before_week,
        sport_config=sport_config,
    )
    active_ids = {
        str(row.get("team_id"))
        for row in offense_rows + defense_rows
        if row.get("team_id")
    }
    teams = _load_teams(
        sport_config,
        active_team_ids=active_ids,
    )
    if not teams:
        return _empty_payload(
            sport=sport_config.id,
            season=season,
            week=snapshot_week,
            reason=f"No {sport_config.id} teams found in dim_team.",
        )

    if not offense_rows and not defense_rows:
        return _empty_payload(
            sport=sport_config.id,
            season=season,
            week=snapshot_week,
            reason=(
                "No completed team-game performance rows for this "
                "season/week window."
            ),
        )

    offense_by_team = _group_by_team(offense_rows, "team_id")
    defense_by_team = _group_by_team(defense_rows, "team_id")
    current_week_ref = float(before_week or (snapshot_week + 1))

    opponent_game_counts = {
        tid: max(
            len(offense_by_team.get(tid) or []),
            len(defense_by_team.get(tid) or []),
        )
        for tid in set(offense_by_team) | set(defense_by_team)
    }
    exclude_efficiency_opponents: set[str] = set()
    if sport_config.id == SPORT_CFB:
        # FCS foes pollute efficiency the same way they polluted SOS —
        # a 77-7 box score becomes the opponent's entire defensive profile.
        exclude_efficiency_opponents = _cfb_fcs_opponent_ids(
            offense_by_team=offense_by_team,
            defense_by_team=defense_by_team,
            sport_config=sport_config,
        )

    # Iterative opponent adjustment.
    off_means, def_means, league_avg_ppg, iterations = (
        _iterative_opponent_adjustment(
            offense_by_team=offense_by_team,
            defense_by_team=defense_by_team,
            current_week_ref=current_week_ref,
            half_life_weeks=half_life_weeks,
            sport_config=sport_config,
            opponent_game_counts=opponent_game_counts,
            exclude_opponent_ids=exclude_efficiency_opponents,
        )
    )

    priors = _load_prior_ratings(
        season=season,
        sport_config=sport_config,
    )
    personnel = (
        _personnel_adjustments(
            season=season,
            week=snapshot_week,
            sport=sport_config.id,
        )
        if include_personnel
        else {}
    )

    # League z for point conversion.
    off_raw = {
        tid: _offense_composite(metrics, sport_config=sport_config)
        for tid, metrics in off_means.items()
    }
    def_raw = {
        tid: _defense_composite(metrics, sport_config=sport_config)
        for tid, metrics in def_means.items()
    }
    st_raw = {
        tid: _special_teams_proxy(
            off_means.get(tid) or {},
            def_means.get(tid) or {},
            league_avg_ppg=league_avg_ppg,
        )
        for tid in set(off_raw) | set(def_raw)
    }
    off_z = _zscore_map(off_raw)
    def_z = _zscore_map(def_raw)
    st_z = _zscore_map(st_raw)

    previous = (
        _load_previous_snapshot(
            season=season,
            week=snapshot_week,
            sport=sport_config.id,
            half_life_weeks=half_life_weeks,
            prior_k=prior_k,
            home_field_advantage=float(home_field_advantage),
            include_personnel=bool(include_personnel),
        )
        if compare_previous
        else {}
    )

    rows: list[dict[str, Any]] = []
    calculated_at = datetime.now(timezone.utc).isoformat()
    data_limitations: list[str] = [
        "Special teams rating uses a scoring residual proxy; "
        "true ST EPA/return metrics are not persisted in fact tables.",
        "Power rankings are independent of sportsbook prices.",
    ]
    if sport_config.has_epa_features:
        data_limitations.append(
            "Explosive rates use yards/play proxies from fact tables "
            "(PBP success flags are not stored)."
        )
    else:
        data_limitations.append(
            f"{sport_config.id} facts lack EPA — rankings emphasize "
            "opponent-adjusted scoring and yards/play."
        )
    if sport_config.id == SPORT_CFB:
        data_limitations.append(
            "CFB rankings include FBS teams with completed games; "
            "FCS opponents are excluded from SOS, efficiency, and form. "
            "SOS uses opponent off+def strength composites."
        )
    if not personnel:
        data_limitations.append(
            "Personnel adjustments are zero — injury/player-impact "
            "context unavailable or insufficient for this snapshot."
        )

    # CFB SOS ignores FCS foes — a one-game FCS blowout (e.g. Miami vs
    # FAMU 77-7) otherwise dominates the schedule average.
    exclude_sos_opponents = exclude_efficiency_opponents
    # Opponent strength for CFB SOS / record quality: blend efficiency
    # composites with win% so G5 sides that pad yards on each other do not
    # look like a hard slate.
    win_pct_by_team = _team_win_pcts(
        offense_by_team=offense_by_team,
        defense_by_team=defense_by_team,
        exclude_opponent_ids=exclude_efficiency_opponents,
    )
    opp_strength_by_team = {
        tid: (
            CFB_SOS_STRENGTH_WEIGHT
            * (
                POINTS_PER_OFFENSE_Z * float(off_z.get(tid) or 0.0)
                + POINTS_PER_DEFENSE_Z * float(def_z.get(tid) or 0.0)
            )
            + CFB_SOS_WINPCT_WEIGHT
            * (
                (float(win_pct_by_team.get(tid, 0.5)) - 0.5)
                * CFB_SOS_WINPCT_SCALE
            )
        )
        for tid in set(off_z) | set(def_z) | set(win_pct_by_team)
    }

    draft: list[dict[str, Any]] = []
    sos_raw_by_team: dict[str, float] = {}
    for team in teams:
        tid = str(team["team_id"])
        games_off = offense_by_team.get(tid) or []
        games_def = defense_by_team.get(tid) or []
        games_sample = len(games_off) or len(games_def)
        # CFB: do not fabricate ranks for teams with no games in window.
        if sport_config.id == SPORT_CFB and games_sample == 0:
            continue
        sos = _team_sos(
            games_off=games_off,
            games_def=games_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=league_avg_ppg,
            opponent_game_counts=opponent_game_counts,
            exclude_opponent_ids=exclude_sos_opponents,
            opp_strength_by_team=(
                opp_strength_by_team
                if sport_config.id == SPORT_CFB
                else None
            ),
        )
        sos_raw_by_team[tid] = sos
        draft.append(
            {
                "team": team,
                "tid": tid,
                "games_off": games_off,
                "games_def": games_def,
                "games_sample": games_sample,
                "sos": sos,
            }
        )

    sos_z = _zscore_map(sos_raw_by_team)

    for item in draft:
        team = item["team"]
        tid = item["tid"]
        abbr = str(team.get("team_abbreviation") or "")
        name = str(team.get("team_name") or abbr)
        games_off = item["games_off"]
        games_def = item["games_def"]
        games_sample = item["games_sample"]
        sos = float(item["sos"])
        effective_games = _effective_game_count(
            games_off,
            games_def,
            current_week_ref=current_week_ref,
            half_life_weeks=half_life_weeks,
        )
        lam = _shrinkage_lambda(
            effective_games=effective_games,
            prior_k=prior_k,
        )
        prior = priors.get(tid) or {
            "offensive_rating": 0.0,
            "defensive_rating": 0.0,
            "special_teams_rating": 0.0,
        }

        obs_off = float(off_z.get(tid) or 0.0) * POINTS_PER_OFFENSE_Z
        obs_def = float(def_z.get(tid) or 0.0) * POINTS_PER_DEFENSE_Z
        obs_st = float(st_z.get(tid) or 0.0) * POINTS_PER_ST_Z

        offensive_rating = (
            lam * obs_off + (1.0 - lam) * float(prior["offensive_rating"])
        )
        defensive_rating = (
            lam * obs_def + (1.0 - lam) * float(prior["defensive_rating"])
        )
        special_teams_rating = (
            lam * obs_st
            + (1.0 - lam) * float(prior["special_teams_rating"])
        )
        if sport_config.id == SPORT_CFB:
            # Raw SOS (not z): negative always penalizes soft G5/FCS padding.
            sos_adj = CFB_SOS_DIRECT_SCALE * sos
            mult_per = (
                CFB_SOS_MULT_PER_POINT_SOFT
                if sos < 0.0
                else CFB_SOS_MULT_PER_POINT
            )
            sos_mult = max(
                CFB_SOS_MULT_FLOOR,
                min(
                    CFB_SOS_MULT_CEIL,
                    1.0 + mult_per * sos,
                ),
            )
            offensive_rating *= sos_mult
            defensive_rating *= sos_mult
            special_teams_rating *= sos_mult
        else:
            sos_adj = NFL_SOS_RATING_SCALE * float(sos_z.get(tid) or 0.0)
        sos_adj = max(
            -SOS_ADJUSTMENT_CAP,
            min(SOS_ADJUSTMENT_CAP, sos_adj),
        )
        record = _team_record(
            games_off=games_off,
            games_def=games_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=league_avg_ppg,
            sport_id=sport_config.id,
            opp_strength_by_team=(
                opp_strength_by_team
                if sport_config.id == SPORT_CFB
                else None
            ),
            exclude_opponent_ids=exclude_efficiency_opponents,
        )
        record_scale = (
            CFB_RECORD_RATING_SCALE
            if sport_config.id == SPORT_CFB
            else NFL_RECORD_RATING_SCALE
        )
        record_adj = float(record_scale) * float(record["record_signal"])
        baseline = (
            offensive_rating
            + defensive_rating
            + special_teams_rating
            + sos_adj
            + record_adj
        )
        personnel_adj = float(
            (personnel.get(tid) or {}).get("adjustment") or 0.0
        )
        form = _recent_form(
            games_off=games_off,
            games_def=games_def,
            current_week_ref=current_week_ref,
            half_life_weeks=half_life_weeks,
            league_avg_ppg=league_avg_ppg,
            off_means=off_means,
            def_means=def_means,
            opponent_game_counts=opponent_game_counts,
            exclude_opponent_ids=exclude_efficiency_opponents,
            sport_id=sport_config.id,
        )
        form_scale = (
            CFB_FORM_RATING_SCALE
            if sport_config.id == SPORT_CFB
            else FORM_RATING_SCALE
        )
        form_adj = form_scale * float(form)
        current_adjusted = baseline + personnel_adj + form_adj
        overall = current_adjusted
        explanation = _explain_components(
            offensive_rating=offensive_rating,
            defensive_rating=defensive_rating,
            special_teams_rating=special_teams_rating,
            personnel_adj=personnel_adj,
            form=form,
            sos=sos,
            wins=int(record["wins"]),
            losses=int(record["losses"]),
            win_pct=float(record["win_pct"]),
        )

        row_out: dict[str, Any] = {
            "team_id": tid,
            "team_abbreviation": abbr,
            "team_name": name,
            "season": int(season),
            "week": int(snapshot_week),
            "sport": sport_config.id,
            "logo_url": _team_logo_url_for_ranking(
                sport_config.id,
                abbreviation=abbr,
                espn_team_id=team.get("espn_team_id"),
            ),
            "offensive_rating": round(offensive_rating, 3),
            "defensive_rating": round(defensive_rating, 3),
            "special_teams_rating": round(special_teams_rating, 3),
            "overall_power_rating": round(overall, 3),
            "baseline_power_rating": round(baseline, 3),
            "current_adjusted_rating": round(current_adjusted, 3),
            "personnel_adjustment": round(personnel_adj, 3),
            "form_adjustment": round(form_adj, 3),
            "sos_adjustment": round(sos_adj, 3),
            "record_adjustment": round(record_adj, 3),
            "wins": int(record["wins"]),
            "losses": int(record["losses"]),
            "ties": int(record["ties"]),
            "win_pct": round(float(record["win_pct"]), 3),
            "recent_form": round(form, 3),
            "strength_of_schedule": round(sos, 3),
            "confidence": round(lam, 3),
            "effective_games": round(effective_games, 3),
            "rating_trend": None,
            "shrinkage_lambda": round(lam, 3),
            "games_sample": games_sample,
            "explanation": explanation,
            "calculation_version": CALCULATION_VERSION,
            "calculated_at": calculated_at,
        }
        if team.get("conference"):
            row_out["conference"] = team.get("conference")
        rows.append(row_out)

    rows.sort(
        key=lambda row: (
            -float(row["overall_power_rating"]),
            str(row["team_abbreviation"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        tid = row["team_id"]
        prev_rank = (previous.get(tid) or {}).get("rank")
        row["rank"] = index
        row["previous_rank"] = prev_rank
        # Positive = moved up (better rank number).
        rank_change = (
            int(prev_rank) - index if prev_rank is not None else None
        )
        row["rank_change"] = rank_change
        # Trend column: week-over-week rank movement (not rating points).
        row["rating_trend"] = rank_change

    payload = {
        "sport": sport_config.id,
        "season": int(season),
        "week": int(snapshot_week),
        "before_week": before_week,
        "team_count": len(rows),
        "games_used": len(offense_rows),
        "league_avg_ppg": round(league_avg_ppg, 3),
        "home_field_advantage": float(home_field_advantage),
        "half_life_weeks": float(half_life_weeks),
        "prior_k": float(prior_k),
        "opponent_adjustment_iterations": iterations,
        "calculation_version": CALCULATION_VERSION,
        "calculated_at": calculated_at,
        "data_limitations": data_limitations,
        "metric_definitions": _metric_definitions(
            sport_config=sport_config
        ),
        "rankings": rows,
    }

    if persist and rows:
        from app.canonical.fact_team_power_ranking import (
            persist_power_ranking_snapshot,
        )

        persist_power_ranking_snapshot(payload)

    return payload


def project_margin_from_power_rankings(
    *,
    home_team_id: str,
    away_team_id: str,
    rankings_by_team: dict[str, dict[str, Any]],
    home_field_advantage: float = DEFAULT_HFA_POINTS,
) -> dict[str, Any]:
    """
    Neutral-style matchup projection from power ratings.

    expected_margin = home_rating - away_rating + HFA
    (home perspective). Does not use sportsbook prices.
    """

    home = rankings_by_team.get(str(home_team_id)) or {}
    away = rankings_by_team.get(str(away_team_id)) or {}
    home_rating = num(home.get("current_adjusted_rating"))
    away_rating = num(away.get("current_adjusted_rating"))
    if home_rating is None or away_rating is None:
        return {
            "available": False,
            "expected_margin": None,
            "home_projected_score": None,
            "away_projected_score": None,
        }
    margin = (
        float(home_rating) - float(away_rating) + float(home_field_advantage)
    )
    # Split margin around league-average scoring level when present.
    league_avg = DEFAULT_LEAGUE_AVG_PPG
    home_off = float(num(home.get("offensive_rating")) or 0.0)
    away_off = float(num(away.get("offensive_rating")) or 0.0)
    home_def = float(num(home.get("defensive_rating")) or 0.0)
    away_def = float(num(away.get("defensive_rating")) or 0.0)
    home_score = league_avg + home_off - away_def + (
        float(home_field_advantage) / 2.0
    )
    away_score = league_avg + away_off - home_def - (
        float(home_field_advantage) / 2.0
    )
    # Re-center so home - away matches expected margin.
    raw_margin = home_score - away_score
    if abs(raw_margin - margin) > 1e-9:
        shift = (margin - raw_margin) / 2.0
        home_score += shift
        away_score -= shift
    return {
        "available": True,
        "expected_margin": round(margin, 3),
        "home_projected_score": round(home_score, 3),
        "away_projected_score": round(away_score, 3),
        "home_rating": round(float(home_rating), 3),
        "away_rating": round(float(away_rating), 3),
        "home_field_advantage": float(home_field_advantage),
    }


def backtest_power_rankings_week(
    *,
    season: int,
    week: int,
    sport: str = SPORT_NFL,
    half_life_weeks: float = DEFAULT_HALF_LIFE_WEEKS,
    prior_k: float = DEFAULT_PRIOR_K,
) -> dict[str, Any]:
    """
    Reconstruct pre-week rankings and score margin prediction error
    for games played in ``week`` (no future leakage).
    """

    sport_config = resolve_betting_sport(sport)
    rankings = build_power_rankings(
        sport=sport_config.id,
        season=season,
        week=week,
        half_life_weeks=half_life_weeks,
        prior_k=prior_k,
        persist=False,
        include_personnel=False,
        compare_previous=False,
    )
    by_team = {
        row["team_id"]: row for row in rankings.get("rankings") or []
    }
    games = _load_completed_games_for_week(
        season=season,
        week=week,
        sport_config=sport_config,
    )
    errors: list[float] = []
    details: list[dict[str, Any]] = []
    for game in games:
        home_id = str(game.get("home_team_id") or "")
        away_id = str(game.get("away_team_id") or "")
        home_score = num(game.get("home_score"))
        away_score = num(game.get("away_score"))
        if (
            not home_id
            or not away_id
            or home_score is None
            or away_score is None
        ):
            continue
        actual_margin = float(home_score) - float(away_score)
        projected = project_margin_from_power_rankings(
            home_team_id=home_id,
            away_team_id=away_id,
            rankings_by_team=by_team,
        )
        if not projected.get("available"):
            continue
        pred = float(projected["expected_margin"])
        err = pred - actual_margin
        errors.append(err)
        details.append(
            {
                "game_id": game.get("game_id"),
                "predicted_margin": pred,
                "actual_margin": actual_margin,
                "error": err,
            }
        )
    mae = mean(abs(e) for e in errors) if errors else None
    rmse = (
        (mean(e * e for e in errors) ** 0.5) if errors else None
    )
    return {
        "sport": sport_config.id,
        "season": season,
        "week": week,
        "sample_size": len(errors),
        "mae": round(mae, 3) if mae is not None else None,
        "rmse": round(rmse, 3) if rmse is not None else None,
        "rankings_meta": {
            "team_count": rankings.get("team_count"),
            "games_used": rankings.get("games_used"),
            "calculation_version": rankings.get("calculation_version"),
        },
        "games": details,
    }


# ── internals ─────────────────────────────────────────────────────


def _empty_payload(
    *,
    sport: str = SPORT_NFL,
    season: int,
    week: int,
    reason: str,
) -> dict[str, Any]:
    sport_config = resolve_betting_sport(sport)
    return {
        "sport": sport_config.id,
        "season": int(season),
        "week": int(week),
        "team_count": 0,
        "games_used": 0,
        "rankings": [],
        "calculation_version": CALCULATION_VERSION,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
        "data_limitations": [reason],
        "metric_definitions": _metric_definitions(
            sport_config=sport_config
        ),
        "error": reason,
    }


def _metric_definitions(
    *,
    sport_config: BettingSportConfig | None = None,
) -> list[dict[str, str]]:
    config = sport_config or resolve_betting_sport(SPORT_NFL)
    schema = config.schema
    defs: list[dict[str, str]] = []
    if config.has_epa_features:
        defs.extend(
            [
                {
                    "metric": "offensive_epa_per_play",
                    "direction": "higher_better",
                    "source": f"{schema}.fact_team_game.offensive_epa / plays",
                    "role": "primary",
                },
                {
                    "metric": "defensive_epa_allowed_per_play",
                    "direction": "lower_raw_better_inverted_to_higher_rating",
                    "source": f"{schema}.fact_defensive_game EPA allowed",
                    "role": "primary",
                },
            ]
        )
    defs.extend(
        [
            {
                "metric": "explosive_rate_proxy",
                "direction": "higher_better",
                "source": f"yards / plays from {schema}.fact_team_game",
                "role": "primary",
            },
            {
                "metric": "opponent_adjusted_scoring",
                "direction": "higher_better",
                "source": "points vs expected given opponent defense rating",
                "role": "primary",
            },
            {
                "metric": "win_loss_record",
                "direction": "higher_better",
                "source": (
                    "win% centered at .500 blended with opponent-quality "
                    "weighted game results"
                ),
                "role": "primary",
            },
            {
                "metric": "special_teams_proxy",
                "direction": "higher_better",
                "source": "scoring residual vs efficiency expectation",
                "role": "secondary_limited",
            },
            {
                "metric": "recency_weight",
                "direction": "n/a",
                "source": "weight = 2 ** (-age_weeks / half_life)",
                "role": "weighting",
            },
            {
                "metric": "prior_shrinkage",
                "direction": "n/a",
                "source": "lambda = n_eff / (n_eff + k); blend vs prior season",
                "role": "regularization",
            },
        ]
    )
    return defs


def _resolve_snapshot_week(
    *,
    season: int,
    before_week: int | None,
    sport_config: BettingSportConfig,
) -> int:
    if before_week is not None:
        return max(1, int(before_week) - 1) if before_week > 1 else 1
    # Latest completed week with results.
    sql = text(
        f"""
        SELECT MAX(week) AS week
        FROM {sport_config.schema}.dim_game
        WHERE season = :season
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        """
    )
    try:
        with engine.connect() as connection:
            value = connection.execute(
                sql, {"season": int(season)}
            ).scalar()
        if value is not None:
            return int(value)
    except Exception:
        pass
    return 1


def _iterative_opponent_adjustment(
    *,
    offense_by_team: dict[str, list[dict[str, Any]]],
    defense_by_team: dict[str, list[dict[str, Any]]],
    current_week_ref: float,
    half_life_weeks: float,
    sport_config: BettingSportConfig,
    opponent_game_counts: dict[str, int] | None = None,
    exclude_opponent_ids: set[str] | None = None,
) -> tuple[
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
    float,
    int,
]:
    raw_off = _team_offense_baselines(offense_by_team)
    raw_def = _team_defense_baselines(defense_by_team)
    league_off = _league_means(list(raw_off.values()))
    league_def = _league_means(list(raw_def.values()))
    league_avg_ppg = _resolve_league_avg_ppg(
        offense_by_team=offense_by_team,
        league_off=league_off,
        league_def=league_def,
        default_ppg=float(sport_config.league_avg_ppg),
        sport_config=sport_config,
    )

    counts = opponent_game_counts
    excluded = exclude_opponent_ids or set()
    prior_k = SOS_OPP_SAMPLE_PRIOR_K

    def _shrink_opp_points(raw_pts: float, opp: str) -> float:
        """Pull thin opponent profiles toward league average."""

        if counts is None:
            return raw_pts
        n = float(counts.get(opp) or 0.0)
        if n <= 0:
            return float(league_avg_ppg)
        weight = n / (n + prior_k)
        return weight * raw_pts + (1.0 - weight) * float(league_avg_ppg)

    def _game_sample_weight(opp: str) -> float:
        if counts is None:
            return 1.0
        n = float(counts.get(opp) or 0.0)
        # Full-sample FBS foes keep unit weight; thin profiles are downweighted.
        if n >= 4:
            return 1.0
        return max(0.20, n / (n + prior_k)) if n > 0 else 0.20

    off_baselines = dict(raw_off)
    def_baselines = dict(raw_def)
    iterations = 0
    for iteration in range(MAX_OPP_ADJ_ITERATIONS):
        iterations = iteration + 1
        adj_off: dict[str, list[dict[str, float]]] = {}
        for tid, games in offense_by_team.items():
            rows: list[dict[str, float]] = []
            for game in games:
                opp = str(game.get("opponent_id") or "")
                if opp and opp in excluded:
                    continue
                metrics = _offense_game_metrics(game)
                weight = _recency_weight(
                    game.get("week"),
                    current_week_ref=current_week_ref,
                    half_life_weeks=half_life_weeks,
                ) * _game_sample_weight(opp)
                opp_def = def_baselines.get(opp) or league_def
                # Residual vs expected given opponent defense quality.
                # Soft D (high points allowed) ⇒ higher expected scoring
                # ⇒ less credit for the same raw point total.
                raw_opp_def_pts = float(
                    opp_def.get("points_allowed") or league_avg_ppg
                )
                opp_def_pts = _shrink_opp_points(raw_opp_def_pts, opp)
                expected_pts = opp_def_pts
                scoring_residual = (
                    float(metrics["points"]) - expected_pts
                )
                metrics = dict(metrics)
                metrics["scoring_margin_proxy"] = scoring_residual
                metrics["_weight"] = weight
                # Opponent-adjust EPA signals toward tougher defenses.
                scale = _opp_scale(
                    opp_def_pts,
                    league_avg_ppg=league_avg_ppg,
                    invert=True,
                    sport_config=sport_config,
                )
                for key in (
                    "epa_per_play",
                    "explosive_rate",
                    "pass_efficiency",
                    "rush_efficiency",
                ):
                    if key in metrics:
                        metrics[key] = float(metrics[key]) * scale
                rows.append(metrics)
            if rows:
                adj_off[tid] = rows

        adj_def: dict[str, list[dict[str, float]]] = {}
        for tid, games in defense_by_team.items():
            rows = []
            for game in games:
                opp = str(game.get("opponent_id") or "")
                if opp and opp in excluded:
                    continue
                metrics = _defense_game_metrics(game)
                weight = _recency_weight(
                    game.get("week"),
                    current_week_ref=current_week_ref,
                    half_life_weeks=half_life_weeks,
                ) * _game_sample_weight(opp)
                opp_off = off_baselines.get(opp) or league_off
                raw_opp_off_pts = float(
                    opp_off.get("points") or league_avg_ppg
                )
                opp_off_pts = _shrink_opp_points(raw_opp_off_pts, opp)
                expected_allowed = opp_off_pts
                metrics = dict(metrics)
                # Higher residual = better defense (held opponent under
                # what their offense usually scores).
                metrics["points_allowed_residual"] = (
                    expected_allowed - float(metrics["points_allowed"])
                )
                metrics["_weight"] = weight
                # Allowed metrics: higher = worse. Facing soft offenses
                # should inflate allowed (less credit); elite offenses
                # should deflate allowed (more credit). invert=True.
                scale = _opp_scale(
                    opp_off_pts,
                    league_avg_ppg=league_avg_ppg,
                    invert=True,
                    sport_config=sport_config,
                )
                for key in (
                    "pass_defense_raw",
                    "rush_defense_raw",
                    "success_allowed_raw",
                    "explosive_allowed_raw",
                ):
                    if key in metrics:
                        metrics[key] = float(metrics[key]) * scale
                rows.append(metrics)
            if rows:
                adj_def[tid] = rows

        new_off = {
            tid: _weighted_mean_metrics(games)
            for tid, games in adj_off.items()
        }
        new_def = {
            tid: _weighted_mean_metrics(games)
            for tid, games in adj_def.items()
        }
        delta = _baseline_delta(off_baselines, new_off) + _baseline_delta(
            def_baselines, new_def
        )
        off_baselines = new_off
        def_baselines = new_def
        if delta < 1e-3:
            break

    return off_baselines, def_baselines, float(league_avg_ppg), iterations


def _opp_scale(
    opponent_points: float,
    *,
    league_avg_ppg: float,
    invert: bool,
    sport_config: BettingSportConfig | None = None,
) -> float:
    """Scale observed efficiency for opponent quality."""

    gap = (opponent_points - league_avg_ppg) / max(league_avg_ppg, 1.0)
    if invert:
        # Facing tough defense (low points allowed) → boost observed offense.
        gap = -gap
    # CFB: stronger schedule discrimination (G5 padding vs P4 gauntlets).
    if sport_config and sport_config.id == SPORT_CFB:
        return max(0.50, min(1.70, 1.0 + 0.90 * gap))
    return max(0.70, min(1.45, 1.0 + 0.50 * gap))


def _recency_weight(
    week: Any,
    *,
    current_week_ref: float,
    half_life_weeks: float,
) -> float:
    try:
        game_week = float(week)
    except (TypeError, ValueError):
        return 1.0
    age = max(0.0, float(current_week_ref) - game_week - 1.0)
    half = max(0.5, float(half_life_weeks))
    return float(2.0 ** (-age / half))


def _weighted_mean_metrics(
    games: list[dict[str, float]],
) -> dict[str, float]:
    if not games:
        return {}
    keys = [
        key
        for key in games[0]
        if key != "_weight" and isinstance(games[0][key], (int, float))
    ]
    out: dict[str, float] = {}
    for key in keys:
        total_w = 0.0
        total = 0.0
        for game in games:
            weight = float(game.get("_weight") or 1.0)
            total_w += weight
            total += weight * float(game.get(key) or 0.0)
        out[key] = total / total_w if total_w else 0.0
    return out


def _league_means(
    profiles: list[dict[str, float]],
) -> dict[str, float]:
    if not profiles:
        return {}
    keys = set()
    for profile in profiles:
        keys.update(profile.keys())
    return {
        key: mean(float(p.get(key) or 0.0) for p in profiles)
        for key in keys
    }


def _baseline_delta(
    previous: dict[str, dict[str, float]],
    current: dict[str, dict[str, float]],
) -> float:
    deltas: list[float] = []
    for tid, metrics in current.items():
        old = previous.get(tid) or {}
        for key, value in metrics.items():
            deltas.append(abs(float(value) - float(old.get(key) or 0.0)))
    return mean(deltas) if deltas else 0.0


def _offense_weights(
    sport_config: BettingSportConfig | None,
) -> dict[str, float]:
    if sport_config and not sport_config.has_epa_features:
        return CFB_OFFENSE_SIGNAL_WEIGHTS
    return OFFENSE_SIGNAL_WEIGHTS


def _defense_weights(
    sport_config: BettingSportConfig | None,
) -> dict[str, float]:
    if sport_config and not sport_config.has_epa_features:
        return CFB_DEFENSE_SIGNAL_WEIGHTS
    return DEFENSE_SIGNAL_WEIGHTS


def _offense_composite(
    metrics: dict[str, float],
    *,
    sport_config: BettingSportConfig | None = None,
) -> float:
    weights = _offense_weights(sport_config)
    epa = float(metrics.get("epa_per_play") or 0.0)
    # yards/play is independent of EPA; do not reuse success_rate (EPA/play).
    explosive = float(metrics.get("explosive_rate") or 0.0)
    explosive_n = (
        (explosive - YARDS_PER_PLAY_BASELINE) / YARDS_PER_PLAY_SCALE
    )
    scoring = float(metrics.get("scoring_margin_proxy") or 0.0)
    # Normalize opponent-adjusted scoring residual into EPA-ish units.
    scoring_n = scoring / 14.0
    return (
        weights["epa_per_play"] * epa
        + weights["explosive_rate"] * explosive_n
        + weights["scoring_margin_proxy"] * scoring_n
    )


def _defense_composite(
    metrics: dict[str, float],
    *,
    sport_config: BettingSportConfig | None = None,
) -> float:
    weights = _defense_weights(sport_config)
    # Invert raw allowed EPA so higher = better defense.
    epa_allowed = float(
        metrics.get("success_allowed_raw")
        or (
            float(metrics.get("pass_defense_raw") or 0.0)
            + float(metrics.get("rush_defense_raw") or 0.0)
        )
        / 2.0
    )
    explosive_allowed = float(metrics.get("explosive_allowed_raw") or 0.0)
    explosive_n = -(
        (explosive_allowed - YARDS_PER_PLAY_BASELINE) / YARDS_PER_PLAY_SCALE
    )
    # Prefer opponent-adjusted residual (higher = better). Raw points
    # allowed ignores slate quality and overrates soft-schedule defenses.
    if metrics.get("points_allowed_residual") is not None:
        points_term = float(metrics["points_allowed_residual"]) / 14.0
    else:
        points_allowed = float(metrics.get("points_allowed") or 0.0)
        baseline_ppg = float(
            (sport_config.league_avg_ppg if sport_config else None)
            or DEFAULT_LEAGUE_AVG_PPG
        )
        points_term = -((points_allowed - baseline_ppg) / 14.0)
    return (
        weights["epa_allowed_per_play"] * (-epa_allowed)
        + weights["explosive_allowed"] * explosive_n
        + weights["points_allowed"] * points_term
    )


def _special_teams_proxy(
    offense: dict[str, float],
    defense: dict[str, float],
    *,
    league_avg_ppg: float,
) -> float:
    """
    Residual scoring not explained by EPA efficiency.

    Positive ⇒ team outscores EPA expectation (ST / hidden factors).
    """

    points = float(offense.get("points") or league_avg_ppg)
    epa = float(offense.get("epa_per_play") or 0.0)
    expected = league_avg_ppg + epa * 55.0
    off_residual = points - expected
    allowed = float(defense.get("points_allowed") or league_avg_ppg)
    def_epa = float(defense.get("success_allowed_raw") or 0.0)
    expected_allowed = league_avg_ppg + def_epa * 55.0
    def_residual = expected_allowed - allowed
    return (off_residual + def_residual) / 2.0


def _zscore_map(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    series = list(values.values())
    avg = mean(series)
    sd = pstdev(series) if len(series) > 1 else 0.0
    if sd <= 1e-9:
        return {tid: 0.0 for tid in values}
    return {tid: (value - avg) / sd for tid, value in values.items()}


def _effective_game_count(
    games_off: list[dict[str, Any]],
    games_def: list[dict[str, Any]],
    *,
    current_week_ref: float,
    half_life_weeks: float,
) -> float:
    """
    Sample size for prior shrinkage.

    Use completed-game counts, not the sum of recency weights. Recency
    already shapes observed means; decaying the sample size again keeps
    last-season priors sticky deep into the year and under-credits
    current results (e.g. quality wins over strong opponents).
    """

    del current_week_ref, half_life_weeks  # signature kept for call sites
    return float(max(len(games_off), len(games_def)))


def _shrinkage_lambda(
    *,
    effective_games: float,
    prior_k: float,
) -> float:
    """
    λ for blending observed vs prior.

    ``k`` decays as games accumulate so last season does not dominate
    mid-year rankings (e.g. 2025 Super Bowl defenses propping 2026
    teams after statement losses). At 0 games k=prior_k; by ~8 games
    k falls toward 15% of prior_k.
    """

    n = max(0.0, float(effective_games))
    base_k = max(0.5, float(prior_k))
    progress = min(1.0, n / 8.0)
    k_eff = base_k * max(0.15, 1.0 - 0.85 * progress)
    return n / (n + k_eff) if (n + k_eff) > 0 else 0.0


# Sparse opponents (1 FCS blowout) shrink toward league average in SOS.
SOS_OPP_SAMPLE_PRIOR_K = 4.0


def _team_sos(
    *,
    games_off: list[dict[str, Any]],
    games_def: list[dict[str, Any]],
    off_means: dict[str, dict[str, float]],
    def_means: dict[str, dict[str, float]],
    league_avg_ppg: float,
    opponent_game_counts: dict[str, int] | None = None,
    exclude_opponent_ids: set[str] | None = None,
    opp_strength_by_team: dict[str, float] | None = None,
) -> float:
    """
    Strength of schedule.

    When ``opp_strength_by_team`` is provided (CFB), SOS is the mean
    opponent off+def composite strength — so quality of foes (Alabama vs
    Ball State) matters more than raw PPG profiles. Otherwise falls back
    to opponent scoring profiles (NFL).

    Positive = tougher slate. Sparse opponents shrink toward average.
    Optional ``exclude_opponent_ids`` drops FCS from the average.
    """

    counts = opponent_game_counts
    excluded = exclude_opponent_ids or set()
    prior_k = SOS_OPP_SAMPLE_PRIOR_K
    values: list[float] = []

    def _sample_weight(opp: str) -> float:
        if counts is None:
            return 1.0
        n = float(counts.get(opp) or 0.0)
        return n / (n + prior_k) if n > 0 else 0.0

    # Prefer unique opponents from offense games (one contribution each).
    seen: set[str] = set()
    if opp_strength_by_team is not None:
        for game in games_off:
            opp = str(game.get("opponent_id") or "")
            if not opp or opp in excluded or opp in seen:
                continue
            if opp not in opp_strength_by_team:
                continue
            seen.add(opp)
            raw = float(opp_strength_by_team.get(opp) or 0.0)
            # Only shrink truly sparse foes; full-sample opponents keep
            # their face value so soft G5 slates stay soft.
            n = float((counts or {}).get(opp) or 0.0) if counts else 99.0
            if counts is not None and n < 4:
                weight = n / (n + prior_k) if n > 0 else 0.0
                values.append(weight * raw)
            else:
                values.append(raw)
        return float(mean(values)) if values else 0.0

    for game in games_off:
        opp = str(game.get("opponent_id") or "")
        if not opp or opp in excluded:
            continue
        opp_def = def_means.get(opp)
        if not opp_def:
            continue
        allowed = float(opp_def.get("points_allowed") or league_avg_ppg)
        weight = _sample_weight(opp)
        # Blend raw allowed toward league avg when sample is thin.
        shrunk_allowed = (
            weight * allowed + (1.0 - weight) * league_avg_ppg
        )
        values.append(league_avg_ppg - shrunk_allowed)
    for game in games_def:
        opp = str(game.get("opponent_id") or "")
        if not opp or opp in excluded:
            continue
        opp_off = off_means.get(opp)
        if not opp_off:
            continue
        scored = float(opp_off.get("points") or league_avg_ppg)
        weight = _sample_weight(opp)
        shrunk_scored = weight * scored + (1.0 - weight) * league_avg_ppg
        values.append(shrunk_scored - league_avg_ppg)
    return float(mean(values)) if values else 0.0


def _team_win_pcts(
    *,
    offense_by_team: dict[str, list[dict[str, Any]]],
    defense_by_team: dict[str, list[dict[str, Any]]],
    exclude_opponent_ids: set[str] | None = None,
) -> dict[str, float]:
    """Win% by team from paired offense/defense rows (FCS optional exclude)."""

    excluded = exclude_opponent_ids or set()
    allowed_by_team: dict[str, dict[tuple[Any, str], float]] = {}
    for tid, games in defense_by_team.items():
        bucket: dict[tuple[Any, str], float] = {}
        for game in games:
            opp = str(game.get("opponent_id") or "")
            if opp in excluded:
                continue
            pts_allowed = num(game.get("points_allowed"))
            if pts_allowed is None:
                continue
            bucket[(game.get("week"), opp)] = float(pts_allowed)
        allowed_by_team[tid] = bucket

    win_pcts: dict[str, float] = {}
    for tid, games in offense_by_team.items():
        wins = 0
        losses = 0
        ties = 0
        allowed_map = allowed_by_team.get(tid) or {}
        for game in games:
            opp = str(game.get("opponent_id") or "")
            if opp in excluded:
                continue
            pts = num(game.get("points"))
            allowed = allowed_map.get((game.get("week"), opp))
            if pts is None or allowed is None:
                continue
            if float(pts) > float(allowed):
                wins += 1
            elif float(pts) < float(allowed):
                losses += 1
            else:
                ties += 1
        games_n = wins + losses + ties
        if games_n <= 0:
            continue
        win_pcts[tid] = (wins + 0.5 * ties) / float(games_n)
    return win_pcts


def _cfb_fcs_opponent_ids(
    *,
    offense_by_team: dict[str, list[dict[str, Any]]],
    defense_by_team: dict[str, list[dict[str, Any]]],
    sport_config: BettingSportConfig,
) -> set[str]:
    """Return opponent team_ids tagged FCS (or non-FBS) in dim_team."""

    opp_ids: set[str] = set()
    for games in list(offense_by_team.values()) + list(
        defense_by_team.values()
    ):
        for game in games:
            opp = str(game.get("opponent_id") or "")
            if opp:
                opp_ids.add(opp)
    if not opp_ids:
        return set()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT team_id, subdivision
                    FROM {sport_config.schema}.dim_team
                    WHERE team_id = ANY(:ids)
                    """
                ),
                {"ids": list(opp_ids)},
            ).mappings()
            return {
                str(row["team_id"])
                for row in rows
                if not _is_fbs_subdivision(row.get("subdivision"))
            }
    except Exception:
        return set()


def _team_record(
    *,
    games_off: list[dict[str, Any]],
    games_def: list[dict[str, Any]],
    off_means: dict[str, dict[str, float]],
    def_means: dict[str, dict[str, float]],
    league_avg_ppg: float,
    sport_id: str | None = None,
    opp_strength_by_team: dict[str, float] | None = None,
    exclude_opponent_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    W/L/T from paired offense/defense game rows plus a rating signal.

    ``record_signal`` is in roughly [-1, +1]: win% centered at .500 blended
    with opponent-quality weighted results (wins over strong sides count
    more; losses to weak sides hurt more). FCS games can be excluded from
    the quality blend while still counting in W-L.
    """

    is_cfb = sport_id == SPORT_CFB
    win_pct_w = (
        CFB_RECORD_WIN_PCT_WEIGHT if is_cfb else RECORD_WIN_PCT_WEIGHT
    )
    quality_w = (
        CFB_RECORD_QUALITY_WEIGHT if is_cfb else RECORD_QUALITY_WEIGHT
    )
    quality_coef = (
        CFB_RECORD_OPP_QUALITY_COEF if is_cfb else RECORD_OPP_QUALITY_COEF
    )
    excluded = exclude_opponent_ids or set()

    allowed_by_key: dict[tuple[Any, str], float] = {}
    for game in games_def:
        key = (game.get("week"), str(game.get("opponent_id") or ""))
        pts_allowed = num(game.get("points_allowed"))
        if pts_allowed is None:
            continue
        allowed_by_key[key] = float(pts_allowed)

    wins = 0
    losses = 0
    ties = 0
    quality_terms: list[float] = []
    for game in games_off:
        key = (game.get("week"), str(game.get("opponent_id") or ""))
        pts = num(game.get("points"))
        allowed = allowed_by_key.get(key)
        if pts is None or allowed is None:
            continue
        team_pts = float(pts)
        opp_pts = float(allowed)
        opp = str(game.get("opponent_id") or "")
        if team_pts > opp_pts:
            wins += 1
            won = True
        elif team_pts < opp_pts:
            losses += 1
            won = False
        else:
            ties += 1
            won = None

        if opp in excluded:
            continue

        if opp_strength_by_team is not None and opp in opp_strength_by_team:
            # Composite strength already in rating-point units (~0 = avg).
            opp_quality = float(opp_strength_by_team.get(opp) or 0.0)
        else:
            opp_off = off_means.get(opp) or {}
            opp_def = def_means.get(opp) or {}
            opp_scored = float(opp_off.get("points") or league_avg_ppg)
            opp_allowed = float(
                opp_def.get("points_allowed") or league_avg_ppg
            )
            opp_quality = (opp_scored - league_avg_ppg) + (
                league_avg_ppg - opp_allowed
            )

        # Win vs strong → large +; win vs cupcake → near 0.
        # Loss vs strong → mild -; loss vs cupcake → large - (bad loss).
        if won is True:
            quality_terms.append(
                max(0.05, 1.0 + quality_coef * opp_quality)
            )
        elif won is False:
            quality_terms.append(
                min(-0.05, -1.0 + quality_coef * opp_quality)
            )
        else:
            quality_terms.append(0.0)

    games = wins + losses + ties
    if games <= 0:
        return {
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "win_pct": 0.5,
            "record_signal": 0.0,
        }
    win_pct = (wins + 0.5 * ties) / float(games)
    pct_term = 2.0 * win_pct - 1.0
    quality_raw = mean(quality_terms) if quality_terms else 0.0
    quality_term = max(-1.5, min(1.5, float(quality_raw))) / 1.5
    # Mild sample shrink so 1-0 does not equal 10-0.
    sample = min(1.0, games / 5.0)
    record_signal = sample * (
        win_pct_w * pct_term + quality_w * quality_term
    )
    # Undefeated CFB teams keep a mild floor only when the slate is not
    # a cupcake parade (mean opp strength must clear a low bar).
    if is_cfb and games >= 6 and losses == 0 and ties == 0:
        if opp_strength_by_team is not None:
            opp_vals = [
                float(opp_strength_by_team.get(str(g.get("opponent_id") or "")) or 0.0)
                for g in games_off
                if str(g.get("opponent_id") or "") not in excluded
                and str(g.get("opponent_id") or "") in opp_strength_by_team
            ]
            mean_opp = float(mean(opp_vals)) if opp_vals else -99.0
            if mean_opp >= -1.0:
                record_signal = max(record_signal, 0.72)
        else:
            record_signal = max(record_signal, 0.72)
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_pct": win_pct,
        "record_signal": float(record_signal),
    }


def _recent_form(
    games_off: list[dict[str, Any]],
    *,
    current_week_ref: float,
    half_life_weeks: float,
    league_avg_ppg: float,
    games_def: list[dict[str, Any]] | None = None,
    off_means: dict[str, dict[str, float]] | None = None,
    def_means: dict[str, dict[str, float]] | None = None,
    opponent_game_counts: dict[str, int] | None = None,
    exclude_opponent_ids: set[str] | None = None,
    sport_id: str | None = None,
) -> float:
    """
    Recent form from opponent-adjusted scoring residuals.

    Uses the last 3 eligible games (FCS excluded for CFB). Each game
    contributes offense residual vs opponent defense and defense residual
    vs opponent offense. Soft recent slates are dampened so padding G5
    foes cannot manufacture a "hot" form boost.
    """

    if not games_off:
        return 0.0

    excluded = exclude_opponent_ids or set()
    offenses = off_means or {}
    defenses = def_means or {}
    counts = opponent_game_counts
    prior_k = SOS_OPP_SAMPLE_PRIOR_K
    is_cfb = sport_id == SPORT_CFB

    allowed_by_key: dict[tuple[Any, str], float] = {}
    for game in games_def or []:
        opp = str(game.get("opponent_id") or "")
        if opp in excluded:
            continue
        key = (game.get("week"), opp)
        pts_allowed = num(game.get("points_allowed"))
        if pts_allowed is None:
            continue
        allowed_by_key[key] = float(pts_allowed)

    def _shrink_pts(raw_pts: float, opp: str) -> float:
        if counts is None:
            return raw_pts
        n = float(counts.get(opp) or 0.0)
        if n <= 0:
            return float(league_avg_ppg)
        weight = n / (n + prior_k)
        return weight * raw_pts + (1.0 - weight) * float(league_avg_ppg)

    eligible = [
        game
        for game in games_off
        if str(game.get("opponent_id") or "") not in excluded
    ]
    ordered = sorted(
        eligible,
        key=lambda row: float(row.get("week") or 0),
        reverse=True,
    )[:3]
    if not ordered:
        return 0.0

    vals: list[float] = []
    weights: list[float] = []
    opp_qualities: list[float] = []
    for game in ordered:
        opp = str(game.get("opponent_id") or "")
        points = float(num(game.get("points")) or 0.0)
        opp_def = defenses.get(opp) or {}
        raw_expected_off = float(
            opp_def.get("points_allowed")
            if opp_def.get("points_allowed") is not None
            else league_avg_ppg
        )
        expected_off = _shrink_pts(raw_expected_off, opp)
        off_resid = points - expected_off

        key = (game.get("week"), opp)
        allowed = allowed_by_key.get(key)
        opp_off = offenses.get(opp) or {}
        raw_expected_def = float(
            opp_off.get("points")
            if opp_off.get("points") is not None
            else league_avg_ppg
        )
        expected_def = _shrink_pts(raw_expected_def, opp)
        if allowed is None:
            game_resid = off_resid
        else:
            def_resid = expected_def - float(allowed)
            game_resid = 0.5 * (off_resid + def_resid)

        # Opponent quality in scoring-margin units (0 ≈ average).
        opp_quality = (expected_def - league_avg_ppg) + (
            league_avg_ppg - expected_off
        )
        opp_qualities.append(opp_quality)

        # Soft recent foes dampen form credit (CFB harder).
        if is_cfb:
            quality_scale = max(0.35, min(1.25, 1.0 + 0.06 * opp_quality))
        else:
            quality_scale = max(0.55, min(1.20, 1.0 + 0.04 * opp_quality))
        vals.append(game_resid * quality_scale)
        weights.append(
            _recency_weight(
                game.get("week"),
                current_week_ref=current_week_ref,
                half_life_weeks=half_life_weeks,
            )
        )

    total_w = sum(weights) or 1.0
    form = sum(v * w for v, w in zip(vals, weights)) / total_w
    # Extra slate-level dampening when the whole recent window is soft.
    if is_cfb and opp_qualities:
        slate_q = float(mean(opp_qualities))
        if slate_q < -1.0:
            form *= max(0.40, 1.0 + 0.12 * slate_q)
    return float(form)


def _explain_components(
    *,
    offensive_rating: float,
    defensive_rating: float,
    special_teams_rating: float,
    personnel_adj: float,
    form: float,
    sos: float,
    wins: int | None = None,
    losses: int | None = None,
    win_pct: float | None = None,
) -> str:
    parts: list[str] = []
    if wins is not None and losses is not None and (wins + losses) > 0:
        parts.append(f"{wins}-{losses} record")
        if win_pct is not None and win_pct >= 0.85:
            parts.append("elite win rate")
        elif win_pct is not None and win_pct <= 0.35:
            parts.append("poor win rate")
    if offensive_rating >= 1.0:
        parts.append("above-average offense")
    elif offensive_rating <= -1.0:
        parts.append("below-average offense")
    if defensive_rating >= 1.0:
        parts.append("strong defense")
    elif defensive_rating <= -1.0:
        parts.append("porous defense")
    if special_teams_rating >= 0.5:
        parts.append("positive special-teams residual")
    elif special_teams_rating <= -0.5:
        parts.append("negative special-teams residual")
    if form >= 3.0:
        parts.append("hot recent scoring form")
    elif form <= -3.0:
        parts.append("cold recent scoring form")
    if sos >= 1.5:
        parts.append("difficult schedule")
    elif sos <= -1.5:
        parts.append("softer schedule")
    if abs(personnel_adj) >= 0.5:
        parts.append(
            "personnel adjustment "
            f"{personnel_adj:+.1f}"
        )
    if not parts:
        return "Near league-average across offense and defense."
    return "Rated on " + ", ".join(parts) + "."


def _is_fbs_subdivision(value: Any) -> bool:
    text_value = str(value or "").strip().upper()
    if not text_value:
        return False
    return (
        "FBS" in text_value
        or text_value in {"I-A", "IA", "DIVISION I-A", "DIV I-A"}
    )


def _team_logo_url_for_ranking(
    sport_id: str,
    *,
    abbreviation: str | None,
    espn_team_id: Any = None,
) -> str | None:
    """Prefer ESPN CDN logos (CFB needs numeric ids)."""

    return _sport_team_logo_url(
        sport_id,
        espn_team_id,
        abbreviation=abbreviation,
    )


def _load_teams(
    sport_config: BettingSportConfig,
    *,
    active_team_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    if sport_config.id == SPORT_CFB:
        sql = text(
            f"""
            SELECT
              team_id,
              team_abbreviation,
              COALESCE(team_name, team_abbreviation) AS team_name,
              conference,
              subdivision,
              source_ids->>'espn_team_id' AS espn_team_id
            FROM {sport_config.schema}.dim_team
            ORDER BY team_abbreviation
            """
        )
    else:
        sql = text(
            f"""
            SELECT
              team_id,
              team_abbreviation,
              COALESCE(team_name, team_abbreviation) AS team_name
            FROM {sport_config.schema}.dim_team
            ORDER BY team_abbreviation
            """
        )
    try:
        with engine.connect() as connection:
            rows = [
                dict(row)
                for row in connection.execute(sql).mappings()
            ]
    except Exception:
        return []

    if sport_config.id != SPORT_CFB:
        return rows

    fbs = [row for row in rows if _is_fbs_subdivision(row.get("subdivision"))]
    pool = fbs if len(fbs) >= 50 else rows
    if active_team_ids:
        # Prefer FBS teams that have completed games in-window.
        filtered = [
            row
            for row in pool
            if str(row.get("team_id")) in active_team_ids
        ]
        if len(filtered) >= 20:
            return filtered
        # Fallback: any team with games (covers sparse subdivision tags).
        return [
            row
            for row in rows
            if str(row.get("team_id")) in active_team_ids
        ]
    return pool


def _load_prior_ratings(
    *,
    season: int,
    sport_config: BettingSportConfig,
) -> dict[str, dict[str, float]]:
    prior_season = int(season) - 1
    if prior_season < 1999:
        return {}
    # Prefer last persisted snapshot from prior season.
    try:
        from app.canonical.fact_team_power_ranking import (
            load_latest_power_rankings,
        )

        prior = load_latest_power_rankings(
            season=prior_season,
            sport=sport_config.id,
        )
        if prior.get("rankings"):
            return {
                str(row["team_id"]): {
                    "offensive_rating": float(
                        row.get("offensive_rating") or 0.0
                    ),
                    "defensive_rating": float(
                        row.get("defensive_rating") or 0.0
                    ),
                    "special_teams_rating": float(
                        row.get("special_teams_rating") or 0.0
                    ),
                }
                for row in prior["rankings"]
            }
    except Exception:
        pass

    # Fallback: build a quick end-of-prior-season observed composite.
    offense_rows = _load_offense_games(
        season=prior_season,
        before_week=None,
        sport_config=sport_config,
    )
    defense_rows = _load_defense_games(
        season=prior_season,
        before_week=None,
        sport_config=sport_config,
    )
    if not offense_rows and not defense_rows:
        return {}
    off_by = _group_by_team(offense_rows, "team_id")
    def_by = _group_by_team(defense_rows, "team_id")
    off_means = _team_offense_baselines(off_by)
    def_means = _team_defense_baselines(def_by)
    off_z = _zscore_map(
        {
            tid: _offense_composite(m, sport_config=sport_config)
            for tid, m in off_means.items()
        }
    )
    def_z = _zscore_map(
        {
            tid: _defense_composite(m, sport_config=sport_config)
            for tid, m in def_means.items()
        }
    )
    out: dict[str, dict[str, float]] = {}
    for tid in set(off_z) | set(def_z):
        out[tid] = {
            "offensive_rating": float(off_z.get(tid) or 0.0)
            * POINTS_PER_OFFENSE_Z,
            "defensive_rating": float(def_z.get(tid) or 0.0)
            * POINTS_PER_DEFENSE_Z,
            "special_teams_rating": 0.0,
        }
    return out


def _load_previous_snapshot(
    *,
    season: int,
    week: int,
    sport: str = SPORT_NFL,
    half_life_weeks: float = DEFAULT_HALF_LIFE_WEEKS,
    prior_k: float = DEFAULT_PRIOR_K,
    home_field_advantage: float = DEFAULT_HFA_POINTS,
    include_personnel: bool = True,
) -> dict[str, dict[str, Any]]:
    """
    Prior-week ranks for trend.

    Prefer a persisted snapshot; if none exists, rebuild the prior
    week's rankings in-memory (without chaining further history).
    """

    sport_config = resolve_betting_sport(sport)
    try:
        from app.canonical.fact_team_power_ranking import (
            load_latest_power_rankings,
            load_power_rankings_snapshot,
        )

        if week <= 1:
            prev = load_latest_power_rankings(
                season=season - 1,
                sport=sport_config.id,
            )
        else:
            prev = load_power_rankings_snapshot(
                season=season,
                week=week - 1,
                sport=sport_config.id,
            )
        by_team = {
            str(row["team_id"]): row
            for row in (prev.get("rankings") or [])
        }
        if by_team:
            return by_team
    except Exception:
        pass

    # No persisted prior snapshot — rebuild prior week for rank compare.
    if week <= 1:
        return {}
    try:
        prior = build_power_rankings(
            sport=sport_config.id,
            season=season,
            # before_week = current snapshot week ⇒ prior snapshot
            week=week,
            half_life_weeks=half_life_weeks,
            prior_k=prior_k,
            home_field_advantage=home_field_advantage,
            persist=False,
            include_personnel=include_personnel,
            compare_previous=False,
        )
        return {
            str(row["team_id"]): row
            for row in (prior.get("rankings") or [])
        }
    except Exception:
        return {}


def _personnel_adjustments(
    *,
    season: int,
    week: int,
    sport: str = SPORT_NFL,
) -> dict[str, dict[str, Any]]:
    """
    Optional personnel layer.

    Returns empty when injury/player-impact context cannot be computed
    reliably — never invents flat injury penalties.
    """

    sport_config = resolve_betting_sport(sport)
    if not sport_config.has_injury_context:
        return {}

    try:
        from app.analysis.insights.betting.player_context import (
            load_week_player_context,
        )
    except Exception:
        return {}

    try:
        context = load_week_player_context(
            season=season,
            week=max(1, int(week)),
            sport=sport_config.id,
        )
    except Exception:
        return {}
    if not isinstance(context, dict) or not context:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for team_id, payload in context.items():
        if not isinstance(payload, dict):
            continue
        adj = payload.get("score_adjustment_pts")
        if adj is None:
            adj = payload.get("adjustment_pts")
        try:
            value = float(adj)
        except (TypeError, ValueError):
            continue
        if abs(value) < 1e-9:
            continue
        out[str(team_id)] = {
            "adjustment": value,
            "source": "player_context.score_adjustment_pts",
        }
    return out


def _load_completed_games_for_week(
    *,
    season: int,
    week: int,
    sport_config: BettingSportConfig | None = None,
) -> list[dict[str, Any]]:
    config = sport_config or resolve_betting_sport(SPORT_NFL)
    sql = text(
        f"""
        SELECT
          game_id,
          home_team_id,
          away_team_id,
          home_score,
          away_score,
          week,
          season
        FROM {config.schema}.dim_game
        WHERE season = :season
          AND week = :week
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        """
    )
    try:
        with engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    sql,
                    {"season": int(season), "week": int(week)},
                ).mappings()
            ]
    except Exception:
        return []
