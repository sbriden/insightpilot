"""
Controlled prediction autopsy for InsightPilot betting models.

Compares, on the same settled historical markets (chronological):
  1. Market baseline (de-vigged offered probabilities)
  2. Fundamental model (team-strength projection, no market blend)
  3. Current blended model (frozen pregame tape)
  4. Bet selection quality (Strong / Lean / Pass)
  5. Realistic flat-1u returns at historical prices

Does not change projection weights — audit only.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.betting_sport import (
    resolve_betting_sport,
)
from app.analysis.insights.betting.clv import (
    enrich_settled_row_metrics,
    selection_side,
    unit_result,
)
from app.analysis.insights.betting.dataset_eligibility import (
    filter_rows,
    qualification_status,
)
from app.analysis.insights.betting.pricing import (
    REFERENCE_PROBABILITY,
    num,
    spread_to_cover_probability,
    total_to_over_probability,
    win_probability_from_spread,
)
from app.analysis.insights.betting.tape_quality_audit import (
    run_tape_and_pricing_audits,
)
from app.analysis.insights.betting.team_strength import (
    load_team_strength_context,
    project_strength_scores,
)
from app.canonical.fact_betting_results import (
    ensure_betting_results_tables,
    load_market_results,
)
from app.database import engine


PROB_BUCKETS = [
    (0.50, 0.55),
    (0.55, 0.60),
    (0.60, 0.65),
    (0.65, 0.70),
    (0.70, 0.80),
    (0.80, 1.01),
]


def run_prediction_autopsy(
    *,
    sport: str | None = None,
    seasons: list[int] | None = None,
    seed: int = 7,
) -> dict[str, Any]:
    """
    Run the full autopsy. ``sport`` filters to NFL or CFB when set;
    otherwise both cohorts are reported separately.
    """

    ensure_betting_results_tables()
    rows = load_market_results()
    if seasons:
        keep = {int(s) for s in seasons}
        rows = [r for r in rows if int(r.get("season") or 0) in keep]

    game_sport = _game_sport_map(
        [str(r.get("event_id") or r.get("game_id") or "") for r in rows]
    )
    tagged = []
    for r in rows:
        out = dict(r)
        eid = str(r.get("event_id") or r.get("game_id") or "")
        out["sport"] = game_sport.get(eid)
        if out["sport"]:
            tagged.append(out)

    sports = (
        [str(sport).upper()]
        if sport
        else sorted({str(r["sport"]) for r in tagged})
    )
    cohorts: dict[str, Any] = {}
    for sp in sports:
        cohort_rows = [r for r in tagged if r.get("sport") == sp]
        cohorts[sp] = _autopsy_cohort(cohort_rows, sport=sp, seed=seed)

    return {
        "title": "InsightPilot prediction autopsy",
        "scope": {
            "sports": sports,
            "seasons": sorted(
                {int(r.get("season") or 0) for r in tagged}
            ),
            "markets": len(tagged),
            "note": (
                "Same settled tape for all comparisons. Fundamental "
                "projections recompute leak-safe strength before each "
                "week; blended uses frozen pregame model probabilities."
            ),
        },
        "cohorts": cohorts,
    }


def _autopsy_cohort(
    rows: list[dict[str, Any]],
    *,
    sport: str,
    seed: int,
) -> dict[str, Any]:
    enriched = [enrich_settled_row_metrics(dict(r)) for r in rows]
    decided = [
        r for r in enriched if r.get("result") in {"won", "lost"}
    ]
    fund_by_market = _fundamental_probabilities(enriched, sport=sport)

    # Legacy autopsy treated synthetic ATS/OU 0.5 as market baseline.
    legacy_market_samples: list[tuple[float, int]] = []
    corrected_market_samples: list[tuple[float, int]] = []
    reference_samples: list[tuple[float, int]] = []
    blend_samples: list[tuple[float, int]] = []
    fund_samples: list[tuple[float, int]] = []
    for row in decided:
        y = 1 if row.get("result") == "won" else 0
        mkt = num(row.get("market_probability"))
        src = str(row.get("market_probability_source") or "").lower()
        blend = num(
            row.get("raw_model_probability")
            if row.get("raw_model_probability") is not None
            else row.get("model_probability")
        )
        # Legacy view: stored market_p, else coin-flip for ATS/OU.
        if mkt is not None:
            legacy_market_samples.append((float(mkt), y))
        elif str(row.get("market_type") or "").lower() in {
            "spread",
            "total",
        }:
            legacy_market_samples.append((REFERENCE_PROBABILITY, y))
        # Corrected: only real book-derived market probabilities.
        if mkt is not None and src not in {
            "",
            "unavailable",
            "synthetic_minus_110",
            "spread_logistic",
            "unverified_legacy",
        }:
            corrected_market_samples.append((float(mkt), y))
        elif mkt is not None and src == "single_side_american":
            corrected_market_samples.append((float(mkt), y))
        ref = num(row.get("reference_probability"))
        if ref is not None:
            reference_samples.append((float(ref), y))
        elif str(row.get("market_type") or "").lower() in {
            "spread",
            "total",
        }:
            reference_samples.append((REFERENCE_PROBABILITY, y))
        if blend is not None:
            blend_samples.append((float(blend), y))
        fund = fund_by_market.get(str(row.get("market_id") or ""))
        if fund is not None:
            fund_samples.append((float(fund), y))

    point_errors = _point_forecast_errors(enriched)
    selection = _selection_audit(decided, seed=seed)
    returns = _returns_audit(decided, seed=seed)
    clv = _clv_audit(enriched)
    qualified = filter_rows(enriched, "qualified_bet_roi")
    forecast_rows = filter_rows(enriched, "forecast_quality")
    audits = run_tape_and_pricing_audits(settled_rows=enriched)

    return {
        "sport": sport,
        "n_markets": len(enriched),
        "n_decided": len(decided),
        "n_forecast_quality": len(forecast_rows),
        "n_qualified_bet_roi": len(qualified),
        "qualification": {
            status: sum(
                1
                for r in enriched
                if qualification_status(r) == status
            )
            for status in ("strong_bet", "lean", "pass", "unknown")
        },
        "weeks": sorted(
            {
                (int(r.get("season") or 0), int(r.get("week") or 0))
                for r in enriched
            }
        ),
        "probability_models": {
            "market_baseline_legacy": _probability_report(
                legacy_market_samples
            ),
            "market_baseline_corrected": _probability_report(
                corrected_market_samples
            ),
            "reference_coin_flip": _probability_report(reference_samples),
            "fundamental": _probability_report(fund_samples),
            "blended": _probability_report(blend_samples),
        },
        "point_forecasts": point_errors,
        "model_vs_market": _delta_report(
            legacy_market_samples, blend_samples, fund_samples
        ),
        "model_vs_market_corrected": _delta_report(
            corrected_market_samples, blend_samples, fund_samples
        ),
        "bet_selection": selection,
        "returns": returns,
        "clv": clv,
        "tape_and_pricing_audits": audits,
        "metric_notes": {
            "market_baseline_legacy": (
                "Includes historical synthetic 0.5 ATS/OU market_p "
                "and unverified rows — not a real book baseline."
            ),
            "market_baseline_corrected": (
                "Only rows with book-derived market_probability_source."
            ),
            "reference_coin_flip": (
                "Diagnostic 0.5 baseline; not sportsbook market_p."
            ),
            "clv": (
                "Corrected CLV is unavailable when bet/close quotes "
                "are missing or not independently observed."
            ),
        },
    }


def _fundamental_probabilities(
    rows: list[dict[str, Any]],
    *,
    sport: str,
) -> dict[str, float]:
    """
    Leak-safe strength-only probabilities for each settled market.

    Chronological: one strength snapshot per (season, week) with
    before_week = week.
    """

    config = resolve_betting_sport(sport)
    game_teams = _load_game_team_ids(
        [
            str(r.get("event_id") or r.get("game_id") or "")
            for r in rows
        ],
        schema=config.schema,
    )
    by_week: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in rows:
        season = int(row.get("season") or 0)
        week = int(row.get("week") or 0)
        if season and week:
            by_week[(season, week)].append(row)

    out: dict[str, float] = {}
    strength_cache: dict[tuple[int, int], dict[str, Any]] = {}

    for (season, week), week_rows in sorted(by_week.items()):
        ctx = strength_cache.get((season, week))
        if ctx is None:
            try:
                ctx = load_team_strength_context(
                    season=season,
                    before_week=week,
                    sport=config,
                )
            except Exception:
                ctx = {"profiles": {}, "sport": sport}
            strength_cache[(season, week)] = ctx

        games: dict[str, dict[str, Any]] = {}
        for row in week_rows:
            eid = str(row.get("event_id") or row.get("game_id") or "")
            if eid and eid not in games:
                games[eid] = row

        fund_scores: dict[str, tuple[float, float]] = {}
        for eid, row in games.items():
            ids = game_teams.get(eid) or {}
            home_id = row.get("home_team_id") or ids.get("home_team_id")
            away_id = row.get("away_team_id") or ids.get("away_team_id")
            if not home_id or not away_id:
                continue
            try:
                sh, sa, detail = project_strength_scores(
                    home_team_id=str(home_id),
                    away_team_id=str(away_id),
                    context=ctx,
                )
            except Exception:
                continue
            if not detail.get("available") or sh is None or sa is None:
                continue
            fund_scores[eid] = (float(sh), float(sa))

        for row in week_rows:
            mid = str(row.get("market_id") or "")
            eid = str(row.get("event_id") or row.get("game_id") or "")
            scores = fund_scores.get(eid)
            if not mid or scores is None:
                continue
            p = _selection_probability_from_scores(row, scores)
            if p is not None:
                out[mid] = p
    return out


def _load_game_team_ids(
    game_ids: list[str],
    *,
    schema: str,
) -> dict[str, dict[str, str]]:
    ids = sorted({g for g in game_ids if g})
    if not ids:
        return {}
    out: dict[str, dict[str, str]] = {}
    try:
        with engine.connect() as connection:
            # Chunk to keep parameter lists bounded.
            for i in range(0, len(ids), 200):
                chunk = ids[i : i + 200]
                params = {
                    f"id_{j}": gid for j, gid in enumerate(chunk)
                }
                placeholders = ", ".join(
                    f":id_{j}" for j in range(len(chunk))
                )
                rows = connection.execute(
                    text(
                        f"""
                        SELECT game_id, home_team_id, away_team_id
                        FROM {schema}.dim_game
                        WHERE game_id IN ({placeholders})
                        """
                    ),
                    params,
                ).mappings()
                for row in rows:
                    gid = str(row.get("game_id") or "")
                    if not gid:
                        continue
                    out[gid] = {
                        "home_team_id": str(row.get("home_team_id") or ""),
                        "away_team_id": str(row.get("away_team_id") or ""),
                    }
    except Exception:
        return out
    return out


def _selection_probability_from_scores(
    row: dict[str, Any],
    scores: tuple[float, float],
) -> float | None:
    sh, sa = scores
    fund_spread = sa - sh  # away − home (matches slate model_spread)
    fund_total = sh + sa
    mtype = str(row.get("market_type") or "").lower()
    side = selection_side(
        market_type=mtype,
        selection=str(row.get("selection") or ""),
        home_team=row.get("home_team"),
        away_team=row.get("away_team"),
    )
    market_spread = num(
        row.get("market_spread")
        if row.get("market_spread") is not None
        else row.get("line")
        if mtype == "spread"
        else None
    )
    # Settled spread rows store selection line; prefer event market_spread.
    if mtype == "spread":
        # Reconstruct home-convention market spread when only selection line.
        sel_line = num(row.get("line") or row.get("bet_line"))
        ms = num(row.get("market_spread"))
        if ms is None and sel_line is not None and side == "home":
            ms = float(sel_line)
        elif ms is None and sel_line is not None and side == "away":
            ms = -float(sel_line)
        home_cover = spread_to_cover_probability(fund_spread, ms)
        if home_cover is None:
            return None
        if side == "home":
            return float(home_cover)
        if side == "away":
            return float(1.0 - home_cover)
        return None
    if mtype == "total":
        mt = num(row.get("market_total") or row.get("line"))
        over_p = total_to_over_probability(fund_total, mt)
        if over_p is None:
            return None
        if side == "over":
            return float(over_p)
        if side == "under":
            return float(1.0 - over_p)
        return None
    if mtype == "moneyline":
        home_win = win_probability_from_spread(fund_spread)
        if home_win is None:
            return None
        if side == "home":
            return float(home_win)
        if side == "away":
            return float(1.0 - home_win)
        return None
    return None


def _point_forecast_errors(rows: list[dict[str, Any]]) -> dict[str, Any]:
    spread_abs: list[float] = []
    total_abs: list[float] = []
    spread_sq: list[float] = []
    total_sq: list[float] = []
    seen_spread: set[str] = set()
    seen_total: set[str] = set()
    for row in rows:
        eid = str(row.get("event_id") or row.get("game_id") or "")
        se = num(row.get("spread_error"))
        te = num(row.get("total_error"))
        if se is not None and eid and eid not in seen_spread:
            seen_spread.add(eid)
            spread_abs.append(abs(float(se)))
            spread_sq.append(float(se) ** 2)
        if te is not None and eid and eid not in seen_total:
            seen_total.add(eid)
            total_abs.append(abs(float(te)))
            total_sq.append(float(te) ** 2)
    return {
        "spread": _error_block(spread_abs, spread_sq),
        "total": _error_block(total_abs, total_sq),
        "note": (
            "Errors are blended pregame projection vs actual "
            "(frozen tape). Absolute points."
        ),
    }


def _error_block(
    abs_errs: list[float], sq_errs: list[float]
) -> dict[str, Any]:
    if not abs_errs:
        return {"n": 0}
    return {
        "n": len(abs_errs),
        "mae": round(sum(abs_errs) / len(abs_errs), 3),
        "rmse": round(math.sqrt(sum(sq_errs) / len(sq_errs)), 3),
    }


def _probability_report(
    samples: list[tuple[float, int]],
) -> dict[str, Any]:
    if not samples:
        return {"n": 0}
    brier = sum((p - y) ** 2 for p, y in samples) / len(samples)
    logloss_vals: list[float] = []
    for p, y in samples:
        pp = min(max(p, 1e-6), 1.0 - 1e-6)
        logloss_vals.append(
            -(y * math.log(pp) + (1 - y) * math.log(1 - pp))
        )
    logloss = sum(logloss_vals) / len(logloss_vals)
    return {
        "n": len(samples),
        "brier": round(brier, 4),
        "log_loss": round(logloss, 4),
        "calibration": _calibration_buckets(samples),
        "mean_predicted": round(
            sum(p for p, _ in samples) / len(samples), 4
        ),
        "base_rate": round(
            sum(y for _, y in samples) / len(samples), 4
        ),
    }


def _calibration_buckets(
    samples: list[tuple[float, int]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lo, hi in PROB_BUCKETS:
        bucket = [(p, y) for p, y in samples if lo <= p < hi]
        if len(bucket) < 5:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        rate = sum(y for _, y in bucket) / len(bucket)
        out.append(
            {
                "bucket": f"{lo:.0%}-{hi:.0%}"
                if hi <= 1.0
                else f"{lo:.0%}+",
                "n": len(bucket),
                "mean_predicted": round(mean_p, 3),
                "actual_rate": round(rate, 3),
                "gap_pp": round((mean_p - rate) * 100.0, 1),
            }
        )
    return out


def _delta_report(
    market: list[tuple[float, int]],
    blend: list[tuple[float, int]],
    fund: list[tuple[float, int]],
) -> dict[str, Any]:
    def _brier(samples: list[tuple[float, int]]) -> float | None:
        if not samples:
            return None
        return sum((p - y) ** 2 for p, y in samples) / len(samples)

    mb = _brier(market)
    bb = _brier(blend)
    fb = _brier(fund)
    return {
        "brier_market": None if mb is None else round(mb, 4),
        "brier_fundamental": None if fb is None else round(fb, 4),
        "brier_blended": None if bb is None else round(bb, 4),
        "blend_minus_market_brier": (
            None
            if mb is None or bb is None
            else round(bb - mb, 4)
        ),
        "fundamental_minus_market_brier": (
            None
            if mb is None or fb is None
            else round(fb - mb, 4)
        ),
        "interpretation": (
            "Negative delta vs market = model improves on market "
            "(lower Brier is better)."
        ),
    }


def _selection_audit(
    decided: list[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in decided:
        status = str(row.get("bet_status") or "unknown").lower()
        by_status[status].append(row)

    bands: dict[str, Any] = {}
    for status, items in sorted(by_status.items()):
        bands[status] = _band_metrics(items, seed=seed)

    # Selected (strong+lean) vs pass on comparable edge.
    selected = [
        r
        for r in decided
        if str(r.get("bet_status") or "").lower()
        in {"strong_bet", "lean"}
    ]
    passed = [
        r
        for r in decided
        if str(r.get("bet_status") or "").lower() == "pass"
    ]
    return {
        "by_status": bands,
        "selected_vs_pass": {
            "selected": _band_metrics(selected, seed=seed),
            "pass": _band_metrics(passed, seed=seed),
            "note": (
                "Selected = Strong Bet + Lean. Compare hit rate, "
                "Brier of model_probability, and flat-1u ROI."
            ),
        },
    }


def _band_metrics(
    rows: list[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    won = sum(1 for r in rows if r.get("result") == "won")
    units = [
        unit_result(r.get("result"), r.get("bet_price") or r.get("price"))
        for r in rows
    ]
    units_f = [float(u) for u in units if u is not None]
    samples = []
    for r in rows:
        p = num(r.get("model_probability"))
        if p is None:
            continue
        y = 1 if r.get("result") == "won" else 0
        samples.append((float(p), y))
    profit = sum(units_f)
    stake = float(len(units_f))
    roi = 100.0 * profit / stake if stake else None
    return {
        "n": len(rows),
        "hit_rate": round(won / len(rows), 4),
        "brier": _probability_report(samples).get("brier"),
        "units": round(profit, 2),
        "roi_pct": None if roi is None else round(roi, 1),
        "roi_ci95": _bootstrap_mean_ci(
            units_f, seed=seed, as_roi=True
        )
        if units_f
        else None,
        "calibration": _calibration_buckets(samples),
    }


def _returns_audit(
    decided: list[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    actionable = [
        r
        for r in decided
        if str(r.get("bet_status") or "").lower()
        in {"strong_bet", "lean"}
    ]
    all_units = []
    equity: list[float] = []
    running = 0.0
    # Chronological by season/week then market_id.
    ordered = sorted(
        decided,
        key=lambda r: (
            int(r.get("season") or 0),
            int(r.get("week") or 0),
            str(r.get("market_id") or ""),
        ),
    )
    for r in ordered:
        if str(r.get("bet_status") or "").lower() not in {
            "strong_bet",
            "lean",
        }:
            continue
        u = unit_result(
            r.get("result"), r.get("bet_price") or r.get("price")
        )
        if u is None:
            continue
        all_units.append(float(u))
        running += float(u)
        equity.append(running)

    max_dd = 0.0
    peak = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = min(max_dd, v - peak)

    profit = sum(all_units)
    stake = float(len(all_units))
    return {
        "rule": (
            "Flat 1u on Strong Bet + Lean only, at historical "
            "bet_price (else price), pushes settle 0."
        ),
        "n": len(all_units),
        "units": round(profit, 2),
        "roi_pct": (
            None if not stake else round(100.0 * profit / stake, 1)
        ),
        "roi_ci95": _bootstrap_mean_ci(
            all_units, seed=seed, as_roi=True
        )
        if all_units
        else None,
        "max_drawdown_units": round(max_dd, 2),
        "by_label": {
            "strong_bet": _band_metrics(
                [
                    r
                    for r in actionable
                    if str(r.get("bet_status") or "") == "strong_bet"
                ],
                seed=seed,
            ),
            "lean": _band_metrics(
                [
                    r
                    for r in actionable
                    if str(r.get("bet_status") or "") == "lean"
                ],
                seed=seed,
            ),
        },
        "weekly": _weekly_returns(ordered),
    }


def _weekly_returns(ordered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_week: dict[tuple[int, int], list[float]] = defaultdict(list)
    for r in ordered:
        if str(r.get("bet_status") or "").lower() not in {
            "strong_bet",
            "lean",
        }:
            continue
        u = unit_result(
            r.get("result"), r.get("bet_price") or r.get("price")
        )
        if u is None:
            continue
        key = (int(r.get("season") or 0), int(r.get("week") or 0))
        by_week[key].append(float(u))
    out = []
    for (season, week), units in sorted(by_week.items()):
        profit = sum(units)
        out.append(
            {
                "season": season,
                "week": week,
                "n": len(units),
                "units": round(profit, 2),
                "roi_pct": round(100.0 * profit / len(units), 1),
            }
        )
    return out


def _clv_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actionable = [
        r
        for r in rows
        if str(r.get("bet_status") or "").lower()
        in {"strong_bet", "lean"}
    ]
    point = [
        float(r["clv"])
        for r in actionable
        if num(r.get("clv")) is not None
        and str(r.get("clv_unit") or "") == "points"
    ]
    known = [
        r for r in actionable if r.get("beat_close") is not None
    ]
    beat = [r for r in known if r.get("beat_close") is True]
    return {
        "n_actionable": len(actionable),
        "n_with_point_clv": len(point),
        "mean_clv_points": (
            None if not point else round(sum(point) / len(point), 3)
        ),
        "beat_close_pct": (
            None
            if not known
            else round(100.0 * len(beat) / len(known), 1)
        ),
        "note": (
            "CLV is diagnostic of price quality vs close, not "
            "proof of long-run ROI."
        ),
    }


def _bootstrap_mean_ci(
    values: list[float],
    *,
    seed: int,
    as_roi: bool = False,
    n_boot: int = 2000,
) -> dict[str, float] | None:
    if len(values) < 8:
        return None
    rng = random.Random(seed)
    means: list[float] = []
    n = len(values)
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        m = sum(sample) / n
        means.append(100.0 * m if as_roi else m)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return {
        "low": round(lo, 1 if as_roi else 3),
        "high": round(hi, 1 if as_roi else 3),
    }


def _game_sport_map(game_ids: list[str]) -> dict[str, str]:
    """Resolve sport from which schema owns the game_id."""

    ids = sorted({g for g in game_ids if g})
    out: dict[str, str] = {}
    if not ids:
        return out
    try:
        with engine.connect() as connection:
            for schema, sport in (
                ("fantasy_football", "NFL"),
                ("college_football", "CFB"),
            ):
                for i in range(0, len(ids), 200):
                    chunk = ids[i : i + 200]
                    params = {
                        f"id_{j}": gid for j, gid in enumerate(chunk)
                    }
                    placeholders = ", ".join(
                        f":id_{j}" for j in range(len(chunk))
                    )
                    try:
                        rows = connection.execute(
                            text(
                                f"""
                                SELECT game_id
                                FROM {schema}.dim_game
                                WHERE game_id IN ({placeholders})
                                """
                            ),
                            params,
                        ).mappings()
                    except Exception:
                        continue
                    for row in rows:
                        gid = str(row.get("game_id") or "")
                        if gid and gid not in out:
                            out[gid] = sport
    except Exception:
        return out
    return out


if __name__ == "__main__":
    import json
    import sys

    report = run_prediction_autopsy()
    json.dump(report, sys.stdout, indent=2, default=str)
