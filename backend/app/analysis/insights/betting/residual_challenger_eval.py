"""
Compare champion vs challenger residuals on held-out rows.

Used by tests and offline diagnostics — does not promote models.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.residual_challenger import (
    fit_residual_challenger,
    predict_challenger_residuals,
    prior_challenger_model,
)
from app.analysis.insights.betting.residual_model import (
    apply_score_residuals,
    predict_score_residuals,
)


def evaluate_challenger_vs_champion(
    rows: list[dict[str, Any]],
    *,
    train_ratio: float = 0.7,
    strength_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Split rows chronologically (by week), fit challenger on train,
    score both models on holdout market-error and projection MAE.
    """

    ordered = sorted(
        rows or [],
        key=lambda row: (
            int(row.get("week") or 0),
            str(row.get("game_id") or ""),
        ),
    )
    if len(ordered) < 10:
        return {
            "available": False,
            "n": len(ordered),
            "note": "Need at least 10 labeled games for eval.",
        }

    cut = max(1, int(len(ordered) * train_ratio))
    train = ordered[:cut]
    test = ordered[cut:] or ordered[-1:]
    model = fit_residual_challenger(train)

    champ_resid_err: list[float] = []
    chall_resid_err: list[float] = []
    champ_proj_err: list[float] = []
    chall_proj_err: list[float] = []

    for row in test:
        market_home = num(row.get("market_home"))
        market_away = num(row.get("market_away"))
        actual_home = num(row.get("actual_home"))
        actual_away = num(row.get("actual_away"))
        y_home = num(row.get("y_home"))
        y_away = num(row.get("y_away"))
        if (
            market_home is None
            or market_away is None
            or actual_home is None
            or actual_away is None
            or y_home is None
            or y_away is None
        ):
            continue

        home_id = row.get("home_team_id")
        away_id = row.get("away_team_id")
        champ = predict_score_residuals(
            market_home=float(market_home),
            market_away=float(market_away),
            home_team_id=str(home_id) if home_id else None,
            away_team_id=str(away_id) if away_id else None,
            strength_context=strength_context,
        )
        chall = predict_challenger_residuals(
            feature_payload={
                "available": row.get("available"),
                "features": row.get("features"),
                "vector": row.get("vector"),
                "strength_home": champ.get("strength_home"),
                "strength_away": champ.get("strength_away"),
                "market_home": float(market_home),
                "market_away": float(market_away),
            },
            model=model,
            market_home=float(market_home),
            market_away=float(market_away),
        )

        c_rh = num(champ.get("residual_home")) or 0.0
        c_ra = num(champ.get("residual_away")) or 0.0
        h_rh = num(chall.get("residual_home")) or 0.0
        h_ra = num(chall.get("residual_away")) or 0.0
        champ_resid_err.append(
            0.5 * (abs(c_rh - float(y_home)) + abs(c_ra - float(y_away)))
        )
        chall_resid_err.append(
            0.5 * (abs(h_rh - float(y_home)) + abs(h_ra - float(y_away)))
        )

        c_home, c_away, _ = apply_score_residuals(champ)
        h_payload = {
            **chall,
            "residual_home": h_rh,
            "residual_away": h_ra,
            "market_home": float(market_home),
            "market_away": float(market_away),
            "situational_residual_home": 0.0,
            "situational_residual_away": 0.0,
        }
        h_home, h_away, _ = apply_score_residuals(h_payload)
        if c_home is not None and c_away is not None:
            champ_proj_err.append(
                0.5
                * (
                    abs(float(c_home) - float(actual_home))
                    + abs(float(c_away) - float(actual_away))
                )
            )
        if h_home is not None and h_away is not None:
            chall_proj_err.append(
                0.5
                * (
                    abs(float(h_home) - float(actual_home))
                    + abs(float(h_away) - float(actual_away))
                )
            )

    def _mae(values: list[float]) -> float | None:
        if not values:
            return None
        return round(float(np.mean(values)), 3)

    return {
        "available": True,
        "n_train": len(train),
        "n_test": len(test),
        "challenger_active": bool(model.get("active")),
        "challenger_method": model.get("method"),
        "champion_residual_mae": _mae(champ_resid_err),
        "challenger_residual_mae": _mae(chall_resid_err),
        "champion_projection_mae": _mae(champ_proj_err),
        "challenger_projection_mae": _mae(chall_proj_err),
        "prior_baseline": prior_challenger_model().get("method"),
        "note": (
            "Holdout MAE for predicted residual vs actual market "
            "error, and for projected scores vs finals."
        ),
    }
