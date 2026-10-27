"""
sportsdataverse data source (college football).

Canonical dimensions use InsightPilot-owned IDs (ip_*).
External provider IDs live only in source_ids.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

import pandas as pd

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


# Current season + three prior seasons for trends / backtesting.
HISTORICAL_SEASON_COUNT = 4
MIN_SEASON = 2003


@dataclass(frozen=True)
class SportsdataverseDatasetDefinition:
    id: str
    name: str
    description: str
    supports_seasons: bool
    domain: str
    domain_label: str
    default_seasons_count: int = 1
    history_lookback_seasons: int = 0
    notes: str | None = None


SPORTSDATAVERSE_DATASETS: list[SportsdataverseDatasetDefinition] = [
    SportsdataverseDatasetDefinition(
        id="dim_team",
        name="dim_team",
        description=(
            "Canonical CFB team dimension. InsightPilot-owned "
            "team_id with name, abbreviation, conference, "
            "subdivision, and stadium."
        ),
        supports_seasons=False,
        domain="canonical",
        domain_label="Canonical model — Core dimensions",
        notes=(
            "Primary key is ip_team_******. Stored in the "
            "college_football schema."
        ),
    ),
    SportsdataverseDatasetDefinition(
        id="dim_player",
        name="dim_player",
        description=(
            "Canonical CFB player dimension. InsightPilot-owned "
            "player_id with ESPN athlete IDs in source_ids."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core dimensions",
        notes=(
            "Built from sportsdataverse load_cfb_rosters. "
            "Resolution keys use cfb_athlete:*."
        ),
    ),
    SportsdataverseDatasetDefinition(
        id="dim_game",
        name="dim_game",
        description=(
            "Canonical CFB game dimension from schedules, "
            "including neutral-site and conference-game flags."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core dimensions",
        notes=(
            "Resolution keys use cfb_game:*. Stored in "
            "college_football.dim_game."
        ),
    ),
    SportsdataverseDatasetDefinition(
        id="fact_player_game",
        name="fact_player_game",
        description=(
            "Player box-score production by game — passing, "
            "rushing, and receiving counting stats."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Facts",
        notes="Grain is player_id × game_id.",
    ),
    SportsdataverseDatasetDefinition(
        id="fact_team_game",
        name="fact_team_game",
        description=(
            "Team offensive box scores — plays, pass/rush "
            "attempts, points, yards, and turnovers."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Facts",
        notes="Grain is team_id × game_id.",
    ),
    SportsdataverseDatasetDefinition(
        id="fact_defensive_game",
        name="fact_defensive_game",
        description=(
            "Points and yards allowed, derived by flipping "
            "opponent fact_team_game rows."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Facts",
        notes="Grain is defensive_team_id × game_id.",
    ),
    SportsdataverseDatasetDefinition(
        id="fact_game_market",
        name="fact_game_market",
        description=(
            "Game-level betting lines — spread, total, "
            "implied totals, and moneylines."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Facts",
        notes=(
            "Built from sportsdataverse CFB betting loaders."
        ),
    ),
]


def _apply_historical_defaults() -> None:
    updated: list[SportsdataverseDatasetDefinition] = []
    for dataset in SPORTSDATAVERSE_DATASETS:
        if not dataset.supports_seasons:
            updated.append(dataset)
            continue
        updated.append(
            replace(
                dataset,
                default_seasons_count=HISTORICAL_SEASON_COUNT,
            )
        )
    SPORTSDATAVERSE_DATASETS[:] = updated


_apply_historical_defaults()


def get_dataset_definition(
    dataset_id: str,
) -> SportsdataverseDatasetDefinition:
    for dataset in SPORTSDATAVERSE_DATASETS:
        if dataset.id == dataset_id:
            return dataset
    raise ValueError(
        f"Unknown sportsdataverse dataset: {dataset_id}"
    )


def list_datasets() -> list[dict[str, Any]]:
    return [
        {
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "supports_seasons": dataset.supports_seasons,
            "default_seasons_count": (
                dataset.default_seasons_count
            ),
            "history_lookback_seasons": (
                dataset.history_lookback_seasons
            ),
            "historical_season_count": HISTORICAL_SEASON_COUNT,
            "domain": dataset.domain,
            "domain_label": dataset.domain_label,
            "notes": dataset.notes,
        }
        for dataset in SPORTSDATAVERSE_DATASETS
    ]


def get_current_season() -> int:
    from sportsdataverse.cfb import most_recent_cfb_season

    return int(most_recent_cfb_season())


def normalize_seasons(
    seasons: list[int] | None,
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> list[int]:
    current = get_current_season()

    if not dataset.supports_seasons:
        return [current]

    if not seasons:
        count = max(1, dataset.default_seasons_count)
        start = max(MIN_SEASON, current - count + 1)
        return list(range(start, current + 1))

    normalized = sorted(
        {
            int(season)
            for season in seasons
            if MIN_SEASON <= int(season) <= current
        }
    )
    if not normalized:
        raise ValueError(
            f"Seasons must be between {MIN_SEASON} and {current}."
        )
    return normalized


def _load_dim_team(
    seasons: list[int],
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> pd.DataFrame:
    del seasons, dataset
    return get_dim_team(force_refresh=False, persist=False)


def _load_dim_player(
    seasons: list[int],
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_dim_player(
        seasons=seasons,
        force_refresh=False,
        persist=False,
    )


def _load_dim_game(
    seasons: list[int],
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_dim_game(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_player_game(
    seasons: list[int],
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_player_game(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_team_game(
    seasons: list[int],
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_team_game(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_defensive_game(
    seasons: list[int],
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_defensive_game(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_game_market(
    seasons: list[int],
    *,
    dataset: SportsdataverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_game_market(
        seasons,
        force_refresh=False,
        persist=False,
    )


_LOADERS: dict[
    str,
    Callable[
        [list[int], SportsdataverseDatasetDefinition],
        pd.DataFrame,
    ],
] = {
    "dim_team": _load_dim_team,
    "dim_player": _load_dim_player,
    "dim_game": _load_dim_game,
    "fact_player_game": _load_fact_player_game,
    "fact_team_game": _load_fact_team_game,
    "fact_defensive_game": _load_fact_defensive_game,
    "fact_game_market": _load_fact_game_market,
}


def load_dataset(
    dataset_id: str,
    seasons: list[int] | None = None,
) -> tuple[
    pd.DataFrame,
    SportsdataverseDatasetDefinition,
    list[int],
]:
    dataset = get_dataset_definition(dataset_id)
    resolved_seasons = normalize_seasons(
        seasons,
        dataset=dataset,
    )
    loader = _LOADERS[dataset.id]
    frame = loader(resolved_seasons, dataset=dataset)

    if frame is None or frame.empty:
        raise ValueError(
            f"No rows returned for sportsdataverse dataset "
            f"'{dataset.id}' (seasons={resolved_seasons})."
        )

    return frame, dataset, resolved_seasons


def infer_field_data_type(
    column_name: str,
    sample_value: Any,
) -> str:
    name = str(column_name).lower()

    if any(token in name for token in ("date", "dob", "birth")):
        return "date"

    if sample_value is None or (
        isinstance(sample_value, float)
        and pd.isna(sample_value)
    ):
        return "string"

    if isinstance(sample_value, bool):
        return "boolean"

    if isinstance(sample_value, int) and not isinstance(
        sample_value,
        bool,
    ):
        return "integer"

    if isinstance(sample_value, float):
        return "number"

    text = str(sample_value).strip()
    if not text:
        return "string"

    if text.lower() in {"true", "false", "yes", "no"}:
        return "boolean"

    try:
        int(text)
        return "integer"
    except ValueError:
        pass

    try:
        float(text)
        return "number"
    except ValueError:
        pass

    return "string"


def dataframe_fields(
    df: pd.DataFrame,
) -> list[dict[str, str]]:
    sample_row = df.iloc[0].to_dict() if len(df) > 0 else {}
    fields: list[dict[str, str]] = []
    for column in df.columns.tolist():
        name = str(column)
        sample = sample_row.get(column)
        fields.append(
            {
                "name": name,
                "normalizedName": (
                    name.strip().lower().replace(" ", "_")
                ),
                "dataType": infer_field_data_type(name, sample),
            }
        )
    return fields


def build_prebuilt_mappings(
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for column in df.columns.tolist():
        name = str(column)
        mappings.append(
            {
                "requiredField": name,
                "uploadedField": name,
                "matchType": "exact",
                "confidence": 1,
                "required": False,
                "valid": True,
            }
        )
    return mappings


def sample_records(
    df: pd.DataFrame,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if limit < 1:
        return []
    sample = df.head(limit).copy()
    import json

    return json.loads(
        sample.to_json(
            orient="records",
            date_format="iso",
        )
    )


def source_label(
    dataset: SportsdataverseDatasetDefinition,
    seasons: list[int],
) -> str:
    season_label = (
        str(seasons[0])
        if len(seasons) == 1
        else f"{seasons[0]}-{seasons[-1]}"
    )
    return f"sportsdataverse - {dataset.name} ({season_label})"


def clear_all_cfb_caches() -> None:
    from app.canonical.cfb.dim_game import clear_dim_game_cache
    from app.canonical.cfb.dim_player import clear_dim_player_cache
    from app.canonical.cfb.dim_team import clear_dim_team_cache
    from app.canonical.cfb.fact_defensive_game import (
        clear_fact_defensive_game_cache,
    )
    from app.canonical.cfb.fact_game_market import (
        clear_fact_game_market_cache,
    )
    from app.canonical.cfb.fact_player_game import (
        clear_fact_player_game_cache,
    )
    from app.canonical.cfb.fact_team_game import (
        clear_fact_team_game_cache,
    )

    clear_dim_team_cache()
    clear_dim_player_cache()
    clear_dim_game_cache()
    clear_fact_player_game_cache()
    clear_fact_team_game_cache()
    clear_fact_defensive_game_cache()
    clear_fact_game_market_cache()
