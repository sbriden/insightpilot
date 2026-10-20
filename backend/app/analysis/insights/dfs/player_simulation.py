"""
Joint simulation of a game and the players in it.

One draw builds the game: score, pace, pass/rush mix, and the
touchdown pool. Players then receive pieces of that same draw.
A pass touchdown is caught by one receiver and thrown by one
quarterback. A rush touchdown goes to one ball carrier. When a
player is out, his share is given to the teammates who are in.

Floors and ceilings are percentiles of that distribution. They
are not a guaranteed minimum or a multiplier around the median.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.analysis.insights.dfs.forecast_contract import (
    apply_forecast_contract,
)
from app.analysis.insights.dfs.player_role import _reception_points
from app.analysis.insights.game_forecast import (
    LEAGUE_DRIVES,
    LEAGUE_PASS_RATE,
    LEAGUE_PLAYS,
    LEAGUE_POINTS,
    LEAGUE_YPA,
    LEAGUE_YPC,
    MARGIN_SD,
    SACK_RATE,
    TOTAL_SD,
)


@dataclass(frozen=True)
class SimulationConfig:
    """Percentile levels and how many games to draw."""

    n_sims: int = 400
    seed: int | None = None
    floor_percentile: float = 10.0
    median_percentile: float = 50.0
    ceiling_percentile: float = 90.0
    # Upside and bust are measured against the component projection.
    upside_multiple: float = 1.25
    bust_multiple: float = 0.60


DEFAULT_SIMULATION_CONFIG = SimulationConfig()


def apply_joint_simulation(
    players: list[dict[str, Any]],
    *,
    scoring: str | None = "ppr",
    config: SimulationConfig | None = None,
    contest_type: str | None = "classic",
    captain_multiplier: float = 1.5,
) -> list[dict[str, Any]]:
    """
    Replace multiplier floors and ceilings with simulation percentiles.

    Players without a game forecast keep the confidence-based range.
    """

    settings = config or DEFAULT_SIMULATION_CONFIG
    groups = _group_games(players)
    for game_players in groups:
        _apply_game(
            game_players,
            scoring=scoring,
            config=settings,
            contest_type=contest_type,
            captain_multiplier=captain_multiplier,
        )
    return players


def simulate_game_points(
    players: list[dict[str, Any]],
    *,
    scoring: str | None = "ppr",
    config: SimulationConfig | None = None,
) -> dict[str, np.ndarray]:
    """
    Fantasy points per simulation for one game's players.

    Also stashes component arrays on ``config``-independent keys
    of a side dictionary returned only through ``details`` when
    requested via the players' simulation scratch. Tests use
    ``simulate_game_details``.
    """

    details = simulate_game_details(
        players,
        scoring=scoring,
        config=config,
    )
    return details["points"]


def simulate_game_details(
    players: list[dict[str, Any]],
    *,
    scoring: str | None = "ppr",
    config: SimulationConfig | None = None,
) -> dict[str, Any]:
    """Points and the shared team draws those points came from."""

    settings = config or DEFAULT_SIMULATION_CONFIG
    prepared = [_prepare_player(player) for player in players]
    prepared = [player for player in prepared if player is not None]
    if len(prepared) < 1:
        return {"points": {}, "teams": {}}
    sides = _game_sides(prepared)
    if sides is None:
        return {"points": {}, "teams": {}}
    rng = np.random.default_rng(_seed(prepared, settings.seed))
    team_draws = _draw_game(sides, settings.n_sims, rng)
    points, components = _score_players(
        prepared,
        team_draws,
        rng,
        scoring=scoring,
    )
    return {
        "points": points,
        "components": components,
        "teams": team_draws,
    }


def _apply_game(
    players: list[dict[str, Any]],
    *,
    scoring: str | None,
    config: SimulationConfig,
    contest_type: str | None = "classic",
    captain_multiplier: float = 1.5,
) -> None:
    details = simulate_game_details(
        players,
        scoring=scoring,
        config=config,
    )
    points = details["points"]
    if not points:
        return
    for player in players:
        player_id = str(player.get("player_id") or "")
        draws = points.get(player_id)
        if draws is None or len(draws) == 0:
            continue
        summary = _summarize(draws, player, config)
        component = float(player.get("projection") or 0.0)
        summary["component_projection"] = round(component, 2)
        player["simulation"] = summary
        player["projection"] = summary["median"]
        apply_forecast_contract(
            player,
            draws,
            contest_type=contest_type,
            floor_percentile=config.floor_percentile,
            ceiling_percentile=config.ceiling_percentile,
            captain_multiplier=captain_multiplier,
        )
        player["insightpilot_projection"] = summary["median"]
        player["floor"] = summary["floor"]
        player["ceiling"] = summary["ceiling"]
        salary = player.get("salary") or 0
        if salary:
            player["value"] = round(
                float(summary["median"]) / (float(salary) / 1000.0),
                2,
            )
        drivers = list(player.get("projection_drivers") or [])
        drivers.append(summary["note"])
        player["projection_drivers"] = drivers
        reason = str(player.get("projection_environment_reason") or "")
        player["projection_environment_reason"] = f"{reason} {summary['note']}".strip()


def _summarize(
    draws: np.ndarray,
    player: dict[str, Any],
    config: SimulationConfig,
) -> dict[str, Any]:
    floor = float(np.percentile(draws, config.floor_percentile))
    median = float(np.percentile(draws, config.median_percentile))
    ceiling = float(np.percentile(draws, config.ceiling_percentile))
    anchor = float(player.get("projection") or median)
    upside_at = max(0.0, anchor * config.upside_multiple)
    bust_at = max(0.0, anchor * config.bust_multiple)
    upside = float(np.mean(draws > upside_at))
    bust = float(np.mean(draws < bust_at))
    floor_label = _pct_label(config.floor_percentile)
    ceil_label = _pct_label(config.ceiling_percentile)
    note = (
        f"Floor is the {floor_label} of the simulated games "
        f"({floor:.1f}) and ceiling is the {ceil_label} ({ceiling:.1f}). "
        "A percentile is not a guaranteed outcome."
    )
    return {
        "source": "joint_game_simulation",
        "n_sims": int(len(draws)),
        "floor_percentile": config.floor_percentile,
        "median_percentile": config.median_percentile,
        "ceiling_percentile": config.ceiling_percentile,
        "floor": round(floor, 1),
        "median": round(median, 1),
        "ceiling": round(ceiling, 1),
        "mean": round(float(np.mean(draws)), 2),
        "upside_probability": round(upside, 3),
        "bust_probability": round(bust, 3),
        "upside_threshold": round(upside_at, 2),
        "bust_threshold": round(bust_at, 2),
        "upside_multiple": config.upside_multiple,
        "bust_multiple": config.bust_multiple,
        "note": note,
    }


def _group_games(
    players: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for player in players:
        source = player.get("adjustment_source") or player.get(
            "projection_source"
        )
        if source not in {None, "game_forecast"}:
            continue
        env = player.get("game_environment") or {}
        if env.get("projected_points") is None:
            continue
        team = str(player.get("team") or env.get("team") or "").upper()
        opponent = str(
            player.get("opponent") or env.get("opponent") or ""
        ).upper()
        if not team or not opponent:
            continue
        key = tuple(sorted((team, opponent)))
        groups.setdefault(key, []).append(player)
    return list(groups.values())


def _prepare_player(player: dict[str, Any]) -> dict[str, Any] | None:
    role = player.get("role_forecast") or {}
    shares = dict(role.get("shares") or {})
    if not shares and not role:
        return None
    env = player.get("game_environment") or {}
    team = str(player.get("team") or env.get("team") or "").upper()
    if not team:
        return None
    availability = float(role.get("availability") if role.get("availability") is not None else 1.0)
    if availability > 0.05:
        restored = {
            key: float(value) / availability
            for key, value in shares.items()
        }
    else:
        restored = {key: 0.0 for key in shares}
    rates = (player.get("scoring_components") or {}).get("rates") or {}
    skill = float(
        (player.get("scoring_components") or {}).get("skill_multiplier") or 1.0
    )
    sample = float(rates.get("sample_weight") or 0.0)
    return {
        "player_id": str(player.get("player_id") or ""),
        "team": team,
        "position": str(role.get("position") or player.get("position") or "WR"),
        "depth": int(role.get("effective_depth") or 1),
        "availability": availability,
        "shares": restored,
        "rates": rates,
        "skill": skill,
        "sample_weight": sample,
        "environment": env,
    }


def _game_sides(
    players: list[dict[str, Any]],
) -> dict[str, dict[str, float]] | None:
    by_team: dict[str, dict[str, Any]] = {}
    for player in players:
        by_team.setdefault(player["team"], player["environment"])
    if len(by_team) == 1:
        only = next(iter(by_team))
        env = by_team[only]
        opponent = str(env.get("opponent") or "OPP").upper()
        by_team[opponent] = {
            "projected_points": env.get("opponent_points"),
            "opponent_points": env.get("projected_points"),
            "expected_plays": env.get("expected_plays"),
        }
    teams = list(by_team)
    if len(teams) < 2:
        return None
    # Stable order so the margin sign matches the first team's view.
    first, second = teams[0], teams[1]
    return {
        "a": _side_mean(first, by_team[first], by_team.get(second) or {}),
        "b": _side_mean(second, by_team.get(second) or {}, by_team[first]),
    }


def _side_mean(
    team: str,
    env: dict[str, Any],
    other: dict[str, Any],
) -> dict[str, float | str]:
    points = _num(env.get("projected_points"))
    if points is None:
        points = _num(other.get("opponent_points")) or LEAGUE_POINTS
    opponent_points = _num(env.get("opponent_points"))
    if opponent_points is None:
        opponent_points = _num(other.get("projected_points")) or LEAGUE_POINTS
    plays = _num(env.get("expected_plays")) or _num(other.get("expected_plays"))
    pace = (plays / LEAGUE_PLAYS) if plays else 1.0
    return {
        "team": team,
        "points": float(points),
        "opponent_points": float(opponent_points),
        "pace": float(pace),
    }


def _draw_game(
    sides: dict[str, dict[str, float | str]],
    n_sims: int,
    rng: np.random.Generator,
) -> dict[str, dict[str, np.ndarray]]:
    mean_a = float(sides["a"]["points"])
    mean_b = float(sides["b"]["points"])
    total_mean = mean_a + mean_b
    margin_mean = mean_a - mean_b
    pace = float(sides["a"]["pace"])
    total = rng.normal(total_mean, TOTAL_SD, size=n_sims)
    margin = rng.normal(margin_mean, MARGIN_SD, size=n_sims)
    pace_draw = np.clip(rng.normal(pace, 0.035, size=n_sims), 0.88, 1.15)
    points_a = np.clip((total + margin) / 2.0, 0.0, 70.0)
    points_b = np.clip((total - margin) / 2.0, 0.0, 70.0)
    env_a = _environment(points_a, points_b, pace_draw)
    env_b = _environment(points_b, points_a, pace_draw)
    return {
        str(sides["a"]["team"]): env_a,
        str(sides["b"]["team"]): env_b,
    }


def _environment(
    points: np.ndarray,
    opponent_points: np.ndarray,
    pace: np.ndarray,
) -> dict[str, np.ndarray]:
    """Same identity as the game forecast: TDs and field goals match the score."""

    points_ratio = points / LEAGUE_POINTS
    plays = LEAGUE_PLAYS * pace
    drives = LEAGUE_DRIVES * pace
    turnover_rate = np.clip(0.105 * (1.08 - 0.08 * points_ratio), 0.06, 0.16)
    turnovers = drives * turnover_rate
    opportunity_rate = np.clip(
        0.382 * (0.45 + 0.55 * points_ratio),
        0.20,
        0.65,
    )
    scoring_opportunities = drives * opportunity_rate
    td_share = np.clip(0.57 + 0.05 * (points_ratio - 1.0), 0.42, 0.72)
    fg_share = np.clip(0.36 - 0.03 * (points_ratio - 1.0), 0.18, 0.48)
    fg_share = np.where(
        td_share + fg_share > 0.92,
        np.maximum(0.0, 0.92 - td_share),
        fg_share,
    )
    offensive_tds = scoring_opportunities * td_share
    field_goals = scoring_opportunities * fg_share
    component = offensive_tds * 7.0 + field_goals * 3.0
    scale = np.ones_like(points)
    positive = component > 1e-6
    scale[positive] = points[positive] / component[positive]
    offensive_tds = offensive_tds * scale
    field_goals = field_goals * scale
    margin = points - opponent_points
    pass_rate = np.clip(LEAGUE_PASS_RATE - 0.004 * margin, 0.48, 0.68)
    pass_attempts = plays * pass_rate * (1.0 - SACK_RATE)
    rush_attempts = plays * (1.0 - pass_rate)
    pass_td_share = np.clip(
        0.63 + (pass_rate - LEAGUE_PASS_RATE) * 1.6,
        0.45,
        0.80,
    )
    pass_tds = offensive_tds * pass_td_share
    rush_tds = np.maximum(0.0, offensive_tds - pass_tds)
    ypa = LEAGUE_YPA * (0.94 + 0.06 * points_ratio)
    ypc = LEAGUE_YPC * (0.96 + 0.04 * points_ratio)
    return {
        "points": points,
        "opponent_points": opponent_points,
        "margin": margin,
        "plays": plays,
        "pass_attempts": pass_attempts,
        "rush_attempts": rush_attempts,
        "pass_tds": pass_tds,
        "rush_tds": rush_tds,
        "offensive_tds": offensive_tds,
        "field_goals": field_goals,
        "turnovers": turnovers,
        "ypa": ypa,
        "ypc": ypc,
        "dropbacks": pass_attempts / max(0.5, 1.0 - SACK_RATE),
    }


def _score_players(
    players: list[dict[str, Any]],
    team_draws: dict[str, dict[str, np.ndarray]],
    rng: np.random.Generator,
    *,
    scoring: str | None,
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, np.ndarray]]]:
    n_sims = len(next(iter(team_draws.values()))["points"])
    rec_point = _reception_points(scoring)
    by_team: dict[str, list[dict[str, Any]]] = {}
    for player in players:
        by_team.setdefault(player["team"], []).append(player)

    points: dict[str, np.ndarray] = {}
    components: dict[str, dict[str, np.ndarray]] = {}
    for team, roster in by_team.items():
        env = team_draws.get(team)
        if env is None:
            continue
        opponent_name = _opponent_name(team, team_draws)
        opponent = team_draws.get(opponent_name) if opponent_name else None
        active = {
            player["player_id"]: _availability_draw(player, n_sims, rng)
            for player in roster
        }
        shocks = {
            player["player_id"]: _mean_one_shock(
                rng,
                n_sims,
                0.16 * (1.0 - 0.45 * player["sample_weight"]),
            )
            for player in roster
        }
        pools = {
            "dropback_share": _pool(roster, "dropback_share", active, shocks),
            "carry_share": _pool(roster, "carry_share", active, shocks),
            "target_share": _pool(roster, "target_share", active, shocks),
            "goal_line_share": _pool(roster, "goal_line_share", active, shocks),
            "red_zone_target_share": _pool(
                roster,
                "red_zone_target_share",
                active,
                shocks,
            ),
            "red_zone_pass_share": _pool(
                roster,
                "red_zone_pass_share",
                active,
                shocks,
            ),
            "designed_rush_share": _pool(
                roster,
                "designed_rush_share",
                active,
                shocks,
            ),
            "field_goal_share": _pool(roster, "field_goal_share", active, shocks),
            "extra_point_share": _pool(
                roster,
                "extra_point_share",
                active,
                shocks,
            ),
        }
        catch_pool = pools["red_zone_target_share"] or pools["target_share"]
        pass_td_catch, pass_td_throw = _allocate_events(
            env["pass_tds"],
            [catch_pool.get(p["player_id"]) for p in roster],
            [pools["dropback_share"].get(p["player_id"]) for p in roster],
            [p["player_id"] for p in roster],
            rng,
        )
        rush_td = _allocate_one_pool(
            env["rush_tds"],
            roster,
            pools,
            rng,
            primary="goal_line_share",
            secondary="designed_rush_share",
        )
        team_pass_shock = _mean_one_shock(rng, n_sims, 0.05)
        team_rush_shock = _mean_one_shock(rng, n_sims, 0.05)
        qb_pass_yards: dict[str, np.ndarray] = {}
        for player in roster:
            if player["position"] != "QB":
                continue
            pid = player["player_id"]
            attempts = env["pass_attempts"] * pools["dropback_share"].get(
                pid,
                np.zeros(n_sims),
            )
            ypa = _rate(player, "yards_per_attempt", LEAGUE_YPA) * player["skill"]
            eff = _mean_one_shock(
                rng,
                n_sims,
                0.08 * (1.0 - 0.4 * player["sample_weight"]),
            )
            qb_pass_yards[pid] = attempts * ypa * team_pass_shock * eff
        if qb_pass_yards:
            team_pass_yards = np.zeros(n_sims)
            for values in qb_pass_yards.values():
                team_pass_yards = team_pass_yards + values
        else:
            team_pass_yards = env["pass_attempts"] * env["ypa"] * team_pass_shock
        raw_rec_yards = {}
        for player in roster:
            if player["position"] not in {"WR", "TE", "RB"}:
                continue
            pid = player["player_id"]
            targets = env["pass_attempts"] * pools["target_share"].get(
                pid,
                np.zeros(n_sims),
            )
            ypt = (
                _rate(player, "yards_per_target", _default_ypt(player))
                * player["skill"]
            )
            eff = _mean_one_shock(
                rng,
                n_sims,
                0.10 * (1.0 - 0.4 * player["sample_weight"]),
            )
            raw_rec_yards[pid] = targets * ypt * eff
        rec_scale = _scale_to(raw_rec_yards, team_pass_yards)
        raw_rush = {}
        for player in roster:
            pid = player["player_id"]
            carries = env["rush_attempts"] * (
                pools["carry_share"].get(pid, np.zeros(n_sims))
                + pools["designed_rush_share"].get(pid, np.zeros(n_sims))
            )
            ypc = _rate(player, "yards_per_carry", LEAGUE_YPC) * player["skill"]
            eff = _mean_one_shock(
                rng,
                n_sims,
                0.10 * (1.0 - 0.4 * player["sample_weight"]),
            )
            raw_rush[pid] = carries * ypc * eff * team_rush_shock
        team_rush_yards = env["rush_attempts"] * env["ypc"] * team_rush_shock
        rush_scale = _scale_to(raw_rush, team_rush_yards)

        for player in roster:
            pid = player["player_id"]
            position = player["position"]
            targets = env["pass_attempts"] * pools["target_share"].get(
                pid,
                np.zeros(n_sims),
            )
            catch = np.clip(
                _rate(player, "catch_rate", _default_catch(player)) * player["skill"],
                0.35,
                0.9,
            )
            receptions = targets * catch
            rec_yards = raw_rec_yards.get(pid, np.zeros(n_sims)) * rec_scale
            rush_yards = raw_rush.get(pid, np.zeros(n_sims)) * rush_scale
            rec_tds = pass_td_catch.get(pid, np.zeros(n_sims))
            rush_tds = rush_td.get(pid, np.zeros(n_sims))
            if position == "QB":
                attempts = env["pass_attempts"] * pools["dropback_share"].get(
                    pid,
                    np.zeros(n_sims),
                )
                pass_yards = qb_pass_yards.get(pid, np.zeros(n_sims))
                pass_tds = pass_td_throw.get(pid, np.zeros(n_sims))
                ints = attempts * _rate(player, "interception_rate", 0.023)
                fantasy = (
                    pass_yards / 25.0
                    + pass_tds * 4.0
                    - ints * 2.0
                    + rush_yards / 10.0
                    + rush_tds * 6.0
                )
                components[pid] = {
                    "attempts": attempts,
                    "pass_yards": pass_yards,
                    "pass_tds": pass_tds,
                    "rush_yards": rush_yards,
                    "rush_tds": rush_tds,
                }
            elif position == "K":
                fg = env["field_goals"] * pools["field_goal_share"].get(
                    pid,
                    np.zeros(n_sims),
                )
                xp = env["offensive_tds"] * pools["extra_point_share"].get(
                    pid,
                    np.zeros(n_sims),
                )
                fantasy = fg * 3.5 + xp * 0.94
                components[pid] = {"field_goals": fg, "extra_points": xp}
            elif position == "DEF":
                opp = opponent or env
                fantasy = _defense_points(player, opp)
                components[pid] = {
                    "opponent_points": opp["points"],
                    "opponent_dropbacks": opp["dropbacks"],
                }
            else:
                fantasy = (
                    rush_yards / 10.0
                    + rush_tds * 6.0
                    + receptions * rec_point
                    + rec_yards / 10.0
                    + rec_tds * 6.0
                )
                carries = env["rush_attempts"] * pools["carry_share"].get(
                    pid,
                    np.zeros(n_sims),
                )
                components[pid] = {
                    "carries": carries,
                    "targets": targets,
                    "receiving_yards": rec_yards,
                    "receiving_tds": rec_tds,
                    "rush_tds": rush_tds,
                    "rush_yards": rush_yards,
                }
            points[pid] = np.maximum(0.0, fantasy)
    return points, components


def _defense_points(
    player: dict[str, Any],
    opponent: dict[str, np.ndarray],
) -> np.ndarray:
    skill = player["skill"] if player["skill"] > 0 else 1.0
    league_dropbacks = (LEAGUE_PLAYS * LEAGUE_PASS_RATE) / (1.0 - SACK_RATE)
    dropbacks = opponent["dropbacks"]
    turnovers = opponent["turnovers"]
    opp_points = np.maximum(opponent["points"], 1.0)
    league_turnovers = 1.15
    return (
        2.4 * (dropbacks / league_dropbacks) * skill
        + 2.3 * (turnovers / league_turnovers) * skill
        + 2.3 * (LEAGUE_POINTS / opp_points) * skill
    )


def _allocate_events(
    expected: np.ndarray,
    catch_shares: list[np.ndarray | None],
    throw_shares: list[np.ndarray | None],
    player_ids: list[str],
    rng: np.random.Generator,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """
    Each touchdown is caught once and thrown once.

    The catcher's receiving touchdown and the thrower's passing
    touchdown are the same event.
    """

    n_sims = len(expected)
    caught = {pid: np.zeros(n_sims) for pid in player_ids}
    thrown = {pid: np.zeros(n_sims) for pid in player_ids}
    counts = rng.poisson(np.maximum(expected, 0.0))
    catchers = [i for i, share in enumerate(catch_shares) if share is not None]
    throwers = [i for i, share in enumerate(throw_shares) if share is not None]
    if not catchers and not throwers:
        return caught, thrown
    for sim in range(n_sims):
        n_events = int(counts[sim])
        if n_events <= 0:
            continue
        catch_p = _probs(catch_shares, catchers, sim)
        throw_p = _probs(throw_shares, throwers, sim)
        if catch_p is not None:
            picks = rng.choice(catchers, size=n_events, p=catch_p)
            for pick in picks:
                caught[player_ids[int(pick)]][sim] += 1.0
        if throw_p is not None:
            picks = rng.choice(throwers, size=n_events, p=throw_p)
            for pick in picks:
                thrown[player_ids[int(pick)]][sim] += 1.0
    return caught, thrown


def _allocate_one_pool(
    expected: np.ndarray,
    roster: list[dict[str, Any]],
    pools: dict[str, dict[str, np.ndarray]],
    rng: np.random.Generator,
    *,
    primary: str,
    secondary: str,
) -> dict[str, np.ndarray]:
    n_sims = len(expected)
    counts = rng.poisson(np.maximum(expected, 0.0))
    awarded = {player["player_id"]: np.zeros(n_sims) for player in roster}
    ids = [player["player_id"] for player in roster]
    for sim in range(n_sims):
        n_events = int(counts[sim])
        if n_events <= 0:
            continue
        weights = []
        for pid in ids:
            primary_w = float(pools[primary].get(pid, np.zeros(1))[sim]) if pid in pools[primary] else 0.0
            secondary_w = (
                float(pools[secondary].get(pid, np.zeros(1))[sim])
                if pid in pools[secondary]
                else 0.0
            )
            weights.append(max(primary_w, secondary_w))
        total = sum(weights)
        if total <= 1e-9:
            continue
        probs = [weight / total for weight in weights]
        picks = rng.choice(len(ids), size=n_events, p=probs)
        for pick in picks:
            awarded[ids[int(pick)]][sim] += 1.0
    return awarded


def _pool(
    roster: list[dict[str, Any]],
    key: str,
    active: dict[str, np.ndarray],
    shocks: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """
    Shock each share, drop players who are out, and give their
    work to the teammates who remain.
    """

    n_sims = len(next(iter(active.values())))
    raw: dict[str, np.ndarray] = {}
    base_mass = 0.0
    for player in roster:
        share = float(player["shares"].get(key) or 0.0)
        if share <= 0:
            continue
        base_mass += share
        raw[player["player_id"]] = (
            share * shocks[player["player_id"]] * active[player["player_id"]]
        )
    if not raw or base_mass <= 0:
        return {}
    stacked = np.vstack(list(raw.values()))
    totals = stacked.sum(axis=0)
    scale = np.ones(n_sims)
    positive = totals > 1e-8
    scale[positive] = base_mass / totals[positive]
    scale[~positive] = 0.0
    return {pid: values * scale for pid, values in raw.items()}


def _probs(
    shares: list[np.ndarray | None],
    indexes: list[int],
    sim: int,
) -> np.ndarray | None:
    if not indexes:
        return None
    weights = np.array(
        [float(shares[index][sim]) if shares[index] is not None else 0.0 for index in indexes],
        dtype=float,
    )
    total = float(weights.sum())
    if total <= 1e-9:
        return None
    return weights / total


def _availability_draw(
    player: dict[str, Any],
    n_sims: int,
    rng: np.random.Generator,
) -> np.ndarray:
    availability = float(player["availability"])
    if availability >= 0.99:
        return np.ones(n_sims)
    if availability <= 0.01:
        return np.zeros(n_sims)
    return (rng.random(n_sims) < availability).astype(float)


def _mean_one_shock(
    rng: np.random.Generator,
    n_sims: int,
    sigma: float,
) -> np.ndarray:
    if sigma <= 1e-6:
        return np.ones(n_sims)
    return rng.lognormal(-0.5 * sigma * sigma, sigma, size=n_sims)


def _scale_to(
    raw: dict[str, np.ndarray],
    target: np.ndarray,
) -> np.ndarray:
    if not raw:
        return np.ones(len(target))
    total = np.zeros(len(target))
    for values in raw.values():
        total = total + values
    scale = np.ones(len(target))
    positive = total > 1e-6
    scale[positive] = target[positive] / total[positive]
    return scale


def _rate(player: dict[str, Any], key: str, default: float) -> float:
    value = player["rates"].get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _default_ypt(player: dict[str, Any]) -> float:
    if player["position"] == "TE":
        return 7.4
    if player["position"] == "RB":
        return 6.5
    return 8.4


def _default_catch(player: dict[str, Any]) -> float:
    if player["position"] == "TE":
        return 0.62
    if player["position"] == "RB":
        return 0.72
    return 0.64


def _opponent_name(
    team: str,
    team_draws: dict[str, dict[str, np.ndarray]],
) -> str | None:
    for name in team_draws:
        if name != team:
            return name
    return None


def _seed(players: list[dict[str, Any]], seed: int | None) -> int:
    if seed is not None:
        return int(seed)
    teams = sorted({player["team"] for player in players})
    text = "|".join(teams)
    return sum(ord(char) for char in text) % 100000


def _pct_label(value: float) -> str:
    number = int(value) if float(value).is_integer() else value
    return f"{number}th percentile"


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
