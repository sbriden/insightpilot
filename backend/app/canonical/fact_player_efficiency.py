"""
fact_player_efficiency — rate metrics, separate from opportunity.

Grain: one player × one game.
Opportunity lives in fact_player_usage; production in
fact_player_game. This table stores only efficiency rates.
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


_FACT_PLAYER_EFFICIENCY_CACHE: pd.DataFrame | None = None
_FACT_PLAYER_EFFICIENCY_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_PLAYER_EFFICIENCY_CACHE_SEASONS: tuple[int, ...] | None = None

SKILL_POSITIONS = {"QB", "RB", "WR", "TE", "FB"}

FACT_PLAYER_EFFICIENCY_COLUMNS = [
    "player_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "team_id",
    "position",
    "yards_per_carry",
    "yards_per_target",
    "yards_per_route_run",
    "catch_rate",
    "td_rate",
    "pass_epa_per_dropback",
    "rush_epa_per_attempt",
    "fantasy_points_per_touch",
    "fantasy_points_per_route",
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


def _load_player_stats(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(
        nfl.load_player_stats(
            seasons=seasons,
            summary_level="week",
        )
    )


def _usage_lookup_frame(
    seasons: list[int],
    *,
    usage_frame: pd.DataFrame | None,
    persist: bool,
) -> pd.DataFrame:
    """
    Bring routes_run / dropbacks / touches from usage when
    available. Touches can also be derived from production.
    """

    columns = [
        "gsis_id",
        "nflverse_game_id",
        "routes_run",
        "dropbacks",
        "touches",
    ]

    if usage_frame is not None:
        frame = usage_frame.copy()
    else:
        from app.canonical.fact_player_usage import (
            get_fact_player_usage,
        )

        frame = get_fact_player_usage(
            seasons,
            force_refresh=False,
            persist=persist,
        )

    if frame.empty:
        return pd.DataFrame(columns=columns)

    working = frame.copy()

    if "gsis_id" not in working.columns:
        def _gsis_from_source(value: Any) -> str | None:
            if isinstance(value, dict):
                return _normalize_text(value.get("gsis_id"))
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, dict):
                    return _normalize_text(parsed.get("gsis_id"))
            return None

        if "source_ids" in working.columns:
            working["gsis_id"] = working["source_ids"].map(
                _gsis_from_source
            )

    if "nflverse_game_id" not in working.columns:
        def _game_from_source(value: Any) -> str | None:
            if isinstance(value, dict):
                return _normalize_text(
                    value.get("nflverse_game_id")
                )
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, dict):
                    return _normalize_text(
                        parsed.get("nflverse_game_id")
                    )
            return None

        if "source_ids" in working.columns:
            working["nflverse_game_id"] = working[
                "source_ids"
            ].map(_game_from_source)

    keep = [
        column
        for column in columns
        if column in working.columns
    ]
    if "gsis_id" not in keep or "nflverse_game_id" not in keep:
        return pd.DataFrame(columns=columns)

    return (
        working[keep]
        .dropna(subset=["gsis_id", "nflverse_game_id"])
        .drop_duplicates(
            subset=["gsis_id", "nflverse_game_id"],
            keep="last",
        )
        .reset_index(drop=True)
    )


def build_fact_player_efficiency(
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

    stats = raw.get("player_stats")
    if stats is None:
        stats = _load_player_stats(resolved_seasons)
    else:
        stats = stats.copy()
    if stats.empty:
        raise ValueError(
            "Unable to build fact_player_efficiency: no player "
            "stats rows were available."
        )

    usage = _usage_lookup_frame(
        resolved_seasons,
        usage_frame=(
            raw.get("usage")
            if "usage" in raw
            else None
            if source_frames is None
            else pd.DataFrame()
        ),
        persist=persist,
    )

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

    spine = stats.copy()
    if "position" in spine.columns:
        spine = spine[
            spine["position"]
            .astype("string")
            .str.upper()
            .isin(SKILL_POSITIONS)
        ].copy()
    if spine.empty:
        raise ValueError(
            "Unable to build fact_player_efficiency: no "
            "skill-position player×game rows."
        )

    spine["gsis_id"] = spine["player_id"].map(_normalize_text)
    spine["nflverse_game_id"] = spine["game_id"].map(
        _normalize_text
    )
    spine = spine[
        spine["gsis_id"].notna()
        & spine["nflverse_game_id"].notna()
    ].copy()

    if not usage.empty:
        spine = spine.merge(
            usage,
            on=["gsis_id", "nflverse_game_id"],
            how="left",
            suffixes=("", "_usage"),
        )

    records: list[dict[str, Any]] = []
    for row in spine.to_dict(orient="records"):
        gsis_id = _normalize_text(row.get("gsis_id"))
        nflverse_game_id = _normalize_text(
            row.get("nflverse_game_id")
        )
        if not gsis_id or not nflverse_game_id:
            continue

        player_id = player_lookup.get(gsis_id)
        if player_id is None:
            try:
                player_id = make_player_id(
                    player_resolution_key(gsis_id=gsis_id)
                )
            except ValueError:
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

        team_abbr = (
            _normalize_text(row.get("team")) or ""
        ).upper() or None
        position = (
            _normalize_text(row.get("position")) or ""
        ).upper() or None

        carries = _normalize_float(row.get("carries"))
        rush_yards = _normalize_float(row.get("rushing_yards"))
        targets = _normalize_float(row.get("targets"))
        receptions = _normalize_float(row.get("receptions"))
        receiving_yards = _normalize_float(
            row.get("receiving_yards")
        )
        rush_tds = _normalize_float(row.get("rushing_tds")) or 0.0
        receiving_tds = (
            _normalize_float(row.get("receiving_tds")) or 0.0
        )
        pass_tds = _normalize_float(row.get("passing_tds")) or 0.0
        pass_attempts = _normalize_float(row.get("attempts"))
        pass_epa = _normalize_float(row.get("passing_epa"))
        rush_epa = _normalize_float(row.get("rushing_epa"))
        fantasy_points = _normalize_float(
            row.get("fantasy_points_ppr")
        )
        if fantasy_points is None:
            fantasy_points = _normalize_float(
                row.get("fantasy_points")
            )

        routes_run = _normalize_float(row.get("routes_run"))
        dropbacks = _normalize_float(row.get("dropbacks"))
        touches = _normalize_float(row.get("touches"))
        if touches is None:
            touch_parts = [
                value
                for value in (carries, receptions)
                if value is not None
            ]
            touches = (
                sum(touch_parts) if touch_parts else None
            )

        skill_tds = rush_tds + receiving_tds
        if touches is not None and touches > 0:
            td_rate = _safe_div(skill_tds, touches)
        else:
            td_rate = _safe_div(pass_tds, pass_attempts)

        records.append(
            {
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
                "position": position,
                "yards_per_carry": _safe_div(
                    rush_yards,
                    carries,
                ),
                "yards_per_target": _safe_div(
                    receiving_yards,
                    targets,
                ),
                "yards_per_route_run": _safe_div(
                    receiving_yards,
                    routes_run,
                ),
                "catch_rate": _safe_div(
                    receptions,
                    targets,
                ),
                "td_rate": td_rate,
                "pass_epa_per_dropback": _safe_div(
                    pass_epa,
                    dropbacks,
                ),
                "rush_epa_per_attempt": _safe_div(
                    rush_epa,
                    carries,
                ),
                "fantasy_points_per_touch": _safe_div(
                    fantasy_points,
                    touches,
                ),
                "fantasy_points_per_route": _safe_div(
                    fantasy_points,
                    routes_run,
                ),
                "source_ids": {
                    "gsis_id": gsis_id,
                    "nflverse_game_id": nflverse_game_id,
                },
                "resolution_key": (
                    f"{gsis_id}:{nflverse_game_id}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build fact_player_efficiency: no "
            "resolvable player×game rows."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_PLAYER_EFFICIENCY_COLUMNS + [
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
        subset=["player_id", "game_id"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_PLAYER_EFFICIENCY_CACHE
    global _FACT_PLAYER_EFFICIENCY_CACHE_WITH_KEYS
    global _FACT_PLAYER_EFFICIENCY_CACHE_SEASONS
    _FACT_PLAYER_EFFICIENCY_CACHE_WITH_KEYS = fact.copy()
    _FACT_PLAYER_EFFICIENCY_CACHE_SEASONS = tuple(
        resolved_seasons
    )

    if persist:
        upsert_fact_player_efficiency(fact)

    output = fact[FACT_PLAYER_EFFICIENCY_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "player_id", "game_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_PLAYER_EFFICIENCY_CACHE = output.copy()
    return output


def fact_player_efficiency_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_player_efficiency"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_player_efficiency(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_PLAYER_EFFICIENCY_CACHE
    global _FACT_PLAYER_EFFICIENCY_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_PLAYER_EFFICIENCY_CACHE is not None
        and not _FACT_PLAYER_EFFICIENCY_CACHE.empty
        and _FACT_PLAYER_EFFICIENCY_CACHE_SEASONS
        == tuple(resolved)
    ):
        return _FACT_PLAYER_EFFICIENCY_CACHE.copy()

    if not force_refresh and fact_player_efficiency_count() > 0:
        frame = load_fact_player_efficiency_from_db(
            seasons=resolved,
        )
        if not frame.empty:
            _FACT_PLAYER_EFFICIENCY_CACHE = frame.copy()
            _FACT_PLAYER_EFFICIENCY_CACHE_SEASONS = tuple(
                resolved
            )
            return frame

    return build_fact_player_efficiency(
        resolved,
        persist=persist,
    )


def upsert_fact_player_efficiency(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_player_efficiency (
            player_id,
            game_id,
            season,
            week,
            season_type,
            team_id,
            position,
            yards_per_carry,
            yards_per_target,
            yards_per_route_run,
            catch_rate,
            td_rate,
            pass_epa_per_dropback,
            rush_epa_per_attempt,
            fantasy_points_per_touch,
            fantasy_points_per_route,
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
            :position,
            :yards_per_carry,
            :yards_per_target,
            :yards_per_route_run,
            :catch_rate,
            :td_rate,
            :pass_epa_per_dropback,
            :rush_epa_per_attempt,
            :fantasy_points_per_touch,
            :fantasy_points_per_route,
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
            position = EXCLUDED.position,
            yards_per_carry = EXCLUDED.yards_per_carry,
            yards_per_target = EXCLUDED.yards_per_target,
            yards_per_route_run = EXCLUDED.yards_per_route_run,
            catch_rate = EXCLUDED.catch_rate,
            td_rate = EXCLUDED.td_rate,
            pass_epa_per_dropback = EXCLUDED.pass_epa_per_dropback,
            rush_epa_per_attempt = EXCLUDED.rush_epa_per_attempt,
            fantasy_points_per_touch = EXCLUDED.fantasy_points_per_touch,
            fantasy_points_per_route = EXCLUDED.fantasy_points_per_route,
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
            "player_id": record["player_id"],
            "game_id": record["game_id"],
            "resolution_key": record["resolution_key"],
            "source_ids": source_ids,
        }
        for column in FACT_PLAYER_EFFICIENCY_COLUMNS:
            if column in {
                "player_id",
                "game_id",
                "source_ids",
            }:
                continue
            row[column] = _sql_null_if_missing(
                record.get(column)
            )
        rows.append(row)

    batch_size = 1000
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def load_fact_player_efficiency_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_PLAYER_EFFICIENCY_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_player_efficiency
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
