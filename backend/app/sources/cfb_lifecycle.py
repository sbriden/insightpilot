"""
Ingestion lifecycle for sportsdataverse college football data.

Modes:
  historical  — multi-season bootstrap (dims + facts)
  incremental — current season only
  reprocess   — rebuild facts from dims / source loaders

Pipeline layers (ordered): dims → facts
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from app.canonical.cfb.schema import COLLEGE_SCHEMA, ensure_college_schema
from app.database import engine
from app.sources import sportsdataverse as sdv_source


HISTORICAL_SEASON_COUNT = sdv_source.HISTORICAL_SEASON_COUNT
MIN_SEASON = sdv_source.MIN_SEASON

LAYER_DIMS = "dims"
LAYER_FACTS = "facts"

LAYER_ORDER = [LAYER_DIMS, LAYER_FACTS]

PIPELINE_BY_LAYER: dict[str, list[str]] = {
    LAYER_DIMS: [
        "dim_team",
        "dim_player",
        "dim_game",
    ],
    LAYER_FACTS: [
        "fact_player_game",
        "fact_team_game",
        "fact_defensive_game",
        "fact_game_market",
    ],
}

REFRESH_PIPELINE: list[str] = [
    dataset_id
    for layer in LAYER_ORDER
    for dataset_id in PIPELINE_BY_LAYER[layer]
]

MODE_HISTORICAL = "historical"
MODE_INCREMENTAL = "incremental"
MODE_REPROCESS = "reprocess"

INGEST_MODES: dict[str, dict[str, Any]] = {
    MODE_HISTORICAL: {
        "id": MODE_HISTORICAL,
        "label": "Historical load",
        "description": (
            "One-time initial ingestion across several CFB seasons. "
            "Seeds dims and facts for trends and backtesting."
        ),
        "layers": list(LAYER_ORDER),
        "season_scope": "historical",
        "force_refresh": True,
    },
    MODE_INCREMENTAL: {
        "id": MODE_INCREMENTAL,
        "label": "Incremental update",
        "description": (
            "Refresh only the live CFB season (new week data)."
        ),
        "layers": list(LAYER_ORDER),
        "season_scope": "current",
        "force_refresh": True,
    },
    MODE_REPROCESS: {
        "id": MODE_REPROCESS,
        "label": "Reprocess facts",
        "description": (
            "Rebuild fact tables from sportsdataverse loaders "
            "and existing dims. Does not skip dim refresh when "
            "dims are empty."
        ),
        "layers": [LAYER_FACTS],
        "season_scope": "historical",
        "force_refresh": True,
    },
}

SCOPE_ALIASES = {
    "historical": MODE_HISTORICAL,
    "current": MODE_INCREMENTAL,
    "incremental": MODE_INCREMENTAL,
    "reprocess": MODE_REPROCESS,
    "seasons": "seasons",
}

INGESTION_STATE_TABLE = f"{COLLEGE_SCHEMA}.ingestion_state"


def list_ingest_modes() -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "description": item["description"],
            "layers": list(item["layers"]),
            "season_scope": item["season_scope"],
        }
        for item in INGEST_MODES.values()
    ]


def ensure_ingestion_state_schema() -> None:
    ensure_college_schema()


def historical_seasons(
    *,
    current_season: int | None = None,
    count: int = HISTORICAL_SEASON_COUNT,
) -> list[int]:
    current = int(
        current_season
        if current_season is not None
        else sdv_source.get_current_season()
    )
    resolved_count = max(1, int(count))
    start = max(MIN_SEASON, current - resolved_count + 1)
    return list(range(start, current + 1))


def current_seasons(
    *,
    current_season: int | None = None,
) -> list[int]:
    current = int(
        current_season
        if current_season is not None
        else sdv_source.get_current_season()
    )
    return [current]


def resolve_scope_seasons(
    scope: str,
    *,
    seasons: list[int] | None = None,
    current_season: int | None = None,
) -> list[int]:
    normalized_scope = str(scope or "").strip().lower()
    if normalized_scope == "historical":
        return historical_seasons(current_season=current_season)
    if normalized_scope in {"current", "incremental"}:
        return current_seasons(current_season=current_season)
    if normalized_scope == "seasons":
        if not seasons:
            raise ValueError(
                "scope='seasons' requires an explicit seasons list."
            )
        current = int(
            current_season
            if current_season is not None
            else sdv_source.get_current_season()
        )
        resolved = sorted(
            {
                int(season)
                for season in seasons
                if MIN_SEASON <= int(season) <= current
            }
        )
        if not resolved:
            raise ValueError(
                f"Seasons must be between {MIN_SEASON} and {current}."
            )
        return resolved
    raise ValueError(
        "scope must be one of: historical, current, "
        "incremental, seasons."
    )


def normalize_ingest_mode(mode: str | None) -> str:
    raw = str(mode or "").strip().lower()
    if not raw:
        return MODE_INCREMENTAL
    if raw in INGEST_MODES:
        return raw
    aliased = SCOPE_ALIASES.get(raw)
    if aliased and aliased in INGEST_MODES:
        return aliased
    raise ValueError(
        "mode must be one of: historical, incremental, reprocess "
        "(aliases: current→incremental)."
    )


def layers_for_mode(
    mode: str,
    *,
    layers: list[str] | None = None,
) -> list[str]:
    definition = INGEST_MODES[normalize_ingest_mode(mode)]
    default_layers = list(definition["layers"])
    if not layers:
        return default_layers

    requested = [
        str(layer).strip().lower()
        for layer in layers
        if str(layer).strip()
    ]
    unknown = [
        layer for layer in requested if layer not in LAYER_ORDER
    ]
    if unknown:
        raise ValueError(
            "Unknown layers: "
            + ", ".join(unknown)
            + f". Allowed: {', '.join(LAYER_ORDER)}."
        )
    allowed = set(default_layers)
    disallowed = [
        layer for layer in requested if layer not in allowed
    ]
    if disallowed:
        raise ValueError(
            f"Layers not valid for mode '{mode}': "
            + ", ".join(disallowed)
            + f". Allowed for this mode: {', '.join(default_layers)}."
        )
    return [
        layer
        for layer in LAYER_ORDER
        if layer in requested
    ]


def datasets_for_layers(layers: list[str]) -> list[str]:
    datasets: list[str] = []
    for layer in layers:
        datasets.extend(PIPELINE_BY_LAYER[layer])
    return datasets


def _refresh_callables() -> dict[
    str,
    Callable[..., pd.DataFrame],
]:
    from app.canonical.cfb.dim_game import get_dim_game
    from app.canonical.cfb.dim_player import get_dim_player
    from app.canonical.cfb.dim_team import get_dim_team
    from app.canonical.cfb.fact_defensive_game import (
        get_fact_defensive_game,
    )
    from app.canonical.cfb.fact_game_market import (
        get_fact_game_market,
    )
    from app.canonical.cfb.fact_player_game import (
        get_fact_player_game,
    )
    from app.canonical.cfb.fact_team_game import get_fact_team_game

    return {
        "dim_team": lambda seasons, **kwargs: get_dim_team(
            seasons=seasons,
            force_refresh=kwargs.get("force_refresh", True),
            persist=kwargs.get("persist", True),
        ),
        "dim_player": lambda seasons, **kwargs: get_dim_player(
            seasons=seasons,
            force_refresh=kwargs.get("force_refresh", True),
            persist=kwargs.get("persist", True),
        ),
        "dim_game": get_dim_game,
        "fact_player_game": get_fact_player_game,
        "fact_team_game": get_fact_team_game,
        "fact_defensive_game": get_fact_defensive_game,
        "fact_game_market": get_fact_game_market,
    }


def refresh_dataset(
    dataset_id: str,
    seasons: list[int],
    *,
    force_refresh: bool = True,
    persist: bool = True,
) -> dict[str, Any]:
    callables = _refresh_callables()
    if dataset_id not in callables:
        raise ValueError(
            f"Dataset '{dataset_id}' does not support refresh."
        )

    frame = callables[dataset_id](
        seasons,
        force_refresh=force_refresh,
        persist=persist,
    )
    row_count = 0 if frame is None else int(len(frame))
    return {
        "dataset_id": dataset_id,
        "seasons": list(seasons),
        "row_count": row_count,
        "persisted": persist,
        "force_refresh": force_refresh,
    }


def _record_ingestion_state(
    *,
    job_key: str,
    mode: str,
    seasons: list[int],
    layers: list[str],
    datasets_completed: list[str],
    current_season: int,
    status: str,
    started_at: datetime,
    finished_at: datetime | None,
    row_count_total: int,
    detail: dict[str, Any],
) -> None:
    try:
        ensure_ingestion_state_schema()
        statement = text(
            f"""
            INSERT INTO {INGESTION_STATE_TABLE} (
                job_key,
                mode,
                seasons,
                layers,
                datasets_completed,
                current_season,
                status,
                started_at,
                finished_at,
                row_count_total,
                detail,
                updated_at
            ) VALUES (
                :job_key,
                :mode,
                :seasons,
                :layers,
                :datasets_completed,
                :current_season,
                :status,
                :started_at,
                :finished_at,
                :row_count_total,
                CAST(:detail AS JSONB),
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (job_key) DO UPDATE SET
                mode = EXCLUDED.mode,
                seasons = EXCLUDED.seasons,
                layers = EXCLUDED.layers,
                datasets_completed = EXCLUDED.datasets_completed,
                current_season = EXCLUDED.current_season,
                status = EXCLUDED.status,
                started_at = EXCLUDED.started_at,
                finished_at = EXCLUDED.finished_at,
                row_count_total = EXCLUDED.row_count_total,
                detail = EXCLUDED.detail,
                updated_at = CURRENT_TIMESTAMP
            """
        )
        with engine.begin() as connection:
            connection.execute(
                statement,
                {
                    "job_key": job_key,
                    "mode": mode,
                    "seasons": seasons,
                    "layers": layers,
                    "datasets_completed": datasets_completed,
                    "current_season": current_season,
                    "status": status,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "row_count_total": row_count_total,
                    "detail": json.dumps(detail, sort_keys=True),
                },
            )
    except Exception:
        pass


def get_latest_ingestion_state() -> dict[str, Any] | None:
    """Return the most recently updated CFB ingestion job, if any."""

    try:
        ensure_ingestion_state_schema()
        statement = text(
            f"""
            SELECT
                job_key,
                mode,
                seasons,
                layers,
                datasets_completed,
                current_season,
                status,
                started_at,
                finished_at,
                row_count_total,
                detail,
                updated_at
            FROM {INGESTION_STATE_TABLE}
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        with engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        if row is None:
            return None
        detail = row["detail"]
        if isinstance(detail, str):
            detail = json.loads(detail)
        return {
            "job_key": row["job_key"],
            "mode": row["mode"],
            "seasons": list(row["seasons"] or []),
            "layers": list(row["layers"] or []),
            "datasets_completed": list(
                row["datasets_completed"] or []
            ),
            "current_season": row["current_season"],
            "status": row["status"],
            "started_at": (
                row["started_at"].isoformat()
                if row["started_at"] is not None
                else None
            ),
            "finished_at": (
                row["finished_at"].isoformat()
                if row["finished_at"] is not None
                else None
            ),
            "row_count_total": int(row["row_count_total"] or 0),
            "detail": detail if isinstance(detail, dict) else {},
            "updated_at": (
                row["updated_at"].isoformat()
                if row["updated_at"] is not None
                else None
            ),
        }
    except Exception:
        return None


def run_ingest(
    *,
    mode: str = MODE_INCREMENTAL,
    seasons: list[int] | None = None,
    layers: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    persist: bool = True,
    force_refresh: bool | None = None,
) -> dict[str, Any]:
    sdv_source.clear_all_cfb_caches()

    resolved_mode = normalize_ingest_mode(mode)
    definition = INGEST_MODES[resolved_mode]
    current = sdv_source.get_current_season()

    season_scope = definition["season_scope"]
    if seasons:
        resolved_seasons = resolve_scope_seasons(
            "seasons",
            seasons=seasons,
            current_season=current,
        )
    else:
        resolved_seasons = resolve_scope_seasons(
            season_scope,
            current_season=current,
        )

    resolved_layers = layers_for_mode(
        resolved_mode,
        layers=layers,
    )
    ordered = datasets_for_layers(resolved_layers)

    if dataset_ids:
        requested = [
            str(dataset_id).strip()
            for dataset_id in dataset_ids
            if str(dataset_id).strip()
        ]
        allowed = set(ordered)
        unknown = [
            dataset_id
            for dataset_id in requested
            if dataset_id not in REFRESH_PIPELINE
        ]
        if unknown:
            raise ValueError(
                "Unknown dataset_ids for ingest: "
                + ", ".join(unknown)
            )
        disallowed = [
            dataset_id
            for dataset_id in requested
            if dataset_id not in allowed
        ]
        if disallowed:
            raise ValueError(
                f"dataset_ids not valid for mode '{resolved_mode}': "
                + ", ".join(disallowed)
            )
        ordered = [
            dataset_id
            for dataset_id in ordered
            if dataset_id in set(requested)
        ]

    refresh_flag = (
        definition["force_refresh"]
        if force_refresh is None
        else bool(force_refresh)
    )

    started_at = datetime.now(timezone.utc)
    job_key = (
        f"cfb:{resolved_mode}:"
        f"{','.join(map(str, resolved_seasons))}"
    )
    results: list[dict[str, Any]] = []

    for dataset_id in ordered:
        target_seasons = resolved_seasons
        if dataset_id == "dim_team":
            target_seasons = [current]
        results.append(
            refresh_dataset(
                dataset_id,
                target_seasons,
                force_refresh=refresh_flag,
                persist=persist,
            )
        )

    finished_at = datetime.now(timezone.utc)
    row_count_total = sum(
        int(item.get("row_count") or 0) for item in results
    )

    try:
        sdv_source.clear_all_cfb_caches()
        caches_cleared = 7
    except Exception:
        caches_cleared = 0

    payload = {
        "mode": resolved_mode,
        "mode_label": definition["label"],
        "scope": season_scope if not seasons else "seasons",
        "seasons": resolved_seasons,
        "current_season": current,
        "historical_season_count": HISTORICAL_SEASON_COUNT,
        "layers": resolved_layers,
        "datasets": [item["dataset_id"] for item in results],
        "results": results,
        "row_count_total": row_count_total,
        "status": "succeeded",
        "message": (
            "College football data loaded successfully "
            "(dims and facts)."
        ),
        "caches_cleared": caches_cleared,
        "foundation": "college_football",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }

    _record_ingestion_state(
        job_key=job_key,
        mode=resolved_mode,
        seasons=resolved_seasons,
        layers=resolved_layers,
        datasets_completed=[
            item["dataset_id"] for item in results
        ],
        current_season=current,
        status="succeeded",
        started_at=started_at,
        finished_at=finished_at,
        row_count_total=row_count_total,
        detail={
            "results": results,
            "foundation": "college_football",
        },
    )
    return payload


def refresh_pipeline(
    *,
    mode: str | None = None,
    scope: str | None = None,
    seasons: list[int] | None = None,
    layers: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Compatibility wrapper matching nflverse refresh_pipeline args.
    """

    resolved_mode = mode
    if not resolved_mode and scope:
        aliased = SCOPE_ALIASES.get(str(scope).strip().lower())
        if aliased == "seasons":
            resolved_mode = MODE_INCREMENTAL
        elif aliased:
            resolved_mode = aliased
    return run_ingest(
        mode=resolved_mode or MODE_INCREMENTAL,
        seasons=seasons,
        layers=layers,
        dataset_ids=dataset_ids,
        persist=persist,
    )


def get_college_data_quality(
    *,
    live: bool = True,
) -> dict[str, Any]:
    """Lightweight row-count quality report for CFB tables."""

    del live
    ensure_college_schema()
    tables = [
        "dim_team",
        "dim_player",
        "dim_game",
        "fact_player_game",
        "fact_team_game",
        "fact_defensive_game",
        "fact_game_market",
    ]
    counts: dict[str, int] = {}
    with engine.connect() as connection:
        for table in tables:
            try:
                result = connection.execute(
                    text(
                        f"SELECT COUNT(*) FROM {COLLEGE_SCHEMA}.{table}"
                    )
                )
                counts[table] = int(result.scalar() or 0)
            except Exception:
                counts[table] = 0

    empty = [name for name, count in counts.items() if count == 0]
    passed = len(empty) == 0
    return {
        "source_id": "sportsdataverse",
        "foundation": "college_football",
        "status": "passed" if passed else "incomplete",
        "passed": passed,
        "message": (
            "All college_football tables have rows."
            if passed
            else (
                "Empty tables: " + ", ".join(empty)
            )
        ),
        "table_counts": counts,
        "empty_tables": empty,
    }
