"""Versioned player forecast passed to the DFS optimizer.

``projection``, ``base_projection``, and ``raw_projection`` stay
on the player. This contract adds the simulated distribution,
workload, and provenance the optimizer needs in order to value a
plausible high score without treating points-per-dollar as the
reason to roster someone.
"""

from __future__ import annotations

from typing import Any

import numpy as np

FORECAST_VERSION = "player_forecast_v1"
FORECAST_SOURCE = (
    "joint_game_simulation:game_forecast+player_role+component_production"
)
CAPTAIN_MULTIPLIER = 1.5
OUTCOME_SAMPLE_SIZE = 40

# (usable score, strong outcome) by contest and position.
# probability_10_plus and probability_20_plus stay the literal
# chances of 10 and 20. strong_outcome_probability uses the
# high threshold from this table, so a contest can move it.
DEFAULT_OUTCOME_THRESHOLDS: dict[str, dict[str, tuple[float, float]]] = {
    "classic": {
        "QB": (15.0, 22.0),
        "RB": (10.0, 20.0),
        "WR": (10.0, 20.0),
        "TE": (8.0, 16.0),
        "K": (6.0, 10.0),
        "DEF": (6.0, 12.0),
        "DST": (6.0, 12.0),
    },
    "showdown": {
        "QB": (12.0, 20.0),
        "RB": (10.0, 20.0),
        "WR": (10.0, 20.0),
        "TE": (8.0, 15.0),
        "K": (6.0, 10.0),
        "DEF": (5.0, 10.0),
        "DST": (5.0, 10.0),
    },
}

_PRIMARY_SHARE = {
    "QB": "dropback_share",
    "RB": "carry_share",
    "WR": "target_share",
    "TE": "target_share",
    "K": "field_goal_share",
}


def thresholds_for(
    position: str | None,
    contest_type: str | None,
    overrides: dict[str, tuple[float, float]] | None = None,
) -> tuple[float, float]:
    contest = (
        "showdown"
        if str(contest_type or "").strip().lower() == "showdown"
        else "classic"
    )
    pos = str(position or "WR").strip().upper()
    if pos == "DST":
        pos = "DEF"
    if overrides and pos in overrides:
        low, high = overrides[pos]
        return float(low), float(high)
    table = DEFAULT_OUTCOME_THRESHOLDS[contest]
    return table.get(pos, table["WR"])


def apply_forecast_contract(
    player: dict[str, Any],
    draws: np.ndarray,
    *,
    contest_type: str | None = "classic",
    floor_percentile: float = 10.0,
    ceiling_percentile: float = 90.0,
    captain_multiplier: float = CAPTAIN_MULTIPLIER,
    threshold_overrides: dict[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Attach the forecast. Leaves the legacy projection fields alone."""

    contract = build_forecast_contract(
        player,
        draws,
        contest_type=contest_type,
        floor_percentile=floor_percentile,
        ceiling_percentile=ceiling_percentile,
        captain_multiplier=captain_multiplier,
        threshold_overrides=threshold_overrides,
    )
    player["forecast"] = contract
    for key in (
        "expected_points",
        "median_projection",
        "floor_projection",
        "ceiling_projection",
        "probability_10_plus",
        "probability_20_plus",
        "strong_outcome_probability",
        "strong_outcome_threshold",
        "projected_opportunity",
        "role_change_signal",
        "projection_uncertainty",
        "projection_version",
    ):
        player[key] = contract[key]
    # Provenance lives on the contract. Overview already uses
    # projection_source for the weekly environment label.
    if not player.get("projection_source"):
        player["projection_source"] = contract["projection_source"]
    player["floor"] = contract["floor_projection"]
    player["ceiling"] = contract["ceiling_projection"]
    return contract


def build_forecast_contract(
    player: dict[str, Any],
    draws: np.ndarray,
    *,
    contest_type: str | None = "classic",
    floor_percentile: float = 10.0,
    ceiling_percentile: float = 90.0,
    captain_multiplier: float = CAPTAIN_MULTIPLIER,
    threshold_overrides: dict[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    values = np.asarray(draws, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        values = np.zeros(1)
    position = str(
        (player.get("role_forecast") or {}).get("position")
        or player.get("position")
        or "WR"
    ).upper()
    usable, strong_at = thresholds_for(
        position,
        contest_type,
        threshold_overrides,
    )
    median = float(np.percentile(values, 50))
    floor = float(np.percentile(values, floor_percentile))
    ceiling = float(np.percentile(values, ceiling_percentile))
    mean = float(np.mean(values))
    contest = (
        "showdown"
        if str(contest_type or "").strip().lower() == "showdown"
        else "classic"
    )
    captain_draws = values * float(captain_multiplier or CAPTAIN_MULTIPLIER)
    return {
        "projection_version": FORECAST_VERSION,
        "projection_source": FORECAST_SOURCE,
        "contest_type": contest,
        "position": position,
        "expected_points": round(mean, 2),
        "median_projection": round(median, 2),
        "floor_projection": round(floor, 2),
        "ceiling_projection": round(ceiling, 2),
        "probability_10_plus": _rate_at(values, 10.0),
        "probability_20_plus": _rate_at(values, 20.0),
        "usable_outcome_threshold": usable,
        "usable_outcome_probability": _rate_at(values, usable),
        "strong_outcome_threshold": strong_at,
        "strong_outcome_probability": _rate_at(values, strong_at),
        "captain_expected_points": round(float(np.mean(captain_draws)), 2),
        "captain_strong_outcome_probability": _rate_at(
            captain_draws,
            strong_at,
        ),
        "projected_opportunity": _projected_opportunity(player, position),
        "role_change_signal": _role_change_signal(player),
        "projection_uncertainty": round(float(np.std(values)), 2),
        "outcome_sample": _downsample(values),
        "floor_percentile": floor_percentile,
        "ceiling_percentile": ceiling_percentile,
        "n_sims": int(len(values)),
    }


def lineup_decision_score(players: list[dict[str, Any]]) -> float | None:
    """
    Rank a showdown lineup from the joint distribution.

    Mean keeps expected points in the decision, the upper percentile
    keeps a credible spike, and the lower percentile keeps downside.
    Salary is not in this score.
    """

    outcomes = evaluate_lineup_outcomes(players)
    if outcomes is None:
        return None
    return (
        0.45 * float(outcomes["mean"])
        + 0.40 * float(outcomes["ceiling"])
        + 0.15 * float(outcomes["floor"])
    )


def evaluate_lineup_outcomes(
    players: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Captain-scaled lineup distribution from aligned simulations."""

    columns: list[np.ndarray] = []
    ids: list[str] = []
    slots: list[str] = []
    for player in players:
        sample = _sample_of(player)
        if sample is None:
            return None
        mult = 1.0
        slot = str(player.get("slot") or "").upper()
        if player.get("is_captain") or slot == "CPT":
            mult = float(
                player.get("captain_multiplier") or CAPTAIN_MULTIPLIER
            )
        columns.append(sample * mult)
        ids.append(str(player.get("player_id") or ""))
        slots.append(slot or ("CPT" if player.get("is_captain") else "FLEX"))
    if len(columns) < 2:
        return None
    width = min(len(column) for column in columns)
    if width < 8:
        return None
    matrix = np.vstack([column[:width] for column in columns])
    totals = matrix.sum(axis=0)
    high_cut = float(np.percentile(totals, 75))
    high = totals >= high_cut
    importance: dict[str, float] = {}
    for index, pid in enumerate(ids):
        if not pid:
            continue
        share = matrix[index] / np.maximum(totals, 1e-6)
        top = matrix[index] >= matrix.max(axis=0) - 1e-6
        importance[pid] = round(
            float(np.mean(high & ((share >= 0.18) | top))),
            3,
        )
    captain_index = next(
        (i for i, slot in enumerate(slots) if slot == "CPT"),
        None,
    )
    flex_indexes = [i for i, slot in enumerate(slots) if slot != "CPT"]
    captain_upside = None
    if captain_index is not None:
        captain_upside = round(
            float(np.mean(matrix[captain_index] >= 20.0)),
            3,
        )
    flex_upside = None
    if flex_indexes:
        flex_hits = [
            float(np.mean(matrix[index] >= 15.0)) for index in flex_indexes
        ]
        flex_upside = round(float(np.mean(flex_hits)), 3)
    return {
        "source": "joint_game_simulation",
        "projection_version": FORECAST_VERSION,
        "n_sims": width,
        "mean": round(float(np.mean(totals)), 2),
        "floor": round(float(np.percentile(totals, 10)), 2),
        "ceiling": round(float(np.percentile(totals, 90)), 2),
        "mean_pairwise_correlation": _mean_correlation(matrix),
        "captain_upside": captain_upside,
        "flex_upside": flex_upside,
        "player_importance": importance,
    }


def _sample_of(player: dict[str, Any]) -> np.ndarray | None:
    forecast = player.get("forecast") or {}
    raw = forecast.get("outcome_sample")
    if not raw:
        raw = player.get("outcome_sample")
    if not raw:
        return None
    values = np.asarray(raw, dtype=float)
    if len(values) == 0 or not np.isfinite(values).all():
        return None
    return values


def _rate_at(values: np.ndarray, threshold: float) -> float:
    return round(float(np.mean(values >= float(threshold))), 3)


def _downsample(values: np.ndarray, size: int = OUTCOME_SAMPLE_SIZE) -> list[float]:
    if len(values) <= size:
        picked = values
    else:
        index = np.linspace(0, len(values) - 1, size).astype(int)
        picked = values[index]
    return [round(float(value), 2) for value in picked]


def _projected_opportunity(
    player: dict[str, Any],
    position: str,
) -> dict[str, Any]:
    role = player.get("role_forecast") or {}
    raw = role.get("opportunities") or {}
    components = {
        str(key): round(float(value), 2)
        for key, value in raw.items()
        if _is_number(value)
    }
    if not components:
        stats = ((player.get("scoring_components") or {}).get("stats")) or {}
        components = {
            str(key): round(float(value), 2)
            for key, value in stats.items()
            if _is_number(value)
        }
    return {"position": position, "components": components}


def _role_change_signal(player: dict[str, Any]) -> float:
    role = player.get("role_forecast") or {}
    listed = _int(role.get("listed_depth"))
    effective = _int(role.get("effective_depth"))
    signal = 0.0
    if listed and effective and listed != effective:
        signal = max(-1.0, min(1.0, (listed - effective) * 0.35))
    if role.get("promoted"):
        signal = max(signal, 0.25)
    position = str(role.get("position") or player.get("position") or "").upper()
    key = _PRIMARY_SHARE.get(position)
    current = _share((role.get("shares") or {}).get(key) if key else None)
    baseline = _share(_usage_value(player.get("historical_usage"), key))
    if current is not None and baseline is not None and baseline > 0:
        delta = (current - baseline) / max(baseline, 0.15)
        signal = max(-1.0, min(1.0, 0.5 * signal + 0.5 * delta))
    return round(float(signal), 3)


def _mean_correlation(matrix: np.ndarray) -> float | None:
    varied = matrix[np.std(matrix, axis=1) > 1e-6]
    if len(varied) < 2:
        return None
    coef = np.corrcoef(varied)
    upper = coef[np.triu_indices(len(varied), k=1)]
    upper = upper[np.isfinite(upper)]
    if len(upper) == 0:
        return None
    return round(float(np.mean(upper)), 3)


def _usage_value(usage: Any, key: str | None) -> Any:
    if not isinstance(usage, dict) or not key:
        return None
    if key in usage:
        return usage.get(key)
    nested = usage.get("shares")
    if isinstance(nested, dict):
        return nested.get(key)
    return None


def _share(value: Any) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if number > 1.5:
        number = number / 100.0
    return number


def _is_number(value: Any) -> bool:
    return _num(value) is not None


def _int(value: Any) -> int:
    number = _num(value)
    if number is None:
        return 0
    return int(number)


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
