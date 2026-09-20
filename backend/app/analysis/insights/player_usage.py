"""
Usage & Trends tab — role, opportunity, and change detection.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.analysis.insights.player_performance import (
    _game_opportunity,
    _game_production,
    _opponent_lookup_for_games,
    _position_group,
    opportunity_fields_for_position,
)
from app.analysis.insights.player_snapshot import (
    _num,
    build_team_defense_tab_payload,
)
from app.analysis.primitives.change import percent_change
from app.analysis.primitives.trends import (
    classify_trend_direction,
)
from app.canonical.analytics.common import normalize_float


PERIOD_OPTIONS: dict[str, int | None] = {
    "full_season": None,
    "last_8": 8,
    "last_6": 6,
    "last_4": 4,
    "last_3": 3,
}

# Primary opportunity metric used for charts / consistency.
PRIMARY_OPPORTUNITY_BY_POSITION: dict[str, str] = {
    "RB": "touches",
    "FB": "touches",
    "HB": "touches",
    "WR": "target_share",
    "TE": "target_share",
    "QB": "dropbacks",
    "K": "snap_pct",
}

ROLE_CARD_KEYS_BY_POSITION: dict[str, tuple[str, ...]] = {
    "RB": (
        "touches",
        "snap_pct",
        "targets",
        "red_zone_opportunities",
    ),
    "FB": (
        "touches",
        "snap_pct",
        "targets",
        "red_zone_opportunities",
    ),
    "HB": (
        "touches",
        "snap_pct",
        "targets",
        "red_zone_opportunities",
    ),
    "WR": (
        "snap_pct",
        "route_participation",
        "targets",
        "target_share",
    ),
    "TE": (
        "snap_pct",
        "route_participation",
        "targets",
        "target_share",
    ),
    "QB": (
        "dropbacks",
        "pass_attempts",
        "rush_attempts",
        "red_zone_opportunities",
    ),
    "K": ("snap_pct",),
}

ROLE_CARD_LABELS: dict[str, str] = {
    "touches": "Touches / Game",
    "snap_pct": "Snap Share",
    "targets": "Targets / Game",
    "target_share": "Target Share",
    "route_participation": "Route Participation",
    "red_zone_opportunities": "Red Zone / Game",
    "dropbacks": "Dropbacks / Game",
    "pass_attempts": "Pass Attempts / Game",
    "rush_attempts": "Rush Attempts / Game",
    "rush_share": "Rush Share",
    "qb_rush_share": "Rush Share",
    "goal_line_opportunities": "Goal-Line / Game",
    "air_yards": "Air Yards / Game",
    "designed_rush_attempts": "Designed Rushes / Game",
}

PERCENT_KEYS = frozenset(
    {
        "snap_pct",
        "target_share",
        "rush_share",
        "qb_rush_share",
        "route_participation",
    }
)


def _normalize_scoring(scoring: str | None) -> str:
    value = str(scoring or "ppr").strip().lower()
    if value in {"half", "half_ppr", "half-ppr"}:
        return "half_ppr"
    if value in {"std", "standard", "non_ppr"}:
        return "standard"
    return "ppr"


def _normalize_period(period: str | None) -> str:
    value = str(period or "last_8").strip().lower()
    if value in PERIOD_OPTIONS:
        return value
    if value in {"season", "full", "all"}:
        return "full_season"
    return "last_8"


def _reception_points(scoring: str) -> float:
    if scoring == "half_ppr":
        return 0.5
    if scoring == "standard":
        return 0.0
    return 1.0


def _fantasy_points(
    row: dict[str, Any],
    *,
    scoring: str,
) -> float | None:
    from app.analysis.insights.fantasy_scoring import (
        fantasy_points_from_row,
    )

    return fantasy_points_from_row(row, scoring=scoring)


def _mean(values: list[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return None
    return round(sum(cleaned) / len(cleaned), 1)


def _stdev(values: list[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    if len(cleaned) < 2:
        return None
    mean = sum(cleaned) / len(cleaned)
    variance = sum((value - mean) ** 2 for value in cleaned) / (
        len(cleaned) - 1
    )
    return round(variance ** 0.5, 1)


def _median(values: list[float | None]) -> float | None:
    cleaned = sorted(
        float(value) for value in values if value is not None
    )
    if not cleaned:
        return None
    mid = len(cleaned) // 2
    if len(cleaned) % 2:
        return round(cleaned[mid], 1)
    return round((cleaned[mid - 1] + cleaned[mid]) / 2.0, 1)


def _direction_from_change(
    change: float | None,
    *,
    sufficient: bool,
    volatility: float | None = None,
    up: float = 0.08,
    down: float = -0.08,
) -> str:
    if not sufficient or change is None:
        return "insufficient"
    if (
        volatility is not None
        and volatility >= 0.45
        and abs(float(change)) < 0.2
    ):
        return "volatile"
    mapped = classify_trend_direction(
        float(change),
        up=up,
        down=down,
    )
    if mapped == "growing":
        return "increasing"
    if mapped == "declining":
        return "decreasing"
    return "stable"


def _change_label(
    *,
    direction: str,
    change_pct: float | None,
    change_pts: float | None,
    format: str,
    comparison_games: int,
) -> str:
    if direction == "insufficient":
        return "— Limited sample"
    if direction == "volatile":
        return "↕ Volatile"
    if format == "percent" and change_pts is not None:
        sign = "+" if change_pts > 0 else ""
        arrow = "↑" if change_pts > 0 else "↓" if change_pts < 0 else "→"
        if abs(change_pts) < 0.5:
            return f"→ Stable vs previous {comparison_games} games"
        return (
            f"{arrow} {sign}{change_pts:.1f} pts "
            f"vs previous {comparison_games} games"
        )
    if change_pct is None:
        return "→ Stable"
    arrow = (
        "↑"
        if change_pct > 0
        else "↓"
        if change_pct < 0
        else "→"
    )
    if abs(change_pct) < 5:
        return f"→ Stable vs previous {comparison_games} games"
    return (
        f"{arrow} {abs(change_pct):.0f}% "
        f"vs previous {comparison_games} games"
    )


def _metric_series(
    weeks: list[dict[str, Any]],
    key: str,
) -> list[float | None]:
    values: list[float | None] = []
    for week in weeks:
        opportunity = week.get("opportunity") or {}
        production = week.get("production") or {}
        if key in opportunity:
            values.append(_num(opportunity.get(key)))
        elif key in production:
            values.append(_num(production.get(key)))
        else:
            values.append(None)
    return values


def _window_compare(
    values: list[float | None],
    *,
    window: int,
) -> dict[str, Any]:
    cleaned_indexes = [
        index
        for index, value in enumerate(values)
        if value is not None
    ]
    if len(cleaned_indexes) < max(3, window):
        recent = _mean(values[-window:] if values else [])
        return {
            "recent": recent,
            "previous": None,
            "change_pct": None,
            "change_pts": None,
            "direction": "insufficient",
            "sufficient": False,
            "comparison_games": 0,
        }

    recent_vals = values[-window:]
    previous_vals = values[-2 * window : -window]
    recent = _mean(recent_vals)
    previous = _mean(previous_vals)
    if recent is None or previous is None:
        return {
            "recent": recent,
            "previous": previous,
            "change_pct": None,
            "change_pts": None,
            "direction": "insufficient",
            "sufficient": False,
            "comparison_games": len(
                [value for value in previous_vals if value is not None]
            ),
        }

    change_pct = percent_change(recent, previous, fill=0.0)
    change_pts = round(float(recent) - float(previous), 1)
    volatility = None
    stdev = _stdev(recent_vals)
    if stdev is not None and abs(float(recent)) > 1e-6:
        volatility = abs(float(stdev) / float(recent))
    sufficient = len(
        [value for value in previous_vals if value is not None]
    ) >= max(2, window // 2)
    direction = _direction_from_change(
        float(change_pct) if change_pct is not None else None,
        sufficient=sufficient,
        volatility=volatility,
    )
    return {
        "recent": recent,
        "previous": previous,
        "change_pct": (
            round(float(change_pct) * 100.0, 1)
            if change_pct is not None
            else None
        ),
        "change_pts": change_pts,
        "direction": direction,
        "sufficient": sufficient,
        "comparison_games": len(
            [value for value in previous_vals if value is not None]
        ),
    }


def _build_weekly_rows(
    *,
    player_id: str,
    season: int,
    scoring: str,
) -> list[dict[str, Any]]:
    try:
        from app.canonical.analytics.persist import load_rows
        from app.canonical.fact_player_game import (
            FACT_PLAYER_GAME_COLUMNS,
        )
        from app.canonical.fact_player_usage import (
            FACT_PLAYER_USAGE_COLUMNS,
        )
    except Exception:
        return []

    try:
        games = load_rows(
            "fact_player_game",
            FACT_PLAYER_GAME_COLUMNS,
            seasons=[int(season)],
            player_id=player_id,
            order_by="season, week, game_id",
        )
        usage = load_rows(
            "fact_player_usage",
            FACT_PLAYER_USAGE_COLUMNS,
            seasons=[int(season)],
            player_id=player_id,
            order_by="season, week, game_id",
        )
    except Exception:
        return []

    player_games = (
        games.to_dict(orient="records")
        if games is not None and not games.empty
        else []
    )
    if not player_games:
        return []

    usage_lookup: dict[tuple[int, int], dict[str, Any]] = {}
    if usage is not None and not usage.empty:
        for row in usage.to_dict(orient="records"):
            try:
                key = (int(row.get("season")), int(row.get("week")))
            except (TypeError, ValueError):
                continue
            usage_lookup[key] = row

    def sort_key(row: dict[str, Any]) -> tuple[int, int]:
        try:
            return (int(row.get("season") or 0), int(row.get("week") or 0))
        except (TypeError, ValueError):
            return (0, 0)

    player_games.sort(key=sort_key)
    opponent_lookup = _opponent_lookup_for_games(player_games)

    weeks: list[dict[str, Any]] = []
    for row in player_games:
        try:
            s = int(row.get("season"))
            w = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        usage_row = usage_lookup.get((s, w), {})
        production = _game_production(row)
        production["fantasy_points"] = _fantasy_points(
            row,
            scoring=scoring,
        )
        production["targets"] = production.get("targets")
        production["pass_attempts"] = production.get("pass_attempts")
        production["rush_attempts"] = production.get("rush_attempts")
        opportunity = _game_opportunity(usage_row)
        if opportunity.get("air_yards") is None:
            opportunity["air_yards"] = production.get("air_yards")
        # Expose common production rates on opportunity for cards.
        if opportunity.get("targets") is None:
            opportunity["targets"] = production.get("targets")
        if opportunity.get("pass_attempts") is None:
            opportunity["pass_attempts"] = production.get(
                "pass_attempts"
            )
        if opportunity.get("rush_attempts") is None:
            opportunity["rush_attempts"] = production.get(
                "rush_attempts"
            )

        game_id = str(row.get("game_id") or "").strip()
        team_id = str(row.get("team_id") or "").strip()
        opponent_info = opponent_lookup.get((game_id, team_id), {})
        weeks.append(
            {
                "season": s,
                "week": w,
                "label": f"W{w}",
                "opponent": opponent_info.get("opponent"),
                "opponent_label": opponent_info.get("opponent_label"),
                "home_away": opponent_info.get("home_away"),
                "production": production,
                "opportunity": opportunity,
            }
        )
    return weeks


def _role_cards(
    weeks: list[dict[str, Any]],
    *,
    position_group: str,
    window: int,
) -> list[dict[str, Any]]:
    keys = ROLE_CARD_KEYS_BY_POSITION.get(
        position_group,
        ROLE_CARD_KEYS_BY_POSITION["WR"],
    )
    cards: list[dict[str, Any]] = []
    for key in keys:
        series = _metric_series(weeks, key)
        compare = _window_compare(series, window=window)
        recent = compare["recent"]
        if recent is None:
            continue
        format_name = "percent" if key in PERCENT_KEYS else "number"
        direction = compare["direction"]
        cards.append(
            {
                "key": key,
                "label": ROLE_CARD_LABELS.get(key, key),
                "value": recent,
                "previous_value": compare["previous"],
                "format": format_name,
                "direction": direction,
                "change_pct": compare["change_pct"],
                "change_pts": compare["change_pts"],
                "change_label": _change_label(
                    direction=direction,
                    change_pct=compare["change_pct"],
                    change_pts=compare["change_pts"],
                    format=format_name,
                    comparison_games=max(
                        1,
                        int(compare["comparison_games"] or window),
                    ),
                ),
            }
        )
    return cards


def _recent_role_change(
    weeks: list[dict[str, Any]],
    *,
    position_group: str,
    window: int,
) -> dict[str, Any] | None:
    if len(weeks) < max(4, window):
        return None
    half = max(3, min(window, len(weeks) // 2))
    keys = ROLE_CARD_KEYS_BY_POSITION.get(
        position_group,
        ROLE_CARD_KEYS_BY_POSITION["WR"],
    )
    metrics: list[dict[str, Any]] = []
    up_count = 0
    down_count = 0
    for key in keys:
        series = _metric_series(weeks, key)
        current_vals = series[-half:]
        previous_vals = series[-2 * half : -half]
        current = _mean(current_vals)
        previous = _mean(previous_vals)
        if current is None or previous is None:
            continue
        format_name = "percent" if key in PERCENT_KEYS else "number"
        change_pct = percent_change(current, previous, fill=0.0)
        change_pts = round(float(current) - float(previous), 1)
        direction = _direction_from_change(
            float(change_pct) if change_pct is not None else None,
            sufficient=True,
        )
        if direction == "increasing":
            up_count += 1
        elif direction == "decreasing":
            down_count += 1
        metrics.append(
            {
                "key": key,
                "label": ROLE_CARD_LABELS.get(key, key),
                "current": current,
                "previous": previous,
                "change_pct": (
                    round(float(change_pct) * 100.0, 1)
                    if change_pct is not None
                    else None
                ),
                "change_pts": change_pts,
                "direction": direction,
                "format": format_name,
            }
        )
    if not metrics:
        return None

    if up_count >= 2 and up_count > down_count:
        interpretation = (
            "Role is expanding across multiple opportunity measures."
        )
    elif down_count >= 2 and down_count > up_count:
        interpretation = (
            "Role is contracting across multiple opportunity measures."
        )
    else:
        interpretation = (
            "Role is largely stable across the compared periods."
        )

    return {
        "current_label": f"Last {half} games",
        "previous_label": f"Previous {half} games",
        "metrics": metrics,
        "interpretation": interpretation,
    }


def _build_signals(
    cards: list[dict[str, Any]],
    *,
    weeks: list[dict[str, Any]],
    position_group: str,
    window: int,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    sample = min(window, len(weeks))

    def confidence_for(direction: str, change_pct: float | None) -> str:
        if direction == "insufficient":
            return "low"
        if sample < 4:
            return "low"
        if change_pct is not None and abs(change_pct) >= 20:
            return "high"
        if sample >= 6:
            return "high"
        return "moderate"

    # Opportunity signal from primary metric.
    primary = PRIMARY_OPPORTUNITY_BY_POSITION.get(
        position_group,
        "target_share",
    )
    primary_card = next(
        (card for card in cards if card["key"] == primary),
        cards[0] if cards else None,
    )
    if primary_card:
        direction = primary_card["direction"]
        headline = {
            "increasing": "Increasing Opportunity",
            "decreasing": "Decreasing Opportunity",
            "stable": "Stable Opportunity",
            "volatile": "Volatile Opportunity",
            "insufficient": "Limited Opportunity Sample",
        }.get(direction, "Stable Opportunity")
        signals.append(
            {
                "signal_type": f"OPPORTUNITY_{direction.upper()}",
                "category": "opportunity",
                "direction": direction,
                "headline": headline,
                "body": (
                    f"{primary_card['label']} is "
                    f"{primary_card['change_label'].lstrip('↑↓→↕— ').strip()}."
                    if primary_card.get("change_label")
                    else f"{primary_card['label']} trend evaluated."
                ),
                "confidence": confidence_for(
                    direction,
                    primary_card.get("change_pct"),
                ),
                "metric": primary_card["key"],
                "sample_size": sample,
            }
        )

    snap = next(
        (card for card in cards if card["key"] == "snap_pct"),
        None,
    )
    if snap:
        direction = snap["direction"]
        headline = {
            "increasing": "Expanding Role",
            "decreasing": "Shrinking Role",
            "stable": "Stable Role",
            "volatile": "Role Transition",
            "insufficient": "Limited Role Sample",
        }.get(direction, "Stable Role")
        signals.append(
            {
                "signal_type": f"ROLE_{direction.upper()}",
                "category": "role",
                "direction": direction,
                "headline": headline,
                "body": (
                    f"Snap share moved from "
                    f"{snap.get('previous_value') if snap.get('previous_value') is not None else '—'}% "
                    f"to {snap['value']}%."
                    if snap.get("format") == "percent"
                    else snap.get("change_label") or ""
                ),
                "confidence": confidence_for(
                    direction,
                    snap.get("change_pct"),
                ),
                "metric": "snap_pct",
                "sample_size": sample,
            }
        )

    # Efficiency: fantasy points vs primary opportunity.
    opp_series = _metric_series(weeks, primary)
    pts_series = _metric_series(weeks, "fantasy_points")
    opp_compare = _window_compare(opp_series, window=window)
    pts_compare = _window_compare(pts_series, window=window)
    if (
        opp_compare["sufficient"]
        and pts_compare["sufficient"]
        and opp_compare["change_pct"] is not None
        and pts_compare["change_pct"] is not None
    ):
        opp_change = float(opp_compare["change_pct"])
        pts_change = float(pts_compare["change_pct"])
        if pts_change - opp_change >= 10:
            direction = "increasing"
            headline = "Improving Efficiency"
            body = (
                "Fantasy production has increased faster than "
                "workload, suggesting efficiency is contributing."
            )
            classification = "exceeding"
        elif opp_change - pts_change >= 10:
            direction = "decreasing"
            headline = "Declining Efficiency"
            body = (
                "Opportunity remains stronger than recent fantasy "
                "production."
            )
            classification = "below"
        else:
            direction = "stable"
            headline = "Stable Efficiency"
            body = (
                "Production remains broadly aligned with recent "
                "opportunity."
            )
            classification = "supported"
        signals.append(
            {
                "signal_type": f"EFFICIENCY_{direction.upper()}",
                "category": "efficiency",
                "direction": direction,
                "headline": headline,
                "body": body,
                "confidence": confidence_for(direction, pts_change),
                "metric": "fantasy_points",
                "sample_size": sample,
                "classification": classification,
            }
        )

    rz = next(
        (
            card
            for card in cards
            if card["key"] == "red_zone_opportunities"
        ),
        None,
    )
    if rz and rz["direction"] in {"increasing", "decreasing"}:
        headline = (
            "Increasing Red-Zone Usage"
            if rz["direction"] == "increasing"
            else "Declining Scoring Opportunity"
        )
        signals.append(
            {
                "signal_type": "SCORING_OPPORTUNITY",
                "category": "scoring",
                "direction": rz["direction"],
                "headline": headline,
                "body": rz.get("change_label") or "",
                "confidence": confidence_for(
                    rz["direction"],
                    rz.get("change_pct"),
                ),
                "metric": "red_zone_opportunities",
                "sample_size": sample,
            }
        )

    return signals[:5]


def _opportunity_vs_production(
    weeks: list[dict[str, Any]],
    *,
    position_group: str,
    window: int,
) -> dict[str, Any] | None:
    if not weeks:
        return None
    primary = PRIMARY_OPPORTUNITY_BY_POSITION.get(
        position_group,
        "target_share",
    )
    label_lookup = {
        field["key"]: field["label"]
        for field in opportunity_fields_for_position(position_group)
    }
    label_lookup.update(ROLE_CARD_LABELS)
    selected = weeks[-window:]
    points = []
    for week in selected:
        opp = _num((week.get("opportunity") or {}).get(primary))
        pts = _num((week.get("production") or {}).get("fantasy_points"))
        if opp is None or pts is None:
            continue
        points.append(
            {
                "week": week.get("week"),
                "label": week.get("label"),
                "opportunity": opp,
                "production": pts,
            }
        )
    if len(points) < 3:
        return {
            "points": points,
            "opportunity_metric": {
                "key": primary,
                "label": label_lookup.get(primary, primary),
            },
            "production_metric": {
                "key": "fantasy_points",
                "label": "Fantasy points",
            },
            "classification": "insufficient",
            "interpretation": (
                "Not enough paired opportunity and production "
                "games yet."
            ),
        }

    opp_compare = _window_compare(
        _metric_series(weeks, primary),
        window=window,
    )
    pts_compare = _window_compare(
        _metric_series(weeks, "fantasy_points"),
        window=window,
    )
    classification = "supported"
    interpretation = (
        "Workload and fantasy production are moving together."
    )
    if (
        opp_compare["change_pct"] is not None
        and pts_compare["change_pct"] is not None
    ):
        opp_change = float(opp_compare["change_pct"])
        pts_change = float(pts_compare["change_pct"])
        if pts_change - opp_change >= 10:
            classification = "exceeding"
            interpretation = (
                "Fantasy output has increased faster than workload, "
                "suggesting efficiency is contributing significantly."
            )
        elif opp_change - pts_change >= 10:
            classification = "below"
            interpretation = (
                "Opportunity remains strong, but fantasy production "
                "has not fully followed."
            )
        elif opp_change >= 8 and pts_change >= 8:
            classification = "supported"
            interpretation = (
                "Increased workload is translating into increased "
                "fantasy production."
            )

    return {
        "points": points,
        "opportunity_metric": {
            "key": primary,
            "label": label_lookup.get(primary, primary),
        },
        "production_metric": {
            "key": "fantasy_points",
            "label": "Fantasy points",
        },
        "classification": classification,
        "interpretation": interpretation,
    }


def _consistency_card(
    weeks: list[dict[str, Any]],
    *,
    position_group: str,
    window: int,
) -> dict[str, Any] | None:
    primary = PRIMARY_OPPORTUNITY_BY_POSITION.get(
        position_group,
        "target_share",
    )
    selected = weeks[-window:]
    values = _metric_series(selected, primary)
    cleaned = [float(value) for value in values if value is not None]
    if len(cleaned) < 3:
        return None
    average = _mean(values)
    median = _median(values)
    low = round(min(cleaned), 1)
    high = round(max(cleaned), 1)
    thresholds: list[dict[str, Any]] = []
    if primary == "touches":
        for threshold in (20, 15):
            thresholds.append(
                {
                    "label": f"Games {threshold}+ touches",
                    "count": sum(
                        1 for value in cleaned if value >= threshold
                    ),
                    "total": len(cleaned),
                }
            )
    elif primary == "target_share":
        # Use targets series for floor thresholds when available.
        target_values = [
            float(value)
            for value in _metric_series(selected, "targets")
            if value is not None
        ]
        if target_values:
            for threshold in (7, 5):
                thresholds.append(
                    {
                        "label": f"Games {threshold}+ targets",
                        "count": sum(
                            1
                            for value in target_values
                            if value >= threshold
                        ),
                        "total": len(target_values),
                    }
                )
    elif primary == "dropbacks":
        for threshold in (35, 30):
            thresholds.append(
                {
                    "label": f"Games {threshold}+ dropbacks",
                    "count": sum(
                        1 for value in cleaned if value >= threshold
                    ),
                    "total": len(cleaned),
                }
            )

    return {
        "metric_key": primary,
        "metric_label": ROLE_CARD_LABELS.get(primary, primary),
        "format": "percent" if primary in PERCENT_KEYS else "number",
        "median": median,
        "average": average,
        "low": low,
        "high": high,
        "threshold_counts": thresholds,
    }


def _position_context(
    *,
    player_id: str,
    position: str | None,
    season: int,
    weeks: list[dict[str, Any]],
    window: int,
) -> dict[str, Any] | None:
    group = _position_group(position)
    if group not in {"QB", "RB", "WR", "TE"}:
        return None
    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    keys = ROLE_CARD_KEYS_BY_POSITION.get(group, ())[:4]
    if not keys:
        return None

    # Season-level positional averages from usage + box score.
    sql = f"""
        SELECT
          AVG(u.offensive_snap_share) AS snap_pct,
          AVG(u.target_share) AS target_share,
          AVG(u.route_participation_rate) AS route_participation,
          AVG(u.touches) AS touches,
          AVG(u.dropbacks) AS dropbacks,
          AVG(
            COALESCE(u.red_zone_touches, 0)
            + COALESCE(u.red_zone_targets, 0)
          ) AS red_zone_opportunities,
          AVG(g.targets) AS targets,
          AVG(g.pass_attempts) AS pass_attempts,
          AVG(g.rush_attempts) AS rush_attempts
        FROM {FANTASY_SCHEMA}.fact_player_usage u
        INNER JOIN {FANTASY_SCHEMA}.dim_player p
          ON p.player_id = u.player_id
        LEFT JOIN {FANTASY_SCHEMA}.fact_player_game g
          ON g.player_id = u.player_id
         AND g.season = u.season
         AND g.week = u.week
        WHERE u.season = :season
          AND UPPER(COALESCE(p.position, '')) = :position
    """
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(sql),
                connection,
                params={
                    "season": int(season),
                    "position": group,
                },
            )
    except Exception:
        return None
    if frame.empty:
        return None
    averages = frame.to_dict(orient="records")[0]
    metrics: list[dict[str, Any]] = []
    selected = weeks[-window:]
    for key in keys:
        player_value = _mean(_metric_series(selected, key))
        raw_avg = averages.get(key)
        position_avg = _num(raw_avg)
        if key in PERCENT_KEYS and position_avg is not None:
            if 0 <= position_avg <= 1.5:
                position_avg = round(position_avg * 100.0, 1)
        if player_value is None or position_avg is None:
            continue
        metrics.append(
            {
                "key": key,
                "label": ROLE_CARD_LABELS.get(key, key),
                "player": player_value,
                "position_avg": round(float(position_avg), 1),
                "format": (
                    "percent" if key in PERCENT_KEYS else "number"
                ),
            }
        )
    if not metrics:
        return None
    return {
        "position_group": group,
        "metrics": metrics,
    }


def _chart_metrics(position_group: str) -> list[dict[str, str]]:
    keys = ROLE_CARD_KEYS_BY_POSITION.get(
        position_group,
        ROLE_CARD_KEYS_BY_POSITION["WR"],
    )
    return [
        {
            "key": key,
            "label": ROLE_CARD_LABELS.get(key, key)
            .replace(" / Game", "")
            .replace(" Share", " %"),
        }
        for key in keys
    ]


def build_player_usage(
    player_id: str,
    *,
    season: int | None = None,
    period: str | None = "last_8",
    scoring: str | None = "ppr",
) -> dict[str, Any] | None:
    """
    Usage & Trends MVP payload for one player.
    """

    pid = str(player_id or "").strip()
    if not pid:
        return None

    defense_payload = build_team_defense_tab_payload(
        pid,
        season=season,
        tab="usage",
    )
    if defense_payload is not None:
        return defense_payload

    scoring_key = _normalize_scoring(scoring)
    period_key = _normalize_period(period)

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
        import nflreadpy as nfl
    except Exception:
        return None

    identity: dict[str, Any] = {}
    available_seasons: list[int] = []
    try:
        with engine.connect() as connection:
            identity_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      p.player_id,
                      p.name,
                      p.position,
                      t.team_abbreviation AS team
                    FROM {FANTASY_SCHEMA}.dim_player p
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team t
                      ON t.team_id = p.current_team_id
                    WHERE p.player_id = :player_id
                    LIMIT 1
                    """
                ),
                connection,
                params={"player_id": pid},
            )
            if identity_frame.empty:
                return None
            identity = identity_frame.to_dict(orient="records")[0]
            seasons_frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT DISTINCT season
                    FROM {FANTASY_SCHEMA}.fact_player_game
                    WHERE player_id = :player_id
                      AND season IS NOT NULL
                    ORDER BY season DESC
                    """
                ),
                connection,
                params={"player_id": pid},
            )
            available_seasons = [
                int(value)
                for value in seasons_frame["season"].tolist()
                if value is not None
            ]
    except Exception:
        return None

    if season is None:
        try:
            season = int(nfl.get_current_season())
        except Exception:
            season = (
                available_seasons[0] if available_seasons else None
            )
    if season is None:
        return None
    if available_seasons and int(season) not in available_seasons:
        season = available_seasons[0]

    position = identity.get("position")
    position_group = _position_group(position)
    weeks = _build_weekly_rows(
        player_id=pid,
        season=int(season),
        scoring=scoring_key,
    )
    if not weeks:
        return {
            "player_id": pid,
            "name": identity.get("name"),
            "position": position,
            "position_group": position_group,
            "team": identity.get("team"),
            "season": int(season),
            "period": period_key,
            "period_games": 0,
            "scoring": scoring_key,
            "available_seasons": available_seasons,
            "data_through_week": None,
            "sample_size": 0,
            "role_opportunity": [],
            "chart_metrics": _chart_metrics(position_group),
            "weekly_usage": [],
            "signals": [],
            "recent_role_change": None,
            "opportunity_vs_production": None,
            "consistency": None,
            "position_context": None,
            "empty_message": (
                "Not enough recent data. InsightPilot needs "
                "additional games to identify a reliable usage trend."
            ),
            "data_note": None,
        }

    configured = PERIOD_OPTIONS.get(period_key)
    window = (
        len(weeks)
        if configured is None
        else min(int(configured), len(weeks))
    )
    window = max(1, window)
    selected_weeks = weeks[-window:]

    cards = _role_cards(
        weeks,
        position_group=position_group,
        window=window,
    )
    signals = _build_signals(
        cards,
        weeks=weeks,
        position_group=position_group,
        window=window,
    )
    role_change = _recent_role_change(
        weeks,
        position_group=position_group,
        window=window,
    )
    opp_vs_prod = _opportunity_vs_production(
        weeks,
        position_group=position_group,
        window=window,
    )
    consistency = _consistency_card(
        weeks,
        position_group=position_group,
        window=window,
    )
    context = _position_context(
        player_id=pid,
        position=position,
        season=int(season),
        weeks=weeks,
        window=window,
    )

    data_through = selected_weeks[-1].get("week")
    period_label = (
        "full season"
        if period_key == "full_season"
        else f"last {window} games"
    )

    return {
        "player_id": pid,
        "name": identity.get("name"),
        "position": position,
        "position_group": position_group,
        "team": identity.get("team"),
        "season": int(season),
        "period": period_key,
        "period_games": window,
        "scoring": scoring_key,
        "available_seasons": available_seasons,
        "data_through_week": data_through,
        "sample_size": len(selected_weeks),
        "role_opportunity": cards,
        "chart_metrics": _chart_metrics(position_group),
        "weekly_usage": selected_weeks,
        "signals": signals,
        "recent_role_change": role_change,
        "opportunity_vs_production": opp_vs_prod,
        "consistency": consistency,
        "position_context": context,
        "empty_message": None,
        "data_note": (
            f"Calculated by InsightPilot · {period_label}"
            + (
                f" through week {data_through}"
                if data_through is not None
                else ""
            )
        ),
    }
