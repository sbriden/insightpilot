"""
Sports Betting model results — auto-settlement and calibration.

When dim_game receives final scores, InsightPilot freezes the latest
pregame projection snapshot, settles every published market against
the actual outcome, and folds residual error into future projections.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.analysis.insights.betting.clv import (
    attach_clv_fields,
    build_clv_diagnostics,
    event_spread_as_selection_line,
    selection_side,
)
from app.analysis.insights.betting.edge_confidence import (
    build_edge_confidence_diagnostics,
)
from app.analysis.insights.betting.market_performance import (
    build_market_performance,
    merge_edge_confidence_with_markets,
)
from app.analysis.insights.betting.pricing import num


def is_game_final(event: dict[str, Any]) -> bool:
    status = str(event.get("status") or "").strip().lower()
    if status in {"final", "complete", "completed", "closed"}:
        return True
    # Do not treat score presence alone as final while the game is
    # still scheduled — placeholder 0–0 rows would freeze projections.
    if status in {
        "scheduled",
        "preview",
        "pregame",
        "upcoming",
        "postponed",
        "bye",
    }:
        return False
    home = num(event.get("home_score"))
    away = num(event.get("away_score"))
    return home is not None and away is not None


def build_projection_snapshot(event: dict[str, Any]) -> dict[str, Any]:
    """Capture the latest model/market view for a game."""

    return {
        "game_id": str(event.get("event_id") or ""),
        "season": event.get("season"),
        "week": event.get("week"),
        "home_team": event.get("home_team"),
        "away_team": event.get("away_team"),
        "projected_home_score": num(event.get("projected_home_score")),
        "projected_away_score": num(event.get("projected_away_score")),
        "projected_total": num(event.get("projected_total")),
        "model_spread": num(event.get("model_spread")),
        "market_spread": num(event.get("market_spread")),
        "market_total": num(event.get("market_total")),
        "market_home_score": num(event.get("market_home_score")),
        "market_away_score": num(event.get("market_away_score")),
        "residual_home": num(event.get("residual_home")),
        "residual_away": num(event.get("residual_away")),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "frozen": False,
    }


def settle_event_markets(
    event: dict[str, Any],
    markets: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Settle every market for a completed game using final scores and
    the frozen (or latest) projection snapshot.

    Also records bet_line vs closing_line for CLV diagnostics.
    """

    if not is_game_final(event):
        return []

    home_score = int(float(event["home_score"]))
    away_score = int(float(event["away_score"]))
    snap = snapshot or build_projection_snapshot(event)
    actual_total = home_score + away_score
    # Same convention as slate model_spread: away − home.
    actual_spread = float(away_score - home_score)

    model_total = num(snap.get("projected_total"))
    model_spread = num(snap.get("model_spread"))
    model_home = num(snap.get("projected_home_score"))
    model_away = num(snap.get("projected_away_score"))

    # Closing market lines = last known event lines at settlement.
    closing_market_spread = num(
        event.get("current_spread")
        if event.get("current_spread") is not None
        else event.get("market_spread")
    )
    closing_market_total = num(
        event.get("current_total")
        if event.get("current_total") is not None
        else event.get("market_total")
    )
    # Bet-time lines prefer the frozen snapshot market.
    bet_market_spread = num(
        snap.get("market_spread")
        if snap.get("market_spread") is not None
        else event.get("opening_spread", event.get("market_spread"))
    )
    bet_market_total = num(
        snap.get("market_total")
        if snap.get("market_total") is not None
        else event.get("opening_total", event.get("market_total"))
    )

    settled: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for market in markets:
        row = _settle_one_market(
            market,
            home_score=home_score,
            away_score=away_score,
            actual_total=actual_total,
            actual_spread=actual_spread,
            bet_market_spread=bet_market_spread,
            closing_market_spread=closing_market_spread,
            bet_market_total=bet_market_total,
            closing_market_total=closing_market_total,
            closing_home_moneyline=num(
                event.get("current_moneyline")
            ),
            bet_home_moneyline=num(event.get("opening_moneyline")),
        )
        if row is None:
            continue
        row.update(
            {
                "season": event.get("season"),
                "week": event.get("week"),
                "event_id": event.get("event_id"),
                "event_label": event.get("label") or market.get("event_label"),
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "home_score": home_score,
                "away_score": away_score,
                "actual_total": actual_total,
                "actual_spread": actual_spread,
                "model_home_score": model_home,
                "model_away_score": model_away,
                "model_total": model_total,
                "model_spread": model_spread,
                "market_spread": num(snap.get("market_spread")),
                "market_total": num(snap.get("market_total")),
                "total_error": (
                    round(float(model_total) - float(actual_total), 1)
                    if model_total is not None
                    else None
                ),
                "spread_error": (
                    round(float(model_spread) - float(actual_spread), 1)
                    if model_spread is not None
                    else None
                ),
                "projection_captured_at": snap.get("captured_at"),
                "settled_at": now,
                "source": "auto_dim_game",
            }
        )
        settled.append(attach_clv_fields(row))

    return settled


def summarize_model_results(
    settled: list[dict[str, Any]],
) -> dict[str, Any]:
    """Portfolio-independent model performance summary."""

    if not settled:
        return {
            "total_markets": 0,
            "decided": 0,
            "model_correct": 0,
            "model_incorrect": 0,
            "push": 0,
            "hit_rate": None,
            "ats_win_pct": None,
            "ou_win_pct": None,
            "ml_win_pct": None,
            "average_clv": None,
            "median_clv": None,
            "beat_close_pct": None,
            "units": None,
            "roi_pct": None,
            "average_edge": None,
            "average_closing_edge": None,
            "clv": None,
            "average_total_error": None,
            "average_spread_error": None,
            "average_abs_total_error": None,
            "average_abs_spread_error": None,
            "by_market": [],
            "by_confidence": [],
            "by_edge_bucket": [],
            "by_favorite_underdog": [],
            "by_home_away": [],
            "by_week": [],
            "edge_confidence": None,
            "market_performance": None,
            "calibration": [],
            "settled_markets": [],
            "games_settled": 0,
            "performance_trend": [],
            "trend_summary": None,
            "note": (
                "Results appear automatically when final scores "
                "land in InsightPilot game data."
            ),
        }

    decided = [
        row
        for row in settled
        if row.get("result") in {"won", "lost"}
    ]
    pushes = [
        row for row in settled if row.get("result") == "push"
    ]
    correct = [row for row in decided if row.get("result") == "won"]
    total_errors = [
        float(row["total_error"])
        for row in settled
        if num(row.get("total_error")) is not None
    ]
    spread_errors = [
        float(row["spread_error"])
        for row in settled
        if num(row.get("spread_error")) is not None
    ]
    # Deduplicate game-level errors (one per event).
    game_total_errors: dict[str, float] = {}
    game_spread_errors: dict[str, float] = {}
    for row in settled:
        eid = str(row.get("event_id") or "")
        if not eid:
            continue
        if num(row.get("total_error")) is not None:
            game_total_errors[eid] = float(row["total_error"])
        if num(row.get("spread_error")) is not None:
            game_spread_errors[eid] = float(row["spread_error"])

    te = list(game_total_errors.values())
    se = list(game_spread_errors.values())
    trend = build_performance_trend(settled)
    clv = build_clv_diagnostics(settled)
    clv_summary = clv.get("summary") or {}
    market_performance = build_market_performance(settled)
    edge_payload = build_edge_confidence_diagnostics(settled)
    edge_payload["thresholds"] = merge_edge_confidence_with_markets(
        edge_payload.get("thresholds"),
        market_performance,
    )
    edge_payload["by_market"] = (
        edge_payload.get("thresholds") or {}
    ).get("by_market")
    edge_payload["market_note"] = market_performance.get("note")

    # Prefer rich market cards over the thin CLV-by-market rows.
    by_market_rows = [
        {
            "key": card.get("label") or mtype,
            "market_type": mtype,
            "bets": card.get("bets") or 0,
            "decided": card.get("decided") or 0,
            "correct": card.get("correct") or 0,
            "hit_rate": card.get("hit_rate"),
            "ats_win_pct": card.get("ats_win_pct"),
            "ou_win_pct": card.get("ou_win_pct"),
            "win_pct": card.get("win_pct"),
            "roi_pct": card.get("roi_pct"),
            "average_clv": card.get("average_clv"),
            "median_clv": card.get("median_clv"),
            "mae": card.get("mae"),
            "calibration_gap": card.get("calibration_gap"),
            "brier": card.get("brier"),
            "quality_score": card.get("quality_score"),
            "confidence_weight": card.get("confidence_weight"),
            "high_min": card.get("high_min"),
            "moderate_min": card.get("moderate_min"),
            "sample_size": card.get("sample_size"),
            "units": card.get("units"),
            "calibration": card.get("calibration"),
        }
        for mtype, card in (market_performance.get("markets") or {}).items()
    ]

    return {
        "total_markets": len(settled),
        "decided": len(decided),
        "model_correct": len(correct),
        "model_incorrect": len(decided) - len(correct),
        "push": len(pushes),
        "hit_rate": (
            round(100.0 * len(correct) / len(decided), 1)
            if decided
            else None
        ),
        "ats_win_pct": clv_summary.get("ats_win_pct"),
        "ou_win_pct": clv_summary.get("ou_win_pct"),
        "ml_win_pct": clv_summary.get("ml_win_pct"),
        "average_clv": clv_summary.get("average_clv"),
        "median_clv": clv_summary.get("median_clv"),
        "beat_close_pct": clv_summary.get("beat_close_pct"),
        "units": clv_summary.get("units"),
        "roi_pct": clv_summary.get("roi_pct"),
        "average_edge": clv_summary.get("average_edge"),
        "average_closing_edge": clv_summary.get("average_closing_edge"),
        "clv": clv_summary,
        "average_total_error": (
            round(sum(te) / len(te), 2) if te else None
        ),
        "average_spread_error": (
            round(sum(se) / len(se), 2) if se else None
        ),
        "average_abs_total_error": (
            round(sum(abs(v) for v in te) / len(te), 2) if te else None
        ),
        "average_abs_spread_error": (
            round(sum(abs(v) for v in se) / len(se), 2) if se else None
        ),
        "by_market": by_market_rows,
        "by_confidence": clv.get("by_confidence") or _breakdown(
            settled, "confidence"
        ),
        "by_edge_bucket": (
            edge_payload.get("buckets")
            or clv.get("by_edge_bucket")
            or []
        ),
        "by_favorite_underdog": clv.get("by_favorite_underdog") or [],
        "by_home_away": clv.get("by_home_away") or [],
        "by_week": clv.get("by_week") or [],
        "edge_confidence": edge_payload,
        "market_performance": market_performance,
        "calibration": _calibration(settled),
        "settled_markets": clv.get("settled_markets")
        or sorted(
            settled,
            key=lambda row: (
                str(row.get("week") or 0),
                str(row.get("event_label") or ""),
                str(row.get("market_type") or ""),
            ),
            reverse=True,
        ),
        "games_settled": len(
            {
                str(row.get("event_id") or "")
                for row in settled
                if row.get("event_id")
            }
        ),
        "performance_trend": trend,
        "trend_summary": trend_summary_from_points(trend),
        "note": (
            "Auto-settled from final scores vs frozen pregame "
            "projections. Spread, total, and moneyline are scored "
            "as separate models — CLV and market quality drive "
            "confidence allocation more than blended win rate."
        ),
    }


def build_performance_trend(
    settled: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Weekly model performance series (hit rate + projection error).

    One point per season week that has settled markets. Cumulative
    hit rate is included so the UI can show both weekly and
    season-to-date trajectory.
    """

    by_week: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in settled:
        season = row.get("season")
        week = row.get("week")
        if season is None or week is None:
            continue
        try:
            key = (int(season), int(week))
        except (TypeError, ValueError):
            continue
        by_week[key].append(row)

    if not by_week:
        return []

    points: list[dict[str, Any]] = []
    cum_correct = 0
    cum_decided = 0
    for season, week in sorted(by_week.keys()):
        rows = by_week[(season, week)]
        decided = [
            row
            for row in rows
            if row.get("result") in {"won", "lost"}
        ]
        correct = [
            row for row in decided if row.get("result") == "won"
        ]
        # Game-level errors (one per event).
        game_total: dict[str, float] = {}
        game_abs_spread: dict[str, float] = {}
        for row in rows:
            eid = str(row.get("event_id") or "")
            if not eid:
                continue
            if num(row.get("total_error")) is not None:
                game_total[eid] = float(row["total_error"])
            if num(row.get("spread_error")) is not None:
                game_abs_spread[eid] = abs(float(row["spread_error"]))

        te = list(game_total.values())
        se = list(game_abs_spread.values())
        week_correct = len(correct)
        week_decided = len(decided)
        cum_correct += week_correct
        cum_decided += week_decided
        hit = (
            round(100.0 * week_correct / week_decided, 1)
            if week_decided
            else None
        )
        cum_hit = (
            round(100.0 * cum_correct / cum_decided, 1)
            if cum_decided
            else None
        )
        prior_hit = points[-1]["hit_rate"] if points else None
        hit_delta = (
            round(float(hit) - float(prior_hit), 1)
            if hit is not None and prior_hit is not None
            else None
        )
        points.append(
            {
                "season": season,
                "week": week,
                "label": f"W{week}",
                "markets": len(rows),
                "decided": week_decided,
                "correct": week_correct,
                "hit_rate": hit,
                "cumulative_hit_rate": cum_hit,
                "hit_rate_delta": hit_delta,
                "games_settled": len(
                    {
                        str(row.get("event_id") or "")
                        for row in rows
                        if row.get("event_id")
                    }
                ),
                "average_total_error": (
                    round(sum(te) / len(te), 2) if te else None
                ),
                "average_abs_spread_error": (
                    round(sum(se) / len(se), 2) if se else None
                ),
            }
        )
    return points


def trend_summary_from_points(
    points: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not points:
        return None
    latest = points[-1]
    first = points[0]
    return {
        "weeks": len(points),
        "latest_week": latest.get("week"),
        "latest_hit_rate": latest.get("hit_rate"),
        "season_hit_rate": latest.get("cumulative_hit_rate"),
        "hit_rate_delta": latest.get("hit_rate_delta"),
        "first_week": first.get("week"),
        "direction": _trend_direction(points),
    }


def _trend_direction(points: list[dict[str, Any]]) -> str:
    """Compare recent weeks vs earlier weeks for a simple label."""

    rates = [
        float(point["cumulative_hit_rate"])
        for point in points
        if point.get("cumulative_hit_rate") is not None
    ]
    if len(rates) < 2:
        return "flat"
    delta = rates[-1] - rates[0]
    if delta >= 2.0:
        return "improving"
    if delta <= -2.0:
        return "declining"
    return "flat"


def calibration_feedback_from_results(
    settled: list[dict[str, Any]],
    *,
    min_games: int = 5,
    dampen: float = 0.35,
) -> dict[str, Any]:
    """
    Convert settled residuals into a dampened bias correction
    for future projections.
    """

    game_total: dict[str, float] = {}
    game_spread: dict[str, float] = {}
    for row in settled:
        eid = str(row.get("event_id") or "")
        if not eid:
            continue
        if num(row.get("total_error")) is not None:
            game_total[eid] = float(row["total_error"])
        if num(row.get("spread_error")) is not None:
            game_spread[eid] = float(row["spread_error"])

    n = max(len(game_total), len(game_spread))
    if n < min_games:
        return {
            "sample_games": n,
            "total_bias": 0.0,
            "spread_bias": 0.0,
            "active": False,
            "note": (
                f"Need at least {min_games} settled games before "
                "projection feedback activates."
            ),
        }

    mean_total = (
        sum(game_total.values()) / len(game_total)
        if game_total
        else 0.0
    )
    mean_spread = (
        sum(game_spread.values()) / len(game_spread)
        if game_spread
        else 0.0
    )
    # Subtract model−actual bias from future projections.
    return {
        "sample_games": n,
        "total_bias": round(mean_total * dampen, 3),
        "spread_bias": round(mean_spread * dampen, 3),
        "raw_mean_total_error": round(mean_total, 3),
        "raw_mean_spread_error": round(mean_spread, 3),
        "active": True,
        "dampen": dampen,
        "note": (
            "Future projections subtract dampened mean residual "
            "error observed on auto-settled games."
        ),
    }


def apply_calibration_to_scores(
    home: float | None,
    away: float | None,
    *,
    feedback: dict[str, Any] | None,
) -> tuple[float | None, float | None]:
    if home is None or away is None or not feedback:
        return home, away
    if not feedback.get("active"):
        return home, away
    total_bias = float(feedback.get("total_bias") or 0.0)
    spread_bias = float(feedback.get("spread_bias") or 0.0)
    # total_bias is model−actual; remove half from each side.
    adj_home = float(home) - total_bias / 2.0
    adj_away = float(away) - total_bias / 2.0
    # spread is away−home; remove spread_bias accordingly.
    adj_away -= spread_bias / 2.0
    adj_home += spread_bias / 2.0
    return round(adj_home, 1), round(adj_away, 1)


def _settle_one_market(
    market: dict[str, Any],
    *,
    home_score: int,
    away_score: int,
    actual_total: int,
    actual_spread: float,
    bet_market_spread: float | None = None,
    closing_market_spread: float | None = None,
    bet_market_total: float | None = None,
    closing_market_total: float | None = None,
    closing_home_moneyline: float | None = None,
    bet_home_moneyline: float | None = None,
) -> dict[str, Any] | None:
    market_type = str(market.get("market_type") or "").lower()
    selection = str(market.get("selection") or "")
    home = str(market.get("home_team") or "").upper()
    away = str(market.get("away_team") or "").upper()
    line = num(market.get("line"))
    price = num(market.get("price"))
    side = selection_side(
        market_type=market_type,
        selection=selection,
        home_team=home,
        away_team=away,
    )

    result = None
    actual_value = None
    bet_line = line
    closing_line = None
    bet_price = price
    closing_price = None

    if market_type == "total":
        if line is None:
            return None
        actual_value = float(actual_total)
        # Closing total = last known market total (not final score).
        closing_line = (
            closing_market_total
            if closing_market_total is not None
            else line
        )
        if bet_market_total is not None:
            bet_line = float(bet_market_total)
        sel_u = selection.upper()
        if "OVER" in sel_u:
            if actual_total > line:
                result = "won"
            elif actual_total < line:
                result = "lost"
            else:
                result = "push"
        elif "UNDER" in sel_u:
            if actual_total < line:
                result = "won"
            elif actual_total > line:
                result = "lost"
            else:
                result = "push"
        else:
            return None

    elif market_type == "spread":
        if line is None:
            return None
        side_home = side == "home"
        side_away = side == "away"
        if not side_home and not side_away:
            return None
        if side_home:
            margin = home_score + float(line) - away_score
            actual_value = float(home_score - away_score)
        else:
            margin = away_score + float(line) - home_score
            actual_value = float(away_score - home_score)
        # Closing = last known market spread on this selection.
        closing_line = event_spread_as_selection_line(
            closing_market_spread, side=side
        )
        if closing_line is None:
            closing_line = line
        snap_bet = event_spread_as_selection_line(
            bet_market_spread, side=side
        )
        if snap_bet is not None:
            bet_line = float(snap_bet)
        if margin > 0:
            result = "won"
        elif margin < 0:
            result = "lost"
        else:
            result = "push"

    elif market_type == "moneyline":
        if side == "home":
            result = "won" if home_score > away_score else (
                "push" if home_score == away_score else "lost"
            )
            actual_value = float(home_score - away_score)
            closing_price = closing_home_moneyline
            bet_price = (
                bet_home_moneyline
                if bet_home_moneyline is not None
                else price
            )
        elif side == "away":
            result = "won" if away_score > home_score else (
                "push" if home_score == away_score else "lost"
            )
            actual_value = float(away_score - home_score)
            # Away ML ≈ inverse of home implied when only home stored.
            if closing_home_moneyline is not None:
                home_imp = None
                from app.analysis.insights.betting.pricing import (
                    american_to_implied_prob,
                    implied_prob_to_american,
                )

                home_imp = american_to_implied_prob(
                    closing_home_moneyline
                )
                if home_imp is not None:
                    closing_price = implied_prob_to_american(
                        1.0 - float(home_imp)
                    )
            if bet_home_moneyline is not None:
                from app.analysis.insights.betting.pricing import (
                    american_to_implied_prob,
                    implied_prob_to_american,
                )

                home_imp = american_to_implied_prob(bet_home_moneyline)
                if home_imp is not None:
                    bet_price = implied_prob_to_american(
                        1.0 - float(home_imp)
                    )
            if bet_price is None:
                bet_price = price
        else:
            return None
        # Moneyline closing_line keeps signed margin for reference;
        # CLV uses prices.
        closing_line = None
        bet_line = None

    else:
        return None

    model_correct = result == "won"
    edge_points = num(market.get("edge"))
    edge_probability = (
        num(market.get("edge_probability"))
        if market.get("edge_probability") is not None
        else None
    )
    return {
        "market_id": market.get("market_id"),
        "market_type": market_type,
        "selection": selection,
        "line": line,
        "bet_line": bet_line,
        "price": price,
        "bet_price": bet_price,
        "closing_price": closing_price,
        "model_probability": num(market.get("model_probability")),
        "raw_model_probability": num(
            market.get("raw_model_probability")
            if market.get("raw_model_probability") is not None
            else market.get("model_probability")
        ),
        "market_probability": num(market.get("market_probability")),
        "edge_points": edge_points,
        "edge": (
            edge_probability
            if edge_probability is not None
            else edge_points
        ),
        "edge_probability": edge_probability,
        "confidence": market.get("confidence") or "Low",
        "result": result,
        "model_correct": model_correct if result != "push" else None,
        "actual_value": actual_value,
        "closing_line": closing_line,
        "bet_side": side,
    }


def _breakdown(
    rows: list[dict[str, Any]],
    field: str,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = str(row.get(field) or "unknown")
        buckets[key].append(row)
    out = []
    for key, items in buckets.items():
        decided = [
            row for row in items if row.get("result") in {"won", "lost"}
        ]
        correct = [
            row for row in decided if row.get("result") == "won"
        ]
        out.append(
            {
                "key": key,
                "bets": len(items),
                "decided": len(decided),
                "correct": len(correct),
                "hit_rate": (
                    round(100.0 * len(correct) / len(decided), 1)
                    if decided
                    else None
                ),
                "average_edge": _avg(
                    [
                        float(row["edge"])
                        for row in items
                        if num(row.get("edge")) is not None
                    ]
                ),
            }
        )
    out.sort(key=lambda row: (-row["bets"], row["key"]))
    return out


def _calibration(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bands = [
        ("50–55%", 0.50, 0.55),
        ("55–60%", 0.55, 0.60),
        ("60–65%", 0.60, 0.65),
        ("65–70%", 0.65, 0.70),
        ("70%+", 0.70, 1.01),
    ]
    out = []
    for label, low, high in bands:
        bucket = [
            row
            for row in rows
            if row.get("result") in {"won", "lost"}
            and num(row.get("model_probability")) is not None
            and low <= float(row["model_probability"]) < high
        ]
        if not bucket:
            out.append(
                {
                    "bucket": label,
                    "bets": 0,
                    "predicted_midpoint": round(
                        100.0 * ((low + min(high, 1.0)) / 2.0), 1
                    ),
                    "actual_win_rate": None,
                }
            )
            continue
        won = sum(1 for row in bucket if row.get("result") == "won")
        out.append(
            {
                "bucket": label,
                "bets": len(bucket),
                "predicted_midpoint": round(
                    100.0 * ((low + min(high, 1.0)) / 2.0), 1
                ),
                "actual_win_rate": round(100.0 * won / len(bucket), 1),
            }
        )
    return out


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)
