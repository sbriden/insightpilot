"""
Player News tab — structured developments from injury + depth data.

There is no external news feed. Events are synthesized from
canonical fact_injury and fact_depth_chart week-over-week diffs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.analysis.insights.injury_relevance import (
    _as_share,
    canonical_news_position,
    evaluate_injury_relevance,
)
from app.analysis.insights.player_performance import (
    _position_group,
)
from app.analysis.insights.player_snapshot import (
    _depth_chart_label,
    _list_injury_type,
    _num,
    _parse_depth_order,
    build_team_defense_tab_payload,
)


LOOKBACK_OPTIONS = {
    "last_24h": 1,
    "last_3d": 3,
    "last_7d": 7,
    "last_30d": 30,
    "season": None,
}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat", "<na>"}:
        return None
    return text.replace("\n", " ").strip() or None


def _normalize_lookback(value: str | None) -> str:
    key = str(value or "last_30d").strip().lower()
    if key in LOOKBACK_OPTIONS:
        return key
    if key in {"24h", "day", "today"}:
        return "last_24h"
    if key in {"3d", "3days"}:
        return "last_3d"
    if key in {"7d", "week"}:
        return "last_7d"
    if key in {"30d", "month"}:
        return "last_30d"
    if key in {"all", "full", "full_season"}:
        return "season"
    return "last_30d"


def _normalize_category(value: str | None) -> str:
    key = str(value or "all").strip().lower()
    allowed = {
        "all",
        "injury",
        "practice",
        "role",
        "team",
        "depth_chart",
    }
    return key if key in allowed else "all"


def _normalize_impact_filter(value: str | None) -> str:
    key = str(value or "all").strip().lower()
    if key in {"all", "high", "moderate", "low"}:
        return key
    return "all"


def _sort_key(season: Any, week: Any, occurred_at: Any) -> tuple:
    try:
        s = int(season or 0)
    except (TypeError, ValueError):
        s = 0
    try:
        w = int(week or 0)
    except (TypeError, ValueError):
        w = 0
    stamp = ""
    if occurred_at is not None:
        stamp = str(occurred_at)
    return (s, w, stamp)


def _impact_rank(level: str | None) -> int:
    return {
        "high": 3,
        "moderate": 2,
        "low": 1,
    }.get(str(level or "").lower(), 0)


def _availability_label(
    game_status: str | None,
    practice_status: str | None,
    is_expected_to_play: bool | None,
) -> str:
    game = (game_status or "").strip().lower()
    practice = (practice_status or "").strip().lower()
    if "out" in game or "ir" in game or "pup" in game:
        return "Unavailable"
    if "doubt" in game:
        return "Likely Unavailable"
    if "question" in game:
        return "Questionable"
    if "did not participate" in practice:
        return "Questionable"
    if "limited" in practice:
        return "Questionable"
    if is_expected_to_play is False:
        return "Likely Unavailable"
    if is_expected_to_play is True or "full participation" in practice:
        return "Available"
    if game or practice:
        return "Unknown"
    return "Unknown"


def _self_injury_impact(
    *,
    game_status: str | None,
    practice_status: str | None,
    previous_game: str | None,
    previous_practice: str | None,
) -> dict[str, Any]:
    game = (game_status or "").lower()
    practice = (practice_status or "").lower()
    prev_game = (previous_game or "").lower()

    if any(token in game for token in ("out", "ir", "pup", "suspend")):
        return {
            "level": "high",
            "fantasy_impact": "negative",
            "role_impact": "Reduced Opportunity",
            "availability": "Unavailable",
            "confidence": "high",
            "label": "High fantasy impact",
            "summary": (
                "Availability is compromised. Near-term fantasy "
                "usage is at risk until status improves."
            ),
        }
    if "doubt" in game:
        return {
            "level": "high",
            "fantasy_impact": "negative",
            "role_impact": "Role Uncertain",
            "availability": "Likely Unavailable",
            "confidence": "high",
            "label": "High fantasy impact",
            "summary": (
                "Doubtful designation introduces substantial "
                "start/sit uncertainty."
            ),
        }
    if "question" in game or "limited" in practice:
        return {
            "level": "moderate",
            "fantasy_impact": "negative",
            "role_impact": "Role Uncertain",
            "availability": "Questionable",
            "confidence": "moderate",
            "label": "Moderate fantasy impact",
            "summary": (
                "Current status introduces uncertainty around "
                "expected workload."
            ),
        }
    if "did not participate" in practice:
        return {
            "level": "moderate",
            "fantasy_impact": "negative",
            "role_impact": "Role Uncertain",
            "availability": "Questionable",
            "confidence": "moderate",
            "label": "Moderate fantasy impact",
            "summary": (
                "Missed practice participation raises short-term "
                "availability risk."
            ),
        }
    if (
        prev_game
        and any(token in prev_game for token in ("out", "doubt", "question"))
        and (
            "full participation" in practice
            or not game
            or game in {"active", "probable"}
        )
    ):
        return {
            "level": "moderate",
            "fantasy_impact": "positive",
            "role_impact": "Increased Opportunity",
            "availability": "Available",
            "confidence": "moderate",
            "label": "Moderate fantasy impact",
            "summary": (
                "Status appears to be improving relative to the "
                "prior designation."
            ),
        }
    if "full participation" in practice:
        return {
            "level": "low",
            "fantasy_impact": "neutral",
            "role_impact": "Role Unchanged",
            "availability": "Available",
            "confidence": "moderate",
            "label": "Low fantasy impact",
            "summary": (
                "Full practice participation suggests limited "
                "near-term availability risk."
            ),
        }
    return {
        "level": "low",
        "fantasy_impact": "unclear",
        "role_impact": "Role Uncertain",
        "availability": _availability_label(
            game_status,
            practice_status,
            None,
        ),
        "confidence": "low",
        "label": "Low fantasy impact",
        "summary": "Useful context, but near-term fantasy impact is unclear.",
    }


def _listed_out(game_status: str | None) -> bool:
    game = (game_status or "").strip().lower()
    return any(
        token in game
        for token in ("out", "ir", "pup", "doubt", "suspend")
    )


def _remaining_share(
    usage_by_player: dict[str, dict[str, Any]],
    players_by_id: dict[str, dict[str, Any]],
    *,
    exclude_id: str,
    positions: set[str],
    field: str,
) -> float | None:
    total = 0.0
    found = False
    for pid, shares in usage_by_player.items():
        if pid == exclude_id:
            continue
        person = players_by_id.get(pid, {})
        position = canonical_news_position(
            person.get("depth_position")
            or person.get("position")
            or shares.get("position")
        )
        if position not in positions:
            continue
        value = _as_share(shares.get(field))
        if value is None:
            continue
        total += value
        found = True
    return total if found else None


def _depth_change_impact(
    *,
    before_order: int | None,
    after_order: int | None,
) -> dict[str, Any]:
    if before_order is None or after_order is None:
        return {
            "level": "low",
            "fantasy_impact": "unclear",
            "role_impact": "Role Uncertain",
            "availability": "Unknown",
            "confidence": "low",
            "label": "Low fantasy impact",
            "summary": "Depth chart movement noted.",
        }
    if after_order < before_order:
        level = "high" if after_order == 1 or before_order - after_order >= 2 else "moderate"
        return {
            "level": level,
            "fantasy_impact": "positive",
            "role_impact": "Increased Opportunity",
            "availability": "Available",
            "confidence": "moderate",
            "label": (
                "High fantasy impact"
                if level == "high"
                else "Moderate fantasy impact"
            ),
            "summary": (
                "Depth chart movement suggests an expanded role "
                "and potential workload increase."
            ),
        }
    if after_order > before_order:
        level = "high" if before_order == 1 or after_order - before_order >= 2 else "moderate"
        return {
            "level": level,
            "fantasy_impact": "negative",
            "role_impact": "Reduced Opportunity",
            "availability": "Available",
            "confidence": "moderate",
            "label": (
                "High fantasy impact"
                if level == "high"
                else "Moderate fantasy impact"
            ),
            "summary": (
                "Depth chart movement suggests a reduced role "
                "and potential workload decline."
            ),
        }
    return {
        "level": "low",
        "fantasy_impact": "neutral",
        "role_impact": "Role Unchanged",
        "availability": "Available",
        "confidence": "low",
        "label": "Low fantasy impact",
        "summary": "Depth chart label updated without a clear order change.",
    }


def _development(
    *,
    event_id: str,
    event_type: str,
    category: str,
    season: int,
    week: int | None,
    occurred_at: str | None,
    subject: dict[str, Any],
    headline: str,
    body: str | None,
    facts: dict[str, Any],
    impact: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "event_type": event_type,
        "category": category,
        "season": season,
        "week": week,
        "occurred_at": occurred_at,
        "subject": subject,
        "headline": headline,
        "body": body,
        "facts": facts,
        "impact": {
            "level": impact.get("level"),
            "label": impact.get("label"),
            "summary": impact.get("summary"),
            "fantasy_impact": impact.get("fantasy_impact"),
            "role_impact": impact.get("role_impact"),
            "availability": impact.get("availability"),
            "confidence": impact.get("confidence"),
        },
        "source": source,
        "source_label": (
            "NFL / nflverse injury report"
            if source == "fact_injury"
            else "NFL / nflverse depth chart"
            if source == "fact_depth_chart"
            else "InsightPilot"
        ),
    }


def _injury_developments(
    *,
    player_id: str,
    player_name: str | None,
    player_position: str | None,
    player_depth_order: int | None,
    team_id: str | None,
    season: int,
    injuries: pd.DataFrame,
    players_by_id: dict[str, dict[str, Any]],
    usage_by_player: dict[str, dict[str, Any]] | None = None,
    week_opponents: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    if injuries is None or injuries.empty:
        return []

    rows = injuries.to_dict(orient="records")
    by_player: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        pid = str(row.get("player_id") or "").strip()
        if not pid:
            continue
        try:
            row_season = int(row.get("season"))
        except (TypeError, ValueError):
            continue
        if row_season != int(season):
            continue
        by_player.setdefault(pid, []).append(row)

    usage_by_player = usage_by_player or {}
    week_opponents = week_opponents or {}
    absences: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for pid, player_rows in by_player.items():
        identity = players_by_id.get(pid, {})
        position = canonical_news_position(
            identity.get("depth_position") or identity.get("position")
        )
        depth = _parse_depth_order(identity.get("depth_order"))
        if position is None or depth is None or depth > 2:
            continue
        for row in player_rows:
            if not _listed_out(_clean_text(row.get("game_status"))):
                continue
            try:
                week = int(row.get("week"))
            except (TypeError, ValueError):
                continue
            team = str(row.get("team_id") or "").strip()
            bucket = absences.setdefault((team, week), [])
            bucket[:] = [
                item for item in bucket if item["player_id"] != pid
            ]
            bucket.append(
                {
                    "player_id": pid,
                    "position": position,
                    "depth": depth,
                }
            )

    developments: list[dict[str, Any]] = []
    for pid, player_rows in by_player.items():
        player_rows.sort(
            key=lambda item: _sort_key(
                item.get("season"),
                item.get("week"),
                item.get("report_date"),
            )
        )
        previous = None
        for row in player_rows:
            try:
                week = int(row.get("week")) if row.get("week") is not None else None
                row_season = int(row.get("season"))
            except (TypeError, ValueError):
                continue

            injury_type = _list_injury_type(row.get("injury_type"))
            practice = _clean_text(row.get("practice_status"))
            game = _clean_text(row.get("game_status"))
            expected = row.get("is_expected_to_play")
            try:
                if pd.isna(expected):
                    expected = None
            except (TypeError, ValueError):
                pass
            if expected is not None:
                expected = bool(expected)

            prev_practice = (
                _clean_text(previous.get("practice_status"))
                if previous
                else None
            )
            prev_game = (
                _clean_text(previous.get("game_status"))
                if previous
                else None
            )
            prev_injury = (
                _list_injury_type(previous.get("injury_type"))
                if previous
                else None
            )

            changed = (
                previous is None
                or practice != prev_practice
                or game != prev_game
                or injury_type != prev_injury
            )
            if not changed:
                previous = row
                continue

            # Skip empty noise rows.
            if not practice and not game and not injury_type:
                previous = row
                continue

            identity = players_by_id.get(pid, {})
            name = identity.get("name") or (
                player_name if pid == player_id else pid
            )
            position = identity.get("position") or (
                player_position if pid == player_id else None
            )
            is_self = pid == player_id
            relationship = "self" if is_self else "teammate"

            if is_self:
                if game and game != prev_game:
                    event_type = "injury_status"
                    category = "injury"
                    headline = (
                        f"{name} listed as {game}"
                        + (f" ({injury_type})" if injury_type else "")
                    )
                elif practice and practice != prev_practice:
                    event_type = "practice_status"
                    category = "practice"
                    headline = f"{name}: {practice}"
                else:
                    event_type = "injury_designation"
                    category = "injury"
                    headline = (
                        f"{name} injury update"
                        + (f": {injury_type}" if injury_type else "")
                    )
                impact = _self_injury_impact(
                    game_status=game,
                    practice_status=practice,
                    previous_game=prev_game,
                    previous_practice=prev_practice,
                )
                body_parts = []
                if injury_type:
                    body_parts.append(f"Injury: {injury_type}.")
                if practice:
                    body_parts.append(f"Practice: {practice}.")
                if game:
                    body_parts.append(f"Game status: {game}.")
                if prev_game or prev_practice:
                    body_parts.append(
                        "Prior designation: "
                        + ", ".join(
                            part
                            for part in [
                                prev_game,
                                prev_practice,
                            ]
                            if part
                        )
                        + "."
                    )
                body = " ".join(body_parts) or None
            else:
                # Teammate: only surface meaningful availability issues.
                if not game and not (
                    practice
                    and (
                        "limited" in practice.lower()
                        or "did not participate" in practice.lower()
                    )
                ):
                    previous = row
                    continue
                injured_depth = _parse_depth_order(
                    identity.get("depth_order")
                )
                injured_position = (
                    identity.get("depth_position") or position
                )
                injured_team = str(row.get("team_id") or "").strip()
                same_team = injured_team == str(team_id or "").strip()
                if not same_team:
                    expected_opponent = (
                        week_opponents.get(week)
                        if week is not None
                        else None
                    )
                    if (
                        not expected_opponent
                        or injured_team != expected_opponent
                    ):
                        previous = row
                        continue
                    relationship = "opponent"
                cohort = []
                if week is not None:
                    cohort = [
                        item
                        for item in absences.get(
                            (
                                str(row.get("team_id") or "").strip(),
                                week,
                            ),
                            [],
                        )
                        if item["player_id"] != pid
                    ]
                viewer_usage = usage_by_player.get(player_id, {})
                injured_usage = usage_by_player.get(pid, {})
                impact = evaluate_injury_relevance(
                    viewer_position=player_position,
                    viewer_depth=player_depth_order,
                    injured_position=injured_position,
                    injured_depth=injured_depth,
                    game_status=game,
                    same_team=same_team,
                    injured_target_share=injured_usage.get(
                        "target_share"
                    ),
                    viewer_target_share=viewer_usage.get(
                        "target_share"
                    ),
                    remaining_target_share=_remaining_share(
                        usage_by_player,
                        players_by_id,
                        exclude_id=pid,
                        positions={"WR", "TE", "RB"},
                        field="target_share",
                    ) if same_team else None,
                    injured_air_yard_share=injured_usage.get(
                        "air_yard_share"
                    ),
                    injured_rush_share=injured_usage.get("rush_share"),
                    viewer_rush_share=viewer_usage.get("rush_share"),
                    remaining_rush_share=_remaining_share(
                        usage_by_player,
                        players_by_id,
                        exclude_id=pid,
                        positions={"RB"},
                        field="rush_share",
                    ) if same_team else None,
                    other_wr_out=sum(
                        1
                        for item in cohort
                        if item["position"] == "WR"
                    ),
                    other_edge_out=sum(
                        1
                        for item in cohort
                        if item["position"] in {"EDGE", "DL"}
                    ),
                    other_cb_out=sum(
                        1
                        for item in cohort
                        if item["position"] == "CB"
                    ),
                    other_dt_out=sum(
                        1
                        for item in cohort
                        if item["position"] == "DT"
                    ),
                    other_front_out=sum(
                        1
                        for item in cohort
                        if item["position"] in {"EDGE", "DT", "DL"}
                    ),
                )
                if impact is None or impact["level"] == "low":
                    previous = row
                    continue
                event_type = (
                    "teammate_injury"
                    if same_team
                    else "opponent_injury"
                )
                category = "team"
                status_bit = game or practice or "availability update"
                who = (
                    "Teammate"
                    if same_team
                    else "Opposing"
                )
                headline = (
                    f"{who} update: {name}"
                    + (f" ({position})" if position else "")
                    + f" — {status_bit}"
                )
                body = (
                    f"{name}"
                    + (f" ({position})" if position else "")
                    + " has an availability note"
                    + (f" ({injury_type})" if injury_type else "")
                    + "."
                )

            occurred = _clean_text(row.get("report_date"))
            developments.append(
                _development(
                    event_id=(
                        f"injury:{pid}:{row_season}:{week}:{occurred or 'na'}"
                    ),
                    event_type=event_type,
                    category=category,
                    season=row_season,
                    week=week,
                    occurred_at=occurred,
                    subject={
                        "player_id": pid,
                        "name": name,
                        "relationship": relationship,
                        "position": position,
                    },
                    headline=headline,
                    body=body,
                    facts={
                        "injury_type": injury_type,
                        "practice_status": practice,
                        "game_status": game,
                        "is_expected_to_play": expected,
                        "previous_game_status": prev_game,
                        "previous_practice_status": prev_practice,
                    },
                    impact=impact,
                    source="fact_injury",
                )
            )
            previous = row

    return developments


def _depth_developments(
    *,
    player_id: str,
    player_name: str | None,
    player_position: str | None,
    team_id: str | None,
    season: int,
    depth_rows: pd.DataFrame,
) -> list[dict[str, Any]]:
    if depth_rows is None or depth_rows.empty or not team_id:
        return []

    aliases = {
        "RB": {"RB", "HB", "FB"},
        "HB": {"RB", "HB", "FB"},
        "FB": {"RB", "HB", "FB"},
        "K": {"K", "PK"},
        "PK": {"K", "PK"},
    }
    group = _position_group(player_position)
    allowed = aliases.get(group, {group} if group else set())

    rows = []
    for row in depth_rows.to_dict(orient="records"):
        try:
            row_season = int(row.get("season"))
        except (TypeError, ValueError):
            continue
        if row_season != int(season):
            continue
        if str(row.get("team_id") or "").strip() != str(team_id).strip():
            continue
        if str(row.get("player_id") or "").strip() != player_id:
            continue
        position = _clean_text(row.get("position"))
        if position and allowed and position.upper() not in allowed:
            continue
        rows.append(row)

    if not rows:
        return []

    # Keep best row per week (prefer matching position).
    by_week: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            week = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        current = by_week.get(week)
        if current is None:
            by_week[week] = row
            continue
        # Prefer exact position match.
        pos = (_clean_text(row.get("position")) or "").upper()
        cur_pos = (_clean_text(current.get("position")) or "").upper()
        if pos == group and cur_pos != group:
            by_week[week] = row

    weeks = sorted(by_week.keys())
    developments: list[dict[str, Any]] = []
    previous = None
    for week in weeks:
        row = by_week[week]
        after_order = _parse_depth_order(row.get("depth_order"))
        after_pos = (_clean_text(row.get("position")) or group or "").upper()
        after_role = _clean_text(row.get("role"))
        after_label = _depth_chart_label(after_pos, after_order)

        before_order = None
        before_role = None
        before_label = None
        if previous is not None:
            before_order = _parse_depth_order(previous.get("depth_order"))
            before_pos = (
                _clean_text(previous.get("position")) or group or ""
            ).upper()
            before_role = _clean_text(previous.get("role"))
            before_label = _depth_chart_label(before_pos, before_order)

        changed = (
            previous is not None
            and (
                before_order != after_order
                or before_role != after_role
                or before_label != after_label
            )
        )
        if not changed:
            previous = row
            continue

        impact = _depth_change_impact(
            before_order=before_order,
            after_order=after_order,
        )
        name = player_name or player_id
        if before_label and after_label and before_label != after_label:
            headline = f"Depth chart: {name} {before_label} → {after_label}"
        else:
            headline = f"Depth chart update for {name}"
        body = (
            f"{name} moved from {before_label or '—'} to "
            f"{after_label or '—'} on the latest depth chart."
        )
        occurred = _clean_text(row.get("effective_date"))
        developments.append(
            _development(
                event_id=f"depth:{player_id}:{season}:{week}",
                event_type="depth_change",
                category="depth_chart",
                season=int(season),
                week=week,
                occurred_at=occurred,
                subject={
                    "player_id": player_id,
                    "name": name,
                    "relationship": "self",
                    "position": player_position,
                },
                headline=headline,
                body=body,
                facts={
                    "depth_chart_before": before_label,
                    "depth_chart_after": after_label,
                    "role_before": before_role,
                    "role_after": after_role,
                    "depth_order_before": before_order,
                    "depth_order_after": after_order,
                },
                impact=impact,
                source="fact_depth_chart",
            )
        )
        previous = row

    return developments


def _news_current_week(
    season: int,
    scheduled_weeks: list[int],
) -> int | None:
    """
    Week the featured and important panels should describe.

    For the live season this is the nflverse current week.
    For an older season it is the last scheduled week.
    """

    try:
        import nflreadpy as nfl

        if int(season) == int(nfl.get_current_season()):
            week = max(1, int(nfl.get_current_week()))
            if scheduled_weeks and week not in scheduled_weeks:
                if week > max(scheduled_weeks):
                    return max(scheduled_weeks)
            return week
    except Exception:
        pass
    if scheduled_weeks:
        return max(scheduled_weeks)
    return None


def _developments_for_week(
    developments: list[dict[str, Any]],
    week: int | None,
) -> list[dict[str, Any]]:
    if week is None:
        return []
    target = int(week)
    return [
        item
        for item in developments
        if item.get("week") is not None
        and int(item["week"]) == target
    ]


def _important_developments(
    developments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Compact status bullets for the Important Developments panel.
    """

    buckets: dict[str, dict[str, Any]] = {}
    for item in developments:
        category = item.get("category") or "other"
        level = (item.get("impact") or {}).get("level")
        current = buckets.get(category)
        if current is None or _impact_rank(level) > _impact_rank(
            (current.get("impact") or {}).get("level")
        ):
            buckets[category] = item

    order = ["injury", "practice", "depth_chart", "role", "team"]
    results: list[dict[str, Any]] = []
    for key in order:
        item = buckets.get(key)
        if not item:
            continue
        relationship = (
            (item.get("subject") or {}).get("relationship")
        )
        label = {
            "injury": "Injury status",
            "practice": "Practice status",
            "depth_chart": "Depth chart",
            "role": "Role",
            "team": (
                "Opponent"
                if relationship == "opponent"
                else "Teammate"
            ),
        }.get(key, key.title())
        results.append(
            {
                "category": key,
                "label": label,
                "summary": item.get("headline"),
                "impact_level": (item.get("impact") or {}).get("level"),
                "week": item.get("week"),
                "development_id": item.get("id"),
            }
        )
    return results[:5]


def build_player_news(
    player_id: str,
    *,
    season: int | None = None,
    lookback: str | None = "last_30d",
    category: str | None = "all",
    impact: str | None = "all",
) -> dict[str, Any] | None:
    """
    News-tab MVP payload for one player.
    """

    pid = str(player_id or "").strip()
    if not pid:
        return None

    defense_payload = build_team_defense_tab_payload(
        pid,
        season=season,
        tab="news",
    )
    if defense_payload is not None:
        return defense_payload

    lookback_key = _normalize_lookback(lookback)
    category_key = _normalize_category(category)
    impact_key = _normalize_impact_filter(impact)

    try:
        import nflreadpy as nfl
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
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
                      p.status,
                      p.current_team_id,
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
                    FROM {FANTASY_SCHEMA}.fact_injury
                    WHERE season IS NOT NULL
                    ORDER BY season DESC
                    """
                ),
                connection,
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

    team_id = str(identity.get("current_team_id") or "").strip() or None
    player_name = identity.get("name")
    player_position = identity.get("position")
    team_abbr = identity.get("team")

    # Load injuries for the player, teammates, and weekly opponents.
    opponent_team_ids: list[str] = []
    week_opponents: dict[int, str] = {}
    try:
        with engine.connect() as connection:
            if team_id:
                schedule = pd.read_sql_query(
                    text(
                        f"""
                        SELECT week, home_team_id, away_team_id
                        FROM {FANTASY_SCHEMA}.dim_game
                        WHERE season = :season
                          AND (
                            home_team_id = :team_id
                            OR away_team_id = :team_id
                          )
                        """
                    ),
                    connection,
                    params={
                        "season": int(season),
                        "team_id": team_id,
                    },
                )
                seen_opponents: set[str] = set()
                for game in schedule.to_dict(orient="records"):
                    home = str(game.get("home_team_id") or "").strip()
                    away = str(game.get("away_team_id") or "").strip()
                    opponent = away if home == team_id else home
                    if not opponent:
                        continue
                    if opponent not in seen_opponents:
                        seen_opponents.add(opponent)
                        opponent_team_ids.append(opponent)
                    try:
                        week_opponents[int(game.get("week"))] = opponent
                    except (TypeError, ValueError):
                        continue

            injury_team_ids = [
                value
                for value in [team_id, *opponent_team_ids]
                if value
            ]
            if injury_team_ids:
                team_params = {
                    f"team_{index}": value
                    for index, value in enumerate(injury_team_ids)
                }
                team_sql = ", ".join(
                    f":team_{index}"
                    for index in range(len(injury_team_ids))
                )
                injuries = pd.read_sql_query(
                    text(
                        f"""
                        SELECT
                          i.player_id,
                          i.team_id,
                          i.report_date,
                          i.season,
                          i.week,
                          i.injury_type,
                          i.practice_status,
                          i.game_status,
                          i.is_expected_to_play
                        FROM {FANTASY_SCHEMA}.fact_injury i
                        WHERE i.season = :season
                          AND (
                            i.player_id = :player_id
                            OR i.team_id IN ({team_sql})
                          )
                        ORDER BY i.week ASC NULLS LAST,
                          i.report_date ASC NULLS LAST
                        """
                    ),
                    connection,
                    params={
                        "season": int(season),
                        "player_id": pid,
                        **team_params,
                    },
                )
            else:
                injuries = pd.read_sql_query(
                    text(
                        f"""
                        SELECT
                          i.player_id,
                          i.team_id,
                          i.report_date,
                          i.season,
                          i.week,
                          i.injury_type,
                          i.practice_status,
                          i.game_status,
                          i.is_expected_to_play
                        FROM {FANTASY_SCHEMA}.fact_injury i
                        WHERE i.season = :season
                          AND i.player_id = :player_id
                        ORDER BY i.week ASC NULLS LAST,
                          i.report_date ASC NULLS LAST
                        """
                    ),
                    connection,
                    params={
                        "season": int(season),
                        "player_id": pid,
                    },
                )

            depth_team_ids = injury_team_ids or (
                [team_id] if team_id else []
            )
            if depth_team_ids:
                depth_params = {
                    f"depth_team_{index}": value
                    for index, value in enumerate(depth_team_ids)
                }
                depth_sql = ", ".join(
                    f":depth_team_{index}"
                    for index in range(len(depth_team_ids))
                )
                depth = pd.read_sql_query(
                    text(
                        f"""
                        SELECT
                          d.player_id,
                          d.team_id,
                          d.position,
                          d.depth_order,
                          d.role,
                          d.effective_date,
                          d.season,
                          d.week
                        FROM {FANTASY_SCHEMA}.fact_depth_chart d
                        WHERE d.season = :season
                          AND d.team_id IN ({depth_sql})
                        ORDER BY d.week ASC NULLS LAST,
                          d.effective_date ASC NULLS LAST
                        """
                    ),
                    connection,
                    params={
                        "season": int(season),
                        **depth_params,
                    },
                )
            else:
                depth = pd.DataFrame()

            teammate_ids = sorted(
                {
                    str(value).strip()
                    for value in injuries["player_id"].tolist()
                    if value is not None
                }
            ) if not injuries.empty else [pid]
            if pid not in teammate_ids:
                teammate_ids.append(pid)

            players_by_id: dict[str, dict[str, Any]] = {}
            if teammate_ids:
                id_params = {
                    f"id_{index}": value
                    for index, value in enumerate(teammate_ids)
                }
                id_sql = ", ".join(
                    f":id_{index}" for index in range(len(teammate_ids))
                )
                people = pd.read_sql_query(
                    text(
                        f"""
                        SELECT player_id, name, position
                        FROM {FANTASY_SCHEMA}.dim_player
                        WHERE player_id IN ({id_sql})
                        """
                    ),
                    connection,
                    params=id_params,
                )
                for row in people.to_dict(orient="records"):
                    players_by_id[str(row["player_id"])] = row

            # Latest depth order per player, including opponents.
            if not depth.empty:
                latest_by_player: dict[str, tuple[int, dict[str, Any]]] = {}
                for row in depth.to_dict(orient="records"):
                    person_id = str(row.get("player_id") or "").strip()
                    if not person_id:
                        continue
                    try:
                        depth_week = int(row.get("week") or 0)
                    except (TypeError, ValueError):
                        depth_week = 0
                    current = latest_by_player.get(person_id)
                    if current is None or depth_week >= current[0]:
                        latest_by_player[person_id] = (depth_week, row)
                for person_id, (_, row) in latest_by_player.items():
                    person = players_by_id.get(person_id)
                    if person is None:
                        continue
                    person["depth_order"] = _parse_depth_order(
                        row.get("depth_order")
                    )
                    person["depth_position"] = row.get("position")

            usage_by_player = {}
            if team_id:
                try:
                    usage = pd.read_sql_query(
                        text(
                            f"""
                            SELECT
                              u.player_id,
                              p.position,
                              AVG(u.target_share) AS target_share,
                              AVG(u.rush_share) AS rush_share,
                              AVG(u.air_yard_share) AS air_yard_share
                            FROM {FANTASY_SCHEMA}.fact_player_usage u
                            LEFT JOIN {FANTASY_SCHEMA}.dim_player p
                              ON p.player_id = u.player_id
                            WHERE u.season = :season
                              AND u.team_id = :team_id
                              AND (
                                u.season_type IS NULL
                                OR UPPER(u.season_type) IN ('REG', 'REGULAR')
                              )
                            GROUP BY u.player_id, p.position
                            """
                        ),
                        connection,
                        params={
                            "season": int(season),
                            "team_id": team_id,
                        },
                    )
                    for row in usage.to_dict(orient="records"):
                        usage_by_player[str(row["player_id"])] = row
                except Exception:
                    usage_by_player = {}
    except Exception:
        return {
            "player_id": pid,
            "name": player_name,
            "position": player_position,
            "team": team_abbr,
            "season": int(season),
            "lookback": lookback_key,
            "category": category_key,
            "impact_filter": impact_key,
            "available_seasons": available_seasons,
            "current_week": None,
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
            "featured": None,
            "important_developments": [],
            "developments": [],
            "counts": {
                "total": 0,
                "high": 0,
                "moderate": 0,
                "low": 0,
            },
            "empty_message": (
                "No significant recent news. InsightPilot hasn't "
                "identified injury or depth-chart developments for "
                "this player yet."
            ),
            "data_note": (
                "Synthesized from nflverse injury reports and depth "
                "charts — not an external news wire."
            ),
        }

    player_depth_order = None
    me = players_by_id.get(pid)
    if me:
        player_depth_order = _parse_depth_order(me.get("depth_order"))

    developments = []
    developments.extend(
        _injury_developments(
            player_id=pid,
            player_name=player_name,
            player_position=player_position,
            player_depth_order=player_depth_order,
            team_id=team_id,
            season=int(season),
            injuries=injuries,
            players_by_id=players_by_id,
            usage_by_player=usage_by_player,
            week_opponents=week_opponents,
        )
    )
    developments.extend(
        _depth_developments(
            player_id=pid,
            player_name=player_name,
            player_position=player_position,
            team_id=team_id,
            season=int(season),
            depth_rows=depth,
        )
    )

    developments.sort(
        key=lambda item: (
            _sort_key(
                item.get("season"),
                item.get("week"),
                item.get("occurred_at"),
            ),
            _impact_rank((item.get("impact") or {}).get("level")),
        ),
        reverse=True,
    )

    # Lookback by week count approximation for season data.
    lookback_weeks = LOOKBACK_OPTIONS.get(lookback_key)
    if lookback_weeks is not None and developments:
        max_week = max(
            int(item["week"])
            for item in developments
            if item.get("week") is not None
        )
        min_week = max(1, max_week - lookback_weeks + 1)
        developments = [
            item
            for item in developments
            if item.get("week") is None
            or int(item["week"]) >= min_week
        ]

    if category_key != "all":
        developments = [
            item
            for item in developments
            if item.get("category") == category_key
            or (
                category_key == "role"
                and item.get("category") == "depth_chart"
            )
        ]

    if impact_key != "all":
        developments = [
            item
            for item in developments
            if (item.get("impact") or {}).get("level") == impact_key
        ]

    counts = {
        "total": len(developments),
        "high": sum(
            1
            for item in developments
            if (item.get("impact") or {}).get("level") == "high"
        ),
        "moderate": sum(
            1
            for item in developments
            if (item.get("impact") or {}).get("level") == "moderate"
        ),
        "low": sum(
            1
            for item in developments
            if (item.get("impact") or {}).get("level") == "low"
        ),
    }

    current_week = _news_current_week(
        int(season),
        sorted(week_opponents),
    )
    this_week = _developments_for_week(
        developments,
        current_week,
    )

    featured = None
    if this_week:
        featured = max(
            this_week,
            key=lambda item: (
                _impact_rank((item.get("impact") or {}).get("level")),
                _sort_key(
                    item.get("season"),
                    item.get("week"),
                    item.get("occurred_at"),
                ),
            ),
        )

    empty_message = None
    if not developments:
        empty_message = (
            "No significant recent news. InsightPilot hasn't "
            "identified any recent injury or depth-chart "
            "developments likely to materially affect this "
            "player's fantasy outlook."
        )

    return {
        "player_id": pid,
        "name": player_name,
        "position": player_position,
        "team": team_abbr,
        "season": int(season),
        "lookback": lookback_key,
        "category": category_key,
        "impact_filter": impact_key,
        "available_seasons": available_seasons,
        "current_week": current_week,
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
        "featured": featured,
        "important_developments": _important_developments(
            this_week
        ),
        "developments": developments,
        "counts": counts,
        "empty_message": empty_message,
        "data_note": (
            "Synthesized from nflverse injury reports and depth "
            "charts — not an external news wire. "
            "Injury items are limited to absences that can change "
            "this player's opportunity or efficiency."
        ),
    }
