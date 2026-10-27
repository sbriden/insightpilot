"""
College-football resolution keys and ID helpers.

Reuses InsightPilot ip_* minting from app.canonical.ids but
namespaces natural keys so CFB never collides with NFL aliases.
"""

from __future__ import annotations

from typing import Any

from app.canonical.ids import (
    make_game_id,
    make_player_id,
    make_team_id,
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except (TypeError, ValueError, ImportError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {
        "nan",
        "none",
        "nat",
        "<na>",
    }:
        return None
    return text


def cfb_team_resolution_key(
    *,
    espn_team_id: str | None = None,
    team_abbreviation: str | None = None,
    team_name: str | None = None,
) -> str:
    espn_id = _text(espn_team_id)
    if espn_id:
        return f"cfb_espn_team:{espn_id}"

    abbr = _text(team_abbreviation)
    if abbr:
        return f"cfb_abbr:{abbr.upper()}"

    name = _text(team_name)
    if name:
        return f"cfb_team_name:{name.lower()}"

    raise ValueError(
        "Unable to build a CFB team resolution key."
    )


def mint_cfb_team_id(
    *,
    espn_team_id: str | None = None,
    team_abbreviation: str | None = None,
    team_name: str | None = None,
    resolution_key: str | None = None,
) -> str:
    key = resolution_key or cfb_team_resolution_key(
        espn_team_id=espn_team_id,
        team_abbreviation=team_abbreviation,
        team_name=team_name,
    )
    # Pass resolution_key so NFL abbr aliases are not applied.
    return make_team_id(
        None,
        resolution_key=key,
    )


def cfb_player_resolution_key(
    *,
    athlete_id: str | None = None,
    espn_id: str | None = None,
    name: str | None = None,
    birth_date: str | None = None,
) -> str:
    athlete = _text(athlete_id) or _text(espn_id)
    if athlete:
        return f"cfb_athlete:{athlete}"

    name_text = (_text(name) or "").lower()
    dob = _text(birth_date)
    if name_text and dob:
        return f"cfb_name_dob:{name_text}|{dob}"
    if name_text:
        return f"cfb_name:{name_text}"

    raise ValueError(
        "Unable to build a CFB player resolution key."
    )


def mint_cfb_player_id(
    *,
    athlete_id: str | None = None,
    espn_id: str | None = None,
    name: str | None = None,
    birth_date: str | None = None,
    resolution_key: str | None = None,
) -> str:
    key = resolution_key or cfb_player_resolution_key(
        athlete_id=athlete_id,
        espn_id=espn_id,
        name=name,
        birth_date=birth_date,
    )
    return make_player_id(key)


def cfb_game_resolution_key(
    *,
    game_id: str | None = None,
    season: int | None = None,
    week: int | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> str:
    external = _text(game_id)
    if external:
        return f"cfb_game:{external}"

    if (
        season is not None
        and week is not None
        and _text(home_team)
        and _text(away_team)
    ):
        home = _text(home_team).upper()
        away = _text(away_team).upper()
        return (
            f"cfb_game:{int(season)}-{int(week)}-"
            f"{home}-{away}"
        )

    raise ValueError(
        "Unable to build a CFB game resolution key."
    )


def mint_cfb_game_id(
    *,
    game_id: str | None = None,
    season: int | None = None,
    week: int | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
    resolution_key: str | None = None,
) -> str:
    key = resolution_key or cfb_game_resolution_key(
        game_id=game_id,
        season=season,
        week=week,
        home_team=home_team,
        away_team=away_team,
    )
    return make_game_id(key)
