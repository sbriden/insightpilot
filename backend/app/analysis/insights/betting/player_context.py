"""
Player / injury context for Sports Betting projections.

Reuses fantasy canonical facts (fact_injury, fact_depth_chart,
dim_player) and applies position-specific injury impacts
(QB / RB / WR / TE / OL / DL / LB / CB / S) so a starter QB Out
moves projections far more than a rotational linebacker.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.analysis.insights.betting.injury_impact import (
    CANONICAL_POSITIONS,
    DEPTH_CHART_POSITIONS,
    canonicalize_position,
    estimate_injury_impact,
    material_injury,
)
from app.analysis.insights.betting.pricing import num
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


# Market-implied scores often already price known outs; dampen
# the summed raw positional delta before applying to projections.
INJURY_MARKET_WEIGHT = 0.45
_MAX_OWN_ADJUSTMENT = -7.5
_MAX_OPPONENT_ADJUSTMENT = 4.5

_STATUS_WEIGHT = {
    "out": 1.0,
    "doubtful": 0.65,
    "questionable": 0.25,
}


def load_week_player_context(
    *,
    season: int,
    week: int,
) -> dict[str, Any]:
    """
    Build a team_id → injury/depth context map for one slate week.

    Returns per team:
      adjustment_pts          — net effect on THIS team's score
      opponent_adjustment_pts — effect on OPPONENT score (D injuries)
      raw_adjustment_pts / raw_opponent_adjustment_pts
      injuries / drivers
    """

    injuries = _load_injuries(season=season, week=week)
    if not injuries:
        prior = _nearest_injury_week(season=season, week=week)
        if prior is not None and prior != week:
            injuries = _load_injuries(season=season, week=prior)
            week = prior

    depth = _load_depth_chart(season=season, week=week)
    names = _load_player_directory(
        {row["player_id"] for row in injuries if row.get("player_id")}
        | {row["player_id"] for row in depth if row.get("player_id")}
    )

    starter_keys = {
        (row["team_id"], str(row.get("position") or "").upper()): row
        for row in depth
        if row.get("team_id") and row.get("position")
    }

    by_team: dict[str, dict[str, Any]] = {}
    for row in injuries:
        team_id = str(row.get("team_id") or "").strip()
        player_id = str(row.get("player_id") or "").strip()
        if not team_id or not player_id:
            continue

        status = _normalize_status(row.get("game_status"))
        if status is None and row.get("is_expected_to_play") is False:
            status = "out"
        if status not in _STATUS_WEIGHT:
            continue

        name_info = names.get(player_id) or {}
        name = name_info.get("name") or player_id
        enriched_row = row
        if not _injury_row_has_position(row):
            roster_pos = name_info.get("position")
            if roster_pos:
                enriched_row = {**row, "roster_position": roster_pos}

        position = _resolve_position(enriched_row, starter_keys)
        depth_order = _resolve_depth_order(
            player_id=player_id,
            team_id=team_id,
            position=position,
            depth_rows=depth,
        )
        is_starter = bool(
            depth_order == 1
            or (
                position == "QB"
                and depth_order is not None
                and depth_order <= 1
            )
        )

        injury_type = _clean_text(enriched_row.get("injury_type"))
        practice = _clean_text(enriched_row.get("practice_status"))
        impact = estimate_injury_impact(
            position=position,
            status=status,
            depth_order=depth_order,
            is_starter=is_starter,
        )
        # Only apply impact for starters / high-role slots, or any
        # QB Out/Doubtful, or material rotational outs.
        apply = False
        if impact.get("applies"):
            if is_starter or (
                position == "QB" and status in {"out", "doubtful"}
            ):
                apply = True
            elif status in {"out", "doubtful"} and material_injury(
                impact, min_magnitude=0.2
            ):
                apply = True

        own_raw = (
            float(impact.get("own_score_delta") or 0.0) if apply else 0.0
        )
        opp_raw = (
            float(impact.get("opponent_score_delta") or 0.0)
            if apply
            else 0.0
        )
        market_own = round(own_raw * INJURY_MARKET_WEIGHT, 2)
        market_opp = round(opp_raw * INJURY_MARKET_WEIGHT, 2)

        note = {
            "player_id": player_id,
            "player_name": name,
            "team_id": team_id,
            "position": position,
            "depth_order": depth_order,
            "depth_label": _depth_label(position, depth_order),
            "game_status": _display_status(
                status,
                enriched_row.get("game_status"),
            ),
            "practice_status": practice,
            "injury_type": injury_type,
            "is_starter": bool(is_starter),
            "impact_side": impact.get("side"),
            "role_multiplier": impact.get("role_multiplier"),
            "base_impact": impact.get("base_impact"),
            "raw_magnitude": (
                impact.get("raw_magnitude") if apply else 0.0
            ),
            "own_score_delta": market_own,
            "opponent_score_delta": market_opp,
            "projection_impact_pts": market_own if market_own else (
                market_opp if market_opp else 0.0
            ),
            "quality_factors": impact.get("quality_factors"),
            "is_expected_to_play": enriched_row.get("is_expected_to_play"),
        }

        if not (
            is_starter
            or status in {"out", "doubtful"}
            or note["projection_impact_pts"]
            or note["opponent_score_delta"]
        ):
            continue

        bucket = by_team.setdefault(
            team_id,
            {
                "adjustment_pts": 0.0,
                "opponent_adjustment_pts": 0.0,
                "raw_adjustment_pts": 0.0,
                "raw_opponent_adjustment_pts": 0.0,
                "injuries": [],
                "drivers": [],
            },
        )
        bucket["injuries"].append(note)
        if apply and (own_raw or opp_raw):
            bucket["raw_adjustment_pts"] += own_raw
            bucket["raw_opponent_adjustment_pts"] += opp_raw
            label = note["depth_label"] or position or "Player"
            detail = injury_type or note["game_status"]
            if own_raw:
                shown = market_own
                bucket["drivers"].append(
                    f"{name} ({label}) listed {note['game_status']}"
                    f"{f' — {detail}' if detail and detail != note['game_status'] else ''}"
                    f"; own projection {shown:+g} pts"
                )
            if opp_raw:
                shown = market_opp
                bucket["drivers"].append(
                    f"{name} ({label}) listed {note['game_status']}"
                    f"{f' — {detail}' if detail and detail != note['game_status'] else ''}"
                    f"; opponent projection {shown:+g} pts"
                )

    for team_id, bucket in by_team.items():
        raw_own = float(bucket["raw_adjustment_pts"])
        raw_opp = float(bucket["raw_opponent_adjustment_pts"])
        bucket["raw_adjustment_pts"] = round(raw_own, 2)
        bucket["raw_opponent_adjustment_pts"] = round(raw_opp, 2)
        bucket["adjustment_pts"] = max(
            _MAX_OWN_ADJUSTMENT,
            round(raw_own * INJURY_MARKET_WEIGHT, 2),
        )
        bucket["opponent_adjustment_pts"] = min(
            _MAX_OPPONENT_ADJUSTMENT,
            round(raw_opp * INJURY_MARKET_WEIGHT, 2),
        )
        bucket["injuries"].sort(
            key=lambda item: (
                0 if item.get("is_starter") else 1,
                -abs(
                    float(item.get("raw_magnitude") or 0)
                    or float(item.get("projection_impact_pts") or 0)
                ),
                str(item.get("player_name") or ""),
            )
        )

    return {
        "season": int(season),
        "week": int(week),
        "by_team": by_team,
        "positions_modeled": list(CANONICAL_POSITIONS),
    }


def team_injury_context(
    context: dict[str, Any] | None,
    team_id: str | None,
) -> dict[str, Any]:
    empty = {
        "adjustment_pts": 0.0,
        "opponent_adjustment_pts": 0.0,
        "raw_adjustment_pts": 0.0,
        "raw_opponent_adjustment_pts": 0.0,
        "injuries": [],
        "drivers": [],
    }
    if not context or not team_id:
        return dict(empty)
    return dict(context.get("by_team", {}).get(str(team_id), empty))


def combined_score_adjustments(
    *,
    home_injury: dict[str, Any] | None,
    away_injury: dict[str, Any] | None,
) -> tuple[float, float]:
    """
    Net home/away score deltas from both teams' injury reports.

    Offense injuries cut that team's score; defense injuries raise
    the opponent's score.
    """

    home = home_injury or {}
    away = away_injury or {}
    home_adj = (
        float(home.get("adjustment_pts") or 0.0)
        + float(away.get("opponent_adjustment_pts") or 0.0)
    )
    away_adj = (
        float(away.get("adjustment_pts") or 0.0)
        + float(home.get("opponent_adjustment_pts") or 0.0)
    )
    return round(home_adj, 2), round(away_adj, 2)


def apply_injury_adjustment(
    score: float | None,
    adjustment_pts: float,
) -> float | None:
    if score is None:
        return None
    return round(float(score) + float(adjustment_pts or 0.0), 1)


def _normalize_status(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    if lowered in _STATUS_WEIGHT:
        return lowered
    if "out" in lowered:
        return "out"
    if "doubt" in lowered:
        return "doubtful"
    if "question" in lowered:
        return "questionable"
    return None


def _display_status(normalized: str | None, raw: Any) -> str:
    text = _clean_text(raw)
    if text:
        return text
    if normalized:
        return normalized.title()
    return "Unknown"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\n", " ")
    if not text or text.lower() in {"nan", "none", "nat", "<na>"}:
        return None
    if text.lower().startswith("not injury related"):
        return None
    return text


def _resolve_position(
    injury_row: dict[str, Any],
    starter_keys: dict[tuple[str, str], dict[str, Any]],
) -> str:
    for key in ("position", "roster_position", "depth_position"):
        pos = _clean_text(injury_row.get(key))
        if pos:
            canonical = canonicalize_position(pos)
            if canonical:
                return canonical
    team_id = str(injury_row.get("team_id") or "")
    player_id = str(injury_row.get("player_id") or "")
    for (tid, pos), starter in starter_keys.items():
        if tid == team_id and str(starter.get("player_id")) == player_id:
            return canonicalize_position(pos) or pos
    # Unknown skill → WR as soft default keeps prior behavior for
    # offense-only reports without a roster position.
    return "WR"


def _resolve_depth_order(
    *,
    player_id: str,
    team_id: str,
    position: str | None,
    depth_rows: list[dict[str, Any]],
) -> int | None:
    matches = [
        row
        for row in depth_rows
        if str(row.get("player_id")) == player_id
        and str(row.get("team_id")) == team_id
    ]
    if not matches:
        return None
    if position:
        canonical = canonicalize_position(position) or position.upper()
        pos_matches = [
            row
            for row in matches
            if (
                canonicalize_position(row.get("position"))
                or str(row.get("position") or "").upper()
            )
            == canonical
        ]
        if pos_matches:
            matches = pos_matches
    orders = [
        int(row["depth_order"])
        for row in matches
        if num(row.get("depth_order")) is not None
    ]
    return min(orders) if orders else None


def _depth_label(position: str | None, depth_order: int | None) -> str | None:
    if not position:
        return None
    if depth_order is None:
        return position
    return f"{position}{depth_order}"


def _fetch_rows(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params).mappings().all()
    return [dict(row) for row in rows]


def _load_injuries(*, season: int, week: int) -> list[dict[str, Any]]:
    try:
        return _fetch_rows(
            f"""
            SELECT DISTINCT ON (player_id)
              player_id,
              team_id,
              report_date,
              season,
              week,
              injury_type,
              practice_status,
              game_status,
              is_expected_to_play
            FROM {FANTASY_SCHEMA}.fact_injury
            WHERE season = :season
              AND week = :week
            ORDER BY player_id, report_date DESC NULLS LAST
            """,
            {"season": int(season), "week": int(week)},
        )
    except Exception:
        return []


def _nearest_injury_week(*, season: int, week: int) -> int | None:
    try:
        rows = _fetch_rows(
            f"""
            SELECT MAX(week) AS week
            FROM {FANTASY_SCHEMA}.fact_injury
            WHERE season = :season
              AND week <= :week
            """,
            {"season": int(season), "week": int(week)},
        )
    except Exception:
        return None
    if not rows:
        return None
    return _as_int(rows[0].get("week"))


def _depth_rows_for_week(
    *,
    season: int,
    week: int,
) -> list[dict[str, Any]]:
    return _fetch_rows(
        f"""
        SELECT
          team_id,
          player_id,
          position,
          depth_order,
          role,
          week
        FROM {FANTASY_SCHEMA}.fact_depth_chart
        WHERE season = :season
          AND week = :week
          AND depth_order IS NOT NULL
          AND depth_order <= 3
        """,
        {"season": int(season), "week": int(week)},
    )


def _load_depth_chart(
    *,
    season: int,
    week: int,
) -> list[dict[str, Any]]:
    try:
        week_rows = _depth_rows_for_week(season=season, week=week)
        if not week_rows:
            prior = _fetch_rows(
                f"""
                SELECT MAX(week) AS week
                FROM {FANTASY_SCHEMA}.fact_depth_chart
                WHERE season = :season
                  AND week <= :week
                """,
                {"season": int(season), "week": int(week)},
            )
            target = _as_int(prior[0].get("week")) if prior else None
            if target is None or target == week:
                return []
            week_rows = _depth_rows_for_week(
                season=season,
                week=target,
            )
    except Exception:
        return []

    chart: list[dict[str, Any]] = []
    for row in week_rows:
        raw_pos = str(row.get("position") or "").strip().upper()
        if raw_pos not in DEPTH_CHART_POSITIONS and not canonicalize_position(
            raw_pos
        ):
            continue
        canonical = canonicalize_position(raw_pos) or raw_pos
        if canonical not in CANONICAL_POSITIONS:
            continue
        order = _as_int(row.get("depth_order"))
        # Keep starters + next two for role multipliers.
        if order is None or order > 3:
            continue
        chart.append({**row, "position": canonical})
    return chart


def _load_player_directory(
    player_ids: set[str],
) -> dict[str, dict[str, str]]:
    ids = [str(player_id).strip() for player_id in player_ids if player_id]
    if not ids:
        return {}
    try:
        params = {
            f"id_{index}": player_id
            for index, player_id in enumerate(ids)
        }
        placeholders = ", ".join(
            f":id_{index}" for index in range(len(ids))
        )
        rows = _fetch_rows(
            f"""
            SELECT player_id, name, position
            FROM {FANTASY_SCHEMA}.dim_player
            WHERE player_id IN ({placeholders})
            """,
            params,
        )
    except Exception:
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        pid = str(row.get("player_id") or "").strip()
        if not pid:
            continue
        name = _clean_text(row.get("name"))
        position = _clean_text(row.get("position"))
        entry: dict[str, str] = {}
        if name:
            entry["name"] = name
        if position:
            canonical = canonicalize_position(position) or position.upper()
            entry["position"] = canonical
        if entry:
            out[pid] = entry
    return out


def _injury_row_has_position(row: dict[str, Any]) -> bool:
    for key in ("position", "roster_position", "depth_position"):
        if _clean_text(row.get(key)):
            return True
    return False


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
