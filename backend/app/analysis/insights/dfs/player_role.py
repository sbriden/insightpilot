"""
Predict a player's role in the upcoming game, then the opportunities
that role can earn inside the game forecast.

Historical usage and fantasy production are priors for role and
skill. Current usage estimates the role they have now. Depth chart,
availability, and teammate absences forecast the role they will
have this week. Team plays, attempts, and scoring opportunities
cap how large that role can be.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.analysis.insights.dfs.projection_calibration import (
    DEFAULT_CALIBRATION_CONFIG,
    current_season_weight_for_games,
)
from app.analysis.insights.fantasy_scoring import normalize_scoring
from app.analysis.insights.game_forecast import (
    SACK_RATE,
    league_team_environment,
)


# Shares of team opportunity by listed depth. These are roles,
# not fantasy-point splits.
_ROLE_PRIORS: dict[str, dict[int, dict[str, float]]] = {
    "QB": {
        1: {
            "dropback_share": 0.97,
            "designed_rush_share": 0.055,
            "scramble_rate": 0.055,
            "red_zone_pass_share": 0.96,
        },
        2: {
            "dropback_share": 0.06,
            "designed_rush_share": 0.012,
            "scramble_rate": 0.04,
            "red_zone_pass_share": 0.05,
        },
        3: {
            "dropback_share": 0.015,
            "designed_rush_share": 0.004,
            "scramble_rate": 0.03,
            "red_zone_pass_share": 0.01,
        },
    },
    "RB": {
        1: {
            "snap_share": 0.65,
            "carry_share": 0.55,
            "target_share": 0.13,
            "route_participation": 0.52,
            "goal_line_share": 0.58,
            "receiving_role": 0.40,
        },
        2: {
            "snap_share": 0.38,
            "carry_share": 0.28,
            "target_share": 0.08,
            "route_participation": 0.38,
            "goal_line_share": 0.22,
            "receiving_role": 0.32,
        },
        3: {
            "snap_share": 0.14,
            "carry_share": 0.08,
            "target_share": 0.03,
            "route_participation": 0.16,
            "goal_line_share": 0.05,
            "receiving_role": 0.18,
        },
    },
    "WR": {
        1: {
            "route_participation": 0.92,
            "target_share": 0.24,
            "air_yard_share": 0.30,
            "red_zone_target_share": 0.26,
        },
        2: {
            "route_participation": 0.88,
            "target_share": 0.18,
            "air_yard_share": 0.20,
            "red_zone_target_share": 0.16,
        },
        3: {
            "route_participation": 0.72,
            "target_share": 0.11,
            "air_yard_share": 0.11,
            "red_zone_target_share": 0.08,
        },
        4: {
            "route_participation": 0.35,
            "target_share": 0.045,
            "air_yard_share": 0.04,
            "red_zone_target_share": 0.025,
        },
    },
    "TE": {
        1: {
            "route_participation": 0.72,
            "target_share": 0.16,
            "air_yard_share": 0.12,
            "red_zone_target_share": 0.16,
            "receiving_role": 0.74,
        },
        2: {
            "route_participation": 0.42,
            "target_share": 0.055,
            "air_yard_share": 0.04,
            "red_zone_target_share": 0.04,
            "receiving_role": 0.38,
        },
        3: {
            "route_participation": 0.18,
            "target_share": 0.02,
            "air_yard_share": 0.015,
            "red_zone_target_share": 0.015,
            "receiving_role": 0.16,
        },
    },
    "K": {
        1: {"field_goal_share": 0.98, "extra_point_share": 0.98},
        2: {"field_goal_share": 0.04, "extra_point_share": 0.04},
    },
    "DEF": {
        1: {"unit_share": 1.0},
    },
}

_USAGE_TO_ROLE = {
    "offensive_snap_share": "snap_share",
    "target_share": "target_share",
    "rush_share": "carry_share",
    "route_participation_rate": "route_participation",
    "air_yard_share": "air_yard_share",
    "qb_rush_share": "designed_rush_share",
    "dropback_share": "dropback_share",
}

_OUT_STATUSES = {
    "out",
    "ir",
    "injured reserve",
    "suspended",
    "pup",
    "physically unable to perform",
    "nfi",
    "inactive",
    "reserve",
}
_DOUBTFUL = {"doubtful"}
_QUESTIONABLE = {"questionable"}


def forecast_player_role(
    *,
    position: str,
    team_forecast: dict[str, Any],
    depth_order: int | None = None,
    current_season_games: int = 0,
    opportunity_score: float | None = None,
    injury_status: str | None = None,
    roster_status: str | None = None,
    current_usage: dict[str, Any] | None = None,
    historical_usage: dict[str, Any] | None = None,
    teammates_ahead_out: int = 0,
    matchup_score: float | None = None,
) -> dict[str, Any]:
    """
    Forecast this week's role and the opportunities it produces.

    Opportunity counts are shares of the team game forecast, so a
    player cannot be assigned more work than the game contains.
    """

    pos = _normalize_position(position)
    listed_depth = _listed_depth(depth_order, opportunity_score)
    effective_depth = max(1, listed_depth - max(0, int(teammates_ahead_out or 0)))
    availability = _availability(injury_status, roster_status)
    chart = _prior_for(pos, effective_depth)
    historical = (
        _usage_role(historical_usage, None) if historical_usage else {}
    )
    current = _usage_role(current_usage, None) if current_usage else {}
    games = max(0, int(current_season_games or 0))
    promoted = effective_depth < listed_depth
    chart_size = _role_size(chart)
    observed_size = max(_role_size(historical), _role_size(current))
    demoted = chart_size + 0.02 < observed_size * 0.65
    # Played, but the depth chart still describes a much bigger job
    # than anything he has actually done.
    chart_overstates = (
        games >= 2
        and chart_size > 0.2
        and observed_size + 0.02 < chart_size * 0.35
    )
    role_changed = (
        promoted
        or demoted
        or availability < 0.99
        or listed_depth >= 3
    )
    observed_keys = set(historical) | (set(current) if games > 0 else set())

    blended = _scale_unobserved_shares(
        _blend_roles(
            chart=chart,
            historical=historical,
            current=current if games > 0 else None,
            games=games,
            role_changed=role_changed,
            chart_overstates=chart_overstates,
        ),
        chart,
        observed_keys,
        pos,
    )
    tilted = _apply_matchup(blended, matchup_score, pos)
    shares = {
        key: round(max(0.0, value * availability), 4)
        for key, value in tilted.items()
    }
    opportunities = _opportunities(
        pos,
        shares,
        team_forecast,
        availability=availability,
    )
    summary = _summary(pos, effective_depth, shares, opportunities, promoted)
    drivers = _role_drivers(
        position=pos,
        listed_depth=listed_depth,
        effective_depth=effective_depth,
        games=games,
        promoted=promoted,
        availability=availability,
        injury_status=injury_status,
        matchup_score=matchup_score,
        opportunities=opportunities,
    )
    return {
        "position": pos,
        "listed_depth": listed_depth,
        "effective_depth": effective_depth,
        "depth_label": f"{pos}{effective_depth}",
        "availability": round(availability, 2),
        "promoted": promoted,
        "role_changed": role_changed,
        "shares": shares,
        "opportunities": opportunities,
        "summary": summary,
        "drivers": drivers,
    }


def reference_role_shares(
    role: dict[str, Any],
    *,
    earned_as_starter: bool,
    current_season_games: int,
    current_usage: dict[str, Any] | None = None,
    historical_usage: dict[str, Any] | None = None,
    production_prior: float | None = None,
) -> dict[str, float]:
    """
    Role that produced the skill prior.

    A promotion is scored against the old depth. Points that are
    too large for the listed depth were earned in a bigger role,
    so a backup week scales those points down instead of keeping
    them.
    """

    pos = str(role.get("position") or "WR")
    listed = int(role.get("listed_depth") or 1)
    if role.get("promoted"):
        return _prior_for(pos, listed)
    prior = max(0.0, float(production_prior or 0.0))
    if listed > 1 and _prior_from_larger_role(
        pos,
        listed,
        prior,
        earned_as_starter=earned_as_starter,
    ):
        if current_season_games < 3 and historical_usage:
            observed = _observed_role(
                historical_usage,
                _prior_for(pos, 1),
                pos,
            )
            if _role_size(observed) > _role_size(_prior_for(pos, listed)):
                return observed
        return _prior_for(pos, 1)
    if current_season_games >= 3 and current_usage:
        return _observed_role(current_usage, _prior_for(pos, listed), pos)
    if historical_usage:
        return _observed_role(historical_usage, _prior_for(pos, listed), pos)
    if current_usage:
        return _observed_role(current_usage, _prior_for(pos, listed), pos)
    if current_season_games <= 0:
        return _prior_for(pos, 1)
    return _prior_for(pos, listed)


def score_role_fantasy_points(
    role: dict[str, Any],
    team_forecast: dict[str, Any],
    *,
    production_prior: float,
    scoring: str | None = "ppr",
    reference_shares: dict[str, float] | None = None,
) -> float:
    """
    Turn a role forecast into fantasy points.

    ``production_prior`` is fantasy points in the reference role.
    This week's points scale with the opportunities that role
    actually receives inside the game forecast.
    """

    pos = str(role.get("position") or "WR")
    weekly = _points_at_unit_skill(
        pos,
        role.get("shares") or {},
        team_forecast,
        scoring=scoring,
    )
    baseline_shares = reference_shares or _prior_for(pos, 1)
    reference = _points_at_unit_skill(
        pos,
        baseline_shares,
        league_team_environment(),
        scoring=scoring,
    )
    if reference <= 0.05:
        # The prior was not earned on an empty role. Scale it from
        # the depth-chart job down to the opportunities actually
        # forecast, instead of substituting unit-skill points.
        chart_points = _points_at_unit_skill(
            pos,
            _prior_for(pos, int(role.get("effective_depth") or 1)),
            league_team_environment(),
            scoring=scoring,
        )
        if chart_points > 0.05 and production_prior > 0:
            return max(0.0, float(production_prior) * (weekly / chart_points))
        return max(0.0, weekly)
    return max(0.0, float(production_prior) * (weekly / reference))


def production_prior_for_player(
    *,
    position: str,
    base_projection: float,
    current_season_games: int | None,
    historical_baseline: float | None,
    raw_projection: float | None,
) -> tuple[float, bool]:
    """
    Skill prior, and whether that skill was earned in a starter role.

    A zero current-season average does not wipe out a historical
    starter. A small historical average was not a starter role.
    """

    pos = _normalize_position(position)
    games = current_season_games
    historical = _num(historical_baseline)
    current = _num(raw_projection)
    base = max(0.0, float(base_projection or 0.0))
    if games is None and historical is None:
        return base, base >= _starter_points(pos) * 0.55

    games_played = max(0, int(games or 0))
    if games_played <= 0:
        current_weight = 0.0
    else:
        current_weight = current_season_weight_for_games(games_played)
    current_value = 0.0 if current is None else max(0.0, current)
    if historical is None:
        prior = base if base > 0 else current_value
    else:
        prior = (historical * (1.0 - current_weight)) + (
            current_value * current_weight
        )
        if base > 0 and games_played >= 3:
            # Calibration already shrunk a real sample. Keep it.
            prior = base
    starter_points = _starter_points(pos)
    earned_as_starter = prior >= starter_points * 0.8
    return max(0.0, prior), earned_as_starter


def index_teammates_ahead_out(
    players: list[dict[str, Any]],
) -> dict[str, int]:
    """player_id → how many better depth-chart teammates are unavailable."""

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for player in players:
        player_id = str(player.get("player_id") or "").strip()
        team = str(player.get("team") or "").strip().upper()
        position = _normalize_position(player.get("position"))
        if not player_id or not team:
            continue
        groups[(team, position)].append(player)

    indexed: dict[str, int] = {}
    for group in groups.values():
        for player in group:
            player_id = str(player.get("player_id") or "")
            depth = _num(player.get("depth_order"))
            if depth is None:
                indexed[player_id] = 0
                continue
            ahead = 0
            for other in group:
                if other is player:
                    continue
                other_depth = _num(other.get("depth_order"))
                if other_depth is None or other_depth >= depth:
                    continue
                if _is_unavailable(other):
                    ahead += 1
            indexed[player_id] = ahead
    return indexed


def load_player_role_usage(
    *,
    season: int,
    player_ids: list[str] | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """
    player_id → {"current": shares, "historical": shares}.

    Returns empty dicts when the database is unavailable.
    """

    try:
        current = _load_usage_window(
            seasons=[int(season)],
            player_ids=player_ids,
        )
        historical = _load_usage_window(
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


def _opportunities(
    position: str,
    shares: dict[str, float],
    team: dict[str, Any],
    *,
    availability: float,
) -> dict[str, float]:
    attempts = _num(team.get("expected_pass_attempts")) or 0.0
    rushes = _num(team.get("expected_rush_attempts")) or 0.0
    dropbacks = attempts / max(0.5, 1.0 - SACK_RATE)
    scoring_opps = _num(team.get("expected_scoring_opportunities")) or 0.0
    pass_rate = _num(team.get("pass_rate")) or 0.58
    ypa = _num(team.get("yards_per_pass_attempt")) or 7.1
    out: dict[str, float] = {}

    if position == "QB":
        share = shares.get("dropback_share", 0.0)
        player_attempts = attempts * share
        player_dropbacks = dropbacks * share
        designed = rushes * shares.get("designed_rush_share", 0.0)
        scrambles = player_dropbacks * shares.get("scramble_rate", 0.0)
        out.update(
            {
                "dropbacks": player_dropbacks,
                "attempts": player_attempts,
                "completions": player_attempts * 0.645,
                "designed_rushes": designed,
                "scrambles": scrambles,
                "red_zone_pass_opportunities": (
                    scoring_opps
                    * pass_rate
                    * shares.get("red_zone_pass_share", 0.0)
                ),
            }
        )
    elif position == "RB":
        carries = rushes * shares.get("carry_share", 0.0)
        targets = attempts * shares.get("target_share", 0.0)
        out.update(
            {
                "snap_share": shares.get("snap_share", 0.0),
                "carries": carries,
                "targets": targets,
                "routes": dropbacks * shares.get("route_participation", 0.0),
                "goal_line_carries": (
                    3.0
                    * (rushes / max(1.0, _league("expected_rush_attempts")))
                    * (
                        scoring_opps
                        / max(0.5, _league("expected_scoring_opportunities"))
                    )
                    * shares.get("goal_line_share", 0.0)
                ),
                "receiving_role": shares.get("receiving_role", 0.0),
            }
        )
    elif position in {"WR", "TE"}:
        targets = attempts * shares.get("target_share", 0.0)
        out.update(
            {
                "routes": dropbacks * shares.get("route_participation", 0.0),
                "target_share": shares.get("target_share", 0.0),
                "targets": targets,
                "air_yards": attempts * 8.2 * shares.get("air_yard_share", 0.0),
                "red_zone_targets": (
                    scoring_opps
                    * pass_rate
                    * 1.5
                    * shares.get("red_zone_target_share", 0.0)
                ),
            }
        )
        if position == "TE":
            out["receiving_role"] = shares.get("receiving_role", 0.0)
            out["blocking_role"] = max(
                0.0,
                1.0 - shares.get("receiving_role", 0.0),
            ) * availability
    elif position == "K":
        out.update(
            {
                "field_goal_opportunities": (
                    (_num(team.get("expected_field_goals")) or 0.0)
                    * shares.get("field_goal_share", 0.0)
                ),
                "extra_point_opportunities": (
                    (_num(team.get("expected_offensive_tds")) or 0.0)
                    * shares.get("extra_point_share", 0.0)
                ),
            }
        )
    elif position == "DEF":
        opponent_attempts = _num(team.get("opponent_pass_attempts")) or 0.0
        opponent_dropbacks = opponent_attempts / max(0.5, 1.0 - SACK_RATE)
        out.update(
            {
                "opponent_dropbacks": opponent_dropbacks * availability,
                "sack_opportunities": opponent_dropbacks * availability,
                "turnover_opportunities": (
                    (_num(team.get("opponent_plays")) or 0.0) * availability
                ),
                "scoring_environment": _num(team.get("opponent_points")) or 0.0,
            }
        )

    # Yards are reported with the opportunities so the forecast
    # explains the path to points. Skill scaling happens later.
    if position == "QB":
        out["pass_yards"] = out.get("attempts", 0.0) * ypa
    return {key: round(float(value), 2) for key, value in out.items()}


def _points_at_unit_skill(
    position: str,
    shares: dict[str, float],
    team: dict[str, Any],
    *,
    scoring: str | None,
) -> float:
    opportunities = _opportunities(
        position,
        shares,
        team,
        availability=1.0,
    )
    rec_point = _reception_points(scoring)
    ypa = _num(team.get("yards_per_pass_attempt")) or 7.1
    ypc = _num(team.get("yards_per_rush")) or 4.3
    if position == "QB":
        attempts = opportunities.get("attempts", 0.0)
        rushes = opportunities.get("designed_rushes", 0.0) + opportunities.get(
            "scrambles", 0.0
        )
        pass_tds = (
            (_num(team.get("expected_pass_tds")) or 0.0)
            * shares.get("red_zone_pass_share", shares.get("dropback_share", 0.0))
        )
        rush_tds = (_num(team.get("expected_rush_tds")) or 0.0) * shares.get(
            "designed_rush_share",
            0.0,
        )
        interceptions = attempts * 0.023
        return (
            attempts * ypa / 25.0
            + pass_tds * 4.0
            - interceptions * 2.0
            + rushes * ypc / 10.0
            + rush_tds * 6.0
        )
    if position == "RB":
        carries = opportunities.get("carries", 0.0)
        targets = opportunities.get("targets", 0.0)
        rush_tds = (_num(team.get("expected_rush_tds")) or 0.0) * shares.get(
            "goal_line_share",
            0.0,
        )
        rec_tds = (_num(team.get("expected_pass_tds")) or 0.0) * shares.get(
            "target_share",
            0.0,
        )
        receptions = targets * 0.72
        return (
            carries * ypc / 10.0
            + rush_tds * 6.0
            + receptions * rec_point
            + targets * 6.5 / 10.0
            + rec_tds * 6.0
        )
    if position in {"WR", "TE"}:
        targets = opportunities.get("targets", 0.0)
        rec_tds = (_num(team.get("expected_pass_tds")) or 0.0) * shares.get(
            "red_zone_target_share",
            0.0,
        )
        catch = 0.62 if position == "TE" else 0.64
        yards_per_target = 7.4 if position == "TE" else 8.4
        if position == "TE":
            yards_per_target *= 0.65 + 0.35 * shares.get("receiving_role", 0.7)
        receptions = targets * catch
        return (
            receptions * rec_point
            + targets * yards_per_target / 10.0
            + rec_tds * 6.0
        )
    if position == "K":
        return (
            opportunities.get("field_goal_opportunities", 0.0) * 3.5
            + opportunities.get("extra_point_opportunities", 0.0)
        )
    if position == "DEF":
        league = league_team_environment()
        opp_points = _num(team.get("opponent_points")) or _num(
            league.get("opponent_points")
        ) or 22.0
        league_points = _num(league.get("opponent_points")) or 22.0
        opp_yards = (_num(team.get("opponent_pass_yards")) or 0.0) + (
            _num(team.get("opponent_rush_yards")) or 0.0
        )
        league_yards = (_num(league.get("opponent_pass_yards")) or 0.0) + (
            _num(league.get("opponent_rush_yards")) or 0.0
        )
        opp_turnovers = _num(team.get("opponent_turnovers")) or 0.0
        league_turnovers = _num(league.get("opponent_turnovers")) or 1.0
        points_scale = league_points / opp_points if opp_points else 1.0
        yards_scale = (
            league_yards / opp_yards if opp_yards else 1.0
        )
        turnover_scale = (
            opp_turnovers / league_turnovers if league_turnovers else 1.0
        )
        # Unit skill of 7 fantasy points in a league environment,
        # moved by the opponent's forecast rather than a flat boost.
        return 7.0 * (
            0.55 * points_scale
            + 0.25 * yards_scale
            + 0.20 * turnover_scale
        )
    return 0.0


def _prior_from_larger_role(
    position: str,
    listed_depth: int,
    production_prior: float,
    *,
    earned_as_starter: bool,
) -> bool:
    """True when the point prior cannot have been earned at this depth."""

    if earned_as_starter:
        return True
    if production_prior <= 0:
        return False
    depth_points = _points_at_unit_skill(
        position,
        _prior_for(position, listed_depth),
        league_team_environment(),
        scoring="ppr",
    )
    return production_prior > max(depth_points * 1.35, 0.5)


def _starter_points(position: str) -> float:
    pos = _normalize_position(position)
    cached = _starter_points_cache(pos)
    return cached


def _starter_points_cache(position: str) -> float:
    shares = _prior_for(position, 1)
    points = _points_at_unit_skill(
        position,
        shares,
        league_team_environment(),
        scoring="ppr",
    )
    if points > 0.5:
        return points
    return float(
        DEFAULT_CALIBRATION_CONFIG.positional_priors.get(position, 10.0)
    )


def _blend_roles(
    *,
    chart: dict[str, float],
    historical: dict[str, float],
    current: dict[str, float] | None,
    games: int,
    role_changed: bool,
    chart_overstates: bool = False,
) -> dict[str, float]:
    keys = set(chart) | set(historical) | set(current or {})
    current_weight = (
        current_season_weight_for_games(games) if current else 0.0
    )
    if games <= 0:
        current_weight = 0.0
    # A changed depth-chart job outweighs a rolling average.
    # An unchanged starter still keeps most of his recent usage.
    # A chart that describes a job the player is not playing
    # stays a light prior.
    if chart_overstates:
        context_weight = 0.15
    elif role_changed:
        context_weight = 0.92
    else:
        context_weight = 0.35
    blended: dict[str, float] = {}
    for key in keys:
        chart_value = float(chart.get(key) or 0.0)
        if key in historical:
            historical_value = float(historical[key])
        elif current is not None and key in current:
            historical_value = float(current[key])
        else:
            historical_value = chart_value
        if current is None:
            observed = historical_value
            weight = 0.0
        else:
            observed = float(current.get(key, historical_value))
            weight = current_weight
        past = (historical_value * (1.0 - weight)) + (observed * weight)
        blended[key] = (past * (1.0 - context_weight)) + (
            chart_value * context_weight
        )
    return blended


# Shares the usage table does not store. They follow the share
# that is observed, instead of keeping a starter's chart value
# after his carries or targets have been scaled down.
_UNOBSERVED_SCALED_BY = {
    "QB": (("red_zone_pass_share", "dropback_share"),),
    "RB": (
        ("goal_line_share", "carry_share"),
        ("receiving_role", "target_share"),
    ),
    "WR": (
        ("air_yard_share", "target_share"),
        ("red_zone_target_share", "target_share"),
    ),
    "TE": (
        ("air_yard_share", "target_share"),
        ("red_zone_target_share", "target_share"),
        ("receiving_role", "target_share"),
    ),
}


def _scale_unobserved_shares(
    shares: dict[str, float],
    chart: dict[str, float],
    observed_keys: set[str],
    position: str,
) -> dict[str, float]:
    scaled = dict(shares)
    for derived, driver in _UNOBSERVED_SCALED_BY.get(position, ()):
        if derived in observed_keys or derived not in chart:
            continue
        chart_driver = float(chart.get(driver) or 0.0)
        if chart_driver <= 0:
            continue
        ratio = float(scaled.get(driver) or 0.0) / chart_driver
        scaled[derived] = float(chart.get(derived) or 0.0) * ratio
    return scaled


def _observed_role(
    usage: dict[str, Any],
    chart: dict[str, float],
    position: str,
) -> dict[str, float]:
    observed = _usage_role(usage, None)
    return _scale_unobserved_shares(
        _usage_role(usage, chart),
        chart,
        set(observed),
        position,
    )


def _apply_matchup(
    shares: dict[str, float],
    matchup_score: float | None,
    position: str,
) -> dict[str, float]:
    score = _num(matchup_score)
    if score is None or position in {"K", "DEF"}:
        return dict(shares)
    tilt = _clamp(1.0 + 0.0025 * (score - 50.0), 0.92, 1.08)
    tilted = dict(shares)
    for key in (
        "target_share",
        "carry_share",
        "route_participation",
        "dropback_share",
        "air_yard_share",
        "red_zone_target_share",
    ):
        if key in tilted:
            tilted[key] = tilted[key] * tilt
    return tilted


def _prior_for(position: str, depth: int) -> dict[str, float]:
    table = _ROLE_PRIORS.get(position) or _ROLE_PRIORS["WR"]
    if depth in table:
        return dict(table[depth])
    deepest = max(table)
    if depth > deepest:
        return dict(table[deepest])
    return dict(table[min(table)])


def _usage_role(
    usage: dict[str, Any] | None,
    fallback: dict[str, float] | None,
) -> dict[str, float]:
    if not usage:
        return dict(fallback or {})
    mapped: dict[str, float] = dict(fallback or {})
    for source, target in _USAGE_TO_ROLE.items():
        value = _share(usage.get(source))
        if value is None:
            continue
        mapped[target] = value
    snap = _share(usage.get("offensive_snap_share"))
    starter_dropbacks = float((fallback or {}).get("dropback_share") or 0.0)
    if (
        snap is not None
        and snap >= 0.85
        and starter_dropbacks >= 0.5
        and "dropback_share" not in usage
    ):
        # Only a depth-chart starter converts snap share into
        # the offense's dropbacks. A backup's old snap rate
        # does not keep the starting job.
        mapped["dropback_share"] = max(
            snap,
            mapped.get("dropback_share", 0.0),
        )
    return mapped


def _role_size(shares: dict[str, float]) -> float:
    keys = (
        "dropback_share",
        "carry_share",
        "target_share",
        "field_goal_share",
        "unit_share",
    )
    values = [float(shares.get(key) or 0.0) for key in keys]
    return max(values) if values else 0.0


def _listed_depth(
    depth_order: int | None,
    opportunity_score: float | None,
) -> int:
    if depth_order is not None and depth_order > 0:
        return int(depth_order)
    score = _num(opportunity_score)
    if score is not None and score < 35:
        return 3
    return 1


def _availability(
    injury_status: str | None,
    roster_status: str | None,
) -> float:
    injury = str(injury_status or "").strip().lower()
    roster = str(roster_status or "").strip().lower()
    if injury in _OUT_STATUSES or roster in _OUT_STATUSES:
        return 0.0
    if injury in _DOUBTFUL:
        return 0.25
    if injury in _QUESTIONABLE:
        return 0.85
    return 1.0


def _is_unavailable(player: dict[str, Any]) -> bool:
    return (
        _availability(
            str(player.get("injury_status") or "") or None,
            str(player.get("status") or "") or None,
        )
        <= 0.25
    )


def _summary(
    position: str,
    depth: int,
    shares: dict[str, float],
    opportunities: dict[str, float],
    promoted: bool,
) -> str:
    label = f"{position}{depth}"
    prefix = f"Promoted to {label}" if promoted else label
    if position == "QB":
        return (
            f"{prefix}: {opportunities.get('dropbacks', 0):.1f} dropbacks, "
            f"{opportunities.get('attempts', 0):.1f} attempts, "
            f"{opportunities.get('completions', 0):.1f} completions, "
            f"{opportunities.get('designed_rushes', 0):.1f} designed rushes, "
            f"{opportunities.get('scrambles', 0):.1f} scrambles, "
            f"{opportunities.get('red_zone_pass_opportunities', 0):.1f} "
            "red-zone pass chances."
        )
    if position == "RB":
        return (
            f"{prefix}: {shares.get('snap_share', 0):.0%} snaps, "
            f"{opportunities.get('carries', 0):.1f} carries, "
            f"{opportunities.get('targets', 0):.1f} targets, "
            f"{opportunities.get('routes', 0):.1f} routes, "
            f"{opportunities.get('goal_line_carries', 0):.1f} goal-line carries."
        )
    if position == "WR":
        return (
            f"{prefix}: {opportunities.get('routes', 0):.1f} routes, "
            f"{shares.get('target_share', 0):.0%} target share, "
            f"{opportunities.get('targets', 0):.1f} targets, "
            f"{opportunities.get('air_yards', 0):.0f} air yards, "
            f"{opportunities.get('red_zone_targets', 0):.1f} red-zone targets."
        )
    if position == "TE":
        return (
            f"{prefix}: {opportunities.get('routes', 0):.1f} routes, "
            f"{shares.get('target_share', 0):.0%} target share, "
            f"{opportunities.get('targets', 0):.1f} targets, "
            f"{opportunities.get('red_zone_targets', 0):.1f} red-zone targets, "
            f"{shares.get('receiving_role', 0):.0%} receiving role."
        )
    if position == "K":
        return (
            f"{prefix}: {opportunities.get('field_goal_opportunities', 0):.1f} "
            "field-goal chances, "
            f"{opportunities.get('extra_point_opportunities', 0):.1f} "
            "extra-point chances."
        )
    return (
        f"Opponent {opportunities.get('opponent_dropbacks', 0):.1f} dropbacks, "
        f"{opportunities.get('sack_opportunities', 0):.1f} sack chances, "
        f"{opportunities.get('turnover_opportunities', 0):.0f} turnover chances, "
        f"scoring environment {opportunities.get('scoring_environment', 0):.1f}."
    )


def _role_drivers(
    *,
    position: str,
    listed_depth: int,
    effective_depth: int,
    games: int,
    promoted: bool,
    availability: float,
    injury_status: str | None,
    matchup_score: float | None,
    opportunities: dict[str, float],
) -> list[str]:
    drivers = [
        (
            "Role is forecast from the depth chart, recent usage, and "
            "historical role. Fantasy points are the sum of the yards, "
            "catches, and touchdowns that role is predicted to produce."
        )
    ]
    if games <= 0:
        drivers.append(
            "No current-season sample; the forecast uses the expected "
            "role and historical skill instead of a zero average."
        )
    if promoted:
        drivers.append(
            f"{position}{listed_depth} is promoted to {position}{effective_depth} "
            "because a teammate ahead of him is unavailable."
        )
    elif listed_depth >= 3:
        drivers.append(
            f"Depth-chart {position}{listed_depth} does not inherit a "
            "starter's historical workload."
        )
    if availability <= 0:
        drivers.append(
            f"Listed {injury_status or 'unavailable'}; expected role is zero."
        )
    elif availability < 1:
        drivers.append(
            f"Availability ({injury_status or 'limited'}) scales the "
            f"expected role to {availability:.0%}."
        )
    if matchup_score is not None and position not in {"K", "DEF"}:
        drivers.append(
            "Matchup adjusts how the role is used. It does not apply "
            "a second environment multiplier."
        )
    if position == "QB":
        drivers.append(
            f"Forecast {opportunities.get('attempts', 0):.1f} attempts and "
            f"{opportunities.get('red_zone_pass_opportunities', 0):.1f} "
            "red-zone pass chances."
        )
    elif position == "RB":
        drivers.append(
            f"Forecast {opportunities.get('carries', 0):.1f} rush carries and "
            f"{opportunities.get('targets', 0):.1f} targets."
        )
    elif position in {"WR", "TE"}:
        drivers.append(
            f"Forecast {opportunities.get('targets', 0):.1f} targets "
            "and red-zone chances drawn from the team's passing touchdowns."
        )
    elif position == "K":
        drivers.append(
            f"Forecast {opportunities.get('field_goal_opportunities', 0):.1f} "
            "field goal opportunities."
        )
    else:
        drivers.append(
            f"Opponent scoring environment "
            f"{opportunities.get('scoring_environment', 0):.1f}."
        )
    return drivers


def _load_usage_window(
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
          AVG(offensive_snap_share) AS offensive_snap_share,
          AVG(target_share) AS target_share,
          AVG(rush_share) AS rush_share,
          AVG(route_participation_rate) AS route_participation_rate,
          AVG(air_yard_share) AS air_yard_share,
          AVG(qb_rush_share) AS qb_rush_share
        FROM {FANTASY_SCHEMA}.fact_player_usage
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
        shares = {}
        for key, value in row.items():
            if key == "player_id":
                continue
            number = _share(value)
            if number is not None:
                shares[key] = number
        if shares:
            out[player_id] = shares
    return out


def _league(key: str) -> float:
    value = _num(league_team_environment().get(key))
    return float(value or 1.0)


def _share(value: Any) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if number > 1.5:
        number = number / 100.0
    return _clamp(number, 0.0, 1.0)


def _reception_points(scoring: str | None) -> float:
    key = normalize_scoring(scoring)
    if key == "standard":
        return 0.0
    if key == "half_ppr":
        return 0.5
    return 1.0


def _normalize_position(position: Any) -> str:
    pos = str(position or "").strip().upper()
    if pos in {"DST", "D/ST", "DEFENSE"}:
        return "DEF"
    if pos in {"PK"}:
        return "K"
    if pos in {"FB", "HB"}:
        return "RB"
    return pos or "WR"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number
