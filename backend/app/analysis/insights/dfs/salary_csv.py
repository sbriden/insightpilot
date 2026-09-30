"""Parse DFS site salary CSVs and match to canonical players."""

from __future__ import annotations

import csv
import io
import re
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from app.analysis.insights.dfs.sites import (
    normalize_contest_type,
)
from app.canonical.dim_player import get_dim_player
from app.canonical.dim_team import (
    get_dim_team,
    normalize_team_abbreviation,
)
from app.canonical.fact_dfs_salary import (
    salary_resolution_key,
    upsert_fact_dfs_salary,
)
from app.canonical.ids import make_player_id


_NAME_SUFFIX_RE = re.compile(
    r"\b(jr\.?|sr\.?|ii|iii|iv|v)\b\.?",
    re.IGNORECASE,
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_WS_RE = re.compile(r"\s+")

_MIN_NAME_SCORE = 0.78
_STRONG_NAME_SCORE = 0.92

_NAME_ALIASES = (
    ("name", "nickname", "player", "player name", "full name"),
    ("first name", "firstname", "first"),
    ("last name", "lastname", "last"),
)
_SALARY_ALIASES = ("salary", "sal", "price", "cost")
_TEAM_ALIASES = (
    "teamabbrev",
    "team abbrev",
    "team",
    "team abbreviation",
    "abbrev",
)
_POS_ALIASES = (
    "roster position",
    "position",
    "pos",
    "roster_position",
)

# Common DFS / colloquial team tokens not present as dim_team abbr.
_EXTRA_TEAM_ALIASES = {
    "niners": "SF",
    "49ers": "SF",
    "frisco": "SF",
    "washington": "WAS",
    "commanders": "WAS",
    "football team": "WAS",
    "bolts": "LAC",
    "chargers": "LAC",
    "raiders": "LV",
    "rams": "LA",
}

_TEAM_ALIAS_CACHE: dict[str, str] | None = None


def ingest_dfs_salary_csv(
    content: bytes | str,
    *,
    site: str,
    contest_type: str = "classic",
    season: int,
    week: int,
    filename: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    site_key = str(site or "draftkings").strip().lower()
    if site_key not in {"draftkings", "fanduel"}:
        raise ValueError(
            f"Unsupported DFS site: {site}. "
            "Use draftkings or fanduel."
        )
    format_key = normalize_contest_type(contest_type)
    rows = parse_salary_csv(content)
    if not rows:
        raise ValueError("No player rows found in CSV.")

    candidates = _load_match_candidates()
    matched_rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    seen_players: set[str] = set()

    for row in rows:
        result = match_salary_row(row, candidates)
        if result is None:
            unmatched.append(
                {
                    "name": row.get("name"),
                    "team": row.get("team"),
                    "position": row.get("position"),
                    "salary": row.get("salary"),
                    "reason": "no_match",
                }
            )
            continue
        player_id = result["player_id"]
        if player_id in seen_players:
            unmatched.append(
                {
                    "name": row.get("name"),
                    "team": row.get("team"),
                    "position": row.get("position"),
                    "salary": row.get("salary"),
                    "reason": "duplicate_match",
                    "matched_name": result.get("matched_name"),
                }
            )
            continue
        seen_players.add(player_id)
        matched_rows.append(
            {
                "player_id": player_id,
                "site": site_key,
                "contest_type": format_key,
                "season": int(season),
                "week": int(week),
                "team": result.get("team") or row.get("team"),
                "position": result.get("position")
                or row.get("position"),
                "player_name": result.get("matched_name")
                or row.get("name"),
                "salary": int(row["salary"]),
                "match_score": result.get("score"),
                "source_name": filename,
                "source_ids": {
                    "csv_name": row.get("name"),
                    "csv_team": row.get("team"),
                    "csv_position": row.get("position"),
                },
                "resolution_key": salary_resolution_key(
                    site=site_key,
                    contest_type=format_key,
                    season=int(season),
                    week=int(week),
                    player_id=player_id,
                ),
            }
        )

    persisted = 0
    if persist and matched_rows:
        frame = pd.DataFrame(matched_rows)
        persisted = upsert_fact_dfs_salary(frame)

    return {
        "site": site_key,
        "contest_type": format_key,
        "season": int(season),
        "week": int(week),
        "filename": filename,
        "rows_parsed": len(rows),
        "matched": len(matched_rows),
        "unmatched": len(unmatched),
        "persisted": persisted,
        "unmatched_samples": unmatched[:25],
        "matched_samples": [
            {
                "player_id": item["player_id"],
                "name": item["player_name"],
                "team": item["team"],
                "position": item["position"],
                "salary": item["salary"],
                "match_score": item["match_score"],
            }
            for item in matched_rows[:10]
        ],
    }


def parse_salary_csv(content: bytes | str) -> list[dict[str, Any]]:
    text = (
        content.decode("utf-8-sig", errors="replace")
        if isinstance(content, (bytes, bytearray))
        else str(content)
    )
    # Skip DraftKings preamble rows until a header with Salary.
    lines = text.splitlines()
    header_index = 0
    for index, line in enumerate(lines[:30]):
        lower = line.lower()
        if "salary" in lower and (
            "name" in lower
            or "nickname" in lower
            or "position" in lower
        ):
            header_index = index
            break
    usable = "\n".join(lines[header_index:])
    reader = csv.DictReader(io.StringIO(usable))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")

    field_map = _map_fields(reader.fieldnames)
    if "salary" not in field_map:
        raise ValueError(
            "CSV is missing a Salary column."
        )
    if "name" not in field_map and not (
        "first_name" in field_map and "last_name" in field_map
    ):
        raise ValueError(
            "CSV is missing a player Name column."
        )

    rows: list[dict[str, Any]] = []
    for raw in reader:
        name = _row_name(raw, field_map)
        salary = _parse_salary(
            raw.get(field_map["salary"])
        )
        if not name or salary is None:
            continue
        team = None
        if "team" in field_map:
            team = _resolve_team_abbreviation(
                raw.get(field_map["team"])
            )
        position = None
        if "position" in field_map:
            position = _normalize_position(
                raw.get(field_map["position"])
            )
        rows.append(
            {
                "name": name,
                "team": team,
                "position": position,
                "salary": salary,
            }
        )
    return rows


def match_salary_row(
    row: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    name = str(row.get("name") or "").strip()
    team = _resolve_team_abbreviation(row.get("team"))
    position = _normalize_position(row.get("position"))
    if not name:
        return None

    pool = candidates
    if team:
        pool = [
            item
            for item in pool
            if item.get("team") == team
        ]
    if position:
        pool = [
            item
            for item in pool
            if item.get("position") == position
            or (
                position == "DEF"
                and item.get("position") in {"DEF", "DST"}
            )
        ]
    if not pool and team:
        # Fall back to team-only if position labels diverge.
        pool = [
            item
            for item in candidates
            if item.get("team") == team
        ]
    if not pool:
        # Defense rows often put the nickname in Name ("Packers")
        # with a non-abbreviation Team value we already failed to
        # resolve — try resolving the name itself as a team token.
        if position == "DEF":
            name_team = _resolve_team_abbreviation(name)
            if name_team:
                pool = [
                    item
                    for item in candidates
                    if item.get("team") == name_team
                    and item.get("position") in {"DEF", "DST"}
                ]
    if not pool:
        return None

    needle = _normalize_name(name)
    best: dict[str, Any] | None = None
    best_score = 0.0
    for item in pool:
        score = _name_similarity(needle, item["name_key"])
        if score > best_score:
            best_score = score
            best = item
    if best is None or best_score < _MIN_NAME_SCORE:
        # Exact team-defense match: name resolves to the same
        # franchise as the candidate (e.g. "Packers" → GB).
        if position == "DEF" and team:
            defense = next(
                (
                    item
                    for item in pool
                    if item.get("position") in {"DEF", "DST"}
                    and item.get("team") == team
                    and item.get("is_primary_defense")
                ),
                None,
            )
            if defense is None:
                defense = next(
                    (
                        item
                        for item in pool
                        if item.get("position") in {"DEF", "DST"}
                        and item.get("team") == team
                    ),
                    None,
                )
            name_as_team = _resolve_team_abbreviation(name)
            if defense is not None and (
                name_as_team == team
                or _defense_nickname_match(needle, defense)
            ):
                return {
                    "player_id": defense["player_id"],
                    "matched_name": defense["name"],
                    "team": defense.get("team"),
                    "position": defense.get("position"),
                    "score": 0.95,
                }
        return None
    # Require a stronger match when team/pos filters were loose.
    if position is None and best_score < _STRONG_NAME_SCORE:
        return None
    return {
        "player_id": best["player_id"],
        "matched_name": best["name"],
        "team": best.get("team"),
        "position": best.get("position"),
        "score": round(best_score, 4),
    }

def _load_match_candidates() -> list[dict[str, Any]]:
    players = get_dim_player()
    teams = get_dim_team()
    team_lookup: dict[str, str] = {}
    if not teams.empty:
        for record in teams.to_dict(orient="records"):
            team_id = str(record.get("team_id") or "").strip()
            abbr = normalize_team_abbreviation(
                record.get("team_abbreviation")
            )
            if team_id and abbr:
                team_lookup[team_id] = abbr

    # Warm nickname / full-name → abbr map used while matching.
    _team_alias_lookup(teams)

    candidates: list[dict[str, Any]] = []
    if not players.empty:
        for record in players.to_dict(orient="records"):
            player_id = str(
                record.get("player_id") or ""
            ).strip()
            name = str(record.get("name") or "").strip()
            if not player_id or not name:
                continue
            position = _normalize_position(
                record.get("position")
            )
            team = team_lookup.get(
                str(record.get("current_team_id") or "").strip()
            )
            candidates.append(
                {
                    "player_id": player_id,
                    "name": name,
                    "name_key": _normalize_name(name),
                    "team": team,
                    "position": position,
                }
            )

    # Synthetic team defenses used by DFS / overview.
    for abbr, team_name, nickname in _team_defense_names(teams):
        player_id = make_player_id(f"fantasy_dst:{abbr}")
        primary_name = f"{team_name} D/ST"
        candidates.append(
            {
                "player_id": player_id,
                "name": primary_name,
                "name_key": _normalize_name(primary_name),
                "team": abbr,
                "position": "DEF",
                "is_primary_defense": True,
                "nickname_key": _normalize_name(nickname)
                if nickname
                else None,
            }
        )
        aliases = {
            f"{abbr} DST",
            f"{abbr} D/ST",
            f"{team_name} DST",
            f"{abbr}",
            team_name,
        }
        if nickname:
            aliases.update(
                {
                    nickname,
                    f"{nickname} DST",
                    f"{nickname} D/ST",
                    f"{nickname} DEF",
                }
            )
        for alias in aliases:
            if not alias or alias == primary_name:
                continue
            candidates.append(
                {
                    "player_id": player_id,
                    "name": alias,
                    "name_key": _normalize_name(alias),
                    "team": abbr,
                    "position": "DEF",
                    "is_primary_defense": False,
                    "nickname_key": _normalize_name(nickname)
                    if nickname
                    else None,
                }
            )
    return candidates


def _team_defense_names(
    teams: pd.DataFrame,
) -> list[tuple[str, str, str | None]]:
    if teams.empty:
        return []
    out: list[tuple[str, str, str | None]] = []
    for record in teams.to_dict(orient="records"):
        abbr = normalize_team_abbreviation(
            record.get("team_abbreviation")
        )
        if not abbr:
            continue
        name = (
            str(record.get("team_name") or "").strip()
            or abbr
        )
        nickname = _team_nickname(name)
        out.append((abbr, name, nickname))
    return out


def _team_nickname(team_name: str) -> str | None:
    parts = _normalize_name(team_name).split()
    if not parts:
        return None
    # Prefer the franchise nickname (last token): Packers, Bills.
    nick = parts[-1]
    if nick in {"dst", "def"}:
        return None
    return nick


def _team_alias_lookup(
    teams: pd.DataFrame | None = None,
) -> dict[str, str]:
    """
    Map abbreviations, full names, and nicknames → team abbr.

    Examples: gb→GB, packers→GB, green bay packers→GB.
    Ambiguous tokens (e.g. \"new york\") are omitted.
    """

    global _TEAM_ALIAS_CACHE
    if _TEAM_ALIAS_CACHE is not None and teams is None:
        return _TEAM_ALIAS_CACHE

    frame = teams
    if frame is None:
        frame = get_dim_team()

    counts: dict[str, set[str]] = {}
    mapping: dict[str, str] = {}

    def _register(token: str | None, abbr: str) -> None:
        key = _normalize_name(token or "")
        if not key:
            return
        counts.setdefault(key, set()).add(abbr)

    if frame is not None and not frame.empty:
        for record in frame.to_dict(orient="records"):
            abbr = normalize_team_abbreviation(
                record.get("team_abbreviation")
            )
            if not abbr:
                continue
            abbr = abbr.upper()
            _register(abbr, abbr)
            _register(abbr.lower(), abbr)
            name = str(record.get("team_name") or "").strip()
            if name:
                _register(name, abbr)
                nick = _team_nickname(name)
                if nick:
                    _register(nick, abbr)
                # City / region prefix without nickname when unique.
                parts = _normalize_name(name).split()
                if len(parts) >= 2:
                    _register(" ".join(parts[:-1]), abbr)

    for token, abbr in _EXTRA_TEAM_ALIASES.items():
        _register(token, abbr.upper())

    for key, abbrs in counts.items():
        if len(abbrs) == 1:
            mapping[key] = next(iter(abbrs))

    _TEAM_ALIAS_CACHE = mapping
    return mapping


def _resolve_team_abbreviation(value: Any) -> str | None:
    """
    Resolve CSV team tokens to a canonical abbreviation.

    Accepts GB, Packers, Green Bay Packers, Packers DST, etc.
    """

    raw = str(value or "").strip()
    if not raw:
        return None

    lookup = _team_alias_lookup()
    key = _normalize_name(raw)
    if key in lookup:
        return lookup[key]

    # Retry without DST/DEF suffixes: "Packers DST".
    stripped = re.sub(
        r"\b(dst|d/?st|def|defense)\b",
        "",
        key,
    )
    stripped = _WS_RE.sub(" ", stripped).strip()
    if stripped and stripped in lookup:
        return lookup[stripped]

    # Abbreviation / historical alias path (GB, GNB, LAR, …).
    compact = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if 2 <= len(compact) <= 3:
        direct = normalize_team_abbreviation(compact)
        if direct and (
            direct.lower() in lookup
            or direct in set(lookup.values())
        ):
            return direct
    return None


def _defense_nickname_match(
    needle: str,
    defense: dict[str, Any],
) -> bool:
    nick = defense.get("nickname_key")
    if not nick:
        return False
    if needle == nick:
        return True
    if needle.startswith(f"{nick} ") or needle.endswith(
        f" {nick}"
    ):
        return True
    return nick in needle.split()


def _map_fields(fieldnames: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not fieldnames:
        return mapping
    normalized = {
        _header_key(name): name for name in fieldnames if name
    }
    for alias in _SALARY_ALIASES:
        if alias in normalized:
            mapping["salary"] = normalized[alias]
            break
    for alias in _TEAM_ALIASES:
        if alias in normalized:
            mapping["team"] = normalized[alias]
            break
    for alias in _POS_ALIASES:
        if alias in normalized:
            mapping["position"] = normalized[alias]
            break
    for alias in _NAME_ALIASES[0]:
        if alias in normalized:
            mapping["name"] = normalized[alias]
            break
    for alias in _NAME_ALIASES[1]:
        if alias in normalized:
            mapping["first_name"] = normalized[alias]
            break
    for alias in _NAME_ALIASES[2]:
        if alias in normalized:
            mapping["last_name"] = normalized[alias]
            break
    return mapping


def _header_key(value: str) -> str:
    return _WS_RE.sub(" ", str(value or "").strip().lower())


def _row_name(
    raw: dict[str, Any],
    field_map: dict[str, str],
) -> str | None:
    if "name" in field_map:
        value = str(raw.get(field_map["name"]) or "").strip()
        return value or None
    first = str(
        raw.get(field_map.get("first_name", ""), "") or ""
    ).strip()
    last = str(
        raw.get(field_map.get("last_name", ""), "") or ""
    ).strip()
    combined = f"{first} {last}".strip()
    return combined or None


def _parse_salary(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("$", "").replace(",", "")
    try:
        amount = float(text)
    except ValueError:
        return None
    if amount <= 0:
        return None
    return int(round(amount))


def _normalize_position(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    # DK roster position can be "RB/FLEX" or "CPT".
    text = text.split("/")[0].strip()
    if text in {"PK"}:
        return "K"
    if text in {"DST", "D/ST", "D-ST", "DEFENSE", "TEAM DEF", "D"}:
        return "DEF"
    if text in {"CPT", "FLEX", "UTIL"}:
        return None
    if text in {"FB", "HB"}:
        return "RB"
    return text


def _normalize_name(value: str) -> str:
    text = str(value or "").lower().strip()
    text = text.replace("d/st", "dst").replace("d-st", "dst")
    text = _NAME_SUFFIX_RE.sub("", text)
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _name_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    # Prefer last-token overlap for "Josh Allen" vs "J. Allen".
    left_parts = left.split()
    right_parts = right.split()
    score = SequenceMatcher(None, left, right).ratio()
    if left_parts and right_parts:
        if left_parts[-1] == right_parts[-1]:
            score = max(score, 0.85)
            if len(left_parts) > 1 and len(right_parts) > 1:
                if left_parts[0][0] == right_parts[0][0]:
                    score = max(score, 0.9)
    # Containment for defense aliases.
    if left in right or right in left:
        score = max(score, 0.88)
    return score
