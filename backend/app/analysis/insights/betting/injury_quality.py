"""
Build InjuryQualityFactors from usage / efficiency / depth.

Uses existing fact_player_usage + fact_player_efficiency
(lookback before the slate week) and depth-chart replacements.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.injury_impact import (
    InjuryQualityFactors,
    canonicalize_position,
)
from app.analysis.insights.betting.pricing import num
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


# Position priors when replacement has no sample.
_BACKUP_PRIOR: dict[str, float] = {
    "QB": 0.55,
    "RB": 0.85,
    "WR": 0.80,
    "TE": 0.85,
    "OL": 0.75,
    "DL": 0.80,
    "LB": 0.85,
    "CB": 0.75,
    "S": 0.85,
}

_SCHEME_PRIOR: dict[str, float] = {
    "QB": 1.15,
    "OL": 1.08,
    "WR": 1.05,
    "RB": 1.0,
    "TE": 1.0,
    "CB": 1.05,
    "DL": 1.0,
    "LB": 0.95,
    "S": 0.95,
}


def build_quality_factors(
    *,
    player_id: str,
    team_id: str,
    position: str | None,
    depth_order: int | None,
    season: int,
    before_week: int,
    depth_rows: list[dict[str, Any]] | None = None,
    usage_cache: dict[str, dict[str, float]] | None = None,
    efficiency_cache: dict[str, dict[str, float]] | None = None,
) -> InjuryQualityFactors:
    """
    Estimate quality multipliers for one injured player.

    Caches are optional preloaded maps player_id → metrics.
    """

    pos = canonicalize_position(position) or (position or "").upper()
    usage = (usage_cache or {}).get(str(player_id)) or {}
    efficiency = (efficiency_cache or {}).get(str(player_id)) or {}
    if not usage and not efficiency:
        loaded = load_player_quality_metrics(
            player_ids={str(player_id)},
            season=season,
            before_week=before_week,
        )
        usage = loaded.get("usage", {}).get(str(player_id)) or {}
        efficiency = loaded.get("efficiency", {}).get(str(player_id)) or {}

    snap = num(usage.get("offensive_snap_share"))
    if snap is None:
        snap = 0.85 if (depth_order is None or depth_order == 1) else 0.35
    snap = float(np_clip(snap, 0.05, 1.15))

    starter_quality = _starter_quality_from_efficiency(
        position=pos,
        efficiency=efficiency,
        snap_share=snap,
    )
    team_dependency = _team_dependency(pos, snap)
    scheme = float(_SCHEME_PRIOR.get(pos) or 1.0)

    replacement_id = _find_replacement(
        team_id=team_id,
        position=pos,
        injured_player_id=str(player_id),
        injured_depth_order=depth_order,
        depth_rows=depth_rows or [],
    )
    replacement_quality = float(_BACKUP_PRIOR.get(pos) or 0.8)
    backup_performance = replacement_quality
    if replacement_id:
        rep_usage = (usage_cache or {}).get(replacement_id)
        rep_eff = (efficiency_cache or {}).get(replacement_id)
        if usage_cache is None or efficiency_cache is None:
            loaded = load_player_quality_metrics(
                player_ids={replacement_id},
                season=season,
                before_week=before_week,
            )
            rep_usage = loaded.get("usage", {}).get(replacement_id)
            rep_eff = loaded.get("efficiency", {}).get(replacement_id)
        replacement_quality, backup_performance = _replacement_scores(
            position=pos,
            usage=rep_usage or {},
            efficiency=rep_eff or {},
            prior=replacement_quality,
        )

    return InjuryQualityFactors(
        starter_quality=round(starter_quality, 3),
        replacement_quality=round(replacement_quality, 3),
        snap_expectation=round(snap, 3),
        team_dependency=round(team_dependency, 3),
        backup_performance=round(backup_performance, 3),
        scheme_impact=round(scheme, 3),
    )


def load_player_quality_metrics(
    *,
    player_ids: set[str],
    season: int,
    before_week: int,
    lookback_weeks: int = 6,
) -> dict[str, dict[str, dict[str, float]]]:
    """
    Aggregate recent usage/efficiency before ``before_week``.

    Returns ``{"usage": {pid: {...}}, "efficiency": {pid: {...}}}``.
    """

    ids = [str(pid).strip() for pid in player_ids if pid]
    empty: dict[str, dict[str, dict[str, float]]] = {
        "usage": {},
        "efficiency": {},
    }
    if not ids:
        return empty

    week_lo = max(1, int(before_week) - int(lookback_weeks))
    week_hi = max(1, int(before_week) - 1)
    if week_hi < week_lo:
        return empty

    params: dict[str, Any] = {
        "season": int(season),
        "week_lo": week_lo,
        "week_hi": week_hi,
    }
    placeholders = ", ".join(f":pid_{i}" for i in range(len(ids)))
    for i, pid in enumerate(ids):
        params[f"pid_{i}"] = pid

    usage: dict[str, dict[str, float]] = {}
    try:
        sql = f"""
            SELECT
              player_id,
              AVG(offensive_snap_share) AS offensive_snap_share,
              AVG(snap_count) AS snap_count,
              COUNT(*) AS games
            FROM {FANTASY_SCHEMA}.fact_player_usage
            WHERE season = :season
              AND week BETWEEN :week_lo AND :week_hi
              AND player_id IN ({placeholders})
            GROUP BY player_id
        """
        with engine.connect() as connection:
            rows = connection.execute(text(sql), params).mappings()
            for row in rows:
                pid = str(row.get("player_id") or "")
                if not pid:
                    continue
                usage[pid] = {
                    "offensive_snap_share": float(
                        num(row.get("offensive_snap_share")) or 0.0
                    ),
                    "snap_count": float(num(row.get("snap_count")) or 0.0),
                    "games": float(num(row.get("games")) or 0.0),
                }
    except Exception:
        usage = {}

    efficiency: dict[str, dict[str, float]] = {}
    try:
        sql = f"""
            SELECT
              player_id,
              AVG(pass_epa_per_dropback) AS pass_epa_per_dropback,
              AVG(rush_epa_per_attempt) AS rush_epa_per_attempt,
              AVG(yards_per_target) AS yards_per_target,
              AVG(fantasy_points_per_touch) AS fantasy_points_per_touch,
              COUNT(*) AS games
            FROM {FANTASY_SCHEMA}.fact_player_efficiency
            WHERE season = :season
              AND week BETWEEN :week_lo AND :week_hi
              AND player_id IN ({placeholders})
            GROUP BY player_id
        """
        with engine.connect() as connection:
            rows = connection.execute(text(sql), params).mappings()
            for row in rows:
                pid = str(row.get("player_id") or "")
                if not pid:
                    continue
                efficiency[pid] = {
                    "pass_epa_per_dropback": float(
                        num(row.get("pass_epa_per_dropback")) or 0.0
                    ),
                    "rush_epa_per_attempt": float(
                        num(row.get("rush_epa_per_attempt")) or 0.0
                    ),
                    "yards_per_target": float(
                        num(row.get("yards_per_target")) or 0.0
                    ),
                    "fantasy_points_per_touch": float(
                        num(row.get("fantasy_points_per_touch")) or 0.0
                    ),
                    "games": float(num(row.get("games")) or 0.0),
                }
    except Exception:
        efficiency = {}

    return {"usage": usage, "efficiency": efficiency}


def _starter_quality_from_efficiency(
    *,
    position: str,
    efficiency: dict[str, float],
    snap_share: float,
) -> float:
    """Map EPA / snap into ~0.7–1.35 starter quality."""

    if position == "QB":
        epa = float(efficiency.get("pass_epa_per_dropback") or 0.0)
        # League-ish center ~0; ±0.15 EPA → quality swing.
        quality = 1.0 + np_clip(epa / 0.20, -0.35, 0.40)
    elif position in {"RB"}:
        epa = float(efficiency.get("rush_epa_per_attempt") or 0.0)
        quality = 1.0 + np_clip(epa / 0.15, -0.25, 0.30)
    elif position in {"WR", "TE"}:
        # yards/target ~7–9 typical; map excess to quality.
        ypt = float(efficiency.get("yards_per_target") or 0.0)
        quality = 1.0 + np_clip((ypt - 7.5) / 4.0, -0.25, 0.30)
    else:
        quality = 1.0
    # High snap share slightly raises quality (volume-critical).
    quality *= 0.92 + 0.16 * np_clip(snap_share, 0.0, 1.0)
    return float(np_clip(quality, 0.65, 1.40))


def _team_dependency(position: str, snap_share: float) -> float:
    base = {
        "QB": 1.25,
        "OL": 1.10,
        "WR": 1.05,
        "CB": 1.05,
    }.get(position, 1.0)
    return float(np_clip(base * (0.85 + 0.3 * snap_share), 0.7, 1.45))


def _replacement_scores(
    *,
    position: str,
    usage: dict[str, float],
    efficiency: dict[str, float],
    prior: float,
) -> tuple[float, float]:
    snap = num(usage.get("offensive_snap_share"))
    if snap is None:
        return prior, prior
    # More experienced backup (higher historical snaps) → better replacement.
    experience = float(np_clip(float(snap) / 0.55, 0.5, 1.35))
    starterish = _starter_quality_from_efficiency(
        position=position,
        efficiency=efficiency,
        snap_share=float(snap),
    )
    # Replacement quality relative to average starter (~1.0).
    replacement = float(np_clip(0.55 * experience + 0.45 * starterish, 0.4, 1.25))
    backup_perf = float(np_clip(0.6 * prior + 0.4 * replacement, 0.4, 1.25))
    return replacement, backup_perf


def _find_replacement(
    *,
    team_id: str,
    position: str,
    injured_player_id: str,
    injured_depth_order: int | None,
    depth_rows: list[dict[str, Any]],
) -> str | None:
    candidates: list[tuple[int, str]] = []
    injured_order = int(injured_depth_order or 1)
    for row in depth_rows:
        if str(row.get("team_id") or "") != str(team_id):
            continue
        pos = canonicalize_position(row.get("position")) or str(
            row.get("position") or ""
        ).upper()
        if pos != position:
            continue
        pid = str(row.get("player_id") or "")
        if not pid or pid == injured_player_id:
            continue
        order = int(num(row.get("depth_order")) or 99)
        if order <= injured_order:
            continue
        candidates.append((order, pid))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def np_clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))
