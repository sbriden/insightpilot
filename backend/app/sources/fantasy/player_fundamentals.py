"""
Domain 1 — Player fundamentals.

Builds a season-grained player foundation from nflverse joined
to canonical dim_player. player_id is always InsightPilot-owned.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from app.canonical.dim_player import (
    get_dim_player,
    player_id_lookup_from_dim,
)
from app.canonical.ids import (
    make_player_id,
    player_resolution_key,
)


UNIVERSAL_ID_COLUMN = "player_id"
GSIS_ID_COLUMN = "gsis_id"

FANTASY_ID_COLUMNS = [
    "sleeper_id",
    "espn_id",
    "yahoo_id",
    "fantasypros_id",
    "mfl_id",
    "rotowire_id",
    "pfr_id",
]


def _to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    raise TypeError("Expected a pandas or polars DataFrame.")


def _normalize_id(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .replace({"": pd.NA})
    )


def _as_of_date(season: int, current_season: int) -> date:
    if season >= current_season:
        return date.today()
    # Approximate end of regular season for historical age.
    return date(season, 12, 31)


def _compute_age(
    birth_dates: pd.Series,
    *,
    season: int,
    current_season: int,
) -> pd.Series:
    as_of = _as_of_date(season, current_season)
    parsed = pd.to_datetime(birth_dates, errors="coerce")
    age_days = (pd.Timestamp(as_of) - parsed).dt.days
    return (age_days / 365.25).round(1)


def _rookie_veteran_status(
    years_exp: pd.Series,
    rookie_year: pd.Series,
    season: int,
) -> pd.Series:
    years = pd.to_numeric(years_exp, errors="coerce")
    rookie = pd.to_numeric(rookie_year, errors="coerce")
    is_rookie = (years.fillna(-1) <= 0) | (rookie == season)
    return is_rookie.map(
        {True: "rookie", False: "veteran"}
    ).astype("string")


def _active_status(status: pd.Series) -> pd.Series:
    normalized = (
        status.astype("string")
        .str.upper()
        .str.strip()
    )
    return normalized.map(
        lambda value: (
            "active"
            if value == "ACT"
            else "inactive"
            if pd.notna(value)
            else pd.NA
        )
    ).astype("string")


def _latest_by_week(
    df: pd.DataFrame,
    *,
    keys: list[str],
    week_col: str = "week",
) -> pd.DataFrame:
    if df.empty:
        return df
    working = df.copy()
    working[week_col] = pd.to_numeric(
        working[week_col],
        errors="coerce",
    )
    working = working.sort_values(
        keys + [week_col],
        ascending=True,
    )
    return working.drop_duplicates(
        subset=keys,
        keep="last",
    )


def _load_raw_frames(
    seasons: list[int],
) -> dict[str, pd.DataFrame]:
    import nflreadpy as nfl

    return {
        "rosters": _to_pandas(
            nfl.load_rosters(seasons=seasons)
        ),
        "players": _to_pandas(nfl.load_players()),
        "depth_charts": _to_pandas(
            nfl.load_depth_charts(seasons=seasons)
        ),
        "injuries": _to_pandas(
            nfl.load_injuries(seasons=seasons)
        ),
        "ff_playerids": _to_pandas(
            nfl.load_ff_playerids()
        ),
    }


def _prepare_rosters(rosters: pd.DataFrame) -> pd.DataFrame:
    if rosters.empty:
        return pd.DataFrame()

    frame = rosters.copy()
    frame[GSIS_ID_COLUMN] = _normalize_id(
        frame[GSIS_ID_COLUMN]
    )
    frame = frame[frame[GSIS_ID_COLUMN].notna()].copy()

    if "week" in frame.columns:
        frame = _latest_by_week(
            frame,
            keys=["season", GSIS_ID_COLUMN],
        )
    else:
        frame = frame.drop_duplicates(
            subset=["season", GSIS_ID_COLUMN],
            keep="last",
        )

    keep = [
        "season",
        GSIS_ID_COLUMN,
        "full_name",
        "first_name",
        "last_name",
        "football_name",
        "team",
        "position",
        "depth_chart_position",
        "status",
        "years_exp",
        "height",
        "weight",
        "birth_date",
        "rookie_year",
        "entry_year",
        "college",
        "jersey_number",
        "headshot_url",
    ]
    present = [col for col in keep if col in frame.columns]
    return frame[present].reset_index(drop=True)


def _prepare_players(players: pd.DataFrame) -> pd.DataFrame:
    if players.empty:
        return pd.DataFrame(columns=[GSIS_ID_COLUMN])

    frame = players.copy()
    frame[GSIS_ID_COLUMN] = _normalize_id(
        frame[GSIS_ID_COLUMN]
    )
    frame = frame[frame[GSIS_ID_COLUMN].notna()].copy()
    frame = frame.drop_duplicates(
        subset=[GSIS_ID_COLUMN],
        keep="last",
    )

    rename = {
        "display_name": "player_display_name",
        "latest_team": "latest_team",
        "years_of_experience": "career_years_of_experience",
        "status": "career_status",
        "rookie_season": "players_rookie_season",
        "height": "players_height",
        "weight": "players_weight",
        "birth_date": "players_birth_date",
        "position": "players_position",
    }
    keep = [GSIS_ID_COLUMN] + [
        col for col in rename if col in frame.columns
    ]
    frame = frame[keep].rename(columns=rename)
    return frame


def _prepare_depth(depth: pd.DataFrame) -> pd.DataFrame:
    if depth.empty:
        return pd.DataFrame(
            columns=[
                "season",
                GSIS_ID_COLUMN,
                "depth_chart_slot",
                "depth_chart_rank",
                "depth_chart_formation",
            ]
        )

    frame = depth.copy()
    frame[GSIS_ID_COLUMN] = _normalize_id(
        frame[GSIS_ID_COLUMN]
    )
    frame = frame[frame[GSIS_ID_COLUMN].notna()].copy()
    frame = _latest_by_week(
        frame,
        keys=["season", GSIS_ID_COLUMN],
    )
    frame = frame.rename(
        columns={
            "depth_position": "depth_chart_slot",
            "depth_team": "depth_chart_rank",
            "formation": "depth_chart_formation",
            "club_code": "depth_chart_team",
        }
    )
    keep = [
        "season",
        GSIS_ID_COLUMN,
        "depth_chart_slot",
        "depth_chart_rank",
        "depth_chart_formation",
        "depth_chart_team",
    ]
    present = [col for col in keep if col in frame.columns]
    return frame[present]


def _prepare_injuries(injuries: pd.DataFrame) -> pd.DataFrame:
    if injuries.empty:
        return pd.DataFrame(
            columns=[
                "season",
                GSIS_ID_COLUMN,
                "injury_status",
                "injury_primary",
                "injury_week",
            ]
        )

    frame = injuries.copy()
    frame[GSIS_ID_COLUMN] = _normalize_id(
        frame[GSIS_ID_COLUMN]
    )
    frame = frame[frame[GSIS_ID_COLUMN].notna()].copy()
    frame = _latest_by_week(
        frame,
        keys=["season", GSIS_ID_COLUMN],
    )
    frame = frame.rename(
        columns={
            "report_status": "injury_status",
            "report_primary_injury": "injury_primary",
            "week": "injury_week",
        }
    )
    keep = [
        "season",
        GSIS_ID_COLUMN,
        "injury_status",
        "injury_primary",
        "injury_week",
    ]
    present = [col for col in keep if col in frame.columns]
    return frame[present]


def _prepare_ff_ids(ff_ids: pd.DataFrame) -> pd.DataFrame:
    if ff_ids.empty:
        return pd.DataFrame(columns=[GSIS_ID_COLUMN])

    frame = ff_ids.copy()
    frame[GSIS_ID_COLUMN] = _normalize_id(
        frame[GSIS_ID_COLUMN]
    )
    frame = frame[frame[GSIS_ID_COLUMN].notna()].copy()
    frame = frame.drop_duplicates(
        subset=[GSIS_ID_COLUMN],
        keep="last",
    )

    keep = [GSIS_ID_COLUMN] + [
        col for col in FANTASY_ID_COLUMNS if col in frame.columns
    ]
    return frame[keep]


def _build_team_history(
    rosters: pd.DataFrame,
) -> pd.DataFrame:
    if rosters.empty:
        return pd.DataFrame(
            columns=[
                GSIS_ID_COLUMN,
                "career_teams",
                "team_season_history",
                "seasons_played",
            ]
        )

    working = rosters[
        [GSIS_ID_COLUMN, "season", "team"]
    ].dropna(
        subset=[GSIS_ID_COLUMN, "team"]
    ).copy()
    working["season"] = pd.to_numeric(
        working["season"],
        errors="coerce",
    ).astype("Int64")
    working = working.dropna(subset=["season"])
    working = working.drop_duplicates(
        subset=[GSIS_ID_COLUMN, "season", "team"]
    )
    working = working.sort_values(
        [GSIS_ID_COLUMN, "season", "team"]
    )
    working["team_season"] = (
        working["season"].astype(str)
        + ":"
        + working["team"].astype(str)
    )

    grouped = working.groupby(GSIS_ID_COLUMN, as_index=False).agg(
        career_teams=(
            "team",
            lambda values: ", ".join(
                dict.fromkeys(
                    str(value) for value in values if pd.notna(value)
                )
            ),
        ),
        team_season_history=(
            "team_season",
            lambda values: ", ".join(
                str(value) for value in values if pd.notna(value)
            ),
        ),
        seasons_played=("season", "nunique"),
    )
    return grouped


def build_player_fundamentals(
    seasons: list[int],
    *,
    current_season: int | None = None,
    history_seasons: list[int] | None = None,
    player_id_lookup: dict[str, str] | None = None,
    persist_dim_player: bool = True,
) -> pd.DataFrame:
    """
    Return one row per InsightPilot player_id per season.

    Joins nflverse rosters, players, depth charts, injuries,
    and fantasy player IDs, then attaches canonical player_id
    from dim_player.
    """

    if not seasons:
        raise ValueError("At least one season is required.")

    import nflreadpy as nfl

    resolved_current = (
        int(current_season)
        if current_season is not None
        else int(nfl.get_current_season())
    )

    history = sorted(
        set(seasons).union(history_seasons or [])
    )
    raw = _load_raw_frames(history)

    rosters = _prepare_rosters(raw["rosters"])
    if rosters.empty:
        raise ValueError(
            "No roster rows available for the selected seasons."
        )

    season_rosters = rosters[
        rosters["season"].isin(seasons)
    ].copy()
    if season_rosters.empty:
        raise ValueError(
            "No roster rows available for the selected seasons."
        )

    players = _prepare_players(raw["players"])
    depth = _prepare_depth(raw["depth_charts"])
    injuries = _prepare_injuries(raw["injuries"])
    ff_ids = _prepare_ff_ids(raw["ff_playerids"])
    team_history = _build_team_history(rosters)

    frame = season_rosters.merge(
        players,
        on=GSIS_ID_COLUMN,
        how="left",
    )
    frame = frame.merge(
        depth,
        on=["season", GSIS_ID_COLUMN],
        how="left",
    )
    frame = frame.merge(
        injuries,
        on=["season", GSIS_ID_COLUMN],
        how="left",
    )
    frame = frame.merge(
        ff_ids,
        on=GSIS_ID_COLUMN,
        how="left",
    )
    frame = frame.merge(
        team_history,
        on=GSIS_ID_COLUMN,
        how="left",
    )

    # Prefer roster identity fields; fill gaps from players table.
    frame["player_name"] = frame["full_name"].fillna(
        frame.get("player_display_name")
    )
    if "players_birth_date" in frame.columns:
        frame["birth_date"] = frame["birth_date"].fillna(
            frame["players_birth_date"]
        )
    if "players_height" in frame.columns:
        frame["height"] = frame["height"].fillna(
            frame["players_height"]
        )
    if "players_weight" in frame.columns:
        frame["weight"] = frame["weight"].fillna(
            frame["players_weight"]
        )
    if "players_position" in frame.columns:
        frame["position"] = frame["position"].fillna(
            frame["players_position"]
        )
    if "players_rookie_season" in frame.columns:
        frame["rookie_year"] = frame["rookie_year"].fillna(
            frame["players_rookie_season"]
        )
    if "career_years_of_experience" in frame.columns:
        frame["years_exp"] = frame["years_exp"].fillna(
            frame["career_years_of_experience"]
        )

    # Mint/join InsightPilot-owned player_id. Never use gsis_id
    # (or any external ID) as the primary key.
    if player_id_lookup is None:
        dim = get_dim_player(
            force_refresh=False,
            persist=persist_dim_player,
        )
        lookup = player_id_lookup_from_dim(dim)
    else:
        lookup = player_id_lookup

    def _resolve_player_id(gsis_value):
        gsis_text = (
            str(gsis_value).strip()
            if pd.notna(gsis_value)
            else ""
        )
        if gsis_text and gsis_text in lookup:
            return lookup[gsis_text]
        if not gsis_text:
            return pd.NA
        try:
            key = player_resolution_key(gsis_id=gsis_text)
            return make_player_id(key)
        except ValueError:
            return pd.NA

    frame[UNIVERSAL_ID_COLUMN] = frame[GSIS_ID_COLUMN].map(
        _resolve_player_id
    )
    frame["experience_years"] = pd.to_numeric(
        frame["years_exp"],
        errors="coerce",
    )

    ages = []
    for season_value, birth_value in zip(
        frame["season"],
        frame["birth_date"],
    ):
        ages.append(
            _compute_age(
                pd.Series([birth_value]),
                season=int(season_value),
                current_season=resolved_current,
            ).iloc[0]
        )
    frame["age"] = ages

    rookie_years = frame["rookie_year"] if "rookie_year" in frame.columns else pd.Series(
        [pd.NA] * len(frame)
    )
    frame["rookie_veteran_status"] = [
        (
            "rookie"
            if (
                (pd.notna(years) and float(years) <= 0)
                or (
                    pd.notna(rookie)
                    and int(rookie) == int(season_value)
                )
            )
            else "veteran"
        )
        for years, rookie, season_value in zip(
            frame["experience_years"],
            rookie_years,
            frame["season"],
        )
    ]
    frame["active_status"] = _active_status(
        frame["status"]
    )
    frame["roster_status"] = frame["status"]
    frame["depth_chart_position"] = frame[
        "depth_chart_slot"
    ].fillna(
        frame["depth_chart_position"]
    )

    ordered = [
        UNIVERSAL_ID_COLUMN,
        GSIS_ID_COLUMN,
        *FANTASY_ID_COLUMNS,
        "season",
        "player_name",
        "first_name",
        "last_name",
        "position",
        "team",
        "age",
        "birth_date",
        "experience_years",
        "rookie_year",
        "rookie_veteran_status",
        "height",
        "weight",
        "jersey_number",
        "depth_chart_position",
        "depth_chart_rank",
        "depth_chart_formation",
        "roster_status",
        "active_status",
        "injury_status",
        "injury_primary",
        "injury_week",
        "career_teams",
        "team_season_history",
        "seasons_played",
        "college",
        "headshot_url",
    ]
    present = [col for col in ordered if col in frame.columns]
    extras = [
        col for col in frame.columns if col not in present
    ]
    result = frame[present + extras].copy()
    result = result.sort_values(
        ["season", "team", "position", "player_name"],
        kind="mergesort",
    ).reset_index(drop=True)
    return result
