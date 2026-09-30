"""DFS multi-lineup portfolio generation and analysis."""

from __future__ import annotations

import copy
import hashlib
import random
from collections import Counter
from typing import Any

from app.analysis.insights.dfs.correlation import (
    CorrelationContext,
    build_correlation_context,
    score_lineup_correlation,
    summarize_portfolio_correlations,
)
from app.analysis.insights.dfs.optimize import (
    RISK_BLEND,
    _optimize_classic,
    _optimize_showdown,
    _player_score,
)
from app.analysis.insights.dfs.showdown_scripts import (
    build_script_hints,
    load_showdown_script_context,
)
from app.analysis.insights.dfs.sites import (
    get_site_config,
    normalize_contest_type,
)
from app.analysis.insights.dfs.slate import build_dfs_slate


STRATEGY_DEFAULTS: dict[str, dict[str, float]] = {
    # Strong lineups first; only light uniqueness.
    "max_projection": {
        "default_max_exposure": 0.85,
        "max_lineup_similarity": 0.92,
        "selection_ceiling_weight": 0.05,
        "selection_leverage_weight": 0.0,
        "stage1_noise": 1.0,
        "stage1_anchor_exclude_rate": 0.0,
        "stage1_noisy_exclude_rate": 0.0,
    },
    "balanced": {
        "default_max_exposure": 0.70,
        "max_lineup_similarity": 0.80,
        "selection_ceiling_weight": 0.15,
        "selection_leverage_weight": 0.0,
        "stage1_noise": 2.5,
        "stage1_anchor_exclude_rate": 0.0,
        "stage1_noisy_exclude_rate": 0.08,
    },
    "tournament": {
        "default_max_exposure": 0.55,
        "max_lineup_similarity": 0.70,
        "selection_ceiling_weight": 0.28,
        "selection_leverage_weight": 0.12,
        "stage1_noise": 3.0,
        "stage1_anchor_exclude_rate": 0.0,
        "stage1_noisy_exclude_rate": 0.10,
    },
    "contrarian": {
        "default_max_exposure": 0.45,
        "max_lineup_similarity": 0.65,
        "selection_ceiling_weight": 0.20,
        "selection_leverage_weight": 0.22,
        "stage1_noise": 3.5,
        "stage1_anchor_exclude_rate": 0.0,
        "stage1_noisy_exclude_rate": 0.12,
    },
    # Back-compat aliases (same settings as renamed strategies).
    "cash": {
        "default_max_exposure": 0.85,
        "max_lineup_similarity": 0.92,
        "selection_ceiling_weight": 0.05,
        "selection_leverage_weight": 0.0,
        "stage1_noise": 1.0,
        "stage1_anchor_exclude_rate": 0.0,
        "stage1_noisy_exclude_rate": 0.0,
    },
    "gpp": {
        "default_max_exposure": 0.55,
        "max_lineup_similarity": 0.70,
        "selection_ceiling_weight": 0.28,
        "selection_leverage_weight": 0.12,
        "stage1_noise": 3.0,
        "stage1_anchor_exclude_rate": 0.0,
        "stage1_noisy_exclude_rate": 0.10,
    },
    "custom": {
        "default_max_exposure": 0.70,
        "max_lineup_similarity": 0.80,
        "selection_ceiling_weight": 0.15,
        "selection_leverage_weight": 0.05,
        "stage1_noise": 2.5,
        "stage1_anchor_exclude_rate": 0.0,
        "stage1_noisy_exclude_rate": 0.08,
    },
}

# Stage 1 always builds strong lineups; portfolio strategy does not
# demote chalk projection during candidate generation.
CANDIDATE_WEIGHTS: dict[str, float] = {
    "projection": 0.72,
    "floor": 0.05,
    "value": 0.10,
    "ownership": 0.0,
    "ceiling": 0.08,
    "correlation": 0.05,
}

STRATEGY_ALIASES: dict[str, str] = {
    "cash": "max_projection",
    "max_projection": "max_projection",
    "max-projection": "max_projection",
    "projection": "max_projection",
    "balanced": "balanced",
    "gpp": "tournament",
    "tournament": "tournament",
    "contrarian": "contrarian",
    "custom": "custom",
}


def _normalize_strategy_key(strategy: str | None) -> str:
    raw = str(strategy or "balanced").strip().lower()
    mapped = STRATEGY_ALIASES.get(raw, raw)
    if mapped not in STRATEGY_DEFAULTS:
        return "balanced"
    return mapped


def generate_portfolio(
    *,
    slate_id: str,
    site: str = "draftkings",
    contest_type: str = "classic",
    lineup_count: int = 20,
    strategy: str = "balanced",
    risk: str = "balanced",
    max_lineup_similarity: float | None = None,
    min_unique_players: int | None = None,
    default_max_exposure: float | None = None,
    default_max_captain_exposure: float | None = None,
    player_exposure: dict[str, Any] | None = None,
    locked_players: list[str] | None = None,
    excluded_players: list[str] | None = None,
    season: int | None = None,
    scoring: str | None = "ppr",
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Build a diversified portfolio of lineups for one slate.

    Stage 1: generate high-quality candidate lineups (no portfolio
    exposure penalties). Stage 2: select under hard portfolio
    constraints (exposure, uniqueness, game scripts).
    """

    format_key = normalize_contest_type(contest_type)
    strategy_key = _normalize_strategy_key(strategy)
    risk_key = str(risk or "balanced").strip().lower()
    if risk_key not in RISK_BLEND:
        risk_key = "balanced"

    defaults = STRATEGY_DEFAULTS[strategy_key]
    max_sim = (
        float(max_lineup_similarity)
        if max_lineup_similarity is not None
        else float(defaults["max_lineup_similarity"])
    )
    max_sim = max(0.0, min(1.0, max_sim))
    max_exp = (
        float(default_max_exposure)
        if default_max_exposure is not None
        else float(defaults["default_max_exposure"])
    )
    max_exp = max(0.05, min(1.0, max_exp))
    max_cpt_exp = (
        float(default_max_captain_exposure)
        if default_max_captain_exposure is not None
        else max_exp
    )
    max_cpt_exp = max(0.05, min(1.0, max_cpt_exp))

    count = max(1, min(int(lineup_count or 20), 100))
    exposure_cfg = _normalize_exposure_config(
        player_exposure,
        locked_players=locked_players,
        excluded_players=excluded_players,
    )

    site_config = get_site_config(site, contest_type=format_key)
    slate = build_dfs_slate(
        slate_id,
        site=site_config["id"],
        season=season,
        contest_type=format_key,
        scoring=scoring,
    )
    players = list(slate.get("players") or [])
    players = [
        player
        for player in players
        if _is_active_roster_player(player)
    ]
    if not players:
        raise ValueError(
            "Slate has no eligible Active-status players."
        )

    roster_size = len(site_config["roster"])
    unique_floor = _resolve_min_unique_players(
        min_unique_players=min_unique_players,
        max_similarity=max_sim,
        roster_size=roster_size,
    )

    # Stage 1 always optimizes strong individual lineups.
    stage1_weights = dict(CANDIDATE_WEIGHTS)
    # Stage 2 selection uses strategy-specific soft preferences
    # (ceiling/leverage) while hard constraints gate feasibility.
    stage2_defaults = dict(defaults)
    rng = random.Random(
        seed
        if seed is not None
        else _stable_seed(slate_id, site_config["id"], strategy_key)
    )
    correlation_context = build_correlation_context(
        players,
        sport="nfl",
        season=(
            int(slate["season"])
            if slate.get("season") is not None
            else season
        ),
        week=(
            int(slate["week"])
            if slate.get("week") is not None
            else None
        ),
    )
    # Keep correlation subordinate during Stage 1 so projection
    # remains the primary driver of candidate quality.
    corr_weight = float(stage1_weights.get("correlation") or 0.0)

    script_context = None
    script_allocations: list[dict[str, Any]] = []
    if format_key == "showdown":
        script_context = load_showdown_script_context(
            slate,
            lineup_count=count,
        )
        if script_context:
            script_allocations = list(
                script_context.get("allocations") or []
            )

    seen_lineup_keys: set[str] = set()
    if script_allocations:
        candidates = _generate_showdown_script_candidates(
            players=players,
            site_config=site_config,
            weights=stage1_weights,
            exposure_cfg=exposure_cfg,
            rng=rng,
            strategy_key=strategy_key,
            risk_key=risk_key,
            slate=slate,
            script_context=script_context,
            allocations=script_allocations,
            correlation_context=correlation_context,
            correlation_weight=corr_weight,
            stage_defaults=stage2_defaults,
        )
    else:
        candidate_target = max(count * 16, 80)
        candidates = _generate_candidates(
            players=players,
            site_config=site_config,
            format_key=format_key,
            weights=stage1_weights,
            exposure_cfg=exposure_cfg,
            target_count=candidate_target,
            rng=rng,
            strategy_key=strategy_key,
            risk_key=risk_key,
            slate=slate,
            seen_keys=seen_lineup_keys,
            correlation_context=correlation_context,
            correlation_weight=corr_weight,
            stage_defaults=stage2_defaults,
        )
    if not candidates:
        raise ValueError(
            "Unable to generate portfolio candidates "
            "with the current constraints."
        )

    rejection_counts: Counter[str] = Counter()
    if script_allocations:
        selected, conflicts = _select_portfolio_by_script(
            candidates=candidates,
            allocations=script_allocations,
            lineup_count=count,
            max_similarity=max_sim,
            min_unique_players=unique_floor,
            default_max_exposure=max_exp,
            default_max_captain_exposure=max_cpt_exp,
            exposure_cfg=exposure_cfg,
            strategy_defaults=stage2_defaults,
            rejection_counts=rejection_counts,
        )
    else:
        def _refill_for_selection(
            counts: Counter[str],
            captain_counts: Counter[str],
        ) -> list[dict[str, Any]]:
            at_cap = _players_at_max_exposure(
                counts,
                lineup_count=count,
                default_max_exposure=max_exp,
                exposure_cfg=exposure_cfg,
            )
            refill_cfg = dict(exposure_cfg)
            refill_exclude = set(exposure_cfg["exclude"]) | at_cap
            refill_exclude -= set(exposure_cfg["lock"])
            refill_cfg["exclude"] = sorted(refill_exclude)
            return _generate_candidates(
                players=players,
                site_config=site_config,
                format_key=format_key,
                weights=stage1_weights,
                exposure_cfg=refill_cfg,
                target_count=max(count * 6, 30),
                rng=rng,
                strategy_key=strategy_key,
                risk_key=risk_key,
                slate=slate,
                seen_keys=seen_lineup_keys,
                correlation_context=correlation_context,
                correlation_weight=corr_weight,
                stage_defaults=stage2_defaults,
            )

        selected, conflicts = _select_portfolio(
            candidates=candidates,
            lineup_count=count,
            max_similarity=max_sim,
            min_unique_players=unique_floor,
            default_max_exposure=max_exp,
            default_max_captain_exposure=max_cpt_exp,
            exposure_cfg=exposure_cfg,
            strategy_defaults=stage2_defaults,
            refill_candidates=_refill_for_selection,
            rejection_counts=rejection_counts,
        )
    analysis = analyze_portfolio(
        selected,
        slate=slate,
        max_similarity=max_sim,
        default_max_exposure=max_exp,
        default_max_captain_exposure=max_cpt_exp,
        exposure_cfg=exposure_cfg,
        conflicts=conflicts,
        requested_lineup_count=count,
        correlation_context=correlation_context,
        player_pool=players,
    )
    player_diagnostics = _build_player_diagnostics(
        candidates=candidates,
        selected=selected,
        players=players,
        exposure_cfg=exposure_cfg,
        default_max_exposure=max_exp,
        default_max_captain_exposure=max_cpt_exp,
        lineup_count=count,
        min_unique_players=unique_floor,
        max_similarity=max_sim,
        rejection_counts=rejection_counts,
        strategy_key=strategy_key,
    )

    projections = [
        float(item.get("projected_points") or 0.0)
        for item in selected
    ]
    salaries_remaining = [
        float(item.get("salary_remaining") or 0.0)
        for item in selected
    ]
    portfolio_id = (
        f"pf-{slate['slate_id']}-"
        f"{site_config['id']}-{format_key}-{count}"
    )
    portfolio = {
        "portfolio_id": portfolio_id,
        "slate_id": slate["slate_id"],
        "site": site_config["id"],
        "contest_type": format_key,
        "strategy": strategy_key,
        "risk": risk_key,
        "lineup_count": len(selected),
        "requested_lineup_count": count,
        "max_lineup_similarity": max_sim,
        "min_unique_players": unique_floor,
        "default_max_exposure": max_exp,
        "default_max_captain_exposure": max_cpt_exp,
        "constraints": exposure_cfg,
        "best_projection": (
            round(max(projections), 1) if projections else 0.0
        ),
        "lowest_projection": (
            round(min(projections), 1) if projections else 0.0
        ),
        "average_salary_remaining": (
            round(_avg(salaries_remaining), 1)
            if salaries_remaining
            else 0.0
        ),
        "unique_lineups": len(
            {
                _lineup_key(item.get("players") or [])
                for item in selected
            }
        ),
        **analysis["summary"],
    }
    if script_context:
        portfolio["game_scripts"] = {
            "favorite": script_context.get("favorite"),
            "underdog": script_context.get("underdog"),
            "home_team": script_context.get("home_team"),
            "away_team": script_context.get("away_team"),
            "projected_total": script_context.get(
                "projected_total"
            ),
            "market_total": script_context.get("market_total"),
            "market_spread": script_context.get("market_spread"),
            "allocations": script_allocations,
            "note": (
                "Showdown lineup mix follows normalized game-script "
                "weights (independent betting probabilities rescaled "
                "to 100%)."
            ),
        }

    return {
        "portfolio": portfolio,
        "lineups": selected,
        "exposure": analysis["exposure"],
        "similarity": analysis["similarity"],
        "correlation": analysis.get("correlation"),
        "core": analysis["core"],
        "differentiators": analysis["differentiators"],
        "signals": analysis["signals"],
        "alerts": analysis["alerts"],
        "player_diagnostics": player_diagnostics,
        "game_scripts": (
            portfolio.get("game_scripts")
            if script_context
            else None
        ),
        "optimization_metadata": {
            "portfolio_strategy": strategy_key,
            "portfolio_size": count,
            "candidate_lineups_generated": len(candidates),
            "candidate_lineups_selected": len(selected),
            "candidates_unique": len(candidates),
            "average_projection": portfolio.get(
                "average_projection"
            ),
            "best_projection": portfolio.get("best_projection"),
            "worst_projection": portfolio.get("lowest_projection"),
            "unique_lineups": portfolio.get("unique_lineups"),
            "average_salary_remaining": portfolio.get(
                "average_salary_remaining"
            ),
            "lineups_selected": len(selected),
            "strategy": strategy_key,
            "risk": risk_key,
            "max_lineup_similarity": max_sim,
            "min_unique_players": unique_floor,
            "default_max_exposure": max_exp,
            "constraint_conflicts": len(conflicts),
            "rejected": dict(rejection_counts),
            "game_script_driven": bool(script_allocations),
            "correlation_edges": len(correlation_context.edges),
            "stage1_weights": stage1_weights,
        },
        "slate": {
            "slate_id": slate["slate_id"],
            "label": slate.get("label"),
            "freshness": slate.get("freshness"),
            "contest_type": format_key,
        },
    }


def analyze_portfolio(
    lineups: list[dict[str, Any]],
    *,
    slate: dict[str, Any] | None = None,
    max_similarity: float = 0.75,
    default_max_exposure: float = 0.6,
    default_max_captain_exposure: float = 0.6,
    exposure_cfg: dict[str, Any] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    requested_lineup_count: int | None = None,
    correlation_context: Any | None = None,
    player_pool: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute exposure, similarity, and structured signals."""

    del slate  # reserved for future game/team enrichment
    exposure_cfg = exposure_cfg or _normalize_exposure_config(None)
    generated = len(lineups)
    # Exposure % is vs the requested portfolio size so it matches
    # the hard caps used during selection (not inflated when the
    # builder returns fewer lineups than requested).
    n = max(
        generated,
        int(requested_lineup_count or 0),
        1,
    ) if generated else 0
    if generated == 0:
        return {
            "summary": {
                "unique_players": 0,
                "average_projection": 0.0,
                "average_ceiling": 0.0,
                "average_floor": 0.0,
                "average_ownership": 0.0,
                "average_salary": 0.0,
                "average_lineup_similarity": 0.0,
                "diversity_label": "None",
            },
            "exposure": {"players": []},
            "similarity": {
                "average": 0.0,
                "most_similar_pairs": [],
            },
            "correlation": None,
            "core": [],
            "differentiators": [],
            "signals": [],
            "alerts": [],
        }

    player_counts: Counter[str] = Counter()
    captain_counts: Counter[str] = Counter()
    player_meta: dict[str, dict[str, Any]] = {}
    for lineup in lineups:
        seen: set[str] = set()
        for player in lineup.get("players") or []:
            pid = str(player.get("player_id") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            player_counts[pid] += 1
            if pid not in player_meta:
                player_meta[pid] = {
                    "player_id": pid,
                    "name": player.get("name"),
                    "position": player.get("position"),
                    "team": player.get("team"),
                    "opponent": player.get("opponent"),
                    "projection": player.get("projection"),
                    "ceiling": player.get("ceiling"),
                    "floor": player.get("floor"),
                    "projected_ownership": player.get(
                        "projected_ownership"
                    ),
                    "salary": player.get("salary"),
                }
        cpt = _captain_id(lineup)
        if cpt:
            captain_counts[cpt] += 1

    player_exposure = []
    for pid, appearances in player_counts.most_common():
        meta = player_meta[pid]
        rate = appearances / float(n)
        cpt_apps = captain_counts.get(pid, 0)
        cpt_rate = cpt_apps / float(n)
        max_allowed = float(
            exposure_cfg["max"].get(pid, default_max_exposure)
        )
        max_apps = int(max_allowed * float(n) + 1e-9)
        player_exposure.append(
            {
                **meta,
                "lineups": appearances,
                "lineup_count": n,
                "generated_lineup_count": generated,
                "exposure": round(rate, 4),
                "exposure_pct": round(rate * 100.0, 1),
                "captain_lineups": cpt_apps,
                "captain_exposure": round(cpt_rate, 4),
                "captain_exposure_pct": round(cpt_rate * 100.0, 1),
                "min_exposure": exposure_cfg["min"].get(pid),
                "max_exposure": exposure_cfg["max"].get(
                    pid, default_max_exposure
                ),
                "min_captain_exposure": exposure_cfg[
                    "captain_min"
                ].get(pid),
                "max_captain_exposure": exposure_cfg[
                    "captain_max"
                ].get(pid, default_max_captain_exposure),
                "max_allowed_exposure": round(max_allowed, 4),
                "max_allowed_lineups": max_apps,
                "remaining_capacity": max(0, max_apps - appearances),
                "locked": pid in exposure_cfg["lock"],
                "excluded": pid in exposure_cfg["exclude"],
            }
        )

    player_exposure = _append_constrained_zero_exposure(
        player_exposure,
        player_meta=player_meta,
        player_pool=player_pool or [],
        exposure_cfg=exposure_cfg,
        lineup_count=n,
        default_max_exposure=default_max_exposure,
        default_max_captain_exposure=default_max_captain_exposure,
    )

    avg_proj = _avg(
        [float(item.get("projected_points") or 0) for item in lineups]
    )
    avg_ceil = _avg(
        [
            float(item.get("projected_ceiling") or 0)
            for item in lineups
        ]
    )
    avg_floor = _avg(
        [
            float(item.get("projected_floor") or 0)
            for item in lineups
        ]
    )
    avg_own = _avg(
        [
            float(item.get("projected_ownership") or 0)
            for item in lineups
        ]
    )
    avg_sal = _avg(
        [float(item.get("salary_used") or 0) for item in lineups]
    )
    avg_sal_rem = _avg(
        [
            float(item.get("salary_remaining") or 0)
            for item in lineups
        ]
    )
    projections = [
        float(item.get("projected_points") or 0) for item in lineups
    ]

    sim = _similarity_report(lineups)
    diversity_label = _diversity_label(
        unique_players=len(player_counts),
        lineup_count=n,
        avg_similarity=sim["average"],
        max_player_exposure=(
            player_exposure[0]["exposure"]
            if player_exposure
            else 0.0
        ),
    )

    core = [
        {
            "player_id": row["player_id"],
            "name": row["name"],
            "position": row["position"],
            "exposure": row["exposure"],
            "exposure_pct": row["exposure_pct"],
            "lineups": row["lineups"],
        }
        for row in player_exposure
        if row["exposure"] >= 0.40
    ][:8]
    differentiators = [
        {
            "player_id": row["player_id"],
            "name": row["name"],
            "position": row["position"],
            "exposure": row["exposure"],
            "exposure_pct": row["exposure_pct"],
            "lineups": row["lineups"],
        }
        for row in reversed(player_exposure)
        if 0 < row["exposure"] <= 0.15
    ][:8]

    signals, alerts = _build_signals(
        player_exposure=player_exposure,
        lineup_count=n,
        unique_players=len(player_counts),
        similarity=sim,
        max_similarity=max_similarity,
        core=core,
        conflicts=conflicts or [],
    )

    correlation_summary = None
    if correlation_context is not None and lineups:
        correlation_summary = summarize_portfolio_correlations(
            lineups,
            correlation_context,
        )
        if correlation_summary.get("narrative"):
            signals.append(
                {
                    "id": "correlation-concentration",
                    "type": "CORRELATION_CONCENTRATION",
                    "severity": "info",
                    "explanation": correlation_summary["narrative"],
                }
            )

    return {
        "summary": {
            "unique_players": len(player_counts),
            "average_projection": round(avg_proj, 1),
            "average_ceiling": round(avg_ceil, 1),
            "average_floor": round(avg_floor, 1),
            "average_ownership": round(avg_own, 1),
            "average_salary": round(avg_sal),
            "average_salary_remaining": round(avg_sal_rem, 1),
            "best_projection": (
                round(max(projections), 1) if projections else 0.0
            ),
            "lowest_projection": (
                round(min(projections), 1) if projections else 0.0
            ),
            "unique_lineups": len(
                {
                    _lineup_key(item.get("players") or [])
                    for item in lineups
                }
            ),
            "average_lineup_similarity": round(sim["average"], 3),
            "diversity_label": diversity_label,
        },
        "exposure": {"players": player_exposure},
        "similarity": sim,
        "correlation": correlation_summary,
        "core": core,
        "differentiators": differentiators,
        "signals": signals,
        "alerts": alerts,
    }


def _captain_id(lineup: dict[str, Any]) -> str | None:
    for player in lineup.get("players") or []:
        slot = str(player.get("slot") or "").upper()
        if slot == "CPT" or player.get("is_captain"):
            pid = str(player.get("player_id") or "").strip()
            return pid or None
    return None


def _normalize_exposure_config(
    raw: dict[str, Any] | None,
    *,
    locked_players: list[str] | None = None,
    excluded_players: list[str] | None = None,
) -> dict[str, Any]:
    raw = raw or {}
    min_map = {
        str(key): max(0.0, min(1.0, float(value)))
        for key, value in dict(raw.get("min") or {}).items()
    }
    max_map = {
        str(key): max(0.0, min(1.0, float(value)))
        for key, value in dict(raw.get("max") or {}).items()
    }
    target_map = {
        str(key): max(0.0, min(1.0, float(value)))
        for key, value in dict(raw.get("target") or {}).items()
    }
    captain_min_map = {
        str(key): max(0.0, min(1.0, float(value)))
        for key, value in dict(raw.get("captain_min") or {}).items()
    }
    captain_max_map = {
        str(key): max(0.0, min(1.0, float(value)))
        for key, value in dict(raw.get("captain_max") or {}).items()
    }
    lock = {
        str(item).strip()
        for item in list(raw.get("lock") or [])
        + list(locked_players or [])
        if str(item).strip()
    }
    exclude = {
        str(item).strip()
        for item in list(raw.get("exclude") or [])
        + list(excluded_players or [])
        if str(item).strip()
    }
    # Locked players cannot also be excluded.
    exclude -= lock
    for pid in lock:
        min_map[pid] = 1.0
        max_map[pid] = 1.0
    for pid in exclude:
        min_map.pop(pid, None)
        max_map[pid] = 0.0
        captain_max_map[pid] = 0.0
        captain_min_map.pop(pid, None)
    # Min cannot exceed max; raise max when needed so force-include works.
    for pid, minimum in list(min_map.items()):
        if pid in exclude:
            continue
        current_max = max_map.get(pid)
        if current_max is None or current_max < minimum:
            max_map[pid] = max(minimum, current_max or 0.0)
    return {
        "min": min_map,
        "max": max_map,
        "target": target_map,
        "captain_min": captain_min_map,
        "captain_max": captain_max_map,
        "lock": sorted(lock),
        "exclude": sorted(exclude),
    }


def _stable_seed(*parts: Any) -> int:
    digest = hashlib.sha1(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return int(digest[:8], 16)


def _generate_showdown_script_candidates(
    *,
    players: list[dict[str, Any]],
    site_config: dict[str, Any],
    weights: dict[str, float],
    exposure_cfg: dict[str, Any],
    rng: random.Random,
    strategy_key: str,
    risk_key: str,
    slate: dict[str, Any],
    script_context: dict[str, Any],
    allocations: list[dict[str, Any]],
    correlation_context: CorrelationContext | None = None,
    correlation_weight: float = 0.0,
    stage_defaults: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Build showdown candidates partitioned by game script."""

    favorite = str(script_context.get("favorite") or "").upper()
    underdog = str(script_context.get("underdog") or "").upper()
    all_candidates: list[dict[str, Any]] = []
    global_seen: set[str] = set()

    for allocation in allocations:
        seats = int(allocation.get("lineup_count") or 0)
        if seats <= 0:
            continue
        script_id = str(allocation.get("script_id") or "")
        hints = build_script_hints(
            script_id,
            favorite=favorite,
            underdog=underdog,
            players=players,
        )
        # Oversample high-quota scripts so selection can meet seats
        # after similarity / exposure filtering.
        target = max(seats * 12, 24)
        bucket = _generate_candidates(
            players=players,
            site_config=site_config,
            format_key="showdown",
            weights=weights,
            exposure_cfg=exposure_cfg,
            target_count=target,
            rng=rng,
            strategy_key=strategy_key,
            risk_key=risk_key,
            slate=slate,
            script_hints=hints,
            script_meta={
                "script_id": script_id,
                "script_label": allocation.get("label"),
                "script_code": allocation.get("code"),
                "script_weight": allocation.get("weight"),
                "script_implication": allocation.get("implication"),
                "raw_probability": allocation.get("raw_probability"),
            },
            seen_keys=global_seen,
            correlation_context=correlation_context,
            correlation_weight=correlation_weight,
            stage_defaults=stage_defaults,
        )
        all_candidates.extend(bucket)

    return all_candidates


def _generate_candidates(
    *,
    players: list[dict[str, Any]],
    site_config: dict[str, Any],
    format_key: str,
    weights: dict[str, float],
    exposure_cfg: dict[str, Any],
    target_count: int,
    rng: random.Random,
    strategy_key: str,
    risk_key: str,
    slate: dict[str, Any],
    script_hints: dict[str, Any] | None = None,
    script_meta: dict[str, Any] | None = None,
    seen_keys: set[str] | None = None,
    correlation_context: CorrelationContext | None = None,
    correlation_weight: float = 0.0,
    stage_defaults: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    salary_cap = int(site_config["salary_cap"])
    captain_mult = float(
        site_config.get("captain_multiplier") or 1.0
    )
    base_lock = set(exposure_cfg["lock"])
    base_exclude = set(exposure_cfg["exclude"])
    hints = script_hints or {}
    boosts = {
        str(key): float(value)
        for key, value in (hints.get("score_boosts") or {}).items()
    }
    captain_pool = [
        str(pid)
        for pid in (hints.get("captain_pool") or [])
        if pid
    ]
    soft_lock = [
        str(pid) for pid in (hints.get("soft_lock") or []) if pid
    ]
    soft_exclude = [
        str(pid) for pid in (hints.get("soft_exclude") or []) if pid
    ]
    defaults = stage_defaults or STRATEGY_DEFAULTS.get(
        strategy_key, STRATEGY_DEFAULTS["balanced"]
    )
    noise_amp = float(defaults.get("stage1_noise") or 2.5)
    anchor_exclude_rate = float(
        defaults.get("stage1_anchor_exclude_rate") or 0.0
    )
    noisy_exclude_rate = float(
        defaults.get("stage1_noisy_exclude_rate") or 0.0
    )

    scored = []
    for player in players:
        row = dict(player)
        base = _player_score(
            row,
            weights=weights,
            max_ownership=None,
        )
        pid = str(row.get("player_id") or "")
        row["_base_opt_score"] = base + boosts.get(pid, 0.0)
        scored.append(row)
    scored.sort(
        key=lambda item: (
            -float(item.get("_base_opt_score") or 0.0),
            -float(item.get("projection") or 0.0),
        )
    )

    anchors = _anchor_player_ids(scored, format_key=format_key)
    if captain_pool:
        captain_rotation = [
            pid
            for pid in captain_pool
            if any(
                str(player.get("player_id")) == pid
                for player in scored
            )
        ]
    else:
        captain_rotation = (
            _captain_rotation_ids(scored)
            if format_key == "showdown"
            else []
        )
    local_seen: set[str] = seen_keys if seen_keys is not None else set()
    used_captains: set[str] = set()
    candidates: list[dict[str, Any]] = []
    attempts = 0
    max_attempts = max(target_count * 10, 120)

    while len(candidates) < target_count and attempts < max_attempts:
        attempts += 1
        lock = set(base_lock)
        exclude = set(base_exclude)

        # Soft script excludes (don't override user locks).
        for pid in soft_exclude:
            if pid not in lock and rng.random() < 0.55:
                exclude.add(pid)

        # Soft script locks for archetype shape.
        for pid in soft_lock:
            if pid not in exclude and rng.random() < 0.45:
                lock.add(pid)

        # Force-include: soft-lock min-exposure players often enough
        # that selection can meet the floor.
        for pid, minimum in exposure_cfg["min"].items():
            if pid in exclude or pid in lock:
                continue
            rate = max(0.0, min(1.0, float(minimum)))
            if rate <= 0:
                continue
            # Slight oversample so portfolio selection has room.
            if rng.random() < min(0.95, rate + 0.15):
                lock.add(pid)

        # Rotate anchors so cores differ across candidates without
        # systematically excluding other elite players.
        if anchors:
            anchor = anchors[(attempts - 1) % len(anchors)]
            if anchor not in exclude:
                lock.add(anchor)
            if anchor_exclude_rate > 0:
                for other in anchors:
                    if other == anchor or other in lock:
                        continue
                    if rng.random() < anchor_exclude_rate:
                        exclude.add(other)

        required_captain: str | None = None
        if captain_rotation:
            ordered = (
                [pid for pid in captain_rotation if pid not in used_captains]
                + [pid for pid in captain_rotation if pid in used_captains]
            )
            pick_index = (attempts - 1) % len(ordered)
            required_captain = ordered[pick_index]
            if required_captain in exclude:
                exclude.discard(required_captain)
            if required_captain not in lock and rng.random() < 0.65:
                lock.add(required_captain)

        if noisy_exclude_rate > 0:
            noisy_exclude = [
                str(player.get("player_id"))
                for player in scored[8:40]
                if player.get("player_id")
                and str(player.get("player_id")) not in lock
                and str(player.get("player_id")) != required_captain
                and rng.random() < noisy_exclude_rate
            ]
            exclude.update(noisy_exclude)

        pool = []
        for player in scored:
            pid = str(player.get("player_id") or "")
            if not pid or pid in exclude:
                continue
            row = dict(player)
            noise = rng.uniform(-noise_amp, noise_amp)
            row["_opt_score"] = (
                float(row.get("_base_opt_score") or 0.0) + noise
            )
            pool.append(row)

        if format_key == "showdown":
            selected = _optimize_showdown(
                pool=pool,
                salary_cap=salary_cap,
                captain_multiplier=captain_mult,
                locked=lock,
                max_ownership=None,
                required_captain_id=required_captain,
                correlation_context=correlation_context,
                correlation_weight=correlation_weight,
            )
        else:
            selected = _optimize_classic(
                pool=pool,
                roster_slots=copy.deepcopy(site_config["roster"]),
                salary_cap=salary_cap,
                locked=lock,
                excluded=exclude,
                max_ownership=None,
                min_salary=None,
                correlation_context=correlation_context,
                correlation_weight=correlation_weight,
            )

        roster_size = len(site_config["roster"])
        if len(selected) < roster_size:
            continue

        key = _lineup_key(selected)
        if key in local_seen:
            continue
        local_seen.add(key)
        if format_key == "showdown":
            captain_id = next(
                (
                    str(item.get("player_id"))
                    for item in selected
                    if str(item.get("slot") or "").upper() == "CPT"
                ),
                None,
            )
            if captain_id:
                used_captains.add(captain_id)
        candidates.append(
            _package_lineup(
                selected,
                slate=slate,
                site_config=site_config,
                format_key=format_key,
                strategy_key=strategy_key,
                risk_key=risk_key,
                index=len(candidates) + 1,
                script_meta=script_meta,
                correlation_context=correlation_context,
            )
        )

    return candidates


def _captain_rotation_ids(
    players: list[dict[str, Any]],
) -> list[str]:
    """Top showdown CPT candidates for portfolio diversification."""

    ids: list[str] = []
    for player in players[:24]:
        pid = str(player.get("player_id") or "")
        if pid and pid not in ids:
            ids.append(pid)
    return ids


def _anchor_player_ids(
    players: list[dict[str, Any]],
    *,
    format_key: str,
) -> list[str]:
    anchors: list[str] = []
    if format_key == "showdown":
        for player in players[:16]:
            pid = str(player.get("player_id") or "")
            if pid:
                anchors.append(pid)
        return anchors

    # Prefer distinct QBs then high-proj skill players.
    for player in players:
        if player.get("position") == "QB":
            pid = str(player.get("player_id") or "")
            if pid and pid not in anchors:
                anchors.append(pid)
            if len(anchors) >= 8:
                break
    for player in players:
        if player.get("position") in {"RB", "WR", "TE"}:
            pid = str(player.get("player_id") or "")
            if pid and pid not in anchors:
                anchors.append(pid)
            if len(anchors) >= 16:
                break
    return anchors


def _package_lineup(
    selected: list[dict[str, Any]],
    *,
    slate: dict[str, Any],
    site_config: dict[str, Any],
    format_key: str,
    strategy_key: str,
    risk_key: str,
    index: int,
    script_meta: dict[str, Any] | None = None,
    correlation_context: CorrelationContext | None = None,
) -> dict[str, Any]:
    salary_used = sum(int(item.get("salary") or 0) for item in selected)
    projection = round(
        sum(float(item.get("projection") or 0.0) for item in selected),
        1,
    )
    floor = round(
        sum(float(item.get("floor") or 0.0) for item in selected),
        1,
    )
    ceiling = round(
        sum(float(item.get("ceiling") or 0.0) for item in selected),
        1,
    )
    ownership = round(
        sum(
            float(item.get("projected_ownership") or 0.0) * 100.0
            for item in selected
        ),
        1,
    )
    salary_cap = int(site_config["salary_cap"])
    value = None
    if salary_used > 0:
        value = round(projection / (salary_used / 1000.0), 2)
    roster_size = len(site_config["roster"])
    packaged = {
        "lineup_id": (
            f"pf-{slate['slate_id']}-{site_config['id']}"
            f"-{format_key}-{index}"
        ),
        "slate_id": slate["slate_id"],
        "site": site_config["id"],
        "contest_type": format_key,
        "strategy": strategy_key,
        "risk": risk_key,
        "players": selected,
        "salary_used": salary_used,
        "salary_remaining": salary_cap - salary_used,
        "salary_cap": salary_cap,
        "projected_points": projection,
        "projected_floor": floor,
        "projected_ceiling": ceiling,
        "projected_ownership": ownership,
        "value": value,
        "roster_filled": len(selected),
        "roster_size": roster_size,
        "valid": len(selected) == roster_size
        and salary_used <= salary_cap,
        "player_ids": sorted(
            {
                str(item.get("player_id"))
                for item in selected
                if item.get("player_id")
            }
        ),
    }
    if correlation_context is not None:
        correlation = score_lineup_correlation(
            selected,
            correlation_context,
        )
        packaged["correlation"] = correlation
        packaged["lineup_correlation_score"] = correlation.get(
            "lineup_correlation_score"
        )
    if script_meta:
        packaged["game_script_id"] = script_meta.get("script_id")
        packaged["game_script_label"] = script_meta.get("script_label")
        packaged["game_script_code"] = script_meta.get("script_code")
        packaged["game_script_weight"] = script_meta.get("script_weight")
        packaged["game_script_implication"] = script_meta.get(
            "script_implication"
        )
        packaged["game_script_raw_probability"] = script_meta.get(
            "raw_probability"
        )
    return packaged


def _lineup_key(players: list[dict[str, Any]]) -> str:
    ids = sorted(
        {
            str(item.get("player_id"))
            for item in players
            if item.get("player_id")
        }
    )
    return "|".join(ids)


def _select_portfolio_by_script(
    *,
    candidates: list[dict[str, Any]],
    allocations: list[dict[str, Any]],
    lineup_count: int,
    max_similarity: float,
    default_max_exposure: float,
    default_max_captain_exposure: float,
    exposure_cfg: dict[str, Any],
    min_unique_players: int = 2,
    strategy_defaults: dict[str, float] | None = None,
    rejection_counts: Counter[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Fill script quotas so lineup mix tracks normalized weights.

    Under-filled scripts keep priority on top-off instead of letting
    higher-projection archetypes steal leftover seats.
    """

    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    captain_counts: Counter[str] = Counter()
    conflicts: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    filled_by_script: Counter[str] = Counter()

    by_script: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        script_id = str(candidate.get("game_script_id") or "")
        by_script.setdefault(script_id, []).append(candidate)
    for bucket in by_script.values():
        bucket.sort(
            key=lambda item: (
                -float(item.get("projected_points") or 0.0),
                -float(item.get("projected_ceiling") or 0.0),
            )
        )

    quota_by_script = {
        str(row.get("script_id") or ""): int(
            row.get("lineup_count") or 0
        )
        for row in allocations
        if row.get("script_id")
    }

    def _take_from_pool(
        pool: list[dict[str, Any]],
        *,
        seats_left: int,
        strict: bool,
    ) -> int:
        taken = 0
        while (
            taken < seats_left
            and pool
            and len(selected) < lineup_count
        ):
            if strict:
                pick_idx = _best_candidate_index(
                    pool,
                    selected=selected,
                    counts=counts,
                    captain_counts=captain_counts,
                    lineup_count=lineup_count,
                    max_similarity=max_similarity,
                    min_unique_players=min_unique_players,
                    default_max_exposure=default_max_exposure,
                    default_max_captain_exposure=(
                        default_max_captain_exposure
                    ),
                    exposure_cfg=exposure_cfg,
                    strategy_defaults=strategy_defaults,
                    rejection_counts=rejection_counts,
                )
                if pick_idx is None:
                    pick_idx = _pick_relaxed(
                        pool,
                        selected=selected,
                        counts=counts,
                        captain_counts=captain_counts,
                        lineup_count=lineup_count,
                        selected_count=len(selected),
                        default_max_exposure=default_max_exposure,
                        default_max_captain_exposure=(
                            default_max_captain_exposure
                        ),
                        exposure_cfg=exposure_cfg,
                        max_similarity=max_similarity,
                        min_unique_players=min_unique_players,
                        strategy_defaults=strategy_defaults,
                        rejection_counts=rejection_counts,
                    )
            else:
                # Last resort within-script: unique lineups only,
                # but never breach hard exposure caps.
                pick_idx = None
                for index, candidate in enumerate(pool):
                    key = _lineup_key(
                        candidate.get("players") or []
                    )
                    if key in used_keys:
                        continue
                    if not _passes_max_exposure(
                        candidate,
                        counts=counts,
                        captain_counts=captain_counts,
                        lineup_count=lineup_count,
                        selected_count=len(selected),
                        default_max_exposure=default_max_exposure,
                        default_max_captain_exposure=(
                            default_max_captain_exposure
                        ),
                        exposure_cfg=exposure_cfg,
                    ):
                        continue
                    pick_idx = index
                    break
            if pick_idx is None:
                break
            pick = pool.pop(pick_idx)
            key = _lineup_key(pick.get("players") or [])
            if key in used_keys:
                continue
            used_keys.add(key)
            selected.append(pick)
            script_id = str(pick.get("game_script_id") or "")
            if script_id:
                filled_by_script[script_id] += 1
            for pid in pick.get("player_ids") or []:
                counts[str(pid)] += 1
            cpt = _captain_id(pick)
            if cpt:
                captain_counts[cpt] += 1
            taken += 1
        return taken

    # Pass 1: strict + relaxed fill per script quota (weight order).
    for allocation in allocations:
        script_id = str(allocation.get("script_id") or "")
        seats = int(allocation.get("lineup_count") or 0)
        if seats <= 0:
            continue
        pool = list(by_script.get(script_id) or [])
        _take_from_pool(pool, seats_left=seats, strict=True)
        by_script[script_id] = pool

    # Pass 2: uniqueness + hard exposure refill for under scripts.
    for allocation in allocations:
        script_id = str(allocation.get("script_id") or "")
        seats = int(allocation.get("lineup_count") or 0)
        need = seats - filled_by_script.get(script_id, 0)
        if need <= 0:
            continue
        pool = list(by_script.get(script_id) or [])
        _take_from_pool(pool, seats_left=need, strict=False)
        by_script[script_id] = pool

    # Pass 3: top off remaining seats from under-quota scripts first
    # (largest unmet weight), then any leftover candidates.
    while len(selected) < lineup_count:
        underfilled = [
            (
                float(row.get("weight") or 0.0),
                int(row.get("lineup_count") or 0)
                - filled_by_script.get(
                    str(row.get("script_id") or ""), 0
                ),
                str(row.get("script_id") or ""),
            )
            for row in allocations
        ]
        underfilled = [
            item
            for item in underfilled
            if item[1] > 0 and by_script.get(item[2])
        ]
        underfilled.sort(key=lambda item: (-item[0], -item[1]))
        progress = False
        if underfilled:
            _, need, script_id = underfilled[0]
            pool = list(by_script.get(script_id) or [])
            taken = _take_from_pool(
                pool, seats_left=need, strict=False
            )
            by_script[script_id] = pool
            progress = taken > 0
        if progress:
            continue

        leftovers = [
            candidate
            for candidate in candidates
            if _lineup_key(candidate.get("players") or [])
            not in used_keys
        ]
        if not leftovers:
            break
        leftovers.sort(
            key=lambda item: (
                -float(item.get("projected_points") or 0.0),
                -float(item.get("projected_ceiling") or 0.0),
            )
        )
        taken = _take_from_pool(
            leftovers, seats_left=1, strict=False
        )
        if taken <= 0:
            break

    # Persist actual seat fills on allocations for the UI mix panel.
    for allocation in allocations:
        script_id = str(allocation.get("script_id") or "")
        allocation["target_lineup_count"] = int(
            quota_by_script.get(script_id, 0)
        )
        allocation["lineup_count"] = int(
            filled_by_script.get(script_id, 0)
        )

    # Soft-check locks after selection.
    for pid in exposure_cfg["lock"]:
        rate = counts.get(pid, 0) / float(max(lineup_count, 1))
        if rate < 0.999:
            conflicts.append(
                {
                    "type": "EXPOSURE_CONSTRAINT_CONFLICT",
                    "player_id": pid,
                    "constraint": "lock",
                    "requested": 1.0,
                    "actual": round(rate, 3),
                }
            )
    for pid, minimum in exposure_cfg["min"].items():
        if pid in exposure_cfg["lock"]:
            continue
        rate = counts.get(pid, 0) / float(max(lineup_count, 1))
        if rate + 1e-9 < float(minimum):
            conflicts.append(
                {
                    "type": "EXPOSURE_CONSTRAINT_CONFLICT",
                    "player_id": pid,
                    "constraint": "min",
                    "requested": float(minimum),
                    "actual": round(rate, 4),
                    "explanation": (
                        f"Min exposure {minimum:.0%} not met "
                        f"(actual {rate:.0%})."
                    ),
                }
            )

    # Renumber lineup ids for the final portfolio order.
    for index, lineup in enumerate(selected, start=1):
        lineup["portfolio_index"] = index
        base_id = str(lineup.get("lineup_id") or f"pf-{index}")
        script_code = lineup.get("game_script_code")
        suffix = f"-{script_code}" if script_code else ""
        lineup["lineup_id"] = f"{base_id}{suffix}-{index}"

    return selected[:lineup_count], conflicts


def _best_candidate_index(
    remaining: list[dict[str, Any]],
    *,
    selected: list[dict[str, Any]],
    counts: Counter[str],
    captain_counts: Counter[str],
    lineup_count: int,
    max_similarity: float,
    default_max_exposure: float,
    default_max_captain_exposure: float,
    exposure_cfg: dict[str, Any],
    min_unique_players: int = 2,
    strategy_defaults: dict[str, float] | None = None,
    rejection_counts: Counter[str] | None = None,
) -> int | None:
    best_idx = None
    best_score = float("-inf")
    rejections = (
        rejection_counts if rejection_counts is not None else Counter()
    )
    for index, candidate in enumerate(remaining):
        if not _passes_max_exposure(
            candidate,
            counts=counts,
            captain_counts=captain_counts,
            lineup_count=lineup_count,
            selected_count=len(selected),
            default_max_exposure=default_max_exposure,
            default_max_captain_exposure=default_max_captain_exposure,
            exposure_cfg=exposure_cfg,
        ):
            rejections["player_exposure_maximum"] += 1
            continue
        if not _passes_uniqueness(
            candidate,
            selected=selected,
            min_unique_players=min_unique_players,
            max_similarity=max_similarity,
        ):
            rejections["uniqueness_constraint"] += 1
            continue
        score = _candidate_select_score(
            candidate,
            counts=counts,
            selected_count=len(selected),
            lineup_count=lineup_count,
            exposure_cfg=exposure_cfg,
            default_max_exposure=default_max_exposure,
            strategy_defaults=strategy_defaults,
        )
        if score > best_score:
            best_score = score
            best_idx = index
    return best_idx


def _select_portfolio(
    *,
    candidates: list[dict[str, Any]],
    lineup_count: int,
    max_similarity: float,
    default_max_exposure: float,
    default_max_captain_exposure: float,
    exposure_cfg: dict[str, Any],
    refill_candidates: Any | None = None,
    min_unique_players: int = 2,
    strategy_defaults: dict[str, float] | None = None,
    rejection_counts: Counter[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Greedy portfolio selection under exposure + similarity caps."""

    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    captain_counts: Counter[str] = Counter()
    conflicts: list[dict[str, Any]] = []
    remaining = list(candidates)
    refill_rounds = 0
    max_refill_rounds = 4

    # Prefer higher projection first as the quality prior.
    remaining.sort(
        key=lambda item: (
            -float(item.get("projected_points") or 0.0),
            -float(item.get("projected_ceiling") or 0.0),
        )
    )

    while len(selected) < lineup_count and remaining:
        best_idx = None
        best_score = float("-inf")
        for index, candidate in enumerate(remaining):
            if not _passes_max_exposure(
                candidate,
                counts=counts,
                captain_counts=captain_counts,
                lineup_count=lineup_count,
                selected_count=len(selected),
                default_max_exposure=default_max_exposure,
                default_max_captain_exposure=(
                    default_max_captain_exposure
                ),
                exposure_cfg=exposure_cfg,
            ):
                continue
            if not _passes_uniqueness(
                candidate,
                selected=selected,
                min_unique_players=min_unique_players,
                max_similarity=max_similarity,
            ):
                if rejection_counts is not None:
                    rejection_counts["uniqueness_constraint"] += 1
                continue
            score = _candidate_select_score(
                candidate,
                counts=counts,
                selected_count=len(selected),
                lineup_count=lineup_count,
                exposure_cfg=exposure_cfg,
                default_max_exposure=default_max_exposure,
                strategy_defaults=strategy_defaults,
            )
            if score > best_score:
                best_score = score
                best_idx = index

        if best_idx is None:
            # Gradually relax similarity only; exposure stays hard.
            relaxed = _pick_relaxed(
                remaining,
                selected=selected,
                counts=counts,
                captain_counts=captain_counts,
                lineup_count=lineup_count,
                selected_count=len(selected),
                default_max_exposure=default_max_exposure,
                default_max_captain_exposure=(
                    default_max_captain_exposure
                ),
                exposure_cfg=exposure_cfg,
                max_similarity=max_similarity,
                min_unique_players=min_unique_players,
                strategy_defaults=strategy_defaults,
                rejection_counts=rejection_counts,
            )
            if relaxed is None:
                if (
                    refill_candidates is not None
                    and refill_rounds < max_refill_rounds
                ):
                    refill_rounds += 1
                    extra = list(
                        refill_candidates(counts, captain_counts)
                        or []
                    )
                    if extra:
                        existing = {
                            _lineup_key(item.get("players") or [])
                            for item in remaining
                        }
                        existing.update(
                            _lineup_key(item.get("players") or [])
                            for item in selected
                        )
                        added = 0
                        for item in extra:
                            key = _lineup_key(
                                item.get("players") or []
                            )
                            if key in existing:
                                continue
                            remaining.append(item)
                            existing.add(key)
                            added += 1
                        if added:
                            remaining.sort(
                                key=lambda row: (
                                    -float(
                                        row.get("projected_points")
                                        or 0.0
                                    ),
                                    -float(
                                        row.get("projected_ceiling")
                                        or 0.0
                                    ),
                                )
                            )
                            continue
                break
            best_idx = relaxed

        pick = remaining.pop(best_idx)
        selected.append(pick)
        for pid in pick.get("player_ids") or []:
            counts[str(pid)] += 1
        cpt = _captain_id(pick)
        if cpt:
            captain_counts[cpt] += 1

    if len(selected) < lineup_count:
        conflicts.append(
            {
                "type": "PORTFOLIO_UNDERFILLED",
                "requested": lineup_count,
                "actual": len(selected),
                "explanation": (
                    f"Built {len(selected)} of {lineup_count} "
                    "lineups under hard exposure caps and the "
                    "configured max lineup similarity. Loosen "
                    "max exposure / similarity or exclude fewer "
                    "players to fill the rest."
                ),
            }
        )

    # Soft-check min exposure / locks after selection.
    for pid in exposure_cfg["lock"]:
        rate = counts.get(pid, 0) / float(lineup_count)
        if rate < 0.999:
            conflicts.append(
                {
                    "type": "EXPOSURE_CONSTRAINT_CONFLICT",
                    "player_id": pid,
                    "constraint": "lock",
                    "requested": 1.0,
                    "actual": round(rate, 4),
                    "explanation": (
                        f"Locked player appears in "
                        f"{counts.get(pid, 0)} of {lineup_count} "
                        "lineups."
                    ),
                }
            )
    for pid, minimum in exposure_cfg["min"].items():
        if pid in exposure_cfg["lock"]:
            continue
        rate = counts.get(pid, 0) / float(lineup_count)
        if rate + 1e-9 < float(minimum):
            conflicts.append(
                {
                    "type": "EXPOSURE_CONSTRAINT_CONFLICT",
                    "player_id": pid,
                    "constraint": "min",
                    "requested": float(minimum),
                    "actual": round(rate, 4),
                    "explanation": (
                        f"Min exposure {minimum:.0%} not met "
                        f"(actual {rate:.0%})."
                    ),
                }
            )

    # Renumber lineup ids for the final portfolio order.
    for index, lineup in enumerate(selected, start=1):
        base = str(lineup.get("lineup_id") or "pf-lineup")
        parts = base.rsplit("-", 1)
        lineup["lineup_id"] = (
            f"{parts[0]}-{index}"
            if len(parts) == 2
            else f"{base}-{index}"
        )
        lineup["portfolio_index"] = index
        lineup["similarity"] = _avg_similarity_to_others(
            lineup, selected
        )

    return selected, conflicts


def _passes_max_exposure(
    candidate: dict[str, Any],
    *,
    counts: Counter[str],
    captain_counts: Counter[str],
    lineup_count: int,
    selected_count: int,
    default_max_exposure: float,
    default_max_captain_exposure: float,
    exposure_cfg: dict[str, Any],
) -> bool:
    """
    Hard max-exposure gate.

    Caps are evaluated against the requested portfolio size so a
    player cannot appear in more than floor(cap * lineup_count)
    lineups. Individual ``exposure_cfg['max']`` / ``captain_max``
    entries override the defaults.
    """

    del selected_count  # kept for call-site compatibility
    requested = max(int(lineup_count), 1)
    for pid in candidate.get("player_ids") or []:
        pid = str(pid)
        cap = float(
            exposure_cfg["max"].get(pid, default_max_exposure)
        )
        cap = max(0.0, min(1.0, cap))
        max_apps = int(cap * requested + 1e-9)
        if counts.get(pid, 0) + 1 > max_apps:
            return False

    captain_id = _captain_id(candidate)
    if captain_id:
        cpt_cap = float(
            exposure_cfg["captain_max"].get(
                captain_id, default_max_captain_exposure
            )
        )
        cpt_cap = max(0.0, min(1.0, cpt_cap))
        max_cpt_apps = int(cpt_cap * requested + 1e-9)
        if captain_counts.get(captain_id, 0) + 1 > max_cpt_apps:
            return False
    return True


def _passes_similarity(
    candidate: dict[str, Any],
    *,
    selected: list[dict[str, Any]],
    max_similarity: float,
) -> bool:
    if not selected:
        return True
    ids = set(candidate.get("player_ids") or [])
    for other in selected:
        other_ids = set(other.get("player_ids") or [])
        if _jaccard(ids, other_ids) > max_similarity + 1e-9:
            return False
    return True


def _candidate_select_score(
    candidate: dict[str, Any],
    *,
    counts: Counter[str],
    selected_count: int,
    lineup_count: int,
    exposure_cfg: dict[str, Any],
    default_max_exposure: float,
    strategy_defaults: dict[str, float] | None = None,
) -> float:
    """
    Stage 2 ranking: projection-first.

    Soft exposure penalties are intentionally omitted. Hard max
    exposure gates already enforce configured caps; scoring must not
    demote elite players merely because they already appear.
    """

    del default_max_exposure  # caps are hard constraints, not scores
    projection = float(candidate.get("projected_points") or 0.0)
    ceiling = float(candidate.get("projected_ceiling") or 0.0)
    ownership = float(candidate.get("projected_ownership") or 0.0)
    defaults = strategy_defaults or {}
    ceil_w = float(defaults.get("selection_ceiling_weight") or 0.15)
    lev_w = float(defaults.get("selection_leverage_weight") or 0.0)
    # Ownership is stored as sum of player ownership percentages.
    leverage = max(0.0, 120.0 - ownership)
    score = projection + ceil_w * ceiling + lev_w * (leverage * 0.04)

    ids = {
        str(pid)
        for pid in (candidate.get("player_ids") or [])
        if pid
    }

    # Soft nudge toward optional exposure targets only (not max caps).
    for pid in ids:
        target = exposure_cfg["target"].get(pid)
        if target is not None:
            projected = (counts.get(pid, 0) + 1) / float(
                max(lineup_count, 1)
            )
            score -= abs(projected - float(target)) * 4.0
        if pid in exposure_cfg["lock"]:
            score += 12.0

    # Strong preference for lineups that fill unmet min exposure.
    remaining_slots = max(lineup_count - selected_count, 1)
    for pid, minimum in exposure_cfg["min"].items():
        if pid in exposure_cfg["exclude"]:
            continue
        need = float(minimum) * float(lineup_count)
        have = float(counts.get(pid, 0))
        deficit = need - have
        if deficit <= 1e-9:
            continue
        urgency = deficit / float(remaining_slots)
        if pid in ids:
            score += 18.0 + 22.0 * min(1.5, urgency)
        elif urgency > 0.85:
            # Penalize candidates that ignore a nearly-due min.
            score -= 8.0 * urgency

    return score


def _pick_relaxed(
    remaining: list[dict[str, Any]],
    *,
    selected: list[dict[str, Any]],
    counts: Counter[str],
    captain_counts: Counter[str],
    lineup_count: int,
    selected_count: int,
    default_max_exposure: float,
    default_max_captain_exposure: float,
    exposure_cfg: dict[str, Any],
    max_similarity: float,
    min_unique_players: int = 2,
    strategy_defaults: dict[str, float] | None = None,
    rejection_counts: Counter[str] | None = None,
) -> int | None:
    """
    Gradually relax uniqueness to fill seats.

    Exposure caps stay hard. Uniqueness starts at the configured
    floor and steps downward; only the final step allows any
    unique exposure-legal lineup.
    """

    del rejection_counts
    unique_floors: list[int | None] = [
        max(0, int(min_unique_players) - step)
        for step in (0, 1, 2)
        if int(min_unique_players) - step >= 0
    ]
    unique_floors.append(None)

    for floor in unique_floors:
        best_idx = None
        best_score = float("-inf")
        for index, candidate in enumerate(remaining):
            if not _passes_max_exposure(
                candidate,
                counts=counts,
                captain_counts=captain_counts,
                lineup_count=lineup_count,
                selected_count=selected_count,
                default_max_exposure=default_max_exposure,
                default_max_captain_exposure=(
                    default_max_captain_exposure
                ),
                exposure_cfg=exposure_cfg,
            ):
                continue
            if floor is not None and not _passes_uniqueness(
                candidate,
                selected=selected,
                min_unique_players=floor,
                max_similarity=max_similarity,
            ):
                continue
            score = _candidate_select_score(
                candidate,
                counts=counts,
                selected_count=selected_count,
                lineup_count=lineup_count,
                exposure_cfg=exposure_cfg,
                default_max_exposure=default_max_exposure,
                strategy_defaults=strategy_defaults,
            )
            if score > best_score:
                best_score = score
                best_idx = index
        if best_idx is not None:
            return best_idx
    return None


def _resolve_min_unique_players(
    *,
    min_unique_players: int | None,
    max_similarity: float,
    roster_size: int,
) -> int:
    """Convert uniqueness settings into a min unique-player floor."""

    if min_unique_players is not None:
        return max(0, min(int(roster_size), int(min_unique_players)))
    if max_similarity >= 0.90:
        return 1
    if max_similarity >= 0.70:
        return 2
    if max_similarity >= 0.60:
        return 3
    return 3


def _passes_uniqueness(
    candidate: dict[str, Any],
    *,
    selected: list[dict[str, Any]],
    min_unique_players: int,
    max_similarity: float,
) -> bool:
    """Lineup-level uniqueness without penalizing shared elites."""

    if not selected:
        return True
    ids = {
        str(pid)
        for pid in (candidate.get("player_ids") or [])
        if pid
    }
    floor = max(0, int(min_unique_players or 0))
    for other in selected:
        other_ids = {
            str(pid)
            for pid in (other.get("player_ids") or [])
            if pid
        }
        if floor > 0:
            if len(ids - other_ids) < floor:
                return False
        elif _jaccard(ids, other_ids) > max_similarity + 1e-9:
            return False
    return True


def _build_player_diagnostics(
    *,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    players: list[dict[str, Any]],
    exposure_cfg: dict[str, Any],
    default_max_exposure: float,
    default_max_captain_exposure: float,
    lineup_count: int,
    min_unique_players: int,
    max_similarity: float,
    rejection_counts: Counter[str],
    strategy_key: str,
) -> list[dict[str, Any]]:
    """Explain why important players have lower-than-expected exposure."""

    del default_max_captain_exposure
    selected_ids = {
        _lineup_key(item.get("players") or []) for item in selected
    }
    selected_counts: Counter[str] = Counter()
    for lineup in selected:
        seen: set[str] = set()
        for pid in lineup.get("player_ids") or []:
            pid = str(pid)
            if pid and pid not in seen:
                seen.add(pid)
                selected_counts[pid] += 1

    pool_by_id = {
        str(player.get("player_id")): player
        for player in players
        if player.get("player_id")
    }
    ranked = sorted(
        pool_by_id.values(),
        key=lambda row: -float(row.get("projection") or 0.0),
    )
    focus_ids = [
        str(player.get("player_id"))
        for player in ranked[:12]
        if player.get("player_id")
    ]
    for group in (
        exposure_cfg.get("min") or {},
        exposure_cfg.get("max") or {},
    ):
        for pid in group:
            if str(pid) not in focus_ids:
                focus_ids.append(str(pid))
    for pid in list(exposure_cfg.get("exclude") or []) + list(
        exposure_cfg.get("lock") or []
    ):
        if str(pid) not in focus_ids:
            focus_ids.append(str(pid))

    diagnostics: list[dict[str, Any]] = []
    n = max(int(lineup_count), 1)
    for pid in focus_ids:
        player = pool_by_id.get(pid) or {}
        max_allowed = float(
            exposure_cfg["max"].get(pid, default_max_exposure)
        )
        max_apps = int(max_allowed * float(n) + 1e-9)
        apps = int(selected_counts.get(pid, 0))
        exposure = apps / float(n)
        containing = [
            candidate
            for candidate in candidates
            if pid in set(candidate.get("player_ids") or [])
        ]
        reasons: list[str] = []
        if pid in set(exposure_cfg.get("exclude") or []):
            reasons.append(
                "Slate eligibility / excluded from portfolio"
            )
        if apps >= max_apps and max_apps >= 0:
            reasons.append("Exposure cap reached")
        if not containing:
            reasons.append("No valid candidate lineups")

        uniqueness_rejects = 0
        for candidate in containing:
            key = _lineup_key(candidate.get("players") or [])
            if key in selected_ids:
                continue
            if not _passes_uniqueness(
                candidate,
                selected=selected,
                min_unique_players=min_unique_players,
                max_similarity=max_similarity,
            ):
                uniqueness_rejects += 1

        if uniqueness_rejects:
            reasons.append(
                f"{uniqueness_rejects} additional candidate lineups "
                "containing this player were rejected because they "
                "violated the minimum uniqueness rule"
            )
        if strategy_key == "contrarian" and exposure < max_allowed * 0.5:
            reasons.append("Portfolio strategy")
        if not reasons and apps < max_apps:
            reasons.append(
                "Higher-projection alternate lineups were preferred"
            )

        diagnostics.append(
            {
                "player_id": pid,
                "name": player.get("name"),
                "position": player.get("position"),
                "projection": player.get("projection"),
                "exposure": round(exposure, 4),
                "exposure_pct": round(exposure * 100.0, 1),
                "lineups": apps,
                "max_exposure": round(max_allowed, 4),
                "max_allowed_lineups": max_apps,
                "remaining_capacity": max(0, max_apps - apps),
                "candidate_lineups_with_player": len(containing),
                "reasons": reasons,
                "why_not_more": (
                    reasons[0]
                    if reasons
                    else "Exposure is within configured strategy bounds"
                ),
                "rejection_summary": dict(rejection_counts),
            }
        )
    diagnostics.sort(
        key=lambda row: (
            -float(row.get("projection") or 0.0),
            -float(row.get("exposure") or 0.0),
        )
    )
    return diagnostics


def _players_at_max_exposure(
    counts: Counter[str],
    *,
    lineup_count: int,
    default_max_exposure: float,
    exposure_cfg: dict[str, Any],
) -> set[str]:
    """Player ids that cannot appear in any additional lineup."""

    requested = max(int(lineup_count), 1)
    at_cap: set[str] = set()
    for pid, apps in counts.items():
        cap = float(
            exposure_cfg["max"].get(pid, default_max_exposure)
        )
        cap = max(0.0, min(1.0, cap))
        max_apps = int(cap * requested + 1e-9)
        if int(apps) >= max_apps:
            at_cap.add(str(pid))
    return at_cap


def _is_active_roster_player(player: dict[str, Any]) -> bool:
    """Portfolio pool includes Active roster players (and team DST)."""

    if player.get("is_team_defense"):
        return True
    position = str(player.get("position") or "").strip().upper()
    if position in {"DEF", "DST"}:
        return True
    status = str(player.get("status") or "Active").strip().lower()
    return status in {"active", "a"}


def _append_constrained_zero_exposure(
    player_exposure: list[dict[str, Any]],
    *,
    player_meta: dict[str, dict[str, Any]],
    player_pool: list[dict[str, Any]],
    exposure_cfg: dict[str, Any],
    lineup_count: int,
    default_max_exposure: float,
    default_max_captain_exposure: float,
) -> list[dict[str, Any]]:
    """
    Keep excluded / force-include (min) players visible at 0% so
    the UI can re-include or edit floors without a full reset.
    """

    present = {str(row["player_id"]) for row in player_exposure}
    pool_by_id = {
        str(player.get("player_id")): player
        for player in player_pool
        if player.get("player_id")
    }
    constrained = (
        set(exposure_cfg.get("exclude") or [])
        | set(exposure_cfg.get("lock") or [])
        | set((exposure_cfg.get("min") or {}).keys())
        | set((exposure_cfg.get("max") or {}).keys())
        | set((exposure_cfg.get("captain_max") or {}).keys())
        | set((exposure_cfg.get("captain_min") or {}).keys())
    )
    n = max(int(lineup_count), 1)
    extras: list[dict[str, Any]] = []
    for pid in sorted(constrained):
        if pid in present:
            continue
        meta = player_meta.get(pid) or {}
        if not meta:
            player = pool_by_id.get(pid) or {}
            if not player:
                continue
            meta = {
                "player_id": pid,
                "name": player.get("name"),
                "position": player.get("position"),
                "team": player.get("team"),
                "opponent": player.get("opponent"),
                "projection": player.get("projection"),
                "ceiling": player.get("ceiling"),
                "floor": player.get("floor"),
                "projected_ownership": player.get(
                    "projected_ownership"
                ),
                "salary": player.get("salary"),
            }
        extras.append(
            {
                **meta,
                "lineups": 0,
                "lineup_count": n,
                "generated_lineup_count": n,
                "exposure": 0.0,
                "exposure_pct": 0.0,
                "captain_lineups": 0,
                "captain_exposure": 0.0,
                "captain_exposure_pct": 0.0,
                "min_exposure": exposure_cfg["min"].get(pid),
                "max_exposure": exposure_cfg["max"].get(
                    pid, default_max_exposure
                ),
                "min_captain_exposure": exposure_cfg[
                    "captain_min"
                ].get(pid),
                "max_captain_exposure": exposure_cfg[
                    "captain_max"
                ].get(pid, default_max_captain_exposure),
                "max_allowed_exposure": round(
                    float(
                        exposure_cfg["max"].get(
                            pid, default_max_exposure
                        )
                    ),
                    4,
                ),
                "max_allowed_lineups": int(
                    float(
                        exposure_cfg["max"].get(
                            pid, default_max_exposure
                        )
                    )
                    * float(n)
                    + 1e-9
                ),
                "remaining_capacity": int(
                    float(
                        exposure_cfg["max"].get(
                            pid, default_max_exposure
                        )
                    )
                    * float(n)
                    + 1e-9
                ),
                "locked": pid in exposure_cfg["lock"],
                "excluded": pid in exposure_cfg["exclude"],
            }
        )
    if not extras:
        return player_exposure
    return player_exposure + extras


def _similarity_report(
    lineups: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(lineups) < 2:
        return {"average": 0.0, "most_similar_pairs": []}

    pairs: list[dict[str, Any]] = []
    total = 0.0
    count = 0
    for i in range(len(lineups)):
        ids_i = set(lineups[i].get("player_ids") or [])
        for j in range(i + 1, len(lineups)):
            ids_j = set(lineups[j].get("player_ids") or [])
            sim = _jaccard(ids_i, ids_j)
            shared = len(ids_i & ids_j)
            roster = max(len(ids_i), len(ids_j), 1)
            total += sim
            count += 1
            pairs.append(
                {
                    "lineup_a": lineups[i].get("lineup_id"),
                    "lineup_b": lineups[j].get("lineup_id"),
                    "index_a": lineups[i].get(
                        "portfolio_index", i + 1
                    ),
                    "index_b": lineups[j].get(
                        "portfolio_index", j + 1
                    ),
                    "similarity": round(sim, 3),
                    "shared_players": shared,
                    "roster_size": roster,
                }
            )
    pairs.sort(
        key=lambda item: (
            -float(item["similarity"]),
            -int(item["shared_players"]),
        )
    )
    return {
        "average": (total / count) if count else 0.0,
        "most_similar_pairs": pairs[:5],
    }


def _avg_similarity_to_others(
    lineup: dict[str, Any],
    all_lineups: list[dict[str, Any]],
) -> float:
    ids = set(lineup.get("player_ids") or [])
    values = []
    for other in all_lineups:
        if other is lineup:
            continue
        values.append(
            _jaccard(ids, set(other.get("player_ids") or []))
        )
    return round(_avg(values), 3) if values else 0.0


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / float(len(union))


def _diversity_label(
    *,
    unique_players: int,
    lineup_count: int,
    avg_similarity: float,
    max_player_exposure: float,
) -> str:
    if lineup_count <= 0:
        return "None"
    per_lineup = unique_players / float(lineup_count)
    if (
        avg_similarity <= 0.45
        and max_player_exposure <= 0.55
        and per_lineup >= 3.5
    ):
        return "High"
    if avg_similarity >= 0.75 or max_player_exposure >= 0.85:
        return "Low"
    return "Moderate"


def _build_signals(
    *,
    player_exposure: list[dict[str, Any]],
    lineup_count: int,
    unique_players: int,
    similarity: dict[str, Any],
    max_similarity: float,
    core: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    signals: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    if player_exposure:
        top = player_exposure[0]
        if top["exposure"] >= 0.80:
            alert = {
                "id": "high-player-concentration",
                "type": "HIGH_PLAYER_CONCENTRATION",
                "severity": "high",
                "player_id": top["player_id"],
                "exposure": top["exposure"],
                "threshold": 0.80,
                "explanation": (
                    f"{top['name']} appears in "
                    f"{top['lineups']} of {lineup_count} lineups "
                    f"({top['exposure_pct']:.0f}%)."
                ),
                "action": "Review Exposure",
            }
            alerts.append(alert)
            signals.append(alert)
        elif top["exposure"] >= 0.60:
            signals.append(
                {
                    "id": "elevated-player-exposure",
                    "type": "HIGH_PLAYER_CONCENTRATION",
                    "severity": "moderate",
                    "player_id": top["player_id"],
                    "exposure": top["exposure"],
                    "threshold": 0.60,
                    "explanation": (
                        f"{top['name']} appears in "
                        f"{top['exposure_pct']:.0f}% of lineups."
                    ),
                }
            )

    avg_sim = float(similarity.get("average") or 0.0)
    if avg_sim >= max(max_similarity, 0.75):
        alert = {
            "id": "high-lineup-similarity",
            "type": "HIGH_LINEUP_SIMILARITY",
            "severity": "moderate",
            "similarity": round(avg_sim, 3),
            "threshold": max_similarity,
            "explanation": (
                f"Average lineup similarity is {avg_sim:.0%}. "
                "Several constructions may be redundant."
            ),
            "action": "Review Lineups",
        }
        alerts.append(alert)
        signals.append(alert)

    pairs = similarity.get("most_similar_pairs") or []
    if pairs and pairs[0].get("shared_players", 0) >= 8:
        top_pair = pairs[0]
        alerts.append(
            {
                "id": "redundant-lineups",
                "type": "HIGH_LINEUP_SIMILARITY",
                "severity": "moderate",
                "explanation": (
                    f"Lineup {top_pair.get('index_a')} and "
                    f"Lineup {top_pair.get('index_b')} share "
                    f"{top_pair.get('shared_players')} of "
                    f"{top_pair.get('roster_size')} players."
                ),
                "action": "Compare Lineups",
            }
        )

    if unique_players >= lineup_count * 2:
        signals.append(
            {
                "id": "diverse-player-pool",
                "type": "DIVERSE_PLAYER_POOL",
                "severity": "info",
                "unique_players": unique_players,
                "explanation": (
                    f"Portfolio uses {unique_players} unique "
                    f"players across {lineup_count} lineups."
                ),
            }
        )
    elif unique_players < max(8, lineup_count):
        signals.append(
            {
                "id": "low-player-diversity",
                "type": "LOW_PLAYER_DIVERSITY",
                "severity": "moderate",
                "unique_players": unique_players,
                "explanation": (
                    f"Only {unique_players} unique players across "
                    f"{lineup_count} lineups."
                ),
            }
        )

    if len(core) >= 3:
        names = ", ".join(
            str(item.get("name") or item.get("player_id"))
            for item in core[:4]
        )
        signals.append(
            {
                "id": "strong-core",
                "type": "STRONG_CORE",
                "severity": "info",
                "explanation": (
                    f"These players form the core of your "
                    f"portfolio: {names}."
                ),
            }
        )

    for conflict in conflicts:
        conflict_type = str(
            conflict.get("type") or "EXPOSURE_CONSTRAINT_CONFLICT"
        )
        pid = conflict.get("player_id")
        alerts.append(
            {
                "id": (
                    f"constraint-{pid}"
                    if pid
                    else f"constraint-{conflict_type.lower()}"
                ),
                "type": conflict_type,
                "severity": (
                    "high"
                    if conflict_type == "PORTFOLIO_UNDERFILLED"
                    else "moderate"
                ),
                "player_id": pid,
                "explanation": conflict.get("explanation"),
                "action": (
                    "Adjust Constraints"
                    if conflict_type == "PORTFOLIO_UNDERFILLED"
                    else "Review Exposure"
                ),
            }
        )
        signals.append(
            {
                "id": (
                    f"constraint-signal-{pid}"
                    if pid
                    else f"constraint-signal-{conflict_type.lower()}"
                ),
                "type": conflict_type,
                "severity": (
                    "high"
                    if conflict_type == "PORTFOLIO_UNDERFILLED"
                    else "moderate"
                ),
                "player_id": pid,
                "explanation": conflict.get("explanation"),
            }
        )

    return signals, alerts


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))
