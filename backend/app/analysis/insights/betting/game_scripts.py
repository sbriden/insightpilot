"""
Projected game-script probabilities for Sports Betting.

Scripts are scenario affinities derived from InsightPilot
projected margin and total (with NFL-typical residual variance).
They are not mutually exclusive — a game can be both a shootout
and a favorite-controlled win — so probabilities are independent
scenario chances, not a partition that sums to 100%.
"""

from __future__ import annotations

import math
from typing import Any

from app.analysis.insights.betting.pricing import num


# Residual SDs approximate historical NFL score noise around
# pregame projections (points).
_MARGIN_SD = 13.5
_TOTAL_SD = 13.0

_SCRIPT_DEFS: list[dict[str, str]] = [
    {
        "script_id": "favorite_controls",
        "label": "Favorite controls game",
        "summary": "Favorite wins comfortably and dictates pace.",
    },
    {
        "script_id": "shootout",
        "label": "Shootout",
        "summary": "Both sides score freely in a high-total game.",
    },
    {
        "script_id": "underdog_comeback",
        "label": "Underdog comeback",
        "summary": "Underdog wins a close game (comeback-style finish).",
    },
    {
        "script_id": "low_scoring",
        "label": "Low scoring game",
        "summary": "Defensive / field-position game stays under the market.",
    },
    {
        "script_id": "favorite_passing_win",
        "label": "Favorite wins through passing",
        "summary": "Favorite wins in a higher-scoring, pass-friendly script.",
    },
    {
        "script_id": "contrarian_upset",
        "label": "Contrarian upset",
        "summary": "Clear underdog wins outright against the market favorite.",
    },
]


def project_game_scripts(
    *,
    projected_home: float | None,
    projected_away: float | None,
    projected_total: float | None = None,
    market_total: float | None = None,
    market_spread: float | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> list[dict[str, Any]]:
    """
    Build independent script probabilities for one event.

    Margin convention inside this module: favorite − underdog
    (positive means favorite is ahead).
    """

    home = num(projected_home)
    away = num(projected_away)
    if home is None or away is None:
        return []

    total = num(projected_total)
    if total is None:
        total = float(home) + float(away)

    home_name = (home_team or "Home").upper()
    away_name = (away_team or "Away").upper()

    # Prefer market spread to name the favorite when available;
    # otherwise use projected score edge.
    if market_spread is not None:
        # Home-team spread: negative ⇒ home favored.
        home_is_favorite = float(market_spread) <= 0
    else:
        home_is_favorite = float(home) >= float(away)

    if home_is_favorite:
        favorite = home_name
        underdog = away_name
        fav_score = float(home)
        dog_score = float(away)
    else:
        favorite = away_name
        underdog = home_name
        fav_score = float(away)
        dog_score = float(home)

    expected_margin = fav_score - dog_score  # favorite perspective
    market_ou = num(market_total)

    scripts: list[dict[str, Any]] = []
    for definition in _SCRIPT_DEFS:
        script_id = definition["script_id"]
        probability, explanation, drivers = _probability_for_script(
            script_id=script_id,
            expected_margin=expected_margin,
            expected_total=float(total),
            market_total=market_ou,
            favorite=favorite,
            underdog=underdog,
        )
        scripts.append(
            {
                "script_id": script_id,
                "label": definition["label"],
                "summary": definition["summary"],
                "probability": probability,
                "explanation": explanation,
                "drivers": drivers,
                "favorite": favorite,
                "underdog": underdog,
            }
        )

    scripts.sort(
        key=lambda row: (
            -(float(row.get("probability") or 0.0)),
            str(row.get("label") or ""),
        )
    )
    return scripts


def _probability_for_script(
    *,
    script_id: str,
    expected_margin: float,
    expected_total: float,
    market_total: float | None,
    favorite: str,
    underdog: str,
) -> tuple[float, str, list[str]]:
    if script_id == "favorite_controls":
        # Favorite wins by 10+ points.
        p = _norm_sf(10.0, expected_margin, _MARGIN_SD)
        explanation = (
            f"{favorite} is projected ahead by {expected_margin:+.1f}; "
            f"about {p * 100:.0f}% chance they win by 10+ and control the game."
        )
        drivers = [
            f"Projected margin {expected_margin:+.1f} ({favorite})",
            "Control threshold: favorite wins by ≥10",
        ]
        return _round_p(p), explanation, drivers

    if script_id == "shootout":
        threshold = 50.0
        p = _norm_sf(threshold, expected_total, _TOTAL_SD)
        explanation = (
            f"Projected total {expected_total:.1f}; about {p * 100:.0f}% "
            f"chance the game clears {threshold:g} combined points."
        )
        drivers = [
            f"Projected total {expected_total:.1f}",
            f"Shootout threshold: total ≥ {threshold:g}",
        ]
        if market_total is not None:
            drivers.append(f"Market total {market_total:g}")
        return _round_p(p), explanation, drivers

    if script_id == "underdog_comeback":
        # Underdog wins, but only by 1–7 (tight finish / comeback proxy).
        # dog_margin = -favorite_margin; P(0 < dog_margin <= 7)
        # = P(-7 <= fav_margin < 0)
        p = max(
            0.0,
            _norm_cdf(0.0, expected_margin, _MARGIN_SD)
            - _norm_cdf(-7.0, expected_margin, _MARGIN_SD),
        )
        explanation = (
            f"About {p * 100:.0f}% chance {underdog} wins a close game "
            f"(by 7 or fewer) — the underdog-comeback style finish."
        )
        drivers = [
            f"Projected margin {expected_margin:+.1f} ({favorite})",
            f"Comeback window: {underdog} wins by 1–7",
        ]
        return _round_p(p), explanation, drivers

    if script_id == "low_scoring":
        threshold = 38.0
        # Soften threshold toward market when market is already low.
        if market_total is not None:
            threshold = min(threshold, float(market_total) - 3.0)
            threshold = max(32.0, threshold)
        p = _norm_cdf(threshold, expected_total, _TOTAL_SD)
        explanation = (
            f"Projected total {expected_total:.1f}; about {p * 100:.0f}% "
            f"chance scoring stays at or below {threshold:g}."
        )
        drivers = [
            f"Projected total {expected_total:.1f}",
            f"Low-scoring threshold: total ≤ {threshold:g}",
        ]
        return _round_p(p), explanation, drivers

    if script_id == "favorite_passing_win":
        # Proxy: favorite wins and game still has pass-friendly scoring.
        p_fav_wins = _norm_sf(0.0, expected_margin, _MARGIN_SD)
        p_high = _norm_sf(48.0, expected_total, _TOTAL_SD)
        # Independence assumption for Phase 1.
        p = p_fav_wins * p_high
        explanation = (
            f"About {p * 100:.0f}% chance {favorite} wins in a "
            f"higher-scoring environment (pass-friendly favorite script)."
        )
        drivers = [
            f"P({favorite} wins) ≈ {p_fav_wins * 100:.0f}%",
            f"P(total ≥ 48) ≈ {p_high * 100:.0f}%",
            "Passing-win script uses scoring environment as a proxy",
        ]
        return _round_p(p), explanation, drivers

    if script_id == "contrarian_upset":
        # Underdog wins by 8+ (decisive upset vs market favorite).
        # P(dog_margin >= 8) = P(fav_margin <= -8)
        p = _norm_cdf(-8.0, expected_margin, _MARGIN_SD)
        explanation = (
            f"About {p * 100:.0f}% chance {underdog} wins outright by 8+ "
            f"— a contrarian upset versus {favorite}."
        )
        drivers = [
            f"Projected margin {expected_margin:+.1f} ({favorite})",
            f"Upset threshold: {underdog} wins by ≥8",
        ]
        return _round_p(p), explanation, drivers

    return 0.0, "Script not recognized.", []


def normalize_script_weights(
    scripts: list[dict[str, Any]],
    *,
    lineup_count: int,
) -> list[dict[str, Any]]:
    """
    Convert independent script probabilities into portfolio weights
    that sum to 1.0 and allocate ``lineup_count`` seats.

    Sports Betting keeps raw independent probabilities; DFS Showdown
    portfolios use this normalized allocation so lineup mix matches
    relative script likelihood.
    """

    count = max(0, int(lineup_count or 0))
    if not scripts or count <= 0:
        return []

    cleaned: list[dict[str, Any]] = []
    for row in scripts:
        script_id = str(row.get("script_id") or "").strip()
        if not script_id:
            continue
        raw = num(row.get("probability"))
        if raw is None or raw < 0:
            raw = 0.0
        cleaned.append(
            {
                "script_id": script_id,
                "label": row.get("label") or script_id,
                "summary": row.get("summary"),
                "raw_probability": float(raw),
                "favorite": row.get("favorite"),
                "underdog": row.get("underdog"),
                "explanation": row.get("explanation"),
            }
        )
    if not cleaned:
        return []

    total_raw = sum(item["raw_probability"] for item in cleaned)
    if total_raw <= 0:
        equal = 1.0 / len(cleaned)
        for item in cleaned:
            item["weight"] = equal
    else:
        for item in cleaned:
            item["weight"] = item["raw_probability"] / total_raw

    # Largest-remainder method so allocations sum exactly to count.
    exact = [item["weight"] * count for item in cleaned]
    floors = [int(value) for value in exact]
    assigned = sum(floors)
    remainders = sorted(
        (
            (exact[index] - floors[index], index)
            for index in range(len(cleaned))
        ),
        key=lambda pair: (-pair[0], pair[1]),
    )
    leftover = count - assigned
    for _, index in remainders:
        if leftover <= 0:
            break
        floors[index] += 1
        leftover -= 1

    # Ensure every script with meaningful weight gets at least one
    # lineup when the portfolio is large enough.
    meaningful = [
        index
        for index, item in enumerate(cleaned)
        if item["weight"] >= 0.08 and floors[index] == 0
    ]
    if meaningful and count >= len(cleaned):
        # Steal from the largest floor bucket.
        for index in meaningful:
            donor = max(
                range(len(floors)),
                key=lambda i: (floors[i], cleaned[i]["weight"]),
            )
            if floors[donor] <= 1:
                continue
            floors[donor] -= 1
            floors[index] += 1

    out: list[dict[str, Any]] = []
    for item, seats in zip(cleaned, floors):
        out.append(
            {
                **item,
                "weight": round(float(item["weight"]), 4),
                "lineup_count": int(seats),
            }
        )
    out.sort(key=lambda row: (-row["weight"], row["script_id"]))
    return out


def _norm_cdf(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def _norm_sf(x: float, mu: float, sigma: float) -> float:
    return 1.0 - _norm_cdf(x, mu, sigma)


def _round_p(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)
