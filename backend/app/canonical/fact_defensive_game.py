"""
fact_defensive_game — team×game defensive performance.

Canonical defensive fact, kept separate from offensive
fact_team_game. Grain: defensive_team × game.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.dim_game import (
    game_id_lookup_from_dim,
    get_dim_game,
)
from app.canonical.ids import (
    game_resolution_key,
    make_game_id,
    make_team_id,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_FACT_DEFENSIVE_GAME_CACHE: pd.DataFrame | None = None
_FACT_DEFENSIVE_GAME_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_DEFENSIVE_GAME_CACHE_SEASONS: tuple[int, ...] | None = None

FACT_DEFENSIVE_GAME_COLUMNS = [
    "defensive_team_id",
    "opponent_team_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "points_allowed",
    "yards_allowed",
    "pass_yards_allowed",
    "rush_yards_allowed",
    "pass_epa_allowed",
    "rush_epa_allowed",
    "pressure_rate",
    "sack_rate",
    "targets_allowed",
    "receptions_allowed",
    "receiving_yards_allowed",
    "source_ids",
]


def _to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    raise TypeError("Expected a pandas or polars DataFrame.")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _normalize_text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text_value = str(value).strip()
    if not text_value or text_value.lower() in {
        "nan",
        "none",
        "nat",
        "<na>",
    }:
        return None
    return text_value


def _sql_null_if_missing(value: Any) -> Any:
    if _is_missing(value):
        return None
    return value


def _normalize_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _season_type(value: Any) -> str | None:
    raw = _normalize_text(value)
    if raw is None:
        return None
    return raw.upper()


def _safe_div(
    numerator: Any,
    denominator: Any,
) -> float | None:
    num = _normalize_float(numerator)
    den = _normalize_float(denominator)
    if num is None or den is None or den == 0:
        return None
    return num / den


def _load_pbp(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_pbp(seasons=seasons))


def _load_schedules(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_schedules(seasons=seasons))


def _points_allowed_by_team_game(
    schedules: pd.DataFrame,
) -> pd.DataFrame:
    """
    Points allowed = opponent's score from the schedule.
    """

    if schedules.empty:
        return pd.DataFrame(
            columns=[
                "nflverse_game_id",
                "defensive_team",
                "opponent_team",
                "points_allowed",
                "season",
                "week",
                "season_type",
            ]
        )

    rows: list[dict[str, Any]] = []
    for record in schedules.to_dict(orient="records"):
        game_id = _normalize_text(record.get("game_id"))
        if not game_id:
            continue
        season = _normalize_int(record.get("season"))
        week = _normalize_int(record.get("week"))
        season_type = _season_type(
            record.get("game_type") or record.get("season_type")
        )
        home = (
            _normalize_text(record.get("home_team")) or ""
        ).upper()
        away = (
            _normalize_text(record.get("away_team")) or ""
        ).upper()
        home_score = _normalize_int(record.get("home_score"))
        away_score = _normalize_int(record.get("away_score"))

        if home and away:
            rows.append(
                {
                    "nflverse_game_id": game_id,
                    "defensive_team": home,
                    "opponent_team": away,
                    "points_allowed": away_score,
                    "season": season,
                    "week": week,
                    "season_type": season_type,
                }
            )
            rows.append(
                {
                    "nflverse_game_id": game_id,
                    "defensive_team": away,
                    "opponent_team": home,
                    "points_allowed": home_score,
                    "season": season,
                    "week": week,
                    "season_type": season_type,
                }
            )
    return pd.DataFrame.from_records(rows)


def _aggregate_defensive_game_from_pbp(
    pbp: pd.DataFrame,
) -> pd.DataFrame:
    if pbp.empty:
        return pd.DataFrame()

    plays = pbp.copy()
    plays["game_id"] = plays["game_id"].map(_normalize_text)
    plays["defteam"] = (
        plays["defteam"].map(_normalize_text).str.upper()
    )
    plays["posteam"] = (
        plays["posteam"].map(_normalize_text).str.upper()
    )

    for column in (
        "pass",
        "rush",
        "epa",
        "yards_gained",
        "passing_yards",
        "rushing_yards",
        "receiving_yards",
        "sack",
        "qb_hit",
        "qb_dropback",
        "complete_pass",
        "pass_attempt",
        "season",
        "week",
    ):
        if column in plays.columns:
            plays[column] = pd.to_numeric(
                plays[column],
                errors="coerce",
            )

    defense = plays[
        plays["defteam"].notna()
        & plays["posteam"].notna()
        & (
            (plays.get("pass", 0) == 1)
            | (plays.get("rush", 0) == 1)
        )
    ].copy()
    if defense.empty:
        return pd.DataFrame()

    defense["is_pass"] = defense.get("pass", 0) == 1
    defense["is_rush"] = defense.get("rush", 0) == 1
    defense["is_sack"] = defense.get("sack", 0) == 1
    defense["is_pressure"] = (
        (defense.get("sack", 0) == 1)
        | (defense.get("qb_hit", 0) == 1)
    )
    defense["is_target"] = defense["is_pass"]
    if "receiver_player_id" in defense.columns:
        defense["is_target"] = defense["is_pass"] & defense[
            "receiver_player_id"
        ].notna()
    defense["is_reception"] = defense["is_target"] & (
        defense.get("complete_pass", 0) == 1
    )

    # Prefer dedicated yard columns; fall back to yards_gained.
    if "passing_yards" in defense.columns:
        defense["pass_yards"] = defense["passing_yards"].where(
            defense["is_pass"],
            0,
        ).fillna(0)
    else:
        defense["pass_yards"] = defense["yards_gained"].where(
            defense["is_pass"],
            0,
        ).fillna(0)

    if "rushing_yards" in defense.columns:
        defense["rush_yards"] = defense["rushing_yards"].where(
            defense["is_rush"],
            0,
        ).fillna(0)
    else:
        defense["rush_yards"] = defense["yards_gained"].where(
            defense["is_rush"],
            0,
        ).fillna(0)

    if "receiving_yards" in defense.columns:
        defense["rec_yards"] = defense["receiving_yards"].where(
            defense["is_reception"],
            0,
        ).fillna(0)
    else:
        defense["rec_yards"] = defense["yards_gained"].where(
            defense["is_reception"],
            0,
        ).fillna(0)

    group_keys = ["defteam", "game_id"]

    totals = (
        defense.groupby(group_keys, dropna=True)
        .agg(
            opponent_team=("posteam", "first"),
            yards_allowed=("yards_gained", "sum"),
            pass_yards_allowed=("pass_yards", "sum"),
            rush_yards_allowed=("rush_yards", "sum"),
            pass_attempts_faced=("is_pass", "sum"),
            pressures=("is_pressure", "sum"),
            sacks=("is_sack", "sum"),
            targets_allowed=("is_target", "sum"),
            receptions_allowed=("is_reception", "sum"),
            receiving_yards_allowed=("rec_yards", "sum"),
        )
        .reset_index()
    )

    meta_cols = [
        column
        for column in ("season", "week", "season_type")
        if column in defense.columns
    ]
    if meta_cols:
        meta = (
            defense.groupby(group_keys, dropna=True)[meta_cols]
            .first()
            .reset_index()
        )
        totals = totals.merge(meta, on=group_keys, how="left")

    pass_epa = (
        defense.loc[defense["is_pass"]]
        .groupby(group_keys, dropna=True)["epa"]
        .sum()
        .reset_index(name="pass_epa_allowed")
    )
    rush_epa = (
        defense.loc[defense["is_rush"]]
        .groupby(group_keys, dropna=True)["epa"]
        .sum()
        .reset_index(name="rush_epa_allowed")
    )
    totals = totals.merge(
        pass_epa,
        on=group_keys,
        how="left",
    ).merge(
        rush_epa,
        on=group_keys,
        how="left",
    )

    totals["pressure_rate"] = [
        _safe_div(pressures, pass_attempts)
        for pressures, pass_attempts in zip(
            totals["pressures"],
            totals["pass_attempts_faced"],
        )
    ]
    totals["sack_rate"] = [
        _safe_div(sacks, pass_attempts)
        for sacks, pass_attempts in zip(
            totals["sacks"],
            totals["pass_attempts_faced"],
        )
    ]

    totals = totals.rename(
        columns={
            "defteam": "defensive_team",
            "game_id": "nflverse_game_id",
        }
    )
    return totals


def build_fact_defensive_game(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
    game_id_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved_seasons = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    pbp = raw.get("pbp")
    if pbp is None:
        pbp = _load_pbp(resolved_seasons)
    else:
        pbp = pbp.copy()

    schedules = raw.get("schedules")
    if schedules is None:
        if source_frames is None:
            schedules = _load_schedules(resolved_seasons)
        else:
            schedules = pd.DataFrame()
    else:
        schedules = schedules.copy()

    if pbp.empty:
        raise ValueError(
            "Unable to build fact_defensive_game: no "
            "play-by-play rows were available."
        )

    if game_id_lookup is None:
        dim_game = get_dim_game(
            seasons=resolved_seasons,
            force_refresh=False,
            persist=persist,
        )
        game_lookup = game_id_lookup_from_dim(dim_game)
    else:
        game_lookup = game_id_lookup

    aggregated = _aggregate_defensive_game_from_pbp(pbp)
    if aggregated.empty:
        raise ValueError(
            "Unable to build fact_defensive_game: no defensive "
            "plays were available."
        )

    points = _points_allowed_by_team_game(schedules)
    if not points.empty:
        aggregated = aggregated.merge(
            points,
            on=["nflverse_game_id", "defensive_team"],
            how="left",
            suffixes=("", "_sched"),
        )
        if "opponent_team_sched" in aggregated.columns:
            aggregated["opponent_team"] = aggregated[
                "opponent_team_sched"
            ].combine_first(aggregated["opponent_team"])
            aggregated = aggregated.drop(
                columns=["opponent_team_sched"]
            )
        for column in ("season", "week", "season_type"):
            sched_col = f"{column}_sched"
            if sched_col not in aggregated.columns:
                continue
            if column not in aggregated.columns:
                aggregated[column] = aggregated[sched_col]
            else:
                aggregated[column] = aggregated[
                    sched_col
                ].combine_first(aggregated[column])
            aggregated = aggregated.drop(columns=[sched_col])
    else:
        aggregated["points_allowed"] = None

    records: list[dict[str, Any]] = []
    for row in aggregated.to_dict(orient="records"):
        defensive_abbr = (
            _normalize_text(row.get("defensive_team")) or ""
        ).upper() or None
        opponent_abbr = (
            _normalize_text(row.get("opponent_team")) or ""
        ).upper() or None
        nflverse_game_id = _normalize_text(
            row.get("nflverse_game_id")
        )
        if not defensive_abbr or not nflverse_game_id:
            continue

        game_id = game_lookup.get(nflverse_game_id)
        if game_id is None:
            try:
                game_id = make_game_id(
                    game_resolution_key(
                        nflverse_game_id=nflverse_game_id,
                    )
                )
            except ValueError:
                continue

        season_type = row.get("season_type")
        if isinstance(season_type, str):
            season_type = season_type.upper()
        else:
            season_type = _season_type(season_type)

        records.append(
            {
                "defensive_team_id": make_team_id(
                    defensive_abbr
                ),
                "opponent_team_id": (
                    make_team_id(opponent_abbr)
                    if opponent_abbr
                    else None
                ),
                "game_id": game_id,
                "season": _normalize_int(row.get("season")),
                "week": _normalize_int(row.get("week")),
                "season_type": season_type,
                "points_allowed": _normalize_int(
                    row.get("points_allowed")
                ),
                "yards_allowed": _normalize_float(
                    row.get("yards_allowed")
                ),
                "pass_yards_allowed": _normalize_float(
                    row.get("pass_yards_allowed")
                ),
                "rush_yards_allowed": _normalize_float(
                    row.get("rush_yards_allowed")
                ),
                "pass_epa_allowed": _normalize_float(
                    row.get("pass_epa_allowed")
                ),
                "rush_epa_allowed": _normalize_float(
                    row.get("rush_epa_allowed")
                ),
                "pressure_rate": _normalize_float(
                    row.get("pressure_rate")
                ),
                "sack_rate": _normalize_float(
                    row.get("sack_rate")
                ),
                "targets_allowed": _normalize_int(
                    row.get("targets_allowed")
                ),
                "receptions_allowed": _normalize_int(
                    row.get("receptions_allowed")
                ),
                "receiving_yards_allowed": _normalize_float(
                    row.get("receiving_yards_allowed")
                ),
                "source_ids": {
                    "defensive_team_abbreviation": (
                        defensive_abbr
                    ),
                    "opponent_team_abbreviation": (
                        opponent_abbr
                    ),
                    "nflverse_game_id": nflverse_game_id,
                },
                "resolution_key": (
                    f"{defensive_abbr}:{nflverse_game_id}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build fact_defensive_game: no resolvable "
            "defensive team×game rows."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_DEFENSIVE_GAME_COLUMNS + [
        "resolution_key"
    ]:
        if column == "source_ids" or column not in fact.columns:
            continue
        fact[column] = fact[column].astype("object")
        fact[column] = fact[column].where(
            fact[column].notna(),
            None,
        )

    fact = fact.drop_duplicates(
        subset=["defensive_team_id", "game_id"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_DEFENSIVE_GAME_CACHE
    global _FACT_DEFENSIVE_GAME_CACHE_WITH_KEYS
    global _FACT_DEFENSIVE_GAME_CACHE_SEASONS
    _FACT_DEFENSIVE_GAME_CACHE_WITH_KEYS = fact.copy()
    _FACT_DEFENSIVE_GAME_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_defensive_game(fact)

    output = fact[FACT_DEFENSIVE_GAME_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        [
            "season",
            "week",
            "defensive_team_id",
            "game_id",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_DEFENSIVE_GAME_CACHE = output.copy()
    return output


def fact_defensive_game_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_defensive_game"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_defensive_game(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_DEFENSIVE_GAME_CACHE
    global _FACT_DEFENSIVE_GAME_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_DEFENSIVE_GAME_CACHE is not None
        and not _FACT_DEFENSIVE_GAME_CACHE.empty
        and _FACT_DEFENSIVE_GAME_CACHE_SEASONS
        == tuple(resolved)
    ):
        return _FACT_DEFENSIVE_GAME_CACHE.copy()

    if not force_refresh and fact_defensive_game_count() > 0:
        frame = load_fact_defensive_game_from_db(
            seasons=resolved,
        )
        if not frame.empty:
            _FACT_DEFENSIVE_GAME_CACHE = frame.copy()
            _FACT_DEFENSIVE_GAME_CACHE_SEASONS = tuple(
                resolved
            )
            return frame

    return build_fact_defensive_game(
        resolved,
        persist=persist,
    )


def upsert_fact_defensive_game(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_defensive_game (
            defensive_team_id,
            opponent_team_id,
            game_id,
            season,
            week,
            season_type,
            points_allowed,
            yards_allowed,
            pass_yards_allowed,
            rush_yards_allowed,
            pass_epa_allowed,
            rush_epa_allowed,
            pressure_rate,
            sack_rate,
            targets_allowed,
            receptions_allowed,
            receiving_yards_allowed,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :defensive_team_id,
            :opponent_team_id,
            :game_id,
            :season,
            :week,
            :season_type,
            :points_allowed,
            :yards_allowed,
            :pass_yards_allowed,
            :rush_yards_allowed,
            :pass_epa_allowed,
            :rush_epa_allowed,
            :pressure_rate,
            :sack_rate,
            :targets_allowed,
            :receptions_allowed,
            :receiving_yards_allowed,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            defensive_team_id = EXCLUDED.defensive_team_id,
            opponent_team_id = EXCLUDED.opponent_team_id,
            game_id = EXCLUDED.game_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            points_allowed = EXCLUDED.points_allowed,
            yards_allowed = EXCLUDED.yards_allowed,
            pass_yards_allowed = EXCLUDED.pass_yards_allowed,
            rush_yards_allowed = EXCLUDED.rush_yards_allowed,
            pass_epa_allowed = EXCLUDED.pass_epa_allowed,
            rush_epa_allowed = EXCLUDED.rush_epa_allowed,
            pressure_rate = EXCLUDED.pressure_rate,
            sack_rate = EXCLUDED.sack_rate,
            targets_allowed = EXCLUDED.targets_allowed,
            receptions_allowed = EXCLUDED.receptions_allowed,
            receiving_yards_allowed = EXCLUDED.receiving_yards_allowed,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in fact.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(
                source_ids,
                sort_keys=True,
            )
        row = {
            "defensive_team_id": record["defensive_team_id"],
            "game_id": record["game_id"],
            "resolution_key": record["resolution_key"],
            "source_ids": source_ids,
        }
        for column in FACT_DEFENSIVE_GAME_COLUMNS:
            if column in {
                "defensive_team_id",
                "game_id",
                "source_ids",
            }:
                continue
            row[column] = _sql_null_if_missing(
                record.get(column)
            )
        rows.append(row)

    batch_size = 500
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def load_fact_defensive_game_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_DEFENSIVE_GAME_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_defensive_game
        ORDER BY season, week, defensive_team_id, game_id
    """

    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(query),
            connection,
        )

    if seasons and not frame.empty and "season" in frame.columns:
        allowed = {int(season) for season in seasons}
        frame = frame[
            frame["season"].map(
                lambda value: (
                    int(value) in allowed
                    if not _is_missing(value)
                    else False
                )
            )
        ].reset_index(drop=True)

    if "source_ids" in frame.columns:
        frame["source_ids"] = frame["source_ids"].map(
            lambda value: (
                json.dumps(value, sort_keys=True)
                if isinstance(value, dict)
                else value
            )
        )
    return frame
