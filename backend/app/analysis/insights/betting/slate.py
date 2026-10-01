"""
Build NFL Sports Betting slate from canonical game markets.

Phase 1 sources:
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

from app.analysis.insights.betting.pricing import (
    american_to_implied_prob,
    confidence_explanation,
    confidence_from_edge,
    expected_value,
    implied_prob_to_american,
    num,
    remove_vig_two_way,
    spread_to_cover_probability,
    total_to_over_probability,
)
from app.analysis.insights.betting.game_scripts import (
    project_game_scripts,
)
from app.analysis.insights.betting.player_context import (
    combined_score_adjustments,
    load_week_player_context,
    team_injury_context,
)
from app.analysis.insights.betting.results import (
    build_performance_trend,
    build_projection_snapshot,
    calibration_feedback_from_results,
    is_game_final,
    settle_event_markets,
    summarize_model_results,
    trend_summary_from_points,
)
from app.analysis.insights.betting.team_strength import (
    load_team_strength_context,
)
from app.analysis.insights.betting.residual_model import (
    add_situational_residuals,
    apply_score_residuals,
    calibration_score_deltas,
    predict_score_residuals,
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
    del sport  # NFL-only Phase 1
    resolved = _resolve_season(season)
    weeks: list[int] = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT DISTINCT week
                    FROM {FANTASY_SCHEMA}.fact_game_market
                    WHERE season = :season
                      AND week IS NOT NULL
                    ORDER BY week
                    """
                ),
                {"season": resolved},
            ).fetchall()
            weeks = [int(row[0]) for row in rows if row[0] is not None]
    except Exception:
        weeks = []
    current = _current_betting_week(
        season=resolved,
        available_weeks=weeks,
    )
    return {
        "sport": _SPORT,
        "league": _LEAGUE,
        "season": resolved,
        "weeks": weeks,
        "current_week": current,
    }


def build_betting_slate(
    *,
    season: int | None = None,
    week: int | None = None,
    sport: str = "NFL",
) -> dict[str, Any]:
    del sport
    resolved_season = _resolve_season(season)
    resolved_week = _resolve_week(week, season=resolved_season)
    events = _load_events(
        season=resolved_season,
        week=resolved_week,
    )
    strength_context = load_team_strength_context(
        season=resolved_season,
        before_week=resolved_week,
    )
    player_context = load_week_player_context(
        season=resolved_season,
        week=resolved_week,
    )
    calibration = _load_calibration_feedback(resolved_season)
    probability_calibration = _load_probability_calibration(
        resolved_season
    )
    edge_confidence = _load_edge_confidence(resolved_season)
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

    for event in events:
        built = _enrich_event(
            event,
            strength_context=strength_context,
            player_context=player_context,
            calibration=calibration,
            probability_calibration=probability_calibration,
            edge_confidence=edge_confidence,
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
        newly_settled.extend(settled_rows)
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
        "sport": _SPORT,
        "league": _LEAGUE,
        "season": resolved_season,
        "week": resolved_week,
        "slate_id": f"nfl-{resolved_season}-w{resolved_week}",
        "label": f"NFL Week {resolved_week}",
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
        "source": "nflverse_schedules",
        "source_note": (
            "Market lines are nflverse schedule snapshots "
            "(not live multi-book sportsbook feeds). "
            "InsightPilot projection = market baseline + "
            "model residual (where the market is likely "
            "wrong). Residuals come from confidence-shrunk "
            "opponent-adjusted team-strength disagreement "
            "plus situational injury / calibration layers. "
            "Opening vs current lines track whether the "
            "market has started incorporating that view. "
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
    }


def get_betting_event(
    event_id: str,
    *,
    season: int | None = None,
) -> dict[str, Any] | None:
    eid = str(event_id or "").strip()
    if not eid:
        return None
    resolved_season = _resolve_season(season)
    events = _load_events(
        season=resolved_season,
        week=None,
        event_id=eid,
    )
    if not events:
        return None
    week = _as_int(events[0].get("week")) or _resolve_week(
        None,
        season=resolved_season,
    )
    strength_context = load_team_strength_context(
        season=resolved_season,
        before_week=week,
    )
    player_context = load_week_player_context(
        season=resolved_season,
        week=week,
    )
    calibration = _load_calibration_feedback(resolved_season)
    probability_calibration = _load_probability_calibration(
        resolved_season
    )
    edge_confidence = _load_edge_confidence(resolved_season)
    built = _enrich_event(
        events[0],
        strength_context=strength_context,
        player_context=player_context,
        calibration=calibration,
        probability_calibration=probability_calibration,
        edge_confidence=edge_confidence,
    )
    _sync_event_results(built["event"], built["markets"])
    return built


def build_betting_results(
    *,
    season: int | None = None,
    week: int | None = None,
) -> dict[str, Any]:
    """
    Auto-settle completed games for the week/season and return
    model-vs-actual performance (all markets, not portfolio-only).
    """

    resolved_season = _resolve_season(season)
    resolved_week = _resolve_week(week, season=resolved_season)
    # Pull overnight / MNF finals into dim_game before settlement.
    # Without this, Results depended on a manual dim_game refresh and
    # Monday-night scores could sit in nflverse while the page still
    # treated the game as unsettled.
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
            snap = build_projection_snapshot(event)
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
    # Keep probability calibration current from season settled bets.
    try:
        _refresh_season_calibration(
            season=int(season_value or resolved_season),
            extra_rows=season_stored or stored,
        )
    except Exception:
        pass
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
    return {
        "sport": _SPORT,
        "league": _LEAGUE,
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
    snap = build_projection_snapshot(event)

    if not is_game_final(event):
        # Capture a first-publish snapshot for later CLV/settlement
        # bet_line, but do not freeze yet — open games recompute
        # live so model upgrades appear on refresh.
        if not existing:
            upsert_projection_snapshot(snap, freeze=False)
        return []

    if existing and not existing.get("frozen"):
        freeze_projection_snapshot(event_id)
        existing = get_projection_snapshot(event_id)
    elif not existing:
        snap["frozen"] = True
        upsert_projection_snapshot(snap, freeze=True)
        existing = snap

    settled = settle_event_markets(
        event, markets, snapshot=existing or snap
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
    try:
        from app.canonical.fact_betting_results import (
            get_probability_calibration,
        )

        return get_probability_calibration(int(season))
    except Exception:
        return None


def _load_edge_confidence(season: int) -> dict[str, Any] | None:
    try:
        from app.canonical.fact_betting_results import (
            get_edge_confidence,
        )

        return get_edge_confidence(int(season))
    except Exception:
        return None


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
    feedback = calibration_feedback_from_results(rows)
    upsert_calibration(feedback, season=int(season))

    # Probability calibration: fit from raw predicted vs actual.
    prob_model = fit_probability_calibration(rows, method="auto")
    upsert_probability_calibration(
        prob_model,
        season=int(season),
        market_type="all",
    )

    # Learn High/Moderate floors from point-edge bucket backtests.
    edge_model = fit_confidence_thresholds(rows)
    market_perf = build_market_performance(rows)
    edge_model = merge_edge_confidence_with_markets(
        edge_model, market_perf
    )
    upsert_edge_confidence(edge_model, season=int(season))

    # Also fit probability calibration per market when samples allow.
    for mtype in ("spread", "total", "moneyline"):
        subset = [
            row
            for row in rows
            if str(row.get("market_type") or "").lower() == mtype
        ]
        if len(subset) < 25:
            continue
        m_model = fit_probability_calibration(
            subset, method="auto", market_type=mtype
        )
        upsert_probability_calibration(
            m_model,
            season=int(season),
            market_type=mtype,
        )


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


def _resolve_season(season: int | None) -> int:
    if season is not None:
        return int(season)
    try:
        import nflreadpy as nfl

        return int(nfl.get_current_season())
    except Exception:
        return datetime.now(timezone.utc).year


def _resolve_week(
    week: int | None,
    *,
    season: int,
) -> int:
    if week is not None:
        return max(1, int(week))
    listed = list_betting_weeks(season=season)
    current = listed.get("current_week")
    if current is not None:
        return int(current)
    return 1


def _current_betting_week(
    *,
    season: int,
    available_weeks: list[int],
) -> int | None:
    """
    Prefer nflverse's live NFL week over the latest week present
    in fact_game_market (future schedules often land early).
    """

    nfl_week: int | None = None
    try:
        import nflreadpy as nfl

        current_season = int(nfl.get_current_season())
        if int(season) == current_season:
            nfl_week = max(1, int(nfl.get_current_week()))
    except Exception:
        nfl_week = None

    if not available_weeks:
        return nfl_week

    if nfl_week is not None:
        if nfl_week in available_weeks:
            return nfl_week
        # If live week is ahead of loaded markets, stay on the
        # latest available week at or before the live week.
        prior = [w for w in available_weeks if w <= nfl_week]
        if prior:
            return prior[-1]
        return available_weeks[0]

    return available_weeks[-1]


def _load_events(
    *,
    season: int,
    week: int | None,
    event_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["m.season = :season"]
    params: dict[str, Any] = {"season": int(season)}
    if week is not None:
        clauses.append("m.week = :week")
        params["week"] = int(week)
    if event_id:
        clauses.append("m.game_id = :event_id")
        params["event_id"] = event_id
    where = " AND ".join(clauses)
    sql = f"""
        SELECT DISTINCT ON (m.game_id)
          m.game_id AS event_id,
          m.season,
          m.week,
          m.season_type,
          m.spread,
          m.over_under,
          m.home_implied_total,
          m.away_implied_total,
          m.opening_spread,
          m.opening_over_under,
          m.opening_home_implied_total,
          m.opening_away_implied_total,
          m.opening_captured_at,
          m.line_moved_at,
          m.timestamp AS market_timestamp,
          m.source,
          g.game_date AS start_time,
          g.game_status AS status,
          g.home_score,
          g.away_score,
          ht.team_id AS home_team_id,
          ht.team_abbreviation AS home_team,
          ht.team_name AS home_team_name,
          at.team_id AS away_team_id,
          at.team_abbreviation AS away_team,
          at.team_name AS away_team_name
        FROM {FANTASY_SCHEMA}.fact_game_market m
        JOIN {FANTASY_SCHEMA}.dim_game g
          ON g.game_id = m.game_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team ht
          ON ht.team_id = g.home_team_id
        LEFT JOIN {FANTASY_SCHEMA}.dim_team at
          ON at.team_id = g.away_team_id
        WHERE {where}
        ORDER BY m.game_id, m.timestamp DESC NULLS LAST
    """
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
    recent_ppg: dict[str, float] | None = None,
    player_context: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    probability_calibration: dict[str, Any] | None = None,
    edge_confidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    home = str(raw.get("home_team") or "").upper()
    away = str(raw.get("away_team") or "").upper()
    event_id = str(raw.get("event_id") or "")
    market_spread_raw = num(raw.get("spread"))
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

    home_injury = team_injury_context(player_context, home_team_id)
    away_injury = team_injury_context(player_context, away_team_id)
    home_adj, away_adj = combined_score_adjustments(
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
    if opening_total is None:
        opening_total = market_total

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
        opening_spread = market_spread

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

    label = f"{away} @ {home}" if away and home else event_id
    # Prefer schedule kickoff (gameday + gametime stored on
    # fact_game_market.timestamp) over date-only dim_game.game_date.
    # Date-only ISO strings shift a day in US timezones when parsed
    # as UTC midnight in the browser.
    kickoff = raw.get("market_timestamp") or raw.get("start_time")
    event = {
        "event_id": event_id,
        "sport": _SPORT,
        "league": _LEAGUE,
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
        "model_spread": model_spread,
        "residual_home": residual_home,
        "residual_away": residual_away,
        "team_strength": strength_detail if strength_detail.get("available") else None,
        "projection_blend": blend_meta or None,
        "residuals": residual_meta or None,
        "model_disagreement": disagreement,
        "game_scripts": game_scripts,
        "injury_adjustment_home": home_adj or None,
        "injury_adjustment_away": away_adj or None,
        "injuries": injury_notes,
        "model_drivers": model_drivers,
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
        edge_confidence=edge_confidence,
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


def _model_scores(
    *,
    market_home: float | None,
    market_away: float | None,
    home_team_id: str | None = None,
    away_team_id: str | None = None,
    strength_context: dict[str, Any] | None = None,
    recent_ppg: dict[str, float] | None = None,
    home_injury_adj: float = 0.0,
    away_injury_adj: float = 0.0,
    calibration: dict[str, Any] | None = None,
) -> tuple[float | None, float | None, dict[str, Any]]:
    """
    Market + residual projection.

    1. Predict where the market is wrong (team-strength residual)
    2. Shrink residual by projection confidence
    3. Add situational residuals (injuries, calibration)
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
    # market-anchored strength projection, plus injury adjustments.
    provisional_home, provisional_away, _ = apply_score_residuals(
        residual_model
    )
    cal_home, cal_away = calibration_score_deltas(
        projected_home=provisional_home,
        projected_away=provisional_away,
        feedback=calibration,
    )
    residual_model = add_situational_residuals(
        residual_model,
        home_adjustment=float(home_injury_adj or 0.0) + cal_home,
        away_adjustment=float(away_injury_adj or 0.0) + cal_away,
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
    edge_confidence: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    event_id = event["event_id"]
    home = event.get("home_team")
    away = event.get("away_team")
    start = event.get("start_time")
    label = event.get("label")
    cal_model = probability_calibration
    conf_thresholds = edge_confidence

    market_spread = num(event.get("market_spread"))
    model_spread = num(event.get("model_spread"))
    market_total = num(event.get("market_total"))
    model_total = num(event.get("projected_total"))
    opening_spread = num(event.get("opening_spread"))
    opening_total = num(event.get("opening_total"))
    opening_ml = event.get("opening_moneyline")
    current_ml = event.get("current_moneyline")
    move = event.get("market_movement") or {}

    if market_spread is not None:
        # Home-team spread line (nflverse convention).
        selection = (
            f"{home} {market_spread:+g}"
            if home
            else f"Home {market_spread:+g}"
        )
        cover_p = spread_to_cover_probability(
            model_spread,
            market_spread,
        )
        # Market at -110 each side → ~52.4% implied before vig.
        market_p_raw = american_to_implied_prob(_DEFAULT_PRICE)
        market_p, _ = remove_vig_two_way(
            market_p_raw,
            market_p_raw,
        )
        # Favorable side: if model has home covering more than 50%.
        side_is_home = cover_p is not None and cover_p >= 0.5
        raw_model_p = cover_p if side_is_home else (
            (1.0 - cover_p) if cover_p is not None else None
        )
        cal = calibrate_market_probability(
            raw_model_p, model=cal_model
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
        edge_prob = (
            round((float(model_p) - float(market_p)) * 100.0, 1)
            if model_p is not None and market_p is not None
            else None
        )
        fair = implied_prob_to_american(model_p)
        ev = expected_value(model_p, _DEFAULT_PRICE)
        confidence = confidence_from_edge(
            edge_points=edge_points,
            edge_probability=(
                (model_p - market_p)
                if model_p is not None and market_p is not None
                else None
            ),
            model_coverage=model_spread is not None,
            thresholds=conf_thresholds,
            market_type="spread",
            model_agreement=(
                ((event.get("model_disagreement") or {}).get("spread") or {})
                .get("model_agreement")
            ),
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
                model_fair_price=fair,
                edge=edge_points,
                edge_probability=edge_prob,
                expected_value=ev,
                confidence=confidence,
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
        over_p = total_to_over_probability(
            model_total,
            market_total,
        )
        market_p_raw = american_to_implied_prob(_DEFAULT_PRICE)
        market_p, _ = remove_vig_two_way(
            market_p_raw,
            market_p_raw,
        )
        side_over = over_p is not None and over_p >= 0.5
        raw_model_p = over_p if side_over else (
            (1.0 - over_p) if over_p is not None else None
        )
        cal = calibrate_market_probability(
            raw_model_p, model=cal_model
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
        edge_prob = (
            round((float(model_p) - float(market_p)) * 100.0, 1)
            if model_p is not None and market_p is not None
            else None
        )
        fair = implied_prob_to_american(model_p)
        ev = expected_value(model_p, _DEFAULT_PRICE)
        confidence = confidence_from_edge(
            edge_points=edge_points,
            edge_probability=(
                (model_p - market_p)
                if model_p is not None and market_p is not None
                else None
            ),
            model_coverage=model_total is not None,
            thresholds=conf_thresholds,
            market_type="total",
            model_agreement=(
                ((event.get("model_disagreement") or {}).get("total") or {})
                .get("model_agreement")
            ),
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
                model_fair_price=fair,
                edge=edge_points,
                edge_probability=edge_prob,
                expected_value=ev,
                confidence=confidence,
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

    # Moneyline from spread-derived home win probability.
    if model_spread is not None:
        # Rough home win prob from model spread (no push).
        home_win_p = 1.0 / (
            1.0 + math_exp_safe(float(model_spread) / 7.0)
        )
        # Market home win from market spread.
        market_home_win = (
            1.0
            / (1.0 + math_exp_safe(float(market_spread) / 7.0))
            if market_spread is not None
            else 0.5
        )
        side_home = home_win_p >= 0.5
        raw_model_p = home_win_p if side_home else (1.0 - home_win_p)
        cal = calibrate_market_probability(
            raw_model_p, model=cal_model
        )
        model_p = cal["model_probability"]
        market_p = (
            market_home_win if side_home else (1.0 - market_home_win)
        )
        selection = home if side_home else away
        fair = implied_prob_to_american(model_p)
        # Synthetic market American price from market_p.
        market_price = implied_prob_to_american(market_p) or -110
        # Re-apply light juice for display.
        if market_price < 0:
            market_price = min(market_price, -105)
        else:
            market_price = max(market_price, 100)
        edge_prob = (
            round((float(model_p) - float(market_p)) * 100.0, 1)
            if model_p is not None
            else None
        )
        ev = expected_value(model_p, market_price)
        confidence = confidence_from_edge(
            edge_probability=(
                (model_p - market_p) if model_p is not None else None
            ),
            model_coverage=True,
            thresholds=conf_thresholds,
            market_type="moneyline",
            model_agreement=(
                ((event.get("model_disagreement") or {}).get("spread") or {})
                .get("model_agreement")
            ),
        )
        # Prefer stored/derived home ML; flip for away selection.
        open_home_ml = (
            int(opening_ml) if opening_ml is not None else None
        )
        cur_home_ml = (
            int(current_ml) if current_ml is not None else None
        )
        if side_home:
            open_price = open_home_ml
            display_price = cur_home_ml or int(market_price)
        else:
            open_price = None
            if opening_spread is not None:
                away_open_p = 1.0 - (
                    1.0
                    / (1.0 + math_exp_safe(float(opening_spread) / 7.0))
                )
                open_price = implied_prob_to_american(away_open_p)
            display_price = int(market_price)

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
                model_fair_price=fair,
                edge=edge_prob,
                edge_probability=edge_prob,
                expected_value=ev,
                confidence=confidence,
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
    ensemble_block = disagreement_for_market(
        (event or {}).get("model_disagreement"),
        market_type,
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
        probability_calibrated=probability_calibrated,
    )
    bet = decision.get("bet") or {}
    prediction = decision.get("prediction") or {}
    data_quality = decision.get("data_quality") or {}

    return {
        "market_id": market_id,
        "event_id": event_id,
        "event_label": event_label,
        "start_time": start_time,
        "sport": _SPORT,
        "league": _LEAGUE,
        "home_team": home_team,
        "away_team": away_team,
        "market_type": market_type,
        "market_subtype": None,
        "selection": selection,
        "line": line,
        "price": price,
        "opening_line": opening_line if opening_line is not None else line,
        "opening_price": (
            opening_price if opening_price is not None else price
        ),
        "current_line": line,
        "current_price": price,
        "line_move": line_move,
        "sportsbook": "consensus",
        "market_timestamp": None,
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
        "probability_calibrated": bool(probability_calibrated),
        "probability_calibration_method": (
            probability_calibration_method
        ),
        "market_probability": (
            round(float(market_probability), 4)
            if market_probability is not None
            else None
        ),
        "model_fair_price": model_fair_price,
        "model_projection": model_projection,
        "market_implied_projection": market_projection,
        "edge": edge,
        "edge_probability": edge_probability,
        "expected_value": ev_pct,
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
            (ensemble_block or {}).get("model_agreement")
        ),
        "model_agreement_label": (ensemble_block or {}).get("label"),
        "ensemble_estimates": (ensemble_block or {}).get("estimates"),
        "ensemble_n_models": (ensemble_block or {}).get("n_models"),
        "model_disagreement": ensemble_block,
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
