"""
Showdown portfolio game-script archetypes.

Maps InsightPilot betting game-script probabilities onto DraftKings
Showdown lineup construction so portfolio lineup mix tracks the
normalized script distribution.
"""

from __future__ import annotations

from typing import Any

from app.analysis.insights.betting.game_scripts import (
    normalize_script_weights,
    project_game_scripts,
)


SCRIPT_ARCHETYPES: dict[str, dict[str, str]] = {
    "favorite_controls": {
        "code": "A",
        "label": "Favorite controls game",
        "implication": (
            "Favorite QB/RB, favorite DST, fewer opposing pieces"
        ),
    },
    "shootout": {
        "code": "B",
        "label": "Shootout",
        "implication": "Both QBs + multiple pass catchers",
    },
    "underdog_comeback": {
        "code": "C",
        "label": "Underdog comeback",
        "implication": (
            "Underdog QB/pass catchers, favorite pass volume"
        ),
    },
    "low_scoring": {
        "code": "D",
        "label": "Low-scoring game",
        "implication": (
            "RBs, DST, kickers, limited pass-game exposure"
        ),
    },
    "favorite_passing_win": {
        "code": "E",
        "label": "Favorite wins through passing",
        "implication": "Favorite QB + 2 pass catchers",
    },
    "contrarian_upset": {
        "code": "F",
        "label": "Contrarian upset",
        "implication": (
            "Underdog QB + pass catcher + correlated pieces"
        ),
    },
}


def load_showdown_script_context(
    slate: dict[str, Any],
    *,
    lineup_count: int,
) -> dict[str, Any] | None:
    """
    Resolve favorite/underdog + normalized script allocations
    for a Showdown slate. Returns None when scripts cannot be built.
    """

    games = list(slate.get("games") or [])
    if not games:
        return None
    game = games[0]
    home = str(
        game.get("home_team")
        or slate.get("home_team")
        or ""
    ).upper()
    away = str(
        game.get("away_team")
        or slate.get("away_team")
        or ""
    ).upper()
    if not home or not away:
        return None

    season = slate.get("season")
    week = slate.get("week")
    event_id = str(game.get("game_id") or "").strip()
    scripts: list[dict[str, Any]] = []
    favorite = home
    underdog = away
    market_spread = None
    projected_home = None
    projected_away = None
    projected_total = None
    market_total = None

    detail = None
    if event_id:
        try:
            from app.analysis.insights.betting.slate import (
                get_betting_event,
            )

            detail = get_betting_event(
                event_id,
                season=int(season) if season is not None else None,
            )
        except Exception:
            detail = None

    # DFS schedules use nflverse game_ids (e.g. 2026_03_ATL_GB);
    # betting markets use InsightPilot ids (ip_game_*). Fall back
    # to home/away matchup on the betting slate.
    if not detail:
        try:
            from app.analysis.insights.betting.slate import (
                find_betting_event_by_matchup,
            )

            detail = find_betting_event_by_matchup(
                home_team=home,
                away_team=away,
                season=int(season) if season is not None else None,
                week=int(week) if week is not None else None,
            )
        except Exception:
            detail = None

    if detail and isinstance(detail, dict):
        event = detail.get("event") or detail
        scripts = list(event.get("game_scripts") or [])
        market_spread = event.get("market_spread")
        market_total = event.get("market_total")
        projected_home = event.get("projected_home_score")
        projected_away = event.get("projected_away_score")
        projected_total = event.get("projected_total")
        if scripts:
            favorite = str(
                scripts[0].get("favorite") or favorite
            ).upper()
            underdog = str(
                scripts[0].get("underdog") or underdog
            ).upper()
        # Prefer market favorite when scripts are missing.
        if market_spread is not None and not scripts:
            if float(market_spread) <= 0:
                favorite, underdog = home, away
            else:
                favorite, underdog = away, home

    if not scripts:
        # Fallback: team PPG from the player pool if betting
        # enrichment is unavailable.
        projected_home, projected_away = _fallback_scores_from_pool(
            slate.get("players") or [],
            home=home,
            away=away,
        )
        if projected_home is None or projected_away is None:
            return None
        scripts = project_game_scripts(
            projected_home=projected_home,
            projected_away=projected_away,
            projected_total=(
                float(projected_home) + float(projected_away)
            ),
            market_total=market_total,
            market_spread=market_spread,
            home_team=home,
            away_team=away,
        )
        if scripts:
            favorite = str(
                scripts[0].get("favorite") or favorite
            ).upper()
            underdog = str(
                scripts[0].get("underdog") or underdog
            ).upper()

    if not scripts:
        return None

    allocations = normalize_script_weights(
        scripts,
        lineup_count=lineup_count,
    )
    if not allocations:
        return None

    for row in allocations:
        meta = SCRIPT_ARCHETYPES.get(row["script_id"]) or {}
        row["code"] = meta.get("code")
        row["implication"] = meta.get("implication")
        if not row.get("label"):
            row["label"] = meta.get("label") or row["script_id"]

    return {
        "home_team": home,
        "away_team": away,
        "favorite": favorite,
        "underdog": underdog,
        "market_spread": market_spread,
        "market_total": market_total,
        "projected_home_score": projected_home,
        "projected_away_score": projected_away,
        "projected_total": projected_total,
        "scripts_raw": scripts,
        "allocations": allocations,
    }


def build_script_hints(
    script_id: str,
    *,
    favorite: str,
    underdog: str,
    players: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Translate a script archetype into captain pool, soft locks,
    excludes, and per-player score boosts for Showdown builds.
    """

    fav = favorite.upper()
    dog = underdog.upper()
    fav_players = _team_players(players, fav)
    dog_players = _team_players(players, dog)

    boosts: dict[str, float] = {}
    captain_pool: list[str] = []
    soft_lock: list[str] = []
    soft_exclude: list[str] = []

    if script_id == "favorite_controls":
        captain_pool = _ids(
            _pos(fav_players, {"RB", "QB", "DST", "DEF"})
        )
        soft_lock = _ids(_pos(fav_players, {"RB", "DST", "DEF"}))[:2]
        soft_exclude = _ids(_pos(dog_players, {"QB", "WR", "TE"}))[:4]
        _boost(boosts, fav_players, {"RB", "DST", "DEF", "QB"}, 8.0)
        _boost(boosts, dog_players, {"WR", "TE", "QB"}, -6.0)

    elif script_id == "shootout":
        captain_pool = _ids(
            _pos(fav_players + dog_players, {"QB", "WR", "TE"})
        )
        soft_lock = _ids(_pos(fav_players + dog_players, {"QB"}))[:2]
        soft_exclude = _ids(
            _pos(fav_players + dog_players, {"DST", "DEF", "K"})
        )
        _boost(boosts, fav_players + dog_players, {"QB", "WR", "TE"}, 9.0)
        _boost(boosts, fav_players + dog_players, {"DST", "DEF", "K"}, -8.0)

    elif script_id == "underdog_comeback":
        captain_pool = _ids(_pos(dog_players, {"QB", "WR", "TE"}))
        soft_lock = (
            _ids(_pos(dog_players, {"QB", "WR"}))[:2]
            + _ids(_pos(fav_players, {"WR", "TE"}))[:1]
        )
        soft_exclude = _ids(_pos(fav_players, {"DST", "DEF", "RB"}))[:3]
        _boost(boosts, dog_players, {"QB", "WR", "TE"}, 10.0)
        _boost(boosts, fav_players, {"WR", "TE"}, 5.0)
        _boost(boosts, fav_players, {"RB", "DST", "DEF"}, -5.0)

    elif script_id == "low_scoring":
        # Prefer ground/defense without locking out the pass game —
        # Showdown still needs six rosterable pieces, and hard WR/TE
        # excludes made this archetype chronically under-fill seats.
        captain_pool = _ids(
            _pos(fav_players + dog_players, {"RB", "DST", "DEF", "K"})
        )
        soft_lock = _ids(
            _pos(fav_players + dog_players, {"RB", "DST", "DEF"})
        )[:2]
        soft_exclude = _ids(
            _pos(fav_players + dog_players, {"WR", "TE"})
        )[4:]
        _boost(boosts, fav_players + dog_players, {"RB", "DST", "DEF", "K"}, 11.0)
        _boost(boosts, fav_players + dog_players, {"QB"}, -2.0)
        _boost(boosts, fav_players + dog_players, {"WR", "TE"}, -4.0)

    elif script_id == "favorite_passing_win":
        captain_pool = _ids(_pos(fav_players, {"QB", "WR", "TE"}))
        soft_lock = _ids(_pos(fav_players, {"QB", "WR", "TE"}))[:3]
        soft_exclude = _ids(_pos(dog_players, {"RB", "DST", "DEF"}))[:3]
        _boost(boosts, fav_players, {"QB", "WR", "TE"}, 10.0)
        _boost(boosts, dog_players, {"WR"}, 3.0)
        _boost(boosts, fav_players, {"RB", "DST", "DEF"}, -3.0)

    elif script_id == "contrarian_upset":
        captain_pool = _ids(
            _pos(dog_players, {"QB", "WR", "RB", "TE"})
        )
        soft_lock = _ids(_pos(dog_players, {"QB", "WR", "TE", "RB"}))[:3]
        soft_exclude = _ids(_pos(fav_players, {"QB", "RB", "DST", "DEF"}))[:4]
        _boost(boosts, dog_players, {"QB", "WR", "TE", "RB"}, 11.0)
        _boost(boosts, fav_players, {"WR"}, 2.0)
        _boost(boosts, fav_players, {"QB", "RB", "DST", "DEF"}, -7.0)

    else:
        captain_pool = _ids(players)[:12]

    return {
        "script_id": script_id,
        "captain_pool": captain_pool,
        "soft_lock": soft_lock,
        "soft_exclude": soft_exclude,
        "score_boosts": boosts,
        "meta": SCRIPT_ARCHETYPES.get(script_id) or {
            "code": "?",
            "label": script_id,
            "implication": "",
        },
    }


def _fallback_scores_from_pool(
    players: list[dict[str, Any]],
    *,
    home: str,
    away: str,
) -> tuple[float | None, float | None]:
    home_proj = [
        float(player.get("projection") or 0.0)
        for player in players
        if str(player.get("team") or "").upper() == home
        and str(player.get("position") or "").upper()
        in {"QB", "RB", "WR", "TE"}
    ]
    away_proj = [
        float(player.get("projection") or 0.0)
        for player in players
        if str(player.get("team") or "").upper() == away
        and str(player.get("position") or "").upper()
        in {"QB", "RB", "WR", "TE"}
    ]
    if not home_proj or not away_proj:
        return None, None
    # Rough team scoring proxy from skill projections.
    return (
        round(sum(sorted(home_proj, reverse=True)[:4]) * 0.55, 1),
        round(sum(sorted(away_proj, reverse=True)[:4]) * 0.55, 1),
    )


def _team_players(
    players: list[dict[str, Any]],
    team: str,
) -> list[dict[str, Any]]:
    team_u = team.upper()
    return [
        player
        for player in players
        if str(player.get("team") or "").upper() == team_u
    ]


def _pos(
    players: list[dict[str, Any]],
    positions: set[str],
) -> list[dict[str, Any]]:
    out = [
        player
        for player in players
        if str(player.get("position") or "").upper() in positions
    ]
    out.sort(
        key=lambda item: (
            -float(item.get("projection") or 0.0),
            -float(item.get("_base_opt_score") or 0.0),
        )
    )
    return out


def _ids(players: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for player in players:
        pid = str(player.get("player_id") or "").strip()
        if pid and pid not in ids:
            ids.append(pid)
    return ids


def _boost(
    boosts: dict[str, float],
    players: list[dict[str, Any]],
    positions: set[str],
    amount: float,
) -> None:
    for player in _pos(players, positions):
        pid = str(player.get("player_id") or "")
        if not pid:
            continue
        boosts[pid] = boosts.get(pid, 0.0) + float(amount)
