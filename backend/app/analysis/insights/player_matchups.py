"""
Player Matchups tab — schedule difficulty and opponent context.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.analysis.insights.player_performance import (
    _position_group,
)
from app.analysis.insights.player_snapshot import (
    _num,
    build_team_defense_tab_payload,
)
from app.analysis.insights.player_stats import (
    _fantasy_points_sql,
    _normalize_scoring,
)
from app.canonical.analytics.common import (
    normalize_float,
    weighted_mean,
)
from app.canonical.analytics.player_matchup import (
    _epa_allowed_score,
    _opponent_team_id,
    _pressure_ease_score,
    _prior_defensive_averages,
    _rate_allowed_score,
    _yards_allowed_score,
)


VIEW_OPTIONS: dict[str, int | None] = {
    "next_4": 4,
    "next_6": 6,
    "next_8": 8,
    "rest_of_season": None,
    "full_season": None,
}

PLAYOFF_WEEKS = (15, 16, 17)
REG_WEEKS = tuple(range(1, 19))

DIFFICULTY_LEVELS = (
    "very_favorable",
    "favorable",
    "neutral",
    "difficult",
    "very_difficult",
)


def _normalize_view(view: str | None) -> str:
    value = str(view or "next_8").strip().lower()
    if value in VIEW_OPTIONS:
        return value
    if value in {"ros", "remaining"}:
        return "rest_of_season"
    if value in {"season", "full", "all"}:
        return "full_season"
    return "next_8"


def _difficulty_from_score(score: float | None) -> str:
    if score is None:
        return "neutral"
    value = float(score)
    if value >= 70:
        return "very_favorable"
    if value >= 58:
        return "favorable"
    if value >= 45:
        return "neutral"
    if value >= 35:
        return "difficult"
    return "very_difficult"


def _difficulty_from_positional(
    *,
    pct_vs_avg: float | None,
    rank: int | None,
    rank_of: int | None,
) -> tuple[str, float | None]:
    """
    Fallback difficulty + synthetic 0–100 score from FPTS allowed.
    """

    if pct_vs_avg is not None:
        score = max(1.0, min(99.0, 50.0 + float(pct_vs_avg)))
        return _difficulty_from_score(score), round(score, 1)
    if rank is not None and rank_of:
        # Rank 1 = most FPTS allowed = easiest matchup.
        percentile = float(rank) / float(rank_of)
        score = max(1.0, min(99.0, (1.0 - percentile) * 100.0))
        return _difficulty_from_score(score), round(score, 1)
    return "neutral", None


def _difficulty_label(level: str) -> str:
    return {
        "very_favorable": "Very Favorable",
        "favorable": "Favorable",
        "neutral": "Neutral",
        "difficult": "Difficult",
        "very_difficult": "Very Difficult",
    }.get(level, "Neutral")


def _difficulty_10(score: float | None) -> float | None:
    """Higher = harder schedule (1–10)."""
    if score is None:
        return None
    value = (100.0 - float(score)) / 10.0
    return round(max(1.0, min(10.0, value)), 1)


def _score_matchup_from_priors(
    defense_row: dict[str, Any],
) -> dict[str, float | None]:
    pass_matchup = weighted_mean(
        [
            _epa_allowed_score(
                defense_row.get("prior_pass_epa_allowed")
            ),
            _yards_allowed_score(
                defense_row.get("prior_pass_yards_allowed"),
                scale=0.25,
            ),
            _pressure_ease_score(
                defense_row.get("prior_pressure_rate")
            ),
            _pressure_ease_score(
                defense_row.get("prior_sack_rate")
            ),
        ],
        weights=[0.35, 0.25, 0.2, 0.2],
    )
    rush_matchup = weighted_mean(
        [
            _epa_allowed_score(
                defense_row.get("prior_rush_epa_allowed")
            ),
            _yards_allowed_score(
                defense_row.get("prior_rush_yards_allowed"),
                scale=0.4,
            ),
        ],
        weights=[0.55, 0.45],
    )
    targets = normalize_float(
        defense_row.get("prior_targets_allowed")
    )
    receiving_matchup = weighted_mean(
        [
            _yards_allowed_score(
                defense_row.get("prior_receiving_yards_allowed"),
                scale=0.3,
            ),
            _rate_allowed_score(
                None
                if targets is None
                else min(1.0, float(targets) / 40.0)
            ),
            _epa_allowed_score(
                defense_row.get("prior_pass_epa_allowed")
            ),
        ],
        weights=[0.4, 0.3, 0.3],
    )
    overall = weighted_mean(
        [pass_matchup, rush_matchup, receiving_matchup],
        weights=[0.3, 0.3, 0.4],
    )
    return {
        "matchup_score": overall,
        "pass_matchup_score": pass_matchup,
        "rush_matchup_score": rush_matchup,
        "receiving_matchup_score": receiving_matchup,
    }


def _position_relevant_score(
    scores: dict[str, float | None],
    position_group: str,
) -> float | None:
    if position_group == "QB":
        return scores.get("pass_matchup_score") or scores.get(
            "matchup_score"
        )
    if position_group == "RB":
        rush = scores.get("rush_matchup_score")
        recv = scores.get("receiving_matchup_score")
        if rush is None and recv is None:
            return scores.get("matchup_score")
        return weighted_mean(
            [rush, recv],
            weights=[0.65, 0.35],
        )
    if position_group in {"WR", "TE"}:
        return scores.get("receiving_matchup_score") or scores.get(
            "matchup_score"
        )
    return scores.get("matchup_score")


def _latest_defense_priors(
    defense: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    if defense is None or defense.empty:
        return {}
    priors = _prior_defensive_averages(defense)
    if priors.empty:
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for row in priors.to_dict(orient="records"):
        team_id = str(row.get("defensive_team_id") or "").strip()
        if not team_id:
            continue
        try:
            week = int(row.get("week") or 0)
            season = int(row.get("season") or 0)
        except (TypeError, ValueError):
            continue
        current = latest.get(team_id)
        if current is None:
            latest[team_id] = row
            continue
        try:
            cur_season = int(current.get("season") or 0)
            cur_week = int(current.get("week") or 0)
        except (TypeError, ValueError):
            latest[team_id] = row
            continue
        if (season, week) >= (cur_season, cur_week):
            latest[team_id] = row
    return latest


def _positional_defense_profile(
    *,
    season: int,
    position_group: str,
    scoring: str,
) -> dict[str, dict[str, Any]]:
    """
    Per-defense season stats vs a position group.

    Returns team_id -> {fpts_allowed_avg, rank, pct_vs_avg, ...}
    """

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return {}

    points_sql = _fantasy_points_sql(scoring, alias="g")
    position_filter = position_group
    if position_group == "RB":
        position_sql = "UPPER(COALESCE(p.position, '')) IN ('RB', 'FB', 'HB')"
        params: dict[str, Any] = {"season": int(season)}
    else:
        position_sql = "UPPER(COALESCE(p.position, '')) = :position"
        params = {
            "season": int(season),
            "position": position_filter,
        }

    sql = f"""
        WITH game_points AS (
          SELECT
            CASE
              WHEN g.team_id = dg.home_team_id THEN dg.away_team_id
              WHEN g.team_id = dg.away_team_id THEN dg.home_team_id
              ELSE NULL
            END AS defense_team_id,
            ({points_sql}) AS fantasy_points,
            g.rush_yards,
            g.rush_attempts,
            g.rush_tds,
            g.targets,
            g.receptions,
            g.receiving_yards,
            g.receiving_tds,
            g.pass_yards,
            g.pass_tds,
            g.pass_attempts
          FROM {FANTASY_SCHEMA}.fact_player_game g
          INNER JOIN {FANTASY_SCHEMA}.dim_player p
            ON p.player_id = g.player_id
          INNER JOIN {FANTASY_SCHEMA}.dim_game dg
            ON dg.game_id = g.game_id
          WHERE g.season = :season
            AND {position_sql}
        )
        SELECT
          defense_team_id,
          AVG(fantasy_points) AS fpts_allowed_avg,
          AVG(rush_yards) AS rush_yards_avg,
          AVG(rush_attempts) AS rush_attempts_avg,
          AVG(rush_tds) AS rush_tds_avg,
          AVG(targets) AS targets_avg,
          AVG(receptions) AS receptions_avg,
          AVG(receiving_yards) AS receiving_yards_avg,
          AVG(receiving_tds) AS receiving_tds_avg,
          AVG(pass_yards) AS pass_yards_avg,
          AVG(pass_tds) AS pass_tds_avg,
          AVG(pass_attempts) AS pass_attempts_avg,
          COUNT(*) AS sample_games
        FROM game_points
        WHERE defense_team_id IS NOT NULL
        GROUP BY defense_team_id
    """
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(sql),
                connection,
                params=params,
            )
    except Exception:
        return {}

    if frame.empty:
        return {}

    league_avg = _num(frame["fpts_allowed_avg"].mean())
    ranked = frame.sort_values(
        "fpts_allowed_avg",
        ascending=False,
    ).reset_index(drop=True)
    # Rank 1 = most FPTS allowed (easiest for offense).
    ranked["rank"] = ranked.index + 1
    total = len(ranked)

    profiles: dict[str, dict[str, Any]] = {}
    for record in ranked.to_dict(orient="records"):
        team_id = str(record.get("defense_team_id") or "").strip()
        if not team_id:
            continue
        fpts = _num(record.get("fpts_allowed_avg"))
        pct_vs_avg = None
        if fpts is not None and league_avg not in (None, 0):
            pct_vs_avg = round(
                ((float(fpts) - float(league_avg)) / float(league_avg))
                * 100.0,
                1,
            )
        rush_att = _num(record.get("rush_attempts_avg"))
        rush_yds = _num(record.get("rush_yards_avg"))
        ypc = None
        if rush_att not in (None, 0) and rush_yds is not None:
            ypc = round(float(rush_yds) / float(rush_att), 2)
        profiles[team_id] = {
            "fpts_allowed_avg": (
                round(float(fpts), 1) if fpts is not None else None
            ),
            "rank": int(record["rank"]),
            "rank_of": total,
            "pct_vs_avg": pct_vs_avg,
            "rush_yards_avg": _num(record.get("rush_yards_avg")),
            "rush_tds_avg": _num(record.get("rush_tds_avg")),
            "yards_per_carry": ypc,
            "targets_avg": _num(record.get("targets_avg")),
            "receptions_avg": _num(record.get("receptions_avg")),
            "receiving_yards_avg": _num(
                record.get("receiving_yards_avg")
            ),
            "receiving_tds_avg": _num(record.get("receiving_tds_avg")),
            "pass_yards_avg": _num(record.get("pass_yards_avg")),
            "pass_tds_avg": _num(record.get("pass_tds_avg")),
            "pass_attempts_avg": _num(record.get("pass_attempts_avg")),
            "sample_games": int(record.get("sample_games") or 0),
        }
    return profiles


def _matchup_factors(
    scores: dict[str, float | None],
    position_group: str,
) -> list[dict[str, Any]]:
    mapping: list[tuple[str, str, str]] = []
    if position_group == "QB":
        mapping = [
            ("pass", "Passing", "pass_matchup_score"),
            ("rush", "QB Rushing", "rush_matchup_score"),
            ("overall", "Overall", "matchup_score"),
        ]
    elif position_group == "RB":
        mapping = [
            ("rush", "Rushing Efficiency", "rush_matchup_score"),
            (
                "receiving",
                "Receiving Opportunity",
                "receiving_matchup_score",
            ),
            ("overall", "Overall", "matchup_score"),
        ]
    else:
        mapping = [
            (
                "receiving",
                "Receiving Opportunity",
                "receiving_matchup_score",
            ),
            ("pass", "Pass Defense", "pass_matchup_score"),
            ("overall", "Overall", "matchup_score"),
        ]

    factors: list[dict[str, Any]] = []
    for key, label, score_key in mapping:
        score = scores.get(score_key)
        level = _difficulty_from_score(score)
        factors.append(
            {
                "key": key,
                "label": label,
                "score": (
                    round(float(score), 1) if score is not None else None
                ),
                "difficulty": level,
                "difficulty_label": _difficulty_label(level),
            }
        )
    return factors


def _build_signals(
    upcoming: list[dict[str, Any]],
    *,
    recent_avg: float | None,
    upcoming_avg: float | None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    if not upcoming:
        return signals

    levels = [
        row.get("difficulty")
        for row in upcoming
        if not row.get("is_bye")
    ]
    fav = sum(
        1
        for level in levels
        if level in {"favorable", "very_favorable"}
    )
    tough = sum(
        1
        for level in levels
        if level in {"difficult", "very_difficult"}
    )
    neutral = sum(1 for level in levels if level == "neutral")

    if fav >= 3 and fav > tough:
        signals.append(
            {
                "signal_type": "FAVORABLE_WINDOW",
                "category": "schedule",
                "direction": "favorable",
                "headline": "Favorable Window",
                "body": (
                    f"{fav} of the next {len(levels)} opponents "
                    "project as favorable matchups."
                ),
                "confidence": "high" if fav >= 4 else "moderate",
            }
        )
    if tough >= 3 and tough > fav:
        signals.append(
            {
                "signal_type": "DIFFICULT_STRETCH",
                "category": "schedule",
                "direction": "difficult",
                "headline": "Difficult Stretch",
                "body": (
                    f"{tough} of the next {len(levels)} opponents "
                    "project as above-average defenses."
                ),
                "confidence": "high" if tough >= 4 else "moderate",
            }
        )

    if (
        recent_avg is not None
        and upcoming_avg is not None
        and len(levels) >= 3
    ):
        delta = float(upcoming_avg) - float(recent_avg)
        if delta >= 6:
            signals.append(
                {
                    "signal_type": "IMPROVING_SCHEDULE",
                    "category": "schedule",
                    "direction": "favorable",
                    "headline": "Schedule Improvement",
                    "body": (
                        "Upcoming opponents are materially easier "
                        "than those faced recently."
                    ),
                    "confidence": "moderate",
                }
            )
        elif delta <= -6:
            signals.append(
                {
                    "signal_type": "DETERIORATING_SCHEDULE",
                    "category": "schedule",
                    "direction": "difficult",
                    "headline": "Schedule Deterioration",
                    "body": (
                        "Matchup difficulty increases relative to "
                        "recent competition."
                    ),
                    "confidence": "moderate",
                }
            )

    if fav and tough and abs(fav - tough) <= 1 and len(levels) >= 4:
        signals.append(
            {
                "signal_type": "MIXED_SCHEDULE",
                "category": "schedule",
                "direction": "neutral",
                "headline": "Mixed Schedule",
                "body": (
                    "Favorable and difficult matchups are "
                    "interleaved over the selected window."
                ),
                "confidence": "moderate",
            }
        )

    if not signals and levels:
        signals.append(
            {
                "signal_type": "CONSISTENT_MATCHUP",
                "category": "schedule",
                "direction": "neutral",
                "headline": "Consistent Matchup Profile",
                "body": (
                    "Upcoming opponents have relatively similar "
                    "defensive profiles."
                ),
                "confidence": "low" if len(levels) < 4 else "moderate",
            }
        )

    return signals[:4]


def _outlook_copy(
    upcoming: list[dict[str, Any]],
) -> dict[str, Any]:
    active = [row for row in upcoming if not row.get("is_bye")]
    fav = sum(
        1
        for row in active
        if row.get("difficulty") in {"favorable", "very_favorable"}
    )
    tough = sum(
        1
        for row in active
        if row.get("difficulty") in {"difficult", "very_difficult"}
    )
    neutral = len(active) - fav - tough
    if fav > tough and fav >= 2:
        headline = "Favorable Upcoming Window"
        body = (
            f"{fav} of the next {len(active)} opponents rank as "
            f"favorable for this position. "
        )
    elif tough > fav and tough >= 2:
        headline = "Difficult Upcoming Stretch"
        body = (
            f"{tough} of the next {len(active)} opponents project "
            f"as difficult matchups. "
        )
    else:
        headline = "Balanced Upcoming Schedule"
        body = (
            "Upcoming opponents are mixed between favorable, "
            "neutral, and difficult matchups. "
        )

    best = None
    worst = None
    for row in active:
        score = _num(row.get("matchup_score"))
        if score is None:
            continue
        if best is None or score > _num(best.get("matchup_score")):
            best = row
        if worst is None or score < _num(worst.get("matchup_score")):
            worst = row
    if best and best.get("week") is not None:
        body += (
            f"The strongest opportunity is Week {best['week']}"
            f" ({best.get('opponent') or 'TBD'}). "
        )
    if (
        worst
        and best
        and worst.get("week") != best.get("week")
        and worst.get("week") is not None
    ):
        body += (
            f"Week {worst['week']} presents a tougher "
            f"defensive profile."
        )

    overall = "neutral"
    if fav > tough:
        overall = "favorable"
    elif tough > fav:
        overall = "difficult"

    return {
        "headline": headline,
        "body": body.strip(),
        "overall": overall,
        "overall_label": _difficulty_label(
            "favorable"
            if overall == "favorable"
            else "difficult"
            if overall == "difficult"
            else "neutral"
        ),
        "favorable_count": fav,
        "neutral_count": max(0, neutral),
        "difficult_count": tough,
    }


def build_player_matchups(
    player_id: str,
    *,
    season: int | None = None,
    view: str | None = "next_8",
    scoring: str | None = "ppr",
) -> dict[str, Any] | None:
    """
    Matchups-tab MVP payload for one player.
    """

    pid = str(player_id or "").strip()
    if not pid:
        return None

    defense_payload = build_team_defense_tab_payload(
        pid,
        season=season,
        tab="matchups",
    )
    if defense_payload is not None:
        return defense_payload

    scoring_key = _normalize_scoring(scoring)
    view_key = _normalize_view(view)

    try:
        import nflreadpy as nfl
        from sqlalchemy import text

        from app.canonical.dim_game import get_dim_game
        from app.canonical.dim_team import get_dim_team
        from app.canonical.fact_defensive_game import (
            get_fact_defensive_game,
        )
        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
        from app.canonical.analytics.persist import load_rows
        from app.canonical.analytics.player_matchup import (
            PLAYER_MATCHUP_COLUMNS,
        )
    except Exception:
        return None

    identity: dict[str, Any] = {}
    available_seasons: list[int] = []
    try:
        with engine.connect() as connection:
            identity_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      p.player_id,
                      p.name,
                      p.position,
                      p.current_team_id,
                      t.team_abbreviation AS team
                    FROM {FANTASY_SCHEMA}.dim_player p
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team t
                      ON t.team_id = p.current_team_id
                    WHERE p.player_id = :player_id
                    LIMIT 1
                    """
                ),
                connection,
                params={"player_id": pid},
            )
            if identity_frame.empty:
                return None
            identity = identity_frame.to_dict(orient="records")[0]
            seasons_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT DISTINCT season
                    FROM {FANTASY_SCHEMA}.dim_game
                    WHERE season IS NOT NULL
                    ORDER BY season DESC
                    """
                ),
                connection,
            )
            available_seasons = [
                int(value)
                for value in seasons_frame["season"].tolist()
                if value is not None
            ]
    except Exception:
        return None

    if season is None:
        try:
            season = int(nfl.get_current_season())
        except Exception:
            season = (
                available_seasons[0] if available_seasons else None
            )
    if season is None:
        return None

    team_id = str(identity.get("current_team_id") or "").strip()
    team_abbr = identity.get("team")
    position = identity.get("position")
    position_group = _position_group(position)

    if not team_id:
        return {
            "player_id": pid,
            "name": identity.get("name"),
            "position": position,
            "position_group": position_group,
            "team": team_abbr,
            "season": int(season),
            "view": view_key,
            "scoring": scoring_key,
            "available_seasons": available_seasons,
            "empty_message": (
                "Upcoming matchup data unavailable. "
                "This player is not currently assigned to a team."
            ),
            "data_note": None,
        }

    try:
        games = get_dim_game(
            [int(season)],
            force_refresh=False,
            persist=False,
        )
        defense = get_fact_defensive_game(
            [int(season)],
            force_refresh=False,
            persist=False,
        )
        teams = get_dim_team(force_refresh=False, persist=False)
        stored_matchups = load_rows(
            "player_matchup",
            PLAYER_MATCHUP_COLUMNS,
            seasons=[int(season)],
            player_id=pid,
            order_by="season, week",
        )
    except Exception:
        games = None
        defense = None
        teams = None
        stored_matchups = None

    if games is None or games.empty:
        return {
            "player_id": pid,
            "name": identity.get("name"),
            "position": position,
            "position_group": position_group,
            "team": team_abbr,
            "season": int(season),
            "view": view_key,
            "scoring": scoring_key,
            "available_seasons": available_seasons,
            "empty_message": (
                "Upcoming matchup data unavailable. "
                "InsightPilot doesn't currently have schedule "
                "information for this season."
            ),
            "data_note": None,
        }

    team_abbr_lookup: dict[str, str] = {}
    team_name_lookup: dict[str, str] = {}
    if teams is not None and not teams.empty:
        for row in teams.to_dict(orient="records"):
            tid = str(row.get("team_id") or "").strip()
            if not tid:
                continue
            abbr = row.get("team_abbreviation")
            name = row.get("team_name") or row.get("full_name")
            if abbr:
                team_abbr_lookup[tid] = str(abbr)
            if name:
                team_name_lookup[tid] = str(name)

    season_games = games[
        (games["season"] == int(season))
        & (games["season_type"].fillna("REG").astype(str).str.upper() == "REG")
    ].copy()

    team_games = season_games[
        (season_games["home_team_id"] == team_id)
        | (season_games["away_team_id"] == team_id)
    ].copy()

    by_week: dict[int, dict[str, Any]] = {}
    for row in team_games.to_dict(orient="records"):
        try:
            week = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        home_id = str(row.get("home_team_id") or "").strip()
        away_id = str(row.get("away_team_id") or "").strip()
        if team_id == home_id:
            opponent_id = away_id
            home_away = "vs"
        else:
            opponent_id = home_id
            home_away = "@"
        status_raw = str(row.get("game_status") or "").strip()
        home_score = row.get("home_score")
        away_score = row.get("away_score")
        try:
            scores_present = (
                home_score is not None
                and away_score is not None
                and not pd.isna(home_score)
                and not pd.isna(away_score)
            )
        except (TypeError, ValueError):
            scores_present = False
        played = status_raw.lower() == "final" or scores_present
        by_week[week] = {
            "week": week,
            "game_id": row.get("game_id"),
            "game_date": (
                str(row.get("game_date"))[:10]
                if row.get("game_date") is not None
                else None
            ),
            "opponent_team_id": opponent_id,
            "opponent": team_abbr_lookup.get(opponent_id),
            "opponent_name": team_name_lookup.get(opponent_id),
            "home_away": home_away,
            "is_bye": False,
            "status": "played" if played else "upcoming",
        }

    # Infer bye weeks from missing REG weeks that appear elsewhere.
    present_weeks = set(by_week.keys())
    league_weeks = set()
    for value in season_games["week"].dropna().tolist():
        try:
            league_weeks.add(int(value))
        except (TypeError, ValueError):
            continue
    for week in sorted(league_weeks):
        if week not in present_weeks and 1 <= week <= 18:
            by_week[week] = {
                "week": week,
                "game_id": None,
                "game_date": None,
                "opponent_team_id": None,
                "opponent": None,
                "opponent_name": None,
                "home_away": None,
                "is_bye": True,
                "status": "bye",
            }

    stored_lookup: dict[int, dict[str, Any]] = {}
    if stored_matchups is not None and not stored_matchups.empty:
        for row in stored_matchups.to_dict(orient="records"):
            try:
                week = int(row.get("week"))
            except (TypeError, ValueError):
                continue
            stored_lookup[week] = row

    latest_priors = _latest_defense_priors(
        defense if defense is not None else pd.DataFrame()
    )
    positional = _positional_defense_profile(
        season=int(season),
        position_group=position_group,
        scoring=scoring_key,
    )

    # Current week = first upcoming non-bye, else max played + 1.
    upcoming_weeks = [
        week
        for week, row in sorted(by_week.items())
        if row.get("status") == "upcoming" and not row.get("is_bye")
    ]
    played_weeks = [
        week
        for week, row in sorted(by_week.items())
        if row.get("status") == "played"
    ]
    current_week = (
        upcoming_weeks[0]
        if upcoming_weeks
        else (max(played_weeks) + 1 if played_weeks else 1)
    )
    data_through_week = max(played_weeks) if played_weeks else None

    timeline: list[dict[str, Any]] = []
    for week in sorted(by_week.keys()):
        row = dict(by_week[week])
        scores = {
            "matchup_score": None,
            "pass_matchup_score": None,
            "rush_matchup_score": None,
            "receiving_matchup_score": None,
        }
        if row.get("is_bye"):
            row.update(
                {
                    **scores,
                    "position_matchup_score": None,
                    "difficulty": None,
                    "difficulty_label": "Bye",
                    "difficulty_10": None,
                    "opponent_rank": None,
                    "fpts_pct_vs_avg": None,
                    "factors": [],
                    "interpretation": "No game — bye week.",
                }
            )
            timeline.append(row)
            continue

        opponent_id = str(row.get("opponent_team_id") or "").strip()
        if row.get("status") == "played" and week in stored_lookup:
            stored = stored_lookup[week]
            scores = {
                "matchup_score": _num(stored.get("matchup_score")),
                "pass_matchup_score": _num(
                    stored.get("pass_matchup_score")
                ),
                "rush_matchup_score": _num(
                    stored.get("rush_matchup_score")
                ),
                "receiving_matchup_score": _num(
                    stored.get("receiving_matchup_score")
                ),
            }
        elif opponent_id:
            prior_row = latest_priors.get(opponent_id, {})
            scores = _score_matchup_from_priors(prior_row)

        position_score = _position_relevant_score(
            scores,
            position_group,
        )
        profile = positional.get(opponent_id, {})
        rank = profile.get("rank")
        rank_of = profile.get("rank_of")
        pct = profile.get("pct_vs_avg")
        if position_score is None:
            level, position_score = _difficulty_from_positional(
                pct_vs_avg=pct,
                rank=rank,
                rank_of=rank_of,
            )
        else:
            level = _difficulty_from_score(position_score)
        interpretation = None
        if rank is not None and pct is not None:
            interpretation = (
                f"Opponent ranks {rank}"
                f"{_ordinal(rank)} vs {position_group} fantasy points "
                f"({'+' if pct > 0 else ''}{pct}% vs league average)."
            )
        elif level in {"favorable", "very_favorable"}:
            interpretation = "Elevated matchup based on defensive priors."
        elif level in {"difficult", "very_difficult"}:
            interpretation = (
                "Tougher matchup based on recent defensive performance."
            )
        else:
            interpretation = "Neutral matchup based on available evidence."

        row.update(
            {
                **scores,
                "position_matchup_score": (
                    round(float(position_score), 1)
                    if position_score is not None
                    else None
                ),
                "difficulty": level,
                "difficulty_label": _difficulty_label(level),
                "difficulty_10": _difficulty_10(position_score),
                "opponent_rank": rank,
                "opponent_rank_of": rank_of,
                "fpts_allowed_avg": profile.get("fpts_allowed_avg"),
                "fpts_pct_vs_avg": pct,
                "factors": _matchup_factors(scores, position_group),
                "interpretation": interpretation,
                "opponent_profile": {
                    "team": row.get("opponent"),
                    "team_name": row.get("opponent_name"),
                    **profile,
                }
                if opponent_id
                else None,
            }
        )
        timeline.append(row)

    # Slice upcoming window for outlook.
    future = [
        row
        for row in timeline
        if row.get("status") in {"upcoming", "bye"}
        and int(row.get("week") or 0) >= int(current_week)
    ]
    configured = VIEW_OPTIONS.get(view_key)
    if view_key == "full_season":
        selected = [
            row
            for row in timeline
            if not row.get("is_bye") or row.get("status") == "bye"
        ]
        upcoming_selected = future
    elif view_key == "rest_of_season":
        selected = future
        upcoming_selected = [
            row for row in future if not row.get("is_bye")
        ]
    else:
        limit = int(configured or 8)
        upcoming_selected = []
        for row in future:
            if row.get("is_bye"):
                continue
            upcoming_selected.append(row)
            if len(upcoming_selected) >= limit:
                break
        # Include byes that fall inside the selected week span.
        if upcoming_selected:
            max_week = max(
                int(row["week"]) for row in upcoming_selected
            )
            selected = [
                row
                for row in future
                if int(row.get("week") or 0) <= max_week
            ]
        else:
            selected = []

    recent_played = [
        row
        for row in timeline
        if row.get("status") == "played" and not row.get("is_bye")
    ][-4:]
    recent_scores = [
        _num(row.get("position_matchup_score"))
        for row in recent_played
        if _num(row.get("position_matchup_score")) is not None
    ]
    upcoming_scores = [
        _num(row.get("position_matchup_score"))
        for row in upcoming_selected
        if _num(row.get("position_matchup_score")) is not None
    ]
    recent_avg = (
        round(sum(recent_scores) / len(recent_scores), 1)
        if recent_scores
        else None
    )
    upcoming_avg = (
        round(sum(upcoming_scores) / len(upcoming_scores), 1)
        if upcoming_scores
        else None
    )

    next_matchup = next(
        (
            row
            for row in future
            if not row.get("is_bye")
        ),
        None,
    )
    outlook = _outlook_copy(upcoming_selected)
    signals = _build_signals(
        upcoming_selected,
        recent_avg=recent_avg,
        upcoming_avg=upcoming_avg,
    )

    schedule_difficulty = _difficulty_10(upcoming_avg)
    schedule_level = _difficulty_from_score(upcoming_avg)

    playoff_rows = [
        row
        for row in timeline
        if int(row.get("week") or 0) in PLAYOFF_WEEKS
    ]
    playoff_scores = [
        _num(row.get("position_matchup_score"))
        for row in playoff_rows
        if not row.get("is_bye")
        and _num(row.get("position_matchup_score")) is not None
    ]
    playoff_avg = (
        round(sum(playoff_scores) / len(playoff_scores), 1)
        if playoff_scores
        else None
    )
    playoff_outlook = {
        "weeks": playoff_rows,
        "avg_score": playoff_avg,
        "difficulty": _difficulty_from_score(playoff_avg),
        "difficulty_label": _difficulty_label(
            _difficulty_from_score(playoff_avg)
        ),
        "favorable_count": sum(
            1
            for row in playoff_rows
            if row.get("difficulty")
            in {"favorable", "very_favorable"}
        ),
        "neutral_count": sum(
            1
            for row in playoff_rows
            if row.get("difficulty") == "neutral"
        ),
        "difficult_count": sum(
            1
            for row in playoff_rows
            if row.get("difficulty")
            in {"difficult", "very_difficult"}
        ),
    }

    recent_vs_upcoming = {
        "recent_label": f"Recent {len(recent_played)} Games",
        "upcoming_label": (
            f"Next {len(upcoming_selected)} Games"
            if upcoming_selected
            else "Upcoming"
        ),
        "recent_avg_score": recent_avg,
        "upcoming_avg_score": upcoming_avg,
        "recent_difficulty_10": _difficulty_10(recent_avg),
        "upcoming_difficulty_10": _difficulty_10(upcoming_avg),
        "interpretation": None,
    }
    if recent_avg is not None and upcoming_avg is not None:
        if upcoming_avg - recent_avg >= 6:
            recent_vs_upcoming["interpretation"] = (
                "Schedule becomes more favorable."
            )
        elif recent_avg - upcoming_avg >= 6:
            recent_vs_upcoming["interpretation"] = (
                "Schedule becomes more difficult."
            )
        else:
            recent_vs_upcoming["interpretation"] = (
                "Upcoming difficulty is similar to recent competition."
            )

    empty_message = None
    if not timeline:
        empty_message = (
            "Upcoming matchup data unavailable. "
            "InsightPilot doesn't currently have schedule "
            "information for this player."
        )

    return {
        "player_id": pid,
        "name": identity.get("name"),
        "position": position,
        "position_group": position_group,
        "team": team_abbr,
        "season": int(season),
        "view": view_key,
        "scoring": scoring_key,
        "available_seasons": available_seasons,
        "current_week": current_week,
        "data_through_week": data_through_week,
        "next_matchup": next_matchup,
        "outlook_summary": {
            "schedule_difficulty_10": schedule_difficulty,
            "schedule_difficulty": schedule_level,
            "schedule_difficulty_label": _difficulty_label(
                schedule_level
            ),
            "favorable_count": outlook["favorable_count"],
            "neutral_count": outlook["neutral_count"],
            "difficult_count": outlook["difficult_count"],
            "overall": outlook["overall"],
            "overall_label": outlook["overall_label"],
        },
        "insight_outlook": outlook,
        "signals": signals,
        "upcoming_matchups": selected,
        "timeline": timeline,
        "recent_vs_upcoming": recent_vs_upcoming,
        "playoff_outlook": playoff_outlook,
        "empty_message": empty_message,
        "data_note": (
            "Matchup analysis calculated by InsightPilot"
            + (
                f" · Opponent data through Week {data_through_week}"
                if data_through_week is not None
                else ""
            )
            + ". Difficulty based on positional fantasy production "
            "allowed and defensive priors relative to league average."
        ),
    }


def _ordinal(value: int) -> str:
    value = int(value)
    if 10 <= (value % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
