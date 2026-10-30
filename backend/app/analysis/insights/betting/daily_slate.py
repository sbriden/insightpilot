"""
Daily multi-sport bet slate generator.

Market-Probability Randomized mode:
  1) Collect today's eligible markets (ScoresAndOdds boards for all
     selected sports).
  2) Uniformly sample markets from the full eligible slate (subject
     to max_per_game), then pick each side by vig-adjusted sportsbook
     probability.
  3) Shuffle sides into singles vs parlays by risk targets, then
     allocate whole-unit exposure with a risk exponent on those
     market probabilities.

Does not use InsightPilot projections, residuals, edge, or
Strong/Lean qualification for selection or allocation.
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.analysis.insights.betting.pricing import (
    american_profit_per_unit,
    american_to_implied_prob,
    remove_vig_two_way,
    num,
)
from app.analysis.insights.betting.slate import (
    _sport_team_logo_url,
    build_betting_slate,
    list_betting_weeks,
)

_ET = ZoneInfo("America/New_York")
_DEFAULT_PRICE = -110.0
_MIN_STAKE = 1
_MAX_PICKS_HARD_CAP = 25
_SLATE_MODE = "market_probability_randomized"
_SLATE_MODE_LABEL = "Market-Probability Randomized"

# Public daily-slate sport labels. College football is NCAAF
# (not CFB) to stay consistent with NCAAB; model slate still
# uses backend sport id CFB via _MODEL_SPORT_BACKEND.
_ALL_SPORTS = ("NFL", "NCAAF", "NBA", "NHL", "MLB", "NCAAB")
_MODEL_SPORT_BACKEND = {
    "NFL": "NFL",
    "NCAAF": "CFB",
}
# Overlay live ScoresAndOdds prices onto model-slate candidates.
_MODEL_SPORT_SAO_LEAGUE = {
    "NFL": "nfl",
    "NCAAF": "ncaaf",
}
# Market-only daily slate uses ScoresAndOdds two-way boards for every
# sport. Model slate rows are one-sided (edge picks) and cannot build
# vig-normalized markets on their own.
_SAO_LEAGUES = ("nfl", "ncaaf", "nba", "nhl", "mlb", "ncaab")
_SAO_SPORT_LABEL = {
    "nfl": "NFL",
    "ncaaf": "NCAAF",
    "nba": "NBA",
    "nhl": "NHL",
    "mlb": "MLB",
    "ncaab": "NCAAB",
}

# Risk aliases: UI still sends conservative/balanced/aggressive.
# Exponent drives stake concentration; single/parlay mix and leg
# counts restore multi-bet cards while keeping market-only selection.
_RISK_PROFILES: dict[str, dict[str, Any]] = {
    "conservative": {
        "label": "Low",
        "exponent": 3.0,
        "target_singles": 4,
        "max_per_game": 1,
        "single_pct": 0.70,
        "parlay_pct": 0.30,
        "max_parlays": 2,
        "parlay_legs": (2,),
        "min_stake": _MIN_STAKE,
        "max_stake_share": 0.40,
    },
    "low": {
        "label": "Low",
        "exponent": 3.0,
        "target_singles": 4,
        "max_per_game": 1,
        "single_pct": 0.70,
        "parlay_pct": 0.30,
        "max_parlays": 2,
        "parlay_legs": (2,),
        "min_stake": _MIN_STAKE,
        "max_stake_share": 0.40,
    },
    "balanced": {
        "label": "Medium",
        "exponent": 1.5,
        "target_singles": 6,
        "max_per_game": 1,
        "single_pct": 0.60,
        "parlay_pct": 0.40,
        "max_parlays": 3,
        "parlay_legs": (2, 3),
        "min_stake": _MIN_STAKE,
        "max_stake_share": 0.35,
    },
    "medium": {
        "label": "Medium",
        "exponent": 1.5,
        "target_singles": 6,
        "max_per_game": 1,
        "single_pct": 0.60,
        "parlay_pct": 0.40,
        "max_parlays": 3,
        "parlay_legs": (2, 3),
        "min_stake": _MIN_STAKE,
        "max_stake_share": 0.35,
    },
    "aggressive": {
        "label": "High",
        "exponent": 0.75,
        "target_singles": 8,
        "max_per_game": 2,
        "single_pct": 0.45,
        "parlay_pct": 0.55,
        "max_parlays": 4,
        "parlay_legs": (2, 3, 5),
        "min_stake": _MIN_STAKE,
        "max_stake_share": 0.30,
    },
    "high": {
        "label": "High",
        "exponent": 0.75,
        "target_singles": 8,
        "max_per_game": 2,
        "single_pct": 0.45,
        "parlay_pct": 0.55,
        "max_parlays": 4,
        "parlay_legs": (2, 3, 5),
        "min_stake": _MIN_STAKE,
        "max_stake_share": 0.30,
    },
}


def list_daily_sport_availability(
    *,
    slate_date: str | date | None = None,
) -> dict[str, Any]:
    """
    Return which sports have eligible same-day markets.

    Used by the Daily Slate UI to disable sport toggles with no
    games for the selected calendar day (America/New_York).

    Availability requires at least one vig-normalizable two-sided
    market — raw one-sided model picks do not count.
    """

    target_date = _resolve_date(slate_date)
    candidates, pool_meta = _collect_candidates(
        target_date,
        sports=set(_ALL_SPORTS),
    )
    markets, _rejected = _build_eligible_markets(candidates)

    by_sport: dict[str, dict[str, Any]] = {
        sport: {
            "sport": sport,
            "available": False,
            "candidates": 0,
            "markets": 0,
            "games": 0,
        }
        for sport in _ALL_SPORTS
    }

    for sport, sport_meta in (pool_meta.get("sao_sports") or {}).items():
        if sport not in by_sport:
            continue
        games = int(sport_meta.get("games") or 0)
        by_sport[sport]["games"] = games
        if sport_meta.get("error"):
            by_sport[sport]["error"] = sport_meta.get("error")

    games_by_sport: dict[str, set[str]] = defaultdict(set)
    for market in markets:
        sport = str(market.get("sport") or "")
        if sport not in by_sport:
            continue
        by_sport[sport]["markets"] += 1
        by_sport[sport]["candidates"] += len(market.get("sides") or [])
        by_sport[sport]["available"] = True
        event_id = str(market.get("event_id") or "")
        if event_id:
            games_by_sport[sport].add(event_id)

    for sport, event_ids in games_by_sport.items():
        by_sport[sport]["games"] = max(
            int(by_sport[sport]["games"] or 0),
            len(event_ids),
        )

    available = [
        sport
        for sport, row in by_sport.items()
        if row["available"]
    ]
    return {
        "date": target_date.isoformat(),
        "timezone": "America/New_York",
        "sports": [by_sport[sport] for sport in _ALL_SPORTS],
        "available_sports": available,
        "unavailable_sports": [
            sport
            for sport in _ALL_SPORTS
            if sport not in available
        ],
    }


def _resolve_max_picks(max_picks: int | None) -> int | None:
    if max_picks is None:
        return None
    value = int(max_picks)
    if value < 1:
        raise ValueError("max_picks must be a whole number >= 1.")
    return min(value, _MAX_PICKS_HARD_CAP)


def _apply_max_picks_to_profile(
    profile: dict[str, Any],
    max_picks: int | None,
) -> dict[str, Any]:
    """
    Shrink target singles / parlays so their sum never exceeds
    ``max_picks``, preserving the risk profile's single share.
    No-op when ``max_picks`` is unset.
    """

    capped = dict(profile)
    if max_picks is None:
        return capped
    target_singles = int(capped["target_singles"])
    max_parlays = int(capped["max_parlays"])
    natural = target_singles + max_parlays
    if max_picks >= natural:
        return capped

    single_share = float(capped.get("single_pct") or 0.6)
    desired_singles = max(1, int(round(max_picks * single_share)))
    desired_singles = min(desired_singles, max_picks)
    desired_parlays = max_picks - desired_singles
    capped["target_singles"] = desired_singles
    capped["max_parlays"] = desired_parlays
    if desired_parlays <= 0:
        capped["single_pct"] = 1.0
        capped["parlay_pct"] = 0.0
    return capped


def generate_daily_betting_slate(
    *,
    total_units: float,
    max_picks: int | None = None,
    risk: str = "balanced",
    slate_date: str | date | None = None,
    sports: list[str] | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Generate a Market-Probability Randomized daily bet slate.

    Markets are sampled uniformly from the full eligible slate
    (subject to ``max_per_game``). Each side is then drawn from
    vig-adjusted sportsbook probabilities. Allocation uses
    ``p ^ risk_exponent`` then min/max stake clamps. Model
    projections, residuals, edge, and qualification grades are
    not used. Optional ``max_picks`` caps total positions
    (singles + parlays); omit for no cap.
    """

    units = int(round(float(total_units or 0.0)))
    if units < 1:
        raise ValueError("total_units must be a whole number >= 1.")
    picks_cap = _resolve_max_picks(max_picks)

    risk_key = str(risk or "balanced").strip().lower()
    if risk_key not in _RISK_PROFILES:
        risk_key = "balanced"
    profile = _apply_max_picks_to_profile(
        dict(_RISK_PROFILES[risk_key]),
        picks_cap,
    )
    # Canonical risk key for API/UI aliases (low/medium/high).
    risk_label = str(profile["label"])
    if risk_key in {"low", "medium", "high"}:
        risk_out = {
            "Low": "conservative",
            "Medium": "balanced",
            "High": "aggressive",
        }[risk_label]
    else:
        risk_out = risk_key

    selected_sports = _normalize_sports(sports)
    target_date = _resolve_date(slate_date)
    rng = random.Random(seed)
    generated_at = datetime.now(timezone.utc).isoformat()

    candidates, pool_meta = _collect_candidates(
        target_date,
        sports=selected_sports,
    )
    markets, rejected = _build_eligible_markets(candidates)
    if not markets:
        raise ValueError(
            f"No eligible two-sided markets for "
            f"{target_date.isoformat()} in "
            f"{', '.join(sorted(selected_sports))}. "
            "Refresh ScoresAndOdds odds and ensure selected "
            "sports have games today with valid prices on "
            "both sides."
        )

    min_stake = int(profile["min_stake"])
    max_stake = max(
        min_stake,
        int(units * float(profile["max_stake_share"])),
    )
    if units < min_stake:
        raise ValueError(
            f"Budget of {units}u cannot fund any bets at the "
            f"minimum stake of {min_stake}u."
        )

    # Draw from the full eligible market list; max_per_game is the
    # only structural cap before card-size targets apply.
    selected_markets = _sample_markets_without_replacement(
        markets,
        count=len(markets),
        max_per_game=int(profile["max_per_game"]),
        rng=rng,
    )
    if not selected_markets:
        raise ValueError(
            "Unable to sample any markets from today's eligible pool."
        )

    selected_sides: list[dict[str, Any]] = []
    for market in selected_markets:
        selected_sides.append(_sample_market_side(market, rng))

    singles, parlays, unallocated, unalloc_reason = (
        _allocate_singles_and_parlays(
            selected_sides,
            total_units=units,
            profile=profile,
            risk_label=risk_label,
            generated_at=generated_at,
            rng=rng,
            min_stake=min_stake,
            max_stake=max_stake,
            max_picks=picks_cap,
        )
    )
    picks = singles + parlays
    allocated = int(sum(int(p.get("units") or 0) for p in picks))
    if unallocated is None:
        unallocated = max(0, units - allocated)
    sports_used = sorted(
        {
            str(p.get("sport") or "")
            for p in picks
            if p.get("sport") and p.get("sport") != "MULTI"
        }
        | {
            str(leg.get("sport") or "")
            for p in parlays
            for leg in (p.get("legs") or [])
            if leg.get("sport")
        }
    )

    return {
        "date": target_date.isoformat(),
        "risk": risk_out,
        "risk_label": risk_label,
        "slate_mode": _SLATE_MODE,
        "slate_mode_label": _SLATE_MODE_LABEL,
        "total_units": units,
        "max_picks": picks_cap,
        "allocated_units": allocated,
        "unallocated_units": int(unallocated),
        "unallocated_reason": unalloc_reason,
        "sports": sports_used,
        "sports_requested": sorted(selected_sports),
        "picks": picks,
        "meta": {
            "candidate_count": len(candidates),
            "eligible_markets": len(markets),
            "rejected_markets": len(rejected),
            "selected_bets": len(picks),
            "sampled_markets": len(selected_markets),
            "singles": len(singles),
            "parlays": len(parlays),
            "max_picks": picks_cap,
            "timezone": "America/New_York",
            "selection": (
                "full_slate_uniform_markets_"
                "probability_weighted_sides"
            ),
            "selection_method": (
                "sample_side_from_vig_adjusted_market_probs"
            ),
            "allocation": "probability_exponent_normalized",
            "allocation_exponent": float(profile["exponent"]),
            "risk_label": risk_label,
            "min_stake": min_stake,
            "max_stake": max_stake,
            "unit_sizing": "whole_units",
            "slate_mode": _SLATE_MODE,
            "slate_mode_label": _SLATE_MODE_LABEL,
            "probability_note": (
                "Win probabilities are vig-adjusted sportsbook "
                "implied probabilities, not InsightPilot "
                "predictions."
            ),
            "parlay_probability_note": (
                "Parlay win probability is the product of leg "
                "market probabilities (illustrative; assumes "
                "independence)."
            ),
            "pool": pool_meta,
            "rejected": rejected[:50],
            "seed": seed,
            "generated_at": generated_at,
        },
    }


def _normalize_sports(sports: list[str] | None) -> set[str]:
    if not sports:
        return set(_ALL_SPORTS)
    selected: set[str] = set()
    for raw in sports:
        key = str(raw or "").strip().upper()
        if key in {"CFB", "NCAAF", "COLLEGE", "NCAA"}:
            key = "NCAAF"
        if key in _ALL_SPORTS:
            selected.add(key)
    if not selected:
        raise ValueError(
            "No valid sports selected. Choose from "
            + ", ".join(_ALL_SPORTS)
            + "."
        )
    return selected


def _resolve_date(value: str | date | None) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if value:
        text = str(value).strip()
        if text:
            return date.fromisoformat(text[:10])
    return datetime.now(_ET).date()


def _collect_candidates(
    target_date: date,
    *,
    sports: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Collect two-sided sportsbook candidates for the ET calendar day.

    NFL/NCAAF use ScoresAndOdds boards (both sides + live prices).
    The InsightPilot model slate is one-sided edge picks and is not
    used as the selection pool in market-probability mode.
    """

    candidates: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "model_sports": {},
        "sao_sports": {},
        "sports_requested": sorted(sports),
    }

    for league in _SAO_LEAGUES:
        label = _SAO_SPORT_LABEL[league]
        if label not in sports:
            continue
        rows, sport_meta = _candidates_from_sao(
            league=league,
            target_date=target_date,
        )
        # Attach model-slate logos when the schedule matchup aligns.
        if label in _MODEL_SPORT_BACKEND and rows:
            rows = _attach_model_logos_to_sao_rows(
                rows,
                public_sport=label,
                target_date=target_date,
            )
        candidates.extend(rows)
        meta["sao_sports"][label] = sport_meta

    # Deduplicate by stable candidate id.
    by_id: dict[str, dict[str, Any]] = {}
    for row in candidates:
        by_id[str(row["candidate_id"])] = row
    return list(by_id.values()), meta


def _candidates_from_model_slate(
    *,
    sport: str,
    target_date: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {
        "sport": sport,
        "events_today": 0,
        "candidates": 0,
        "error": None,
    }
    try:
        weeks = list_betting_weeks(sport=sport)
        season = weeks.get("season")
        week = weeks.get("current_week")
        if week is None:
            available = weeks.get("weeks") or []
            week = available[-1] if available else None
        if season is None or week is None:
            meta["error"] = "No season/week available."
            return [], meta
        slate = build_betting_slate(
            season=int(season),
            week=int(week),
            sport=sport,
        )
    except Exception as exc:
        meta["error"] = str(exc)
        return [], meta

    events = {
        str(event.get("event_id") or ""): event
        for event in (slate.get("events") or [])
        if event.get("event_id")
    }
    today_event_ids = {
        eid
        for eid, event in events.items()
        if _event_on_date(event, target_date)
        and not _event_started(event)
    }
    meta["events_today"] = len(today_event_ids)
    meta["season"] = season
    meta["week"] = week

    rows: list[dict[str, Any]] = []
    for market in slate.get("markets") or []:
        event_id = str(market.get("event_id") or "")
        if event_id not in today_event_ids:
            continue
        market_type = str(market.get("market_type") or "").lower()
        if market_type not in {"spread", "total", "moneyline"}:
            continue
        selection = str(market.get("selection") or "").strip()
        if not selection:
            continue
        price = num(market.get("price"))
        # Spreads/totals may use assumed −110; moneylines need a real
        # offered price (filled later from ScoresAndOdds when possible).
        if price is None and market_type != "moneyline":
            price = _DEFAULT_PRICE
        implied = (
            american_to_implied_prob(price)
            if price is not None
            else None
        )
        # Market-only mode: keep schedule rows even without a price so
        # SAO enrichment can fill moneylines. Selection ignores any
        # model_probability / residual / edge fields on the slate.
        if implied is None and price is None and market_type != "moneyline":
            continue
        event = events.get(event_id) or {}
        rows.append(
            {
                "candidate_id": (
                    f"{sport}:{market.get('market_id') or selection}"
                ),
                "sport": sport,
                "event_id": event_id,
                "event_label": (
                    market.get("event_label")
                    or event.get("label")
                    or event_id
                ),
                "market_type": market_type,
                "selection": selection,
                "line": num(market.get("line")),
                "price": float(price) if price is not None else None,
                "home_team": market.get("home_team")
                or event.get("home_team"),
                "away_team": market.get("away_team")
                or event.get("away_team"),
                "home_logo_url": (
                    market.get("home_logo_url")
                    or event.get("home_logo_url")
                ),
                "away_logo_url": (
                    market.get("away_logo_url")
                    or event.get("away_logo_url")
                ),
                "start_time": market.get("start_time")
                or event.get("start_time"),
                "raw_implied_probability": (
                    float(implied) if implied is not None else None
                ),
                "probability_source": (
                    "american_implied"
                    if implied is not None
                    else "pending_sao"
                ),
                "source": "model_slate",
            }
        )
    meta["candidates"] = len(rows)
    return rows, meta


def _enrich_model_candidates_with_sao(
    rows: list[dict[str, Any]],
    *,
    league: str,
    target_date: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Overlay ScoresAndOdds consensus prices onto model-slate picks.

    Model spreads/totals often carry assumed −110 juice and moneylines
    may be missing entirely. SAO supplies the live offered prices.
    """

    meta: dict[str, Any] = {
        "league": league,
        "matched": 0,
        "priced": 0,
        "dropped_unpriced": 0,
        "source": None,
        "error": None,
    }
    if not rows:
        return rows, meta

    games: list[dict[str, Any]] = []
    try:
        from app.sources import scoresandodds as sao

        sao_rows, _fetch_meta = sao.fetch_odds_rows(
            league,
            dates=(
                [target_date.isoformat()]
                if league in {"nba", "nhl", "mlb", "ncaab"}
                else None
            ),
            weeks=None,
            season=None,
        )
        games = [
            row
            for row in sao_rows
            if _sao_row_on_date(row, target_date)
            or not row.get("start_time")
        ]
        # Week-based football boards already scope to current week;
        # still keep games whose ET calendar day matches when known.
        if not games and sao_rows:
            games = list(sao_rows)
        meta["source"] = "scoresandodds_live"
        meta["sao_games"] = len(games)
    except Exception as exc:
        meta["error"] = str(exc)
        # Keep model rows; drop still-unpriced moneylines below.
        games = []

    by_matchup = _index_sao_games_by_matchup(games)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        home = str(updated.get("home_team") or "").upper()
        away = str(updated.get("away_team") or "").upper()
        game = by_matchup.get((away, home))
        flipped = False
        if not game:
            game = by_matchup.get((home, away))
            flipped = bool(game)
        if game:
            meta["matched"] += 1
            updated = _apply_sao_price_to_candidate(
                updated,
                game,
                flipped=flipped,
            )
            if updated.get("price") is not None:
                meta["priced"] += 1
                updated["price_source"] = "scoresandodds"

        price = num(updated.get("price"))
        if price is None:
            # Never show an unpriced / fabricated moneyline.
            if str(updated.get("market_type") or "") == "moneyline":
                meta["dropped_unpriced"] += 1
                continue
            updated["price"] = _DEFAULT_PRICE
            price = _DEFAULT_PRICE

        implied = american_to_implied_prob(price)
        if implied is not None:
            updated["raw_implied_probability"] = float(implied)
            updated["probability_source"] = "american_implied"
        if game and (
            game.get("as_of") or game.get("quote_timestamp")
        ):
            updated["quote_timestamp"] = (
                game.get("quote_timestamp") or game.get("as_of")
            )

        enriched.append(updated)

    meta["candidates"] = len(enriched)
    return enriched, meta


def _index_sao_games_by_matchup(
    games: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for game in games:
        home = str(game.get("home_abbr") or "").upper()
        away = str(game.get("away_abbr") or "").upper()
        if not home or not away:
            continue
        index[(away, home)] = game
    return index


def _apply_sao_price_to_candidate(
    row: dict[str, Any],
    game: dict[str, Any],
    *,
    flipped: bool,
) -> dict[str, Any]:
    market_type = str(row.get("market_type") or "").lower()
    selection = str(row.get("selection") or "").strip().upper()
    home = str(row.get("home_team") or "").upper()
    away = str(row.get("away_team") or "").upper()

    home_ml = num(game.get("home_moneyline"))
    away_ml = num(game.get("away_moneyline"))
    spread_price = num(game.get("spread_price"))
    over_price = num(game.get("total_over_price"))
    under_price = num(game.get("total_under_price"))
    if flipped:
        home_ml, away_ml = away_ml, home_ml

    if market_type == "moneyline":
        if selection == home or selection.startswith(f"{home} "):
            if home_ml is not None:
                row["price"] = float(home_ml)
        elif selection == away or selection.startswith(f"{away} "):
            if away_ml is not None:
                row["price"] = float(away_ml)
        return row

    if market_type == "spread" and spread_price is not None:
        row["price"] = float(spread_price)
        return row

    if market_type == "total":
        if selection.startswith("OVER") and over_price is not None:
            row["price"] = float(over_price)
        elif selection.startswith("UNDER") and under_price is not None:
            row["price"] = float(under_price)
        return row

    return row


def _candidates_from_sao(
    *,
    league: str,
    target_date: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sport = _SAO_SPORT_LABEL[league]
    meta: dict[str, Any] = {
        "sport": sport,
        "league": league,
        "games": 0,
        "candidates": 0,
        "source": None,
        "error": None,
    }
    # Prefer the live ScoresAndOdds board for the ET calendar day.
    # A partial sports_odds DB snapshot (e.g. only early tip-offs)
    # must not hide the rest of tonight's slate.
    games: list[dict[str, Any]] = []
    try:
        from app.sources import scoresandodds as sao

        # Week boards (NFL/NCAAF) ignore dates= and return the
        # current week; slate boards use the ET calendar date.
        rows, _fetch_meta = sao.fetch_odds_rows(
            league,
            dates=[target_date.isoformat()],
        )
        games = [
            row
            for row in rows
            if _sao_row_on_date(row, target_date)
            and not _event_started(
                {
                    "start_time": row.get("start_time"),
                    "status": row.get("status"),
                }
            )
        ]
        meta["source"] = "scoresandodds_live"
    except Exception as exc:
        meta["live_error"] = str(exc)
        games = []

    if not games:
        try:
            games = _load_sao_games_for_date(league, target_date)
            meta["source"] = "sports_odds_db"
        except Exception as exc:
            meta["error"] = str(exc)
            return [], meta

    if not games and meta.get("live_error") and not meta.get("error"):
        meta["error"] = meta["live_error"]

    meta["games"] = len(games)
    candidates: list[dict[str, Any]] = []
    for game in games:
        candidates.extend(
            _expand_sao_game_candidates(game, sport=sport, league=league)
        )
    meta["candidates"] = len(candidates)
    return candidates, meta


def _attach_model_logos_to_sao_rows(
    rows: list[dict[str, Any]],
    *,
    public_sport: str,
    target_date: date,
) -> list[dict[str, Any]]:
    """
    Copy home/away logo URLs from the model schedule when abbreviations
    match. Fall back to dim_team ESPN ids by abbr — CFB date-only
    schedules often land one ET calendar day off midnight-UTC SAO
    tips (e.g. SHSU @ MOST).
    """

    backend = _MODEL_SPORT_BACKEND.get(public_sport)
    if not backend or not rows:
        return rows

    logos: dict[tuple[str, str], dict[str, Any]] = {}
    # Search adjacent ET days — date-only CFB kickoffs skew vs SAO.
    for offset in (0, -1, 1):
        day = date.fromordinal(target_date.toordinal() + offset)
        try:
            model_rows, _meta = _candidates_from_model_slate(
                sport=backend,
                target_date=day,
            )
        except Exception:
            continue
        for model in model_rows:
            home = str(model.get("home_team") or "").upper()
            away = str(model.get("away_team") or "").upper()
            if not home or not away:
                continue
            key = (away, home)
            if key in logos:
                continue
            logos[key] = {
                "home_logo_url": model.get("home_logo_url"),
                "away_logo_url": model.get("away_logo_url"),
            }

    logo_by_abbr = _team_logo_urls_by_abbreviation(public_sport)

    enriched: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        home = str(updated.get("home_team") or "").upper()
        away = str(updated.get("away_team") or "").upper()
        key = (away, home)
        match = logos.get(key) or logos.get((home, away))
        if match:
            if match.get("home_logo_url") and not updated.get(
                "home_logo_url"
            ):
                # Respect flipped matchup if we matched reversed key.
                if key in logos:
                    updated["home_logo_url"] = match["home_logo_url"]
                    updated["away_logo_url"] = (
                        match.get("away_logo_url")
                        or updated.get("away_logo_url")
                    )
                else:
                    updated["home_logo_url"] = match.get(
                        "away_logo_url"
                    )
                    updated["away_logo_url"] = match.get(
                        "home_logo_url"
                    )
            elif match.get("away_logo_url") and not updated.get(
                "away_logo_url"
            ):
                if key in logos:
                    updated["away_logo_url"] = match["away_logo_url"]

        if not updated.get("home_logo_url") and home:
            updated["home_logo_url"] = logo_by_abbr.get(home) or (
                _sport_team_logo_url(
                    "NFL", None, abbreviation=home
                )
                if backend == "NFL"
                else None
            )
        if not updated.get("away_logo_url") and away:
            updated["away_logo_url"] = logo_by_abbr.get(away) or (
                _sport_team_logo_url(
                    "NFL", None, abbreviation=away
                )
                if backend == "NFL"
                else None
            )
        enriched.append(updated)
    return enriched


def _team_logo_urls_by_abbreviation(
    public_sport: str,
) -> dict[str, str]:
    """Map team abbreviation → ESPN CDN logo URL for logo backfill."""

    backend = _MODEL_SPORT_BACKEND.get(public_sport)
    if backend == "NFL":
        # Abbreviation paths are enough for NFL CDN filenames.
        return {}
    if backend != "CFB":
        return {}

    try:
        from app.canonical.cfb.dim_team import get_dim_team
    except Exception:
        return {}

    try:
        teams = get_dim_team(force_refresh=False, persist=False)
    except Exception:
        return {}
    if teams is None or teams.empty:
        return {}

    import json

    out: dict[str, str] = {}
    for row in teams.to_dict(orient="records"):
        abbr = str(row.get("team_abbreviation") or "").strip().upper()
        if not abbr:
            continue
        source_ids = row.get("source_ids") or {}
        if isinstance(source_ids, str):
            try:
                source_ids = json.loads(source_ids)
            except Exception:
                source_ids = {}
        espn_id = None
        if isinstance(source_ids, dict):
            espn_id = source_ids.get("espn_team_id")
        url = _sport_team_logo_url(
            "CFB",
            espn_id,
            abbreviation=abbr,
        )
        if url:
            out[abbr] = url
    return out


def _load_sao_games_for_date(
    league: str,
    target_date: date,
) -> list[dict[str, Any]]:
    from app.canonical.sports_odds.fact_game_market import (
        load_fact_game_market_from_db,
    )

    frame = load_fact_game_market_from_db(leagues=[league])
    if frame is None or frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        start_time = record.get("start_time") or record.get(
            "timestamp"
        )
        # Prefer ET calendar day from kickoff so late West Coast
        # tips (UTC next-day) stay on tonight's slate. Fall back to
        # stored game_date when start_time is missing/unusable.
        if start_time:
            on_date = _sao_row_on_date(
                {"start_time": start_time},
                target_date,
            )
        else:
            on_date = False
        if not on_date:
            game_date = record.get("game_date")
            if game_date is None:
                continue
            if hasattr(game_date, "date"):
                game_date = game_date.date()
            elif isinstance(game_date, str):
                try:
                    game_date = date.fromisoformat(game_date[:10])
                except ValueError:
                    continue
            if game_date != target_date:
                continue
        if _event_started(
            {
                "start_time": start_time,
                "status": record.get("status"),
            }
        ):
            continue
        rows.append(
            {
                "provider_game_id": str(record.get("game_id") or ""),
                "home_abbr": record.get("home_abbr"),
                "away_abbr": record.get("away_abbr"),
                "home_name": record.get("home_name"),
                "away_name": record.get("away_name"),
                "start_time": start_time,
                "spread": num(record.get("spread")),
                "over_under": num(record.get("over_under")),
                "home_moneyline": num(record.get("home_moneyline")),
                "away_moneyline": num(record.get("away_moneyline")),
                "status": record.get("status"),
            }
        )
    return rows


def _sao_row_on_date(row: dict[str, Any], target_date: date) -> bool:
    start = row.get("start_time")
    if not start:
        return True
    parsed = _parse_dt(start)
    if parsed is None:
        return True
    return parsed.astimezone(_ET).date() == target_date


def _expand_sao_game_candidates(
    game: dict[str, Any],
    *,
    sport: str,
    league: str,
) -> list[dict[str, Any]]:
    home = str(game.get("home_abbr") or "").upper()
    away = str(game.get("away_abbr") or "").upper()
    if not home or not away:
        return []
    event_id = str(
        game.get("provider_game_id")
        or game.get("game_id")
        or f"{league}:{away}@{home}"
    )
    label = f"{away} @ {home}"
    start = game.get("start_time")
    spread = num(game.get("spread"))
    total = num(game.get("over_under"))
    home_ml = num(game.get("home_moneyline"))
    away_ml = num(game.get("away_moneyline"))
    spread_price = num(game.get("spread_price")) or _DEFAULT_PRICE
    over_price = num(game.get("total_over_price")) or _DEFAULT_PRICE
    under_price = num(game.get("total_under_price")) or _DEFAULT_PRICE

    rows: list[dict[str, Any]] = []

    def add(
        *,
        market_type: str,
        selection: str,
        line: float | None,
        price: float,
        side_key: str,
    ) -> None:
        implied = american_to_implied_prob(price)
        if implied is None:
            return
        rows.append(
            {
                "candidate_id": (
                    f"{sport}:{event_id}:{market_type}:{side_key}"
                ),
                "sport": sport,
                "event_id": event_id,
                "event_label": label,
                "market_type": market_type,
                "selection": selection,
                "line": line,
                "price": float(price),
                "home_team": home,
                "away_team": away,
                "start_time": start,
                "raw_implied_probability": float(implied),
                "probability_source": "american_implied",
                "quote_timestamp": game.get("quote_timestamp")
                or game.get("as_of"),
                "source": "scoresandodds",
            }
        )

    if spread is not None:
        add(
            market_type="spread",
            selection=f"{home} {spread:+g}",
            line=spread,
            price=float(spread_price),
            side_key="home",
        )
        add(
            market_type="spread",
            selection=f"{away} {-spread:+g}",
            line=-spread,
            price=float(spread_price),
            side_key="away",
        )
    if total is not None:
        add(
            market_type="total",
            selection=f"Over {total:g}",
            line=total,
            price=float(over_price),
            side_key="over",
        )
        add(
            market_type="total",
            selection=f"Under {total:g}",
            line=total,
            price=float(under_price),
            side_key="under",
        )
    if home_ml is not None:
        add(
            market_type="moneyline",
            selection=home,
            line=None,
            price=float(home_ml),
            side_key="home_ml",
        )
    if away_ml is not None:
        add(
            market_type="moneyline",
            selection=away,
            line=None,
            price=float(away_ml),
            side_key="away_ml",
        )
    return rows


def _build_eligible_markets(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Pair candidate sides into vig-normalized two-way markets.

    Rejects rows with missing/invalid odds and groups that cannot
    form a complete two-sided market. Never fabricates the missing
    side's probability.
    """

    rejected: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = (
        defaultdict(list)
    )

    for row in candidates:
        price = num(row.get("price"))
        raw = american_to_implied_prob(price)
        if price is None or raw is None:
            rejected.append(
                {
                    "reason": "missing_or_invalid_odds",
                    "candidate_id": row.get("candidate_id"),
                    "sport": row.get("sport"),
                    "event_id": row.get("event_id"),
                    "market_type": row.get("market_type"),
                    "selection": row.get("selection"),
                }
            )
            continue
        key = (
            str(row.get("sport") or ""),
            str(row.get("event_id") or ""),
            str(row.get("market_type") or "").lower(),
        )
        if not key[0] or not key[1] or key[2] not in {
            "spread",
            "total",
            "moneyline",
        }:
            rejected.append(
                {
                    "reason": "unsupported_market",
                    "candidate_id": row.get("candidate_id"),
                }
            )
            continue
        enriched = dict(row)
        enriched["price"] = float(price)
        enriched["raw_implied_probability"] = float(raw)
        groups[key].append(enriched)

    markets: list[dict[str, Any]] = []
    for key, sides in groups.items():
        sport, event_id, market_type = key
        pair = _pair_two_sides(sides, market_type=market_type)
        if pair is None:
            rejected.append(
                {
                    "reason": "incomplete_two_way_market",
                    "sport": sport,
                    "event_id": event_id,
                    "market_type": market_type,
                    "side_count": len(sides),
                }
            )
            continue
        side_a, side_b = pair
        fair_a, fair_b = remove_vig_two_way(
            side_a["raw_implied_probability"],
            side_b["raw_implied_probability"],
        )
        if fair_a is None or fair_b is None:
            rejected.append(
                {
                    "reason": "unable_to_normalize_probabilities",
                    "sport": sport,
                    "event_id": event_id,
                    "market_type": market_type,
                }
            )
            continue
        market_key = f"{sport}:{event_id}:{market_type}"
        markets.append(
            {
                "market_key": market_key,
                "sport": sport,
                "event_id": event_id,
                "market_type": market_type,
                "event_label": (
                    side_a.get("event_label")
                    or side_b.get("event_label")
                ),
                "home_team": side_a.get("home_team")
                or side_b.get("home_team"),
                "away_team": side_a.get("away_team")
                or side_b.get("away_team"),
                "home_logo_url": side_a.get("home_logo_url")
                or side_b.get("home_logo_url"),
                "away_logo_url": side_a.get("away_logo_url")
                or side_b.get("away_logo_url"),
                "start_time": side_a.get("start_time")
                or side_b.get("start_time"),
                "quote_timestamp": side_a.get("quote_timestamp")
                or side_b.get("quote_timestamp"),
                "probability_source": "vig_adjusted_two_way_american",
                "sides": [
                    {
                        **side_a,
                        "fair_probability": float(fair_a),
                        "market_key": market_key,
                    },
                    {
                        **side_b,
                        "fair_probability": float(fair_b),
                        "market_key": market_key,
                    },
                ],
            }
        )
    return markets, rejected


def _pair_two_sides(
    sides: list[dict[str, Any]],
    *,
    market_type: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Choose exactly two competing outcomes for a market."""

    unique: dict[str, dict[str, Any]] = {}
    for row in sides:
        cid = str(row.get("candidate_id") or id(row))
        unique[cid] = row
    rows = list(unique.values())
    if len(rows) < 2:
        return None

    if market_type == "total":
        overs = [
            r
            for r in rows
            if str(r.get("selection") or "").lower().startswith("over")
        ]
        unders = [
            r
            for r in rows
            if str(r.get("selection") or "")
            .lower()
            .startswith("under")
        ]
        if overs and unders:
            return overs[0], unders[0]
        return None

    if market_type == "moneyline":
        home = next(
            (
                r
                for r in rows
                if str(r.get("selection") or "").upper()
                == str(r.get("home_team") or "").upper()
            ),
            None,
        )
        away = next(
            (
                r
                for r in rows
                if str(r.get("selection") or "").upper()
                == str(r.get("away_team") or "").upper()
            ),
            None,
        )
        if home is not None and away is not None:
            return home, away
        return rows[0], rows[1]

    # spread: prefer home/away team prefixes, else first two.
    home = next(
        (
            r
            for r in rows
            if str(r.get("home_team") or "")
            and str(r.get("selection") or "")
            .upper()
            .startswith(str(r.get("home_team") or "").upper())
        ),
        None,
    )
    away = next(
        (
            r
            for r in rows
            if str(r.get("away_team") or "")
            and str(r.get("selection") or "")
            .upper()
            .startswith(str(r.get("away_team") or "").upper())
        ),
        None,
    )
    if (
        home is not None
        and away is not None
        and home.get("candidate_id") != away.get("candidate_id")
    ):
        return home, away
    return rows[0], rows[1]


def _sample_markets_without_replacement(
    markets: list[dict[str, Any]],
    *,
    count: int,
    max_per_game: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    Uniform sample of markets without replacement.

    Honors ``max_per_game`` so a single event cannot dominate the
    pool when multiple market types are available.
    """

    ordered = list(markets)
    rng.shuffle(ordered)
    selected: list[dict[str, Any]] = []
    per_game: dict[str, int] = {}
    seen_keys: set[str] = set()

    for market in ordered:
        if len(selected) >= count:
            break
        key = str(market.get("market_key") or "")
        if key in seen_keys:
            continue
        event_id = str(market.get("event_id") or "")
        if per_game.get(event_id, 0) >= max_per_game:
            continue
        selected.append(market)
        seen_keys.add(key)
        per_game[event_id] = per_game.get(event_id, 0) + 1
    return selected


def _sample_market_side(
    market: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    """
    Draw one side from the market's vig-adjusted probability mass.

    For two sides with fair probs p and 1-p: select A when u < p_A.
    """

    sides = list(market.get("sides") or [])
    if not sides:
        raise ValueError("Market has no sides to sample.")
    if len(sides) == 1:
        chosen = dict(sides[0])
        chosen["selection_probability"] = float(
            chosen.get("fair_probability") or 1.0
        )
        chosen["selection_method"] = "single_outcome"
        return chosen

    u = rng.random()
    cumulative = 0.0
    chosen = sides[-1]
    for side in sides:
        cumulative += float(side["fair_probability"])
        if u < cumulative:
            chosen = side
            break
    result = dict(chosen)
    result["selection_probability"] = float(
        chosen["fair_probability"]
    )
    result["selection_method"] = "weighted_random_market_prob"
    result["selection_u"] = u
    return result


def _allocate_singles_and_parlays(
    selected_sides: list[dict[str, Any]],
    *,
    total_units: int,
    profile: dict[str, Any],
    risk_label: str,
    generated_at: str,
    rng: random.Random,
    min_stake: int,
    max_stake: int,
    max_picks: int | None = None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
    str | None,
]:
    """
    Split market-sampled sides into singles and parlays, then
    allocate whole-unit budgets with the risk exponent.
    When set, ``max_picks`` caps total positions (singles + parlays).
    """

    total = int(total_units)
    picks_cap = max(1, int(max_picks)) if max_picks is not None else None
    exponent = float(profile["exponent"])
    single_budget = int(round(total * float(profile["single_pct"])))
    parlay_budget = total - single_budget
    if single_budget < min_stake and total >= min_stake:
        single_budget = min_stake
        parlay_budget = total - single_budget
    if parlay_budget < 0:
        parlay_budget = 0
        single_budget = total

    target_singles = min(
        int(profile["target_singles"]),
        len(selected_sides),
    )
    if picks_cap is not None:
        target_singles = min(target_singles, picks_cap)
    # Shuffle the full-slate sampled sides into singles vs parlays.
    # Side choice within each market is already probability-weighted;
    # do not re-rank favorites into the singles pool.
    shuffled = list(selected_sides)
    rng.shuffle(shuffled)
    single_pool = shuffled[:target_singles]
    parlay_pool = list(shuffled[target_singles:])

    min_legs = (
        min(profile["parlay_legs"]) if profile["parlay_legs"] else 2
    )
    if (
        int(profile["max_parlays"]) > 0
        and len(parlay_pool) < min_legs
        and len(single_pool) > 2
    ):
        move = min(
            len(single_pool) - 2,
            min_legs - len(parlay_pool),
        )
        if move > 0:
            parlay_pool = single_pool[-move:] + parlay_pool
            single_pool = single_pool[:-move]

    # Cap single count by what the single budget can fund.
    max_singles_by_budget = max(0, single_budget // min_stake)
    single_pool = single_pool[:max_singles_by_budget]

    single_stakes, single_unalloc, single_reason = (
        _allocate_by_probability(
            single_pool,
            total_units=single_budget,
            exponent=exponent,
            min_stake=min_stake,
            max_stake=max_stake,
        )
    )
    singles: list[dict[str, Any]] = []
    for side, stake in zip(single_pool, single_stakes):
        if stake < min_stake:
            continue
        if picks_cap is not None and len(singles) >= picks_cap:
            break
        singles.append(
            _pick_from_selected(
                side,
                units=stake,
                risk_label=risk_label,
                exponent=exponent,
                generated_at=generated_at,
            )
        )

    parlay_profile = dict(profile)
    if picks_cap is not None:
        parlay_slots = max(0, picks_cap - len(singles))
        parlay_profile["max_parlays"] = min(
            int(profile["max_parlays"]),
            parlay_slots,
        )
    parlays = _build_parlays(
        parlay_pool,
        budget=parlay_budget,
        profile=parlay_profile,
        risk_label=risk_label,
        exponent=exponent,
        generated_at=generated_at,
        rng=rng,
        min_stake=min_stake,
        max_stake=max_stake,
    )

    used_parlay = sum(int(p["units"]) for p in parlays)
    leftover = max(0, parlay_budget - used_parlay) + int(
        single_unalloc or 0
    )
    # Roll unused parlay/single remainder into extra singles when
    # unused market sides remain (and any pick cap still has room).
    if picks_cap is None:
        pick_room = 3
    else:
        pick_room = max(0, picks_cap - len(singles) - len(parlays))
    if leftover >= min_stake and pick_room > 0:
        used_ids = {
            str(p.get("candidate_id") or "")
            for p in singles
        }
        for p in parlays:
            for leg in p.get("legs") or []:
                used_ids.add(str(leg.get("candidate_id") or ""))
        extras_pool = [
            side
            for side in selected_sides
            if str(side.get("candidate_id") or "") not in used_ids
        ][:pick_room]
        if extras_pool:
            extra_stakes, extra_unalloc, _ = _allocate_by_probability(
                extras_pool,
                total_units=leftover,
                exponent=exponent,
                min_stake=min_stake,
                max_stake=max_stake,
            )
            for side, stake in zip(extras_pool, extra_stakes):
                if stake < min_stake:
                    continue
                if (
                    picks_cap is not None
                    and len(singles) + len(parlays) >= picks_cap
                ):
                    break
                singles.append(
                    _pick_from_selected(
                        side,
                        units=stake,
                        risk_label=risk_label,
                        exponent=exponent,
                        generated_at=generated_at,
                    )
                )
            leftover = int(extra_unalloc or 0)
        elif singles:
            # Top up the highest-probability single if capacity remains.
            singles.sort(
                key=lambda p: float(p.get("fair_probability") or 0),
                reverse=True,
            )
            room = max_stake - int(singles[0]["units"])
            add = min(leftover, max(0, room))
            if add > 0:
                singles[0]["units"] = int(singles[0]["units"]) + add
                # Refresh payout fields for the topped-up stake.
                topped = _pick_from_selected(
                    {
                        **{
                            k: singles[0].get(k)
                            for k in (
                                "candidate_id",
                                "sport",
                                "event_id",
                                "event_label",
                                "market_key",
                                "market_type",
                                "selection",
                                "line",
                                "price",
                                "home_team",
                                "away_team",
                                "home_logo_url",
                                "away_logo_url",
                                "start_time",
                                "source",
                                "quote_timestamp",
                                "selection_method",
                                "selection_probability",
                            )
                        },
                        "fair_probability": singles[0][
                            "fair_probability"
                        ],
                        "raw_implied_probability": singles[0].get(
                            "raw_implied_probability"
                        ),
                    },
                    units=int(singles[0]["units"]),
                    risk_label=risk_label,
                    exponent=exponent,
                    generated_at=generated_at,
                )
                singles[0] = topped
                leftover -= add
    elif leftover >= min_stake and singles:
        # Cap already full — fold remainder into the top single.
        singles.sort(
            key=lambda p: float(p.get("fair_probability") or 0),
            reverse=True,
        )
        room = max_stake - int(singles[0]["units"])
        add = min(leftover, max(0, room))
        if add > 0:
            singles[0]["units"] = int(singles[0]["units"]) + add
            topped = _pick_from_selected(
                {
                    **{
                        k: singles[0].get(k)
                        for k in (
                            "candidate_id",
                            "sport",
                            "event_id",
                            "event_label",
                            "market_key",
                            "market_type",
                            "selection",
                            "line",
                            "price",
                            "home_team",
                            "away_team",
                            "home_logo_url",
                            "away_logo_url",
                            "start_time",
                            "source",
                            "quote_timestamp",
                            "selection_method",
                            "selection_probability",
                        )
                    },
                    "fair_probability": singles[0][
                        "fair_probability"
                    ],
                    "raw_implied_probability": singles[0].get(
                        "raw_implied_probability"
                    ),
                },
                units=int(singles[0]["units"]),
                risk_label=risk_label,
                exponent=exponent,
                generated_at=generated_at,
            )
            singles[0] = topped

    singles, parlays, unallocated, reason = _fully_allocate_budget(
        singles,
        parlays,
        total_units=total,
        exponent=exponent,
        risk_label=risk_label,
        generated_at=generated_at,
        fallback_reason=single_reason,
    )
    return singles, parlays, unallocated, reason


def _clone_side_from_pick(pick: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a side dict so stake refreshes keep payout fields in sync."""

    return {
        "candidate_id": pick.get("candidate_id"),
        "sport": pick.get("sport"),
        "event_id": pick.get("event_id"),
        "event_label": pick.get("event_label"),
        "market_key": pick.get("market_key"),
        "market_type": pick.get("market_type"),
        "selection": pick.get("selection"),
        "line": pick.get("line"),
        "price": pick.get("price") or pick.get("offered_odds"),
        "home_team": pick.get("home_team"),
        "away_team": pick.get("away_team"),
        "home_logo_url": pick.get("home_logo_url"),
        "away_logo_url": pick.get("away_logo_url"),
        "start_time": pick.get("start_time"),
        "source": pick.get("source"),
        "quote_timestamp": pick.get("quote_timestamp"),
        "selection_method": pick.get("selection_method"),
        "selection_probability": pick.get("selection_probability"),
        "fair_probability": pick.get("fair_probability"),
        "raw_implied_probability": pick.get("raw_implied_probability"),
    }


def _with_updated_units(
    pick: dict[str, Any],
    *,
    units: int,
    risk_label: str,
    exponent: float,
    generated_at: str,
) -> dict[str, Any]:
    units = int(units)
    if pick.get("kind") == "parlay":
        legs: list[dict[str, Any]] = []
        for leg in pick.get("legs") or []:
            legs.append(
                {
                    **leg,
                    "fair_probability": float(
                        leg.get("fair_probability")
                        or leg.get("win_probability")
                        or 0.0
                    ),
                }
            )
        return _parlay_from_legs(
            legs,
            units=units,
            risk_label=risk_label,
            exponent=exponent,
            generated_at=generated_at,
        )
    return _pick_from_selected(
        _clone_side_from_pick(pick),
        units=units,
        risk_label=risk_label,
        exponent=exponent,
        generated_at=generated_at,
    )


def _fully_allocate_budget(
    singles: list[dict[str, Any]],
    parlays: list[dict[str, Any]],
    *,
    total_units: int,
    exponent: float,
    risk_label: str,
    generated_at: str,
    fallback_reason: str | None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
    str | None,
]:
    """
    Guarantee the user's full stake is placed on the card.

    Risk-profile max_stake may leave remainder after the primary
    pass; pour that remainder into existing picks (no max-stake
    ceiling) so allocated_units == total_units whenever picks exist.
    """

    total = int(total_units)
    allocated = sum(int(p["units"]) for p in singles) + sum(
        int(p["units"]) for p in parlays
    )
    leftover = max(0, total - allocated)
    if leftover <= 0:
        return singles, parlays, 0, None
    if not singles and not parlays:
        return (
            singles,
            parlays,
            leftover,
            fallback_reason or "no_picks_to_absorb_budget",
        )

    indexed: list[tuple[str, int, dict[str, Any]]] = [
        ("single", index, pick) for index, pick in enumerate(singles)
    ] + [
        ("parlay", index, pick) for index, pick in enumerate(parlays)
    ]
    stubs = [
        {
            "fair_probability": float(
                pick.get("fair_probability") or 0.0
            )
        }
        for _kind, _index, pick in indexed
    ]
    adds, rem, _ = _allocate_by_probability(
        stubs,
        total_units=leftover,
        exponent=exponent,
        min_stake=0,
        max_stake=leftover,
    )
    for add, (kind, index, pick) in zip(adds, indexed):
        if add <= 0:
            continue
        updated = _with_updated_units(
            pick,
            units=int(pick["units"]) + int(add),
            risk_label=risk_label,
            exponent=exponent,
            generated_at=generated_at,
        )
        if kind == "single":
            singles[index] = updated
        else:
            parlays[index] = updated

    if rem > 0:
        # Rounding crumbs — fold into the highest-probability pick.
        kind, index, pick = max(
            indexed,
            key=lambda row: float(
                row[2].get("fair_probability") or 0.0
            ),
        )
        current = (
            singles[index] if kind == "single" else parlays[index]
        )
        updated = _with_updated_units(
            current,
            units=int(current["units"]) + int(rem),
            risk_label=risk_label,
            exponent=exponent,
            generated_at=generated_at,
        )
        if kind == "single":
            singles[index] = updated
        else:
            parlays[index] = updated

    allocated = sum(int(p["units"]) for p in singles) + sum(
        int(p["units"]) for p in parlays
    )
    unallocated = max(0, total - allocated)
    reason = None
    if unallocated > 0:
        reason = fallback_reason or "budget_not_fully_allocated"
    return singles, parlays, unallocated, reason


def _build_parlays(
    pool: list[dict[str, Any]],
    *,
    budget: int,
    profile: dict[str, Any],
    risk_label: str,
    exponent: float,
    generated_at: str,
    rng: random.Random,
    min_stake: int,
    max_stake: int,
) -> list[dict[str, Any]]:
    budget = int(budget)
    if budget < min_stake or not pool:
        return []
    max_parlays = int(profile["max_parlays"])
    leg_options = list(profile["parlay_legs"])
    if not leg_options:
        return []

    remaining = list(pool)
    built_legs: list[list[dict[str, Any]]] = []
    for _ in range(max_parlays):
        if len(remaining) < min(leg_options):
            break
        possible = [n for n in leg_options if n <= len(remaining)]
        if not possible:
            break
        leg_count = rng.choice(possible)
        legs = _take_diverse_legs(remaining, leg_count, rng)
        if len(legs) < min(leg_options):
            break
        used = {str(leg.get("candidate_id") or "") for leg in legs}
        remaining = [
            row
            for row in remaining
            if str(row.get("candidate_id") or "") not in used
        ]
        built_legs.append(legs)

    if not built_legs:
        return []

    max_n = max(1, budget // min_stake)
    built_legs = built_legs[:max_n]
    # Allocate by joint market probability ^ exponent.
    stubs = [
        {
            "fair_probability": _joint_fair_probability(legs),
        }
        for legs in built_legs
    ]
    stakes, _, _ = _allocate_by_probability(
        stubs,
        total_units=budget,
        exponent=exponent,
        min_stake=min_stake,
        max_stake=max(
            min_stake,
            int(budget * max(0.35, float(profile["max_stake_share"]))),
        ),
    )
    parlays: list[dict[str, Any]] = []
    for legs, units in zip(built_legs, stakes):
        if units < min_stake:
            continue
        parlays.append(
            _parlay_from_legs(
                legs,
                units=units,
                risk_label=risk_label,
                exponent=exponent,
                generated_at=generated_at,
            )
        )
    return parlays


def _take_diverse_legs(
    pool: list[dict[str, Any]],
    count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Pick legs preferring different games."""

    ordered = list(pool)
    rng.shuffle(ordered)
    picked: list[dict[str, Any]] = []
    used_events: set[str] = set()
    for row in ordered:
        if len(picked) >= count:
            break
        event_id = str(row.get("event_id") or "")
        if event_id in used_events:
            continue
        picked.append(row)
        used_events.add(event_id)
    if len(picked) < count:
        for row in ordered:
            if len(picked) >= count:
                break
            if row in picked:
                continue
            # Still avoid same market_key duplicates.
            key = str(row.get("market_key") or "")
            if key and any(
                str(p.get("market_key") or "") == key for p in picked
            ):
                continue
            picked.append(row)
    return picked[:count]


def _joint_fair_probability(legs: list[dict[str, Any]]) -> float:
    joint = 1.0
    for leg in legs:
        joint *= max(float(leg.get("fair_probability") or 0.0), 1e-12)
    return joint


def _parlay_american_from_joint(joint_p: float) -> float | None:
    if joint_p <= 0 or joint_p >= 1:
        return None
    if joint_p >= 0.5:
        return round(-100.0 * joint_p / (1.0 - joint_p), 0)
    return round(100.0 * (1.0 - joint_p) / joint_p, 0)


def _parlay_offered_american(
    legs: list[dict[str, Any]],
) -> float | None:
    """Combine offered American prices into a parlay price."""

    decimal = 1.0
    for leg in legs:
        odds = num(leg.get("price") if "price" in leg else leg.get("offered_odds"))
        if odds is None:
            return None
        if odds > 0:
            decimal *= 1.0 + (odds / 100.0)
        elif odds < 0:
            decimal *= 1.0 + (100.0 / abs(odds))
        else:
            return None
    if decimal <= 1.0:
        return None
    profit = decimal - 1.0
    if profit >= 1.0:
        return round(profit * 100.0, 0)
    return round(-100.0 / profit, 0)


def _parlay_from_legs(
    legs: list[dict[str, Any]],
    *,
    units: int,
    risk_label: str,
    exponent: float,
    generated_at: str,
) -> dict[str, Any]:
    joint = _joint_fair_probability(legs)
    offered = _parlay_offered_american(legs)
    # Prefer multiplicative offered odds for payout; fall back to
    # joint-implied American only for display if prices are missing.
    price = offered if offered is not None else _parlay_american_from_joint(
        joint
    )
    profit_per_unit = american_profit_per_unit(price)
    potential_profit = (
        round(float(units) * float(profit_per_unit), 4)
        if profit_per_unit is not None
        else None
    )
    potential_payout = (
        round(float(units) + float(potential_profit), 4)
        if potential_profit is not None
        else None
    )
    sports = sorted({str(leg["sport"]) for leg in legs})
    return {
        "kind": "parlay",
        "sport": sports[0] if len(sports) == 1 else "MULTI",
        "sports": sports,
        "event_id": None,
        "event_label": " · ".join(
            str(leg.get("event_label") or "") for leg in legs
        ),
        "market_type": "parlay",
        "selection": f"{len(legs)}-leg parlay",
        "line": None,
        "price": price,
        "offered_odds": offered,
        "units": int(units),
        "win_probability": round(joint, 6),
        "fair_probability": round(joint, 6),
        "probability_source": "product_of_leg_market_probs",
        "selection_method": "market_probability_parlay_legs",
        "selection_probability": round(joint, 6),
        "risk_label": risk_label,
        "allocation_exponent": float(exponent),
        "potential_profit": potential_profit,
        "potential_payout": potential_payout,
        "generated_at": generated_at,
        "reason_codes": [
            "market_probability_randomized",
            "parlay_from_market_legs",
            f"risk_{risk_label.lower()}",
        ],
        "home_team": None,
        "away_team": None,
        "start_time": min(
            (
                str(leg.get("start_time") or "9999")
                for leg in legs
            ),
            default=None,
        ),
        "legs": [
            {
                "candidate_id": leg.get("candidate_id"),
                "sport": leg.get("sport"),
                "event_id": leg.get("event_id"),
                "event_label": leg.get("event_label"),
                "market_type": leg.get("market_type"),
                "market_key": leg.get("market_key"),
                "selection": leg.get("selection"),
                "line": leg.get("line"),
                "price": leg.get("price"),
                "home_team": leg.get("home_team"),
                "away_team": leg.get("away_team"),
                "home_logo_url": leg.get("home_logo_url"),
                "away_logo_url": leg.get("away_logo_url"),
                "win_probability": round(
                    float(leg.get("fair_probability") or 0.0),
                    6,
                ),
                "fair_probability": round(
                    float(leg.get("fair_probability") or 0.0),
                    6,
                ),
            }
            for leg in legs
        ],
        "source": "daily_slate",
        "slate_mode": _SLATE_MODE,
        "slate_mode_label": _SLATE_MODE_LABEL,
    }


def _allocate_by_probability(
    selected: list[dict[str, Any]],
    *,
    total_units: int,
    exponent: float,
    min_stake: int,
    max_stake: int,
) -> tuple[list[int], int, str | None]:
    """
    Allocate whole-unit stakes with weight = p^exponent.

    Returns (stakes, unallocated_units, reason).
    Never exceeds ``total_units``. ``min_stake`` may be 0 when
    distributing remainder onto existing picks.
    """

    n = len(selected)
    total = int(total_units)
    min_stake = max(0, int(min_stake))
    max_stake = max(min_stake, int(max_stake))

    if n == 0:
        return [], total, "no_selected_bets"
    if total <= 0:
        return [0] * n, 0, None
    if min_stake > 0 and min_stake * n > total:
        return [0] * n, total, "min_stakes_exceed_budget"

    weights = [
        max(float(row.get("fair_probability") or 0.0), 1e-12)
        ** float(exponent)
        for row in selected
    ]
    stakes = [min_stake] * n
    remaining = total - (min_stake * n)

    while remaining > 0:
        eligible = [
            i for i in range(n) if stakes[i] < max_stake
        ]
        if not eligible:
            break
        ew = [weights[i] for i in eligible]
        ew_sum = sum(ew)
        rooms = [max_stake - stakes[i] for i in eligible]
        exact = [remaining * (w / ew_sum) for w in ew]
        adds = _largest_remainder_capped(exact, remaining, rooms)
        added = sum(adds)
        if added <= 0:
            break
        for index, add in zip(eligible, adds):
            stakes[index] += int(add)
            remaining -= int(add)

    unallocated = max(0, remaining)
    reason = "max_stake_limits" if unallocated > 0 else None
    assert sum(stakes) + unallocated == total
    assert sum(stakes) <= total
    return stakes, unallocated, reason


def _largest_remainder_capped(
    exact: list[float],
    total: int,
    rooms: list[int],
) -> list[int]:
    """Integer allocation of ``total`` capped by per-slot rooms."""

    n = len(exact)
    if n == 0 or total <= 0:
        return [0] * n
    floors = [
        max(0, min(int(value), int(room)))
        for value, room in zip(exact, rooms)
    ]
    used = sum(floors)
    leftover = max(0, int(total) - used)
    order = sorted(
        range(n),
        key=lambda i: (exact[i] - int(exact[i]), -i),
        reverse=True,
    )
    result = list(floors)
    for index in order:
        if leftover <= 0:
            break
        if result[index] < rooms[index]:
            result[index] += 1
            leftover -= 1
    # If caps blocked some remainder units, leave them unassigned.
    return result


def _pick_from_selected(
    row: dict[str, Any],
    *,
    units: int,
    risk_label: str,
    exponent: float,
    generated_at: str,
) -> dict[str, Any]:
    price = num(row.get("price"))
    fair_p = float(row["fair_probability"])
    raw_p = float(
        row.get("raw_implied_probability")
        or american_to_implied_prob(price)
        or 0.0
    )
    profit_per_unit = american_profit_per_unit(price)
    potential_profit = (
        round(float(units) * float(profit_per_unit), 4)
        if profit_per_unit is not None
        else None
    )
    potential_payout = (
        round(float(units) + float(potential_profit), 4)
        if potential_profit is not None
        else None
    )
    return {
        "kind": "single",
        "candidate_id": row.get("candidate_id"),
        "sport": row["sport"],
        "event_id": row.get("event_id"),
        "event_label": row.get("event_label"),
        "market_key": row.get("market_key"),
        "market_type": row.get("market_type"),
        "selection": row.get("selection"),
        "line": row.get("line"),
        "price": price,
        "offered_odds": price,
        "units": int(units),
        "win_probability": round(fair_p, 6),
        "raw_implied_probability": round(raw_p, 6),
        "fair_probability": round(fair_p, 6),
        "probability_source": "vig_adjusted_two_way_american",
        "selection_method": row.get(
            "selection_method",
            "weighted_random_market_prob",
        ),
        "selection_probability": round(
            float(row.get("selection_probability") or fair_p),
            6,
        ),
        "risk_label": risk_label,
        "allocation_exponent": float(exponent),
        "potential_profit": potential_profit,
        "potential_payout": potential_payout,
        "quote_timestamp": row.get("quote_timestamp"),
        "generated_at": generated_at,
        "reason_codes": [
            "market_probability_randomized",
            "vig_adjusted_selection",
            f"risk_{risk_label.lower()}",
        ],
        "home_team": row.get("home_team"),
        "away_team": row.get("away_team"),
        "home_logo_url": row.get("home_logo_url"),
        "away_logo_url": row.get("away_logo_url"),
        "start_time": row.get("start_time"),
        "source": row.get("source"),
        "slate_mode": _SLATE_MODE,
        "slate_mode_label": _SLATE_MODE_LABEL,
    }


def _event_on_date(event: dict[str, Any], target_date: date) -> bool:
    for key in ("start_time", "game_date", "gameday"):
        raw = event.get(key)
        if not raw:
            continue
        if hasattr(raw, "date") and not isinstance(raw, str):
            try:
                return raw.astimezone(_ET).date() == target_date
            except Exception:
                try:
                    return raw.date() == target_date
                except Exception:
                    pass
        text = str(raw).strip()
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            # Date-only strings are calendar dates as stored.
            if "T" not in text and " " not in text:
                return text[:10] == target_date.isoformat()
            parsed = _parse_dt(text)
            if parsed is not None:
                return parsed.astimezone(_ET).date() == target_date
    return False


def _event_started(event: dict[str, Any]) -> bool:
    status = str(event.get("status") or "").lower()
    if status in {
        "final",
        "completed",
        "closed",
        "in_progress",
        "inprogress",
        "live",
    }:
        return True
    start = event.get("start_time")
    if start is None:
        return False
    # Date-only schedules (common for CFB/NCAAF) are calendar days,
    # not midnight kickoffs — keep them available through that ET day.
    if hasattr(start, "date") and not isinstance(start, datetime):
        try:
            return start < datetime.now(_ET).date()
        except Exception:
            return False
    text = str(start).strip()
    if (
        len(text) >= 10
        and text[4] == "-"
        and text[7] == "-"
        and "T" not in text
        and " " not in text
    ):
        try:
            game_day = date.fromisoformat(text[:10])
        except ValueError:
            return False
        return game_day < datetime.now(_ET).date()

    parsed = _parse_dt(start)
    if parsed is None:
        return False
    return parsed <= datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None
