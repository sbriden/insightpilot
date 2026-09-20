"""
Ingestion lifecycle for nflverse fantasy data.

Modes (not just "load a CSV into Postgres"):

  historical  — one-time / bootstrap load of several seasons
  incremental — refresh only the live season (new week data)
  reprocess   — rebuild derived analytics/intelligence from
                stored facts when transformation logic changes

Pipeline layers (ordered):

  dims → facts → analytics → intelligence → domain
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine
from app.sources import nflverse as nflverse_source


HISTORICAL_SEASON_COUNT = nflverse_source.HISTORICAL_SEASON_COUNT

LAYER_DIMS = "dims"
LAYER_FACTS = "facts"
LAYER_ANALYTICS = "analytics"
LAYER_INTELLIGENCE = "intelligence"
LAYER_DOMAIN = "domain"

LAYER_ORDER = [
    LAYER_DIMS,
    LAYER_FACTS,
    LAYER_ANALYTICS,
    LAYER_INTELLIGENCE,
    LAYER_DOMAIN,
]

PIPELINE_BY_LAYER: dict[str, list[str]] = {
    LAYER_DIMS: [
        "dim_team",
        "dim_player",
        "dim_game",
    ],
    LAYER_FACTS: [
        "fact_player_game",
        "fact_player_usage",
        "fact_player_efficiency",
        "fact_team_game",
        "fact_defensive_game",
        "fact_injury",
        "fact_depth_chart",
        "fact_market",
        "fact_game_market",
    ],
    LAYER_ANALYTICS: [
        "player_usage_trend",
        "player_opportunity",
        "player_efficiency",
        "player_matchup",
        "player_environment",
    ],
    LAYER_INTELLIGENCE: [
        "player_fantasy_profile",
        "fantasy_signal",
    ],
    LAYER_DOMAIN: [
        "player_fundamentals",
    ],
}

# Flat ordered list for compatibility with older callers.
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
            "One-time initial ingestion across several seasons. "
            "Seeds dims, facts, analytics, and intelligence for "
            "trends, matchups, and backtesting."
        ),
        "layers": list(LAYER_ORDER),
        "season_scope": "historical",
        "force_refresh": True,
    },
    MODE_INCREMENTAL: {
        "id": MODE_INCREMENTAL,
        "label": "Incremental update",
        "description": (
            "Retrieve and process newly available current-season "
            "data (weekly). Upserts the live season without "
            "rebuilding stored historical seasons."
        ),
        "layers": list(LAYER_ORDER),
        "season_scope": "current",
        "force_refresh": True,
    },
    MODE_REPROCESS: {
        "id": MODE_REPROCESS,
        "label": "Reprocess derived",
        "description": (
            "Rebuild analytics and intelligence from facts already "
            "in Postgres when transformation logic changes. Does "
            "not re-fetch raw nflverse source tables."
        ),
        # Derived only — facts remain the source of truth in DB.
        "layers": [
            LAYER_ANALYTICS,
            LAYER_INTELLIGENCE,
        ],
        "season_scope": "historical",
        "force_refresh": True,
    },
}

# Back-compat aliases used by earlier refresh UI/API.
SCOPE_ALIASES = {
    "historical": MODE_HISTORICAL,
    "current": MODE_INCREMENTAL,
    "incremental": MODE_INCREMENTAL,
    "reprocess": MODE_REPROCESS,
    "seasons": "seasons",
}

INGESTION_STATE_TABLE = f"{FANTASY_SCHEMA}.ingestion_state"

INGESTION_STATE_DDL = f"""
CREATE TABLE IF NOT EXISTS {INGESTION_STATE_TABLE} (
    job_key TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    seasons INTEGER[] NOT NULL DEFAULT '{{}}',
    layers TEXT[] NOT NULL DEFAULT '{{}}',
    datasets_completed TEXT[] NOT NULL DEFAULT '{{}}',
    current_season INTEGER,
    status TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    row_count_total INTEGER NOT NULL DEFAULT 0,
    detail JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def ensure_ingestion_state_schema() -> None:
    with engine.begin() as connection:
        connection.execute(text(INGESTION_STATE_DDL))


def historical_seasons(
    *,
    current_season: int | None = None,
    count: int = HISTORICAL_SEASON_COUNT,
) -> list[int]:
    current = int(
        current_season
        if current_season is not None
        else nflverse_source.get_current_season()
    )
    resolved_count = max(1, int(count))
    start = max(1999, current - resolved_count + 1)
    return list(range(start, current + 1))


def current_seasons(
    *,
    current_season: int | None = None,
) -> list[int]:
    current = int(
        current_season
        if current_season is not None
        else nflverse_source.get_current_season()
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
            else nflverse_source.get_current_season()
        )
        resolved = sorted(
            {
                int(season)
                for season in seasons
                if 1999 <= int(season) <= current
            }
        )
        if not resolved:
            raise ValueError(
                f"Seasons must be between 1999 and {current}."
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
    from app.canonical.analytics.fantasy_signal import (
        get_fantasy_signal,
    )
    from app.canonical.analytics.player_efficiency import (
        get_player_efficiency,
    )
    from app.canonical.analytics.player_environment import (
        get_player_environment,
    )
    from app.canonical.analytics.player_fantasy_profile import (
        get_player_fantasy_profile,
    )
    from app.canonical.analytics.player_matchup import (
        get_player_matchup,
    )
    from app.canonical.analytics.player_opportunity import (
        get_player_opportunity,
    )
    from app.canonical.analytics.player_usage_trend import (
        get_player_usage_trend,
    )
    from app.canonical.dim_game import get_dim_game
    from app.canonical.dim_player import get_dim_player
    from app.canonical.dim_team import get_dim_team
    from app.canonical.fact_defensive_game import (
        get_fact_defensive_game,
    )
    from app.canonical.fact_depth_chart import (
        get_fact_depth_chart,
    )
    from app.canonical.fact_game_market import (
        get_fact_game_market,
    )
    from app.canonical.fact_injury import get_fact_injury
    from app.canonical.fact_market import get_fact_market
    from app.canonical.fact_player_efficiency import (
        get_fact_player_efficiency,
    )
    from app.canonical.fact_player_game import (
        get_fact_player_game,
    )
    from app.canonical.fact_player_usage import (
        get_fact_player_usage,
    )
    from app.canonical.fact_team_game import get_fact_team_game
    from app.sources.fantasy.player_fundamentals import (
        build_player_fundamentals,
    )

    def _refresh_player_fundamentals(
        seasons: list[int],
        *,
        force_refresh: bool = True,
        persist: bool = True,
    ) -> pd.DataFrame:
        del force_refresh, persist
        dataset = nflverse_source.get_dataset_definition(
            "player_fundamentals"
        )
        history = nflverse_source._history_seasons_for(
            seasons,
            lookback=dataset.history_lookback_seasons,
        )
        return build_player_fundamentals(
            seasons,
            current_season=nflverse_source.get_current_season(),
            history_seasons=history,
        )

    return {
        "dim_team": lambda seasons, **kwargs: get_dim_team(
            force_refresh=kwargs.get("force_refresh", True),
            persist=kwargs.get("persist", True),
        ),
        "dim_player": lambda seasons, **kwargs: get_dim_player(
            force_refresh=kwargs.get("force_refresh", True),
            persist=kwargs.get("persist", True),
        ),
        "dim_game": get_dim_game,
        "fact_player_game": get_fact_player_game,
        "fact_player_usage": get_fact_player_usage,
        "fact_player_efficiency": get_fact_player_efficiency,
        "fact_team_game": get_fact_team_game,
        "fact_defensive_game": get_fact_defensive_game,
        "fact_injury": get_fact_injury,
        "fact_depth_chart": get_fact_depth_chart,
        "fact_market": get_fact_market,
        "fact_game_market": get_fact_game_market,
        "player_usage_trend": get_player_usage_trend,
        "player_opportunity": get_player_opportunity,
        "player_efficiency": get_player_efficiency,
        "player_matchup": get_player_matchup,
        "player_environment": get_player_environment,
        "player_fantasy_profile": get_player_fantasy_profile,
        "fantasy_signal": get_fantasy_signal,
        "player_fundamentals": _refresh_player_fundamentals,
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
        import json

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
        # State tracking must not block ingestion.
        pass


def run_ingest(
    *,
    mode: str = MODE_INCREMENTAL,
    seasons: list[int] | None = None,
    layers: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    persist: bool = True,
    force_refresh: bool | None = None,
    fail_on_validation_error: bool = True,
) -> dict[str, Any]:
    """
    Run an ingestion job for the requested mode.

    historical  — bootstrap several seasons through all layers
    incremental — current season only (new week / live data)
    reprocess   — rebuild derived layers from stored facts

    After dims/facts are available, data-quality validation runs.
    Failed validation blocks derived layers when
    fail_on_validation_error=True.
    """

    from app.canonical.data_quality import (
        validate_ingested_seasons,
    )

    resolved_mode = normalize_ingest_mode(mode)
    definition = INGEST_MODES[resolved_mode]
    current = nflverse_source.get_current_season()

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
    job_key = f"{resolved_mode}:{','.join(map(str, resolved_seasons))}"
    results: list[dict[str, Any]] = []

    foundation_ids = set(
        PIPELINE_BY_LAYER[LAYER_DIMS]
        + PIPELINE_BY_LAYER[LAYER_FACTS]
    )
    derived_ids = set(
        PIPELINE_BY_LAYER[LAYER_ANALYTICS]
        + PIPELINE_BY_LAYER[LAYER_INTELLIGENCE]
        + PIPELINE_BY_LAYER[LAYER_DOMAIN]
    )
    foundation_queue = [
        dataset_id
        for dataset_id in ordered
        if dataset_id in foundation_ids
    ]
    derived_queue = [
        dataset_id
        for dataset_id in ordered
        if dataset_id in derived_ids
    ]

    def _run_queue(queue: list[str]) -> None:
        for dataset_id in queue:
            target_seasons = resolved_seasons
            if dataset_id in {"dim_team", "dim_player"}:
                target_seasons = [current]
            results.append(
                refresh_dataset(
                    dataset_id,
                    target_seasons,
                    force_refresh=refresh_flag,
                    persist=persist,
                )
            )

    # 1) Load / refresh foundation tables (dims + facts).
    _run_queue(foundation_queue)

    # 2) Validate before derived analytics/intelligence.
    needs_validation = bool(foundation_queue) or bool(derived_queue)
    validation: dict[str, Any] | None = None
    validation_blocked = False
    if needs_validation:
        report = validate_ingested_seasons(
            resolved_seasons,
            current_season=current,
            require_core_facts=True,
        )
        validation = report.to_dict()
        validation_blocked = (
            fail_on_validation_error and not report.passed
        )

    # 3) Derived layers only when validation passes (or skipped).
    if derived_queue and not validation_blocked:
        _run_queue(derived_queue)

    finished_at = datetime.now(timezone.utc)
    row_count_total = sum(
        int(item.get("row_count") or 0) for item in results
    )
    status = "succeeded"
    message = (
        "The data loaded successfully and passed validation."
        if validation is None
        else str(validation.get("message"))
    )
    if validation_blocked:
        status = "failed_validation"
        message = str(
            (validation or {}).get("message")
            or "The data loaded but failed validation."
        )
    elif validation and validation.get("status") == "passed_with_warnings":
        status = "succeeded_with_warnings"

    payload = {
        "mode": resolved_mode,
        "mode_label": definition["label"],
        "scope": season_scope if not seasons else "seasons",
        "seasons": resolved_seasons,
        "current_season": current,
        "historical_season_count": HISTORICAL_SEASON_COUNT,
        "layers": resolved_layers,
        "datasets_refreshed": len(results),
        "row_count_total": row_count_total,
        "force_refresh": refresh_flag,
        "persisted": persist,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": status,
        "message": message,
        "validation": validation,
        "validation_blocked_derived": validation_blocked,
        "results": results,
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
        status=status,
        started_at=started_at.replace(tzinfo=None),
        finished_at=finished_at.replace(tzinfo=None),
        row_count_total=row_count_total,
        detail={
            "datasets_refreshed": len(results),
            "force_refresh": refresh_flag,
            "message": message,
            "validation_status": (
                None if validation is None else validation.get("status")
            ),
            "validation_blocked_derived": validation_blocked,
            "validation": validation,
        },
    )
    return payload


def get_latest_ingestion_state() -> dict[str, Any] | None:
    """Return the most recently updated ingestion job, if any."""

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
            import json

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


def get_fantasy_data_quality(
    *,
    live: bool = True,
    seasons: list[int] | None = None,
) -> dict[str, Any]:
    """
    Data-quality summary for the fantasy_football foundation.

    Prefer a live validation pass against persisted canonical
    tables; fall back to the last ingestion_state report.
    """

    from app.canonical.data_quality import (
        validate_ingested_seasons,
    )

    current = nflverse_source.get_current_season()
    resolved_seasons = (
        resolve_scope_seasons(
            "seasons",
            seasons=seasons,
            current_season=current,
        )
        if seasons
        else historical_seasons(current_season=current)
    )
    latest = get_latest_ingestion_state()
    validation: dict[str, Any] | None = None
    report_source = "none"

    if live:
        try:
            report = validate_ingested_seasons(
                resolved_seasons,
                current_season=current,
                require_core_facts=True,
            )
            validation = report.to_dict()
            report_source = "live"
        except Exception:
            validation = None

    if validation is None and latest is not None:
        detail = latest.get("detail") or {}
        stored = detail.get("validation")
        if isinstance(stored, dict):
            validation = stored
            report_source = "ingestion_state"
        elif detail.get("message") or detail.get("validation_status"):
            validation = {
                "passed": latest.get("status")
                not in {"failed_validation", "failed"},
                "status": detail.get("validation_status")
                or latest.get("status")
                or "unknown",
                "message": detail.get("message")
                or "No detailed validation report stored.",
                "error_count": 0,
                "warning_count": 0,
                "seasons": list(latest.get("seasons") or []),
                "checks": [],
            }
            report_source = "ingestion_state"

    if validation is None:
        message = (
            "No fantasy football data has been validated yet. "
            "Run a historical or incremental load first."
        )
        status = "not_run"
        passed = False
    else:
        message = str(validation.get("message") or "")
        status = str(validation.get("status") or "unknown")
        passed = bool(validation.get("passed"))

    return {
        "source_id": "nflverse",
        "product": "fantasy_football",
        "label": "Fantasy Football",
        "description": (
            "Canonical ingestion checks for duplicates, IDs, "
            "season/week, positions, teams, stats, row counts, "
            "and referential integrity."
        ),
        "current_season": current,
        "seasons": resolved_seasons,
        "report_source": report_source,
        "status": status,
        "passed": passed,
        "message": message,
        "validation": validation,
        "latest_ingest": latest,
    }


def refresh_pipeline(
    *,
    scope: str = "current",
    seasons: list[int] | None = None,
    dataset_ids: list[str] | None = None,
    persist: bool = True,
    mode: str | None = None,
    layers: list[str] | None = None,
) -> dict[str, Any]:
    """
    Back-compat entrypoint.

    Prefer run_ingest(mode=...). scope='current' maps to incremental;
    scope='historical' maps to historical load.
    """

    if mode:
        return run_ingest(
            mode=mode,
            seasons=seasons,
            layers=layers,
            dataset_ids=dataset_ids,
            persist=persist,
        )

    normalized = str(scope or "").strip().lower()
    if normalized == "seasons":
        return run_ingest(
            mode=MODE_HISTORICAL if not seasons else MODE_INCREMENTAL,
            seasons=seasons,
            layers=layers,
            dataset_ids=dataset_ids,
            persist=persist,
        )

    return run_ingest(
        mode=normalize_ingest_mode(normalized),
        seasons=seasons,
        layers=layers,
        dataset_ids=dataset_ids,
        persist=persist,
    )


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
