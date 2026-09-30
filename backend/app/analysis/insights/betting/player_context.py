"""
Player / injury context for Sports Betting projections.

Reuses fantasy canonical facts (fact_injury, fact_depth_chart,
dim_player) so betting totals reflect starter availability the
same way Player Overview surfaces injury status.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.pricing import num


# Raw team-point deltas before market double-count dampening.
# Market-implied scores often already price known outs; callers
# apply INJURY_MARKET_WEIGHT to the summed raw delta.
_STATUS_WEIGHT = {
    "out": 1.0,
    "doubtful": 0.65,
    "questionable": 0.25,
}

_POSITION_IMPACT = {
    "QB": 4.0,
    "RB": 1.5,
    "WR": 1.0,
    "TE": 0.6,
}

_OFFENSE_POSITIONS = {"QB", "RB", "WR", "TE", "FB", "HB"}
INJURY_MARKET_WEIGHT = 0.45
_MAX_TEAM_ADJUSTMENT = -6.0


def load_week_player_context(
    *,
    season: int,
    week: int,
) -> dict[str, Any]:
    """
    Build a team_id → injury/depth context map for one slate week.

    Returns:
      {
        "season": int,
        "week": int,
        "by_team": {
          team_id: {
            "adjustment_pts": float,
            "raw_adjustment_pts": float,
            "injuries": [InjuryNote, ...],
            "drivers": [str, ...],
          }
        }
      }
    """

    injuries = _load_injuries(season=season, week=week)
    if not injuries:
        # Fall back to nearest prior week with reports.
        prior = _nearest_injury_week(season=season, week=week)
        if prior is not None and prior != week:
            injuries = _load_injuries(season=season, week=prior)
            week = prior

    depth = _load_depth_starters(season=season, week=week)
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
        is_starter = depth_order == 1 or (
            position == "QB"
            and depth_order is not None
            and depth_order <= 1
        )

        injury_type = _clean_text(enriched_row.get("injury_type"))
        practice = _clean_text(enriched_row.get("practice_status"))
        raw_delta = 0.0
        if is_starter or (
            position == "QB" and status in {"out", "doubtful"}
        ):
            raw_delta = _raw_point_delta(position=position, status=status)

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
            "projection_impact_pts": (
                round(raw_delta * INJURY_MARKET_WEIGHT, 2)
                if raw_delta
                else 0.0
            ),
            "is_expected_to_play": enriched_row.get("is_expected_to_play"),
        }

        # Keep the board focused: starters, or Out/Doubtful anyone.
        if not (
            is_starter
            or status in {"out", "doubtful"}
            or note["projection_impact_pts"]
        ):
            continue

        bucket = by_team.setdefault(
            team_id,
            {
                "adjustment_pts": 0.0,
                "raw_adjustment_pts": 0.0,
                "injuries": [],
                "drivers": [],
            },
        )
        bucket["injuries"].append(note)
        if raw_delta:
            bucket["raw_adjustment_pts"] += raw_delta
            impact = round(raw_delta * INJURY_MARKET_WEIGHT, 2)
            label = note["depth_label"] or position or "Player"
            detail = injury_type or note["game_status"]
            bucket["drivers"].append(
                f"{name} ({label}) listed {note['game_status']}"
                f"{f' — {detail}' if detail and detail != note['game_status'] else ''}"
                f"; projection {impact:+g} pts"
            )

    for team_id, bucket in by_team.items():
        raw = float(bucket["raw_adjustment_pts"])
        adjusted = max(
            _MAX_TEAM_ADJUSTMENT,
            round(raw * INJURY_MARKET_WEIGHT, 2),
        )
        bucket["raw_adjustment_pts"] = round(raw, 2)
        bucket["adjustment_pts"] = adjusted
        # Sort: starters first, then by absolute impact, then name.
        bucket["injuries"].sort(
            key=lambda item: (
                0 if item.get("is_starter") else 1,
                -abs(float(item.get("projection_impact_pts") or 0)),
                str(item.get("player_name") or ""),
            )
        )

    return {
        "season": int(season),
        "week": int(week),
        "by_team": by_team,
    }


def team_injury_context(
    context: dict[str, Any] | None,
    team_id: str | None,
) -> dict[str, Any]:
    if not context or not team_id:
        return {
            "adjustment_pts": 0.0,
            "raw_adjustment_pts": 0.0,
            "injuries": [],
            "drivers": [],
        }
    return dict(
        context.get("by_team", {}).get(
            str(team_id),
            {
                "adjustment_pts": 0.0,
                "raw_adjustment_pts": 0.0,
                "injuries": [],
                "drivers": [],
            },
        )
    )


def apply_injury_adjustment(
    score: float | None,
    adjustment_pts: float,
) -> float | None:
    if score is None:
        return None
    return round(float(score) + float(adjustment_pts or 0.0), 1)


def _raw_point_delta(*, position: str | None, status: str) -> float:
    pos = (position or "").upper()
    base = _POSITION_IMPACT.get(pos)
    if base is None:
        return 0.0
    weight = _STATUS_WEIGHT.get(status, 0.0)
    if weight <= 0:
        return 0.0
    return -abs(base) * weight


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
    # Prefer roster/depth offense position when available.
    for key in ("position", "roster_position", "depth_position"):
        pos = _clean_text(injury_row.get(key))
        if pos:
            upper = pos.upper()
            if upper in {"FB", "HB"}:
                return "RB"
            if upper in _OFFENSE_POSITIONS:
                return upper
    team_id = str(injury_row.get("team_id") or "")
    player_id = str(injury_row.get("player_id") or "")
    for (tid, pos), starter in starter_keys.items():
        if tid == team_id and str(starter.get("player_id")) == player_id:
            return pos
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
        pos_matches = [
            row
            for row in matches
            if str(row.get("position") or "").upper() == position.upper()
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


def _load_injuries(*, season: int, week: int) -> list[dict[str, Any]]:
    try:
        from app.canonical.fact_injury import get_fact_injury

        frame = get_fact_injury(seasons=[int(season)], persist=False)
    except Exception:
        return []
    if frame is None or getattr(frame, "empty", True):
        return []

    rows = frame.to_dict(orient="records")
    week_rows = [
        row
        for row in rows
        if _as_int(row.get("season")) == int(season)
        and _as_int(row.get("week")) == int(week)
    ]
    # Keep latest report_date per player.
    latest: dict[str, dict[str, Any]] = {}
    for row in week_rows:
        pid = str(row.get("player_id") or "").strip()
        if not pid:
            continue
        current = latest.get(pid)
        if current is None:
            latest[pid] = row
            continue
        if str(row.get("report_date") or "") >= str(
            current.get("report_date") or ""
        ):
            latest[pid] = row
    return list(latest.values())


def _nearest_injury_week(*, season: int, week: int) -> int | None:
    try:
        from app.canonical.fact_injury import get_fact_injury

        frame = get_fact_injury(seasons=[int(season)], persist=False)
    except Exception:
        return None
    if frame is None or getattr(frame, "empty", True):
        return None
    weeks = sorted(
        {
            int(value)
            for value in frame["week"].dropna().tolist()
            if _as_int(value) is not None and int(value) <= int(week)
        }
    )
    return weeks[-1] if weeks else None


def _load_depth_starters(
    *,
    season: int,
    week: int,
) -> list[dict[str, Any]]:
    try:
        from app.canonical.fact_depth_chart import get_fact_depth_chart

        frame = get_fact_depth_chart(seasons=[int(season)], persist=False)
    except Exception:
        return []
    if frame is None or getattr(frame, "empty", True):
        return []

    rows = frame.to_dict(orient="records")
    week_rows = [
        row
        for row in rows
        if _as_int(row.get("season")) == int(season)
        and _as_int(row.get("week")) == int(week)
    ]
    if not week_rows:
        # Fall back to latest week ≤ requested.
        prior_weeks = sorted(
            {
                int(row["week"])
                for row in rows
                if _as_int(row.get("season")) == int(season)
                and _as_int(row.get("week")) is not None
                and int(row["week"]) <= int(week)
            }
        )
        if not prior_weeks:
            return []
        target = prior_weeks[-1]
        week_rows = [
            row
            for row in rows
            if _as_int(row.get("season")) == int(season)
            and _as_int(row.get("week")) == target
        ]

    offense: list[dict[str, Any]] = []
    for row in week_rows:
        pos = str(row.get("position") or "").strip().upper()
        if pos in {"FB", "HB"}:
            pos = "RB"
            row = {**row, "position": pos}
        if pos not in {"QB", "RB", "WR", "TE"}:
            continue
        order = _as_int(row.get("depth_order"))
        if order is None or order > 2:
            continue
        offense.append(row)
    return offense


def _load_player_directory(
    player_ids: set[str],
) -> dict[str, dict[str, str]]:
    if not player_ids:
        return {}
    try:
        from app.canonical.dim_player import get_dim_player

        frame = get_dim_player(persist=False)
    except Exception:
        return {}
    if frame is None or getattr(frame, "empty", True):
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in frame.to_dict(orient="records"):
        pid = str(row.get("player_id") or "").strip()
        if pid not in player_ids:
            continue
        name = _clean_text(row.get("name"))
        position = _clean_text(row.get("position"))
        entry: dict[str, str] = {}
        if name:
            entry["name"] = name
        if position:
            upper = position.upper()
            if upper in {"FB", "HB"}:
                upper = "RB"
            entry["position"] = upper
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
