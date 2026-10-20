"""
Turn a forecasted role into fantasy points one stat at a time.

Opportunities come from the role forecast. Yards, catches, and
turnovers come from those opportunities times a conditional rate.
The rate is a positional prior until the player has a real sample,
then it shrinks toward what he has actually done. Touchdowns come
from goal-line carries, red-zone chances, and the team's scoring
forecast. They are not a historical touchdown rate.

A thin sample still uses the calibrated fantasy-point baseline, but
only to set efficiency. The projection itself is the sum of the
scoring rules applied to the predicted stats.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.dfs.player_role import (
    _normalize_position,
    _opportunities,
    _prior_for,
    _reception_points,
)
from app.analysis.insights.dfs.projection_calibration import (
    current_season_weight_for_games,
)
from app.analysis.insights.game_forecast import (
    SACK_RATE,
    league_team_environment,
)


# League efficiency. Observed rates shrink toward these.
_RATE_PRIORS: dict[str, dict[str, float]] = {
    "QB": {
        "yards_per_attempt": 7.1,
        "completion_rate": 0.645,
        "interception_rate": 0.023,
        "yards_per_carry": 4.3,
    },
    "RB": {
        "yards_per_carry": 4.3,
        "catch_rate": 0.72,
        "yards_per_target": 6.5,
    },
    "WR": {
        "catch_rate": 0.64,
        "yards_per_target": 8.4,
    },
    "TE": {
        "catch_rate": 0.62,
        "yards_per_target": 7.4,
    },
}

# Games of evidence required before an observed rate
# outweighs the positional prior. A handful of carries
# does not replace 4.3 yards per carry.
_RATE_STRENGTH = {
    "yards_per_carry": 14.0,
    "yards_per_target": 12.0,
    "catch_rate": 12.0,
    "yards_per_attempt": 12.0,
    "completion_rate": 12.0,
    "interception_rate": 20.0,
}

_OBSERVED_RATES = (
    "yards_per_carry",
    "yards_per_target",
    "catch_rate",
)

# Touchdown and turnover counts are scoring events. Efficiency
# shrinkage does not move them.
_EVENT_KEYS = {
    "pass_tds",
    "rush_tds",
    "receiving_tds",
    "interceptions",
    "extra_points",
}


def forecast_player_production(
    *,
    role: dict[str, Any],
    team_forecast: dict[str, Any],
    reference_shares: dict[str, float],
    production_prior: float,
    scoring: str | None = "ppr",
    current_season_games: int = 0,
    current_efficiency: dict[str, Any] | None = None,
    historical_efficiency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Predicted stats and the fantasy points each one is worth.
    """

    position = _normalize_position(role.get("position"))
    rates = shrunk_efficiency(
        position,
        current_efficiency=current_efficiency,
        historical_efficiency=historical_efficiency,
        current_season_games=current_season_games,
    )
    league = league_team_environment()
    weekly_shares = dict(role.get("shares") or {})
    anchor_shares = dict(reference_shares or {})
    anchor = _components(
        position,
        anchor_shares,
        league,
        rates,
        scoring=scoring,
        skill_multiplier=1.0,
    )
    if _total(anchor) < 1.0:
        chart = _prior_for(
            position,
            int(role.get("effective_depth") or 1),
        )
        chart_parts = _components(
            position,
            chart,
            league,
            rates,
            scoring=scoring,
            skill_multiplier=1.0,
        )
        if _total(chart_parts) > _total(anchor):
            anchor = chart_parts
    multiplier = _skill_multiplier(
        position,
        production_prior=production_prior,
        anchor=anchor,
        sample_weight=float(rates.get("sample_weight") or 0.0),
    )
    parts = _components(
        position,
        weekly_shares,
        team_forecast,
        rates,
        scoring=scoring,
        skill_multiplier=multiplier,
    )
    total = _total(parts)
    summary = _summary(position, parts, rates)
    stats = {part["key"]: part["stat"] for part in parts}
    points = {part["key"]: part["points"] for part in parts}
    return {
        "total": total,
        "stats": {key: round(value, 2) for key, value in stats.items()},
        "points": {key: round(value, 2) for key, value in points.items()},
        "components": _public_components(parts),
        "rates": {
            key: rates[key]
            for key in rates
            if key
            in {
                "yards_per_carry",
                "yards_per_target",
                "catch_rate",
                "yards_per_attempt",
                "completion_rate",
                "interception_rate",
                "sample_weight",
            }
            and rates.get(key) is not None
        },
        "skill_multiplier": round(multiplier, 3),
        "summary": summary,
    }


def shrunk_efficiency(
    position: str,
    *,
    current_efficiency: dict[str, Any] | None,
    historical_efficiency: dict[str, Any] | None,
    current_season_games: int,
) -> dict[str, Any]:
    """
    Positional rate, pulled toward observed efficiency as the
    sample grows. Historical touchdown rate is ignored.
    """

    pos = _normalize_position(position)
    priors = dict(_RATE_PRIORS.get(pos) or _RATE_PRIORS["WR"])
    current = current_efficiency or {}
    historical = historical_efficiency or {}
    games = max(0, int(current_season_games or 0))
    season_weight = (
        current_season_weight_for_games(games) if games > 0 else 0.0
    )
    out: dict[str, Any] = dict(priors)
    weights: list[float] = []
    notes: list[str] = []
    for key in _OBSERVED_RATES:
        if key not in priors and pos != "QB":
            continue
        if key not in priors:
            continue
        observed, sample = _blend_observed(
            current.get(key),
            _num(current.get(f"{key}_games")),
            historical.get(key),
            _num(historical.get(f"{key}_games")),
            season_weight,
        )
        strength = _RATE_STRENGTH[key]
        weight = 0.0 if observed is None else sample / (sample + strength)
        shrunk = priors[key]
        if observed is not None and weight > 0:
            shrunk = (priors[key] * (1.0 - weight)) + (observed * weight)
            notes.append(
                f"{_rate_label(key)} {shrunk:.2f}, shrunk from "
                f"{observed:.2f} toward {priors[key]:.2f}."
            )
        out[key] = shrunk
        out[f"{key}_observed"] = observed
        out[f"{key}_weight"] = round(weight, 3)
        if weight > 0:
            weights.append(weight)
    out["sample_weight"] = max(weights) if weights else 0.0
    out["notes"] = notes
    return out


def load_player_efficiency(
    *,
    season: int,
    player_ids: list[str] | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """
    player_id → {"current": rates, "historical": rates}.

    Rates only. Touchdown rate is not loaded, because scoring
    chances come from this week's opportunities.
    """

    try:
        current = _load_efficiency_window(
            seasons=[int(season)],
            player_ids=player_ids,
        )
        historical = _load_efficiency_window(
            seasons=[int(season) - 1, int(season) - 2],
            player_ids=player_ids,
        )
    except Exception:
        return {}
    keys = set(current) | set(historical)
    return {
        player_id: {
            "current": current.get(player_id) or {},
            "historical": historical.get(player_id) or {},
        }
        for player_id in keys
    }


def _components(
    position: str,
    shares: dict[str, float],
    team: dict[str, Any],
    rates: dict[str, Any],
    *,
    scoring: str | None,
    skill_multiplier: float,
) -> list[dict[str, Any]]:
    if position == "DEF":
        return _defense_components(team, skill_multiplier)
    if position == "K":
        return _kicker_components(shares, team)
    opportunities = _opportunities(
        position,
        shares,
        team,
        availability=1.0,
    )
    skill = skill_multiplier if skill_multiplier > 0 else 0.0
    if position == "QB":
        return _quarterback_components(
            shares,
            team,
            opportunities,
            rates,
            skill,
        )
    if position == "RB":
        return _running_back_components(
            shares,
            team,
            opportunities,
            rates,
            skill,
            scoring=scoring,
        )
    return _receiver_components(
        position,
        shares,
        team,
        opportunities,
        rates,
        skill,
        scoring=scoring,
    )


def _quarterback_components(
    shares: dict[str, float],
    team: dict[str, Any],
    opportunities: dict[str, float],
    rates: dict[str, Any],
    skill: float,
) -> list[dict[str, Any]]:
    attempts = opportunities.get("attempts", 0.0)
    ypa = _conditional_rate(
        float(rates.get("yards_per_attempt") or 7.1) * skill,
        team.get("yards_per_pass_attempt"),
        7.1,
    )
    completions = attempts * float(rates.get("completion_rate") or 0.645)
    pass_yards = attempts * ypa
    pass_tds = (_num(team.get("expected_pass_tds")) or 0.0) * shares.get(
        "red_zone_pass_share",
        shares.get("dropback_share", 0.0),
    )
    interceptions = attempts * float(rates.get("interception_rate") or 0.023)
    rushes = opportunities.get("designed_rushes", 0.0) + opportunities.get(
        "scrambles",
        0.0,
    )
    ypc = _conditional_rate(
        float(rates.get("yards_per_carry") or 4.3) * skill,
        team.get("yards_per_rush"),
        4.3,
    )
    rush_yards = rushes * ypc
    rush_tds = (_num(team.get("expected_rush_tds")) or 0.0) * shares.get(
        "designed_rush_share",
        0.0,
    )
    return [
        _part(
            "pass_yards",
            "Pass yards",
            attempts,
            "attempts",
            ypa,
            "YPA",
            pass_yards,
            "yards",
            pass_yards / 25.0,
            "1 point per 25 yards",
            scales=True,
        ),
        _part(
            "completions",
            "Completions",
            attempts,
            "attempts",
            float(rates.get("completion_rate") or 0.645),
            "completion rate",
            completions,
            "completions",
            0.0,
            "shown with the passing line; yards are scored separately",
            scales=True,
        ),
        _part(
            "pass_tds",
            "Pass touchdowns",
            _num(team.get("expected_pass_tds")) or 0.0,
            "team pass TD chances",
            shares.get("red_zone_pass_share", 0.0),
            "red-zone share",
            pass_tds,
            "TD",
            pass_tds * 4.0,
            "4 points per TD",
            scales=False,
        ),
        _part(
            "interceptions",
            "Interceptions",
            attempts,
            "attempts",
            float(rates.get("interception_rate") or 0.023),
            "INT rate",
            interceptions,
            "INT",
            -interceptions * 2.0,
            "-2 points per INT",
            scales=False,
        ),
        _part(
            "rush_yards",
            "Rush yards",
            rushes,
            "rushes",
            ypc,
            "YPC",
            rush_yards,
            "yards",
            rush_yards / 10.0,
            "1 point per 10 yards",
            scales=True,
        ),
        _part(
            "rush_tds",
            "Rush touchdowns",
            _num(team.get("expected_rush_tds")) or 0.0,
            "team rush TD chances",
            shares.get("designed_rush_share", 0.0),
            "designed-rush share",
            rush_tds,
            "TD",
            rush_tds * 6.0,
            "6 points per TD",
            scales=False,
        ),
    ]


def _running_back_components(
    shares: dict[str, float],
    team: dict[str, Any],
    opportunities: dict[str, float],
    rates: dict[str, Any],
    skill: float,
    *,
    scoring: str | None,
) -> list[dict[str, Any]]:
    carries = opportunities.get("carries", 0.0)
    targets = opportunities.get("targets", 0.0)
    ypc = _conditional_rate(
        float(rates.get("yards_per_carry") or 4.3) * skill,
        team.get("yards_per_rush"),
        4.3,
    )
    catch = _clamp(float(rates.get("catch_rate") or 0.72) * skill, 0.45, 0.9)
    ypt = float(rates.get("yards_per_target") or 6.5) * skill
    rush_yards = carries * ypc
    receptions = targets * catch
    receiving_yards = targets * ypt
    rush_tds = (_num(team.get("expected_rush_tds")) or 0.0) * shares.get(
        "goal_line_share",
        0.0,
    )
    rec_tds = (_num(team.get("expected_pass_tds")) or 0.0) * shares.get(
        "target_share",
        0.0,
    )
    rec_point = _reception_points(scoring)
    return [
        _part(
            "rush_yards",
            "Rush yards",
            carries,
            "carries",
            ypc,
            "YPC",
            rush_yards,
            "yards",
            rush_yards / 10.0,
            "1 point per 10 yards",
            scales=True,
        ),
        _part(
            "rush_tds",
            "Rush touchdowns",
            opportunities.get("goal_line_carries", 0.0),
            "goal-line carries",
            None,
            None,
            rush_tds,
            "TD",
            rush_tds * 6.0,
            "6 points per TD from goal-line chances",
            scales=False,
        ),
        _part(
            "receptions",
            "Receptions",
            targets,
            "targets",
            catch,
            "catch rate",
            receptions,
            "receptions",
            receptions * rec_point,
            f"{rec_point:g} points per reception",
            scales=True,
        ),
        _part(
            "receiving_yards",
            "Receiving yards",
            targets,
            "targets",
            ypt,
            "yards per target",
            receiving_yards,
            "yards",
            receiving_yards / 10.0,
            "1 point per 10 yards",
            scales=True,
        ),
        _part(
            "receiving_tds",
            "Receiving touchdowns",
            targets,
            "targets",
            shares.get("target_share", 0.0),
            "target share of team pass TDs",
            rec_tds,
            "TD",
            rec_tds * 6.0,
            "6 points per TD from the team pass-TD pool",
            scales=False,
        ),
    ]


def _receiver_components(
    position: str,
    shares: dict[str, float],
    team: dict[str, Any],
    opportunities: dict[str, float],
    rates: dict[str, Any],
    skill: float,
    *,
    scoring: str | None,
) -> list[dict[str, Any]]:
    targets = opportunities.get("targets", 0.0)
    catch_prior = 0.62 if position == "TE" else 0.64
    ypt_prior = 7.4 if position == "TE" else 8.4
    if position == "TE":
        ypt_prior *= 0.65 + 0.35 * shares.get("receiving_role", 0.7)
    catch = _clamp(float(rates.get("catch_rate") or catch_prior) * skill, 0.4, 0.85)
    ypt = float(rates.get("yards_per_target") or ypt_prior) * skill
    if position == "TE" and rates.get("yards_per_target") is not None:
        ypt *= 0.65 + 0.35 * shares.get("receiving_role", 0.7)
    receptions = targets * catch
    receiving_yards = targets * ypt
    rec_tds = (_num(team.get("expected_pass_tds")) or 0.0) * shares.get(
        "red_zone_target_share",
        0.0,
    )
    rec_point = _reception_points(scoring)
    parts = [
        _part(
            "routes",
            "Routes",
            opportunities.get("routes", 0.0),
            "routes",
            None,
            None,
            opportunities.get("routes", 0.0),
            "routes",
            0.0,
            "routes create the targets; they are not scored directly",
            scales=False,
        ),
        _part(
            "receptions",
            "Receptions",
            targets,
            "targets",
            catch,
            "catch rate",
            receptions,
            "receptions",
            receptions * rec_point,
            f"{rec_point:g} points per reception",
            scales=True,
        ),
        _part(
            "receiving_yards",
            "Receiving yards",
            targets,
            "targets",
            ypt,
            "yards per target",
            receiving_yards,
            "yards",
            receiving_yards / 10.0,
            "1 point per 10 yards",
            scales=True,
        ),
        _part(
            "receiving_tds",
            "Receiving touchdowns",
            opportunities.get("red_zone_targets", 0.0),
            "red-zone targets",
            shares.get("red_zone_target_share", 0.0),
            "share of team pass TDs",
            rec_tds,
            "TD",
            rec_tds * 6.0,
            "6 points per TD from red-zone chances",
            scales=False,
        ),
    ]
    return parts


def _kicker_components(
    shares: dict[str, float],
    team: dict[str, Any],
) -> list[dict[str, Any]]:
    fg_opps = (_num(team.get("expected_field_goals")) or 0.0) * shares.get(
        "field_goal_share",
        0.0,
    )
    xp_opps = (_num(team.get("expected_offensive_tds")) or 0.0) * shares.get(
        "extra_point_share",
        0.0,
    )
    # 3.5 is make rate times typical distance value. Extra points
    # use a 0.94 make rate.
    return [
        _part(
            "field_goals",
            "Field goals",
            fg_opps,
            "field-goal chances",
            3.5,
            "expected points per chance",
            fg_opps,
            "attempts",
            fg_opps * 3.5,
            "expected makes and distance, per chance",
            scales=False,
        ),
        _part(
            "extra_points",
            "Extra points",
            xp_opps,
            "extra-point chances",
            0.94,
            "make rate",
            xp_opps * 0.94,
            "makes",
            xp_opps * 0.94,
            "1 point per make",
            scales=False,
        ),
    ]


def _defense_components(
    team: dict[str, Any],
    skill_multiplier: float,
) -> list[dict[str, Any]]:
    league = league_team_environment()
    dropbacks = _opponent_dropbacks(team)
    league_dropbacks = _opponent_dropbacks(league) or dropbacks or 1.0
    sack_rate = SACK_RATE
    sacks = dropbacks * sack_rate
    turnovers = _num(team.get("opponent_turnovers"))
    if turnovers is None:
        turnovers = _num(league.get("opponent_turnovers")) or 1.15
    league_turnovers = _num(league.get("opponent_turnovers")) or turnovers or 1.0
    opp_points = _num(team.get("opponent_points")) or _num(
        league.get("opponent_points")
    ) or 22.0
    league_points = _num(league.get("opponent_points")) or 22.0
    points_scale = league_points / opp_points if opp_points else 1.0
    sack_scale = dropbacks / league_dropbacks if league_dropbacks else 1.0
    turnover_scale = turnovers / league_turnovers if league_turnovers else 1.0
    # League environment is worth 7 points: sacks, turnovers, and
    # how many the opponent is expected to score. Skill scales that
    # baseline. The opponent's forecast moves the pieces.
    skill = skill_multiplier if skill_multiplier > 0 else 1.0
    sack_points = 2.4 * sack_scale * skill
    turnover_points = 2.3 * turnover_scale * skill
    scoring_points = 2.3 * points_scale * skill
    return [
        _part(
            "sacks",
            "Sacks",
            dropbacks,
            "opponent dropbacks",
            sack_rate,
            "sack rate",
            sacks,
            "sacks",
            sack_points,
            "sack chances from opponent dropbacks",
            scales=True,
        ),
        _part(
            "turnovers",
            "Turnovers",
            _num(team.get("opponent_plays")) or 0.0,
            "opponent plays",
            None,
            None,
            turnovers,
            "turnovers",
            turnover_points,
            "takeaways from the opponent turnover forecast",
            scales=True,
        ),
        _part(
            "scoring_environment",
            "Scoring environment",
            opp_points,
            "opponent points",
            None,
            None,
            opp_points,
            "opponent points",
            scoring_points,
            "fewer opponent points are worth more",
            scales=True,
        ),
    ]


def _skill_multiplier(
    position: str,
    *,
    production_prior: float,
    anchor: list[dict[str, Any]],
    sample_weight: float,
) -> float:
    """
    How far efficiency sits from the positional rate.

    With no efficiency sample, the multiplier is the one that makes
    the reference role in a league game equal the calibrated
    baseline. A real yards-per-carry sample replaces that residual.
    Touchdowns are not multiplied.
    """

    if position == "K":
        return 1.0
    if position == "DEF":
        if production_prior <= 0:
            return 1.0
        baseline = _total(
            _defense_components(league_team_environment(), 1.0)
        )
        if baseline <= 0.05:
            return 1.0
        return float(production_prior) / baseline
    if production_prior <= 0:
        return 1.0
    event = sum(part["points"] for part in anchor if not part["scales"])
    volume = sum(part["points"] for part in anchor if part["scales"])
    if volume <= 0.05:
        solved = 1.0
    else:
        solved = (float(production_prior) - event) / volume
        solved = _clamp(solved, 0.35, 1.85)
    weight = _clamp(sample_weight, 0.0, 1.0)
    return (solved * (1.0 - weight)) + (1.0 * weight)


def _part(
    key: str,
    label: str,
    opportunities: float,
    opportunity_label: str,
    rate: float | None,
    rate_label: str | None,
    stat: float,
    stat_label: str,
    points: float,
    scoring_rule: str,
    *,
    scales: bool,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "opportunities": opportunities,
        "opportunity_label": opportunity_label,
        "rate": rate,
        "rate_label": rate_label,
        "stat": stat,
        "stat_label": stat_label,
        "points": points,
        "scoring_rule": scoring_rule,
        "scales": scales and key not in _EVENT_KEYS,
    }


def _public_components(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for part in parts:
        public.append(
            {
                "key": part["key"],
                "label": part["label"],
                "opportunities": round(float(part["opportunities"]), 2),
                "opportunity_label": part["opportunity_label"],
                "rate": (
                    round(float(part["rate"]), 3)
                    if part["rate"] is not None
                    else None
                ),
                "rate_label": part["rate_label"],
                "stat": round(float(part["stat"]), 2),
                "stat_label": part["stat_label"],
                "points": round(float(part["points"]), 2),
                "scoring_rule": part["scoring_rule"],
            }
        )
    return public


def _summary(
    position: str,
    parts: list[dict[str, Any]],
    rates: dict[str, Any],
) -> str:
    scored = [part for part in parts if abs(part["points"]) >= 0.05 or part["stat"] >= 0.05]
    bits: list[str] = []
    for part in scored:
        if part["key"] in {"routes", "completions"}:
            continue
        if part["rate"] is not None and part["opportunities"] > 0 and part["key"] in {
            "pass_yards",
            "rush_yards",
            "receiving_yards",
            "receptions",
            "field_goals",
            "sacks",
        }:
            bits.append(
                f"{part['stat']:.1f} {part['stat_label']} "
                f"({part['opportunities']:.1f} {part['opportunity_label']} "
                f"× {part['rate']:.2f})"
            )
        else:
            bits.append(f"{part['stat']:.2f} {part['stat_label']}")
    text = ", ".join(bits[:6])
    if position in {"QB", "RB", "WR", "TE"}:
        text += (
            ". Touchdowns follow this week's goal-line and red-zone "
            "chances, not a historical touchdown rate."
        )
    elif position == "K":
        text += ". Field goals and extra points follow the team's scoring chances."
    else:
        text += ". Sacks, turnovers, and opponent scoring are scored separately."
    notes = rates.get("notes") or []
    if notes:
        text += " " + " ".join(str(note) for note in notes)
    return text


def _conditional_rate(
    player_rate: float,
    team_rate: Any,
    league_rate: float,
) -> float:
    """Player efficiency, nudged by the team's forecasted rate."""

    team = _num(team_rate)
    if team is None or league_rate <= 0:
        return player_rate
    factor = _clamp(team / league_rate, 0.88, 1.12)
    return player_rate * factor


def _opponent_dropbacks(team: dict[str, Any]) -> float:
    attempts = _num(team.get("opponent_pass_attempts"))
    if attempts is None:
        attempts = _num(team.get("expected_pass_attempts")) or 0.0
    return attempts / max(0.5, 1.0 - SACK_RATE)


def _blend_observed(
    current: Any,
    current_games: float | None,
    historical: Any,
    historical_games: float | None,
    season_weight: float,
) -> tuple[float | None, float]:
    current_value = _num(current)
    historical_value = _num(historical)
    current_n = max(0.0, current_games or 0.0)
    historical_n = max(0.0, historical_games or 0.0)
    if current_value is None and historical_value is None:
        return None, 0.0
    if current_value is None:
        return historical_value, historical_n
    if historical_value is None:
        return current_value, current_n
    value = (historical_value * (1.0 - season_weight)) + (
        current_value * season_weight
    )
    sample = (historical_n * (1.0 - season_weight)) + (
        current_n * season_weight
    )
    return value, sample


def _total(parts: list[dict[str, Any]]) -> float:
    return sum(float(part["points"]) for part in parts)


def _rate_label(key: str) -> str:
    return {
        "yards_per_carry": "Yards per carry",
        "yards_per_target": "Yards per target",
        "catch_rate": "Catch rate",
    }.get(key, key)


def _load_efficiency_window(
    *,
    seasons: list[int],
    player_ids: list[str] | None,
) -> dict[str, dict[str, float]]:
    from sqlalchemy import text

    from app.canonical.schema import FANTASY_SCHEMA
    from app.database import engine

    seasons = [season for season in seasons if season >= 2015]
    if not seasons:
        return {}
    params: dict[str, Any] = {"seasons": seasons}
    player_filter = ""
    if player_ids:
        cleaned = [str(pid).strip() for pid in player_ids if str(pid).strip()]
        if cleaned:
            params["player_ids"] = cleaned
            player_filter = "AND player_id = ANY(:player_ids)"
    sql = f"""
        SELECT
          player_id,
          AVG(yards_per_carry) FILTER (
            WHERE yards_per_carry IS NOT NULL
          ) AS yards_per_carry,
          COUNT(yards_per_carry) AS yards_per_carry_games,
          AVG(yards_per_target) FILTER (
            WHERE yards_per_target IS NOT NULL
          ) AS yards_per_target,
          COUNT(yards_per_target) AS yards_per_target_games,
          AVG(catch_rate) FILTER (
            WHERE catch_rate IS NOT NULL
          ) AS catch_rate,
          COUNT(catch_rate) AS catch_rate_games
        FROM {FANTASY_SCHEMA}.fact_player_efficiency
        WHERE season = ANY(:seasons)
          {player_filter}
        GROUP BY player_id
    """
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params).mappings()
        parsed = [dict(row) for row in rows]
    out: dict[str, dict[str, float]] = {}
    for row in parsed:
        player_id = str(row.get("player_id") or "").strip()
        if not player_id:
            continue
        shares: dict[str, float] = {}
        for key in _OBSERVED_RATES:
            value = _num(row.get(key))
            games = _num(row.get(f"{key}_games"))
            if value is None:
                continue
            shares[key] = value
            shares[f"{key}_games"] = float(games or 0.0)
        if shares:
            out[player_id] = shares
    return out


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
