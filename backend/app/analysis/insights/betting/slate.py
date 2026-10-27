"""
Build Sports Betting slate from canonical game markets.

Supports NFL (fantasy_football / nflverse) and CFB
(college_football / sportsdataverse).

Sources:
  - dim_game / dim_team for schedule identity
  - fact_game_market for spread / total / implied scores
  - fact_team_game / fact_defensive_game opponent-adjusted
    team strength for InsightPilot score residuals

Architecture:
  market baseline + model residual = InsightPilot projection

Market types emitted: spread, total, moneyline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.betting_sport import (
    BettingSportConfig,
    resolve_betting_sport,
    resolve_current_season,
)
from app.analysis.insights.betting.pricing import (
    REFERENCE_PROBABILITY,
    american_to_implied_prob,
    confidence_explanation,
    confidence_from_edge,
    cover_probability_from_engine,
    expected_value_american,
    implied_prob_to_american,
    market_edge_probability,
    num,
    over_probability_from_engine,
    reference_edge_probability,
    spread_to_cover_probability,
    total_to_over_probability,
    win_probability_from_engine,
    win_probability_from_spread,
)
from app.analysis.insights.betting.qualification_thresholds import (
    fit_qualification_thresholds,
    prior_qualification_thresholds,
)
from app.analysis.insights.betting.score_distribution import (
    build_distribution_features,
    empty_score_distribution,
    fit_score_distribution,
    prior_score_distribution_model,
    simulate_game_scores,
)
from app.analysis.insights.betting.score_distribution_dataset import (
    build_score_distribution_rows,
)
from app.analysis.insights.betting.context_ablation import (
    run_context_ablation,
)
from app.analysis.insights.betting.game_scripts import (
    project_game_scripts,
)
from app.analysis.insights.betting.player_context import (
    combined_impact_sigma,
    combined_score_adjustments,
    load_week_player_context,
    refine_injury_with_market_move,
    team_injury_context,
)
from app.analysis.insights.betting.results import (
    build_bet_tape_snapshot,
    build_performance_trend,
    calibration_feedback_from_results,
    filter_learning_rows,
    is_game_final,
    settle_event_markets,
    summarize_model_results,
    trend_summary_from_points,
)
from app.analysis.insights.betting.team_strength import (
    load_team_strength_context,
)
from app.analysis.insights.betting.opponent_tendency import (
    event_tendency_payload,
    load_opponent_tendency_context,
    tendency_situational_adjustments,
)
from app.analysis.insights.betting.residual_model import (
    add_situational_residuals,
    apply_score_residuals,
    calibration_score_deltas,
    predict_score_residuals,
)
from app.analysis.insights.betting.residual_features import (
    build_residual_features,
)
from app.analysis.insights.betting.residual_challenger import (
    challenger_to_residual_payload,
    compare_champion_challenger,
    fit_residual_challenger,
    predict_challenger_residuals,
    prior_challenger_model,
)
from app.analysis.insights.betting.residual_challenger_dataset import (
    build_challenger_training_rows,
    rest_days_by_game,
)
from app.analysis.insights.betting.model_disagreement import (
    build_model_disagreement,
    disagreement_for_market,
)
from app.analysis.insights.betting.market_movement import (
    build_market_movement,
)
from app.analysis.insights.betting.probability_calibration import (
    calibrate_market_probability,
    fit_probability_calibration,
)
from app.analysis.insights.betting.edge_confidence import (
    fit_confidence_thresholds,
)
from app.analysis.insights.betting.market_performance import (
    build_market_performance,
    merge_edge_confidence_with_markets,
)
from app.analysis.insights.betting.bet_qualification import (
    evaluate_market_decision,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_DEFAULT_PRICE = -110
_SPORT = "NFL"
_LEAGUE = "NFL"


def list_betting_weeks(
    *,
    season: int | None = None,
    sport: str = "NFL",
) -> dict[str, Any]:
    sport_config = resolve_betting_sport(sport)
    resolved = _resolve_season(season, sport_config=sport_config)
    weeks = _available_betting_weeks(
        season=resolved,
        sport_config=sport_config,
    )
    current = _current_betting_week(
        season=resolved,
        available_weeks=weeks,
        sport_config=sport_config,
    )
    return {
        "sport": sport_config.id,
        "league": sport_config.league,
        "season": resolved,
        "weeks": weeks,
        "current_week": current,
    }


def _sport_team_logo_url(
    sport: str,
    espn_team_id: Any,
    *,
    abbreviation: str | None = None,
) -> str | None:
    """
    ESPN CDN logo URL scoped by sport.

    CFB must use ncaa/{espn_id} — abbreviation URLs collide with NFL.
    """

    espn_id = str(espn_team_id or "").strip()
    if sport == "CFB":
        if not espn_id or not espn_id.isdigit():
            return None
        return (
            "https://a.espncdn.com/i/teamlogos/ncaa/500/"
            f"{espn_id}.png"
        )

    abbr = str(abbreviation or "").strip().lower()
    if abbr:
        return (
            f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"
        )
    if espn_id and espn_id.isdigit():
        return (
            "https://a.espncdn.com/i/teamlogos/nfl/500/"
            f"{espn_id}.png"
        )
    return None


def _available_betting_weeks(
    *,
    season: int,
    sport_config: BettingSportConfig,
) -> list[int]:
    """
    Weeks selectable in the UI.

    Prefer schedule weeks from dim_game so the current / upcoming
    slate is available even before lines land in fact_game_market.
    Fall back to market weeks when the schedule table is empty.
    """

    schema = sport_config.schema
    weeks: list[int] = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT DISTINCT week
                    FROM {schema}.dim_game
                    WHERE season = :season
                      AND week IS NOT NULL
                    ORDER BY week
                    """
                ),
                {"season": int(season)},
            ).fetchall()
            weeks = [int(row[0]) for row in rows if row[0] is not None]
    except Exception:
        weeks = []

    if weeks:
        return weeks

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT DISTINCT week
                    FROM {schema}.fact_game_market
                    WHERE season = :season
                      AND week IS NOT NULL
                    ORDER BY week
                    """
                ),
                {"season": int(season)},
            ).fetchall()
            weeks = [int(row[0]) for row in rows if row[0] is not None]
    except Exception:
        weeks = []
    return weeks


def build_betting_slate(
    *,
    season: int | None = None,
    week: int | None = None,
    sport: str = "NFL",
    residual_model: str = "auto",
    probability_engine: str = "logistic",
) -> dict[str, Any]:
    sport_config = resolve_betting_sport(sport)
    resolved_season = _resolve_season(
        season,
        sport_config=sport_config,
    )
    applied_residual = _resolve_residual_model(
        residual_model, season=resolved_season
    )
    applied_prob_engine = _resolve_probability_engine(
        probability_engine
    )
    resolved_week = _resolve_week(
        week,
        season=resolved_season,
        sport_config=sport_config,
    )
    events = _load_events(
        season=resolved_season,
        week=resolved_week,
        sport_config=sport_config,
    )
    strength_context = load_team_strength_context(
        season=resolved_season,
        before_week=resolved_week,
        sport=sport_config,
    )
    player_context = load_week_player_context(
        season=resolved_season,
        week=resolved_week,
        sport=sport_config.id,
    )
    # Learning / calibration tables are NFL-scoped for now.
    # Skipping them on CFB avoids multi-minute cold loads.
    # Opponent tendency uses sport-native strength + markets and
    # is available for both NFL and CFB champion paths.
    use_learning = sport_config.id == "NFL"
    try:
        tendency_context = load_opponent_tendency_context(
            season=resolved_season,
            before_week=resolved_week,
            sport=sport_config,
        )
    except Exception:
        tendency_context = None
    calibration = (
        _load_calibration_feedback(resolved_season)
        if use_learning
        else None
    )
    probability_calibrations = (
        _load_probability_calibrations(resolved_season)
        if use_learning
        else {}
    )
    probability_calibration = probability_calibrations.get("all")
    edge_confidence = (
        _load_edge_confidence(resolved_season)
        if use_learning
        else None
    )
    challenger_model = (
        _load_residual_challenger(resolved_season)
        if use_learning
        else None
    )
    score_dist_model = (
        _load_score_distribution(resolved_season)
        if use_learning
        else None
    )
    rest_by_game = (
        rest_days_by_game(season=resolved_season)
        if use_learning
        else {}
    )
    context_ablation = (
        _load_context_ablation(resolved_season)
        if use_learning
        else None
    )
    qualification_thresholds = (
        (
            _load_qualification_thresholds(resolved_season)
            or prior_qualification_thresholds()
        )
        if use_learning
        else prior_qualification_thresholds()
    )
    enriched: list[dict[str, Any]] = []
    markets: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    newly_settled: list[dict[str, Any]] = []

    from app.canonical.fact_betting_results import (
        get_projection_snapshots,
    )

    snapshots = get_projection_snapshots(
        [
            str(event.get("event_id") or "")
            for event in events
        ]
    )
    stored_by_id = _stored_results_by_market(
        season=resolved_season,
        week=resolved_week,
    )

    for event in events:
        built = _enrich_event(
            event,
            strength_context=strength_context,
            tendency_context=tendency_context,
            player_context=player_context,
            calibration=calibration,
            probability_calibration=probability_calibration,
            probability_calibrations=probability_calibrations,
            rest_by_game=rest_by_game,
            edge_confidence=edge_confidence,
            challenger_model=challenger_model,
            residual_model=applied_residual,
            score_distribution_model=score_dist_model,
            probability_engine=applied_prob_engine,
            qualification_thresholds=qualification_thresholds,
            sport_config=sport_config,
        )
        event_row = built["event"]
        event_markets = built["markets"]
        event_id = str(event_row.get("event_id") or "")
        # Snapshot / settle against final scores when available.
        settled_rows = _sync_event_results(
            event_row,
            event_markets,
            existing_snapshot=snapshots.get(event_id),
            snapshot_loaded=True,
        )
        newly_settled.extend(
            row
            for row in settled_rows
            if _settlement_changed(
                stored_by_id.get(str(row.get("market_id") or "")),
                row,
            )
        )
        enriched.append(event_row)
        markets.extend(event_markets)
        signals.extend(built["signals"])

    if newly_settled:
        _refresh_season_calibration(
            season=resolved_season,
            extra_rows=newly_settled,
        )

    markets_sorted = sorted(
        markets,
        key=lambda row: (
            -(abs(num(row.get("edge")) or 0.0)),
            str(row.get("start_time") or ""),
        ),
    )
    enriched_sorted = sorted(
        enriched,
        key=lambda row: (
            str(row.get("start_time") or "9999"),
            str(row.get("label") or ""),
        ),
    )
    with_edge = [
        row
        for row in markets_sorted
        if (num(row.get("edge")) or 0.0) != 0.0
        and row.get("confidence") in {"High", "Moderate"}
    ]
    qualified_bets = [
        row
        for row in markets_sorted
        if row.get("bet_qualified")
    ]
    strong_bets = [
        row
        for row in markets_sorted
        if row.get("bet_status") == "strong_bet"
    ]
    lean_bets = [
        row
        for row in markets_sorted
        if row.get("bet_status") == "lean"
    ]
    no_bets = [
        row
        for row in markets_sorted
        if row.get("no_bet") or row.get("bet_status") == "pass"
    ]
    confidences = [
        row.get("confidence")
        for row in markets_sorted
        if row.get("confidence")
    ]
    avg_confidence = _majority_confidence(confidences)
    covered = sum(
        1
        for row in markets_sorted
        if row.get("model_probability") is not None
        or row.get("model_projection") is not None
    )
    coverage = (
        round(100.0 * covered / len(markets_sorted), 0)
        if markets_sorted
        else 0.0
    )

    return {
        "sport": sport_config.id,
        "league": sport_config.league,
        "season": resolved_season,
        "week": resolved_week,
        "slate_id": (
            f"{sport_config.slate_prefix}-"
            f"{resolved_season}-w{resolved_week}"
        ),
        "label": (
            f"{sport_config.label_sport} Week {resolved_week}"
        ),
        "game_count": len(enriched_sorted),
        "market_count": len(markets_sorted),
        "model_coverage_pct": coverage,
        "markets_with_edge": len(with_edge),
        "markets_qualified": len(qualified_bets),
        "markets_strong_bet": len(strong_bets),
        "markets_lean": len(lean_bets),
        "markets_no_bet": len(no_bets),
        "average_confidence": avg_confidence,
        "events": enriched_sorted,
        "markets": markets_sorted,
        "signals": signals[:12],
        "source": sport_config.source_label,
        "source_note": (
            f"{sport_config.source_note} "
            "Displayed win probabilities are calibrated "
            "against historical predicted vs actual results "
            "when enough settled bets exist. "
            "Predictions are separate from bets — markets are "
            "classified Strong Bet / Lean / Pass using explicit "
            "edge, EV, confidence, data-quality, and market-move "
            "thresholds. Pass / No Bet is a first-class outcome."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "injury_report_week": player_context.get("week"),
        "residual_model": applied_residual,
        "probability_engine": applied_prob_engine,
        "score_distribution_model": (
            {
                "active": bool(
                    (score_dist_model or {}).get("active")
                ),
                "method": (score_dist_model or {}).get("method"),
                "sample_size": (score_dist_model or {}).get(
                    "sample_size"
                ),
                "sigma_home": (score_dist_model or {}).get(
                    "sigma_home"
                ),
                "sigma_away": (score_dist_model or {}).get(
                    "sigma_away"
                ),
                "rho": (score_dist_model or {}).get("rho"),
                "note": (score_dist_model or {}).get("note"),
            }
            if score_dist_model
            else {
                "active": False,
                "method": "prior",
                "sample_size": 0,
            }
        ),
        "residual_challenger": (
            {
                "active": bool(
                    (challenger_model or {}).get("active")
                ),
                "method": (challenger_model or {}).get("method"),
                "sample_size": (challenger_model or {}).get(
                    "sample_size"
                ),
                "model_version": (challenger_model or {}).get(
                    "model_version"
                ),
                "note": (challenger_model or {}).get("note"),
            }
            if challenger_model
            else {
                "active": False,
                "method": "prior",
                "sample_size": 0,
                "model_version": None,
                "note": "Challenger model not fitted yet.",
            }
        ),
        "probability_calibration": (
            {
                "active": bool(
                    probability_calibration.get("active")
                ),
                "method": probability_calibration.get("method"),
                "sample_size": probability_calibration.get(
                    "sample_size"
                ),
                "metrics": probability_calibration.get("metrics"),
                "note": probability_calibration.get("note"),
            }
            if probability_calibration
            else None
        ),
        "edge_confidence": (
            {
                "active": bool(edge_confidence.get("active")),
                "method": edge_confidence.get("method"),
                "sample_size": edge_confidence.get("sample_size"),
                "high_min": edge_confidence.get("high_min"),
                "moderate_min": edge_confidence.get("moderate_min"),
                "by_market": edge_confidence.get("by_market"),
                "note": edge_confidence.get("note"),
                "market_note": edge_confidence.get("market_note"),
            }
            if edge_confidence
            else None
        ),
        "context_ablation": context_ablation,
        "qualification_thresholds": {
            "active": bool(qualification_thresholds.get("active")),
            "source": qualification_thresholds.get("source"),
            "method": qualification_thresholds.get("method"),
            "strong_bet": qualification_thresholds.get("strong_bet"),
            "lean": qualification_thresholds.get("lean"),
            "metrics": qualification_thresholds.get("metrics"),
            "note": qualification_thresholds.get("note"),
            "sample_size": qualification_thresholds.get("sample_size"),
        },
        "model_promotion": _load_model_promotion_summary(
            resolved_season
        ),
    }


def get_betting_event(
    event_id: str,
    *,
    season: int | None = None,
    sport: str = "NFL",
) -> dict[str, Any] | None:
    eid = str(event_id or "").strip()
    if not eid:
        return None
    sport_config = resolve_betting_sport(sport)
    resolved_season = _resolve_season(
        season,
        sport_config=sport_config,
    )
    events = _load_events(
        season=resolved_season,
        week=None,
        event_id=eid,
        sport_config=sport_config,
    )
    if not events:
        return None
    week = _as_int(events[0].get("week")) or _resolve_week(
        None,
        season=resolved_season,
        sport_config=sport_config,
    )
    strength_context = load_team_strength_context(
        season=resolved_season,
        before_week=week,
        sport=sport_config,
    )
    player_context = load_week_player_context(
        season=resolved_season,
        week=week,
        sport=sport_config.id,
    )
    use_learning = sport_config.id == "NFL"
    try:
        tendency_context = load_opponent_tendency_context(
            season=resolved_season,
            before_week=week,
            sport=sport_config,
        )
    except Exception:
        tendency_context = None
    calibration = (
        _load_calibration_feedback(resolved_season)
        if use_learning
        else None
    )
    probability_calibrations = (
        _load_probability_calibrations(resolved_season)
        if use_learning
        else {}
    )
    probability_calibration = probability_calibrations.get("all")
    edge_confidence = (
        _load_edge_confidence(resolved_season)
        if use_learning
        else None
    )
    challenger_model = (
        _load_residual_challenger(resolved_season)
        if use_learning
        else None
    )
    score_dist_model = (
        _load_score_distribution(resolved_season)
        if use_learning
        else None
    )
    applied_residual = _resolve_residual_model(
        "auto", season=resolved_season
    )
    built = _enrich_event(
        events[0],
        strength_context=strength_context,
        tendency_context=tendency_context,
        player_context=player_context,
        calibration=calibration,
        probability_calibration=probability_calibration,
        probability_calibrations=probability_calibrations,
        edge_confidence=edge_confidence,
        challenger_model=challenger_model,
        residual_model=applied_residual,
        score_distribution_model=score_dist_model,
        probability_engine="logistic",
        sport_config=sport_config,
    )
    _sync_event_results(built["event"], built["markets"])
    return built


def build_betting_results(
    *,
    season: int | None = None,
    week: int | None = None,
    sport: str = "NFL",
) -> dict[str, Any]:
    """
    Auto-settle completed games for the week/season and return
    model-vs-actual performance (all markets, not portfolio-only).
    """

    sport_config = resolve_betting_sport(sport)
    resolved_season = _resolve_season(
        season,
        sport_config=sport_config,
    )
    resolved_week = _resolve_week(
        week,
        season=resolved_season,
        sport_config=sport_config,
    )
    # Pull overnight / MNF finals into dim_game before settlement.
    # Without this, Results depended on a manual dim_game refresh and
    # Monday-night scores could sit in nflverse while the page still
    # treated the game as unsettled. CFB has no nflverse score sync.
    if sport_config.id == "NFL":
        try:
            from app.canonical.dim_game import sync_dim_game_scores

            sync_dim_game_scores(
                [resolved_season],
                week=resolved_week,
            )
        except Exception:
            pass

    slate = build_betting_slate(
        season=resolved_season,
        week=resolved_week,
        sport=sport_config.id,
    )
    season_value = slate.get("season")
    week_value = slate.get("week")
    try:
        from app.canonical.fact_betting_results import (
            load_market_results,
        )

        stored = load_market_results(
            season=season_value,
            week=week_value,
        )
        # Season-wide rows power the performance trend chart.
        season_stored = load_market_results(season=season_value)
    except Exception:
        stored = []
        season_stored = []

    # Prefer freshly settled rows from this slate build when storage
    # is empty (e.g. tests / first run).
    if not stored:
        live: list[dict[str, Any]] = []
        markets_by_event: dict[str, list[dict[str, Any]]] = {}
        for market in slate.get("markets") or []:
            eid = str(market.get("event_id") or "")
            markets_by_event.setdefault(eid, []).append(market)
        for event in slate.get("events") or []:
            if not is_game_final(event):
                continue
            snap = build_bet_tape_snapshot(
                event, prefer_opening=True
            )
            live.extend(
                settle_event_markets(
                    event,
                    markets_by_event.get(
                        str(event.get("event_id") or ""), []
                    ),
                    snapshot=snap,
                )
            )
        stored = live

    summary = summarize_model_results(stored)
    trend_source = season_stored or stored
    summary["performance_trend"] = build_performance_trend(
        trend_source
    )
    summary["trend_summary"] = trend_summary_from_points(
        summary["performance_trend"]
    )

    feedback = _load_calibration_feedback(
        int(season_value or 0)
    ) or calibration_feedback_from_results(stored)
    # The slate refits calibration when a final score is new.
    # Doing it again on every Results view blocked the API.
    probability_calibration = _load_probability_calibration(
        int(season_value) if season_value is not None else resolved_season
    )
    edge_confidence = (
        (summary or {}).get("edge_confidence")
        or _load_edge_confidence(
            int(season_value)
            if season_value is not None
            else resolved_season
        )
    )
    learning_report = None
    model_promotion = None
    try:
        from app.canonical.fact_betting_results import (
            get_learning_report,
            get_model_promotion,
        )

        sid = int(
            season_value
            if season_value is not None
            else resolved_season
        )
        learning_report = get_learning_report(sid)
        model_promotion = get_model_promotion(sid)
    except Exception:
        pass
    return {
        "sport": sport_config.id,
        "league": sport_config.league,
        "season": season_value,
        "week": week_value,
        "slate_id": slate.get("slate_id"),
        "label": f"{slate.get('label')} · Model Results",
        "model_results": summary,
        "calibration_feedback": feedback,
        "probability_calibration": (
            {
                "active": bool(
                    (probability_calibration or {}).get("active")
                ),
                "method": (probability_calibration or {}).get("method"),
                "sample_size": (probability_calibration or {}).get(
                    "sample_size"
                ),
                "metrics": (probability_calibration or {}).get("metrics"),
                "note": (probability_calibration or {}).get("note"),
            }
            if probability_calibration
            else None
        ),
        "edge_confidence": edge_confidence,
        "market_performance": (summary or {}).get("market_performance"),
        "learning": learning_report,
        "model_promotion": model_promotion,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _sync_event_results(
    event: dict[str, Any],
    markets: list[dict[str, Any]],
    *,
    existing_snapshot: dict[str, Any] | None = None,
    snapshot_loaded: bool = False,
) -> list[dict[str, Any]]:
    try:
        from app.canonical.fact_betting_results import (
            freeze_projection_snapshot,
            get_projection_snapshot,
            upsert_market_results,
            upsert_projection_snapshot,
        )
    except Exception:
        return []

    event_id = str(event.get("event_id") or "")
    if snapshot_loaded:
        existing = existing_snapshot
    else:
        existing = get_projection_snapshot(event_id)

    from app.analysis.insights.betting.model_learning import (
        build_enriched_prediction_snapshot,
    )

    if not is_game_final(event):
        # Capture a first-publish prediction log (features, versions,
        # odds, decisions) for later CLV/settlement grading, but do
        # not freeze yet — open games recompute live so model
        # upgrades appear on refresh.
        if not existing:
            snap = build_enriched_prediction_snapshot(
                event, markets, prefer_opening=False
            )
            upsert_projection_snapshot(snap, freeze=False)
        return []

    if existing and not existing.get("frozen"):
        freeze_projection_snapshot(event_id)
        existing = get_projection_snapshot(event_id)
    elif not existing:
        # No pregame tape — use opening lines, never close/current.
        snap = build_enriched_prediction_snapshot(
            event, markets, prefer_opening=True
        )
        snap["frozen"] = True
        upsert_projection_snapshot(snap, freeze=True)
        existing = snap

    settled = settle_event_markets(
        event,
        markets,
        snapshot=existing
        or build_enriched_prediction_snapshot(
            event, markets, prefer_opening=True
        ),
    )
    if settled:
        upsert_market_results(settled)
    return settled


def _load_projection_snapshot(
    event_id: str,
) -> dict[str, Any] | None:
    if not event_id:
        return None
    try:
        from app.canonical.fact_betting_results import (
            get_projection_snapshot,
        )

        return get_projection_snapshot(event_id)
    except Exception:
        return None


def _load_calibration_feedback(
    season: int,
) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_calibration_feedback,
        )

        return get_calibration_feedback(int(season))
    except Exception:
        return None


def _load_probability_calibration(
    season: int,
) -> dict[str, Any] | None:
    """Load the blended ``all`` calibration model (compat helper)."""

    models = _load_probability_calibrations(season)
    return models.get("all")


def _load_probability_calibrations(
    season: int,
) -> dict[str, dict[str, Any]]:
    """Load per-market + all probability calibration models."""

    try:
        from app.canonical.fact_betting_results import (
            get_probability_calibration,
        )
    except Exception:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for mtype in ("all", "spread", "total", "moneyline"):
        try:
            model = get_probability_calibration(
                int(season), market_type=mtype
            )
        except Exception:
            model = None
        if model:
            out[mtype] = model
    return out


def _calibration_for_market(
    calibrations: dict[str, dict[str, Any]] | None,
    market_type: str,
) -> dict[str, Any] | None:
    if not calibrations:
        return None
    mtype = str(market_type or "").lower()
    return calibrations.get(mtype) or calibrations.get("all")


def _load_edge_confidence(season: int) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_edge_confidence,
        )

        return get_edge_confidence(int(season))
    except Exception:
        return None


def _load_residual_challenger(season: int) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_residual_challenger,
        )

        return get_residual_challenger(int(season))
    except Exception:
        return None


def _load_model_promotion_summary(
    season: int,
) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_model_promotion,
        )

        row = get_model_promotion(int(season))
        if not row:
            return {
                "active_model": "champion",
                "decision": None,
                "note": "No promotion cycle recorded yet.",
            }
        return {
            "active_model": row.get("active_model") or "champion",
            "decision": row.get("decision"),
            "candidate_version": row.get("candidate_version"),
            "sample_size": row.get("sample_size"),
            "relative_improvement": row.get("relative_improvement"),
            "bootstrap_confidence": row.get("bootstrap_confidence"),
            "note": row.get("note"),
            "decided_at": row.get("decided_at"),
        }
    except Exception:
        return None


def _resolve_residual_model(
    value: str | None,
    *,
    season: int | None = None,
) -> str:
    label = str(value or "auto").strip().lower()
    if label in {"challenger", "challenger_ridge", "ridge"}:
        return "challenger"
    if label == "champion":
        return "champion"
    # auto: use walk-forward promotion registry when available.
    if season is not None:
        try:
            from app.canonical.fact_betting_results import (
                get_active_residual_model,
            )

            return get_active_residual_model(int(season))
        except Exception:
            return "champion"
    return "champion"


def _resolve_probability_engine(value: str | None) -> str:
    label = str(value or "logistic").strip().lower()
    if label in {
        "simulation",
        "sim",
        "bivariate",
        "score_distribution",
        "monte_carlo",
    }:
        return "simulation"
    return "logistic"


def _load_score_distribution(season: int) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_score_distribution,
        )

        return get_score_distribution(int(season))
    except Exception:
        return None


def _load_context_ablation(season: int) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_context_ablation,
        )

        return get_context_ablation(int(season))
    except Exception:
        return None


def _load_qualification_thresholds(season: int) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_qualification_thresholds,
        )

        return get_qualification_thresholds(int(season))
    except Exception:
        return None


def _stored_results_by_market(
    *,
    season: int,
    week: int,
) -> dict[str, dict[str, Any]]:
    try:
        from app.canonical.fact_betting_results import (
            load_market_results,
        )

        rows = load_market_results(season=season, week=week)
    except Exception:
        return {}
    return {
        str(row.get("market_id")): row
        for row in rows
        if row.get("market_id")
    }


def _settlement_changed(
    previous: dict[str, Any] | None,
    row: dict[str, Any],
) -> bool:
    """True when this final is new or the score/result moved."""

    if not previous:
        return True
    for key in ("result", "home_score", "away_score", "model_correct"):
        if not _same_result_value(previous.get(key), row.get(key)):
            return True
    return False


def _same_result_value(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) == bool(right)
    try:
        return abs(float(left) - float(right)) < 1e-6
    except (TypeError, ValueError):
        return str(left) == str(right)


def _refresh_season_calibration(
    *,
    season: int,
    extra_rows: list[dict[str, Any]] | None = None,
) -> None:
    try:
        from app.canonical.fact_betting_results import (
            load_market_results,
            upsert_calibration,
            upsert_edge_confidence,
            upsert_probability_calibration,
            upsert_residual_challenger,
            upsert_score_distribution,
            upsert_context_ablation,
            upsert_qualification_thresholds,
        )
    except Exception:
        return
    rows = load_market_results(season=season)
    if extra_rows:
        # Merge in-memory rows not yet readable.
        seen = {str(row.get("market_id")) for row in rows}
        for row in extra_rows:
            mid = str(row.get("market_id") or "")
            if mid and mid not in seen:
                rows.append(row)
    learn_rows, cohort_label = filter_learning_rows(rows)
    feedback = calibration_feedback_from_results(learn_rows)
    feedback["learning_cohort"] = cohort_label
    upsert_calibration(feedback, season=int(season))

    # Probability calibration: fit from raw predicted vs actual
    # on the actionable cohort when available.
    prob_model = fit_probability_calibration(
        learn_rows, method="auto"
    )
    if isinstance(prob_model, dict):
        note = str(prob_model.get("note") or "")
        prob_model["learning_cohort"] = cohort_label
        prob_model["note"] = (
            f"{note} Cohort={cohort_label}." if note else note
        )
    upsert_probability_calibration(
        prob_model,
        season=int(season),
        market_type="all",
    )

    # Learn High/Moderate floors from point-edge bucket backtests.
    edge_model = fit_confidence_thresholds(learn_rows)
    if isinstance(edge_model, dict):
        edge_model["learning_cohort"] = cohort_label
    market_perf = build_market_performance(learn_rows)
    edge_model = merge_edge_confidence_with_markets(
        edge_model, market_perf
    )
    upsert_edge_confidence(edge_model, season=int(season))

    # Also fit probability calibration per market when samples allow.
    for mtype in ("spread", "total", "moneyline"):
        subset = [
            row
            for row in learn_rows
            if str(row.get("market_type") or "").lower() == mtype
        ]
        if len(subset) < 25:
            continue
        m_model = fit_probability_calibration(
            subset, method="auto", market_type=mtype
        )
        if isinstance(m_model, dict):
            m_model["learning_cohort"] = cohort_label
        upsert_probability_calibration(
            m_model,
            season=int(season),
            market_type=mtype,
        )

    # Fit residual challenger from reconstructed market-error history.
    train_rows: list[dict[str, Any]] = []
    try:
        train_rows = build_challenger_training_rows(season=int(season))
        chall_model = fit_residual_challenger(train_rows)
        upsert_residual_challenger(
            chall_model, season=int(season)
        )
    except Exception:
        chall_model = None

    # Fit bivariate score-distribution params from market residuals.
    try:
        dist_rows = build_score_distribution_rows(season=int(season))
        dist_model = fit_score_distribution(dist_rows)
        upsert_score_distribution(
            dist_model, season=int(season)
        )
    except Exception:
        pass

    # Context feature-group ablation report (injury / rest / move).
    try:
        if not train_rows:
            train_rows = build_challenger_training_rows(
                season=int(season)
            )
        ablation = run_context_ablation(train_rows)
        upsert_context_ablation(ablation, season=int(season))
    except Exception:
        pass

    # Learn Strong/Lean EV + edge floors on time-ordered holdout.
    try:
        learn_rows, _ = filter_learning_rows(rows)
        qual_model = fit_qualification_thresholds(learn_rows)
        upsert_qualification_thresholds(
            qual_model, season=int(season)
        )
    except Exception:
        pass

    # Continuous learning report + walk-forward promotion decision.
    try:
        from app.analysis.insights.betting.model_learning import (
            evaluate_settled_learning,
        )
        from app.analysis.insights.betting.model_promotion import (
            run_model_promotion_cycle,
        )
        from app.canonical.fact_betting_results import (
            get_model_promotion,
            upsert_learning_report,
            upsert_model_promotion,
        )

        learning = evaluate_settled_learning(rows)
        prior = get_model_promotion(int(season)) or {}
        current_active = str(
            prior.get("active_model") or "champion"
        )
        if not train_rows:
            train_rows = build_challenger_training_rows(
                season=int(season)
            )
        promotion_cycle = run_model_promotion_cycle(
            season=int(season),
            training_rows=train_rows,
            current_active=current_active,
            mode="expanding",
        )
        upsert_model_promotion(
            promotion_cycle, season=int(season)
        )
        learning["model_promotion"] = {
            "decision": (
                (promotion_cycle.get("promotion") or {}).get(
                    "decision"
                )
            ),
            "active_model": (
                (promotion_cycle.get("promotion") or {}).get(
                    "active_model"
                )
            ),
            "relative_improvement": (
                (promotion_cycle.get("promotion") or {}).get(
                    "relative_improvement"
                )
            ),
            "bootstrap": (
                (promotion_cycle.get("promotion") or {}).get(
                    "bootstrap"
                )
            ),
            "reasons": (
                (promotion_cycle.get("promotion") or {}).get(
                    "reasons"
                )
            ),
            "walk_forward_available": bool(
                (promotion_cycle.get("walk_forward") or {}).get(
                    "available"
                )
            ),
            "candidate": promotion_cycle.get("candidate"),
        }
        upsert_learning_report(learning, season=int(season))
    except Exception:
        pass


def find_betting_event_by_matchup(
    *,
    home_team: str,
    away_team: str,
    season: int | None = None,
    week: int | None = None,
) -> dict[str, Any] | None:
    """
    Resolve a betting event when DFS nflverse game_ids do not
    match InsightPilot ``ip_game_*`` market event ids.
    """

    home = str(home_team or "").strip().upper()
    away = str(away_team or "").strip().upper()
    if not home or not away:
        return None

    slate = build_betting_slate(season=season, week=week)
    for event in slate.get("events") or []:
        event_home = str(event.get("home_team") or "").upper()
        event_away = str(event.get("away_team") or "").upper()
        if {event_home, event_away} != {home, away}:
            continue
        # Match get_betting_event shape for callers.
        return {
            "event": event,
            "markets": [],
            "signals": [],
        }
    return None


def _resolve_season(
    season: int | None,
    *,
    sport_config: BettingSportConfig | None = None,
) -> int:
    if season is not None:
        return int(season)
    config = sport_config or resolve_betting_sport("NFL")
    return resolve_current_season(config)


def _resolve_week(
    week: int | None,
    *,
    season: int,
    sport_config: BettingSportConfig | None = None,
) -> int:
    if week is not None:
        return max(1, int(week))
    config = sport_config or resolve_betting_sport("NFL")
    listed = list_betting_weeks(
        season=season,
        sport=config.id,
    )
    current = listed.get("current_week")
    if current is not None:
        return int(current)
    return 1


def _current_betting_week(
    *,
    season: int,
    available_weeks: list[int],
    sport_config: BettingSportConfig | None = None,
) -> int | None:
    """
    Prefer the live / upcoming slate week, not the latest completed
    week that happens to have markets.
    """

    config = sport_config or resolve_betting_sport("NFL")
    live_week: int | None = None

    if config.id == "NFL":
        try:
            import nflreadpy as nfl

            current_season = int(nfl.get_current_season())
            if int(season) == current_season:
                live_week = max(1, int(nfl.get_current_week()))
        except Exception:
            live_week = None
    else:
        live_week = _current_week_from_schedule(
            season=season,
            schema=config.schema,
        )
        # Prefer a priced slate when the schedule week has no lines
        # yet (common early in a CFB week before odds publish).
        if live_week is not None and not _week_has_market_lines(
            season=season,
            week=live_week,
            schema=config.schema,
        ):
            lined = _latest_week_with_market_lines(
                season=season,
                schema=config.schema,
                at_or_before=live_week,
            )
            if lined is not None:
                live_week = lined

    if not available_weeks:
        return live_week

    if live_week is not None:
        if live_week in available_weeks:
            return live_week
        prior = [w for w in available_weeks if w <= live_week]
        if prior:
            return prior[-1]
        return available_weeks[0]

    return available_weeks[-1]


def _week_has_market_lines(
    *,
    season: int,
    week: int,
    schema: str,
) -> bool:
    try:
        with engine.connect() as connection:
            count = connection.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM {schema}.fact_game_market
                    WHERE season = :season
                      AND week = :week
                      AND (
                        spread IS NOT NULL
                        OR over_under IS NOT NULL
                      )
                    """
                ),
                {"season": int(season), "week": int(week)},
            ).scalar()
            return int(count or 0) > 0
    except Exception:
        return False


def _latest_week_with_market_lines(
    *,
    season: int,
    schema: str,
    at_or_before: int | None = None,
) -> int | None:
    clauses = [
        "season = :season",
        "(spread IS NOT NULL OR over_under IS NOT NULL)",
        "week IS NOT NULL",
    ]
    params: dict[str, Any] = {"season": int(season)}
    if at_or_before is not None:
        clauses.append("week <= :at_or_before")
        params["at_or_before"] = int(at_or_before)
    where = " AND ".join(clauses)
    try:
        with engine.connect() as connection:
            week = connection.execute(
                text(
                    f"""
                    SELECT MAX(week)
                    FROM {schema}.fact_game_market
                    WHERE {where}
                    """
                ),
                params,
            ).scalar()
            return int(week) if week is not None else None
    except Exception:
        return None


def _current_week_from_schedule(
    *,
    season: int,
    schema: str,
) -> int | None:
    """
    Week containing today, else the next upcoming week, else the
    most recent completed week on the schedule.
    """

    try:
        with engine.connect() as connection:
            upcoming = connection.execute(
                text(
                    f"""
                    SELECT week
                    FROM {schema}.dim_game
                    WHERE season = :season
                      AND week IS NOT NULL
                      AND game_date IS NOT NULL
                      AND game_date >= CURRENT_DATE
                    ORDER BY game_date ASC, week ASC
                    LIMIT 1
                    """
                ),
                {"season": int(season)},
            ).scalar()
            if upcoming is not None:
                return int(upcoming)

            containing = connection.execute(
                text(
                    f"""
                    SELECT week
                    FROM {schema}.dim_game
                    WHERE season = :season
                      AND week IS NOT NULL
                      AND game_date IS NOT NULL
                    GROUP BY week
                    HAVING MIN(game_date) <= CURRENT_DATE
                       AND MAX(game_date) >= CURRENT_DATE
                    ORDER BY week
                    LIMIT 1
                    """
                ),
                {"season": int(season)},
            ).scalar()
            if containing is not None:
                return int(containing)

            prior = connection.execute(
                text(
                    f"""
                    SELECT week
                    FROM {schema}.dim_game
                    WHERE season = :season
                      AND week IS NOT NULL
                      AND game_date IS NOT NULL
                      AND game_date < CURRENT_DATE
                    ORDER BY game_date DESC, week DESC
                    LIMIT 1
                    """
                ),
                {"season": int(season)},
            ).scalar()
            if prior is not None:
                return int(prior)
    except Exception:
        return None
    return None


def _load_events(
    *,
    season: int,
    week: int | None,
    event_id: str | None = None,
    sport_config: BettingSportConfig | None = None,
) -> list[dict[str, Any]]:
    config = sport_config or resolve_betting_sport("NFL")
    schema = config.schema
    params: dict[str, Any] = {"season": int(season)}

    if config.has_opening_lines:
        # CFB fact_game_market has opening_* but not line_moved_at.
        line_moved_expr = (
            "NULL::timestamp AS line_moved_at"
            if config.id == "CFB"
            else "m.line_moved_at"
        )
        opening_cols = f"""
          m.opening_spread,
          m.opening_over_under,
          m.opening_home_implied_total,
          m.opening_away_implied_total,
          m.opening_captured_at,
          {line_moved_expr},
        """
    else:
        opening_cols = """
          NULL::double precision AS opening_spread,
          NULL::double precision AS opening_over_under,
          NULL::double precision AS opening_home_implied_total,
          NULL::double precision AS opening_away_implied_total,
          NULL::timestamp AS opening_captured_at,
          NULL::timestamp AS line_moved_at,
        """

    # Schedule-first so upcoming weeks appear before lines land.
    # Markets are the latest row per game when present.
    clauses = ["g.season = :season"]
    if week is not None:
        clauses.append("g.week = :week")
        params["week"] = int(week)
    if event_id:
        clauses.append("g.game_id = :event_id")
        params["event_id"] = event_id
    where = " AND ".join(clauses)

    # CFB schedule includes FCS / non-FBS noise. Prefer FBS–FBS
    # matchups, and always keep any game that already has a line.
    sport_filter = ""
    if config.id == "CFB":
        sport_filter = """
          AND (
            m.game_id IS NOT NULL
            OR (
              LOWER(COALESCE(ht.subdivision, '')) = 'fbs'
              AND LOWER(COALESCE(at.subdivision, '')) = 'fbs'
            )
          )
        """

    sql = f"""
        SELECT DISTINCT ON (g.game_id)
          g.game_id AS event_id,
          g.season,
          g.week,
          COALESCE(m.season_type, g.season_type) AS season_type,
          m.spread,
          m.over_under,
          m.home_implied_total,
          m.away_implied_total,
          {opening_cols}
          m.timestamp AS market_timestamp,
          COALESCE(m.source, :default_source) AS source,
          g.game_date AS start_time,
          g.game_status AS status,
          g.home_score,
          g.away_score,
          ht.team_id AS home_team_id,
          ht.team_abbreviation AS home_team,
          ht.team_name AS home_team_name,
          ht.source_ids->>'espn_team_id' AS home_espn_team_id,
          at.team_id AS away_team_id,
          at.team_abbreviation AS away_team,
          at.team_name AS away_team_name,
          at.source_ids->>'espn_team_id' AS away_espn_team_id
        FROM {schema}.dim_game g
        LEFT JOIN {schema}.fact_game_market m
          ON m.game_id = g.game_id
        LEFT JOIN {schema}.dim_team ht
          ON ht.team_id = g.home_team_id
        LEFT JOIN {schema}.dim_team at
          ON at.team_id = g.away_team_id
        WHERE {where}
        {sport_filter}
        ORDER BY g.game_id, m.timestamp DESC NULLS LAST
    """
    params["default_source"] = config.source_label
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(sql),
                params,
            ).mappings()
            return [dict(row) for row in rows]
    except Exception:
        return []


def _load_recent_ppg(
    *,
    season: int,
    lookback: int = 4,
) -> dict[str, float]:
    """
    Deprecated PPG helper retained for tests/back-compat.

    Prefer ``load_team_strength_context`` for projections.
    """

    sql = f"""
        WITH scored AS (
          SELECT
            team_id,
            season,
            week,
            points,
            ROW_NUMBER() OVER (
              PARTITION BY team_id
              ORDER BY season DESC, week DESC
            ) AS rn
          FROM {FANTASY_SCHEMA}.fact_team_game
          WHERE season = :season
            AND points IS NOT NULL
        )
        SELECT
          team_id,
          AVG(points)::float AS ppg
        FROM scored
        WHERE rn <= :lookback
        GROUP BY team_id
    """
    out: dict[str, float] = {}
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(sql),
                {"season": int(season), "lookback": lookback},
            ).mappings()
            for row in rows:
                tid = str(row.get("team_id") or "").strip()
                ppg = num(row.get("ppg"))
                if tid and ppg is not None:
                    out[tid] = float(ppg)
    except Exception:
        return {}
    return out


def _enrich_event(
    raw: dict[str, Any],
    *,
    strength_context: dict[str, Any] | None = None,
    tendency_context: dict[str, Any] | None = None,
    recent_ppg: dict[str, float] | None = None,
    player_context: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    probability_calibration: dict[str, Any] | None = None,
    probability_calibrations: dict[str, dict[str, Any]] | None = None,
    edge_confidence: dict[str, Any] | None = None,
    challenger_model: dict[str, Any] | None = None,
    residual_model: str = "champion",
    score_distribution_model: dict[str, Any] | None = None,
    probability_engine: str = "logistic",
    rest_by_game: dict[str, tuple[float, float]] | None = None,
    qualification_thresholds: dict[str, Any] | None = None,
    sport_config: BettingSportConfig | None = None,
) -> dict[str, Any]:
    active_sport = sport_config or resolve_betting_sport("NFL")
    home = str(raw.get("home_team") or "").upper()
    away = str(raw.get("away_team") or "").upper()
    event_id = str(raw.get("event_id") or "")
    market_spread_raw = num(raw.get("spread"))
    applied_residual = _resolve_residual_model(residual_model)
    applied_prob_engine = _resolve_probability_engine(
        probability_engine
    )
    rest_home, rest_away = (7.0, 7.0)
    if rest_by_game and event_id in rest_by_game:
        rest_home, rest_away = rest_by_game[event_id]
    if probability_calibrations is None and probability_calibration:
        probability_calibrations = {"all": probability_calibration}
    market_total = num(raw.get("over_under"))
    market_home = num(raw.get("home_implied_total"))
    market_away = num(raw.get("away_implied_total"))

    if (
        market_home is None
        and market_total is not None
        and market_spread_raw is not None
    ):
        # Derive implied from total/spread when missing.
        market_home = (market_total - market_spread_raw) / 2.0
        market_away = (market_total + market_spread_raw) / 2.0

    # Home-team spread convention: negative = home favored.
    # Prefer implied scores when present — nflverse schedule
    # spread_line sign can disagree with implied totals.
    if market_home is not None and market_away is not None:
        market_spread = round(float(market_away) - float(market_home), 1)
    else:
        market_spread = market_spread_raw

    home_team_id = str(raw.get("home_team_id") or "")
    away_team_id = str(raw.get("away_team_id") or "")

    # Build market movement early so injury edge can residualize
    # against lines that already moved toward the injury.
    opening_home_early = num(raw.get("opening_home_implied_total"))
    opening_away_early = num(raw.get("opening_away_implied_total"))
    opening_spread_raw_early = num(raw.get("opening_spread"))
    opening_total_early = num(raw.get("opening_over_under"))
    if opening_home_early is not None and opening_away_early is not None:
        opening_spread_early = round(
            float(opening_away_early) - float(opening_home_early), 1
        )
    elif opening_spread_raw_early is not None:
        opening_spread_early = round(-float(opening_spread_raw_early), 1)
    else:
        opening_spread_early = None
    market_movement_early = build_market_movement(
        opening_spread=opening_spread_early,
        current_spread=market_spread,
        opening_total=opening_total_early,
        current_total=market_total,
    )

    home_injury = refine_injury_with_market_move(
        team_injury_context(player_context, home_team_id),
        spread_move=num(market_movement_early.get("spread_move")),
        total_move=num(market_movement_early.get("total_move")),
        is_home=True,
    )
    away_injury = refine_injury_with_market_move(
        team_injury_context(player_context, away_team_id),
        spread_move=num(market_movement_early.get("spread_move")),
        total_move=num(market_movement_early.get("total_move")),
        is_home=False,
    )
    home_adj, away_adj = combined_score_adjustments(
        home_injury=home_injury,
        away_injury=away_injury,
    )
    injury_sigma = combined_impact_sigma(
        home_injury=home_injury,
        away_injury=away_injury,
    )

    locked = _load_projection_snapshot(event_id)
    locked_home = num((locked or {}).get("projected_home_score"))
    locked_away = num((locked or {}).get("projected_away_score"))
    # Only frozen snapshots pin the UI. Unfrozen first-publish
    # rows are kept for settlement/CLV bet_line but open games
    # must recompute so model upgrades (residuals, injuries,
    # disagreement, etc.) actually show on refresh.
    using_locked = bool(
        locked
        and locked.get("frozen")
        and locked_home is not None
        and locked_away is not None
    )
    strength_detail: dict[str, Any] = {"available": False}
    blend_meta: dict[str, Any] = {}

    if using_locked:
        # Settlement lock — published pregame projection stays fixed.
        model_home = locked_home
        model_away = locked_away
        model_total = num(locked.get("projected_total"))
        if model_total is None:
            model_total = round(model_home + model_away, 1)
        model_spread = num(locked.get("model_spread"))
        if model_spread is None:
            model_spread = round(model_away - model_home, 1)
    else:
        model_home, model_away, strength_detail = _model_scores(
            market_home=market_home,
            market_away=market_away,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            strength_context=strength_context,
            tendency_context=tendency_context,
            recent_ppg=recent_ppg,
            home_injury_adj=home_adj,
            away_injury_adj=away_adj,
            calibration=calibration,
        )
        model_total = (
            round(model_home + model_away, 1)
            if model_home is not None and model_away is not None
            else None
        )
        model_spread = (
            round(model_away - model_home, 1)
            if model_home is not None and model_away is not None
            else None
        )
        blend_meta = dict(strength_detail.get("blend") or {})

    disagreement = build_model_disagreement(
        market_home=market_home,
        market_away=market_away,
        market_spread=market_spread,
        market_total=market_total,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        strength_context=strength_context,
        recent_ppg=recent_ppg,
        home_injury_adj=home_adj,
        away_injury_adj=away_adj,
        strength_home=strength_detail.get("strength_home"),
        strength_away=strength_detail.get("strength_away"),
        strength_detail=strength_detail,
    )

    game_scripts = project_game_scripts(
        projected_home=model_home,
        projected_away=model_away,
        projected_total=model_total,
        market_total=market_total,
        market_spread=market_spread,
        home_team=home,
        away_team=away,
    )

    injury_notes = []
    for note in away_injury.get("injuries") or []:
        injury_notes.append({**note, "team": away})
    for note in home_injury.get("injuries") or []:
        injury_notes.append({**note, "team": home})
    model_drivers = [
        "InsightPilot projection = market baseline + model "
        "residual (where the market is likely wrong)."
    ]
    blend_meta = strength_detail.get("blend") or blend_meta or {}
    residual_meta = strength_detail.get("residuals") or {}
    if residual_meta.get("residual_home") is not None:
        model_drivers.append(
            f"Residuals — home {float(residual_meta['residual_home']):+0.1f}, "
            f"away {float(residual_meta['residual_away']):+0.1f} "
            f"(shrink {float(residual_meta.get('shrink') or 0):.0%}, "
            f"{residual_meta.get('confidence') or 'Low'} confidence)."
        )
    elif blend_meta:
        model_drivers.append(
            f"Blend confidence {blend_meta.get('confidence')} — "
            f"market {float(blend_meta.get('market_weight') or 0):.0%} / "
            f"model {float(blend_meta.get('model_weight') or 0):.0%} "
            f"({blend_meta.get('policy_source') or 'prior'})."
        )
    spread_ens = (disagreement or {}).get("spread") or {}
    if spread_ens.get("n_models"):
        model_drivers.append(
            f"Ensemble spread mean {spread_ens.get('projection_mean')} "
            f"(σ {spread_ens.get('projection_stddev')}, "
            f"agreement {spread_ens.get('model_agreement')} · "
            f"{spread_ens.get('n_models')} models)."
        )
    if strength_detail.get("available"):
        home_m = strength_detail.get("home_matchup")
        away_m = strength_detail.get("away_matchup")
        model_drivers.append(
            f"Matchup strength — home {home_m:+.2f}, "
            f"away {away_m:+.2f} "
            "(offense efficiency minus opponent defense)."
        )
    tendency_sit = (strength_detail.get("opponent_tendency_sit") or {})
    if tendency_sit.get("applied"):
        model_drivers.append(
            "Opponent tendency — "
            f"home {float(tendency_sit.get('home_pts') or 0):+0.1f}, "
            f"away {float(tendency_sit.get('away_pts') or 0):+0.1f} "
            "(gated market residual vs opponent tier)."
        )
    if using_locked:
        frozen = bool((locked or {}).get("frozen"))
        model_drivers.append(
            "Using locked pregame projection snapshot"
            + (" (frozen for settlement)." if frozen else ".")
        )
    model_drivers.extend(away_injury.get("drivers") or [])
    model_drivers.extend(home_injury.get("drivers") or [])
    if not using_locked and not (home_adj or away_adj):
        model_drivers.append(
            "No material starter injury adjustments applied for this slate week."
        )

    residual_home = residual_meta.get("total_residual_home")
    residual_away = residual_meta.get("total_residual_away")
    if using_locked:
        residual_home = num((locked or {}).get("residual_home")) or residual_home
        residual_away = num((locked or {}).get("residual_away")) or residual_away

    opening_home = num(raw.get("opening_home_implied_total"))
    opening_away = num(raw.get("opening_away_implied_total"))
    opening_spread_raw = num(raw.get("opening_spread"))
    opening_total = num(raw.get("opening_over_under"))
    # Do not copy current total into opening when opening is missing.

    # Match event spread convention (away − home).
    if opening_home is not None and opening_away is not None:
        opening_spread = round(
            float(opening_away) - float(opening_home),
            1,
        )
    elif opening_spread_raw is not None:
        # nflverse spread_line: positive = home favored → negate.
        opening_spread = round(-float(opening_spread_raw), 1)
    else:
        opening_spread = None

    market_movement = build_market_movement(
        opening_spread=opening_spread,
        current_spread=market_spread,
        opening_total=opening_total,
        current_total=market_total,
        opening_captured_at=_iso(raw.get("opening_captured_at")),
        line_moved_at=_iso(raw.get("line_moved_at")),
        residual_home=residual_home,
        residual_away=residual_away,
    )
    vs_model = market_movement.get("vs_model") or {}
    if market_movement.get("moved"):
        bits = []
        if market_movement.get("spread_move") is not None:
            bits.append(f"spread {float(market_movement['spread_move']):+0.1f}")
        if market_movement.get("total_move") is not None:
            bits.append(f"total {float(market_movement['total_move']):+0.1f}")
        model_drivers.append(
            "Market move since open — " + ", ".join(bits) + "."
        )
        if vs_model.get("explanation"):
            model_drivers.append(str(vs_model["explanation"]))

    # Shadow challenger residual (optional apply). Champion stays default.
    if not using_locked:
        prev_applied = applied_residual
        model_home, model_away, model_total, model_spread, strength_detail = (
            _merge_challenger_into_scores(
                model_home=model_home,
                model_away=model_away,
                model_total=model_total,
                model_spread=model_spread,
                strength_detail=strength_detail,
                market_home=market_home,
                market_away=market_away,
                market_spread=market_spread,
                market_total=market_total,
                market_movement=market_movement,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                strength_context=strength_context,
                tendency_context=tendency_context,
                home_injury=home_injury,
                away_injury=away_injury,
                home_injury_adj=home_adj,
                away_injury_adj=away_adj,
                disagreement=disagreement,
                week=_as_int(raw.get("week")),
                calibration=calibration,
                challenger_model=challenger_model,
                residual_model=applied_residual,
                home_rest_days=rest_home,
                away_rest_days=rest_away,
            )
        )
        residual_meta = strength_detail.get("residuals") or residual_meta
        residual_home = residual_meta.get("total_residual_home")
        residual_away = residual_meta.get("total_residual_away")
        blend_meta = strength_detail.get("blend") or blend_meta
        compare = (residual_meta.get("compare") or {})
        if compare.get("challenger"):
            model_drivers.append(
                "Challenger residual model attached for comparison "
                f"(applied={compare.get('applied')})."
            )
        if prev_applied == "challenger":
            game_scripts = project_game_scripts(
                projected_home=model_home,
                projected_away=model_away,
                projected_total=model_total,
                market_total=market_total,
                market_spread=market_spread,
                home_team=home,
                away_team=away,
            )

    # Bivariate score simulation (shadow; optional apply in markets).
    score_distribution = empty_score_distribution()
    if model_home is not None and model_away is not None:
        home_prof = (strength_detail.get("home_profile") or {})
        away_prof = (strength_detail.get("away_profile") or {})
        home_off = home_prof.get("offense") or {}
        away_off = away_prof.get("offense") or {}
        disagree = disagreement or {}
        dist_features = build_distribution_features(
            week=_as_int(raw.get("week")),
            min_games=float(
                min(
                    int(strength_detail.get("home_games") or 0),
                    int(strength_detail.get("away_games") or 0),
                )
                if strength_detail.get("available")
                else 0
            ),
            pace_z=num(strength_detail.get("pace_z")),
            home_turnover_rate=num(home_off.get("turnover_rate")),
            away_turnover_rate=num(away_off.get("turnover_rate")),
            disagreement_spread_sd=num(
                ((disagree.get("spread") or {}).get("stddev"))
            ),
            disagreement_total_sd=num(
                ((disagree.get("total") or {}).get("stddev"))
            ),
            missing_strength=(
                0.0 if strength_detail.get("available") else 1.0
            ),
        )
        if injury_sigma:
            # Fold injury uncertainty into scale drivers.
            dist_features["disagreement"] = min(
                1.0,
                float(dist_features.get("disagreement") or 0.0)
                + min(1.0, float(injury_sigma) / 6.0),
            )
            dist_features["injury_sigma"] = float(injury_sigma)
        score_distribution = simulate_game_scores(
            mean_home=float(model_home),
            mean_away=float(model_away),
            model=(
                score_distribution_model
                or prior_score_distribution_model()
            ),
            features=dist_features,
            market_spread=market_spread,
            market_total=market_total,
            event_id=event_id,
        )
        score_distribution.pop("_probs", None)

    label = f"{away} @ {home}" if away and home else event_id
    # NFL: fact_game_market.timestamp carries gameday + gametime.
    # CFB: that column is odds-capture time (scrape), so prefer
    # dim_game.game_date (aliased as start_time) for the card date.
    if active_sport.id == "CFB":
        kickoff = raw.get("start_time") or raw.get("market_timestamp")
    else:
        kickoff = raw.get("market_timestamp") or raw.get("start_time")
    game_forecast = _game_forecast_for_event(
        event_id=event_id,
        raw=raw,
        home=home,
        away=away,
        model_home=model_home,
        model_away=model_away,
        using_locked=using_locked,
        locked=locked,
        strength_detail=strength_detail,
        score_distribution=score_distribution,
        game_scripts=game_scripts,
        timestamp=_iso(kickoff),
    )
    event = {
        "event_id": event_id,
        "sport": active_sport.id,
        "league": active_sport.league,
        "season": raw.get("season"),
        "week": raw.get("week"),
        "start_time": _iso(kickoff),
        "status": raw.get("status") or "scheduled",
        "home_team": home,
        "away_team": away,
        "home_team_name": raw.get("home_team_name"),
        "away_team_name": raw.get("away_team_name"),
        "home_team_id": raw.get("home_team_id"),
        "away_team_id": raw.get("away_team_id"),
        "home_logo_url": _sport_team_logo_url(
            active_sport.id,
            raw.get("home_espn_team_id"),
            abbreviation=home,
        ),
        "away_logo_url": _sport_team_logo_url(
            active_sport.id,
            raw.get("away_espn_team_id"),
            abbreviation=away,
        ),
        "label": label,
        "market_spread": market_spread,
        "market_total": market_total,
        "opening_spread": market_movement.get("opening_spread"),
        "current_spread": market_movement.get("current_spread"),
        "opening_total": market_movement.get("opening_total"),
        "current_total": market_movement.get("current_total"),
        "opening_moneyline": market_movement.get("opening_moneyline"),
        "current_moneyline": market_movement.get("current_moneyline"),
        "spread_move": market_movement.get("spread_move"),
        "total_move": market_movement.get("total_move"),
        "moneyline_move": market_movement.get("moneyline_move"),
        "market_movement": market_movement,
        "market_home_score": (
            round(market_home, 1) if market_home is not None else None
        ),
        "market_away_score": (
            round(market_away, 1) if market_away is not None else None
        ),
        "projected_home_score": model_home,
        "projected_away_score": model_away,
        "projected_total": model_total,
        "game_forecast": game_forecast,
        "model_spread": model_spread,
        "residual_home": residual_home,
        "residual_away": residual_away,
        "team_strength": strength_detail if strength_detail.get("available") else None,
        "projection_blend": blend_meta or None,
        "residuals": residual_meta or None,
        "model_disagreement": disagreement,
        "game_scripts": game_scripts,
        "score_distribution": score_distribution,
        "probability_engine": applied_prob_engine,
        "injury_adjustment_home": home_adj or None,
        "injury_adjustment_away": away_adj or None,
        "injury_score_impact_home": (
            float(home_injury.get("score_adjustment_pts") or 0.0)
            + float(away_injury.get("score_opponent_adjustment_pts") or 0.0)
        ) or None,
        "injury_score_impact_away": (
            float(away_injury.get("score_adjustment_pts") or 0.0)
            + float(home_injury.get("score_opponent_adjustment_pts") or 0.0)
        ) or None,
        "injury_impact_sigma": injury_sigma or None,
        "injury_context": {
            "home": {
                "edge": home_injury.get("adjustment_pts"),
                "score": home_injury.get("score_adjustment_pts"),
                "sigma": home_injury.get("impact_sigma"),
            },
            "away": {
                "edge": away_injury.get("adjustment_pts"),
                "score": away_injury.get("score_adjustment_pts"),
                "sigma": away_injury.get("impact_sigma"),
            },
            "model": "predictive_injury_v1",
        },
        "rest_days": {"home": rest_home, "away": rest_away},
        "injuries": injury_notes,
        "model_drivers": model_drivers,
        "opponent_tendency": event_tendency_payload(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            tendency_context=tendency_context,
            situational_meta=tendency_sit
            or (strength_detail.get("opponent_tendency_sit") or {}),
        ),
        "injury_report_week": (
            player_context.get("week") if player_context else None
        ),
        "market_timestamp": _iso(raw.get("market_timestamp")),
        "source": raw.get("source"),
        "home_score": raw.get("home_score"),
        "away_score": raw.get("away_score"),
    }

    markets = _build_markets(
        event,
        probability_calibration=probability_calibration,
        probability_calibrations=probability_calibrations,
        edge_confidence=edge_confidence,
        probability_engine=applied_prob_engine,
        qualification_thresholds=qualification_thresholds,
    )
    signals = _build_signals(
        event, markets, edge_confidence=edge_confidence
    )
    event["primary_signal"] = signals[0] if signals else None
    event["market_ids"] = [m["market_id"] for m in markets]
    event["probability_calibration"] = (
        {
            "active": bool(
                (probability_calibration or {}).get("active")
            ),
            "method": (probability_calibration or {}).get("method"),
            "sample_size": (probability_calibration or {}).get(
                "sample_size"
            ),
        }
        if probability_calibration
        else None
    )
    event["edge_confidence"] = (
        {
            "active": bool((edge_confidence or {}).get("active")),
            "method": (edge_confidence or {}).get("method"),
            "sample_size": (edge_confidence or {}).get("sample_size"),
            "high_min": (edge_confidence or {}).get("high_min"),
            "moderate_min": (edge_confidence or {}).get("moderate_min"),
            "by_market": (edge_confidence or {}).get("by_market"),
            "note": (edge_confidence or {}).get("note"),
            "market_note": (edge_confidence or {}).get("market_note"),
        }
        if edge_confidence
        else None
    )
    return {
        "event": event,
        "markets": markets,
        "signals": signals,
    }


def _game_forecast_for_event(
    *,
    event_id: str,
    raw: dict[str, Any],
    home: str | None,
    away: str | None,
    model_home: float | None,
    model_away: float | None,
    using_locked: bool,
    locked: dict[str, Any] | None,
    strength_detail: dict[str, Any] | None,
    score_distribution: dict[str, Any] | None,
    game_scripts: list[dict[str, Any]] | None,
    timestamp: str | None,
) -> dict[str, Any] | None:
    """Attach the shared scoring environment for this game."""

    from app.analysis.insights.game_forecast import (
        build_game_forecast,
        forecast_from_snapshot_payload,
    )

    if using_locked and isinstance(locked, dict):
        stored = forecast_from_snapshot_payload(locked.get("payload"))
        if stored:
            return stored
    if model_home is None or model_away is None:
        return None
    pace_z = None
    if isinstance(strength_detail, dict):
        pace_z = num(strength_detail.get("pace_z"))
    return build_game_forecast(
        event_id=event_id,
        season=_as_int(raw.get("season")),
        week=_as_int(raw.get("week")),
        home_team=home,
        away_team=away,
        projected_home_points=float(model_home),
        projected_away_points=float(model_away),
        source="insightpilot_game_model",
        timestamp=timestamp,
        pace_z=pace_z,
        score_distribution_preview=score_distribution,
        game_scripts_preview=game_scripts,
    )


def _merge_challenger_into_scores(
    *,
    model_home: float | None,
    model_away: float | None,
    model_total: float | None,
    model_spread: float | None,
    strength_detail: dict[str, Any],
    market_home: float | None,
    market_away: float | None,
    market_spread: float | None,
    market_total: float | None,
    market_movement: dict[str, Any] | None,
    home_team_id: str | None,
    away_team_id: str | None,
    strength_context: dict[str, Any] | None,
    tendency_context: dict[str, Any] | None = None,
    home_injury: dict[str, Any] | None,
    away_injury: dict[str, Any] | None,
    home_injury_adj: float,
    away_injury_adj: float,
    disagreement: dict[str, Any] | None,
    week: int | None,
    calibration: dict[str, Any] | None,
    challenger_model: dict[str, Any] | None,
    residual_model: str,
    home_rest_days: float | None = None,
    away_rest_days: float | None = None,
) -> tuple[
    float | None,
    float | None,
    float | None,
    float | None,
    dict[str, Any],
]:
    """Attach challenger shadow; optionally apply it instead of champion."""

    detail = dict(strength_detail or {})
    residual_meta = dict(detail.get("residuals") or {})
    move = market_movement or {}
    feature_payload = build_residual_features(
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        strength_context=strength_context,
        market_home=market_home,
        market_away=market_away,
        market_spread=market_spread,
        market_total=market_total,
        spread_move=num(move.get("spread_move")),
        total_move=num(move.get("total_move")),
        week=week,
        home_injury_adj=home_injury_adj,
        away_injury_adj=away_injury_adj,
        home_rest_days=home_rest_days,
        away_rest_days=away_rest_days,
        home_injury=home_injury,
        away_injury=away_injury,
        disagreement=disagreement,
        tendency_context=tendency_context,
    )
    chall_pred = predict_challenger_residuals(
        feature_payload=feature_payload,
        model=challenger_model or prior_challenger_model(),
        market_home=market_home,
        market_away=market_away,
    )
    champion_view = {
        "residual_home": residual_meta.get("residual_home"),
        "residual_away": residual_meta.get("residual_away"),
        "shrink": residual_meta.get("shrink"),
        "projection_confidence": residual_meta.get("confidence"),
        "policy_source": (detail.get("blend") or {}).get("policy_source"),
    }
    compare = compare_champion_challenger(
        champion=champion_view,
        challenger=chall_pred,
        applied=residual_model,
    )
    residual_meta["compare"] = compare
    residual_meta["feature_snapshot"] = {
        "available": feature_payload.get("available"),
        "feature_names": feature_payload.get("feature_names"),
        "features": feature_payload.get("features"),
        "vector": feature_payload.get("vector"),
    }
    residual_meta["challenger"] = {
        "residual_home": chall_pred.get("residual_home"),
        "residual_away": chall_pred.get("residual_away"),
        "mu_home": chall_pred.get("mu_home"),
        "mu_away": chall_pred.get("mu_away"),
        "sigma": chall_pred.get("sigma"),
        "shrink": chall_pred.get("shrink"),
        "model_active": chall_pred.get("model_active"),
        "model_version": chall_pred.get("model_version"),
        "method": chall_pred.get("method"),
    }

    out_home = model_home
    out_away = model_away
    out_total = model_total
    out_spread = model_spread

    if residual_model == "challenger":
        chall_payload = challenger_to_residual_payload(chall_pred)
        provisional_h, provisional_a, _ = apply_score_residuals(
            chall_payload
        )
        cal_home, cal_away = calibration_score_deltas(
            projected_home=provisional_h,
            projected_away=provisional_a,
            feedback=calibration,
        )
        # Injury already in challenger features — only add calibration
        # here to avoid double-counting personnel impact.
        chall_payload = add_situational_residuals(
            chall_payload,
            home_adjustment=cal_home,
            away_adjustment=cal_away,
        )
        out_home, out_away, apply_meta = apply_score_residuals(
            chall_payload
        )
        residual_meta.update(
            {
                "raw_residual_home": chall_payload.get("raw_residual_home"),
                "raw_residual_away": chall_payload.get("raw_residual_away"),
                "residual_home": chall_payload.get("residual_home"),
                "residual_away": chall_payload.get("residual_away"),
                "situational_residual_home": chall_payload.get(
                    "situational_residual_home"
                ),
                "situational_residual_away": chall_payload.get(
                    "situational_residual_away"
                ),
                "total_residual_home": apply_meta.get(
                    "total_residual_home"
                ),
                "total_residual_away": apply_meta.get(
                    "total_residual_away"
                ),
                "shrink": chall_payload.get("shrink"),
                "confidence": chall_payload.get("projection_confidence"),
                "architecture": "market + residual",
                "applied_model": "challenger",
            }
        )
        detail["blend"] = {
            "confidence": chall_payload.get("projection_confidence"),
            "market_weight": chall_payload.get("market_weight"),
            "model_weight": chall_payload.get("model_weight"),
            "policy_source": chall_payload.get("policy_source"),
            "policy_learned": chall_payload.get("policy_learned"),
            "mode": apply_meta.get("mode"),
            "formula": chall_payload.get("formula"),
            "home_applied_delta": apply_meta.get("home_applied_delta"),
            "away_applied_delta": apply_meta.get("away_applied_delta"),
        }
        detail["projection_confidence"] = chall_payload.get(
            "projection_confidence"
        )
        out_total = (
            round(out_home + out_away, 1)
            if out_home is not None and out_away is not None
            else None
        )
        out_spread = (
            round(out_away - out_home, 1)
            if out_home is not None and out_away is not None
            else None
        )
    else:
        residual_meta["applied_model"] = "champion"

    detail["residuals"] = residual_meta
    return out_home, out_away, out_total, out_spread, detail


def _model_scores(
    *,
    market_home: float | None,
    market_away: float | None,
    home_team_id: str | None = None,
    away_team_id: str | None = None,
    strength_context: dict[str, Any] | None = None,
    tendency_context: dict[str, Any] | None = None,
    recent_ppg: dict[str, float] | None = None,
    home_injury_adj: float = 0.0,
    away_injury_adj: float = 0.0,
    calibration: dict[str, Any] | None = None,
) -> tuple[float | None, float | None, dict[str, Any]]:
    """
    Market + residual projection (champion path).

    1. Predict where the market is wrong (team-strength residual)
    2. Shrink residual by projection confidence
    3. Add situational residuals (injuries, calibration, tendency)
    4. final = market + total residual
    """

    residual_model = predict_score_residuals(
        market_home=market_home,
        market_away=market_away,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        strength_context=strength_context,
        recent_ppg=recent_ppg,
    )
    detail = dict(residual_model.get("strength") or {"available": False})

    # Situational residuals: calibration expressed as deltas vs the
    # market-anchored strength projection, plus injury adjustments
    # and gated opponent-tendency points (NFL only).
    provisional_home, provisional_away, _ = apply_score_residuals(
        residual_model
    )
    cal_home, cal_away = calibration_score_deltas(
        projected_home=provisional_home,
        projected_away=provisional_away,
        feedback=calibration,
    )
    tend_home, tend_away, tend_meta = tendency_situational_adjustments(
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        strength_context=strength_context,
        tendency_context=tendency_context,
        shrink=float(residual_model.get("shrink") or 0.0) or None,
    )
    residual_model = add_situational_residuals(
        residual_model,
        home_adjustment=(
            float(home_injury_adj or 0.0) + cal_home + tend_home
        ),
        away_adjustment=(
            float(away_injury_adj or 0.0) + cal_away + tend_away
        ),
    )
    home, away, apply_meta = apply_score_residuals(residual_model)

    blend_meta = {
        "confidence": apply_meta.get("confidence"),
        "market_weight": apply_meta.get("market_weight"),
        "model_weight": apply_meta.get("model_weight"),
        "policy_source": apply_meta.get("policy_source"),
        "policy_learned": apply_meta.get("policy_learned"),
        "mode": apply_meta.get("mode"),
        "formula": apply_meta.get("formula"),
        "home_applied_delta": apply_meta.get("home_applied_delta"),
        "away_applied_delta": apply_meta.get("away_applied_delta"),
    }
    detail = {
        **detail,
        "available": bool(
            detail.get("available") or residual_model.get("available")
        ),
        "projection_confidence": residual_model.get(
            "projection_confidence"
        ),
        "blend": blend_meta,
        "opponent_tendency_sit": tend_meta,
        "residuals": {
            "raw_residual_home": residual_model.get("raw_residual_home"),
            "raw_residual_away": residual_model.get("raw_residual_away"),
            "residual_home": residual_model.get("residual_home"),
            "residual_away": residual_model.get("residual_away"),
            "situational_residual_home": residual_model.get(
                "situational_residual_home"
            ),
            "situational_residual_away": residual_model.get(
                "situational_residual_away"
            ),
            "total_residual_home": apply_meta.get("total_residual_home"),
            "total_residual_away": apply_meta.get("total_residual_away"),
            "shrink": residual_model.get("shrink"),
            "confidence": residual_model.get("projection_confidence"),
            "architecture": "market + residual",
            "applied_model": "champion",
        },
        "strength_home": residual_model.get("strength_home"),
        "strength_away": residual_model.get("strength_away"),
        "market_home": market_home,
        "market_away": market_away,
    }
    return home, away, detail


def _build_markets(
    event: dict[str, Any],
    *,
    probability_calibration: dict[str, Any] | None = None,
    probability_calibrations: dict[str, dict[str, Any]] | None = None,
    edge_confidence: dict[str, Any] | None = None,
    probability_engine: str = "logistic",
    qualification_thresholds: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    event_id = event["event_id"]
    home = event.get("home_team")
    away = event.get("away_team")
    start = event.get("start_time")
    label = event.get("label")
    calibrations = probability_calibrations
    if calibrations is None and probability_calibration:
        calibrations = {"all": probability_calibration}
    conf_thresholds = edge_confidence
    applied_engine = _resolve_probability_engine(probability_engine)
    simulation = event.get("score_distribution")
    qual_thresholds = (
        qualification_thresholds or prior_qualification_thresholds()
    )

    market_spread = num(event.get("market_spread"))
    model_spread = num(event.get("model_spread"))
    market_total = num(event.get("market_total"))
    model_total = num(event.get("projected_total"))
    opening_spread = num(event.get("opening_spread"))
    opening_total = num(event.get("opening_total"))
    opening_ml = event.get("opening_moneyline")
    current_ml = event.get("current_moneyline")
    move = event.get("market_movement") or {}
    sport = str(event.get("sport") or _SPORT).upper()
    # No chalk-forcing deadband. With market-anchored residuals,
    # near-zero deltas are common; forcing the market favorite there
    # made slates pile onto giving points / favorites.
    spread_deadband = 0.0

    if market_spread is not None:
        # Home-team spread line (nflverse convention).
        selection = (
            f"{home} {market_spread:+g}"
            if home
            else f"Home {market_spread:+g}"
        )
        cover_logistic = spread_to_cover_probability(
            model_spread,
            market_spread,
        )
        cover_p = cover_probability_from_engine(
            engine=applied_engine,
            model_spread=model_spread,
            market_spread=market_spread,
            simulation=simulation,
        )
        event.setdefault("probability_compare", {})["spread"] = {
            "logistic": cover_logistic,
            "simulation": (
                ((simulation or {}).get("cover_at_line") or {}).get(
                    "home_cover"
                )
            ),
            "applied": applied_engine,
        }
        # No two-sided ATS book quotes in Phase 1 — market_p unavailable.
        # reference_probability=0.5 is diagnostic only (not a sportsbook).
        reference_p = REFERENCE_PROBABILITY
        market_p = None
        no_vig_market_p = None
        market_p_source = "unavailable"
        # Favorable side: home cover >= 50%, unless disagreement is
        # inside the deadband — then stay with the market favorite.
        spread_delta = (
            float(model_spread) - float(market_spread)
            if model_spread is not None
            else None
        )
        if cover_p is None:
            side_is_home = (
                float(market_spread) <= 0.0
                if market_spread is not None
                else True
            )
        elif (
            spread_deadband > 0
            and spread_delta is not None
            and abs(spread_delta) < spread_deadband
        ):
            side_is_home = float(market_spread) <= 0.0
        else:
            side_is_home = cover_p >= 0.5
        raw_model_p = cover_p if side_is_home else (
            (1.0 - cover_p) if cover_p is not None else None
        )
        cal = calibrate_market_probability(
            raw_model_p,
            model=_calibration_for_market(calibrations, "spread"),
        )
        model_p = cal["model_probability"]
        if not side_is_home and away:
            selection = (
                f"{away} {-market_spread:+g}"
            )
            # Away spread is opposite of home line.
        edge_points = (
            round(float(model_spread) - float(market_spread), 1)
            if model_spread is not None
            else None
        )
        ref_edge_prob = reference_edge_probability(model_p)
        mkt_edge_prob = market_edge_probability(model_p, market_p)
        # Operational qualification still uses reference edge until
        # real two-way ATS prices exist (thresholds unchanged).
        edge_prob = (
            mkt_edge_prob if mkt_edge_prob is not None else ref_edge_prob
        )
        edge_basis = (
            "vig_adjusted_market"
            if mkt_edge_prob is not None
            else "reference_coin_flip"
        )
        fair = implied_prob_to_american(model_p)
        push_p = None
        cover_block = (simulation or {}).get("cover_at_line") or {}
        if cover_block.get("push") is not None:
            push_p = float(cover_block["push"])
        # Assumed-juice EV at −110 is labeled; not price-based book EV.
        assumed_ev = expected_value_american(
            model_p, _DEFAULT_PRICE, p_push=push_p or 0.0
        )
        ev = None
        ev_basis = "unavailable"
        spread_agreement = (
            ((event.get("model_disagreement") or {}).get("spread") or {})
            .get("model_agreement")
        )
        confidence = confidence_from_edge(
            edge_points=edge_points,
            edge_probability=(
                (float(edge_prob) / 100.0)
                if edge_prob is not None
                else None
            ),
            model_coverage=model_spread is not None,
            thresholds=conf_thresholds,
            market_type="spread",
            model_agreement=spread_agreement,
        )
        markets.append(
            _market_row(
                market_id=f"{event_id}:spread",
                event_id=event_id,
                event_label=label,
                start_time=start,
                market_type="spread",
                selection=selection,
                line=market_spread if side_is_home else (
                    -market_spread if market_spread is not None else None
                ),
                price=_DEFAULT_PRICE,
                model_projection=model_spread,
                market_projection=market_spread,
                model_probability=model_p,
                raw_model_probability=cal.get("raw_model_probability"),
                probability_calibrated=bool(cal.get("calibrated")),
                probability_calibration_method=cal.get("method"),
                event=event,
                market_probability=market_p,
                no_vig_market_probability=no_vig_market_p,
                reference_probability=reference_p,
                market_probability_source=market_p_source,
                market_edge_probability=mkt_edge_prob,
                reference_edge_probability=ref_edge_prob,
                edge_probability_basis=edge_basis,
                model_fair_price=fair,
                edge=edge_points,
                edge_probability=edge_prob,
                expected_value=assumed_ev,
                expected_value_basis="assumed_minus_110",
                price_expected_value=ev,
                push_probability=push_p,
                confidence=confidence,
                model_agreement=spread_agreement,
                classification_thresholds=qual_thresholds,
                home_team=home,
                away_team=away,
                opening_line=(
                    opening_spread
                    if side_is_home
                    else (
                        -opening_spread
                        if opening_spread is not None
                        else None
                    )
                ),
                line_move=move.get("spread_move"),
                opportunity=_spread_opportunity(
                    home_team=home,
                    away_team=away,
                    market_spread=market_spread,
                    model_spread=model_spread,
                    side_is_home=side_is_home,
                    edge_probability=edge_prob,
                    projected_home=num(event.get("projected_home_score")),
                    projected_away=num(event.get("projected_away_score")),
                ),
            )
        )

    if market_total is not None:
        over_logistic = total_to_over_probability(
            model_total,
            market_total,
        )
        over_p = over_probability_from_engine(
            engine=applied_engine,
            model_total=model_total,
            market_total=market_total,
            simulation=simulation,
        )
        event.setdefault("probability_compare", {})["total"] = {
            "logistic": over_logistic,
            "simulation": (
                ((simulation or {}).get("over_at_line") or {}).get(
                    "over"
                )
            ),
            "applied": applied_engine,
        }
        reference_p = REFERENCE_PROBABILITY
        market_p = None
        no_vig_market_p = None
        market_p_source = "unavailable"
        # >= so exact market-tied totals do not become a 100% Under slate.
        side_over = over_p is not None and over_p >= 0.5
        raw_model_p = over_p if side_over else (
            (1.0 - over_p) if over_p is not None else None
        )
        cal = calibrate_market_probability(
            raw_model_p,
            model=_calibration_for_market(calibrations, "total"),
        )
        model_p = cal["model_probability"]
        selection = (
            f"Over {market_total:g}"
            if side_over
            else f"Under {market_total:g}"
        )
        edge_points = (
            round(float(model_total) - float(market_total), 1)
            if model_total is not None
            else None
        )
        ref_edge_prob = reference_edge_probability(model_p)
        mkt_edge_prob = market_edge_probability(model_p, market_p)
        edge_prob = (
            mkt_edge_prob if mkt_edge_prob is not None else ref_edge_prob
        )
        edge_basis = (
            "vig_adjusted_market"
            if mkt_edge_prob is not None
            else "reference_coin_flip"
        )
        fair = implied_prob_to_american(model_p)
        push_p = None
        over_block = (simulation or {}).get("over_at_line") or {}
        if over_block.get("push") is not None:
            push_p = float(over_block["push"])
        assumed_ev = expected_value_american(
            model_p, _DEFAULT_PRICE, p_push=push_p or 0.0
        )
        total_agreement = (
            ((event.get("model_disagreement") or {}).get("total") or {})
            .get("model_agreement")
        )
        confidence = confidence_from_edge(
            edge_points=edge_points,
            edge_probability=(
                (float(edge_prob) / 100.0)
                if edge_prob is not None
                else None
            ),
            model_coverage=model_total is not None,
            thresholds=conf_thresholds,
            market_type="total",
            model_agreement=total_agreement,
        )
        markets.append(
            _market_row(
                market_id=f"{event_id}:total",
                event_id=event_id,
                event_label=label,
                start_time=start,
                market_type="total",
                selection=selection,
                line=market_total,
                price=_DEFAULT_PRICE,
                model_projection=model_total,
                market_projection=market_total,
                model_probability=model_p,
                raw_model_probability=cal.get("raw_model_probability"),
                probability_calibrated=bool(cal.get("calibrated")),
                probability_calibration_method=cal.get("method"),
                event=event,
                market_probability=market_p,
                no_vig_market_probability=no_vig_market_p,
                reference_probability=reference_p,
                market_probability_source=market_p_source,
                market_edge_probability=mkt_edge_prob,
                reference_edge_probability=ref_edge_prob,
                edge_probability_basis=edge_basis,
                model_fair_price=fair,
                edge=edge_points,
                edge_probability=edge_prob,
                expected_value=assumed_ev,
                expected_value_basis="assumed_minus_110",
                price_expected_value=None,
                push_probability=push_p,
                confidence=confidence,
                model_agreement=total_agreement,
                classification_thresholds=qual_thresholds,
                home_team=home,
                away_team=away,
                opening_line=opening_total,
                line_move=move.get("total_move"),
                opportunity=_total_opportunity(
                    market_total=market_total,
                    model_total=model_total,
                    side_over=side_over,
                    edge_probability=edge_prob,
                ),
            )
        )

    # Moneyline from shared probability engine (logistic or sim).
    # Require a real market anchor (spread or listed ML). Otherwise
    # we synthesize a useless ~-105 coin-flip price for every game.
    has_moneyline_market = (
        market_spread is not None
        or current_ml is not None
        or opening_ml is not None
    )
    if model_spread is not None and has_moneyline_market:
        home_win_logistic = win_probability_from_spread(model_spread)
        home_win_p = win_probability_from_engine(
            engine=applied_engine,
            model_spread=model_spread,
            simulation=simulation,
        )
        event.setdefault("probability_compare", {})["moneyline"] = {
            "logistic": home_win_logistic,
            "simulation": (simulation or {}).get("home_win_prob"),
            "applied": applied_engine,
        }
        # Side pick may use spread logistic as a ranking aid only —
        # never as market_probability.
        spread_home_win = (
            win_probability_from_spread(market_spread)
            if market_spread is not None
            else None
        )
        side_anchor = float(spread_home_win) if spread_home_win is not None else 0.5
        side_home, cal = _moneyline_side_after_calibration(
            home_win_p,
            market_home_win=side_anchor,
            cal_model=_calibration_for_market(
                calibrations, "moneyline"
            ),
            # Winner side (not value side) so ML stays coherent with
            # projected scores / spread favorite when anchored to market.
            pick_by_edge=False,
        )
        model_p = cal["model_probability"]
        selection = home if side_home else away
        fair = implied_prob_to_american(model_p)
        open_home_ml = (
            int(opening_ml) if opening_ml is not None else None
        )
        cur_home_ml = (
            int(current_ml) if current_ml is not None else None
        )
        # Market probability only from actual moneyline odds.
        offered_home = cur_home_ml if cur_home_ml is not None else open_home_ml
        market_p = None
        no_vig_market_p = None
        market_p_source = "unavailable"
        market_implied = None
        display_price = None
        open_price = None
        if offered_home is not None:
            # Single-side American — store vigged implied; no-vig
            # requires a true two-way quote.
            home_implied = american_to_implied_prob(offered_home)
            if home_implied is not None:
                market_implied = (
                    float(home_implied)
                    if side_home
                    else (1.0 - float(home_implied))
                )
                market_p = market_implied
                no_vig_market_p = None
                market_p_source = "single_side_american"
            if side_home:
                display_price = int(offered_home)
                open_price = open_home_ml
            else:
                away_close = implied_prob_to_american(
                    1.0 - float(american_to_implied_prob(offered_home) or 0.5)
                )
                display_price = (
                    int(away_close) if away_close is not None else None
                )
                if open_home_ml is not None:
                    away_open = implied_prob_to_american(
                        1.0
                        - float(
                            american_to_implied_prob(open_home_ml) or 0.5
                        )
                    )
                    open_price = (
                        int(away_open) if away_open is not None else None
                    )
        ref_edge_prob = reference_edge_probability(model_p)
        if market_p_source == "two_way_american":
            mkt_edge_prob = market_edge_probability(model_p, market_p)
            edge_prob = mkt_edge_prob
            edge_basis = "vig_adjusted_market"
        elif market_p is not None:
            mkt_edge_prob = None
            edge_prob = market_edge_probability(model_p, market_p)
            edge_basis = "single_side_american"
        else:
            mkt_edge_prob = None
            edge_prob = ref_edge_prob
            edge_basis = "reference_coin_flip"
        price_ev = (
            expected_value_american(model_p, display_price, p_push=0.0)
            if display_price is not None
            else None
        )
        ev_basis = (
            "offered_price" if price_ev is not None else "unavailable"
        )
        ml_agreement = (
            ((event.get("model_disagreement") or {}).get("spread") or {})
            .get("model_agreement")
        )
        confidence = confidence_from_edge(
            edge_probability=(
                (float(edge_prob) / 100.0)
                if edge_prob is not None
                else None
            ),
            model_coverage=True,
            thresholds=conf_thresholds,
            market_type="moneyline",
            model_agreement=ml_agreement,
        )
        if model_p is not None:
            markets.append(
                _market_row(
                    market_id=f"{event_id}:moneyline",
                    event_id=event_id,
                    event_label=label,
                    start_time=start,
                    market_type="moneyline",
                    selection=str(selection or ""),
                    line=None,
                    price=display_price,
                    model_projection=None,
                    market_projection=None,
                    model_probability=model_p,
                    raw_model_probability=cal.get("raw_model_probability"),
                    probability_calibrated=bool(cal.get("calibrated")),
                    probability_calibration_method=cal.get("method"),
                    event=event,
                    market_probability=market_p,
                    no_vig_market_probability=no_vig_market_p,
                    reference_probability=REFERENCE_PROBABILITY,
                    market_probability_source=market_p_source,
                    market_edge_probability=mkt_edge_prob,
                    reference_edge_probability=ref_edge_prob,
                    edge_probability_basis=edge_basis,
                    model_fair_price=fair,
                    edge=edge_prob,
                    edge_probability=edge_prob,
                    expected_value=price_ev,
                    expected_value_basis=ev_basis,
                    price_expected_value=price_ev,
                    push_probability=0.0,
                    confidence=confidence,
                    model_agreement=ml_agreement,
                    classification_thresholds=qual_thresholds,
                    home_team=home,
                    away_team=away,
                    opening_price=open_price,
                    line_move=move.get("moneyline_move"),
                    opportunity=_moneyline_opportunity(
                        selection=str(selection or ""),
                        model_probability=model_p,
                        market_probability=market_p,
                        edge_probability=edge_prob,
                    ),
                )
            )

    return markets


def math_exp_safe(value: float) -> float:
    import math

    try:
        return math.exp(value)
    except OverflowError:
        return math.inf


def _market_row(
    *,
    market_id: str,
    event_id: str,
    event_label: str | None,
    start_time: str | None,
    market_type: str,
    selection: str,
    line: float | None,
    price: int | float | None,
    model_projection: float | None,
    market_projection: float | None,
    model_probability: float | None,
    market_probability: float | None,
    model_fair_price: float | None,
    edge: float | None,
    edge_probability: float | None,
    expected_value: float | None,
    confidence: str,
    home_team: str | None,
    away_team: str | None,
    opportunity: str | None = None,
    opening_line: float | None = None,
    opening_price: int | float | None = None,
    line_move: float | None = None,
    raw_model_probability: float | None = None,
    probability_calibrated: bool = False,
    probability_calibration_method: str | None = None,
    event: dict[str, Any] | None = None,
    push_probability: float | None = None,
    no_vig_market_probability: float | None = None,
    reference_probability: float | None = None,
    market_probability_source: str | None = None,
    market_edge_probability: float | None = None,
    reference_edge_probability: float | None = None,
    edge_probability_basis: str | None = None,
    expected_value_basis: str | None = None,
    price_expected_value: float | None = None,
    model_agreement: float | None = None,
    classification_thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    direction = "aligned"
    if edge is not None:
        if abs(float(edge)) < 0.5:
            direction = "aligned"
        elif float(edge) > 0:
            direction = "above_market"
        else:
            direction = "below_market"

    # Prediction disagreement signal (not a bet recommendation).
    # Confidence already reflects learned point-edge floors.
    prediction_signal = None
    if confidence in {"High", "Moderate"} and edge is not None:
        prediction_signal = (
            "MODEL_ABOVE_MARKET"
            if float(edge) > 0
            else "MODEL_BELOW_MARKET"
        )
    elif edge is not None and abs(float(edge)) < 0.5:
        prediction_signal = "MARKET_AGREEMENT"

    ev_pct = (
        round(float(expected_value) * 100.0, 1)
        if expected_value is not None
        else None
    )
    price_ev_pct = (
        round(float(price_expected_value) * 100.0, 1)
        if price_expected_value is not None
        else None
    )
    ensemble_block = disagreement_for_market(
        (event or {}).get("model_disagreement"),
        market_type,
    )
    agreement = model_agreement
    if agreement is None and isinstance(ensemble_block, dict):
        agreement = num(ensemble_block.get("model_agreement"))
    ev_basis = expected_value_basis or (
        "offered_price" if ev_pct is not None else "unavailable"
    )
    edge_basis = edge_probability_basis
    # Assumed −110 ATS/OU juice is never a qualifying offered price.
    offered_for_qualification = (
        price if ev_basis == "offered_price" else None
    )
    decision = evaluate_market_decision(
        market_type=market_type,
        selection=selection,
        model_projection=model_projection,
        market_projection=market_projection,
        raw_probability=raw_model_probability,
        calibrated_probability=model_probability,
        market_probability=market_probability,
        expected_value=ev_pct,
        edge_probability=edge_probability,
        model_confidence=confidence,
        direction=direction,
        event=event,
        market={
            "market_type": market_type,
            "model_disagreement": ensemble_block,
            "probability_calibrated": probability_calibrated,
        },
        probability_calibrated=probability_calibrated,
        offered_odds=offered_for_qualification,
        push_probability=push_probability,
        model_agreement=agreement,
        classification_thresholds=classification_thresholds,
        expected_value_basis=ev_basis,
        edge_probability_basis=edge_basis,
        market_probability_source=market_probability_source,
    )
    bet = decision.get("bet") or {}
    prediction = decision.get("prediction") or {}
    data_quality = decision.get("data_quality") or {}

    return {
        "market_id": market_id,
        "event_id": event_id,
        "event_label": event_label,
        "start_time": start_time,
        "sport": (event or {}).get("sport") or _SPORT,
        "league": (event or {}).get("league") or _LEAGUE,
        "home_team": home_team,
        "away_team": away_team,
        "home_logo_url": (event or {}).get("home_logo_url"),
        "away_logo_url": (event or {}).get("away_logo_url"),
        "market_type": market_type,
        "market_subtype": None,
        "selection": selection,
        "line": line,
        "offered_line": line,
        "price": price,
        "offered_odds": price,
        "opening_line": opening_line,
        "opening_price": opening_price,
        "current_line": line,
        "current_price": price,
        "line_move": line_move,
        "sportsbook": "consensus",
        "market_timestamp": (
            (event or {}).get("market_timestamp")
            or (event or {}).get("start_time")
        ),
        "model_probability": (
            round(float(model_probability), 4)
            if model_probability is not None
            else None
        ),
        "raw_model_probability": (
            round(float(raw_model_probability), 4)
            if raw_model_probability is not None
            else (
                round(float(model_probability), 4)
                if model_probability is not None
                else None
            )
        ),
        "push_probability": (
            round(float(push_probability), 4)
            if push_probability is not None
            else None
        ),
        "probability_calibrated": bool(probability_calibrated),
        "probability_calibration_method": (
            probability_calibration_method
        ),
        "market_probability": (
            round(float(market_probability), 4)
            if market_probability is not None
            else None
        ),
        "no_vig_market_probability": (
            round(float(no_vig_market_probability), 4)
            if no_vig_market_probability is not None
            else None
        ),
        "reference_probability": (
            round(float(reference_probability), 4)
            if reference_probability is not None
            else None
        ),
        "market_probability_source": (
            market_probability_source or "unavailable"
        ),
        "market_edge_probability": market_edge_probability,
        "reference_edge_probability": reference_edge_probability,
        "edge_probability_basis": edge_probability_basis,
        "model_fair_price": model_fair_price,
        "model_projection": model_projection,
        "market_implied_projection": market_projection,
        "edge": edge,
        "edge_probability": edge_probability,
        "expected_value": ev_pct,
        "expected_value_basis": ev_basis,
        "price_expected_value": price_ev_pct,
        "confidence": confidence,
        "confidence_explanation": confidence_explanation(
            confidence
        ),
        "projection_mean": (
            (ensemble_block or {}).get("projection_mean")
        ),
        "projection_stddev": (
            (ensemble_block or {}).get("projection_stddev")
        ),
        "model_agreement": (
            agreement
            if agreement is not None
            else (ensemble_block or {}).get("model_agreement")
        ),
        "model_agreement_label": (ensemble_block or {}).get("label"),
        "ensemble_estimates": (ensemble_block or {}).get("estimates"),
        "ensemble_n_models": (ensemble_block or {}).get("n_models"),
        "model_disagreement": ensemble_block,
        "uncertainty": bet.get("uncertainty") or {
            "data_quality": data_quality.get("label"),
            "model_agreement": agreement,
            "probability_calibrated": bool(probability_calibrated),
            "sigma_margin": (
                ((event or {}).get("score_distribution") or {})
                .get("uncertainty")
                or {}
            ).get("sigma_margin"),
        },
        "pricing_audit": bet.get("pricing_audit"),
        "direction": direction,
        # Legacy field — prediction disagreement, not bet advice.
        "primary_signal": prediction_signal,
        "prediction": prediction,
        "data_quality": data_quality,
        "bet_qualification": bet,
        "bet_qualified": bool(bet.get("qualified")),
        "bet_status": bet.get("status") or "pass",
        "bet_label": bet.get("label") or "Pass",
        "no_bet": bool(bet.get("no_bet", not bet.get("qualified"))),
        "opportunity": opportunity,
        "status": "open",
        "source": "nflverse_schedules",
        "decision_pipeline": decision.get("pipeline"),
    }


def _spread_opportunity(
    *,
    home_team: str | None,
    away_team: str | None,
    market_spread: float | None,
    model_spread: float | None,
    side_is_home: bool,
    edge_probability: float | None,
    projected_home: float | None,
    projected_away: float | None,
) -> str | None:
    if market_spread is None or model_spread is None:
        return None

    if projected_home is not None and projected_away is not None:
        margin = abs(float(projected_home) - float(projected_away))
        if projected_home >= projected_away:
            favored = home_team or "Home"
            model_favors_home = True
        else:
            favored = away_team or "Away"
            model_favors_home = False
    else:
        margin = abs(float(model_spread))
        model_favors_home = float(model_spread) <= 0
        favored = (home_team if model_favors_home else away_team) or "Favorite"

    selection_line = (
        float(market_spread)
        if side_is_home
        else -float(market_spread)
    )
    selection = (home_team if side_is_home else away_team) or "This side"
    likelihood = _likelihood_phrase(edge_probability)

    if selection_line < 0:
        giving = abs(selection_line)
        return (
            f"{selection} are projected to win by {margin:g} and are "
            f"only giving {giving:g} points; taking {selection} "
            f"{selection_line:+g} has {likelihood}."
        )
    if selection_line > 0:
        getting = abs(selection_line)
        if model_favors_home == side_is_home:
            return (
                f"{selection} are projected ahead by {margin:g} while "
                f"also getting {getting:g} points; taking {selection} "
                f"{selection_line:+g} has {likelihood}."
            )
        return (
            f"{favored} are projected to win by only {margin:g} while "
            f"{selection} get {getting:g} points; taking {selection} "
            f"{selection_line:+g} has {likelihood}."
        )
    return (
        f"The market is pick'em while InsightPilot projects "
        f"{favored} by {margin:g}; taking {selection} PK has {likelihood}."
    )


def _total_opportunity(
    *,
    market_total: float | None,
    model_total: float | None,
    side_over: bool,
    edge_probability: float | None,
) -> str | None:
    if market_total is None or model_total is None:
        return None
    side = "Over" if side_over else "Under"
    if float(model_total) > float(market_total):
        direction = "higher"
    elif float(model_total) < float(market_total):
        direction = "lower"
    else:
        direction = "similar"
    likelihood = _likelihood_phrase(edge_probability)
    return (
        f"InsightPilot projects {model_total:g} points versus the "
        f"market total of {market_total:g} ({direction} scoring "
        f"environment); taking the {side} {market_total:g} has "
        f"{likelihood}."
    )


def _moneyline_side_after_calibration(
    home_win_p: float,
    *,
    market_home_win: float = 0.5,
    cal_model: dict[str, Any] | None,
    pick_by_edge: bool = False,
) -> tuple[bool, dict[str, Any]]:
    """Choose the moneyline side to price and display.

    Default: the side the model gives >= 50% to win. With
    ``pick_by_edge``, choose the side with the better model-vs-market
    edge so a favorite-win / dog-cover view does not force chalk on
    the moneyline when the model is softer than the market.
    """

    home_raw = float(home_win_p)
    market_home = float(market_home_win)
    if pick_by_edge:
        home_edge = home_raw - market_home
        if abs(home_edge) < 1e-9:
            side_home = home_raw >= 0.5
        else:
            side_home = home_edge > 0.0
    else:
        side_home = home_raw >= 0.5
    raw_model_p = home_raw if side_home else (1.0 - home_raw)
    cal = calibrate_market_probability(
        raw_model_p,
        model=cal_model,
    )
    model_p = cal.get("model_probability")
    # Value picks may sit under 50% win probability — keep them.
    if pick_by_edge or model_p is None or float(model_p) >= 0.5:
        return side_home, cal

    flipped_p = round(1.0 - float(model_p), 4)
    raw = cal.get("raw_model_probability")
    flipped = {
        **cal,
        "model_probability": flipped_p,
        "raw_model_probability": (
            round(1.0 - float(raw), 4)
            if raw is not None
            else None
        ),
    }
    return (not side_home), flipped


def _moneyline_opportunity(
    *,
    selection: str,
    model_probability: float | None,
    market_probability: float | None,
    edge_probability: float | None,
) -> str | None:
    if model_probability is None or market_probability is None:
        return None
    likelihood = _likelihood_phrase(edge_probability)
    return (
        f"InsightPilot gives {selection} a "
        f"{model_probability * 100:.1f}% win probability versus the "
        f"market's {market_probability * 100:.1f}%; taking {selection} "
        f"moneyline has {likelihood}."
    )


def _likelihood_phrase(edge_probability: float | None) -> str:
    if edge_probability is None:
        return "a model-supported edge versus the market price"
    pct = abs(float(edge_probability))
    if float(edge_probability) >= 0.5:
        return (
            f"a {pct:.1f}% increased likelihood of winning versus "
            "the market price"
        )
    if float(edge_probability) <= -0.5:
        return (
            f"a {pct:.1f}% lower implied win likelihood than the "
            "market price"
        )
    return "little separation from the market-implied likelihood"


def _build_signals(
    event: dict[str, Any],
    markets: list[dict[str, Any]],
    *,
    edge_confidence: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    moderate_min = float(
        num((edge_confidence or {}).get("moderate_min")) or 1.5
    )

    market_spread = num(event.get("market_spread"))
    model_spread = num(event.get("model_spread"))
    if (
        market_spread is not None
        and model_spread is not None
        and abs(model_spread - market_spread) >= moderate_min
    ):
        signals.append(
            {
                "signal_id": f"{event['event_id']}:spread_disagreement",
                "event_id": event["event_id"],
                "market_id": f"{event['event_id']}:spread",
                "signal_type": "MARKET_DISAGREEMENT",
                "layer": "prediction",
                "label": "Spread prediction",
                "direction": (
                    "above"
                    if model_spread > market_spread
                    else "below"
                ),
                "confidence": confidence_from_edge(
                    edge_points=model_spread - market_spread,
                    thresholds=edge_confidence,
                    market_type="spread",
                ),
                "explanation": (
                    f"Model spread {model_spread:+g} differs from "
                    f"market {market_spread:+g} by "
                    f"{model_spread - market_spread:+g} points. "
                    "This is a prediction signal, not a qualified bet."
                ),
            }
        )

    home_adj = num(event.get("injury_adjustment_home")) or 0.0
    away_adj = num(event.get("injury_adjustment_away")) or 0.0
    injury_notes = event.get("injuries") or []
    material_injuries = [
        note
        for note in injury_notes
        if note.get("is_starter")
        and abs(float(note.get("projection_impact_pts") or 0)) >= 0.3
    ]
    if material_injuries or abs(home_adj) >= 0.5 or abs(away_adj) >= 0.5:
        top = material_injuries[:2]
        names = ", ".join(
            str(note.get("player_name") or "Player") for note in top
        )
        total_adj = round(home_adj + away_adj, 1)
        signals.insert(
            0,
            {
                "signal_id": f"{event['event_id']}:injury_impact",
                "event_id": event["event_id"],
                "market_id": f"{event['event_id']}:total",
                "signal_type": "INJURY_IMPACT",
                "layer": "prediction",
                "label": "Injury impact",
                "direction": "below" if total_adj < 0 else "aligned",
                "confidence": (
                    "High"
                    if abs(total_adj) >= 2.0
                    else "Moderate"
                ),
                "explanation": (
                    (
                        f"Starter availability ({names}"
                        f"{'…' if len(material_injuries) > 2 else ''}) "
                        f"shifted projected scoring by {total_adj:+g} pts."
                    )
                    if names
                    else (
                        f"Injury context shifted projected scoring by "
                        f"{total_adj:+g} pts."
                    )
                ),
            },
        )

    # Bet classifications are separate from prediction signals.
    for market in markets:
        status = str(market.get("bet_status") or "pass")
        bet = market.get("bet_qualification") or {}
        label = market.get("bet_label") or bet.get("label") or status
        if status in {"strong_bet", "lean"}:
            signals.insert(
                0,
                {
                    "signal_id": (
                        f"{market.get('market_id')}:{status}"
                    ),
                    "event_id": event["event_id"],
                    "market_id": market.get("market_id"),
                    "signal_type": (
                        "STRONG_BET"
                        if status == "strong_bet"
                        else "LEAN"
                    ),
                    "layer": "bet",
                    "label": f"{label} · {market.get('selection')}",
                    "direction": "bet",
                    "confidence": market.get("confidence"),
                    "explanation": bet.get("summary") or (
                        f"{label} after threshold gates."
                    ),
                },
            )
        elif market.get("no_bet") or status == "pass":
            # Surface No Bet when there is a directional prediction
            # that failed gates — makes "no actionable edge" visible.
            pred = market.get("prediction") or {}
            edge_pp = num(market.get("edge_probability"))
            if pred.get("has_prediction") and (
                edge_pp is None or abs(float(edge_pp)) >= 0.5
            ):
                signals.append(
                    {
                        "signal_id": (
                            f"{market.get('market_id')}:no_bet"
                        ),
                        "event_id": event["event_id"],
                        "market_id": market.get("market_id"),
                        "signal_type": "NO_BET",
                        "layer": "bet",
                        "label": f"Pass · {market.get('selection')}",
                        "direction": "no_bet",
                        "confidence": market.get("confidence"),
                        "explanation": bet.get("summary") or (
                            "No actionable edge — Pass / No Bet."
                        ),
                    }
                )

    # Prefer Strong Bet, then Lean, then predictions, then No Bet notes.
    rank = {
        "STRONG_BET": 0,
        "LEAN": 1,
        "INJURY_IMPACT": 2,
        "MARKET_DISAGREEMENT": 3,
        "NO_BET": 4,
    }
    signals.sort(
        key=lambda s: (
            rank.get(str(s.get("signal_type")), 9),
            str(s.get("signal_id") or ""),
        )
    )

    for signal in signals:
        signal["event_label"] = event.get("label")
    return signals


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _majority_confidence(values: list[Any]) -> str:
    if not values:
        return "Low"
    counts = {"High": 0, "Moderate": 0, "Low": 0}
    for value in values:
        key = str(value)
        if key in counts:
            counts[key] += 1
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            # Prefer full datetime when time is present; keep
            # date-only values as YYYY-MM-DD (no fabricated TZ).
            iso = value.isoformat()
            if "T" in iso:
                return iso
            return iso[:10] if len(iso) >= 10 else iso
        except Exception:
            return str(value)
    text = str(value).strip()
    if not text:
        return None
    # Normalize "YYYY-MM-DD HH:MM:SS" → ISO local wall clock.
    if " " in text and "T" not in text[:11]:
        text = text.replace(" ", "T", 1)
    return text
