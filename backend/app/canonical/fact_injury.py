"""
fact_injury — player injury reports as their own entity.

Grain: one injury report row per player × week (tied to a
game when the schedule resolves). InsightPilot owns player_id
and team_id / game_id.
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
from app.canonical.dim_player import (
    get_dim_player,
    player_id_lookup_from_dim,
)
from app.canonical.ids import (
    game_resolution_key,
    make_game_id,
    make_player_id,
    make_team_id,
    player_resolution_key,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_FACT_INJURY_CACHE: pd.DataFrame | None = None
_FACT_INJURY_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_INJURY_CACHE_SEASONS: tuple[int, ...] | None = None

FACT_INJURY_COLUMNS = [
    "player_id",
    "team_id",
    "report_date",
    "game_id",
    "season",
    "week",
    "season_type",
    "injury_type",
    "practice_status",
    "game_status",
    "is_expected_to_play",
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
    # nflverse sometimes embeds literal newlines.
    text_value = text_value.replace("\n", " ").strip()
    if not text_value:
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


def _normalize_date(value: Any) -> str | None:
    if _is_missing(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if _is_missing(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _season_type(value: Any) -> str | None:
    raw = _normalize_text(value)
    if raw is None:
        return None
    return raw.upper()


def _is_expected_to_play(
    game_status: str | None,
    practice_status: str | None,
) -> bool | None:
    status = (game_status or "").strip().lower()
    practice = (practice_status or "").strip().lower()

    if status in {"out", "doubtful"}:
        return False
    if status == "questionable":
        return None
    if "full participation" in practice:
        return True
    if "did not participate" in practice:
        return False
    if status:
        # Probable / active-style labels when present.
        return True
    return None


def _load_injuries(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_injuries(seasons=seasons))


def _load_schedules(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_schedules(seasons=seasons))


def _game_lookup_by_team_week(
    schedules: pd.DataFrame,
) -> dict[tuple[int, int, str], str]:
    """
    Map (season, week, team_abbr) -> nflverse game_id.
    """

    lookup: dict[tuple[int, int, str], str] = {}
    if schedules.empty:
        return lookup

    for record in schedules.to_dict(orient="records"):
        game_id = _normalize_text(record.get("game_id"))
        season = _normalize_int(record.get("season"))
        week = _normalize_int(record.get("week"))
        if not game_id or season is None or week is None:
            continue
        home = (
            _normalize_text(record.get("home_team")) or ""
        ).upper()
        away = (
            _normalize_text(record.get("away_team")) or ""
        ).upper()
        if home:
            lookup[(season, week, home)] = game_id
        if away:
            lookup[(season, week, away)] = game_id
    return lookup


def build_fact_injury(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
    player_id_lookup: dict[str, str] | None = None,
    game_id_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved_seasons = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    injuries = raw.get("injuries")
    if injuries is None:
        injuries = _load_injuries(resolved_seasons)
    else:
        injuries = injuries.copy()
    if injuries.empty:
        raise ValueError(
            "Unable to build fact_injury: no injury rows were "
            "available from nflverse."
        )

    schedules = raw.get("schedules")
    if schedules is None:
        if source_frames is None:
            schedules = _load_schedules(resolved_seasons)
        else:
            schedules = pd.DataFrame()
    else:
        schedules = schedules.copy()

    if player_id_lookup is None:
        dim_player = get_dim_player(
            force_refresh=False,
            persist=persist,
        )
        player_lookup = player_id_lookup_from_dim(dim_player)
    else:
        player_lookup = player_id_lookup

    if game_id_lookup is None:
        dim_game = get_dim_game(
            seasons=resolved_seasons,
            force_refresh=False,
            persist=persist,
        )
        game_lookup = game_id_lookup_from_dim(dim_game)
    else:
        game_lookup = game_id_lookup

    team_week_games = _game_lookup_by_team_week(schedules)

    records: list[dict[str, Any]] = []
    for row in injuries.to_dict(orient="records"):
        gsis_id = _normalize_text(row.get("gsis_id"))
        if not gsis_id:
            continue

        player_id = player_lookup.get(gsis_id)
        if player_id is None:
            try:
                player_id = make_player_id(
                    player_resolution_key(gsis_id=gsis_id)
                )
            except ValueError:
                continue

        team_abbr = (
            _normalize_text(row.get("team")) or ""
        ).upper() or None
        season = _normalize_int(row.get("season"))
        week = _normalize_int(row.get("week"))
        season_type = _season_type(row.get("game_type"))
        report_date = _normalize_date(row.get("date_modified"))

        injury_type = _normalize_text(
            row.get("report_primary_injury")
        ) or _normalize_text(
            row.get("practice_primary_injury")
        )
        secondary = _normalize_text(
            row.get("report_secondary_injury")
        ) or _normalize_text(
            row.get("practice_secondary_injury")
        )
        if injury_type and secondary:
            injury_type = f"{injury_type}; {secondary}"

        practice_status = _normalize_text(
            row.get("practice_status")
        )
        game_status = _normalize_text(row.get("report_status"))

        nflverse_game_id = None
        if (
            season is not None
            and week is not None
            and team_abbr
        ):
            nflverse_game_id = team_week_games.get(
                (season, week, team_abbr)
            )

        game_id = None
        if nflverse_game_id:
            game_id = game_lookup.get(nflverse_game_id)
            if game_id is None:
                try:
                    game_id = make_game_id(
                        game_resolution_key(
                            nflverse_game_id=nflverse_game_id,
                        )
                    )
                except ValueError:
                    game_id = None

        resolution_key = (
            f"{gsis_id}:{season}:{week}:{report_date or 'unknown'}"
        )

        source_ids: dict[str, str] = {"gsis_id": gsis_id}
        if nflverse_game_id:
            source_ids["nflverse_game_id"] = nflverse_game_id
        if team_abbr:
            source_ids["team_abbreviation"] = team_abbr

        records.append(
            {
                "player_id": player_id,
                "team_id": (
                    make_team_id(team_abbr)
                    if team_abbr
                    else None
                ),
                "report_date": report_date,
                "game_id": game_id,
                "season": season,
                "week": week,
                "season_type": season_type,
                "injury_type": injury_type,
                "practice_status": practice_status,
                "game_status": game_status,
                "is_expected_to_play": _is_expected_to_play(
                    game_status,
                    practice_status,
                ),
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build fact_injury: no resolvable "
            "injury rows."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_INJURY_COLUMNS + ["resolution_key"]:
        if column == "source_ids" or column not in fact.columns:
            continue
        fact[column] = fact[column].astype("object")
        fact[column] = fact[column].where(
            fact[column].notna(),
            None,
        )

    fact = fact.drop_duplicates(
        subset=["resolution_key"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_INJURY_CACHE
    global _FACT_INJURY_CACHE_WITH_KEYS
    global _FACT_INJURY_CACHE_SEASONS
    _FACT_INJURY_CACHE_WITH_KEYS = fact.copy()
    _FACT_INJURY_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_injury(fact)

    output = fact[FACT_INJURY_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "report_date", "player_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_INJURY_CACHE = output.copy()
    return output


def fact_injury_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_injury"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_injury(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_INJURY_CACHE
    global _FACT_INJURY_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_INJURY_CACHE is not None
        and not _FACT_INJURY_CACHE.empty
        and _FACT_INJURY_CACHE_SEASONS == tuple(resolved)
    ):
        return _FACT_INJURY_CACHE.copy()

    if not force_refresh and fact_injury_count() > 0:
        frame = load_fact_injury_from_db(seasons=resolved)
        if not frame.empty:
            _FACT_INJURY_CACHE = frame.copy()
            _FACT_INJURY_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_fact_injury(
        resolved,
        persist=persist,
    )


def upsert_fact_injury(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_injury (
            player_id,
            team_id,
            report_date,
            game_id,
            season,
            week,
            season_type,
            injury_type,
            practice_status,
            game_status,
            is_expected_to_play,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :player_id,
            :team_id,
            CAST(NULLIF(:report_date, '') AS DATE),
            :game_id,
            :season,
            :week,
            :season_type,
            :injury_type,
            :practice_status,
            :game_status,
            :is_expected_to_play,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            player_id = EXCLUDED.player_id,
            team_id = EXCLUDED.team_id,
            report_date = EXCLUDED.report_date,
            game_id = EXCLUDED.game_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            injury_type = EXCLUDED.injury_type,
            practice_status = EXCLUDED.practice_status,
            game_status = EXCLUDED.game_status,
            is_expected_to_play = EXCLUDED.is_expected_to_play,
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
        expected = record.get("is_expected_to_play")
        if _is_missing(expected):
            expected = None
        rows.append(
            {
                "player_id": record["player_id"],
                "team_id": _sql_null_if_missing(
                    record.get("team_id")
                ),
                "report_date": _normalize_date(
                    record.get("report_date")
                ),
                "game_id": _sql_null_if_missing(
                    record.get("game_id")
                ),
                "season": _sql_null_if_missing(
                    record.get("season")
                ),
                "week": _sql_null_if_missing(
                    record.get("week")
                ),
                "season_type": _sql_null_if_missing(
                    record.get("season_type")
                ),
                "injury_type": _sql_null_if_missing(
                    record.get("injury_type")
                ),
                "practice_status": _sql_null_if_missing(
                    record.get("practice_status")
                ),
                "game_status": _sql_null_if_missing(
                    record.get("game_status")
                ),
                "is_expected_to_play": expected,
                "source_ids": source_ids,
                "resolution_key": record["resolution_key"],
            }
        )

    batch_size = 1000
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def load_fact_injury_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_INJURY_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_injury
        ORDER BY season, week, report_date, player_id
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
