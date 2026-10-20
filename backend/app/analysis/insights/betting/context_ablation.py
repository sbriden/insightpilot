"""
Context feature-group ablation for residual forecasts.

Compares holdout MAE with groups toggled:
  none, injury_flat, injury_predictive, +rest, +market_move

Weather/travel marked unavailable (not ingested).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.analysis.insights.betting.injury_impact import (
    InjuryQualityFactors,
    estimate_injury_impact,
)
from app.analysis.insights.betting.pricing import num


FEATURE_GROUPS = (
    "none",
    "injury_flat",
    "injury_predictive",
    "injury_predictive_rest",
    "injury_predictive_rest_move",
)


def run_context_ablation(
    rows: list[dict[str, Any]],
    *,
    train_ratio: float = 0.7,
) -> dict[str, Any]:
    """
    Time-ordered ablation on labeled market-error rows.

    Each row should include actual/market scores and optional
    context: rest days, spread/total move, injury stubs.
    """

    ordered = sorted(
        rows or [],
        key=lambda row: (
            int(row.get("week") or 0),
            str(row.get("game_id") or ""),
        ),
    )
    if len(ordered) < 20:
        return {
            "available": False,
            "n": len(ordered),
            "note": "Need at least 20 games for context ablation.",
            "groups": {},
            "unavailable": ["weather", "travel", "roof", "wind"],
        }

    cut = max(1, int(len(ordered) * train_ratio))
    test = ordered[cut:] or ordered[-1:]

    group_err: dict[str, list[float]] = {g: [] for g in FEATURE_GROUPS}

    for row in test:
        market_home = num(row.get("market_home"))
        market_away = num(row.get("market_away"))
        actual_home = num(row.get("actual_home"))
        actual_away = num(row.get("actual_away"))
        if (
            market_home is None
            or market_away is None
            or actual_home is None
            or actual_away is None
        ):
            continue
        y_home = float(actual_home) - float(market_home)
        y_away = float(actual_away) - float(market_away)

        preds = {
            "none": (0.0, 0.0),
            "injury_flat": _flat_injury_pred(row),
            "injury_predictive": _predictive_injury_pred(row, use_move=False),
            "injury_predictive_rest": _add_rest(
                _predictive_injury_pred(row, use_move=False), row
            ),
            "injury_predictive_rest_move": _add_rest(
                _predictive_injury_pred(row, use_move=True), row
            ),
        }
        for group, (ph, pa) in preds.items():
            err = 0.5 * (abs(ph - y_home) + abs(pa - y_away))
            group_err[group].append(err)

    mae: dict[str, Any] = {}
    baseline = None
    for group, errs in group_err.items():
        if not errs:
            mae[group] = None
            continue
        value = round(float(np.mean(errs)), 4)
        mae[group] = value
        if group == "none":
            baseline = value

    improvements: dict[str, Any] = {}
    for group, value in mae.items():
        if value is None or baseline is None:
            improvements[group] = None
        else:
            improvements[group] = round(float(baseline) - float(value), 4)

    best = None
    best_mae = None
    for group, value in mae.items():
        if value is None:
            continue
        if best_mae is None or value < best_mae:
            best_mae = value
            best = group

    return {
        "available": True,
        "n_train": cut,
        "n_test": len(test),
        "metric": "residual_mae",
        "mae_by_group": mae,
        "improvement_vs_none": improvements,
        "best_group": best,
        "unavailable": ["weather", "travel", "roof", "wind"],
        "note": (
            "Lower MAE is better. improvement_vs_none > 0 means "
            "the feature group reduced holdout residual error."
        ),
    }


def _flat_injury_pred(row: dict[str, Any]) -> tuple[float, float]:
    """Legacy-style flat starter deduction without quality."""

    qb_home = float(num(row.get("qb_out_home")) or 0.0)
    qb_away = float(num(row.get("qb_out_away")) or 0.0)
    # Flat market-weighted QB impact ≈ 5.5 * 0.45
    return (-2.5 * qb_home, -2.5 * qb_away)


def _predictive_injury_pred(
    row: dict[str, Any],
    *,
    use_move: bool,
) -> tuple[float, float]:
    """Use estimate_injury_impact with quality if present."""

    home = 0.0
    away = 0.0
    for side, key_prefix in (("home", "home"), ("away", "away")):
        pos = row.get(f"{key_prefix}_injury_position") or (
            "QB" if row.get(f"qb_out_{key_prefix}") else None
        )
        if not pos and not row.get(f"qb_out_{key_prefix}"):
            continue
        status = str(row.get(f"{key_prefix}_injury_status") or "out")
        quality_raw = row.get(f"{key_prefix}_injury_quality") or {}
        factors = InjuryQualityFactors(
            starter_quality=float(quality_raw.get("starter_quality") or 1.0),
            replacement_quality=float(
                quality_raw.get("replacement_quality") or 1.0
            ),
            snap_expectation=float(
                quality_raw.get("snap_expectation") or 1.0
            ),
            team_dependency=float(
                quality_raw.get("team_dependency") or 1.0
            ),
            backup_performance=float(
                quality_raw.get("backup_performance") or 1.0
            ),
            scheme_impact=float(quality_raw.get("scheme_impact") or 1.0),
        )
        impact = estimate_injury_impact(
            position=pos or "QB",
            status=status,
            depth_order=1,
            is_starter=True,
            factors=factors,
            spread_move=(
                num(row.get("spread_move")) if use_move else None
            ),
            total_move=num(row.get("total_move")) if use_move else None,
            injured_team_is_home=(side == "home"),
        )
        delta = float(impact.get("edge_own_delta") or 0.0)
        if side == "home":
            home += delta
        else:
            away += delta
    # Also allow precomputed edge fields.
    if row.get("home_injury_adj") is not None and home == 0.0:
        home = float(row["home_injury_adj"])
    if row.get("away_injury_adj") is not None and away == 0.0:
        away = float(row["away_injury_adj"])
    return home, away


def _add_rest(
    pred: tuple[float, float],
    row: dict[str, Any],
) -> tuple[float, float]:
    """Small rest effect: short rest hurts offense slightly."""

    home, away = pred
    hr = num(row.get("home_rest_days"))
    ar = num(row.get("away_rest_days"))
    if hr is not None and hr < 6:
        home -= 0.35 * (6.0 - float(hr))
    if ar is not None and ar < 6:
        away -= 0.35 * (6.0 - float(ar))
    return home, away
