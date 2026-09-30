"""
fact_player_game — core fantasy production fact.

Grain: one player × one game.
InsightPilot owns player_id and game_id; external IDs stay
in source_ids only.
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


_FACT_PLAYER_GAME_CACHE: pd.DataFrame | None = None
_FACT_PLAYER_GAME_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_PLAYER_GAME_CACHE_SEASONS: tuple[int, ...] | None = None

FACT_PLAYER_GAME_COLUMNS = [
    "player_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "team_id",
    "pass_attempts",
    "pass_completions",
    "pass_yards",
    "pass_tds",
    "interceptions",
    "pass_epa",
    "pass_cpoe",
    "rush_attempts",
    "rush_yards",
    "rush_tds",
    "rush_epa",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "receiving_epa",
    "fg_made",
    "fg_att",
    "fg_made_0_19",
    "fg_made_20_29",
    "fg_made_30_39",
    "fg_made_40_49",
    "fg_made_50_59",
    "fg_made_60_",
    "pat_made",
    "pat_att",
    "source_ids",
]

_SOURCE_COLUMN_MAP = {
    "pass_attempts": ("attempts",),
    "pass_completions": ("completions",),
    "pass_yards": ("passing_yards",),
    "pass_tds": ("passing_tds",),
    "interceptions": (
        "passing_interceptions",
        "interceptions",
    ),
    "pass_epa": ("passing_epa",),
    "pass_cpoe": ("passing_cpoe", "cpoe"),
    "rush_attempts": ("carries", "rushing_attempts"),
    "rush_yards": ("rushing_yards",),
    "rush_tds": ("rushing_tds",),
    "rush_epa": ("rushing_epa",),
    "targets": ("targets",),
    "receptions": ("receptions",),
    "receiving_yards": ("receiving_yards",),
    "receiving_tds": ("receiving_tds",),
    "receiving_epa": ("receiving_epa",),
    "fg_made": ("fg_made",),
    "fg_att": ("fg_att",),
    "fg_made_0_19": ("fg_made_0_19",),
    "fg_made_20_29": ("fg_made_20_29",),
    "fg_made_30_39": ("fg_made_30_39",),
    "fg_made_40_49": ("fg_made_40_49",),
    "fg_made_50_59": ("fg_made_50_59",),
    "fg_made_60_": ("fg_made_60_",),
    "pat_made": ("pat_made",),
    "pat_att": ("pat_att",),
}


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


def _pick_source_value(
    row: dict[str, Any],
    candidates: tuple[str, ...],
) -> Any:
    for column in candidates:
        if column in row and not _is_missing(row.get(column)):
            return row.get(column)
    return None


def _load_player_stats(
    seasons: list[int],
) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(
        nfl.load_player_stats(
            seasons=seasons,
            summary_level="week",
        )
    )


def _load_snap_counts(
    seasons: list[int],
) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_snap_counts(seasons=seasons))


def _pfr_to_gsis_lookup(
    dim_player: pd.DataFrame | None,
) -> dict[str, str]:
    """Map Pro-Football-Reference player ids to GSIS ids."""

    if dim_player is None or dim_player.empty:
        return {}
    if "source_ids" not in dim_player.columns:
        return {}

    lookup: dict[str, str] = {}
    for raw in dim_player["source_ids"].tolist():
        source_ids = raw
        if isinstance(raw, str):
            try:
                source_ids = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        if not isinstance(source_ids, dict):
            continue
        pfr_id = _normalize_text(source_ids.get("pfr_id"))
        gsis_id = _normalize_text(source_ids.get("gsis_id"))
        if pfr_id and gsis_id:
            lookup[pfr_id] = gsis_id
    return lookup


def _resolve_player_game_ids(
    *,
    gsis_id: str,
    nflverse_game_id: str,
    player_lookup: dict[str, str],
    game_lookup: dict[str, str],
) -> tuple[str, str] | None:
    player_id = player_lookup.get(gsis_id)
    if player_id is None:
        try:
            player_id = make_player_id(
                player_resolution_key(gsis_id=gsis_id)
            )
        except ValueError:
            return None

    game_id = game_lookup.get(nflverse_game_id)
    if game_id is None:
        try:
            game_id = make_game_id(
                game_resolution_key(
                    nflverse_game_id=nflverse_game_id,
                )
            )
        except ValueError:
            return None
    return player_id, game_id


def _active_zero_production_records(
    snap_counts: pd.DataFrame,
    *,
    existing_keys: set[tuple[str, str]],
    player_lookup: dict[str, str],
    game_lookup: dict[str, str],
    pfr_to_gsis: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Players who took offensive snaps but have no box-score row.

    nflverse weekly stats omit some active zero-production games.
    Snap participation is the active/played signal; inactive
    players (no offensive snaps) stay omitted.
    """

    if snap_counts is None or snap_counts.empty:
        return []

    working = snap_counts.copy()
    working["pfr_player_id"] = working.get(
        "pfr_player_id",
        pd.Series(dtype="object"),
    ).map(_normalize_text)
    working["gsis_id"] = working["pfr_player_id"].map(pfr_to_gsis)
    working["nflverse_game_id"] = working.get(
        "game_id",
        pd.Series(dtype="object"),
    ).map(_normalize_text)
    working["offense_snaps"] = pd.to_numeric(
        working.get("offense_snaps"),
        errors="coerce",
    ).fillna(0)

    working = working[
        working["gsis_id"].notna()
        & working["nflverse_game_id"].notna()
        & (working["offense_snaps"] > 0)
    ].copy()
    if working.empty:
        return []

    working = working.drop_duplicates(
        subset=["gsis_id", "nflverse_game_id"],
        keep="last",
    )

    zero_stat_fields = {
        target: None for target in _SOURCE_COLUMN_MAP
    }
    # Counting stats default to 0 so FPPG treats the week as
    # an active zero rather than NULL production.
    for target in _SOURCE_COLUMN_MAP:
        if target.endswith("_epa") or target == "pass_cpoe":
            zero_stat_fields[target] = None
        else:
            zero_stat_fields[target] = 0

    records: list[dict[str, Any]] = []
    for row in working.to_dict(orient="records"):
        gsis_id = _normalize_text(row.get("gsis_id"))
        nflverse_game_id = _normalize_text(
            row.get("nflverse_game_id")
        )
        if not gsis_id or not nflverse_game_id:
            continue
        if (gsis_id, nflverse_game_id) in existing_keys:
            continue

        resolved = _resolve_player_game_ids(
            gsis_id=gsis_id,
            nflverse_game_id=nflverse_game_id,
            player_lookup=player_lookup,
            game_lookup=game_lookup,
        )
        if resolved is None:
            continue
        player_id, game_id = resolved

        team_abbr = (
            _normalize_text(row.get("team")) or ""
        ).upper() or None
        season_type = _season_type(
            row.get("game_type") or row.get("season_type")
        )

        record: dict[str, Any] = {
            "player_id": player_id,
            "game_id": game_id,
            "season": _normalize_int(row.get("season")),
            "week": _normalize_int(row.get("week")),
            "season_type": season_type,
            "team_id": (
                make_team_id(team_abbr)
                if team_abbr
                else None
            ),
            "source_ids": {
                "gsis_id": gsis_id,
                "nflverse_game_id": nflverse_game_id,
                "participation": "snap_counts",
            },
            "resolution_key": f"{gsis_id}:{nflverse_game_id}",
            **zero_stat_fields,
        }
        records.append(record)
    return records


def build_fact_player_game(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
    player_id_lookup: dict[str, str] | None = None,
    game_id_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Build fact_player_game for the requested seasons.

    Box-score stats are the primary spine. Players who took
    offensive snaps but are missing from weekly stats are added
    as active zero-production games so FPPG / projections do not
    ignore played weeks. Inactive players (no offensive snaps)
    remain omitted.
    """

    if not seasons:
        raise ValueError("At least one season is required.")

    resolved_seasons = sorted({int(season) for season in seasons})
    raw = source_frames or {}
    stats = raw.get("player_stats")
    if stats is None:
        stats = _load_player_stats(resolved_seasons)
    else:
        stats = stats.copy()
    if stats.empty:
        raise ValueError(
            "Unable to build fact_player_game: no player "
            "stats rows were available from nflverse."
        )

    snap_counts = raw.get("snap_counts")
    if snap_counts is None and source_frames is None:
        snap_counts = _load_snap_counts(resolved_seasons)
    elif snap_counts is None:
        snap_counts = pd.DataFrame()
    else:
        snap_counts = snap_counts.copy()

    dim_player = None
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

    records: list[dict[str, Any]] = []
    existing_keys: set[tuple[str, str]] = set()
    for row in stats.to_dict(orient="records"):
        gsis_id = _normalize_text(row.get("player_id"))
        nflverse_game_id = _normalize_text(row.get("game_id"))
        if not gsis_id or not nflverse_game_id:
            continue

        resolved = _resolve_player_game_ids(
            gsis_id=gsis_id,
            nflverse_game_id=nflverse_game_id,
            player_lookup=player_lookup,
            game_lookup=game_lookup,
        )
        if resolved is None:
            continue
        player_id, game_id = resolved

        team_abbr = (
            _normalize_text(row.get("team")) or ""
        ).upper() or None

        source_ids: dict[str, str] = {
            "gsis_id": gsis_id,
            "nflverse_game_id": nflverse_game_id,
        }
        resolution_key = f"{gsis_id}:{nflverse_game_id}"

        record: dict[str, Any] = {
            "player_id": player_id,
            "game_id": game_id,
            "season": _normalize_int(row.get("season")),
            "week": _normalize_int(row.get("week")),
            "season_type": _season_type(
                row.get("season_type")
            ),
            "team_id": (
                make_team_id(team_abbr)
                if team_abbr
                else None
            ),
            "source_ids": source_ids,
            "resolution_key": resolution_key,
        }

        for target, candidates in _SOURCE_COLUMN_MAP.items():
            raw_value = _pick_source_value(row, candidates)
            if target in {
                "pass_epa",
                "pass_cpoe",
                "rush_epa",
                "receiving_epa",
            }:
                record[target] = _normalize_float(raw_value)
            else:
                record[target] = _normalize_int(raw_value)

        records.append(record)
        existing_keys.add((gsis_id, nflverse_game_id))

    if not snap_counts.empty:
        pfr_to_gsis = raw.get("pfr_to_gsis")
        if not isinstance(pfr_to_gsis, dict):
            if dim_player is None:
                try:
                    dim_player = get_dim_player(
                        force_refresh=False,
                        persist=persist,
                    )
                except Exception:
                    dim_player = None
            pfr_to_gsis = _pfr_to_gsis_lookup(dim_player)
        records.extend(
            _active_zero_production_records(
                snap_counts,
                existing_keys=existing_keys,
                player_lookup=player_lookup,
                game_lookup=game_lookup,
                pfr_to_gsis=pfr_to_gsis,
            )
        )

    if not records:
        raise ValueError(
            "Unable to build fact_player_game: no resolvable "
            "player×game rows."
        )

    fact = pd.DataFrame.from_records(records)
    object_columns = [
        column
        for column in FACT_PLAYER_GAME_COLUMNS
        if column != "source_ids"
    ] + ["resolution_key"]
    for column in object_columns:
        if column in fact.columns:
            fact[column] = fact[column].astype("object")
            fact[column] = fact[column].where(
                fact[column].notna(),
                None,
            )

    fact = fact.drop_duplicates(
        subset=["player_id", "game_id"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_PLAYER_GAME_CACHE
    global _FACT_PLAYER_GAME_CACHE_WITH_KEYS
    global _FACT_PLAYER_GAME_CACHE_SEASONS
    _FACT_PLAYER_GAME_CACHE_WITH_KEYS = fact.copy()
    _FACT_PLAYER_GAME_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_player_game(fact)

    output = fact[FACT_PLAYER_GAME_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "player_id", "game_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_PLAYER_GAME_CACHE = output.copy()
    return output


def fact_player_game_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_player_game"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_player_game(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_PLAYER_GAME_CACHE
    global _FACT_PLAYER_GAME_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_PLAYER_GAME_CACHE is not None
        and not _FACT_PLAYER_GAME_CACHE.empty
        and _FACT_PLAYER_GAME_CACHE_SEASONS == tuple(resolved)
    ):
        return _FACT_PLAYER_GAME_CACHE.copy()

    if not force_refresh and fact_player_game_count() > 0:
        frame = load_fact_player_game_from_db(
            seasons=resolved,
        )
        if not frame.empty:
            _FACT_PLAYER_GAME_CACHE = frame.copy()
            _FACT_PLAYER_GAME_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_fact_player_game(
        resolved,
        persist=persist,
    )


def upsert_fact_player_game(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_player_game (
            player_id,
            game_id,
            season,
            week,
            season_type,
            team_id,
            pass_attempts,
            pass_completions,
            pass_yards,
            pass_tds,
            interceptions,
            pass_epa,
            pass_cpoe,
            rush_attempts,
            rush_yards,
            rush_tds,
            rush_epa,
            targets,
            receptions,
            receiving_yards,
            receiving_tds,
            receiving_epa,
            fg_made,
            fg_att,
            fg_made_0_19,
            fg_made_20_29,
            fg_made_30_39,
            fg_made_40_49,
            fg_made_50_59,
            fg_made_60_,
            pat_made,
            pat_att,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :player_id,
            :game_id,
            :season,
            :week,
            :season_type,
            :team_id,
            :pass_attempts,
            :pass_completions,
            :pass_yards,
            :pass_tds,
            :interceptions,
            :pass_epa,
            :pass_cpoe,
            :rush_attempts,
            :rush_yards,
            :rush_tds,
            :rush_epa,
            :targets,
            :receptions,
            :receiving_yards,
            :receiving_tds,
            :receiving_epa,
            :fg_made,
            :fg_att,
            :fg_made_0_19,
            :fg_made_20_29,
            :fg_made_30_39,
            :fg_made_40_49,
            :fg_made_50_59,
            :fg_made_60_,
            :pat_made,
            :pat_att,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            player_id = EXCLUDED.player_id,
            game_id = EXCLUDED.game_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            team_id = EXCLUDED.team_id,
            pass_attempts = EXCLUDED.pass_attempts,
            pass_completions = EXCLUDED.pass_completions,
            pass_yards = EXCLUDED.pass_yards,
            pass_tds = EXCLUDED.pass_tds,
            interceptions = EXCLUDED.interceptions,
            pass_epa = EXCLUDED.pass_epa,
            pass_cpoe = EXCLUDED.pass_cpoe,
            rush_attempts = EXCLUDED.rush_attempts,
            rush_yards = EXCLUDED.rush_yards,
            rush_tds = EXCLUDED.rush_tds,
            rush_epa = EXCLUDED.rush_epa,
            targets = EXCLUDED.targets,
            receptions = EXCLUDED.receptions,
            receiving_yards = EXCLUDED.receiving_yards,
            receiving_tds = EXCLUDED.receiving_tds,
            receiving_epa = EXCLUDED.receiving_epa,
            fg_made = EXCLUDED.fg_made,
            fg_att = EXCLUDED.fg_att,
            fg_made_0_19 = EXCLUDED.fg_made_0_19,
            fg_made_20_29 = EXCLUDED.fg_made_20_29,
            fg_made_30_39 = EXCLUDED.fg_made_30_39,
            fg_made_40_49 = EXCLUDED.fg_made_40_49,
            fg_made_50_59 = EXCLUDED.fg_made_50_59,
            fg_made_60_ = EXCLUDED.fg_made_60_,
            pat_made = EXCLUDED.pat_made,
            pat_att = EXCLUDED.pat_att,
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
        rows.append(
            {
                "player_id": record["player_id"],
                "game_id": record["game_id"],
                "season": _sql_null_if_missing(
                    record.get("season")
                ),
                "week": _sql_null_if_missing(
                    record.get("week")
                ),
                "season_type": _sql_null_if_missing(
                    record.get("season_type")
                ),
                "team_id": _sql_null_if_missing(
                    record.get("team_id")
                ),
                "pass_attempts": _sql_null_if_missing(
                    record.get("pass_attempts")
                ),
                "pass_completions": _sql_null_if_missing(
                    record.get("pass_completions")
                ),
                "pass_yards": _sql_null_if_missing(
                    record.get("pass_yards")
                ),
                "pass_tds": _sql_null_if_missing(
                    record.get("pass_tds")
                ),
                "interceptions": _sql_null_if_missing(
                    record.get("interceptions")
                ),
                "pass_epa": _sql_null_if_missing(
                    record.get("pass_epa")
                ),
                "pass_cpoe": _sql_null_if_missing(
                    record.get("pass_cpoe")
                ),
                "rush_attempts": _sql_null_if_missing(
                    record.get("rush_attempts")
                ),
                "rush_yards": _sql_null_if_missing(
                    record.get("rush_yards")
                ),
                "rush_tds": _sql_null_if_missing(
                    record.get("rush_tds")
                ),
                "rush_epa": _sql_null_if_missing(
                    record.get("rush_epa")
                ),
                "targets": _sql_null_if_missing(
                    record.get("targets")
                ),
                "receptions": _sql_null_if_missing(
                    record.get("receptions")
                ),
                "receiving_yards": _sql_null_if_missing(
                    record.get("receiving_yards")
                ),
                "receiving_tds": _sql_null_if_missing(
                    record.get("receiving_tds")
                ),
                "receiving_epa": _sql_null_if_missing(
                    record.get("receiving_epa")
                ),
                "fg_made": _sql_null_if_missing(
                    record.get("fg_made")
                ),
                "fg_att": _sql_null_if_missing(
                    record.get("fg_att")
                ),
                "fg_made_0_19": _sql_null_if_missing(
                    record.get("fg_made_0_19")
                ),
                "fg_made_20_29": _sql_null_if_missing(
                    record.get("fg_made_20_29")
                ),
                "fg_made_30_39": _sql_null_if_missing(
                    record.get("fg_made_30_39")
                ),
                "fg_made_40_49": _sql_null_if_missing(
                    record.get("fg_made_40_49")
                ),
                "fg_made_50_59": _sql_null_if_missing(
                    record.get("fg_made_50_59")
                ),
                "fg_made_60_": _sql_null_if_missing(
                    record.get("fg_made_60_")
                ),
                "pat_made": _sql_null_if_missing(
                    record.get("pat_made")
                ),
                "pat_att": _sql_null_if_missing(
                    record.get("pat_att")
                ),
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


def load_fact_player_game_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_PLAYER_GAME_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_player_game
        ORDER BY season, week, player_id, game_id
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
