"""
Opponent-adjusted NFL team strength for betting projections.

Replaces raw PPG as the non-market component of projected scores.
Profiles blend recent offensive and defensive efficiency, then
adjust historical production for opponent quality so scoring 28
against a weak defense is not treated like scoring 28 against
an elite defense.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.pricing import num
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


LOOKBACK_GAMES = 6
# Points moved per unit of matchup strength (offense − opp defense).
POINTS_PER_MATCHUP_UNIT = 3.75
# Pace impact on each side's expected points.
PACE_POINTS_PER_SD = 0.85
DEFAULT_LEAGUE_AVG_PPG = 22.5

# Composite weights (offense). Higher = more influence.
OFFENSE_WEIGHTS = {
    "pass_efficiency": 0.28,
    "rush_efficiency": 0.16,
    "explosive_rate": 0.14,
    "success_rate": 0.22,
    "red_zone_efficiency": 0.12,
    "turnover_rate": 0.08,  # inverted when scoring
}

# Composite weights (defense). Higher = stronger defense.
DEFENSE_WEIGHTS = {
    "pass_defense": 0.28,
    "rush_defense": 0.18,
    "pressure": 0.16,
    "explosive_allowed": 0.14,  # inverted
    "success_allowed": 0.24,  # inverted
}


def load_team_strength_context(
    *,
    season: int,
    before_week: int | None = None,
    lookback: int = LOOKBACK_GAMES,
) -> dict[str, Any]:
    """
    Build opponent-adjusted team strength profiles for a season.

    ``before_week`` excludes games at/after that week so the slate
    week itself does not leak into projections.
    """

    offense_rows = _load_offense_games(
        season=season,
        before_week=before_week,
    )
    defense_rows = _load_defense_games(
        season=season,
        before_week=before_week,
    )
    if not offense_rows and not defense_rows:
        return {
            "profiles": {},
            "league_avg_ppg": DEFAULT_LEAGUE_AVG_PPG,
            "games_used": 0,
            "lookback": lookback,
            "before_week": before_week,
        }

    offense_by_team = _trim_lookback(
        _group_by_team(offense_rows, "team_id"),
        lookback=lookback,
    )
    defense_by_team = _trim_lookback(
        _group_by_team(defense_rows, "team_id"),
        lookback=lookback,
    )

    # First-pass defensive baselines (raw) for opponent adjustment.
    raw_def_baselines = _team_defense_baselines(defense_by_team)
    raw_off_baselines = _team_offense_baselines(offense_by_team)
    league_def = _league_means(list(raw_def_baselines.values()))
    league_off = _league_means(list(raw_off_baselines.values()))
    league_avg_ppg = float(
        league_off.get("points")
        or league_def.get("points_allowed")
        or DEFAULT_LEAGUE_AVG_PPG
    )

    # Opponent-adjust each game, then re-aggregate.
    adj_offense_by_team: dict[str, list[dict[str, float]]] = {}
    for team_id, games in offense_by_team.items():
        adjusted: list[dict[str, float]] = []
        for game in games:
            opp = str(game.get("opponent_id") or "")
            opp_def = raw_def_baselines.get(opp) or league_def
            adjusted.append(
                _opponent_adjust_offense_game(
                    game,
                    opponent_defense=opp_def,
                    league_defense=league_def,
                    league_avg_ppg=league_avg_ppg,
                )
            )
        if adjusted:
            adj_offense_by_team[team_id] = adjusted

    adj_defense_by_team: dict[str, list[dict[str, float]]] = {}
    for team_id, games in defense_by_team.items():
        adjusted = []
        for game in games:
            opp = str(game.get("opponent_id") or "")
            opp_off = raw_off_baselines.get(opp) or league_off
            adjusted.append(
                _opponent_adjust_defense_game(
                    game,
                    opponent_offense=opp_off,
                    league_offense=league_off,
                    league_avg_ppg=league_avg_ppg,
                )
            )
        if adjusted:
            adj_defense_by_team[team_id] = adjusted

    offense_means = {
        tid: _mean_metrics(games)
        for tid, games in adj_offense_by_team.items()
    }
    defense_means = {
        tid: _mean_metrics(games)
        for tid, games in adj_defense_by_team.items()
    }

    offense_z = _zscore_profiles(
        offense_means,
        keys=[
            "pass_efficiency",
            "rush_efficiency",
            "explosive_rate",
            "success_rate",
            "red_zone_efficiency",
            "turnover_rate",
            "pace",
            "pass_rate",
            "rush_rate",
            "epa_per_play",
            "points_adj",
        ],
    )
    defense_z = _zscore_profiles(
        defense_means,
        keys=[
            "pass_defense_raw",
            "rush_defense_raw",
            "pressure",
            "explosive_allowed_raw",
            "success_allowed_raw",
            "points_allowed_adj",
        ],
    )

    team_ids = sorted(
        set(offense_means) | set(defense_means)
    )
    profiles: dict[str, dict[str, Any]] = {}
    for tid in team_ids:
        off_z = offense_z.get(tid) or {}
        def_z = defense_z.get(tid) or {}
        off_raw = offense_means.get(tid) or {}
        def_raw = defense_means.get(tid) or {}

        # Higher offense metrics are better except turnovers.
        offense_components = {
            "pass_efficiency": off_z.get("pass_efficiency"),
            "rush_efficiency": off_z.get("rush_efficiency"),
            "explosive_rate": off_z.get("explosive_rate"),
            "success_rate": off_z.get("success_rate"),
            "red_zone_efficiency": off_z.get("red_zone_efficiency"),
            "turnover_rate": (
                -float(off_z["turnover_rate"])
                if off_z.get("turnover_rate") is not None
                else None
            ),
        }
        # Defense: convert "allowed" metrics so higher = better D.
        defense_components = {
            "pass_defense": (
                -float(def_z["pass_defense_raw"])
                if def_z.get("pass_defense_raw") is not None
                else None
            ),
            "rush_defense": (
                -float(def_z["rush_defense_raw"])
                if def_z.get("rush_defense_raw") is not None
                else None
            ),
            "pressure": def_z.get("pressure"),
            "explosive_plays_allowed": (
                -float(def_z["explosive_allowed_raw"])
                if def_z.get("explosive_allowed_raw") is not None
                else None
            ),
            "success_rate_allowed": (
                -float(def_z["success_allowed_raw"])
                if def_z.get("success_allowed_raw") is not None
                else None
            ),
        }
        offensive_efficiency = _weighted_mean(
            {
                "pass_efficiency": offense_components["pass_efficiency"],
                "rush_efficiency": offense_components["rush_efficiency"],
                "explosive_rate": offense_components["explosive_rate"],
                "success_rate": offense_components["success_rate"],
                "red_zone_efficiency": offense_components[
                    "red_zone_efficiency"
                ],
                "turnover_rate": offense_components["turnover_rate"],
            },
            OFFENSE_WEIGHTS,
        )
        defensive_efficiency = _weighted_mean(
            {
                "pass_defense": defense_components["pass_defense"],
                "rush_defense": defense_components["rush_defense"],
                "pressure": defense_components["pressure"],
                "explosive_allowed": defense_components[
                    "explosive_plays_allowed"
                ],
                "success_allowed": defense_components[
                    "success_rate_allowed"
                ],
            },
            DEFENSE_WEIGHTS,
        )
        profiles[tid] = {
            "team_id": tid,
            "games": max(
                len(adj_offense_by_team.get(tid) or []),
                len(adj_defense_by_team.get(tid) or []),
            ),
            "offensive_efficiency": _round_or_none(offensive_efficiency),
            "defensive_efficiency": _round_or_none(defensive_efficiency),
            "pace": _round_or_none(off_raw.get("pace")),
            "pace_z": _round_or_none(off_z.get("pace")),
            "explosive_play_rate": _round_or_none(
                offense_components["explosive_rate"]
            ),
            "red_zone_efficiency": _round_or_none(
                offense_components["red_zone_efficiency"]
            ),
            "turnover_rate": _round_or_none(off_raw.get("turnover_rate")),
            "success_rate": _round_or_none(
                offense_components["success_rate"]
            ),
            "epa_per_play": _round_or_none(off_raw.get("epa_per_play")),
            "pass_rate": _round_or_none(off_raw.get("pass_rate")),
            "rush_rate": _round_or_none(off_raw.get("rush_rate")),
            "offense": {
                "pass_efficiency": _round_or_none(
                    offense_components["pass_efficiency"]
                ),
                "rush_efficiency": _round_or_none(
                    offense_components["rush_efficiency"]
                ),
                "explosive_rate": _round_or_none(
                    offense_components["explosive_rate"]
                ),
                "success_rate": _round_or_none(
                    offense_components["success_rate"]
                ),
                "red_zone_efficiency": _round_or_none(
                    offense_components["red_zone_efficiency"]
                ),
            },
            "defense": {
                "pass_defense": _round_or_none(
                    defense_components["pass_defense"]
                ),
                "rush_defense": _round_or_none(
                    defense_components["rush_defense"]
                ),
                "pressure": _round_or_none(defense_components["pressure"]),
                "explosive_plays_allowed": _round_or_none(
                    defense_components["explosive_plays_allowed"]
                ),
                "success_rate_allowed": _round_or_none(
                    defense_components["success_rate_allowed"]
                ),
            },
            "points_per_game_adj": _round_or_none(
                off_raw.get("points_adj")
            ),
            "points_allowed_adj": _round_or_none(
                def_raw.get("points_allowed_adj")
            ),
        }

    return {
        "profiles": profiles,
        "league_avg_ppg": round(league_avg_ppg, 2),
        "games_used": sum(
            len(games) for games in adj_offense_by_team.values()
        ),
        "lookback": lookback,
        "before_week": before_week,
    }


def project_strength_scores(
    *,
    home_team_id: str,
    away_team_id: str,
    context: dict[str, Any] | None,
) -> tuple[float | None, float | None, dict[str, Any]]:
    """
    Translate opponent-adjusted matchup strength into expected points.

    Returns (home_points, away_points, matchup_detail).
    """

    context = context or {}
    profiles = context.get("profiles") or {}
    league_avg = float(
        context.get("league_avg_ppg") or DEFAULT_LEAGUE_AVG_PPG
    )
    home = profiles.get(str(home_team_id) or "")
    away = profiles.get(str(away_team_id) or "")
    if not home or not away:
        return None, None, {"available": False}

    home_off = num(home.get("offensive_efficiency")) or 0.0
    home_def = num(home.get("defensive_efficiency")) or 0.0
    away_off = num(away.get("offensive_efficiency")) or 0.0
    away_def = num(away.get("defensive_efficiency")) or 0.0
    home_pace = num(home.get("pace_z")) or 0.0
    away_pace = num(away.get("pace_z")) or 0.0
    pace_z = (home_pace + away_pace) / 2.0

    # Offense vs opposing defense: positive ⇒ score more than average.
    home_matchup = home_off - away_def
    away_matchup = away_off - home_def

    home_points = (
        league_avg
        + POINTS_PER_MATCHUP_UNIT * home_matchup
        + PACE_POINTS_PER_SD * pace_z
    )
    away_points = (
        league_avg
        + POINTS_PER_MATCHUP_UNIT * away_matchup
        + PACE_POINTS_PER_SD * pace_z
    )
    # Keep projections in a realistic NFL band.
    home_points = max(10.0, min(42.0, home_points))
    away_points = max(10.0, min(42.0, away_points))

    detail = {
        "available": True,
        "league_avg_ppg": league_avg,
        "home_matchup": round(home_matchup, 3),
        "away_matchup": round(away_matchup, 3),
        "pace_z": round(pace_z, 3),
        "home_games": int(home.get("games") or 0),
        "away_games": int(away.get("games") or 0),
        "home_profile": {
            "offensive_efficiency": home.get("offensive_efficiency"),
            "defensive_efficiency": home.get("defensive_efficiency"),
            "pace": home.get("pace"),
            "offense": home.get("offense"),
            "defense": home.get("defense"),
        },
        "away_profile": {
            "offensive_efficiency": away.get("offensive_efficiency"),
            "defensive_efficiency": away.get("defensive_efficiency"),
            "pace": away.get("pace"),
            "offense": away.get("offense"),
            "defense": away.get("defense"),
        },
    }
    return round(home_points, 1), round(away_points, 1), detail


def blend_market_and_strength(
    *,
    market_home: float | None,
    market_away: float | None,
    strength_home: float | None,
    strength_away: float | None,
    confidence: str | None = None,
    policy: dict[str, Any] | None = None,
    strength_detail: dict[str, Any] | None = None,
) -> tuple[float | None, float | None, dict[str, Any]]:
    """
    Market-anchored blend with confidence-dependent model weight.

    Prefer ``apply_market_anchor_blend``; this wrapper keeps the
    team_strength import path stable for callers/tests.
    """

    from app.analysis.insights.betting.projection_blend import (
        apply_market_anchor_blend,
        estimate_projection_confidence,
        load_blend_policy,
    )

    active = policy or load_blend_policy()
    conf = confidence or estimate_projection_confidence(
        strength_detail=strength_detail
        or {
            "available": strength_home is not None
            and strength_away is not None
        },
    )
    return apply_market_anchor_blend(
        market_home=market_home,
        market_away=market_away,
        model_home=strength_home,
        model_away=strength_away,
        confidence=conf,
        policy=active,
    )


def _load_offense_games(
    *,
    season: int,
    before_week: int | None,
) -> list[dict[str, Any]]:
    clauses = ["tg.season = :season", "tg.points IS NOT NULL"]
    params: dict[str, Any] = {"season": int(season)}
    if before_week is not None:
        clauses.append("tg.week < :before_week")
        params["before_week"] = int(before_week)
    where = " AND ".join(clauses)
    sql = f"""
        SELECT
          tg.team_id,
          tg.game_id,
          tg.season,
          tg.week,
          tg.points,
          tg.offensive_plays,
          tg.pass_attempts,
          tg.rush_attempts,
          tg.pass_rate,
          tg.pace,
          tg.yards,
          tg.offensive_epa,
          tg.pass_epa,
          tg.rush_epa,
          tg.red_zone_td_rate,
          tg.turnovers,
          CASE
            WHEN tg.team_id = g.home_team_id THEN g.away_team_id
            ELSE g.home_team_id
          END AS opponent_id
        FROM {FANTASY_SCHEMA}.fact_team_game tg
        JOIN {FANTASY_SCHEMA}.dim_game g
          ON g.game_id = tg.game_id
        WHERE {where}
        ORDER BY tg.team_id, tg.week DESC
    """
    try:
        with engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(text(sql), params).mappings()
            ]
    except Exception:
        return []


def _load_defense_games(
    *,
    season: int,
    before_week: int | None,
) -> list[dict[str, Any]]:
    clauses = [
        "dg.season = :season",
        "dg.points_allowed IS NOT NULL",
    ]
    params: dict[str, Any] = {"season": int(season)}
    if before_week is not None:
        clauses.append("dg.week < :before_week")
        params["before_week"] = int(before_week)
    where = " AND ".join(clauses)
    # Join opponent offense row for plays faced / volume denominators.
    sql = f"""
        SELECT
          dg.defensive_team_id AS team_id,
          dg.opponent_team_id AS opponent_id,
          dg.game_id,
          dg.season,
          dg.week,
          dg.points_allowed,
          dg.yards_allowed,
          dg.pass_yards_allowed,
          dg.rush_yards_allowed,
          dg.pass_epa_allowed,
          dg.rush_epa_allowed,
          dg.pressure_rate,
          dg.sack_rate,
          opp.offensive_plays AS plays_faced,
          opp.pass_attempts AS pass_attempts_faced,
          opp.rush_attempts AS rush_attempts_faced
        FROM {FANTASY_SCHEMA}.fact_defensive_game dg
        LEFT JOIN {FANTASY_SCHEMA}.fact_team_game opp
          ON opp.game_id = dg.game_id
         AND opp.team_id = dg.opponent_team_id
        WHERE {where}
        ORDER BY dg.defensive_team_id, dg.week DESC
    """
    try:
        with engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(text(sql), params).mappings()
            ]
    except Exception:
        return []


def _group_by_team(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tid = str(row.get(key) or "").strip()
        if tid:
            grouped[tid].append(row)
    return grouped


def _trim_lookback(
    grouped: dict[str, list[dict[str, Any]]],
    *,
    lookback: int,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for tid, games in grouped.items():
        # Already ordered week DESC from SQL.
        out[tid] = games[: max(1, int(lookback))]
    return out


def _offense_game_metrics(game: dict[str, Any]) -> dict[str, float]:
    plays = max(float(num(game.get("offensive_plays")) or 0.0), 1.0)
    pass_att = max(float(num(game.get("pass_attempts")) or 0.0), 1.0)
    rush_att = max(float(num(game.get("rush_attempts")) or 0.0), 1.0)
    points = float(num(game.get("points")) or 0.0)
    yards = float(num(game.get("yards")) or 0.0)
    off_epa = float(num(game.get("offensive_epa")) or 0.0)
    pass_epa = float(num(game.get("pass_epa")) or 0.0)
    rush_epa = float(num(game.get("rush_epa")) or 0.0)
    turnovers = float(num(game.get("turnovers")) or 0.0)
    pass_rate = num(game.get("pass_rate"))
    if pass_rate is None:
        pass_rate = float(num(game.get("pass_attempts")) or 0.0) / plays
    rush_rate = 1.0 - float(pass_rate)
    return {
        "points": points,
        "pace": float(num(game.get("pace")) or 0.0),
        "pass_efficiency": pass_epa / pass_att,
        "rush_efficiency": rush_epa / rush_att,
        "explosive_rate": yards / plays,
        "success_rate": off_epa / plays,
        "red_zone_efficiency": float(
            num(game.get("red_zone_td_rate")) or 0.0
        ),
        "turnover_rate": turnovers / plays,
        "epa_per_play": off_epa / plays,
        "pass_rate": float(pass_rate),
        "rush_rate": float(rush_rate),
    }


def _defense_game_metrics(game: dict[str, Any]) -> dict[str, float]:
    plays = max(float(num(game.get("plays_faced")) or 0.0), 1.0)
    pass_att = max(float(num(game.get("pass_attempts_faced")) or 0.0), 1.0)
    rush_att = max(float(num(game.get("rush_attempts_faced")) or 0.0), 1.0)
    points_allowed = float(num(game.get("points_allowed")) or 0.0)
    yards_allowed = float(num(game.get("yards_allowed")) or 0.0)
    pass_epa_allowed = float(num(game.get("pass_epa_allowed")) or 0.0)
    rush_epa_allowed = float(num(game.get("rush_epa_allowed")) or 0.0)
    pressure = float(num(game.get("pressure_rate")) or 0.0)
    if pressure == 0.0:
        pressure = float(num(game.get("sack_rate")) or 0.0)
    return {
        "points_allowed": points_allowed,
        "pass_defense_raw": pass_epa_allowed / pass_att,
        "rush_defense_raw": rush_epa_allowed / rush_att,
        "pressure": pressure,
        "explosive_allowed_raw": yards_allowed / plays,
        "success_allowed_raw": (
            (pass_epa_allowed + rush_epa_allowed) / plays
        ),
    }


def _team_offense_baselines(
    by_team: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for tid, games in by_team.items():
        metrics = [_offense_game_metrics(game) for game in games]
        out[tid] = _mean_metrics(metrics)
    return out


def _team_defense_baselines(
    by_team: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for tid, games in by_team.items():
        metrics = [_defense_game_metrics(game) for game in games]
        out[tid] = _mean_metrics(metrics)
    return out


def _opponent_adjust_offense_game(
    game: dict[str, Any],
    *,
    opponent_defense: dict[str, float],
    league_defense: dict[str, float],
    league_avg_ppg: float,
) -> dict[str, float]:
    raw = _offense_game_metrics(game)
    # Points: inflate/deflate by how tough the defense usually is.
    opp_allowed = float(
        opponent_defense.get("points_allowed") or league_avg_ppg
    )
    league_allowed = float(
        league_defense.get("points_allowed") or league_avg_ppg
    )
    points_adj = raw["points"] - (opp_allowed - league_allowed)

    # Efficiency vs what that defense typically allows.
    pass_adj = raw["pass_efficiency"] - (
        float(opponent_defense.get("pass_defense_raw") or 0.0)
        - float(league_defense.get("pass_defense_raw") or 0.0)
    )
    rush_adj = raw["rush_efficiency"] - (
        float(opponent_defense.get("rush_defense_raw") or 0.0)
        - float(league_defense.get("rush_defense_raw") or 0.0)
    )
    explos_adj = raw["explosive_rate"] - (
        float(opponent_defense.get("explosive_allowed_raw") or 0.0)
        - float(league_defense.get("explosive_allowed_raw") or 0.0)
    )
    success_adj = raw["success_rate"] - (
        float(opponent_defense.get("success_allowed_raw") or 0.0)
        - float(league_defense.get("success_allowed_raw") or 0.0)
    )
    return {
        "points_adj": points_adj,
        "pace": raw["pace"],
        "pass_efficiency": pass_adj,
        "rush_efficiency": rush_adj,
        "explosive_rate": explos_adj,
        "success_rate": success_adj,
        "red_zone_efficiency": raw["red_zone_efficiency"],
        "turnover_rate": raw["turnover_rate"],
        "epa_per_play": success_adj,
        "pass_rate": raw["pass_rate"],
        "rush_rate": raw["rush_rate"],
    }


def _opponent_adjust_defense_game(
    game: dict[str, Any],
    *,
    opponent_offense: dict[str, float],
    league_offense: dict[str, float],
    league_avg_ppg: float,
) -> dict[str, float]:
    raw = _defense_game_metrics(game)
    opp_points = float(
        opponent_offense.get("points") or league_avg_ppg
    )
    league_points = float(
        league_offense.get("points") or league_avg_ppg
    )
    # Allowing 28 to an elite offense is better than allowing 28 to a weak one.
    points_allowed_adj = raw["points_allowed"] - (
        opp_points - league_points
    )
    pass_raw = raw["pass_defense_raw"] - (
        float(opponent_offense.get("pass_efficiency") or 0.0)
        - float(league_offense.get("pass_efficiency") or 0.0)
    )
    rush_raw = raw["rush_defense_raw"] - (
        float(opponent_offense.get("rush_efficiency") or 0.0)
        - float(league_offense.get("rush_efficiency") or 0.0)
    )
    explos_raw = raw["explosive_allowed_raw"] - (
        float(opponent_offense.get("explosive_rate") or 0.0)
        - float(league_offense.get("explosive_rate") or 0.0)
    )
    success_raw = raw["success_allowed_raw"] - (
        float(opponent_offense.get("success_rate") or 0.0)
        - float(league_offense.get("success_rate") or 0.0)
    )
    return {
        "points_allowed_adj": points_allowed_adj,
        "pass_defense_raw": pass_raw,
        "rush_defense_raw": rush_raw,
        "pressure": raw["pressure"],
        "explosive_allowed_raw": explos_raw,
        "success_allowed_raw": success_raw,
    }


def _mean_metrics(
    games: list[dict[str, float]],
) -> dict[str, float]:
    if not games:
        return {}
    keys = sorted({key for game in games for key in game})
    out: dict[str, float] = {}
    for key in keys:
        values = [
            float(game[key])
            for game in games
            if game.get(key) is not None
        ]
        if values:
            out[key] = mean(values)
    return out


def _league_means(
    profiles: list[dict[str, float]],
) -> dict[str, float]:
    return _mean_metrics(profiles)


def _zscore_profiles(
    profiles: dict[str, dict[str, float]],
    *,
    keys: list[str],
) -> dict[str, dict[str, float]]:
    if not profiles:
        return {}
    column_values: dict[str, list[float]] = {
        key: [] for key in keys
    }
    for metrics in profiles.values():
        for key in keys:
            value = metrics.get(key)
            if value is not None:
                column_values[key].append(float(value))
    stats: dict[str, tuple[float, float]] = {}
    for key, values in column_values.items():
        if len(values) < 2:
            stats[key] = (mean(values) if values else 0.0, 1.0)
            continue
        mu = mean(values)
        sigma = pstdev(values)
        stats[key] = (mu, sigma if sigma > 1e-9 else 1.0)

    out: dict[str, dict[str, float]] = {}
    for tid, metrics in profiles.items():
        row: dict[str, float] = {}
        for key in keys:
            value = metrics.get(key)
            if value is None:
                continue
            mu, sigma = stats[key]
            row[key] = (float(value) - mu) / sigma
        out[tid] = row
    return out


def _weighted_mean(
    values: dict[str, float | None],
    weights: dict[str, float],
) -> float | None:
    total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        value = values.get(key)
        if value is None:
            continue
        total += float(value) * float(weight)
        weight_sum += float(weight)
    if weight_sum <= 0:
        return None
    return total / weight_sum


def _round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)
