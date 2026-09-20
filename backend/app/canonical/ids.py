"""
InsightPilot-owned canonical identifiers.

External provider IDs are never used as primary keys.
They are stored only as source_ids for resolution/joins.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


PLAYER_ID_PREFIX = "ip_player_"
TEAM_ID_PREFIX = "ip_team_"
GAME_ID_PREFIX = "ip_game_"
SIGNAL_ID_PREFIX = "ip_signal_"

# Historical / alternate abbreviations → current franchise abbr.
# Kept here so make_team_id / resolution keys stay stable.
TEAM_ABBREVIATION_ALIASES = {
    "LAR": "LA",
    "OAK": "LV",
    "SD": "LAC",
    "SDG": "LAC",
    "STL": "LA",
    "WSH": "WAS",
    "JAC": "JAX",
    "ARZ": "ARI",
    "GNB": "GB",
    "KAN": "KC",
    "NOR": "NO",
    "NWE": "NE",
    "SFO": "SF",
    "TAM": "TB",
    "RAM": "LA",
    "RAI": "LV",
    "PHX": "ARI",
}


def canonicalize_team_abbreviation(
    value: Any,
) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    return TEAM_ABBREVIATION_ALIASES.get(text, text)

_PLAYER_ID_PATTERN = re.compile(
    rf"^{re.escape(PLAYER_ID_PREFIX)}\d{{8}}$"
)
_TEAM_ID_PATTERN = re.compile(
    rf"^{re.escape(TEAM_ID_PREFIX)}\d{{6}}$"
)
_GAME_ID_PATTERN = re.compile(
    rf"^{re.escape(GAME_ID_PREFIX)}\d{{8}}$"
)
_SIGNAL_ID_PATTERN = re.compile(
    rf"^{re.escape(SIGNAL_ID_PREFIX)}"
    rf"(?:\d{{8}}|[0-9a-f]{{16}})$"
)


def is_player_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(_PLAYER_ID_PATTERN.match(text))


def is_team_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(_TEAM_ID_PATTERN.match(text))


def is_game_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(_GAME_ID_PATTERN.match(text))


def is_signal_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(_SIGNAL_ID_PATTERN.match(text))


def _stable_digest(
    namespace: str,
    key: str,
) -> bytes:
    material = f"insightpilot:{namespace}:{key}".encode(
        "utf-8"
    )
    return hashlib.sha256(material).digest()


def make_player_id(
    resolution_key: str,
) -> str:
    """
    Build a deterministic InsightPilot player_id.

    Format: ip_player_00000000 (8 zero-padded digits)
    """

    key = str(resolution_key or "").strip()
    if not key:
        raise ValueError(
            "resolution_key is required to mint player_id."
        )

    digest = _stable_digest("dim_player", key)
    number = int.from_bytes(digest[:5], "big") % (10 ** 8)
    return f"{PLAYER_ID_PREFIX}{number:08d}"


def team_resolution_key(
    *,
    team_abbreviation: str | None = None,
    nflverse_team_id: str | None = None,
) -> str:
    abbr = canonicalize_team_abbreviation(team_abbreviation)
    if abbr:
        return f"abbr:{abbr}"

    nfl_id = str(nflverse_team_id or "").strip()
    if nfl_id:
        return f"nflverse_team:{nfl_id}"

    raise ValueError(
        "Unable to build a team resolution key."
    )


def make_team_id(
    team_abbreviation: str | None = None,
    *,
    resolution_key: str | None = None,
) -> str:
    """
    Build a deterministic InsightPilot team_id.

    Format: ip_team_000000 (6 zero-padded digits).
    Minted from the canonical team abbreviation so historical
    aliases (OAK→LV, SD→LAC, …) share one franchise id.
    """

    abbr = canonicalize_team_abbreviation(team_abbreviation)
    if abbr:
        key = abbr
    elif resolution_key:
        key = str(resolution_key).strip()
    else:
        raise ValueError(
            "team_abbreviation is required to mint team_id."
        )

    return _mint_team_id_from_key(key)


def legacy_alias_team_id(team_abbreviation: str) -> str:
    """
    Team id minted from an alias BEFORE canonicalization.

    Used only to remap historical rows (e.g. OAK → LV).
    """

    abbr = str(team_abbreviation or "").strip().upper()
    if not abbr:
        raise ValueError(
            "team_abbreviation is required for legacy alias id."
        )
    return _mint_team_id_from_key(abbr)


def _mint_team_id_from_key(key: str) -> str:
    digest = _stable_digest("dim_team", key)
    number = int.from_bytes(digest[:4], "big") % (10 ** 6)
    return f"{TEAM_ID_PREFIX}{number:06d}"


def player_resolution_key(
    *,
    gsis_id: str | None = None,
    pfr_id: str | None = None,
    sleeper_id: str | None = None,
    espn_id: str | None = None,
    fantasypros_id: str | None = None,
    name: str | None = None,
    birth_date: str | None = None,
) -> str:
    """
    Choose the strongest available natural key for minting
    a stable InsightPilot player_id.
    """

    for prefix, value in (
        ("gsis", gsis_id),
        ("pfr", pfr_id),
        ("sleeper", sleeper_id),
        ("espn", espn_id),
        ("fantasypros", fantasypros_id),
    ):
        text = str(value or "").strip()
        if text:
            return f"{prefix}:{text}"

    name_text = str(name or "").strip().lower()
    dob_text = str(birth_date or "").strip()
    if name_text and dob_text:
        return f"name_dob:{name_text}|{dob_text}"

    if name_text:
        return f"name:{name_text}"

    raise ValueError(
        "Unable to build a player resolution key from "
        "available source identifiers."
    )


def game_resolution_key(
    *,
    nflverse_game_id: str | None = None,
    season: int | None = None,
    week: int | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> str:
    nfl_id = str(nflverse_game_id or "").strip()
    if nfl_id:
        return f"nflverse_game:{nfl_id}"

    home = str(home_team or "").strip().upper()
    away = str(away_team or "").strip().upper()
    if season is not None and week is not None and home and away:
        return f"matchup:{int(season)}-{int(week)}-{away}@{home}"

    raise ValueError(
        "Unable to build a game resolution key."
    )


def make_game_id(
    resolution_key: str,
) -> str:
    """
    Build a deterministic InsightPilot game_id.

    Format: ip_game_00000000 (8 zero-padded digits)
    """

    key = str(resolution_key or "").strip()
    if not key:
        raise ValueError(
            "resolution_key is required to mint game_id."
        )

    digest = _stable_digest("dim_game", key)
    number = int.from_bytes(digest[:5], "big") % (10 ** 8)
    return f"{GAME_ID_PREFIX}{number:08d}"


def signal_resolution_key(
    *,
    player_id: str,
    season: int,
    week: int,
    signal_type: str,
) -> str:
    return (
        f"{player_id}:{int(season)}:{int(week)}:"
        f"{str(signal_type).strip().upper()}"
    )


def make_signal_id(
    resolution_key: str,
) -> str:
    """
    Build a deterministic InsightPilot signal_id.

    Format: ip_signal_ + 16 lowercase hex chars (64-bit digest).
    Wider than the old 8-digit numeric form so player×week×type
    volumes do not collide on the primary key.
    """

    key = str(resolution_key or "").strip()
    if not key:
        raise ValueError(
            "resolution_key is required to mint signal_id."
        )

    digest = _stable_digest("fantasy_signal", key)
    return f"{SIGNAL_ID_PREFIX}{digest[:8].hex()}"

