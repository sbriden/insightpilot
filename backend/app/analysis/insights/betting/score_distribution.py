"""
Bivariate score-distribution engine.

Simulates paired (home, away) scores from projected means and a
learned covariance so spread / moneyline / total probabilities
come from the same draws — preserving score dependence.

Logistic pricing in ``pricing.py`` remains the applied default
until this engine wins out-of-sample; this module always produces
a shadow payload for comparison.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.analysis.insights.betting.pricing import num


MIN_FIT_SAMPLES = 80
DEFAULT_N_SIMS = 5000
MODEL_VERSION = "score_dist_bivar_v1"

# Cold-start priors (~game_scripts residual SDs / NFL typical).
PRIOR_SIGMA_HOME = 13.0
PRIOR_SIGMA_AWAY = 13.0
PRIOR_RHO = 0.25

# Feature scale coefficients: σ_eff = σ_base * (1 + Σ w_i * f_i)
PRIOR_SCALE_WEIGHTS: dict[str, float] = {
    "early_season": 0.12,
    "thin_sample": 0.18,
    "pace_abs": 0.06,
    "turnover_env": 0.08,
    "disagreement": 0.05,
}


def prior_score_distribution_model() -> dict[str, Any]:
    return {
        "method": "prior",
        "model_version": MODEL_VERSION,
        "active": False,
        "sample_size": 0,
        "sigma_home": PRIOR_SIGMA_HOME,
        "sigma_away": PRIOR_SIGMA_AWAY,
        "rho": PRIOR_RHO,
        "scale_weights": dict(PRIOR_SCALE_WEIGHTS),
        "metrics": None,
        "note": (
            "Cold-start bivariate normal priors "
            f"(σ≈{PRIOR_SIGMA_HOME}, ρ≈{PRIOR_RHO}). "
            f"Active after {MIN_FIT_SAMPLES} settled games."
        ),
    }


def fit_score_distribution(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Fit base σ_home / σ_away / ρ from residual score errors.

    Each row needs ``resid_home`` / ``resid_away``
    (= actual − projected_or_market means) and optional
    scale features for weight refinement.
    """

    samples = _normalize_fit_rows(rows)
    n = len(samples)
    if n < MIN_FIT_SAMPLES:
        model = prior_score_distribution_model()
        model["sample_size"] = n
        model["note"] = (
            f"Insufficient samples ({n} < {MIN_FIT_SAMPLES}); "
            "using cold-start prior."
        )
        return model

    rh = np.asarray([s["resid_home"] for s in samples], dtype=float)
    ra = np.asarray([s["resid_away"] for s in samples], dtype=float)
    sigma_h = float(np.std(rh, ddof=1))
    sigma_a = float(np.std(ra, ddof=1))
    if not math.isfinite(sigma_h) or sigma_h < 6.0:
        sigma_h = PRIOR_SIGMA_HOME
    if not math.isfinite(sigma_a) or sigma_a < 6.0:
        sigma_a = PRIOR_SIGMA_AWAY
    if sigma_h > 0 and sigma_a > 0:
        rho = float(np.corrcoef(rh, ra)[0, 1])
    else:
        rho = PRIOR_RHO
    if not math.isfinite(rho):
        rho = PRIOR_RHO
    rho = float(np.clip(rho, -0.05, 0.65))

    scale_weights = _fit_scale_weights(samples, rh, ra, sigma_h, sigma_a)

    metrics = {
        "n": n,
        "sigma_home": round(sigma_h, 3),
        "sigma_away": round(sigma_a, 3),
        "rho": round(rho, 4),
        "mae_home": round(float(np.mean(np.abs(rh))), 3),
        "mae_away": round(float(np.mean(np.abs(ra))), 3),
    }
    return {
        "method": "empirical_bivariate",
        "model_version": MODEL_VERSION,
        "active": True,
        "sample_size": n,
        "sigma_home": round(sigma_h, 4),
        "sigma_away": round(sigma_a, 4),
        "rho": round(rho, 4),
        "scale_weights": scale_weights,
        "metrics": metrics,
        "note": (
            f"Fitted on {n} games: "
            f"σ_h={sigma_h:.1f} σ_a={sigma_a:.1f} ρ={rho:.2f}."
        ),
    }


def estimate_game_covariance(
    *,
    model: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Matchup-aware σ_home, σ_away, ρ after feature scaling."""

    active = model or prior_score_distribution_model()
    feats = features or {}
    weights = active.get("scale_weights") or PRIOR_SCALE_WEIGHTS
    scale = 1.0
    for name, weight in weights.items():
        scale += float(weight) * float(num(feats.get(name)) or 0.0)
    scale = float(np.clip(scale, 0.75, 1.55))

    sigma_h = float(active.get("sigma_home") or PRIOR_SIGMA_HOME) * scale
    sigma_a = float(active.get("sigma_away") or PRIOR_SIGMA_AWAY) * scale
    rho = float(active.get("rho") if active.get("rho") is not None else PRIOR_RHO)
    rho = float(np.clip(rho, -0.05, 0.65))
    return {
        "sigma_home": round(sigma_h, 3),
        "sigma_away": round(sigma_a, 3),
        "rho": round(rho, 4),
        "scale": round(scale, 4),
    }


def build_distribution_features(
    *,
    week: int | None = None,
    min_games: float | None = None,
    pace_z: float | None = None,
    home_turnover_rate: float | None = None,
    away_turnover_rate: float | None = None,
    disagreement_spread_sd: float | None = None,
    disagreement_total_sd: float | None = None,
    missing_strength: float | None = None,
) -> dict[str, float]:
    """Normalized 0–1-ish drivers that inflate score variance."""

    games = float(min_games or 0.0)
    early = 1.0 if games < 3 or (week is not None and int(week) <= 3) else 0.0
    thin = 1.0 if games < 3 else (0.5 if games < 5 else 0.0)
    if missing_strength and float(missing_strength) >= 0.5:
        thin = 1.0
    pace_abs = min(2.0, abs(float(pace_z or 0.0))) / 2.0
    to_home = float(home_turnover_rate or 0.0)
    to_away = float(away_turnover_rate or 0.0)
    # Typical NFL TO/play ~0.02–0.04; map excess to 0–1.
    turnover_env = min(
        1.0,
        max(0.0, ((to_home + to_away) / 2.0 - 0.02) / 0.04),
    )
    disagree = max(
        float(disagreement_spread_sd or 0.0),
        float(disagreement_total_sd or 0.0),
    )
    disagreement = min(1.0, disagree / 4.0)
    return {
        "early_season": early,
        "thin_sample": thin,
        "pace_abs": pace_abs,
        "turnover_env": turnover_env,
        "disagreement": disagreement,
        "min_games": games,
        "missing_strength": float(missing_strength or 0.0),
    }


def simulate_game_scores(
    *,
    mean_home: float,
    mean_away: float,
    model: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    market_spread: float | None = None,
    market_total: float | None = None,
    n_sims: int = DEFAULT_N_SIMS,
    event_id: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Draw paired scores and derive market probabilities.

    Spread convention matches nflverse / slate: home-team line
    (negative = home favored). Margin = home − away.
    """

    active = model or prior_score_distribution_model()
    cov = estimate_game_covariance(model=active, features=features)
    sigma_h = cov["sigma_home"]
    sigma_a = cov["sigma_away"]
    rho = cov["rho"]

    rng = np.random.default_rng(_seed_for_event(event_id, seed))
    means = np.array([float(mean_home), float(mean_away)], dtype=float)
    cov_matrix = np.array(
        [
            [sigma_h ** 2, rho * sigma_h * sigma_a],
            [rho * sigma_h * sigma_a, sigma_a ** 2],
        ],
        dtype=float,
    )
    # Numerical safety if |ρ| near 1.
    try:
        draws = rng.multivariate_normal(means, cov_matrix, size=int(n_sims))
    except np.linalg.LinAlgError:
        draws = rng.normal(means, [sigma_h, sigma_a], size=(int(n_sims), 2))
    home = np.clip(draws[:, 0], 0.0, None)
    away = np.clip(draws[:, 1], 0.0, None)
    home = np.round(home, 1)
    away = np.round(away, 1)

    margin = home - away  # home − away
    total = home + away
    # nflverse spread: home line; cover home when home + line > away
    # i.e. margin + line > 0.
    home_wins = home > away
    away_wins = away > home
    ties = home == away

    home_win_prob = float(np.mean(home_wins))
    away_win_prob = float(np.mean(away_wins))
    tie_prob = float(np.mean(ties))

    cover_block = _cover_at_line(margin, market_spread)
    over_block = _over_at_line(total, market_total)

    # Analytic SDs for reporting.
    sigma_margin = math.sqrt(
        sigma_h ** 2 + sigma_a ** 2 - 2.0 * rho * sigma_h * sigma_a
    )
    sigma_total = math.sqrt(
        sigma_h ** 2 + sigma_a ** 2 + 2.0 * rho * sigma_h * sigma_a
    )

    expected_home = round(float(np.mean(home)), 2)
    expected_away = round(float(np.mean(away)), 2)
    expected_margin = round(float(np.mean(margin)), 2)
    expected_total = round(float(np.mean(total)), 2)

    return {
        "available": True,
        "engine": "bivariate_normal",
        "model_version": active.get("model_version") or MODEL_VERSION,
        "method": active.get("method"),
        "model_active": bool(active.get("active")),
        "n_sims": int(n_sims),
        "expected": {
            "home": expected_home,
            "away": expected_away,
            "margin": expected_margin,
            "total": expected_total,
        },
        "sigma": {
            "home": round(sigma_h, 3),
            "away": round(sigma_a, 3),
            "margin": round(sigma_margin, 3),
            "total": round(sigma_total, 3),
        },
        "rho": round(rho, 4),
        "scale": cov.get("scale"),
        "home_win_prob": round(home_win_prob, 4),
        "away_win_prob": round(away_win_prob, 4),
        "tie_prob": round(tie_prob, 4),
        "margin_histogram": _histogram(margin, bin_width=3.0, lo=-35, hi=35),
        "total_histogram": _histogram(total, bin_width=3.0, lo=20, hi=70),
        "cover_at_line": cover_block,
        "over_at_line": over_block,
        "uncertainty": {
            "sigma_margin": round(sigma_margin, 3),
            "sigma_total": round(sigma_total, 3),
            "scale": cov.get("scale"),
            "entropy_proxy": round(
                min(1.0, sigma_margin / 20.0), 3
            ),
        },
        "data_quality": {
            "sample_depth": (features or {}).get("min_games"),
            "missing_strength": (features or {}).get("missing_strength"),
            "model_active": bool(active.get("active")),
            "sample_size": active.get("sample_size"),
            "method": active.get("method"),
        },
        "features": features,
        # Compact arrays for engine dispatch (not full hist).
        "_probs": {
            "home_win": home_win_prob,
            "away_win": away_win_prob,
            "home_cover": (cover_block or {}).get("home_cover"),
            "over": (over_block or {}).get("over"),
        },
    }


def probabilities_from_simulation(
    simulation: dict[str, Any] | None,
    *,
    market_spread: float | None = None,
    market_total: float | None = None,
) -> dict[str, float | None]:
    """Extract cover / over / win probs from a sim payload."""

    if not simulation or not simulation.get("available"):
        return {
            "home_cover": None,
            "over": None,
            "home_win": None,
            "away_win": None,
        }
    cover = simulation.get("cover_at_line") or {}
    over = simulation.get("over_at_line") or {}
    # Recompute if caller asks for a different line than stored.
    if (
        market_spread is not None
        and cover.get("line") is not None
        and abs(float(cover["line"]) - float(market_spread)) > 1e-6
    ):
        # Without raw draws we cannot recompute; use stored.
        pass
    return {
        "home_cover": num(cover.get("home_cover")),
        "over": num(over.get("over")),
        "home_win": num(simulation.get("home_win_prob")),
        "away_win": num(simulation.get("away_win_prob")),
    }


def empty_score_distribution(
    *,
    reason: str = "missing_means",
) -> dict[str, Any]:
    return {
        "available": False,
        "engine": "bivariate_normal",
        "model_version": MODEL_VERSION,
        "n_sims": 0,
        "note": reason,
        "home_win_prob": None,
        "away_win_prob": None,
        "cover_at_line": None,
        "over_at_line": None,
    }


# --- helpers ----------------------------------------------------------


def _normalize_fit_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        rh = num(row.get("resid_home"))
        ra = num(row.get("resid_away"))
        if rh is None or ra is None:
            # Fall back to actual − market.
            ah = num(row.get("actual_home"))
            aa = num(row.get("actual_away"))
            mh = num(row.get("market_home")) or num(row.get("mean_home"))
            ma = num(row.get("market_away")) or num(row.get("mean_away"))
            if ah is None or aa is None or mh is None or ma is None:
                continue
            rh = float(ah) - float(mh)
            ra = float(aa) - float(ma)
        feats = row.get("features") or {}
        if not feats and row.get("dist_features"):
            feats = row["dist_features"]
        out.append(
            {
                "resid_home": float(rh),
                "resid_away": float(ra),
                "features": feats,
            }
        )
    return out


def _fit_scale_weights(
    samples: list[dict[str, Any]],
    resid_home: np.ndarray,
    resid_away: np.ndarray,
    sigma_h: float,
    sigma_a: float,
) -> dict[str, float]:
    """
    Light empirical tweak: compare residual RMSE in high-feature
    cohorts vs base; convert excess RMSE into scale weights.
    Falls back to priors when cohorts are thin.
    """

    weights = dict(PRIOR_SCALE_WEIGHTS)
    pooled = np.sqrt(
        0.5
        * (
            (resid_home / max(sigma_h, 1e-6)) ** 2
            + (resid_away / max(sigma_a, 1e-6)) ** 2
        )
    )
    base_mask = np.ones(len(samples), dtype=bool)
    for key in ("early_season", "thin_sample", "pace_abs", "turnover_env", "disagreement"):
        vals = np.asarray(
            [float((s["features"] or {}).get(key) or 0.0) for s in samples]
        )
        high = vals >= 0.5
        if int(high.sum()) < 12 or int((~high).sum()) < 12:
            continue
        high_rmse = float(np.mean(pooled[high]))
        low_rmse = float(np.mean(pooled[~high & base_mask]))
        if low_rmse <= 1e-6:
            continue
        excess = max(0.0, (high_rmse / low_rmse) - 1.0)
        # Map excess RMSE to weight; keep modest.
        weights[key] = round(float(np.clip(excess * 0.5, 0.02, 0.25)), 4)
    return weights


def _cover_at_line(
    margin: np.ndarray,
    market_spread: float | None,
) -> dict[str, Any] | None:
    if market_spread is None:
        return None
    line = float(market_spread)
    # Home covers when home_score + line > away_score
    # → margin + line > 0. Push when equal.
    adj = margin + line
    home_cover = float(np.mean(adj > 0))
    away_cover = float(np.mean(adj < 0))
    push = float(np.mean(adj == 0))
    return {
        "line": line,
        "home_cover": round(home_cover, 4),
        "away_cover": round(away_cover, 4),
        "push": round(push, 4),
    }


def _over_at_line(
    total: np.ndarray,
    market_total: float | None,
) -> dict[str, Any] | None:
    if market_total is None:
        return None
    line = float(market_total)
    over = float(np.mean(total > line))
    under = float(np.mean(total < line))
    push = float(np.mean(total == line))
    return {
        "line": line,
        "over": round(over, 4),
        "under": round(under, 4),
        "push": round(push, 4),
    }


def _histogram(
    values: np.ndarray,
    *,
    bin_width: float,
    lo: float,
    hi: float,
) -> list[dict[str, Any]]:
    edges = np.arange(lo, hi + bin_width, bin_width)
    counts, _ = np.histogram(values, bins=edges)
    total = max(1, int(counts.sum()))
    out: list[dict[str, Any]] = []
    for i, count in enumerate(counts):
        out.append(
            {
                "bin_start": round(float(edges[i]), 1),
                "bin_end": round(float(edges[i + 1]), 1),
                "count": int(count),
                "density": round(float(count) / total, 4),
            }
        )
    return out


def _seed_for_event(
    event_id: str | None,
    seed: int | None,
) -> int:
    if seed is not None:
        return int(seed)
    if not event_id:
        return 42
    return abs(hash(str(event_id))) % (2**31 - 1)
