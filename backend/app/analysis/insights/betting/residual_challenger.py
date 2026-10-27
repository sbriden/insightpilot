"""
Challenger residual model — predict market score errors.

Champion (residual_model.py) uses strength − market then fixed
confidence shrink. This challenger predicts:

  μ = f(features)          expected market residual
  σ = uncertainty(features)
  applied = μ * (v / (v + σ²))

so the market dominates when evidence is weak.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.analysis.insights.betting.pricing import num
from app.analysis.insights.betting.residual_features import (
    FEATURE_NAMES,
    PRIOR_HOME_COEF,
    build_residual_features,
    features_to_vector,
)


MIN_FIT_SAMPLES = 40
RIDGE_LAMBDA = 8.0
DEFAULT_PRIOR_VARIANCE = 9.0  # ~3 pts SD prior on residual
MODEL_VERSION = "challenger_ridge_v2"

# Regime buckets for σ (min_games band, disagreement, injury flag).
UNCERTAINTY_BUCKETS = (
    ("thin", lambda g, d, i: g < 3),
    ("disagreement", lambda g, d, i: d >= 2.0),
    ("injury", lambda g, d, i: i >= 0.5),
    ("base", lambda g, d, i: True),
)


def prior_challenger_model() -> dict[str, Any]:
    """Informative cold-start coefficients from strength priors."""

    coef_home = [0.0] * len(FEATURE_NAMES)
    coef_away = [0.0] * len(FEATURE_NAMES)
    for index, name in enumerate(FEATURE_NAMES):
        home_c = float(PRIOR_HOME_COEF.get(name, 0.0))
        coef_home[index] = home_c
        # Mirror: away residual mirrors flipped matchup/home injury.
        away_c = home_c
        if name.startswith("home_matchup"):
            away_c = float(PRIOR_HOME_COEF.get("away_matchup", 0.0))
        elif name.startswith("away_matchup"):
            away_c = float(PRIOR_HOME_COEF.get("home_matchup", 0.0))
        elif name == "pass_matchup_home":
            away_c = float(PRIOR_HOME_COEF.get("pass_matchup_home", 0.0)) * 0.0
            # Use away pass matchup prior via name mapping below.
        elif name == "pass_matchup_away":
            away_c = float(PRIOR_HOME_COEF.get("pass_matchup_home", 1.1))
        elif name == "rush_matchup_home":
            away_c = 0.0
        elif name == "rush_matchup_away":
            away_c = float(PRIOR_HOME_COEF.get("rush_matchup_home", 0.7))
        elif name == "home_injury_adj":
            away_c = float(PRIOR_HOME_COEF.get("away_injury_adj", 0.35))
        elif name == "away_injury_adj":
            away_c = float(PRIOR_HOME_COEF.get("home_injury_adj", 1.0))
        elif name == "qb_out_home":
            away_c = float(PRIOR_HOME_COEF.get("qb_out_away", 0.8))
        elif name == "qb_out_away":
            away_c = float(PRIOR_HOME_COEF.get("qb_out_home", -2.5))
        elif name == "home_rz_eff":
            away_c = 0.0
        elif name == "away_rz_eff":
            away_c = float(PRIOR_HOME_COEF.get("home_rz_eff", 0.6))
        coef_away[index] = away_c

    return {
        "method": "prior",
        "model_version": MODEL_VERSION,
        "active": False,
        "sample_size": 0,
        "feature_names": list(FEATURE_NAMES),
        "intercept_home": 0.0,
        "intercept_away": 0.0,
        "coef_home": coef_home,
        "coef_away": coef_away,
        "prior_variance": DEFAULT_PRIOR_VARIANCE,
        "sigma_by_bucket": {
            "thin": 6.5,
            "disagreement": 5.5,
            "injury": 5.0,
            "base": 4.0,
        },
        "metrics": None,
        "note": (
            "Cold-start prior seeded from team-strength point mapping. "
            f"Becomes active after {MIN_FIT_SAMPLES} historical "
            "market-error samples."
        ),
    }


def fit_residual_challenger(
    rows: list[dict[str, Any]],
    *,
    ridge_lambda: float = RIDGE_LAMBDA,
) -> dict[str, Any]:
    """
    Fit ridge models for home/away market residuals.

    Each row needs ``vector`` (or ``features``) and targets
    ``y_home`` / ``y_away`` (= actual − market).
    """

    samples = _normalize_fit_rows(rows)
    n = len(samples)
    if n < MIN_FIT_SAMPLES:
        model = prior_challenger_model()
        model["sample_size"] = n
        model["note"] = (
            f"Insufficient samples ({n} < {MIN_FIT_SAMPLES}); "
            "using cold-start prior."
        )
        return model

    x = np.asarray([s["vector"] for s in samples], dtype=float)
    y_home = np.asarray([s["y_home"] for s in samples], dtype=float)
    y_away = np.asarray([s["y_away"] for s in samples], dtype=float)

    intercept_h, coef_h = _fit_ridge(x, y_home, ridge_lambda)
    intercept_a, coef_a = _fit_ridge(x, y_away, ridge_lambda)

    pred_h = intercept_h + x @ coef_h
    pred_a = intercept_a + x @ coef_a
    resid_h = y_home - pred_h
    resid_a = y_away - pred_a

    sigma_by_bucket = _fit_sigma_buckets(samples, resid_h, resid_a)
    prior_var = float(np.var(np.concatenate([y_home, y_away])))
    if not math.isfinite(prior_var) or prior_var <= 0.5:
        prior_var = DEFAULT_PRIOR_VARIANCE

    metrics = {
        "n": n,
        "mae_home": round(float(np.mean(np.abs(resid_h))), 4),
        "mae_away": round(float(np.mean(np.abs(resid_a))), 4),
        "rmse_home": round(float(np.sqrt(np.mean(resid_h ** 2))), 4),
        "rmse_away": round(float(np.sqrt(np.mean(resid_a ** 2))), 4),
        "mean_abs_y": round(
            float(np.mean(np.abs(np.concatenate([y_home, y_away])))),
            4,
        ),
    }

    return {
        "method": "ridge",
        "model_version": MODEL_VERSION,
        "active": True,
        "sample_size": n,
        "feature_names": list(FEATURE_NAMES),
        "intercept_home": round(float(intercept_h), 6),
        "intercept_away": round(float(intercept_a), 6),
        "coef_home": [round(float(c), 6) for c in coef_h],
        "coef_away": [round(float(c), 6) for c in coef_a],
        "prior_variance": round(prior_var, 4),
        "sigma_by_bucket": sigma_by_bucket,
        "ridge_lambda": ridge_lambda,
        "metrics": metrics,
        "note": (
            f"Fitted ridge on {n} market-error samples. "
            f"MAE home {metrics['mae_home']:.2f} / "
            f"away {metrics['mae_away']:.2f}."
        ),
    }


def predict_challenger_residuals(
    *,
    feature_payload: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
    market_home: float | None = None,
    market_away: float | None = None,
    **feature_kwargs: Any,
) -> dict[str, Any]:
    """
    Predict shrunk home/away residuals for one game.

    Pass either a prebuilt ``feature_payload`` from
    ``build_residual_features`` or kwargs for that builder.
    """

    active_model = model or prior_challenger_model()
    payload = feature_payload or build_residual_features(**feature_kwargs)
    vector = payload.get("vector")
    if vector is None and payload.get("features"):
        vector = features_to_vector(payload["features"])
    if not vector:
        return _empty_prediction(active_model)

    mu_home, mu_away = _predict_mu(vector, active_model)
    sigma = estimate_residual_uncertainty(
        features=payload.get("features") or {},
        model=active_model,
    )
    prior_var = float(
        active_model.get("prior_variance") or DEFAULT_PRIOR_VARIANCE
    )
    shrink = prior_var / (prior_var + sigma * sigma) if sigma >= 0 else 0.0
    shrink = max(0.0, min(1.0, shrink))

    residual_home = round(float(mu_home) * shrink, 3)
    residual_away = round(float(mu_away) * shrink, 3)

    m_home = (
        num(market_home)
        if market_home is not None
        else num(payload.get("market_home"))
    )
    m_away = (
        num(market_away)
        if market_away is not None
        else num(payload.get("market_away"))
    )

    return {
        "available": bool(payload.get("available")),
        "architecture": "market + residual",
        "model_role": "challenger",
        "model_version": active_model.get("model_version") or MODEL_VERSION,
        "method": active_model.get("method"),
        "model_active": bool(active_model.get("active")),
        "formula": (
            "final = market + shrink(σ) * μ(features); "
            "shrink = v / (v + σ²)"
        ),
        "mu_home": round(float(mu_home), 3),
        "mu_away": round(float(mu_away), 3),
        "sigma": round(float(sigma), 3),
        "prior_variance": round(prior_var, 3),
        "shrink": round(shrink, 4),
        "market_weight": round(1.0 - shrink, 4),
        "model_weight": round(shrink, 4),
        "residual_home": residual_home,
        "residual_away": residual_away,
        "raw_residual_home": round(float(mu_home), 3),
        "raw_residual_away": round(float(mu_away), 3),
        "market_home": m_home,
        "market_away": m_away,
        "strength_home": payload.get("strength_home"),
        "strength_away": payload.get("strength_away"),
        "features_used": list(FEATURE_NAMES),
        "feature_values": payload.get("features"),
        "projection_confidence": _confidence_from_shrink(shrink),
        "situational_residual_home": 0.0,
        "situational_residual_away": 0.0,
        "sample_size": active_model.get("sample_size"),
        "note": active_model.get("note"),
    }


def estimate_residual_uncertainty(
    *,
    features: dict[str, Any],
    model: dict[str, Any] | None = None,
) -> float:
    """Map feature regime → σ from fitted or prior buckets."""

    active = model or prior_challenger_model()
    buckets = active.get("sigma_by_bucket") or {}
    games = float(num(features.get("min_games")) or 0.0)
    disagreement = max(
        float(num(features.get("disagreement_spread_sd")) or 0.0),
        float(num(features.get("disagreement_total_sd")) or 0.0),
    )
    injury = max(
        abs(float(num(features.get("home_injury_adj")) or 0.0)),
        abs(float(num(features.get("away_injury_adj")) or 0.0)),
        float(num(features.get("qb_out_home")) or 0.0) * 3.0,
        float(num(features.get("qb_out_away")) or 0.0) * 3.0,
    )
    missing = float(num(features.get("missing_strength")) or 0.0)
    if missing >= 0.5:
        return float(buckets.get("thin") or 6.5)

    for label, predicate in UNCERTAINTY_BUCKETS:
        if predicate(games, disagreement, injury):
            return float(buckets.get(label) or buckets.get("base") or 4.0)
    return float(buckets.get("base") or 4.0)


def challenger_to_residual_payload(
    prediction: dict[str, Any],
) -> dict[str, Any]:
    """
    Shape challenger output like ``predict_score_residuals`` so
    ``add_situational_residuals`` / ``apply_score_residuals`` work.
    """

    return {
        "available": bool(prediction.get("available")),
        "architecture": "market + residual",
        "formula": prediction.get("formula"),
        "projection_confidence": prediction.get("projection_confidence"),
        "shrink": prediction.get("shrink"),
        "market_weight": prediction.get("market_weight"),
        "model_weight": prediction.get("model_weight"),
        "policy_source": prediction.get("model_version"),
        "policy_learned": bool(prediction.get("model_active")),
        "market_home": prediction.get("market_home"),
        "market_away": prediction.get("market_away"),
        "strength_home": prediction.get("strength_home"),
        "strength_away": prediction.get("strength_away"),
        "raw_residual_home": prediction.get("raw_residual_home"),
        "raw_residual_away": prediction.get("raw_residual_away"),
        "residual_home": prediction.get("residual_home"),
        "residual_away": prediction.get("residual_away"),
        "strength": {"available": bool(prediction.get("available"))},
        "situational_residual_home": float(
            prediction.get("situational_residual_home") or 0.0
        ),
        "situational_residual_away": float(
            prediction.get("situational_residual_away") or 0.0
        ),
        "challenger": prediction,
    }


def compare_champion_challenger(
    *,
    champion: dict[str, Any] | None,
    challenger: dict[str, Any] | None,
    applied: str = "champion",
) -> dict[str, Any]:
    """Structured compare block for slate event residuals."""

    champ = champion or {}
    chall = challenger or {}
    c_home = num(champ.get("residual_home"))
    c_away = num(champ.get("residual_away"))
    h_home = num(chall.get("residual_home"))
    h_away = num(chall.get("residual_away"))

    def _delta(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return round(float(b) - float(a), 2)

    d_home = _delta(c_home, h_home)
    d_away = _delta(c_away, h_away)
    d_total = (
        round(float(d_home) + float(d_away), 2)
        if d_home is not None and d_away is not None
        else None
    )
    # Spread convention away − home.
    d_spread = (
        round(float(d_away) - float(d_home), 2)
        if d_home is not None and d_away is not None
        else None
    )

    return {
        "champion": {
            "residual_home": c_home,
            "residual_away": c_away,
            "shrink": champ.get("shrink"),
            "projection_confidence": champ.get("projection_confidence"),
            "policy_source": champ.get("policy_source"),
        },
        "challenger": {
            "residual_home": h_home,
            "residual_away": h_away,
            "mu_home": chall.get("mu_home"),
            "mu_away": chall.get("mu_away"),
            "sigma": chall.get("sigma"),
            "shrink": chall.get("shrink"),
            "model_active": chall.get("model_active"),
            "model_version": chall.get("model_version"),
            "features_used": chall.get("features_used"),
        },
        "delta_points": {
            "home": d_home,
            "away": d_away,
            "total": d_total,
            "spread": d_spread,
        },
        "applied": (
            "challenger" if applied == "challenger" else "champion"
        ),
    }


# --- fitting helpers -------------------------------------------------


def _normalize_fit_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        y_h = num(row.get("y_home"))
        y_a = num(row.get("y_away"))
        if y_h is None or y_a is None:
            continue
        vector = row.get("vector")
        if vector is None and row.get("features"):
            vector = features_to_vector(row["features"])
        if not vector or len(vector) != len(FEATURE_NAMES):
            continue
        feats = row.get("features") or {}
        out.append(
            {
                "vector": [float(v) for v in vector],
                "y_home": float(y_h),
                "y_away": float(y_a),
                "features": feats,
                "min_games": float(num(feats.get("min_games")) or 0.0),
                "disagreement": max(
                    float(num(feats.get("disagreement_spread_sd")) or 0.0),
                    float(num(feats.get("disagreement_total_sd")) or 0.0),
                ),
                "injury": max(
                    abs(float(num(feats.get("home_injury_adj")) or 0.0)),
                    abs(float(num(feats.get("away_injury_adj")) or 0.0)),
                ),
            }
        )
    return out


def _fit_ridge(
    x: np.ndarray,
    y: np.ndarray,
    ridge_lambda: float,
) -> tuple[float, np.ndarray]:
    """Centered ridge: intercept = mean(y), coef via (X'X + λI)^{-1} X'y."""

    y_mean = float(np.mean(y))
    y_c = y - y_mean
    x_mean = np.mean(x, axis=0)
    x_c = x - x_mean
    p = x_c.shape[1]
    xtx = x_c.T @ x_c + ridge_lambda * np.eye(p)
    xty = x_c.T @ y_c
    try:
        coef = np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        coef = np.linalg.pinv(xtx) @ xty
    # Prediction: y_mean + (x - x_mean) · coef
    # = (y_mean - x_mean · coef) + x · coef
    intercept = y_mean - float(x_mean @ coef)
    return intercept, coef


def _fit_sigma_buckets(
    samples: list[dict[str, Any]],
    resid_home: np.ndarray,
    resid_away: np.ndarray,
) -> dict[str, float]:
    pooled = np.sqrt(0.5 * (resid_home ** 2 + resid_away ** 2))
    by_label: dict[str, list[float]] = {
        label: [] for label, _ in UNCERTAINTY_BUCKETS
    }
    for index, sample in enumerate(samples):
        games = sample["min_games"]
        disagreement = sample["disagreement"]
        injury = sample["injury"]
        for label, predicate in UNCERTAINTY_BUCKETS:
            if predicate(games, disagreement, injury):
                by_label[label].append(float(pooled[index]))
                break

    out: dict[str, float] = {}
    defaults = prior_challenger_model()["sigma_by_bucket"]
    for label, values in by_label.items():
        if len(values) >= 5:
            out[label] = round(float(np.sqrt(np.mean(np.square(values)))), 3)
        else:
            out[label] = float(defaults.get(label) or 4.0)
    return out


def _predict_mu(
    vector: list[float],
    model: dict[str, Any],
) -> tuple[float, float]:
    names = model.get("feature_names") or list(FEATURE_NAMES)
    coef_h = model.get("coef_home") or [0.0] * len(names)
    coef_a = model.get("coef_away") or [0.0] * len(names)
    # Align vector to model feature order if needed.
    if list(names) == list(FEATURE_NAMES):
        x = np.asarray(vector, dtype=float)
        ch = np.asarray(coef_h, dtype=float)
        ca = np.asarray(coef_a, dtype=float)
    else:
        feat_map = {
            name: vector[index]
            for index, name in enumerate(FEATURE_NAMES)
            if index < len(vector)
        }
        x = np.asarray(
            [float(feat_map.get(name) or 0.0) for name in names],
            dtype=float,
        )
        ch = np.asarray(coef_h[: len(names)], dtype=float)
        ca = np.asarray(coef_a[: len(names)], dtype=float)
    inter_h = float(model.get("intercept_home") or 0.0)
    inter_a = float(model.get("intercept_away") or 0.0)
    if len(ch) != len(x):
        ch = np.resize(ch, len(x))
    if len(ca) != len(x):
        ca = np.resize(ca, len(x))
    return float(inter_h + x @ ch), float(inter_a + x @ ca)


def _confidence_from_shrink(shrink: float) -> str:
    if shrink >= 0.45:
        return "High"
    if shrink >= 0.25:
        return "Moderate"
    return "Low"


def _empty_prediction(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": False,
        "architecture": "market + residual",
        "model_role": "challenger",
        "model_version": model.get("model_version"),
        "method": model.get("method"),
        "model_active": bool(model.get("active")),
        "mu_home": 0.0,
        "mu_away": 0.0,
        "sigma": 6.5,
        "shrink": 0.0,
        "residual_home": 0.0,
        "residual_away": 0.0,
        "raw_residual_home": 0.0,
        "raw_residual_away": 0.0,
        "features_used": list(FEATURE_NAMES),
        "projection_confidence": "Low",
    }
