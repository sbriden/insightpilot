"""DFS site roster rules and salary caps."""

from __future__ import annotations

from typing import Any


# Classic NFL (main / multi-game) roster construction.
_CLASSIC_ROSTER = [
    {"slot": "QB", "positions": ["QB"]},
    {"slot": "RB", "positions": ["RB"]},
    {"slot": "RB", "positions": ["RB"]},
    {"slot": "WR", "positions": ["WR"]},
    {"slot": "WR", "positions": ["WR"]},
    {"slot": "WR", "positions": ["WR"]},
    {"slot": "TE", "positions": ["TE"]},
    {
        "slot": "FLEX",
        "positions": ["RB", "WR", "TE"],
    },
    {"slot": "DST", "positions": ["DEF", "DST"]},
]

# Showdown / single-game: Captain + 5 FLEX (any position).
_SHOWDOWN_POSITIONS = [
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

_SHOWDOWN_ROSTER = [
    {
        "slot": "CPT",
        "positions": list(_SHOWDOWN_POSITIONS),
        "is_captain": True,
    },
    {
        "slot": "FLEX",
        "positions": list(_SHOWDOWN_POSITIONS),
    },
    {
        "slot": "FLEX",
        "positions": list(_SHOWDOWN_POSITIONS),
    },
    {
        "slot": "FLEX",
        "positions": list(_SHOWDOWN_POSITIONS),
    },
    {
        "slot": "FLEX",
        "positions": list(_SHOWDOWN_POSITIONS),
    },
    {
        "slot": "FLEX",
        "positions": list(_SHOWDOWN_POSITIONS),
    },
]

# DraftKings-style showdown captain: 1.5× salary and 1.5× fantasy points.
CAPTAIN_MULTIPLIER = 1.5

CONTEST_TYPES = ("classic", "showdown")

DFS_SITES: dict[str, dict[str, Any]] = {
    "draftkings": {
        "id": "draftkings",
        "name": "DraftKings",
        "salary_cap": 50000,
        "formats": {
            "classic": {
                "roster": list(_CLASSIC_ROSTER),
                "captain_multiplier": 1.0,
            },
            "showdown": {
                "roster": list(_SHOWDOWN_ROSTER),
                "captain_multiplier": CAPTAIN_MULTIPLIER,
            },
        },
    },
    "fanduel": {
        "id": "fanduel",
        "name": "FanDuel",
        "salary_cap": 60000,
        "formats": {
            "classic": {
                "roster": list(_CLASSIC_ROSTER),
                "captain_multiplier": 1.0,
            },
            "showdown": {
                "roster": list(_SHOWDOWN_ROSTER),
                "captain_multiplier": CAPTAIN_MULTIPLIER,
            },
        },
    },
}


def list_sites() -> list[dict[str, Any]]:
    return [
        {
            "id": site["id"],
            "name": site["name"],
            "salary_cap": site["salary_cap"],
            "contest_types": list(CONTEST_TYPES),
            "roster_size": len(
                site["formats"]["classic"]["roster"]
            ),
            "slots": [
                slot["slot"]
                for slot in site["formats"]["classic"]["roster"]
            ],
            "showdown_roster_size": len(
                site["formats"]["showdown"]["roster"]
            ),
            "captain_multiplier": CAPTAIN_MULTIPLIER,
        }
        for site in DFS_SITES.values()
    ]


def normalize_contest_type(contest_type: str | None) -> str:
    key = str(contest_type or "classic").strip().lower()
    # Legacy strategy labels were previously sent as contest_type.
    if key in {"cash", "gpp", "custom", "balanced"}:
        return "classic"
    if key in {"showdown", "single", "single_game", "cpt"}:
        return "showdown"
    if key == "classic":
        return "classic"
    return "classic"


def get_site_config(
    site: str,
    *,
    contest_type: str | None = "classic",
) -> dict[str, Any]:
    key = str(site or "draftkings").strip().lower()
    if key not in DFS_SITES:
        raise ValueError(
            f"Unsupported DFS site: {site}. "
            f"Supported: {', '.join(sorted(DFS_SITES))}."
        )
    base = DFS_SITES[key]
    format_key = normalize_contest_type(contest_type)
    fmt = base["formats"][format_key]
    return {
        "id": base["id"],
        "name": base["name"],
        "salary_cap": base["salary_cap"],
        "contest_type": format_key,
        "roster": [dict(slot) for slot in fmt["roster"]],
        "captain_multiplier": float(
            fmt.get("captain_multiplier") or 1.0
        ),
    }
