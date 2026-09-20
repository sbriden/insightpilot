"""DFS lineup optimizer (score-based greedy fill)."""

from __future__ import annotations

import copy
from typing import Any

from app.analysis.insights.dfs.insights import (
    build_lineup_insights,
)
from app.analysis.insights.dfs.sites import (
    get_site_config,
    normalize_contest_type,
)
from app.analysis.insights.dfs.slate import build_dfs_slate


STRATEGY_WEIGHTS: dict[str, dict[str, float]] = {
    "cash": {
        "projection": 0.35,
        "floor": 0.30,
        "value": 0.20,
        "ownership": 0.05,
        "ceiling": 0.05,
        "correlation": 0.05,
    },
    "gpp": {
        "projection": 0.25,
        "floor": 0.05,
        "value": 0.15,
        "ownership": 0.20,
        "ceiling": 0.25,
        "correlation": 0.10,
    },
    "custom": {
        "projection": 0.40,
        "floor": 0.10,
        "value": 0.15,
        "ownership": 0.15,
        "ceiling": 0.15,
        "correlation": 0.05,
    },
    "balanced": {
        "projection": 0.40,
        "floor": 0.15,
        "value": 0.15,
        "ownership": 0.10,
        "ceiling": 0.15,
        "correlation": 0.05,
    },
}


RISK_BLEND: dict[str, dict[str, float]] = {
    "conservative": {
        "floor": 0.15,
        "ceiling": -0.10,
        "ownership": -0.05,
    },
    "balanced": {},
    "aggressive": {
        "ceiling": 0.15,
        "ownership": 0.10,
        "floor": -0.10,
    },
}


def optimize_lineup(
    *,
    slate_id: str,
    site: str = "draftkings",
    contest_type: str = "classic",
    risk: str = "balanced",
    strategy: str | None = None,
    locked_players: list[str] | None = None,
    excluded_players: list[str] | None = None,
    min_salary: int | None = None,
    max_ownership: float | None = None,
    season: int | None = None,
) -> dict[str, Any]:
    format_key, strategy_from_contest = _normalize_contest_inputs(
        contest_type
    )
    site_config = get_site_config(
        site,
        contest_type=format_key,
    )
    slate = build_dfs_slate(
        slate_id,
        site=site_config["id"],
        season=season,
        contest_type=format_key,
    )
    players = list(slate.get("players") or [])
    locked = {
        str(item).strip()
        for item in (locked_players or [])
        if str(item).strip()
    }
    excluded = {
        str(item).strip()
        for item in (excluded_players or [])
        if str(item).strip()
    }

    risk_key = str(risk or "balanced").strip().lower()
    if risk_key not in RISK_BLEND:
        risk_key = "balanced"
    strategy_key = str(
        strategy or strategy_from_contest or "gpp"
    ).strip().lower()
    if strategy_key not in STRATEGY_WEIGHTS:
        strategy_key = "gpp"

    weights = dict(STRATEGY_WEIGHTS[strategy_key])
    for key, delta in RISK_BLEND[risk_key].items():
        weights[key] = max(0.0, weights.get(key, 0.0) + delta)
    total_w = sum(weights.values()) or 1.0
    weights = {
        key: value / total_w for key, value in weights.items()
    }

    pool = [
        player
        for player in players
        if player.get("player_id") not in excluded
    ]
    for player in pool:
        player["_opt_score"] = _player_score(
            player,
            weights=weights,
            max_ownership=max_ownership,
        )

    salary_cap = int(site_config["salary_cap"])
    captain_mult = float(
        site_config.get("captain_multiplier") or 1.0
    )

    if format_key == "showdown":
        selected = _optimize_showdown(
            pool=pool,
            salary_cap=salary_cap,
            captain_multiplier=captain_mult,
            locked=locked,
            max_ownership=max_ownership,
        )
    else:
        selected = _optimize_classic(
            pool=pool,
            roster_slots=copy.deepcopy(site_config["roster"]),
            salary_cap=salary_cap,
            locked=locked,
            excluded=excluded,
            max_ownership=max_ownership,
            min_salary=min_salary,
        )

    salary_used = sum(
        int(item.get("salary") or 0) for item in selected
    )
    projection = round(
        sum(
            float(item.get("projection") or 0.0)
            for item in selected
        ),
        1,
    )
    floor = round(
        sum(float(item.get("floor") or 0.0) for item in selected),
        1,
    )
    ceiling = round(
        sum(
            float(item.get("ceiling") or 0.0)
            for item in selected
        ),
        1,
    )
    ownership = round(
        sum(
            float(item.get("projected_ownership") or 0.0) * 100.0
            for item in selected
        ),
        1,
    )
    value = None
    if salary_used > 0:
        value = round(projection / (salary_used / 1000.0), 2)

    roster_size = len(site_config["roster"])
    lineup = {
        "lineup_id": (
            f"opt-{slate['slate_id']}-"
            f"{site_config['id']}-{format_key}"
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
        "captain_multiplier": captain_mult,
        "valid": len(selected) == roster_size
        and salary_used <= salary_cap,
    }

    insights, signals = build_lineup_insights(lineup, slate=slate)
    lineup["insights"] = insights
    lineup["signals"] = signals
    lineup["edge_summary"] = _edge_summary(lineup)

    return {
        "lineup": lineup,
        "alternatives": [],
        "insights": insights,
        "signals": signals,
        "optimization_metadata": {
            "players_evaluated": len(pool),
            "strategy": strategy_key,
            "contest_type": format_key,
            "risk": risk_key,
            "weights": weights,
            "locked_count": len(locked),
            "excluded_count": len(excluded),
            "site": site_config["id"],
            "salary_cap": salary_cap,
            "captain_multiplier": captain_mult,
        },
        "slate": {
            "slate_id": slate["slate_id"],
            "label": slate.get("label"),
            "freshness": slate.get("freshness"),
            "contest_type": format_key,
        },
    }


def _normalize_contest_inputs(
    contest_type: str | None,
) -> tuple[str, str | None]:
    """
    Returns (format, legacy_strategy).

    Older clients sent cash/gpp/custom as contest_type.
    """

    raw = str(contest_type or "classic").strip().lower()
    if raw in STRATEGY_WEIGHTS:
        return "classic", raw
    return normalize_contest_type(raw), None


def _optimize_classic(
    *,
    pool: list[dict[str, Any]],
    roster_slots: list[dict[str, Any]],
    salary_cap: int,
    locked: set[str],
    excluded: set[str],
    max_ownership: float | None,
    min_salary: int | None,
) -> list[dict[str, Any]]:
    by_id = {
        str(player["player_id"]): player
        for player in pool
        if player.get("player_id")
    }
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    salary_used = 0

    for player_id in locked:
        player = by_id.get(player_id)
        if player is None:
            continue
        slot_index = _first_compatible_slot(
            roster_slots,
            player,
        )
        if slot_index is None:
            continue
        slot = roster_slots[slot_index]
        salary = int(player.get("salary") or 0)
        if salary_used + salary > salary_cap:
            continue
        selected.append(
            _lineup_player(
                player,
                slot=slot["slot"],
                locked=True,
            )
        )
        used_ids.add(player_id)
        salary_used += salary
        roster_slots[slot_index] = {**slot, "_filled": True}

    remaining_slots = [
        (index, slot)
        for index, slot in enumerate(roster_slots)
        if not slot.get("_filled")
    ]

    for offset, (index, slot) in enumerate(remaining_slots):
        later_slots = [
            item for _, item in remaining_slots[offset + 1 :]
        ]
        reserved = _reserve_salary_for_slots(
            later_slots,
            pool=pool,
            used_ids=used_ids,
        )
        budget = salary_cap - salary_used - reserved
        candidates = _slot_candidates(
            pool=pool,
            slot=slot,
            used_ids=used_ids,
            salary_budget=max(budget, 0),
            salary_cap=salary_cap,
            salary_used=salary_used,
            max_ownership=max_ownership,
            relax=False,
        )
        if not candidates:
            candidates = _slot_candidates(
                pool=pool,
                slot=slot,
                used_ids=used_ids,
                salary_budget=salary_cap - salary_used,
                salary_cap=salary_cap,
                salary_used=salary_used,
                max_ownership=max_ownership,
                relax=True,
            )
        if not candidates:
            continue
        candidates.sort(
            key=lambda item: (
                -float(item.get("_opt_score") or 0.0),
                -float(item.get("projection") or 0.0),
                int(item.get("salary") or 0),
            )
        )
        pick = candidates[0]
        salary = int(pick.get("salary") or 0)
        selected.append(
            _lineup_player(
                pick,
                slot=slot["slot"],
                locked=False,
            )
        )
        used_ids.add(str(pick["player_id"]))
        salary_used += salary
        roster_slots[index] = {**slot, "_filled": True}

    selected = _upgrade_lineup(
        selected,
        pool=pool,
        salary_cap=salary_cap,
        excluded=excluded,
        locked=locked,
        max_ownership=max_ownership,
        captain_multiplier=1.0,
        contest_type="classic",
    )

    if min_salary is not None:
        salary_used = sum(
            int(item.get("salary") or 0) for item in selected
        )
        if salary_used < int(min_salary):
            selected = _spend_up(
                selected,
                pool=pool,
                salary_cap=salary_cap,
                min_salary=int(min_salary),
                locked=locked,
                excluded=excluded,
                max_ownership=max_ownership,
                captain_multiplier=1.0,
                contest_type="classic",
            )
    return selected


def _optimize_showdown(
    *,
    pool: list[dict[str, Any]],
    salary_cap: int,
    captain_multiplier: float,
    locked: set[str],
    max_ownership: float | None,
) -> list[dict[str, Any]]:
    """
    Captain (1.5× salary / 1.5× points) + 5 FLEX from the same game.
    Try each viable captain and greedily fill FLEX.
    """

    if len(pool) < 6:
        return []

    mult = float(captain_multiplier) or 1.5
    captain_candidates = list(pool)
    if locked:
        locked_pool = [
            player
            for player in pool
            if str(player.get("player_id")) in locked
        ]
        if locked_pool:
            # Prefer locked players as captain when present.
            captain_candidates = locked_pool + [
                player
                for player in pool
                if str(player.get("player_id")) not in locked
            ]

    best: list[dict[str, Any]] = []
    best_score = float("-inf")

    # Cap captain search for large pools; score-sorted.
    captain_candidates = sorted(
        captain_candidates,
        key=lambda item: (
            -float(item.get("_opt_score") or 0.0),
            -float(item.get("projection") or 0.0),
        ),
    )[: min(len(captain_candidates), 24)]

    for captain in captain_candidates:
        cpt_id = str(captain.get("player_id") or "")
        if not cpt_id:
            continue
        cpt_salary = int(
            round(int(captain.get("salary") or 0) * mult)
        )
        if cpt_salary > salary_cap:
            continue

        used = {cpt_id}
        salary_used = cpt_salary
        selected = [
            _lineup_player(
                captain,
                slot="CPT",
                locked=cpt_id in locked,
                multiplier=mult,
            )
        ]

        remaining_flex = 5
        for flex_index in range(remaining_flex):
            later = remaining_flex - flex_index - 1
            reserved = _cheapest_n(
                pool,
                used_ids=used,
                count=later,
                exclude_salary_mult=1.0,
            )
            budget = salary_cap - salary_used - reserved
            candidates = [
                player
                for player in pool
                if str(player.get("player_id")) not in used
                and int(player.get("salary") or 0) <= max(budget, 0)
                and (
                    max_ownership is None
                    or (player.get("projected_ownership") or 0)
                    <= float(max_ownership)
                )
            ]
            if not candidates:
                candidates = [
                    player
                    for player in pool
                    if str(player.get("player_id")) not in used
                    and salary_used + int(player.get("salary") or 0)
                    <= salary_cap
                    and (
                        max_ownership is None
                        or (player.get("projected_ownership") or 0)
                        <= float(max_ownership)
                    )
                ]
            # Prefer filling remaining locks into FLEX.
            locked_left = [
                player
                for player in candidates
                if str(player.get("player_id")) in locked
            ]
            if locked_left:
                candidates = locked_left
            if not candidates:
                break
            candidates.sort(
                key=lambda item: (
                    -float(item.get("_opt_score") or 0.0),
                    -float(item.get("projection") or 0.0),
                    int(item.get("salary") or 0),
                )
            )
            pick = candidates[0]
            pid = str(pick["player_id"])
            selected.append(
                _lineup_player(
                    pick,
                    slot="FLEX",
                    locked=pid in locked,
                )
            )
            used.add(pid)
            salary_used += int(pick.get("salary") or 0)

        if len(selected) < 6:
            continue

        # Soft-upgrade FLEX seats.
        selected = _upgrade_lineup(
            selected,
            pool=pool,
            salary_cap=salary_cap,
            excluded=set(),
            locked=locked,
            max_ownership=max_ownership,
            captain_multiplier=mult,
            contest_type="showdown",
        )

        total_proj = sum(
            float(item.get("projection") or 0.0)
            for item in selected
        )
        if total_proj > best_score or not best:
            best = selected
            best_score = total_proj

    return best


def _cheapest_n(
    pool: list[dict[str, Any]],
    *,
    used_ids: set[str],
    count: int,
    exclude_salary_mult: float,
) -> int:
    del exclude_salary_mult
    if count <= 0:
        return 0
    options = sorted(
        (
            int(player.get("salary") or 0)
            for player in pool
            if str(player.get("player_id")) not in used_ids
        )
    )
    if not options:
        return 2500 * count
    return sum(options[:count]) + max(
        0, count - len(options)
    ) * 2500


def _slot_candidates(
    *,
    pool: list[dict[str, Any]],
    slot: dict[str, Any],
    used_ids: set[str],
    salary_budget: int,
    salary_cap: int,
    salary_used: int,
    max_ownership: float | None,
    relax: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for player in pool:
        pid = str(player.get("player_id") or "")
        if not pid or pid in used_ids:
            continue
        if not _fits_slot(player, slot):
            continue
        salary = int(player.get("salary") or 0)
        if relax:
            if salary_used + salary > salary_cap:
                continue
        elif salary > salary_budget:
            continue
        if (
            max_ownership is not None
            and (player.get("projected_ownership") or 0)
            > float(max_ownership)
        ):
            continue
        out.append(player)
    return out


def _player_score(
    player: dict[str, Any],
    *,
    weights: dict[str, float],
    max_ownership: float | None,
) -> float:
    projection = float(player.get("projection") or 0.0)
    floor = float(player.get("floor") or projection * 0.65)
    ceiling = float(player.get("ceiling") or projection * 1.4)
    value = float(player.get("value") or 0.0)
    ownership = float(player.get("projected_ownership") or 0.12)
    if max_ownership is not None and ownership > float(max_ownership):
        return -1e9

    proj_n = min(100.0, projection * 3.5)
    floor_n = min(100.0, floor * 4.0)
    ceil_n = min(100.0, ceiling * 2.8)
    value_n = min(100.0, value * 25.0)
    own_n = max(0.0, 100.0 - ownership * 280.0)

    return (
        weights.get("projection", 0) * proj_n
        + weights.get("floor", 0) * floor_n
        + weights.get("ceiling", 0) * ceil_n
        + weights.get("value", 0) * value_n
        + weights.get("ownership", 0) * own_n
    )


def _reserve_salary_for_slots(
    slots: list[dict[str, Any]],
    *,
    pool: list[dict[str, Any]],
    used_ids: set[str],
) -> int:
    """Cheapest feasible salary needed to finish remaining slots."""

    reserved = 0
    claimed: set[str] = set()
    for slot in slots:
        options = sorted(
            (
                player
                for player in pool
                if str(player.get("player_id")) not in used_ids
                and str(player.get("player_id")) not in claimed
                and _fits_slot(player, slot)
            ),
            key=lambda item: int(item.get("salary") or 0),
        )
        if not options:
            reserved += 2500
            continue
        pick = options[0]
        claimed.add(str(pick["player_id"]))
        reserved += int(pick.get("salary") or 2500)
    return reserved


def _is_defense(player: dict[str, Any]) -> bool:
    position = str(player.get("position") or "").upper()
    return (
        position in {"DEF", "DST"}
        or bool(player.get("is_team_defense"))
    )


def _fits_slot(
    player: dict[str, Any],
    slot: dict[str, Any],
    *,
    contest_type: str | None = None,
) -> bool:
    position = str(player.get("position") or "").upper()
    slot_name = str(slot.get("slot") or "").upper()
    allowed = {
        str(item).upper()
        for item in (slot.get("positions") or [])
    }
    format_key = str(contest_type or "").strip().lower()
    # Infer showdown from open-seat markers when not passed.
    if not format_key:
        if "CPT" in allowed or (
            slot_name in {"CPT", "FLEX"} and "FLEX" in allowed
        ):
            format_key = "showdown"
        else:
            format_key = "classic"
    # Classic FLEX is RB/WR/TE only — no defenses.
    if (
        format_key != "showdown"
        and slot_name == "FLEX"
        and _is_defense(player)
    ):
        return False
    if position in allowed:
        return True
    if position == "DEF" and (
        "DST" in allowed or "DEF" in allowed
    ):
        return True
    if position == "K" and "K" in allowed:
        return True
    if slot_name in {"CPT", "FLEX"} and (
        "CPT" in allowed or "FLEX" in allowed or not allowed
    ):
        # Showdown open seats marked with CPT/FLEX sentinels.
        return True
    return False


def _first_compatible_slot(
    roster_slots: list[dict[str, Any]],
    player: dict[str, Any],
) -> int | None:
    for index, slot in enumerate(roster_slots):
        if slot.get("_filled"):
            continue
        if _fits_slot(player, slot):
            return index
    return None


def _lineup_player(
    player: dict[str, Any],
    *,
    slot: str,
    locked: bool,
    multiplier: float = 1.0,
) -> dict[str, Any]:
    mult = float(multiplier) if multiplier else 1.0
    base_salary = int(player.get("salary") or 0)
    base_proj = float(player.get("projection") or 0.0)
    base_floor = float(player.get("floor") or base_proj * 0.65)
    base_ceil = float(player.get("ceiling") or base_proj * 1.4)
    salary = int(round(base_salary * mult))
    projection = round(base_proj * mult, 1)
    floor = round(base_floor * mult, 1)
    ceiling = round(base_ceil * mult, 1)
    value = None
    if salary > 0:
        value = round(projection / (salary / 1000.0), 2)
    return {
        "slot": slot,
        "player_id": player.get("player_id"),
        "dfs_player_id": player.get("dfs_player_id"),
        "name": player.get("name"),
        "position": player.get("position"),
        "team": player.get("team"),
        "opponent": player.get("opponent"),
        "salary": salary,
        "base_salary": base_salary,
        "projection": projection,
        "base_projection": round(base_proj, 1),
        "floor": floor,
        "ceiling": ceiling,
        "projected_ownership": player.get("projected_ownership"),
        "value": value,
        "matchup_label": player.get("matchup_label"),
        "primary_signal": player.get("primary_signal"),
        "locked": locked,
        "is_captain": str(slot or "").upper() == "CPT",
        "captain_multiplier": mult if mult != 1.0 else None,
        "is_team_defense": player.get("is_team_defense"),
    }


def _upgrade_lineup(
    selected: list[dict[str, Any]],
    *,
    pool: list[dict[str, Any]],
    salary_cap: int,
    excluded: set[str],
    locked: set[str],
    max_ownership: float | None,
    captain_multiplier: float,
    contest_type: str = "classic",
) -> list[dict[str, Any]]:
    result = list(selected)
    by_id = {
        str(player["player_id"]): player
        for player in pool
        if player.get("player_id")
    }
    used = {str(item["player_id"]) for item in result}

    for index, current in enumerate(list(result)):
        player_id = str(current.get("player_id") or "")
        if player_id in locked:
            continue
        current_full = by_id.get(player_id)
        if current_full is None:
            continue
        is_cpt = str(current.get("slot") or "").upper() == "CPT"
        mult = captain_multiplier if is_cpt else 1.0
        current_score = float(
            current_full.get("_opt_score") or 0.0
        ) * mult
        salary_without = sum(
            int(item.get("salary") or 0)
            for item_index, item in enumerate(result)
            if item_index != index
        )
        slot = {
            "slot": current["slot"],
            "positions": _slot_positions(
                current["slot"],
                contest_type=contest_type,
            ),
        }
        for candidate in pool:
            cid = str(candidate.get("player_id") or "")
            if not cid or cid in used or cid in excluded:
                continue
            if not _fits_slot(
                candidate,
                slot,
                contest_type=contest_type,
            ):
                continue
            cand_salary = int(
                round(int(candidate.get("salary") or 0) * mult)
            )
            if salary_without + cand_salary > salary_cap:
                continue
            if (
                max_ownership is not None
                and (candidate.get("projected_ownership") or 0)
                > float(max_ownership)
            ):
                continue
            cand_score = float(
                candidate.get("_opt_score") or 0.0
            ) * mult
            if cand_score <= current_score:
                continue
            used.discard(player_id)
            used.add(cid)
            result[index] = _lineup_player(
                candidate,
                slot=current["slot"],
                locked=False,
                multiplier=mult,
            )
            current_score = cand_score
            player_id = cid
    return result


def _spend_up(
    selected: list[dict[str, Any]],
    *,
    pool: list[dict[str, Any]],
    salary_cap: int,
    min_salary: int,
    locked: set[str],
    excluded: set[str],
    max_ownership: float | None,
    captain_multiplier: float,
    contest_type: str = "classic",
) -> list[dict[str, Any]]:
    result = list(selected)
    used = {str(item["player_id"]) for item in result}

    for _ in range(12):
        salary_used = sum(
            int(item.get("salary") or 0) for item in result
        )
        if salary_used >= min_salary:
            break
        improved = False
        for index, current in enumerate(result):
            pid = str(current.get("player_id") or "")
            if pid in locked:
                continue
            is_cpt = (
                str(current.get("slot") or "").upper() == "CPT"
            )
            mult = captain_multiplier if is_cpt else 1.0
            salary_without = salary_used - int(
                current.get("salary") or 0
            )
            slot = {
                "slot": current["slot"],
                "positions": _slot_positions(
                    current["slot"],
                    contest_type=contest_type,
                ),
            }
            current_proj = float(current.get("projection") or 0.0)
            upgrades = []
            for candidate in pool:
                cid = str(candidate.get("player_id") or "")
                if (
                    not cid
                    or cid in used
                    or cid in excluded
                    or not _fits_slot(
                        candidate,
                        slot,
                        contest_type=contest_type,
                    )
                ):
                    continue
                cand_salary = int(
                    round(int(candidate.get("salary") or 0) * mult)
                )
                cand_proj = round(
                    float(candidate.get("projection") or 0.0)
                    * mult,
                    1,
                )
                if salary_without + cand_salary > salary_cap:
                    continue
                if cand_salary <= int(current.get("salary") or 0):
                    continue
                if cand_proj < current_proj - 1.5:
                    continue
                if (
                    max_ownership is not None
                    and (candidate.get("projected_ownership") or 0)
                    > float(max_ownership)
                ):
                    continue
                upgrades.append((candidate, cand_salary, cand_proj))
            if not upgrades:
                continue
            upgrades.sort(
                key=lambda item: (-item[2], -item[1])
            )
            pick, _, _ = upgrades[0]
            used.discard(pid)
            used.add(str(pick["player_id"]))
            result[index] = _lineup_player(
                pick,
                slot=current["slot"],
                locked=False,
                multiplier=mult,
            )
            improved = True
            break
        if not improved:
            break
    return result


def _slot_positions(
    slot: str,
    *,
    contest_type: str = "classic",
) -> list[str]:
    key = str(slot or "").upper()
    if key == "CPT":
        return [
            "QB",
            "RB",
            "WR",
            "TE",
            "DEF",
            "DST",
            "K",
            "FLEX",
            "CPT",
        ]
    if key == "FLEX":
        if contest_type == "showdown":
            return [
                "QB",
                "RB",
                "WR",
                "TE",
                "DEF",
                "DST",
                "K",
                "FLEX",
                "CPT",
            ]
        return ["RB", "WR", "TE"]
    if key == "DST":
        return ["DEF", "DST"]
    return [key]


def _edge_summary(lineup: dict[str, Any]) -> str:
    projection = lineup.get("projected_points")
    value = lineup.get("value")
    ownership = lineup.get("projected_ownership")
    contest = str(lineup.get("contest_type") or "")
    parts = []
    if contest == "showdown":
        parts.append("showdown captain leverage")
    if projection is not None:
        parts.append(f"{projection:.1f} projected points")
    if value is not None and value >= 2.6:
        parts.append("strong salary efficiency")
    if ownership is not None and ownership < 110:
        parts.append("differentiated ownership")
    elif ownership is not None and ownership > 140:
        parts.append("chalk-heavy construction")
    if not parts:
        return (
            "InsightPilot built this lineup from projection, "
            "value, and contest strategy signals."
        )
    if len(parts) == 1:
        joined = parts[0]
    else:
        joined = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    return f"This lineup combines {joined}."
