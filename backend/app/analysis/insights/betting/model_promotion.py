"""
Walk-forward model evaluation and promotion.

Retrain residual challenger candidates on eligible history only,
compare to the champion with expanding/rolling time splits (no
random leakage), and promote only when sample size and uncertainty
gates clear. Weight tweaks after a bad week are not a promotion path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.residual_challenger import (
    fit_residual_challenger,
    predict_challenger_residuals,
    prior_challenger_model,
)
from app.analysis.insights.betting.residual_challenger_eval import (
    evaluate_challenger_vs_champion,
)
from app.analysis.insights.betting.residual_model import (
    apply_score_residuals,
    predict_score_residuals,
)


MIN_WALK_FORWARD_FOLDS = 3
MIN_TRAIN_PER_FOLD = 25
MIN_TEST_PER_FOLD = 8
MIN_TOTAL_FOR_PROMOTION = 60
# Challenger must beat champion MAE by at least this fraction.
MIN_RELATIVE_IMPROVEMENT = 0.03
# Paired-error bootstrap: require P(challenger better) >= this.
MIN_BOOTSTRAP_CONFIDENCE = 0.80
BOOTSTRAP_DRAWS = 400


def walk_forward_residual_eval(
    rows: list[dict[str, Any]],
    *,
    mode: str = "expanding",
    min_train: int = MIN_TRAIN_PER_FOLD,
    test_weeks: int = 2,
    strength_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Time-ordered walk-forward comparison of champion vs challenger.

    ``expanding``: train on all weeks before the test window.
    ``rolling``: train on a fixed recent window of similar size.
    """

    ordered = sorted(
        rows or [],
        key=lambda row: (
            int(row.get("week") or 0),
            str(row.get("game_id") or ""),
        ),
    )
    weeks = sorted(
        {
            int(row.get("week") or 0)
            for row in ordered
            if row.get("week") is not None
        }
    )
    if len(ordered) < min_train + MIN_TEST_PER_FOLD or len(weeks) < 4:
        single = evaluate_challenger_vs_champion(
            ordered, train_ratio=0.7, strength_context=strength_context
        )
        return {
            "available": bool(single.get("available")),
            "mode": mode,
            "folds": [],
            "aggregate": single,
            "n": len(ordered),
            "note": (
                "Insufficient weeks for multi-fold walk-forward; "
                "fell back to a single chronological holdout."
            ),
        }

    folds: list[dict[str, Any]] = []
    all_champ: list[float] = []
    all_chall: list[float] = []
    rolling_train_weeks = max(4, len(weeks) // 2)

    for cut_idx in range(2, len(weeks)):
        test_week_set = set(weeks[cut_idx : cut_idx + test_weeks])
        if not test_week_set:
            continue
        train_weeks = weeks[:cut_idx]
        if mode == "rolling":
            train_weeks = train_weeks[-rolling_train_weeks:]
        train = [
            row
            for row in ordered
            if int(row.get("week") or 0) in set(train_weeks)
        ]
        test = [
            row
            for row in ordered
            if int(row.get("week") or 0) in test_week_set
        ]
        if len(train) < min_train or len(test) < MIN_TEST_PER_FOLD:
            continue

        fold = _score_fold(
            train,
            test,
            strength_context=strength_context,
        )
        fold["train_weeks"] = train_weeks
        fold["test_weeks"] = sorted(test_week_set)
        folds.append(fold)
        all_champ.extend(fold.get("champion_errors") or [])
        all_chall.extend(fold.get("challenger_errors") or [])

    if len(folds) < MIN_WALK_FORWARD_FOLDS:
        single = evaluate_challenger_vs_champion(
            ordered, train_ratio=0.7, strength_context=strength_context
        )
        return {
            "available": bool(single.get("available")),
            "mode": mode,
            "folds": folds,
            "aggregate": single,
            "n": len(ordered),
            "note": (
                f"Only {len(folds)} walk-forward folds cleared sample "
                "gates; include single chronological holdout."
            ),
        }

    champ_mae = float(np.mean(all_champ)) if all_champ else None
    chall_mae = float(np.mean(all_chall)) if all_chall else None
    bootstrap = _bootstrap_improvement(all_champ, all_chall)
    return {
        "available": True,
        "mode": mode,
        "n": len(ordered),
        "n_folds": len(folds),
        "folds": [
            {
                "train_weeks": f["train_weeks"],
                "test_weeks": f["test_weeks"],
                "n_train": f["n_train"],
                "n_test": f["n_test"],
                "champion_projection_mae": f["champion_projection_mae"],
                "challenger_projection_mae": f[
                    "challenger_projection_mae"
                ],
                "challenger_active": f["challenger_active"],
            }
            for f in folds
        ],
        "aggregate": {
            "available": True,
            "n_train": sum(f["n_train"] for f in folds),
            "n_test": sum(f["n_test"] for f in folds),
            "champion_projection_mae": (
                round(champ_mae, 3) if champ_mae is not None else None
            ),
            "challenger_projection_mae": (
                round(chall_mae, 3) if chall_mae is not None else None
            ),
            "bootstrap": bootstrap,
        },
        "note": (
            f"{mode.title()} walk-forward over {len(folds)} folds. "
            "No random splits — weeks only move forward in time."
        ),
    }


def decide_residual_promotion(
    walk_forward: dict[str, Any],
    *,
    candidate_model: dict[str, Any] | None,
    current_active: str = "champion",
) -> dict[str, Any]:
    """
    Gate promotion of the residual challenger to production apply.

    Requires enough samples, active candidate fit, relative MAE gain,
    and bootstrap confidence that the gain is not noise.
    """

    candidate = candidate_model or prior_challenger_model()
    aggregate = (walk_forward or {}).get("aggregate") or {}
    n = int(
        (walk_forward or {}).get("n")
        or aggregate.get("n_test")
        or candidate.get("sample_size")
        or 0
    )
    champ_mae = num(aggregate.get("champion_projection_mae"))
    chall_mae = num(aggregate.get("challenger_projection_mae"))
    bootstrap = aggregate.get("bootstrap") or {}
    conf = num(bootstrap.get("p_challenger_better"))

    reasons: list[str] = []
    promote = True

    if not bool(candidate.get("active")):
        promote = False
        reasons.append("candidate_inactive")
    if n < MIN_TOTAL_FOR_PROMOTION:
        promote = False
        reasons.append(
            f"insufficient_sample:{n}<{MIN_TOTAL_FOR_PROMOTION}"
        )
    if not walk_forward.get("available"):
        promote = False
        reasons.append("walk_forward_unavailable")
    if champ_mae is None or chall_mae is None:
        promote = False
        reasons.append("missing_mae")
    else:
        if float(chall_mae) >= float(champ_mae):
            promote = False
            reasons.append("no_mae_improvement")
        else:
            rel = (float(champ_mae) - float(chall_mae)) / max(
                float(champ_mae), 1e-6
            )
            if rel < MIN_RELATIVE_IMPROVEMENT:
                promote = False
                reasons.append(
                    f"improvement_below_floor:{rel:.3f}"
                    f"<{MIN_RELATIVE_IMPROVEMENT}"
                )
    if conf is None or float(conf) < MIN_BOOTSTRAP_CONFIDENCE:
        promote = False
        reasons.append(
            f"bootstrap_confidence_low:"
            f"{conf if conf is not None else 'none'}"
            f"<{MIN_BOOTSTRAP_CONFIDENCE}"
        )

    decision = "promote" if promote else "hold"
    active_model = "challenger" if promote else (
        current_active if current_active in {"champion", "challenger"} else "champion"
    )
    # Demote challenger if it was active and now fails gates.
    if not promote and current_active == "challenger":
        if "no_mae_improvement" in reasons or any(
            r.startswith("improvement_below_floor") for r in reasons
        ):
            decision = "demote"
            active_model = "champion"

    relative = None
    if champ_mae is not None and chall_mae is not None and champ_mae:
        relative = round(
            (float(champ_mae) - float(chall_mae)) / float(champ_mae), 4
        )

    return {
        "component": "residual_challenger",
        "decision": decision,
        "promoted": promote,
        "active_model": active_model,
        "candidate_version": candidate.get("model_version"),
        "candidate_method": candidate.get("method"),
        "candidate_active": bool(candidate.get("active")),
        "sample_size": n,
        "champion_projection_mae": champ_mae,
        "challenger_projection_mae": chall_mae,
        "relative_improvement": relative,
        "bootstrap": bootstrap,
        "min_sample": MIN_TOTAL_FOR_PROMOTION,
        "min_relative_improvement": MIN_RELATIVE_IMPROVEMENT,
        "min_bootstrap_confidence": MIN_BOOTSTRAP_CONFIDENCE,
        "reasons": reasons,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Promote residual challenger only when walk-forward MAE "
            "improves with enough samples and bootstrap confidence."
            if promote
            else "Hold champion; candidate did not clear promotion gates."
        ),
    }


def run_model_promotion_cycle(
    *,
    season: int,
    training_rows: list[dict[str, Any]],
    current_active: str = "champion",
    mode: str = "expanding",
    strength_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fit candidate on all eligible rows, walk-forward evaluate, decide.
    """

    candidate = fit_residual_challenger(training_rows)
    walk = walk_forward_residual_eval(
        training_rows,
        mode=mode,
        strength_context=strength_context,
    )
    decision = decide_residual_promotion(
        walk,
        candidate_model=candidate,
        current_active=current_active,
    )
    return {
        "season": int(season),
        "component": "residual_challenger",
        "candidate": {
            "method": candidate.get("method"),
            "model_version": candidate.get("model_version"),
            "active": bool(candidate.get("active")),
            "sample_size": candidate.get("sample_size"),
            "metrics": candidate.get("metrics"),
            "note": candidate.get("note"),
        },
        "walk_forward": walk,
        "promotion": decision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _score_fold(
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    *,
    strength_context: dict[str, Any] | None,
) -> dict[str, Any]:
    model = fit_residual_challenger(train)
    champ_err: list[float] = []
    chall_err: list[float] = []

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
        c_home, c_away, _ = apply_score_residuals(champ)
        h_payload = {
            **chall,
            "residual_home": num(chall.get("residual_home")) or 0.0,
            "residual_away": num(chall.get("residual_away")) or 0.0,
            "market_home": float(market_home),
            "market_away": float(market_away),
            "situational_residual_home": 0.0,
            "situational_residual_away": 0.0,
        }
        h_home, h_away, _ = apply_score_residuals(h_payload)
        if c_home is not None and c_away is not None:
            champ_err.append(
                0.5
                * (
                    abs(float(c_home) - float(actual_home))
                    + abs(float(c_away) - float(actual_away))
                )
            )
        if h_home is not None and h_away is not None:
            chall_err.append(
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
        "n_train": len(train),
        "n_test": len(test),
        "challenger_active": bool(model.get("active")),
        "champion_projection_mae": _mae(champ_err),
        "challenger_projection_mae": _mae(chall_err),
        "champion_errors": champ_err,
        "challenger_errors": chall_err,
    }


def _bootstrap_improvement(
    champion_errors: list[float],
    challenger_errors: list[float],
    *,
    draws: int = BOOTSTRAP_DRAWS,
) -> dict[str, Any]:
    """Uncertainty on mean MAE difference (challenger − champion)."""

    n = min(len(champion_errors), len(challenger_errors))
    if n < 8:
        return {
            "n": n,
            "mean_delta": None,
            "p_challenger_better": None,
            "note": "Need at least 8 paired errors for bootstrap.",
        }
    champ = np.asarray(champion_errors[:n], dtype=float)
    chall = np.asarray(challenger_errors[:n], dtype=float)
    delta = chall - champ  # negative => challenger better
    rng = np.random.default_rng(42)
    means = []
    for _ in range(draws):
        idx = rng.integers(0, n, size=n)
        means.append(float(np.mean(delta[idx])))
    means_arr = np.asarray(means, dtype=float)
    p_better = float(np.mean(means_arr < 0.0))
    return {
        "n": n,
        "mean_delta": round(float(np.mean(delta)), 4),
        "delta_ci80": [
            round(float(np.percentile(means_arr, 10)), 4),
            round(float(np.percentile(means_arr, 90)), 4),
        ],
        "p_challenger_better": round(p_better, 4),
        "draws": draws,
    }
