"""
fact_team_game — team×game offensive environment.

Surrounds player opportunity/production with team context:
script, pace, EPA, red-zone efficiency, turnovers.
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


_FACT_TEAM_GAME_CACHE: pd.DataFrame | None = None
_FACT_TEAM_GAME_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_TEAM_GAME_CACHE_SEASONS: tuple[int, ...] | None = None

FACT_TEAM_GAME_COLUMNS = [
    "team_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "offensive_plays",
    "pass_attempts",
    "rush_attempts",
    "pass_rate",
    "neutral_pass_rate",
    "pace",
    "points",
    "yards",
    "offensive_epa",
    "pass_epa",
    "rush_epa",
    "red_zone_trips",
    "red_zone_td_rate",
    "turnovers",
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


def _points_by_team_game(
    schedules: pd.DataFrame,
) -> pd.DataFrame:
    if schedules.empty:
        return pd.DataFrame(
            columns=[
                "nflverse_game_id",
                "team",
                "points",
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
        home = (_normalize_text(record.get("home_team")) or "").upper()
        away = (_normalize_text(record.get("away_team")) or "").upper()
        home_score = _normalize_int(record.get("home_score"))
        away_score = _normalize_int(record.get("away_score"))
        if home:
            rows.append(
                {
                    "nflverse_game_id": game_id,
                    "team": home,
                    "points": home_score,
                    "season": season,
                    "week": week,
                    "season_type": season_type,
                }
            )
        if away:
            rows.append(
                {
                    "nflverse_game_id": game_id,
                    "team": away,
                    "points": away_score,
                    "season": season,
                    "week": week,
                    "season_type": season_type,
                }
            )
    return pd.DataFrame.from_records(rows)


def _aggregate_team_game_from_pbp(
    pbp: pd.DataFrame,
) -> pd.DataFrame:
    if pbp.empty:
        return pd.DataFrame()

    plays = pbp.copy()
    plays["game_id"] = plays["game_id"].map(_normalize_text)
    plays["posteam"] = (
        plays["posteam"]
        .map(_normalize_text)
        .str.upper()
    )
    for column in (
        "pass",
        "rush",
        "epa",
        "yards_gained",
        "yardline_100",
        "touchdown",
        "interception",
        "fumble_lost",
        "score_differential",
        "qtr",
        "game_seconds_remaining",
        "fixed_drive",
        "season",
        "week",
    ):
        if column in plays.columns:
            plays[column] = pd.to_numeric(
                plays[column],
                errors="coerce",
            )

    offense = plays[
        plays["posteam"].notna()
        & (
            (plays.get("pass", 0) == 1)
            | (plays.get("rush", 0) == 1)
        )
    ].copy()
    if offense.empty:
        return pd.DataFrame()

    offense["is_pass"] = offense.get("pass", 0) == 1
    offense["is_rush"] = offense.get("rush", 0) == 1
    offense["is_neutral"] = (
        offense["score_differential"].abs() <= 7
    ) & (offense["qtr"] <= 3)

    group_keys = ["posteam", "game_id"]

    totals = (
        offense.groupby(group_keys, dropna=True)
        .agg(
            offensive_plays=("posteam", "size"),
            pass_attempts=("is_pass", "sum"),
            rush_attempts=("is_rush", "sum"),
            yards=("yards_gained", "sum"),
            offensive_epa=("epa", "sum"),
            turnovers_int=("interception", "sum"),
            turnovers_fum=("fumble_lost", "sum"),
        )
        .reset_index()
    )

    meta_cols = [
        column
        for column in ("season", "week", "season_type")
        if column in offense.columns
    ]
    if meta_cols:
        meta = (
            offense.groupby(group_keys, dropna=True)[meta_cols]
            .first()
            .reset_index()
        )
        totals = totals.merge(meta, on=group_keys, how="left")

    pass_epa = (
        offense.loc[offense["is_pass"]]
        .groupby(group_keys, dropna=True)["epa"]
        .sum()
        .reset_index(name="pass_epa")
    )
    rush_epa = (
        offense.loc[offense["is_rush"]]
        .groupby(group_keys, dropna=True)["epa"]
        .sum()
        .reset_index(name="rush_epa")
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

    neutral = offense.loc[offense["is_neutral"]]
    if not neutral.empty:
        neutral_rates = (
            neutral.groupby(group_keys, dropna=True)
            .agg(
                neutral_plays=("posteam", "size"),
                neutral_pass_attempts=("is_pass", "sum"),
            )
            .reset_index()
        )
        totals = totals.merge(
            neutral_rates,
            on=group_keys,
            how="left",
        )
    else:
        totals["neutral_plays"] = None
        totals["neutral_pass_attempts"] = None

    # Pace: mean seconds between consecutive offensive plays.
    pace_rows: list[dict[str, Any]] = []
    if "game_seconds_remaining" in offense.columns:
        ordered = offense.sort_values(
            ["game_id", "posteam", "game_seconds_remaining"],
            ascending=[True, True, False],
        )
        for (team, game), group in ordered.groupby(
            group_keys,
            dropna=True,
        ):
            seconds = group["game_seconds_remaining"].dropna()
            if len(seconds) < 2:
                pace_rows.append(
                    {
                        "posteam": team,
                        "game_id": game,
                        "pace": None,
                    }
                )
                continue
            deltas = (
                seconds.values[:-1] - seconds.values[1:]
            )
            positive = [float(value) for value in deltas if value > 0]
            pace_rows.append(
                {
                    "posteam": team,
                    "game_id": game,
                    "pace": (
                        sum(positive) / len(positive)
                        if positive
                        else None
                    ),
                }
            )
    pace = pd.DataFrame(pace_rows)
    if not pace.empty:
        totals = totals.merge(
            pace,
            on=group_keys,
            how="left",
        )
    else:
        totals["pace"] = None

    # Red-zone trips / TD rate by drive.
    if (
        "fixed_drive" in plays.columns
        and "yardline_100" in plays.columns
    ):
        drive_plays = plays[
            plays["posteam"].notna()
            & plays["fixed_drive"].notna()
        ].copy()
        rz_drives = (
            drive_plays.loc[
                drive_plays["yardline_100"] <= 20,
                group_keys + ["fixed_drive"],
            ]
            .drop_duplicates()
        )
        trip_counts = (
            rz_drives.groupby(group_keys, dropna=True)
            .size()
            .reset_index(name="red_zone_trips")
        )

        if "td_team" in drive_plays.columns:
            scoring = drive_plays[
                (drive_plays.get("touchdown", 0) == 1)
                & (
                    drive_plays["td_team"]
                    .map(_normalize_text)
                    .str.upper()
                    == drive_plays["posteam"]
                )
            ][group_keys + ["fixed_drive"]].drop_duplicates()
        else:
            scoring = drive_plays[
                drive_plays.get("touchdown", 0) == 1
            ][group_keys + ["fixed_drive"]].drop_duplicates()

        rz_scores = rz_drives.merge(
            scoring,
            on=group_keys + ["fixed_drive"],
            how="inner",
        )
        rz_td_counts = (
            rz_scores.groupby(group_keys, dropna=True)
            .size()
            .reset_index(name="red_zone_tds")
        )
        totals = totals.merge(
            trip_counts,
            on=group_keys,
            how="left",
        ).merge(
            rz_td_counts,
            on=group_keys,
            how="left",
        )
    else:
        totals["red_zone_trips"] = None
        totals["red_zone_tds"] = None

    totals["turnovers"] = (
        totals["turnovers_int"].fillna(0)
        + totals["turnovers_fum"].fillna(0)
    )
    totals["pass_rate"] = [
        _safe_div(pass_attempts, offensive_plays)
        for pass_attempts, offensive_plays in zip(
            totals["pass_attempts"],
            totals["offensive_plays"],
        )
    ]
    totals["neutral_pass_rate"] = [
        _safe_div(neutral_pass_attempts, neutral_plays)
        for neutral_pass_attempts, neutral_plays in zip(
            totals.get(
                "neutral_pass_attempts",
                [None] * len(totals),
            ),
            totals.get(
                "neutral_plays",
                [None] * len(totals),
            ),
        )
    ]
    totals["red_zone_td_rate"] = [
        _safe_div(red_zone_tds, red_zone_trips)
        for red_zone_tds, red_zone_trips in zip(
            totals.get("red_zone_tds", [None] * len(totals)),
            totals.get(
                "red_zone_trips",
                [None] * len(totals),
            ),
        )
    ]

    totals = totals.rename(
        columns={
            "posteam": "team",
            "game_id": "nflverse_game_id",
        }
    )
    return totals


def build_fact_team_game(
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
            "Unable to build fact_team_game: no play-by-play "
            "rows were available."
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

    aggregated = _aggregate_team_game_from_pbp(pbp)
    if aggregated.empty:
        raise ValueError(
            "Unable to build fact_team_game: no offensive "
            "plays were available."
        )

    points = _points_by_team_game(schedules)
    if not points.empty:
        aggregated = aggregated.merge(
            points[
                [
                    "nflverse_game_id",
                    "team",
                    "points",
                    "season",
                    "week",
                    "season_type",
                ]
            ],
            on=["nflverse_game_id", "team"],
            how="left",
            suffixes=("", "_sched"),
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
        aggregated["points"] = None

    records: list[dict[str, Any]] = []
    for row in aggregated.to_dict(orient="records"):
        team_abbr = (
            _normalize_text(row.get("team")) or ""
        ).upper() or None
        nflverse_game_id = _normalize_text(
            row.get("nflverse_game_id")
        )
        if not team_abbr or not nflverse_game_id:
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
        if not isinstance(season_type, str):
            season_type = _season_type(season_type)
        else:
            season_type = season_type.upper()

        records.append(
            {
                "team_id": make_team_id(team_abbr),
                "game_id": game_id,
                "season": _normalize_int(row.get("season")),
                "week": _normalize_int(row.get("week")),
                "season_type": season_type,
                "offensive_plays": _normalize_int(
                    row.get("offensive_plays")
                ),
                "pass_attempts": _normalize_int(
                    row.get("pass_attempts")
                ),
                "rush_attempts": _normalize_int(
                    row.get("rush_attempts")
                ),
                "pass_rate": _normalize_float(
                    row.get("pass_rate")
                ),
                "neutral_pass_rate": _normalize_float(
                    row.get("neutral_pass_rate")
                ),
                "pace": _normalize_float(row.get("pace")),
                "points": _normalize_int(row.get("points")),
                "yards": _normalize_float(row.get("yards")),
                "offensive_epa": _normalize_float(
                    row.get("offensive_epa")
                ),
                "pass_epa": _normalize_float(
                    row.get("pass_epa")
                ),
                "rush_epa": _normalize_float(
                    row.get("rush_epa")
                ),
                "red_zone_trips": _normalize_int(
                    row.get("red_zone_trips")
                ),
                "red_zone_td_rate": _normalize_float(
                    row.get("red_zone_td_rate")
                ),
                "turnovers": _normalize_int(
                    row.get("turnovers")
                ),
                "source_ids": {
                    "team_abbreviation": team_abbr,
                    "nflverse_game_id": nflverse_game_id,
                },
                "resolution_key": (
                    f"{team_abbr}:{nflverse_game_id}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build fact_team_game: no resolvable "
            "team×game rows."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_TEAM_GAME_COLUMNS + ["resolution_key"]:
        if column == "source_ids" or column not in fact.columns:
            continue
        fact[column] = fact[column].astype("object")
        fact[column] = fact[column].where(
            fact[column].notna(),
            None,
        )

    fact = fact.drop_duplicates(
        subset=["team_id", "game_id"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_TEAM_GAME_CACHE
    global _FACT_TEAM_GAME_CACHE_WITH_KEYS
    global _FACT_TEAM_GAME_CACHE_SEASONS
    _FACT_TEAM_GAME_CACHE_WITH_KEYS = fact.copy()
    _FACT_TEAM_GAME_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_team_game(fact)

    output = fact[FACT_TEAM_GAME_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "team_id", "game_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_TEAM_GAME_CACHE = output.copy()
    return output


def fact_team_game_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_team_game"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_team_game(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_TEAM_GAME_CACHE
    global _FACT_TEAM_GAME_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_TEAM_GAME_CACHE is not None
        and not _FACT_TEAM_GAME_CACHE.empty
        and _FACT_TEAM_GAME_CACHE_SEASONS == tuple(resolved)
    ):
        return _FACT_TEAM_GAME_CACHE.copy()

    if not force_refresh and fact_team_game_count() > 0:
        frame = load_fact_team_game_from_db(seasons=resolved)
        if not frame.empty:
            _FACT_TEAM_GAME_CACHE = frame.copy()
            _FACT_TEAM_GAME_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_fact_team_game(
        resolved,
        persist=persist,
    )


def upsert_fact_team_game(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_team_game (
            team_id,
            game_id,
            season,
            week,
            season_type,
            offensive_plays,
            pass_attempts,
            rush_attempts,
            pass_rate,
            neutral_pass_rate,
            pace,
            points,
            yards,
            offensive_epa,
            pass_epa,
            rush_epa,
            red_zone_trips,
            red_zone_td_rate,
            turnovers,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :team_id,
            :game_id,
            :season,
            :week,
            :season_type,
            :offensive_plays,
            :pass_attempts,
            :rush_attempts,
            :pass_rate,
            :neutral_pass_rate,
            :pace,
            :points,
            :yards,
            :offensive_epa,
            :pass_epa,
            :rush_epa,
            :red_zone_trips,
            :red_zone_td_rate,
            :turnovers,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            team_id = EXCLUDED.team_id,
            game_id = EXCLUDED.game_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            offensive_plays = EXCLUDED.offensive_plays,
            pass_attempts = EXCLUDED.pass_attempts,
            rush_attempts = EXCLUDED.rush_attempts,
            pass_rate = EXCLUDED.pass_rate,
            neutral_pass_rate = EXCLUDED.neutral_pass_rate,
            pace = EXCLUDED.pace,
            points = EXCLUDED.points,
            yards = EXCLUDED.yards,
            offensive_epa = EXCLUDED.offensive_epa,
            pass_epa = EXCLUDED.pass_epa,
            rush_epa = EXCLUDED.rush_epa,
            red_zone_trips = EXCLUDED.red_zone_trips,
            red_zone_td_rate = EXCLUDED.red_zone_td_rate,
            turnovers = EXCLUDED.turnovers,
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
            "team_id": record["team_id"],
            "game_id": record["game_id"],
            "resolution_key": record["resolution_key"],
            "source_ids": source_ids,
        }
        for column in FACT_TEAM_GAME_COLUMNS:
            if column in {
                "team_id",
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


def load_fact_team_game_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_TEAM_GAME_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_team_game
        ORDER BY season, week, team_id, game_id
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
