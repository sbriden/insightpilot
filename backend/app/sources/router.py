"""
External data source API routes.

Provides catalog + preview + analyze endpoints for selectable
sources that do not require a CSV upload.
"""

from __future__ import annotations

import traceback

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.services.analysis import analyze_dataframe
from app.sources import data_lifecycle
from app.sources import nflverse as nflverse_source
from app.sources.schemas import (
    DfsSalaryUploadResponse,
    NflverseAnalyzeRequest,
    NflversePreviewRequest,
    NflverseRefreshRequest,
)


router = APIRouter()


@router.get("/")
def list_sources():
    return {
        "sources": [
            {
                "id": "csv",
                "name": "CSV upload",
                "description": (
                    "Upload a CSV file from your computer."
                ),
                "kind": "upload",
            },
            {
                "id": "nflverse",
                "name": "nflverse",
                "description": (
                    "Fantasy football foundation from "
                    "nflverse, starting with player "
                    "fundamentals and a universal player ID."
                ),
                "kind": "connector",
                "homepage": "https://nflverse.nflverse.com/",
            },
        ]
    }


@router.get("/nflverse/datasets")
def list_nflverse_datasets():
    try:
        current_season = nflverse_source.get_current_season()
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to reach nflverse data right now: "
                f"{exc}"
            ),
        ) from exc

    datasets = nflverse_source.list_datasets()
    historical = data_lifecycle.historical_seasons(
        current_season=current_season,
    )
    return {
        "source_id": "nflverse",
        "current_season": current_season,
        "historical_seasons": historical,
        "historical_season_count": (
            data_lifecycle.HISTORICAL_SEASON_COUNT
        ),
        "foundation": "fantasy_football",
        "datasets": datasets,
        "domains": [
            {
                "id": dataset["domain"],
                "label": dataset["domain_label"],
            }
            for dataset in datasets
        ],
        "available_seasons": list(
            range(1999, current_season + 1)
        ),
        "refresh_scopes": [
            "historical",
            "current",
            "seasons",
        ],
        "ingest_modes": data_lifecycle.list_ingest_modes(),
        "ingest_layers": list(data_lifecycle.LAYER_ORDER),
    }


@router.post("/nflverse/preview")
def preview_nflverse_dataset(
    request: NflversePreviewRequest,
    background_tasks: BackgroundTasks,
):
    from app.sources.fantasy.curated_explore import (
        curated_preview_payload,
        is_curated_explore_id,
    )

    if is_curated_explore_id(request.dataset_id):
        try:
            return curated_preview_payload(
                request.dataset_id,
                request.seasons or None,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            traceback.print_exc()
            raise HTTPException(
                status_code=502,
                detail=(
                    "Failed to load curated dataset: "
                    f"{exc}"
                ),
            ) from exc

    try:
        df, dataset, seasons = nflverse_source.load_dataset(
            request.dataset_id,
            request.seasons or None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to load nflverse dataset: "
                f"{exc}"
            ),
        ) from exc

    if dataset.id == "dim_team":
        from app.canonical import dim_team as dim_team_mod

        if (
            dim_team_mod.dim_team_count() == 0
            and dim_team_mod._DIM_TEAM_CACHE_WITH_KEYS is not None
            and not dim_team_mod._DIM_TEAM_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                dim_team_mod.upsert_dim_team,
                dim_team_mod._DIM_TEAM_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "dim_player":
        from app.canonical import dim_player as dim_player_mod
        from app.canonical import dim_team as dim_team_mod

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )

        if (
            dim_player_mod.dim_player_count() == 0
            and dim_player_mod._DIM_PLAYER_CACHE_WITH_KEYS is not None
            and not dim_player_mod._DIM_PLAYER_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                dim_player_mod.upsert_dim_player,
                dim_player_mod._DIM_PLAYER_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "dim_game":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import dim_team as dim_team_mod

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )

        if (
            dim_game_mod.dim_game_count() == 0
            and dim_game_mod._DIM_GAME_CACHE_WITH_KEYS is not None
            and not dim_game_mod._DIM_GAME_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                dim_game_mod.upsert_dim_game,
                dim_game_mod._DIM_GAME_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_player_game":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import dim_player as dim_player_mod
        from app.canonical import dim_team as dim_team_mod
        from app.canonical import (
            fact_player_game as fact_player_game_mod,
        )

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )
        if dim_player_mod.dim_player_count() == 0:
            background_tasks.add_task(
                lambda: dim_player_mod.build_dim_player(
                    persist=True
                )
            )
        if dim_game_mod.dim_game_count() == 0:
            background_tasks.add_task(
                lambda: dim_game_mod.build_dim_game(
                    seasons or [nflverse_source.get_current_season()],
                    persist=True,
                )
            )

        if (
            fact_player_game_mod.fact_player_game_count() == 0
            and fact_player_game_mod._FACT_PLAYER_GAME_CACHE_WITH_KEYS
            is not None
            and not fact_player_game_mod._FACT_PLAYER_GAME_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_player_game_mod.upsert_fact_player_game,
                fact_player_game_mod._FACT_PLAYER_GAME_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_player_usage":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import dim_player as dim_player_mod
        from app.canonical import dim_team as dim_team_mod
        from app.canonical import (
            fact_player_usage as fact_player_usage_mod,
        )

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )
        if dim_player_mod.dim_player_count() == 0:
            background_tasks.add_task(
                lambda: dim_player_mod.build_dim_player(
                    persist=True
                )
            )
        if dim_game_mod.dim_game_count() == 0:
            background_tasks.add_task(
                lambda: dim_game_mod.build_dim_game(
                    seasons or [nflverse_source.get_current_season()],
                    persist=True,
                )
            )

        if (
            fact_player_usage_mod.fact_player_usage_count() == 0
            and fact_player_usage_mod._FACT_PLAYER_USAGE_CACHE_WITH_KEYS
            is not None
            and not fact_player_usage_mod._FACT_PLAYER_USAGE_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_player_usage_mod.upsert_fact_player_usage,
                fact_player_usage_mod._FACT_PLAYER_USAGE_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_player_efficiency":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import dim_player as dim_player_mod
        from app.canonical import dim_team as dim_team_mod
        from app.canonical import (
            fact_player_efficiency as fact_player_efficiency_mod,
        )

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )
        if dim_player_mod.dim_player_count() == 0:
            background_tasks.add_task(
                lambda: dim_player_mod.build_dim_player(
                    persist=True
                )
            )
        if dim_game_mod.dim_game_count() == 0:
            background_tasks.add_task(
                lambda: dim_game_mod.build_dim_game(
                    seasons or [nflverse_source.get_current_season()],
                    persist=True,
                )
            )

        if (
            fact_player_efficiency_mod.fact_player_efficiency_count()
            == 0
            and fact_player_efficiency_mod._FACT_PLAYER_EFFICIENCY_CACHE_WITH_KEYS
            is not None
            and not fact_player_efficiency_mod._FACT_PLAYER_EFFICIENCY_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_player_efficiency_mod.upsert_fact_player_efficiency,
                fact_player_efficiency_mod._FACT_PLAYER_EFFICIENCY_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_team_game":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import dim_team as dim_team_mod
        from app.canonical import (
            fact_team_game as fact_team_game_mod,
        )

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )
        if dim_game_mod.dim_game_count() == 0:
            background_tasks.add_task(
                lambda: dim_game_mod.build_dim_game(
                    seasons or [nflverse_source.get_current_season()],
                    persist=True,
                )
            )

        if (
            fact_team_game_mod.fact_team_game_count() == 0
            and fact_team_game_mod._FACT_TEAM_GAME_CACHE_WITH_KEYS
            is not None
            and not fact_team_game_mod._FACT_TEAM_GAME_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_team_game_mod.upsert_fact_team_game,
                fact_team_game_mod._FACT_TEAM_GAME_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_defensive_game":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import dim_team as dim_team_mod
        from app.canonical import (
            fact_defensive_game as fact_defensive_game_mod,
        )

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )
        if dim_game_mod.dim_game_count() == 0:
            background_tasks.add_task(
                lambda: dim_game_mod.build_dim_game(
                    seasons or [nflverse_source.get_current_season()],
                    persist=True,
                )
            )

        if (
            fact_defensive_game_mod.fact_defensive_game_count() == 0
            and fact_defensive_game_mod._FACT_DEFENSIVE_GAME_CACHE_WITH_KEYS
            is not None
            and not fact_defensive_game_mod._FACT_DEFENSIVE_GAME_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_defensive_game_mod.upsert_fact_defensive_game,
                fact_defensive_game_mod._FACT_DEFENSIVE_GAME_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_injury":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import dim_player as dim_player_mod
        from app.canonical import dim_team as dim_team_mod
        from app.canonical import (
            fact_injury as fact_injury_mod,
        )

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )
        if dim_player_mod.dim_player_count() == 0:
            background_tasks.add_task(
                lambda: dim_player_mod.build_dim_player(
                    persist=True
                )
            )
        if dim_game_mod.dim_game_count() == 0:
            background_tasks.add_task(
                lambda: dim_game_mod.build_dim_game(
                    seasons or [nflverse_source.get_current_season()],
                    persist=True,
                )
            )

        if (
            fact_injury_mod.fact_injury_count() == 0
            and fact_injury_mod._FACT_INJURY_CACHE_WITH_KEYS
            is not None
            and not fact_injury_mod._FACT_INJURY_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_injury_mod.upsert_fact_injury,
                fact_injury_mod._FACT_INJURY_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_depth_chart":
        from app.canonical import dim_player as dim_player_mod
        from app.canonical import dim_team as dim_team_mod
        from app.canonical import (
            fact_depth_chart as fact_depth_chart_mod,
        )

        if dim_team_mod.dim_team_count() == 0:
            background_tasks.add_task(
                lambda: dim_team_mod.build_dim_team(persist=True)
            )
        if dim_player_mod.dim_player_count() == 0:
            background_tasks.add_task(
                lambda: dim_player_mod.build_dim_player(
                    persist=True
                )
            )

        if (
            fact_depth_chart_mod.fact_depth_chart_count() == 0
            and fact_depth_chart_mod._FACT_DEPTH_CHART_CACHE_WITH_KEYS
            is not None
            and not fact_depth_chart_mod._FACT_DEPTH_CHART_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_depth_chart_mod.upsert_fact_depth_chart,
                fact_depth_chart_mod._FACT_DEPTH_CHART_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_market":
        from app.canonical import dim_player as dim_player_mod
        from app.canonical import (
            fact_market as fact_market_mod,
        )

        if dim_player_mod.dim_player_count() == 0:
            background_tasks.add_task(
                lambda: dim_player_mod.build_dim_player(
                    persist=True
                )
            )

        if (
            fact_market_mod.fact_market_count() == 0
            and fact_market_mod._FACT_MARKET_CACHE_WITH_KEYS
            is not None
            and not fact_market_mod._FACT_MARKET_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_market_mod.upsert_fact_market,
                fact_market_mod._FACT_MARKET_CACHE_WITH_KEYS.copy(),
            )

    if dataset.id == "fact_game_market":
        from app.canonical import dim_game as dim_game_mod
        from app.canonical import (
            fact_game_market as fact_game_market_mod,
        )

        if dim_game_mod.dim_game_count() == 0:
            background_tasks.add_task(
                lambda: dim_game_mod.build_dim_game(
                    seasons or [nflverse_source.get_current_season()],
                    persist=True,
                )
            )

        if (
            fact_game_market_mod.fact_game_market_count() == 0
            and fact_game_market_mod._FACT_GAME_MARKET_CACHE_WITH_KEYS
            is not None
            and not fact_game_market_mod._FACT_GAME_MARKET_CACHE_WITH_KEYS.empty
        ):
            background_tasks.add_task(
                fact_game_market_mod.upsert_fact_game_market,
                fact_game_market_mod._FACT_GAME_MARKET_CACHE_WITH_KEYS.copy(),
            )

    _ANALYTICS_PERSIST = {
        "player_usage_trend": (
            "app.canonical.analytics.player_usage_trend",
            "player_usage_trend_count",
            "upsert_player_usage_trend",
            "_CACHE_WITH_KEYS",
        ),
        "player_opportunity": (
            "app.canonical.analytics.player_opportunity",
            "player_opportunity_count",
            "upsert_player_opportunity",
            "_CACHE_WITH_KEYS",
        ),
        "player_efficiency": (
            "app.canonical.analytics.player_efficiency",
            "player_efficiency_count",
            "upsert_player_efficiency",
            "_CACHE_WITH_KEYS",
        ),
        "player_matchup": (
            "app.canonical.analytics.player_matchup",
            "player_matchup_count",
            "upsert_player_matchup",
            "_CACHE_WITH_KEYS",
        ),
        "player_environment": (
            "app.canonical.analytics.player_environment",
            "player_environment_count",
            "upsert_player_environment",
            "_CACHE_WITH_KEYS",
        ),
        "player_fantasy_profile": (
            "app.canonical.analytics.player_fantasy_profile",
            "player_fantasy_profile_count",
            "upsert_player_fantasy_profile",
            "_CACHE_WITH_KEYS",
        ),
        "fantasy_signal": (
            "app.canonical.analytics.fantasy_signal",
            "fantasy_signal_count",
            "upsert_fantasy_signal",
            "_CACHE_WITH_KEYS",
        ),
    }
    if dataset.id in _ANALYTICS_PERSIST:
        import importlib

        module_path, count_name, upsert_name, cache_name = (
            _ANALYTICS_PERSIST[dataset.id]
        )
        analytics_mod = importlib.import_module(module_path)
        count_fn = getattr(analytics_mod, count_name)
        upsert_fn = getattr(analytics_mod, upsert_name)
        cache_frame = getattr(analytics_mod, cache_name, None)
        if (
            count_fn() == 0
            and cache_frame is not None
            and not cache_frame.empty
        ):
            background_tasks.add_task(
                upsert_fn,
                cache_frame.copy(),
            )

    label = nflverse_source.source_label(dataset, seasons)
    sample_rows = nflverse_source.sample_records(
        df,
        limit=100,
    )
    prebuilt_mappings = (
        nflverse_source.build_prebuilt_mappings(df)
    )

    return {
        "source_id": "nflverse",
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "seasons": seasons,
        "label": label,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "fields": nflverse_source.dataframe_fields(df),
        "sample_rows": sample_rows,
        "sample_row_count": len(sample_rows),
        "pre_mapped": True,
        "prebuilt_mappings": prebuilt_mappings,
        "notes": dataset.notes,
    }


@router.post("/nflverse/analyze")
def analyze_nflverse_dataset(
    request: NflverseAnalyzeRequest,
):
    product_ids = [
        str(product_id).strip()
        for product_id in request.product_ids
        if str(product_id).strip()
    ]

    if not product_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one data product must be selected."
            ),
        )

    dataset_id = request.dataset_id
    seasons = list(request.seasons or [])
    # Fantasy Football product expects fantasy_signal grain.
    # Scope to the current season so create-flow analyze does
    # not profile multi-year signal history.
    if "fantasy_football" in product_ids:
        dataset_id = "fantasy_signal"
        try:
            current = nflverse_source.get_current_season()
        except Exception:
            current = None
        if current is not None:
            seasons = [int(current)]
        elif seasons:
            seasons = [max(int(s) for s in seasons)]

    try:
        df, dataset, seasons = nflverse_source.load_dataset(
            dataset_id,
            seasons or None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to load nflverse dataset: "
                f"{exc}"
            ),
        ) from exc

    if (
        "fantasy_football" in product_ids
        and not df.empty
        and "season" in df.columns
        and "week" in df.columns
    ):
        # Keep the latest week only — enough for actionable
        # signals without scanning every historical week.
        season_num = pd.to_numeric(
            df["season"],
            errors="coerce",
        )
        week_num = pd.to_numeric(
            df["week"],
            errors="coerce",
        )
        latest_season = season_num.max()
        latest_week = week_num[
            season_num == latest_season
        ].max()
        df = df[
            (season_num == latest_season)
            & (week_num == latest_week)
        ].reset_index(drop=True)

    label = nflverse_source.source_label(dataset, seasons)
    season_token = (
        str(seasons[0])
        if len(seasons) == 1
        else f"{seasons[0]}-{seasons[-1]}"
    )
    dataset_identity = (
        f"nflverse:{dataset.id}:{season_token}"
    )

    mappings = request.mappings or []
    if not mappings:
        mappings = nflverse_source.build_prebuilt_mappings(df)

    try:
        context = analyze_dataframe(
            df,
            field_mappings=mappings,
            selected_product_ids=product_ids,
            dataset_id=dataset_identity,
            dataset_identity=dataset_identity,
            source_dataset=label,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to analyze nflverse dataset: "
                f"{exc}"
            ),
        ) from exc

    return context.to_api_response()


@router.post("/nflverse/refresh")
def refresh_nflverse_data(
    request: NflverseRefreshRequest,
):
    """
    Run a fantasy data ingestion job.

    Modes:
      historical  — one-time multi-season load
      incremental — current-season update (new week data)
      reprocess   — rebuild derived metrics/signals from
                    facts already stored in Postgres
    """

    try:
        result = data_lifecycle.refresh_pipeline(
            mode=request.mode,
            scope=request.scope,
            seasons=request.seasons or None,
            layers=request.layers or None,
            dataset_ids=request.dataset_ids or None,
            persist=request.persist,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to refresh nflverse data: "
                f"{exc}"
            ),
        ) from exc

    return {
        "source_id": "nflverse",
        **result,
    }


@router.get("/nflverse/players")
def list_nflverse_players(
    q: str = "",
    position: str | None = None,
    team: str | None = None,
    limit: int = 500,
    scoring: str = "ppr",
):
    """
    List fantasy skill-position players for Player Overview.
    """

    from app.analysis.insights.player_snapshot import (
        list_fantasy_players,
    )

    try:
        players = list_fantasy_players(
            query=q,
            position=position,
            team=team,
            limit=max(1, min(int(limit), 2000)),
            scoring=scoring,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to list fantasy players: "
                f"{exc}"
            ),
        ) from exc

    return {
        "players": players,
        "count": len(players),
        "scoring": scoring,
    }


@router.get("/nflverse/teams")
def list_nflverse_teams():
    """List NFL franchises for Team Stats."""

    from app.analysis.insights.team_stats import (
        list_fantasy_teams,
    )

    try:
        teams = list_fantasy_teams()
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list fantasy teams: {exc}",
        ) from exc

    return {
        "teams": teams,
        "count": len(teams),
    }


@router.get("/nflverse/teams/{team}/stats")
def get_nflverse_team_stats(
    team: str,
    season: int | None = None,
):
    """
    Season leaders and depth chart for one franchise.
    """

    from app.analysis.insights.team_stats import (
        get_team_stats,
    )

    try:
        stats = get_team_stats(team, season=season)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to load team stats: {exc}",
        ) from exc

    if stats is None:
        raise HTTPException(
            status_code=404,
            detail=f"Team not found: {team}",
        )

    return {"stats": stats}


@router.get("/nflverse/players/search")
def search_nflverse_players(
    q: str = "",
    limit: int = 20,
):
    """
    Search canonical players for Player Overview selection.
    """

    from app.analysis.insights.player_snapshot import (
        search_players,
    )

    try:
        players = search_players(
            q,
            limit=max(1, min(int(limit), 50)),
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to search fantasy players: "
                f"{exc}"
            ),
        ) from exc

    return {
        "query": q,
        "players": players,
        "count": len(players),
    }


@router.get("/nflverse/players/{player_id}/stats")
def get_nflverse_player_stats(
    player_id: str,
    season: int | None = None,
    scoring: str = "ppr",
):
    """
    Fantasy-oriented Stats tab payload for one player.
    """

    from app.analysis.insights.player_stats import (
        build_player_stats,
    )

    try:
        stats = build_player_stats(
            player_id,
            season=season,
            scoring=scoring,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build player stats: {exc}",
        ) from exc

    if stats is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player not found: {player_id}",
        )

    return {"stats": stats}


@router.get("/nflverse/players/{player_id}/usage")
def get_nflverse_player_usage(
    player_id: str,
    season: int | None = None,
    period: str = "last_8",
    scoring: str = "ppr",
):
    """
    Usage & Trends tab payload for one player.
    """

    from app.analysis.insights.player_usage import (
        build_player_usage,
    )

    try:
        usage = build_player_usage(
            player_id,
            season=season,
            period=period,
            scoring=scoring,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build player usage: {exc}",
        ) from exc

    if usage is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player not found: {player_id}",
        )

    return {"usage": usage}


@router.get("/nflverse/players/{player_id}/matchups")
def get_nflverse_player_matchups(
    player_id: str,
    season: int | None = None,
    view: str = "next_8",
    scoring: str = "ppr",
):
    """
    Matchups tab payload for one player.
    """

    from app.analysis.insights.player_matchups import (
        build_player_matchups,
    )

    try:
        matchups = build_player_matchups(
            player_id,
            season=season,
            view=view,
            scoring=scoring,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build player matchups: {exc}",
        ) from exc

    if matchups is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player not found: {player_id}",
        )

    return {"matchups": matchups}


@router.get("/nflverse/players/{player_id}/news")
def get_nflverse_player_news(
    player_id: str,
    season: int | None = None,
    lookback: str = "last_30d",
    category: str = "all",
    impact: str = "all",
):
    """
    News tab payload — structured developments from
    injury reports and depth-chart changes (not an
    external article feed).
    """

    from app.analysis.insights.player_news import (
        build_player_news,
    )

    try:
        news = build_player_news(
            player_id,
            season=season,
            lookback=lookback,
            category=category,
            impact=impact,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build player news: {exc}",
        ) from exc

    if news is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player not found: {player_id}",
        )

    return {"news": news}


@router.get("/nflverse/players/{player_id}/snapshot")
def get_nflverse_player_snapshot(
    player_id: str,
    season: int | None = None,
    week: int | None = None,
):
    """
    Build a Player Snapshot for one selected player from
    engine profile + fantasy_signal evidence.
    """

    from app.analysis.insights.player_snapshot import (
        get_player_snapshot_by_id,
    )

    try:
        snapshot = get_player_snapshot_by_id(
            player_id,
            season=season,
            week=week,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to build player snapshot: "
                f"{exc}"
            ),
        ) from exc

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"Player '{player_id}' not found.",
        )

    return {
        "snapshot": snapshot,
    }


@router.get("/nflverse/dfs/sites")
def list_dfs_sites():
    """Supported DFS platforms and roster rules."""

    from app.analysis.insights.dfs.sites import list_sites

    return {"sites": list_sites()}


@router.post(
    "/nflverse/dfs/salaries/upload",
    response_model=DfsSalaryUploadResponse,
)
async def upload_dfs_salaries(
    file: UploadFile = File(...),
    site: str = Form("draftkings"),
    contest_type: str = Form("classic"),
    season: int | None = Form(None),
    week: int | None = Form(None),
):
    """
    Upload a DraftKings or FanDuel salary CSV.

    Matches rows on team + position with a fuzzy name match,
    then persists salaries for reuse by slate builds / optimize.
    """

    from app.analysis.insights.dfs.salary_csv import (
        ingest_dfs_salary_csv,
    )
    from app.analysis.insights.dfs.slate import (
        _resolve_season,
        _resolve_week,
    )

    filename = file.filename or "salaries.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Upload a .csv salary export from DK or FD.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    resolved_season = _resolve_season(season)
    resolved_week = _resolve_week(
        week,
        season=resolved_season,
    )

    try:
        result = ingest_dfs_salary_csv(
            content,
            site=site,
            contest_type=contest_type,
            season=resolved_season,
            week=resolved_week,
            filename=filename,
            persist=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to ingest salary CSV: {exc}",
        ) from exc

    if result["matched"] == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No players matched. Check site/contest settings "
                "and that the CSV includes Name, Team, Position, "
                "and Salary columns."
            ),
        )

    return result


@router.get("/nflverse/dfs/weeks")
def list_nflverse_dfs_weeks(season: int | None = None):
    """Available NFL weeks for DFS slate selection."""

    from app.analysis.insights.dfs.slate import list_dfs_weeks

    try:
        return list_dfs_weeks(season=season)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list DFS weeks: {exc}",
        ) from exc


@router.get("/nflverse/dfs/slates")
def list_nflverse_dfs_slates(
    season: int | None = None,
    week: int | None = None,
    contest_type: str = "classic",
):
    """Available DFS slates for classic or showdown contests."""

    from app.analysis.insights.dfs.slate import list_dfs_slates

    try:
        slates = list_dfs_slates(
            season=season,
            week=week,
            contest_type=contest_type,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list DFS slates: {exc}",
        ) from exc
    return {"slates": slates, "count": len(slates)}


@router.get("/nflverse/dfs/slate/{slate_id}")
def get_nflverse_dfs_slate(
    slate_id: str,
    site: str = "draftkings",
    season: int | None = None,
    contest_type: str = "classic",
    scoring: str = "ppr",
    limit: int = 250,
):
    """Player pool for one DFS slate."""

    from app.analysis.insights.dfs.slate import build_dfs_slate

    try:
        slate = build_dfs_slate(
            slate_id,
            site=site,
            season=season,
            contest_type=contest_type,
            scoring=scoring,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build DFS slate: {exc}",
        ) from exc
    return {"slate": slate}


@router.post("/nflverse/dfs/optimize")
def optimize_nflverse_dfs_lineup(payload: dict):
    """
    Optimize a DFS lineup from InsightPilot slate signals.
    """

    from app.analysis.insights.dfs.optimize import (
        optimize_lineup,
    )

    try:
        result = optimize_lineup(
            slate_id=str(
                payload.get("slate_id") or "nfl-current-main"
            ),
            site=str(payload.get("site") or "draftkings"),
            contest_type=str(
                payload.get("contest_type") or "classic"
            ),
            risk=str(payload.get("risk") or "balanced"),
            strategy=payload.get("strategy"),
            locked_players=list(
                payload.get("locked_players") or []
            ),
            excluded_players=list(
                payload.get("excluded_players") or []
            ),
            min_salary=payload.get("min_salary"),
            max_ownership=payload.get("max_ownership"),
            season=payload.get("season"),
            scoring=str(payload.get("scoring") or "ppr"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to optimize DFS lineup: {exc}",
        ) from exc
    return result


@router.post("/nflverse/dfs/portfolio")
def generate_nflverse_dfs_portfolio(payload: dict):
    """
    Generate a diversified multi-lineup DFS portfolio.
    """

    from app.analysis.insights.dfs.portfolio import (
        generate_portfolio,
    )

    try:
        result = generate_portfolio(
            slate_id=str(
                payload.get("slate_id") or "nfl-current-main"
            ),
            site=str(payload.get("site") or "draftkings"),
            contest_type=str(
                payload.get("contest_type") or "classic"
            ),
            lineup_count=int(payload.get("lineup_count") or 20),
            strategy=str(payload.get("strategy") or "balanced"),
            risk=str(payload.get("risk") or "balanced"),
            max_lineup_similarity=payload.get(
                "max_lineup_similarity"
            ),
            min_unique_players=payload.get("min_unique_players"),
            default_max_exposure=payload.get(
                "default_max_exposure"
            ),
            default_max_captain_exposure=payload.get(
                "default_max_captain_exposure"
            ),
            player_exposure=dict(
                payload.get("player_exposure") or {}
            ),
            locked_players=list(
                payload.get("locked_players") or []
            ),
            excluded_players=list(
                payload.get("excluded_players") or []
            ),
            season=payload.get("season"),
            scoring=str(payload.get("scoring") or "ppr"),
            seed=payload.get("seed"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                f"Failed to generate DFS portfolio: {exc}"
            ),
        ) from exc
    return result


@router.get("/nflverse/betting/weeks")
def list_betting_weeks(
    season: int | None = None,
    sport: str = "NFL",
):
    """Available NFL weeks with betting market coverage."""

    from app.analysis.insights.betting import (
        list_betting_weeks as _list_weeks,
    )

    try:
        return _list_weeks(season=season, sport=sport)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list betting weeks: {exc}",
        ) from exc


@router.get("/nflverse/betting/slate")
def get_betting_slate(
    season: int | None = None,
    week: int | None = None,
    sport: str = "NFL",
):
    """
    NFL Sports Betting slate for a week.

    Returns events, expanded markets (spread / total /
    moneyline), model vs market comparisons, and signals.
    """

    from app.analysis.insights.betting import (
        build_betting_slate,
    )

    try:
        return build_betting_slate(
            season=season,
            week=week,
            sport=sport,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build betting slate: {exc}",
        ) from exc


@router.get("/nflverse/betting/event/{event_id}")
def get_betting_event_detail(
    event_id: str,
    season: int | None = None,
):
    """Single-event betting analysis payload."""

    from app.analysis.insights.betting import (
        get_betting_event,
    )

    try:
        result = get_betting_event(
            event_id,
            season=season,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to load betting event: {exc}",
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Betting event not found: {event_id}",
        )
    return result


@router.get("/nflverse/betting/results")
def get_nflverse_betting_results(
    season: int | None = None,
    week: int | None = None,
    sport: str = "NFL",
):
    """
    Auto-settled model vs actual results for all markets
    once final scores are available.
    """

    del sport
    from app.analysis.insights.betting import (
        build_betting_results,
    )

    try:
        return build_betting_results(
            season=season,
            week=week,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build betting results: {exc}",
        ) from exc


@router.post("/nflverse/betting/portfolio/generate")
def generate_nflverse_betting_portfolio(payload: dict):
    """
    Generate an open-position portfolio from total exposure and
    per-game risk exposure against the current betting slate.
    """

    from app.analysis.insights.betting import (
        generate_betting_portfolio,
    )

    try:
        return generate_betting_portfolio(
            total_exposure=float(
                payload.get("total_exposure") or 0
            ),
            risk_exposure=float(
                payload.get("risk_exposure") or 0
            ),
            season=payload.get("season"),
            week=payload.get("week"),
            risk=str(payload.get("risk") or "balanced"),
            market_types=list(
                payload.get("market_types") or []
            )
            or None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to generate betting portfolio: "
                f"{exc}"
            ),
        ) from exc


@router.post("/nflverse/betting/portfolio/analyze")
def analyze_nflverse_betting_portfolio(payload: dict):
    """
    Refresh saved betting positions against the current slate
    and return portfolio analytics (exposure, correlation,
    assumptions, health).
    """

    from app.analysis.insights.betting import (
        analyze_betting_portfolio,
    )

    try:
        return analyze_betting_portfolio(
            list(payload.get("positions") or []),
            season=payload.get("season"),
            week=payload.get("week"),
            status_filter=str(
                payload.get("status_filter") or "open"
            ),
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to analyze betting portfolio: "
                f"{exc}"
            ),
        ) from exc


@router.post("/nflverse/betting/portfolio/position")
def create_nflverse_betting_position(payload: dict):
    """Create a portfolio position from a market snapshot."""

    from app.analysis.insights.betting import (
        create_position_from_market,
    )

    market = dict(payload.get("market") or {})
    if not market.get("market_id"):
        raise HTTPException(
            status_code=400,
            detail="market.market_id is required",
        )
    try:
        return create_position_from_market(
            market,
            exposure=float(payload.get("exposure") or 25.0),
            notes=payload.get("notes"),
            sportsbook=payload.get("sportsbook"),
            entry_price=payload.get("entry_price"),
            entry_line=payload.get("entry_line"),
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create betting position: {exc}",
        ) from exc


@router.get("/nflverse/quality")
def get_nflverse_data_quality(
    live: bool = True,
):
    """
    Fantasy football canonical data-quality report.

    By default runs live checks against persisted tables.
    Falls back to the last ingestion_state validation when
    live validation is unavailable.
    """

    try:
        return data_lifecycle.get_fantasy_data_quality(
            live=live,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to load fantasy data quality: "
                f"{exc}"
            ),
        ) from exc
