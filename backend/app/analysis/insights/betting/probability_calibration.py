"""
Probability calibration for betting markets.

Raw edge→logistic probabilities are not guaranteed to match
empirical win rates. This layer learns a mapping from
historical (predicted_probability, actual_result) pairs:

  raw_p  →  calibrated_p

Supported methods:
  - platt   : logistic scaling on logit(p)
  - isotonic: monotone PAV regression
  - beta    : 3-parameter beta calibration
  - auto    : isotonic when n is large enough, else Platt

Identity is returned until a minimum sample size is met.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

from app.analysis.insights.betting.pricing import num


MIN_SAMPLES_PLATT = 25
MIN_SAMPLES_ISOTONIC = 40
MIN_SAMPLES_BETA = 40
EPS = 1e-6


def collect_calibration_samples(
    rows: list[dict[str, Any]],
    *,
    market_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract decided bets with a usable predicted probability.

    Prefers ``raw_model_probability`` so recalibration does not
    fit on already-calibrated values.
    """

    samples: list[dict[str, Any]] = []
    for row in rows or []:
        result = str(row.get("result") or "").lower()
        if result not in {"won", "lost"}:
            continue
        mtype = str(row.get("market_type") or "").lower()
        if market_type and mtype != market_type.lower():
            continue
        pred = num(row.get("raw_model_probability"))
        if pred is None:
            pred = num(row.get("model_probability"))
        if pred is None:
            continue
        pred = float(np.clip(pred, EPS, 1.0 - EPS))
        samples.append(
            {
                "predicted_probability": pred,
                "actual_result": 1 if result == "won" else 0,
                "market_type": mtype or None,
                "edge": num(row.get("edge")),
                "confidence": row.get("confidence"),
                "market_id": row.get("market_id"),
            }
        )
    return samples


def fit_probability_calibration(
    samples: list[dict[str, Any]],
    *,
    method: str = "auto",
    market_type: str | None = None,
) -> dict[str, Any]:
    """
    Fit a calibration map. Returns a serializable model payload.

    ``samples`` may be settled result rows or normalized dicts with
    ``predicted_probability`` / ``actual_result``.
    """

    normalized = _normalize_samples(samples, market_type=market_type)
    n = len(normalized)
    if n < MIN_SAMPLES_PLATT:
        return _identity_model(
            method=method,
            market_type=market_type,
            sample_size=n,
            reason="insufficient_samples",
        )

    y = np.asarray(
        [int(s["actual_result"]) for s in normalized],
        dtype=float,
    )
    p = np.asarray(
        [float(s["predicted_probability"]) for s in normalized],
        dtype=float,
    )
    p = np.clip(p, EPS, 1.0 - EPS)

    chosen = str(method or "auto").lower().strip()
    if chosen == "auto":
        chosen = "isotonic" if n >= MIN_SAMPLES_ISOTONIC else "platt"

    if chosen == "isotonic" and n >= MIN_SAMPLES_ISOTONIC:
        model = _fit_isotonic(p, y)
    elif chosen == "beta" and n >= MIN_SAMPLES_BETA:
        model = _fit_beta(p, y)
    else:
        chosen = "platt"
        model = _fit_platt(p, y)

    calibrated = apply_probability_calibration(p, model)
    metrics = reliability_metrics(p, y, calibrated)

    return {
        **model,
        "method": chosen,
        "market_type": market_type,
        "sample_size": n,
        "active": True,
        "metrics": metrics,
        "note": (
            f"Calibrated {n} decided bets with {chosen}. "
            f"Brier {metrics['brier_raw']:.4f} → "
            f"{metrics['brier_calibrated']:.4f}."
        ),
    }


def _normalize_samples(
    samples: list[dict[str, Any]],
    *,
    market_type: str | None = None,
) -> list[dict[str, Any]]:
    if not samples:
        return []
    first = samples[0]
    if "predicted_probability" in first and "actual_result" in first:
        out: list[dict[str, Any]] = []
        for row in samples:
            pred = num(row.get("predicted_probability"))
            actual = row.get("actual_result")
            if pred is None or actual not in {0, 1, True, False}:
                continue
            mtype = str(row.get("market_type") or "").lower() or None
            if market_type and mtype != str(market_type).lower():
                continue
            out.append(
                {
                    "predicted_probability": float(
                        np.clip(pred, EPS, 1.0 - EPS)
                    ),
                    "actual_result": int(bool(actual)),
                    "market_type": mtype,
                    "edge": num(row.get("edge")),
                    "confidence": row.get("confidence"),
                }
            )
        return out
    return collect_calibration_samples(samples, market_type=market_type)


def apply_probability_calibration(
    probability: float | np.ndarray | None,
    model: dict[str, Any] | None,
) -> float | np.ndarray | None:
    """Map raw probability → calibrated probability."""

    if probability is None:
        return None
    if not model or not model.get("active"):
        return probability

    method = str(model.get("method") or "identity").lower()
    arr = np.asarray(probability, dtype=float)
    scalar = arr.ndim == 0
    p = np.clip(arr.astype(float), EPS, 1.0 - EPS)

    if method == "platt":
        a = float(model.get("a") or 1.0)
        b = float(model.get("b") or 0.0)
        out = _sigmoid(a * _logit(p) + b)
    elif method == "isotonic":
        xs = np.asarray(model.get("x") or [], dtype=float)
        ys = np.asarray(model.get("y") or [], dtype=float)
        if len(xs) == 0 or len(ys) == 0:
            out = p
        else:
            out = np.interp(p, xs, ys)
    elif method == "beta":
        a = float(model.get("a") or 1.0)
        b = float(model.get("b") or 1.0)
        c = float(model.get("c") or 0.0)
        out = _sigmoid(c + a * np.log(p) + b * np.log(1.0 - p))
    else:
        out = p

    out = np.clip(out, EPS, 1.0 - EPS)
    if scalar:
        return float(out)
    return out


def calibrate_market_probability(
    raw_probability: float | None,
    *,
    model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper used by slate market builders."""

    raw = num(raw_probability)
    if raw is None:
        return {
            "raw_model_probability": None,
            "model_probability": None,
            "calibrated": False,
            "method": None,
        }
    raw_clipped = float(np.clip(raw, EPS, 1.0 - EPS))
    if not model or not model.get("active"):
        return {
            "raw_model_probability": round(raw_clipped, 4),
            "model_probability": round(raw_clipped, 4),
            "calibrated": False,
            "method": "identity",
        }
    cal = apply_probability_calibration(raw_clipped, model)
    return {
        "raw_model_probability": round(raw_clipped, 4),
        "model_probability": round(float(cal), 4),
        "calibrated": True,
        "method": model.get("method"),
        "sample_size": model.get("sample_size"),
    }


def reliability_metrics(
    raw: np.ndarray,
    y: np.ndarray,
    calibrated: np.ndarray | None = None,
    *,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Brier score + ECE for raw (and optional calibrated) probs."""

    raw = np.clip(np.asarray(raw, dtype=float), EPS, 1.0 - EPS)
    y = np.asarray(y, dtype=float)
    cal = (
        np.clip(np.asarray(calibrated, dtype=float), EPS, 1.0 - EPS)
        if calibrated is not None
        else None
    )
    return {
        "brier_raw": round(float(np.mean((raw - y) ** 2)), 6),
        "brier_calibrated": (
            round(float(np.mean((cal - y) ** 2)), 6)
            if cal is not None
            else None
        ),
        "ece_raw": round(_expected_calibration_error(raw, y, n_bins), 6),
        "ece_calibrated": (
            round(_expected_calibration_error(cal, y, n_bins), 6)
            if cal is not None
            else None
        ),
        "n": int(len(y)),
        "empirical_win_rate": round(float(np.mean(y)), 4),
        "mean_predicted_raw": round(float(np.mean(raw)), 4),
        "mean_predicted_calibrated": (
            round(float(np.mean(cal)), 4) if cal is not None else None
        ),
    }


def serialize_calibration_model(model: dict[str, Any] | None) -> str:
    return json.dumps(model or {}, sort_keys=True, default=_json_default)


def deserialize_calibration_model(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return None


# --- fitters ---------------------------------------------------------


def _fit_platt(p: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """
    Platt scaling via Newton-Raphson on Bernoulli NLL.

    calibrated = sigmoid(a * logit(p) + b)
    """

    x = _logit(p)
    a, b = 1.0, 0.0
    for _ in range(40):
        z = a * x + b
        pred = _sigmoid(z)
        # Gradient / Hessian of negative log-likelihood.
        err = pred - y
        g_a = float(np.dot(err, x))
        g_b = float(np.sum(err))
        w = pred * (1.0 - pred)
        h_aa = float(np.dot(w, x * x)) + 1e-8
        h_bb = float(np.sum(w)) + 1e-8
        h_ab = float(np.dot(w, x))
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-12:
            break
        da = (h_bb * g_a - h_ab * g_b) / det
        db = (h_aa * g_b - h_ab * g_a) / det
        a -= da
        b -= db
        if abs(da) + abs(db) < 1e-8:
            break
    return {
        "method": "platt",
        "a": round(float(a), 6),
        "b": round(float(b), 6),
        "active": True,
    }


def _fit_isotonic(p: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """Pool Adjacent Violators — nondecreasing calibration curve."""

    order = np.argsort(p)
    x_sorted = p[order].astype(float)
    y_sorted = y[order].astype(float)
    n = len(y_sorted)
    if n == 0:
        return _identity_model(method="isotonic", reason="empty_fit")

    # Block representation: (weight, sum_y, sum_x)
    weights = [1.0] * n
    sums = list(y_sorted)
    xsums = list(x_sorted)

    i = 0
    while i < len(sums) - 1:
        mean_i = sums[i] / weights[i]
        mean_next = sums[i + 1] / weights[i + 1]
        if mean_i <= mean_next + 1e-15:
            i += 1
            continue
        # Merge with next block and walk backward.
        weights[i] += weights[i + 1]
        sums[i] += sums[i + 1]
        xsums[i] += xsums[i + 1]
        del weights[i + 1], sums[i + 1], xsums[i + 1]
        while i > 0:
            mean_prev = sums[i - 1] / weights[i - 1]
            mean_cur = sums[i] / weights[i]
            if mean_prev <= mean_cur + 1e-15:
                break
            weights[i - 1] += weights[i]
            sums[i - 1] += sums[i]
            xsums[i - 1] += xsums[i]
            del weights[i], sums[i], xsums[i]
            i -= 1

    grid_x: list[float] = []
    grid_y: list[float] = []
    for w, s, xs in zip(weights, sums, xsums):
        grid_x.append(float(xs / w))
        grid_y.append(float(np.clip(s / w, EPS, 1.0 - EPS)))

    if grid_x[0] > EPS:
        grid_x.insert(0, float(EPS))
        grid_y.insert(0, grid_y[0])
    if grid_x[-1] < 1.0 - EPS:
        grid_x.append(float(1.0 - EPS))
        grid_y.append(grid_y[-1])

    return {
        "method": "isotonic",
        "x": [round(v, 6) for v in grid_x],
        "y": [round(v, 6) for v in grid_y],
        "active": True,
    }


def _fit_beta(p: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """
    Beta calibration: sigmoid(c + a*log(p) + b*log(1-p)).

    Fit with Newton-ish gradient steps on Bernoulli NLL.
    """

    lp = np.log(p)
    lq = np.log(1.0 - p)
    a, b, c = 1.0, -1.0, 0.0
    for _ in range(60):
        z = c + a * lp + b * lq
        pred = _sigmoid(z)
        err = pred - y
        w = pred * (1.0 - pred)
        g = np.array(
            [
                float(np.dot(err, lp)),
                float(np.dot(err, lq)),
                float(np.sum(err)),
            ]
        )
        H = np.array(
            [
                [
                    float(np.dot(w, lp * lp)) + 1e-6,
                    float(np.dot(w, lp * lq)),
                    float(np.dot(w, lp)),
                ],
                [
                    float(np.dot(w, lp * lq)),
                    float(np.dot(w, lq * lq)) + 1e-6,
                    float(np.dot(w, lq)),
                ],
                [
                    float(np.dot(w, lp)),
                    float(np.dot(w, lq)),
                    float(np.sum(w)) + 1e-6,
                ],
            ]
        )
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        a -= float(step[0])
        b -= float(step[1])
        c -= float(step[2])
        if float(np.sum(np.abs(step))) < 1e-8:
            break
    return {
        "method": "beta",
        "a": round(float(a), 6),
        "b": round(float(b), 6),
        "c": round(float(c), 6),
        "active": True,
    }


# --- helpers ---------------------------------------------------------


def _identity_model(
    *,
    method: str = "identity",
    market_type: str | None = None,
    sample_size: int = 0,
    reason: str = "identity",
) -> dict[str, Any]:
    return {
        "method": "identity",
        "requested_method": method,
        "market_type": market_type,
        "sample_size": sample_size,
        "active": False,
        "metrics": None,
        "note": (
            f"Identity calibration ({reason}); need at least "
            f"{MIN_SAMPLES_PLATT} decided bets."
        ),
    }


def _logit(p: np.ndarray | float) -> np.ndarray | float:
    p = np.clip(p, EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def _sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    z_arr = np.asarray(z, dtype=float)
    # Numerically stable sigmoid.
    out = np.empty(z_arr.shape, dtype=float)
    if z_arr.shape == ():
        value = float(z_arr)
        if value >= 0:
            return 1.0 / (1.0 + math.exp(-value))
        exp_z = math.exp(value)
        return exp_z / (1.0 + exp_z)
    pos = z_arr >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z_arr[pos]))
    exp_z = np.exp(z_arr[~pos])
    out[~pos] = exp_z / (1.0 + exp_z)
    return out


def _expected_calibration_error(
    p: np.ndarray,
    y: np.ndarray,
    n_bins: int,
) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(p)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        if i == n_bins - 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        if not np.any(mask):
            continue
        conf = float(np.mean(p[mask]))
        acc = float(np.mean(y[mask]))
        ece += (np.sum(mask) / n) * abs(acc - conf)
    return float(ece)


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")
