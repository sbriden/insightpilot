"""
nflverse data source.

Fantasy-football-first curated domains built from nflverse.
Canonical dimensions use InsightPilot-owned IDs (ip_player_*).
External provider IDs live only in source_ids.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

import pandas as pd

from app.canonical.dim_game import (
    get_dim_game,
)
from app.canonical.dim_player import (
    get_dim_player,
)
from app.canonical.dim_team import (
    get_dim_team,
)
from app.canonical.fact_defensive_game import (
    get_fact_defensive_game,
)
from app.canonical.fact_depth_chart import (
    get_fact_depth_chart,
)
from app.canonical.fact_injury import (
    get_fact_injury,
)
from app.canonical.fact_game_market import (
    get_fact_game_market,
)
from app.canonical.fact_market import (
    get_fact_market,
)
from app.canonical.fact_player_efficiency import (
    get_fact_player_efficiency,
)
from app.canonical.fact_player_game import (
    get_fact_player_game,
)
from app.canonical.fact_player_usage import (
    get_fact_player_usage,
)
from app.canonical.fact_team_game import (
    get_fact_team_game,
)
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
from app.sources.fantasy.player_fundamentals import (
    build_player_fundamentals,
)


# Current season + three prior seasons for trends / backtesting.
HISTORICAL_SEASON_COUNT = 4


@dataclass(frozen=True)
class NflverseDatasetDefinition:
    id: str
    name: str
    description: str
    supports_seasons: bool
    domain: str
    domain_label: str
    default_seasons_count: int = 1
    history_lookback_seasons: int = 0
    notes: str | None = None


NFLVERSE_DATASETS: list[NflverseDatasetDefinition] = [
    NflverseDatasetDefinition(
        id="dim_team",
        name="dim_team",
        description=(
            "Canonical team dimension. InsightPilot-owned "
            "team_id with name, abbreviation, conference, "
            "division, and stadium."
        ),
        supports_seasons=False,
        domain="canonical",
        domain_label="Canonical model — Core dimensions",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Primary key is ip_team_******. Stored in the "
            "fantasy_football schema."
        ),
    ),
    NflverseDatasetDefinition(
        id="dim_player",
        name="dim_player",
        description=(
            "Canonical player dimension. InsightPilot-owned "
            "player_id with external provider IDs in source_ids."
        ),
        supports_seasons=False,
        domain="canonical",
        domain_label="Canonical model — Core dimensions",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Primary key is ip_player_********. Never use gsis_id "
            "or other external IDs as the primary key. Stored in "
            "the fantasy_football schema."
        ),
    ),
    NflverseDatasetDefinition(
        id="dim_game",
        name="dim_game",
        description=(
            "Canonical game dimension. Every NFL game with "
            "InsightPilot-owned game_id, season/week, teams, "
            "scores, and status."
        ),
        supports_seasons=False,
        domain="canonical",
        domain_label="Canonical model — Core dimensions",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Primary key is ip_game_********. Never use nflverse "
            "game_id as the primary key. home_team_id / "
            "away_team_id reference dim_team. Stored in the "
            "fantasy_football schema."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_player_game",
        name="fact_player_game",
        description=(
            "Core fantasy production table. One row per "
            "player × game with passing, rushing, and "
            "receiving stats."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Grain is player_id × game_id (InsightPilot-owned). "
            "Built from nflverse weekly player stats. Stored in "
            "the fantasy_football schema."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_player_usage",
        name="fact_player_usage",
        description=(
            "Position-aware opportunity table. One row per "
            "player × game with snaps, routes, and RB/WR/TE/QB "
            "usage metrics (nullable by position)."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Grain is player_id × game_id. Built from weekly "
            "stats, snap counts, and play-by-play. Single table "
            "for all skill positions — metrics may be null."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_player_efficiency",
        name="fact_player_efficiency",
        description=(
            "Efficiency rates per player × game. Kept separate "
            "from opportunity — yards per carry/target/route, "
            "catch rate, EPA rates, fantasy points per touch/route."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Rates only (no raw opportunity volume). Joins "
            "production stats with usage denominators like "
            "routes_run and dropbacks. Metrics may be null."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_team_game",
        name="fact_team_game",
        description=(
            "Team × game offensive environment — script, pace, "
            "EPA, red-zone efficiency, and turnovers surrounding "
            "the player."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Grain is team_id × game_id (InsightPilot-owned). "
            "Built from play-by-play + schedules. Stored in the "
            "fantasy_football schema."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_defensive_game",
        name="fact_defensive_game",
        description=(
            "Team × game defensive performance — points/yards/"
            "EPA allowed, pressure and sack rates, and "
            "receiving opportunity allowed."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Grain is defensive_team_id × game_id. Kept separate "
            "from offensive fact_team_game. Built from "
            "play-by-play + schedules."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_injury",
        name="fact_injury",
        description=(
            "Player injury reports as their own entity — "
            "injury type, practice/game status, and whether "
            "the player is expected to play."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Grain is player × week injury report. game_id is "
            "resolved from the team schedule when available. "
            "Stored in the fantasy_football schema."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_depth_chart",
        name="fact_depth_chart",
        description=(
            "Weekly depth chart for opportunity changes — "
            "team, player, position, depth_order, and role."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "role starts as starter/backup/returner/slot and can "
            "expand later (third_down, goal_line, outside). "
            "effective_date uses the team's game date that week."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_market",
        name="fact_market",
        description=(
            "External fantasy market separate from performance — "
            "rank, projection, ADP, and ownership by source."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Built from FantasyPros weekly rankings and draft ECR "
            "(via nflverse). Live snapshots stamped with the "
            "current season/week."
        ),
    ),
    NflverseDatasetDefinition(
        id="fact_game_market",
        name="fact_game_market",
        description=(
            "Game-level betting / environmental market — spread, "
            "over-under, and implied team totals."
        ),
        supports_seasons=True,
        domain="canonical",
        domain_label="Canonical model — Core facts",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Built from nflverse schedule lines (spread_line / "
            "total_line). source=nflverse_schedules. Separate "
            "from player fact_market."
        ),
    ),
    NflverseDatasetDefinition(
        id="player_fundamentals",
        name="Player fundamentals",
        description=(
            "Season-grained fantasy foundation joined to "
            "canonical dim_player (ip_player_*)."
        ),
        supports_seasons=True,
        domain="player_fundamentals",
        domain_label="Domain 1 — Player fundamentals",
        default_seasons_count=1,
        history_lookback_seasons=4,
        notes=(
            "player_id is the InsightPilot canonical ID from "
            "dim_player. External IDs remain in source systems."
        ),
    ),
    NflverseDatasetDefinition(
        id="player_usage_trend",
        name="player_usage_trend",
        description=(
            "Rolling usage intelligence — 3-week snap/target/"
            "rush/route shares plus week-over-week opportunity "
            "trend."
        ),
        supports_seasons=True,
        domain="analytics",
        domain_label="Analytical layer — Fantasy intelligence",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Derived from fact_player_usage. Separates raw "
            "opportunity facts from trend intelligence."
        ),
    ),
    NflverseDatasetDefinition(
        id="player_opportunity",
        name="player_opportunity",
        description=(
            "Weekly opportunity scores — overall, receiving, "
            "rushing, and red-zone opportunity."
        ),
        supports_seasons=True,
        domain="analytics",
        domain_label="Analytical layer — Fantasy intelligence",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Scored 0–100 from fact_player_usage shares and "
            "red-zone volume. Grain is player_id × season × week."
        ),
    ),
    NflverseDatasetDefinition(
        id="player_efficiency",
        name="player_efficiency",
        description=(
            "Weekly efficiency intelligence scores — overall, "
            "receiving, and rushing efficiency."
        ),
        supports_seasons=True,
        domain="analytics",
        domain_label="Analytical layer — Fantasy intelligence",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Distinct from fact_player_efficiency (raw rates). "
            "This table converts rates into fantasy intelligence "
            "scores."
        ),
    ),
    NflverseDatasetDefinition(
        id="player_matchup",
        name="player_matchup",
        description=(
            "Opponent matchup scores — pass, rush, and "
            "receiving matchup quality for the week."
        ),
        supports_seasons=True,
        domain="analytics",
        domain_label="Analytical layer — Fantasy intelligence",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Built from prior opponent defensive averages in "
            "fact_defensive_game. Higher = easier fantasy matchup."
        ),
    ),
    NflverseDatasetDefinition(
        id="player_environment",
        name="player_environment",
        description=(
            "Game environment expectations — team total, pace, "
            "and game-script lean for the player's team."
        ),
        supports_seasons=True,
        domain="analytics",
        domain_label="Analytical layer — Fantasy intelligence",
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Combines fact_game_market implied totals/spreads "
            "with fact_team_game pace. Grain is player × week."
        ),
    ),
    NflverseDatasetDefinition(
        id="player_fantasy_profile",
        name="player_fantasy_profile",
        description=(
            "InsightPilot proprietary weekly fantasy profile — "
            "production, opportunity, efficiency, trend, matchup, "
            "environment, risk, and fantasy value scores."
        ),
        supports_seasons=True,
        domain="intelligence",
        domain_label=(
            "InsightPilot intelligence — Proprietary profiles"
        ),
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "One row per player × season × week. Composes "
            "analytical-layer scores plus production and injury "
            "risk into fantasy_value_score."
        ),
    ),
    NflverseDatasetDefinition(
        id="fantasy_signal",
        name="fantasy_signal",
        description=(
            "Actionable InsightPilot signals — breakout, buy/sell, "
            "start/sit, waiver, regression, and opportunity surge/"
            "decline."
        ),
        supports_seasons=True,
        domain="intelligence",
        domain_label=(
            "InsightPilot intelligence — Proprietary profiles"
        ),
        default_seasons_count=1,
        history_lookback_seasons=0,
        notes=(
            "Zero-or-more signals per player × week. signal_id is "
            "InsightPilot-owned (ip_signal_*). Derived from "
            "player_fantasy_profile thresholds."
        ),
    ),
]


def _apply_historical_defaults() -> None:
    """Season-aware tables default to several seasons of history."""

    updated: list[NflverseDatasetDefinition] = []
    for dataset in NFLVERSE_DATASETS:
        if not dataset.supports_seasons:
            updated.append(dataset)
            continue

        lookback = dataset.history_lookback_seasons
        if (
            dataset.domain in {"analytics", "intelligence"}
            and lookback <= 0
        ):
            lookback = 1

        updated.append(
            replace(
                dataset,
                default_seasons_count=HISTORICAL_SEASON_COUNT,
                history_lookback_seasons=lookback,
            )
        )

    NFLVERSE_DATASETS[:] = updated


_apply_historical_defaults()


def get_dataset_definition(
    dataset_id: str,
) -> NflverseDatasetDefinition:
    for dataset in NFLVERSE_DATASETS:
        if dataset.id == dataset_id:
            return dataset

    raise ValueError(
        f"Unknown nflverse dataset: {dataset_id}"
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
        for dataset in NFLVERSE_DATASETS
    ]


def get_current_season() -> int:
    import nflreadpy as nfl

    return int(nfl.get_current_season())


def build_seasons_for_dataset(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> list[int]:
    """Expand requested seasons with dataset lookback for builds."""

    return _history_seasons_for(
        seasons,
        lookback=dataset.history_lookback_seasons,
    )


def filter_frame_to_seasons(
    frame: pd.DataFrame,
    seasons: list[int],
) -> pd.DataFrame:
    if frame is None or frame.empty or "season" not in frame.columns:
        return frame
    allowed = {int(season) for season in seasons}
    return frame[
        frame["season"].map(
            lambda value: (
                int(value) in allowed
                if value is not None and not pd.isna(value)
                else False
            )
        )
    ].reset_index(drop=True)


def normalize_seasons(
    seasons: list[int] | None,
    *,
    dataset: NflverseDatasetDefinition,
) -> list[int]:
    current = get_current_season()

    if not dataset.supports_seasons:
        return [current]

    if not seasons:
        count = max(1, dataset.default_seasons_count)
        return list(
            range(current - count + 1, current + 1)
        )

    normalized = sorted(
        {
            int(season)
            for season in seasons
            if 1999 <= int(season) <= current
        }
    )

    if not normalized:
        raise ValueError(
            f"Seasons must be between 1999 and {current}."
        )

    return normalized


def _history_seasons_for(
    seasons: list[int],
    *,
    lookback: int,
) -> list[int]:
    if lookback <= 0:
        return list(seasons)

    minimum = min(seasons) - lookback
    maximum = max(seasons)
    return list(range(max(1999, minimum), maximum + 1))


def _load_dim_team(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del seasons, dataset
    return get_dim_team(
        force_refresh=False,
        persist=False,
    )


def _load_dim_player(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del seasons, dataset
    # Cache/DB first. Do not block UI on a full upsert.
    return get_dim_player(
        force_refresh=False,
        persist=False,
    )


def _load_dim_game(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    # Prefer requested seasons; empty callers still get defaults
    # via normalize_seasons before this loader runs.
    return get_dim_game(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_with_lookback(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
    getter: Callable[..., pd.DataFrame],
) -> pd.DataFrame:
    build_seasons = build_seasons_for_dataset(
        seasons,
        dataset=dataset,
    )
    frame = getter(
        build_seasons,
        force_refresh=False,
        persist=False,
    )
    if dataset.history_lookback_seasons > 0:
        return filter_frame_to_seasons(frame, seasons)
    return frame


def _load_fact_player_game(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_player_game(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_player_usage(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_player_usage(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_player_efficiency(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_player_efficiency(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_team_game(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
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
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_defensive_game(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_injury(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_injury(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_depth_chart(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_depth_chart(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_market(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_market(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_fact_game_market(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    del dataset
    return get_fact_game_market(
        seasons,
        force_refresh=False,
        persist=False,
    )


def _load_player_fundamentals(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    history = _history_seasons_for(
        seasons,
        lookback=dataset.history_lookback_seasons,
    )
    return build_player_fundamentals(
        seasons,
        current_season=get_current_season(),
        history_seasons=history,
    )


def _load_player_usage_trend(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    return _load_with_lookback(
        seasons,
        dataset=dataset,
        getter=get_player_usage_trend,
    )


def _load_player_opportunity(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    return _load_with_lookback(
        seasons,
        dataset=dataset,
        getter=get_player_opportunity,
    )


def _load_player_efficiency_analytics(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    return _load_with_lookback(
        seasons,
        dataset=dataset,
        getter=get_player_efficiency,
    )


def _load_player_matchup(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    return _load_with_lookback(
        seasons,
        dataset=dataset,
        getter=get_player_matchup,
    )


def _load_player_environment(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    return _load_with_lookback(
        seasons,
        dataset=dataset,
        getter=get_player_environment,
    )


def _load_player_fantasy_profile(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    return _load_with_lookback(
        seasons,
        dataset=dataset,
        getter=get_player_fantasy_profile,
    )


def _load_fantasy_signal(
    seasons: list[int],
    *,
    dataset: NflverseDatasetDefinition,
) -> pd.DataFrame:
    return _load_with_lookback(
        seasons,
        dataset=dataset,
        getter=get_fantasy_signal,
    )


_LOADERS: dict[
    str,
    Callable[
        [list[int], NflverseDatasetDefinition],
        pd.DataFrame,
    ],
] = {
    "dim_team": _load_dim_team,
    "dim_player": _load_dim_player,
    "dim_game": _load_dim_game,
    "fact_player_game": _load_fact_player_game,
    "fact_player_usage": _load_fact_player_usage,
    "fact_player_efficiency": _load_fact_player_efficiency,
    "fact_team_game": _load_fact_team_game,
    "fact_defensive_game": _load_fact_defensive_game,
    "fact_injury": _load_fact_injury,
    "fact_depth_chart": _load_fact_depth_chart,
    "fact_market": _load_fact_market,
    "fact_game_market": _load_fact_game_market,
    "player_fundamentals": _load_player_fundamentals,
    "player_usage_trend": _load_player_usage_trend,
    "player_opportunity": _load_player_opportunity,
    "player_efficiency": _load_player_efficiency_analytics,
    "player_matchup": _load_player_matchup,
    "player_environment": _load_player_environment,
    "player_fantasy_profile": _load_player_fantasy_profile,
    "fantasy_signal": _load_fantasy_signal,
}


def load_dataset(
    dataset_id: str,
    seasons: list[int] | None = None,
) -> tuple[pd.DataFrame, NflverseDatasetDefinition, list[int]]:
    dataset = get_dataset_definition(dataset_id)
    resolved_seasons = normalize_seasons(
        seasons,
        dataset=dataset,
    )
    loader = _LOADERS[dataset.id]
    frame = loader(resolved_seasons, dataset=dataset)

    if frame is None or frame.empty:
        raise ValueError(
            f"No rows returned for nflverse dataset "
            f"'{dataset.id}' (seasons={resolved_seasons})."
        )

    return frame, dataset, resolved_seasons


def infer_field_data_type(
    column_name: str,
    sample_value: Any,
) -> str:
    name = str(column_name).lower()

    if any(
        token in name
        for token in ("date", "dob", "birth")
    ):
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

    if text.lower() in {
        "true",
        "false",
        "yes",
        "no",
    }:
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
    sample_row = (
        df.iloc[0].to_dict()
        if len(df) > 0
        else {}
    )

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
                "dataType": infer_field_data_type(
                    name,
                    sample,
                ),
            }
        )

    return fields




def build_prebuilt_mappings(
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Curated sources ship with canonical column names.
    Map each column onto itself so the create flow can
    skip manual field mapping.
    """

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
    """
    Return JSON-safe sample rows for UI preview tables.
    """

    if limit < 1:
        return []

    sample = df.head(limit).copy()

    # pandas to_json handles NaN/NaT/timestamps cleanly.
    import json

    return json.loads(
        sample.to_json(
            orient="records",
            date_format="iso",
        )
    )


def source_label(
    dataset: NflverseDatasetDefinition,
    seasons: list[int],
) -> str:
    season_label = (
        str(seasons[0])
        if len(seasons) == 1
        else f"{seasons[0]}-{seasons[-1]}"
    )
    return f"nflverse - {dataset.name} ({season_label})"
