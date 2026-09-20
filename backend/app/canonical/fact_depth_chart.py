"""
fact_depth_chart — weekly depth chart for opportunity changes.

Grain: team × player × position slot × week.
role starts simple (starter/backup/returner/slot) and can
grow into third_down / goal_line / outside later.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.dim_player import (
    get_dim_player,
    player_id_lookup_from_dim,
)
from app.canonical.ids import (
    make_player_id,
    make_team_id,
    player_resolution_key,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_FACT_DEPTH_CHART_CACHE: pd.DataFrame | None = None
_FACT_DEPTH_CHART_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_DEPTH_CHART_CACHE_SEASONS: tuple[int, ...] | None = None

FACT_DEPTH_CHART_COLUMNS = [
    "team_id",
    "player_id",
    "position",
    "depth_order",
    "role",
    "effective_date",
    "season",
    "week",
    "season_type",
    "source_ids",
]

_RETURNER_POSITIONS = {"KR", "KOR", "PR"}
_SLOT_POSITIONS = {"NCB", "NB", "SWR", "SLWR", "SRWR"}


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
    parsed = pd.to_datetime(value, errors="coerce")
    if _is_missing(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _season_type(value: Any) -> str | None:
    raw = _normalize_text(value)
    if raw is None:
        return None
    return raw.upper()


def _infer_role(
    *,
    depth_order: int | None,
    position: str | None,
) -> str | None:
    """
    Best-effort role from nflverse depth charts.

    Richer roles (third_down, goal_line, outside) can be layered
    on later without changing the table shape.
    """

    pos = (position or "").upper()
    if pos in _RETURNER_POSITIONS:
        return "returner"
    if pos in _SLOT_POSITIONS:
        return "slot"
    if depth_order == 1:
        return "starter"
    if depth_order is not None and depth_order >= 2:
        return "backup"
    return None


def _load_depth_charts(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    frames: list[pd.DataFrame] = []
    for season in seasons:
        frame = _to_pandas(nfl.load_depth_charts(seasons=[season]))
        if frame.empty:
            continue
        frames.append(
            _normalize_depth_chart_source(frame, season=int(season))
        )
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _is_snapshot_depth_schema(frame: pd.DataFrame) -> bool:
    columns = set(frame.columns)
    return (
        "dt" in columns
        and "pos_abb" in columns
        and "team" in columns
        and "club_code" not in columns
    )


def _normalize_depth_chart_source(
    frame: pd.DataFrame,
    *,
    season: int,
) -> pd.DataFrame:
    """
    Normalize nflverse depth charts to the weekly builder shape.

    Recent seasons ship as dated snapshots (dt / team / pos_abb /
    pos_rank) instead of season/week/club_code rows.
    """

    if frame.empty:
        return frame

    if not _is_snapshot_depth_schema(frame):
        working = frame.copy()
        if "season" not in working.columns:
            working["season"] = season
        return working

    working = frame.copy()
    working["_dt"] = pd.to_datetime(
        working["dt"],
        utc=True,
        errors="coerce",
    )
    latest = working["_dt"].max()
    if _is_missing(latest):
        return pd.DataFrame()
    working = working.loc[working["_dt"] == latest].copy()

    return pd.DataFrame(
        {
            "season": season,
            "week": None,
            "club_code": working["team"],
            "gsis_id": working["gsis_id"],
            "position": working.get("pos_abb"),
            "depth_position": working.get("pos_abb"),
            "depth_team": working.get("pos_rank"),
            "formation": working.get("pos_grp"),
            "game_type": "REG",
            "dt": working["dt"],
        }
    )


def _load_schedules(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_schedules(seasons=seasons))


def _weeks_by_team_season(
    schedules: pd.DataFrame,
) -> dict[tuple[int, str], list[tuple[int, str]]]:
    """
    Map (season, team_abbr) -> sorted [(week, gameday), ...].
    """

    lookup: dict[tuple[int, str], list[tuple[int, str]]] = {}
    if schedules.empty:
        return lookup

    for record in schedules.to_dict(orient="records"):
        season = _normalize_int(record.get("season"))
        week = _normalize_int(record.get("week"))
        game_date = _normalize_date(
            record.get("gameday") or record.get("game_date")
        )
        if season is None or week is None or not game_date:
            continue
        for team_key in ("home_team", "away_team"):
            team = (
                _normalize_text(record.get(team_key)) or ""
            ).upper()
            if not team:
                continue
            bucket = lookup.setdefault((season, team), [])
            bucket.append((week, game_date))

    for key, values in lookup.items():
        values.sort(key=lambda item: (item[1], item[0]))
        # De-dupe week entries keeping earliest date.
        seen: dict[int, str] = {}
        for week, game_date in values:
            if week not in seen:
                seen[week] = game_date
        lookup[key] = sorted(
            seen.items(),
            key=lambda item: (item[1], item[0]),
        )
    return lookup


def _week_for_effective_date(
    *,
    season: int | None,
    team_abbr: str | None,
    effective_date: str | None,
    weeks_by_team: dict[tuple[int, str], list[tuple[int, str]]],
) -> int | None:
    if (
        season is None
        or not team_abbr
        or not effective_date
    ):
        return None
    entries = weeks_by_team.get((season, team_abbr.upper()))
    if not entries:
        return None
    matched: int | None = None
    for week, game_date in entries:
        if game_date <= effective_date:
            matched = week
        else:
            break
    return matched


def _effective_date_by_team_week(
    schedules: pd.DataFrame,
) -> dict[tuple[int, int, str], str]:
    """
    Map (season, week, team_abbr) -> game_date (effective_date).
    """

    lookup: dict[tuple[int, int, str], str] = {}
    if schedules.empty:
        return lookup

    for record in schedules.to_dict(orient="records"):
        season = _normalize_int(record.get("season"))
        week = _normalize_int(record.get("week"))
        game_date = _normalize_date(
            record.get("gameday") or record.get("game_date")
        )
        if season is None or week is None or not game_date:
            continue
        home = (
            _normalize_text(record.get("home_team")) or ""
        ).upper()
        away = (
            _normalize_text(record.get("away_team")) or ""
        ).upper()
        if home:
            lookup[(season, week, home)] = game_date
        if away:
            lookup[(season, week, away)] = game_date
    return lookup


def build_fact_depth_chart(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
    player_id_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved_seasons = sorted({int(season) for season in seasons})
    raw = source_frames or {}

    depth_charts = raw.get("depth_charts")
    if depth_charts is None:
        depth_charts = _load_depth_charts(resolved_seasons)
    else:
        # Tests / callers may pass either schema; normalize per season.
        pieces: list[pd.DataFrame] = []
        for season in resolved_seasons:
            subset = depth_charts
            if (
                "season" in depth_charts.columns
                and not _is_snapshot_depth_schema(depth_charts)
            ):
                subset = depth_charts[
                    depth_charts["season"].map(
                        lambda value, season=season: (
                            _normalize_int(value) == season
                        )
                    )
                ]
            pieces.append(
                _normalize_depth_chart_source(
                    subset.copy(),
                    season=season,
                )
            )
        depth_charts = (
            pd.concat(pieces, ignore_index=True)
            if pieces
            else pd.DataFrame()
        )
    if depth_charts.empty:
        raise ValueError(
            "Unable to build fact_depth_chart: no depth chart "
            "rows were available from nflverse."
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

    effective_dates = _effective_date_by_team_week(schedules)
    weeks_by_team = _weeks_by_team_season(schedules)

    records: list[dict[str, Any]] = []
    for row in depth_charts.to_dict(orient="records"):
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
            _normalize_text(row.get("club_code")) or ""
        ).upper() or None
        season = _normalize_int(row.get("season"))
        week = _normalize_int(row.get("week"))
        season_type = _season_type(row.get("game_type"))
        depth_order = _normalize_int(row.get("depth_team"))
        position = _normalize_text(
            row.get("depth_position")
        ) or _normalize_text(row.get("position"))
        formation = _normalize_text(row.get("formation"))

        effective_date = _normalize_date(row.get("dt"))
        if (
            effective_date is None
            and season is not None
            and week is not None
            and team_abbr
        ):
            effective_date = effective_dates.get(
                (season, week, team_abbr)
            )

        if week is None:
            week = _week_for_effective_date(
                season=season,
                team_abbr=team_abbr,
                effective_date=effective_date,
                weeks_by_team=weeks_by_team,
            )

        role = _infer_role(
            depth_order=depth_order,
            position=position,
        )

        resolution_key = (
            f"{gsis_id}:{season}:{week}:"
            f"{formation or ''}:{position or ''}:"
            f"{depth_order if depth_order is not None else ''}:"
            f"{effective_date or ''}"
        )

        source_ids: dict[str, str] = {"gsis_id": gsis_id}
        if team_abbr:
            source_ids["team_abbreviation"] = team_abbr
        if formation:
            source_ids["formation"] = formation
        base_position = _normalize_text(row.get("position"))
        if base_position:
            source_ids["base_position"] = base_position

        records.append(
            {
                "team_id": (
                    make_team_id(team_abbr)
                    if team_abbr
                    else None
                ),
                "player_id": player_id,
                "position": position,
                "depth_order": depth_order,
                "role": role,
                "effective_date": effective_date,
                "season": season,
                "week": week,
                "season_type": season_type,
                "source_ids": source_ids,
                "resolution_key": resolution_key,
            }
        )

    if not records:
        raise ValueError(
            "Unable to build fact_depth_chart: no resolvable "
            "depth chart rows."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_DEPTH_CHART_COLUMNS + ["resolution_key"]:
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

    global _FACT_DEPTH_CHART_CACHE
    global _FACT_DEPTH_CHART_CACHE_WITH_KEYS
    global _FACT_DEPTH_CHART_CACHE_SEASONS
    _FACT_DEPTH_CHART_CACHE_WITH_KEYS = fact.copy()
    _FACT_DEPTH_CHART_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_depth_chart(fact)

    output = fact[FACT_DEPTH_CHART_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        [
            "season",
            "week",
            "team_id",
            "position",
            "depth_order",
            "player_id",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_DEPTH_CHART_CACHE = output.copy()
    return output


def fact_depth_chart_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_depth_chart"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_depth_chart(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_DEPTH_CHART_CACHE
    global _FACT_DEPTH_CHART_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_DEPTH_CHART_CACHE is not None
        and not _FACT_DEPTH_CHART_CACHE.empty
        and _FACT_DEPTH_CHART_CACHE_SEASONS == tuple(resolved)
    ):
        return _FACT_DEPTH_CHART_CACHE.copy()

    if not force_refresh and fact_depth_chart_count() > 0:
        frame = load_fact_depth_chart_from_db(seasons=resolved)
        if not frame.empty:
            _FACT_DEPTH_CHART_CACHE = frame.copy()
            _FACT_DEPTH_CHART_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_fact_depth_chart(
        resolved,
        persist=persist,
    )


def upsert_fact_depth_chart(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_depth_chart (
            team_id,
            player_id,
            position,
            depth_order,
            role,
            effective_date,
            season,
            week,
            season_type,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :team_id,
            :player_id,
            :position,
            :depth_order,
            :role,
            CAST(NULLIF(:effective_date, '') AS DATE),
            :season,
            :week,
            :season_type,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            team_id = EXCLUDED.team_id,
            player_id = EXCLUDED.player_id,
            position = EXCLUDED.position,
            depth_order = EXCLUDED.depth_order,
            role = EXCLUDED.role,
            effective_date = EXCLUDED.effective_date,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
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
                "team_id": _sql_null_if_missing(
                    record.get("team_id")
                ),
                "player_id": record["player_id"],
                "position": _sql_null_if_missing(
                    record.get("position")
                ),
                "depth_order": _sql_null_if_missing(
                    record.get("depth_order")
                ),
                "role": _sql_null_if_missing(
                    record.get("role")
                ),
                "effective_date": _normalize_date(
                    record.get("effective_date")
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


def load_fact_depth_chart_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_DEPTH_CHART_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_depth_chart
        ORDER BY season, week, team_id, position, depth_order, player_id
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
