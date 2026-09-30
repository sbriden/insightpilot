"""Daily Fantasy slate / optimizer helpers."""

from __future__ import annotations

from app.analysis.insights.dfs.insights import (
    build_lineup_insights,
)
from app.analysis.insights.dfs.optimize import (
    optimize_lineup,
)
from app.analysis.insights.dfs.portfolio import (
    generate_portfolio,
)
from app.analysis.insights.dfs.projection_calibration import (
    calibrate_projection,
)
from app.analysis.insights.dfs.sites import (
    DFS_SITES,
    get_site_config,
    list_sites,
)
from app.analysis.insights.dfs.slate import (
    build_dfs_slate,
    list_dfs_slates,
)

__all__ = [
    "DFS_SITES",
    "build_dfs_slate",
    "build_lineup_insights",
    "calibrate_projection",
    "generate_portfolio",
    "get_site_config",
    "list_dfs_slates",
    "list_sites",
    "optimize_lineup",
]
