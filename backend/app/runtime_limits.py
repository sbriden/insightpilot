"""Runtime caps for small cloud instances (e.g. Render free 512MB)."""

from __future__ import annotations

import gc
import os
from typing import Iterable


def env_flag(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def low_memory_mode() -> bool:
    """Prefer INSIGHTPILOT_LOW_MEMORY=1 on ≤512MB hosts."""
    return env_flag("INSIGHTPILOT_LOW_MEMORY", default=False)


def low_memory_season_count() -> int:
    try:
        value = int(os.getenv("INSIGHTPILOT_LOW_MEMORY_SEASONS") or "1")
    except ValueError:
        value = 1
    return max(1, min(value, 2))


# Play-by-play builds routinely exceed 512MB even for a single season.
PBP_HEAVY_DATASETS: frozenset[str] = frozenset(
    {
        "fact_player_usage",
        "fact_player_efficiency",
        "fact_team_game",
        "fact_defensive_game",
    }
)


def filter_datasets_for_memory(
    dataset_ids: Iterable[str],
) -> list[str]:
    ids = list(dataset_ids)
    if not low_memory_mode():
        return ids
    return [dataset_id for dataset_id in ids if dataset_id not in PBP_HEAVY_DATASETS]


def reclaim_memory() -> None:
    """Drop in-process caches and ask the allocator to return pages."""
    try:
        from app.canonical.cache_control import clear_all_fantasy_caches

        clear_all_fantasy_caches()
    except Exception:
        pass
    try:
        from app.sources import sportsdataverse as sdv

        sdv.clear_all_cfb_caches()
    except Exception:
        pass
    gc.collect()
