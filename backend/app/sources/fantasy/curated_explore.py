"""
Curated, denormalized exploration datasets for the Fantasy Football Data tab.

These are user-facing views — not raw canonical tables.
IDs are replaced with names/abbreviations, and related facts
are joined where the grain allows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


PREVIEW_ROW_LIMIT = 250


@dataclass(frozen=True)
class CuratedExploreDataset:
    id: str
    title: str
    description: str
    group: str
    supports_seasons: bool = True


CURATED_EXPLORE_DATASETS: list[CuratedExploreDataset] = [
    CuratedExploreDataset(
        id="curated_fantasy_signals",
        title="Fantasy Signals",
        description=(
            "Breakout, buy/sell, start/sit, and regression "
            "signals with player and team context."
        ),
        group="signals",
    ),
    CuratedExploreDataset(
        id="curated_player_profiles",
        title="Player Fantasy Profiles",
        description=(
            "Weekly proprietary scores — production, "
            "opportunity, efficiency, matchup, and value."
        ),
        group="signals",
    ),
    CuratedExploreDataset(
        id="curated_player_game_logs",
        title="Player Game Logs",
        description=(
            "Game-by-game fantasy production with opponent "
            "and team context."
        ),
        group="performance",
    ),
    CuratedExploreDataset(
        id="curated_player_usage",
        title="Usage & Efficiency",
        description=(
            "Snaps, routes, target/rush shares, and "
            "efficiency rates in one player-game view."
        ),
        group="opportunity",
    ),
    CuratedExploreDataset(
        id="curated_opportunity_trends",
        title="Opportunity Trends",
        description=(
            "Rolling usage shares, opportunity scores, "
            "and efficiency scores by week."
        ),
        group="opportunity",
    ),
    CuratedExploreDataset(
        id="curated_injury_reports",
        title="Injury Reports",
        description=(
            "Practice participation and game status with "
            "player and team names."
        ),
        group="availability",
    ),
    CuratedExploreDataset(
        id="curated_depth_charts",
        title="Depth Charts",
        description=(
            "Weekly depth-chart ranks and roles with "
            "player and team names."
        ),
        group="availability",
    ),
    CuratedExploreDataset(
        id="curated_matchup_outlook",
        title="Matchup Outlook",
        description=(
            "Opponent matchup scores plus game environment "
            "(pace, script, team total)."
        ),
        group="context",
    ),
    CuratedExploreDataset(
        id="curated_team_offense",
        title="Team Offense",
        description=(
            "Team offensive environment by game — pace, "
            "pass rate, EPA, and red-zone efficiency."
        ),
        group="context",
    ),
    CuratedExploreDataset(
        id="curated_defense_allowed",
        title="Defense Allowed",
        description=(
            "What each defense allows to opposing offenses, "
            "with team and opponent names."
        ),
        group="context",
    ),
    CuratedExploreDataset(
        id="curated_market",
        title="Market Snapshot",
        description=(
            "Ranks, projections, ADP, and ownership with "
            "player and team context."
        ),
        group="context",
    ),
    CuratedExploreDataset(
        id="curated_game_lines",
        title="Betting Lines",
        description=(
            "Spreads, totals, and implied scores for each "
            "matchup."
        ),
        group="context",
    ),
    CuratedExploreDataset(
        id="curated_players",
        title="Players",
        description=(
            "Active fantasy roster with position, team, "
            "and status."
        ),
        group="reference",
        supports_seasons=False,
    ),
    CuratedExploreDataset(
        id="curated_schedule",
        title="Schedule",
        description=(
            "NFL schedule with home/away teams and scores."
        ),
        group="reference",
        supports_seasons=False,
    ),
]


def get_curated_dataset(dataset_id: str) -> CuratedExploreDataset | None:
    for item in CURATED_EXPLORE_DATASETS:
        if item.id == dataset_id:
            return item
    return None


def is_curated_explore_id(dataset_id: str) -> bool:
    return get_curated_dataset(dataset_id) is not None


def _season_clause(
    seasons: list[int] | None,
    *,
    column: str = "season",
) -> tuple[str, dict[str, Any]]:
    if not seasons:
        return "", {}
    params: dict[str, Any] = {}
    placeholders: list[str] = []
    for index, season in enumerate(seasons):
        key = f"season_{index}"
        params[key] = int(season)
        placeholders.append(f":{key}")
    return f"AND {column} IN ({', '.join(placeholders)})", params


def _read_sql(
    sql: str,
    params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    with engine.connect() as connection:
        return pd.read_sql_query(
            text(sql),
            connection,
            params=params or {},
        )


def _opponent_expr(
    *,
    team_alias: str = "f",
    game_alias: str = "g",
    home_alias: str = "home_t",
    away_alias: str = "away_t",
) -> str:
    return f"""
        CASE
          WHEN {game_alias}.home_team_id = {team_alias}.team_id
            THEN {away_alias}.team_abbreviation
          WHEN {game_alias}.away_team_id = {team_alias}.team_id
            THEN {home_alias}.team_abbreviation
          ELSE NULL
        END
    """


def _load_fantasy_signals(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="s.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          t.team_abbreviation AS team,
          s.season,
          s.week,
          s.signal_type,
          s.signal_strength,
          s.direction,
          s.confidence
        FROM {FANTASY_SCHEMA}.fantasy_signal s
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = s.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = p.current_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY s.season DESC, s.week DESC, s.signal_strength DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


def _load_player_profiles(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="pf.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          t.team_abbreviation AS team,
          pf.season,
          pf.week,
          pf.production_score,
          pf.opportunity_score,
          pf.efficiency_score,
          pf.trend_score,
          pf.matchup_score,
          pf.environment_score,
          pf.risk_score,
          pf.fantasy_value_score
        FROM {FANTASY_SCHEMA}.player_fantasy_profile pf
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = pf.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = p.current_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY pf.season DESC, pf.week DESC, pf.fantasy_value_score DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


def _load_player_game_logs(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="f.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    opponent = _opponent_expr()
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          team.team_abbreviation AS team,
          {opponent} AS opponent,
          f.season,
          f.week,
          f.season_type,
          f.pass_completions,
          f.pass_attempts,
          f.pass_yards,
          f.pass_tds,
          f.interceptions,
          f.rush_attempts,
          f.rush_yards,
          f.rush_tds,
          f.targets,
          f.receptions,
          f.receiving_yards,
          f.receiving_tds
        FROM {FANTASY_SCHEMA}.fact_player_game f
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = f.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team team
          ON team.team_id = f.team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_game g
          ON g.game_id = f.game_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team home_t
          ON home_t.team_id = g.home_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team away_t
          ON away_t.team_id = g.away_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY f.season DESC, f.week DESC, p.name
        LIMIT :limit
        """,
        params,
    )


def _load_player_usage(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="u.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    opponent = _opponent_expr(team_alias="u")
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          COALESCE(u.position, p.position) AS position,
          team.team_abbreviation AS team,
          {opponent} AS opponent,
          u.season,
          u.week,
          u.snap_count,
          u.offensive_snap_share,
          u.routes_run,
          u.route_participation_rate,
          u.touches,
          u.touch_share,
          u.rush_share,
          u.target_share,
          u.air_yards,
          u.red_zone_touches,
          u.red_zone_targets,
          u.dropbacks,
          e.yards_per_carry,
          e.yards_per_target,
          e.yards_per_route_run,
          e.catch_rate,
          e.td_rate,
          e.fantasy_points_per_touch,
          e.fantasy_points_per_route
        FROM {FANTASY_SCHEMA}.fact_player_usage u
        LEFT JOIN {FANTASY_SCHEMA}.fact_player_efficiency e
          ON e.player_id = u.player_id
         AND e.game_id = u.game_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = u.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team team
          ON team.team_id = u.team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_game g
          ON g.game_id = u.game_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team home_t
          ON home_t.team_id = g.home_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team away_t
          ON away_t.team_id = g.away_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY u.season DESC, u.week DESC, p.name
        LIMIT :limit
        """,
        params,
    )


def _load_opportunity_trends(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="tr.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          t.team_abbreviation AS team,
          tr.season,
          tr.week,
          tr.snap_share_3wk,
          tr.target_share_3wk,
          tr.rush_share_3wk,
          tr.route_participation_3wk,
          tr.target_share_change,
          tr.snap_share_change,
          tr.opportunity_trend,
          opp.opportunity_score,
          opp.receiving_opportunity_score,
          opp.rushing_opportunity_score,
          opp.red_zone_opportunity_score,
          eff.efficiency_score,
          eff.receiving_efficiency,
          eff.rushing_efficiency
        FROM {FANTASY_SCHEMA}.player_usage_trend tr
        LEFT JOIN {FANTASY_SCHEMA}.player_opportunity opp
          ON opp.player_id = tr.player_id
         AND opp.season = tr.season
         AND opp.week = tr.week
        LEFT JOIN {FANTASY_SCHEMA}.player_efficiency eff
          ON eff.player_id = tr.player_id
         AND eff.season = tr.season
         AND eff.week = tr.week
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = tr.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = p.current_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY tr.season DESC, tr.week DESC, opp.opportunity_score DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


def _load_injury_reports(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="i.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          t.team_abbreviation AS team,
          i.season,
          i.week,
          i.report_date,
          i.injury_type,
          i.practice_status,
          i.game_status,
          i.is_expected_to_play
        FROM {FANTASY_SCHEMA}.fact_injury i
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = i.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = COALESCE(i.team_id, p.current_team_id)
        WHERE 1 = 1
          {season_sql}
        ORDER BY i.season DESC, i.week DESC, i.report_date DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


def _load_depth_charts(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="d.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          d.position,
          t.team_abbreviation AS team,
          d.season,
          d.week,
          d.depth_order,
          d.role,
          d.effective_date
        FROM {FANTASY_SCHEMA}.fact_depth_chart d
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = d.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = d.team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY d.season DESC, d.week DESC, t.team_abbreviation, d.position, d.depth_order
        LIMIT :limit
        """,
        params,
    )


def _load_matchup_outlook(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="m.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          t.team_abbreviation AS team,
          m.season,
          m.week,
          m.matchup_score,
          m.pass_matchup_score,
          m.rush_matchup_score,
          m.receiving_matchup_score,
          env.game_environment_score,
          env.team_total,
          env.pace_expectation,
          env.game_script_expectation
        FROM {FANTASY_SCHEMA}.player_matchup m
        LEFT JOIN {FANTASY_SCHEMA}.player_environment env
          ON env.player_id = m.player_id
         AND env.season = m.season
         AND env.week = m.week
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = m.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = p.current_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY m.season DESC, m.week DESC, m.matchup_score DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


def _load_team_offense(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="f.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    opponent = _opponent_expr(team_alias="f")
    return _read_sql(
        f"""
        SELECT
          team.team_abbreviation AS team,
          {opponent} AS opponent,
          f.season,
          f.week,
          f.season_type,
          f.offensive_plays,
          f.pass_attempts,
          f.rush_attempts,
          f.pass_rate,
          f.neutral_pass_rate,
          f.pace,
          f.points,
          f.yards,
          f.offensive_epa,
          f.pass_epa,
          f.rush_epa,
          f.red_zone_trips,
          f.red_zone_td_rate,
          f.turnovers
        FROM {FANTASY_SCHEMA}.fact_team_game f
        LEFT JOIN {FANTASY_SCHEMA}.dim_team team
          ON team.team_id = f.team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_game g
          ON g.game_id = f.game_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team home_t
          ON home_t.team_id = g.home_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team away_t
          ON away_t.team_id = g.away_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY f.season DESC, f.week DESC, team.team_abbreviation
        LIMIT :limit
        """,
        params,
    )


def _load_defense_allowed(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="f.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          def_t.team_abbreviation AS defense,
          opp_t.team_abbreviation AS opponent,
          f.season,
          f.week,
          f.season_type,
          f.points_allowed,
          f.yards_allowed,
          f.pass_yards_allowed,
          f.rush_yards_allowed,
          f.pass_epa_allowed,
          f.rush_epa_allowed,
          f.pressure_rate,
          f.sack_rate,
          f.targets_allowed,
          f.receptions_allowed,
          f.receiving_yards_allowed
        FROM {FANTASY_SCHEMA}.fact_defensive_game f
        LEFT JOIN {FANTASY_SCHEMA}.dim_team def_t
          ON def_t.team_id = f.defensive_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team opp_t
          ON opp_t.team_id = f.opponent_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY f.season DESC, f.week DESC, def_t.team_abbreviation
        LIMIT :limit
        """,
        params,
    )


def _load_market(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="m.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          t.team_abbreviation AS team,
          m.season,
          m.week,
          m.source,
          m.rank,
          m.projection,
          m.adp,
          m.ownership
        FROM {FANTASY_SCHEMA}.fact_market m
        LEFT JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = m.player_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = p.current_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY m.season DESC, m.week DESC NULLS LAST, m.rank ASC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


def _load_game_lines(
    seasons: list[int] | None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="m.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          home_t.team_abbreviation AS home_team,
          away_t.team_abbreviation AS away_team,
          m.season,
          m.week,
          m.season_type,
          m.source,
          m.spread,
          m.over_under,
          m.home_implied_total,
          m.away_implied_total,
          m.timestamp
        FROM {FANTASY_SCHEMA}.fact_game_market m
        LEFT JOIN {FANTASY_SCHEMA}.dim_game g
          ON g.game_id = m.game_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team home_t
          ON home_t.team_id = g.home_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team away_t
          ON away_t.team_id = g.away_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY m.season DESC, m.week DESC, m.timestamp DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


def _load_players(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    del seasons  # roster is not season-scoped
    return _read_sql(
        f"""
        SELECT
          p.name AS player,
          p.position,
          t.team_abbreviation AS team,
          p.status
        FROM {FANTASY_SCHEMA}.dim_player p
        LEFT JOIN {FANTASY_SCHEMA}.dim_team t
          ON t.team_id = p.current_team_id
        WHERE p.position IN ('QB', 'RB', 'WR', 'TE', 'K', 'FB', 'HB')
        ORDER BY t.team_abbreviation NULLS LAST, p.position, p.name
        LIMIT :limit
        """,
        {"limit": PREVIEW_ROW_LIMIT},
    )


def _load_schedule(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    season_sql, params = _season_clause(seasons, column="g.season")
    params["limit"] = PREVIEW_ROW_LIMIT
    return _read_sql(
        f"""
        SELECT
          g.season,
          g.week,
          g.season_type,
          g.game_date,
          away_t.team_abbreviation AS away_team,
          home_t.team_abbreviation AS home_team,
          g.away_score,
          g.home_score,
          g.game_status
        FROM {FANTASY_SCHEMA}.dim_game g
        LEFT JOIN {FANTASY_SCHEMA}.dim_team home_t
          ON home_t.team_id = g.home_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team away_t
          ON away_t.team_id = g.away_team_id
        WHERE 1 = 1
          {season_sql}
        ORDER BY g.season DESC, g.week DESC, g.game_date DESC NULLS LAST
        LIMIT :limit
        """,
        params,
    )


_LOADERS: dict[str, Callable[[list[int] | None], pd.DataFrame]] = {
    "curated_fantasy_signals": _load_fantasy_signals,
    "curated_player_profiles": _load_player_profiles,
    "curated_player_game_logs": _load_player_game_logs,
    "curated_player_usage": _load_player_usage,
    "curated_opportunity_trends": _load_opportunity_trends,
    "curated_injury_reports": _load_injury_reports,
    "curated_depth_charts": _load_depth_charts,
    "curated_matchup_outlook": _load_matchup_outlook,
    "curated_team_offense": _load_team_offense,
    "curated_defense_allowed": _load_defense_allowed,
    "curated_market": _load_market,
    "curated_game_lines": _load_game_lines,
    "curated_players": _load_players,
    "curated_schedule": _load_schedule,
}


def load_curated_explore(
    dataset_id: str,
    seasons: list[int] | None = None,
) -> tuple[pd.DataFrame, CuratedExploreDataset]:
    dataset = get_curated_dataset(dataset_id)
    if dataset is None:
        raise ValueError(f"Unknown curated dataset: {dataset_id}")
    loader = _LOADERS[dataset.id]
    resolved = seasons if dataset.supports_seasons else None
    frame = loader(resolved)
    if frame is None or frame.empty:
        raise ValueError(
            f"No rows available for curated dataset '{dataset.title}'."
        )
    return frame, dataset


def curated_preview_payload(
    dataset_id: str,
    seasons: list[int] | None = None,
) -> dict[str, Any]:
    from app.sources import nflverse as nflverse_source

    frame, dataset = load_curated_explore(dataset_id, seasons)
    sample_rows = nflverse_source.sample_records(frame, limit=100)
    season_label = (
        "all seasons"
        if not seasons
        else (
            str(seasons[0])
            if len(seasons) == 1
            else f"{seasons[0]}-{seasons[-1]}"
        )
    )
    return {
        "source_id": "nflverse",
        "dataset_id": dataset.id,
        "dataset_name": dataset.title,
        "seasons": seasons or [],
        "label": f"{dataset.title} ({season_label})",
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "fields": nflverse_source.dataframe_fields(frame),
        "sample_rows": sample_rows,
        "sample_row_count": len(sample_rows),
        "pre_mapped": True,
        "prebuilt_mappings": [],
        "notes": (
            "Denormalized exploration view — player/team names "
            "instead of IDs; related sources combined where useful."
        ),
        "curated": True,
    }
