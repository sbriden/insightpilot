"""Build synthetic DFS slates from canonical fantasy data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.analysis.insights.dfs.sites import (
    get_site_config,
    normalize_contest_type,
)


# Slate window kinds (DraftKings-style NFL classic).
SLATE_KINDS: dict[str, dict[str, str]] = {
    "main": {
        "label": "Main Slate",
        "start_label": "Sunday early / afternoon",
    },
    "thu": {
        "label": "Thursday Night",
        "start_label": "Thursday Night Football",
    },
    "snf": {
        "label": "Sunday Night",
        "start_label": "Sunday Night Football",
    },
    "mnf": {
        "label": "Monday Night",
        "start_label": "Monday Night Football",
    },
    "sd": {
        "label": "Showdown",
        "start_label": "Single-game showdown",
    },
}

# Sunday games at/after this local kickoff hour are SNF.
_SUNDAY_NIGHT_HOUR = 20


def list_dfs_slates(
    *,
    season: int | None = None,
    week: int | None = None,
    contest_type: str | None = "classic",
) -> list[dict[str, Any]]:
    resolved_season = _resolve_season(season)
    resolved_week = _resolve_week(week, season=resolved_season)
    format_key = normalize_contest_type(contest_type)
    windows = _slate_windows_for_week(
        season=resolved_season,
        week=resolved_week,
    )

    if format_key == "showdown":
        return _list_showdown_slates(
            season=resolved_season,
            week=resolved_week,
            windows=windows,
        )

    slates: list[dict[str, Any]] = []
    # Prefer main first, then primetime windows.
    for kind in ("main", "thu", "snf", "mnf"):
        meta = SLATE_KINDS[kind]
        window = windows.get(kind) or {}
        teams = window.get("teams") or set()
        games = window.get("games") or []
        # Always expose the four windows; empty ones still
        # appear so the UI can show a consistent selector.
        slates.append(
            {
                "slate_id": _slate_id(
                    resolved_season,
                    resolved_week,
                    kind,
                ),
                "sport": "NFL",
                "label": (
                    f"{meta['label']} — "
                    f"Week {resolved_week}"
                ),
                "season": resolved_season,
                "week": resolved_week,
                "kind": kind,
                "contest_type": "classic",
                "start_label": meta["start_label"],
                "game_count": len(games),
                "player_count_estimate": None,
                "teams": sorted(teams),
            }
        )
    return slates


def build_dfs_slate(
    slate_id: str,
    *,
    site: str = "draftkings",
    season: int | None = None,
    contest_type: str | None = None,
    limit: int = 250,
) -> dict[str, Any]:
    resolved_season = _resolve_season(season)
    parsed = _parse_slate_id(slate_id, resolved_season)
    format_key = normalize_contest_type(
        contest_type or parsed.get("contest_type")
    )
    # Game showdown IDs always imply showdown format.
    if parsed.get("kind") == "sd":
        format_key = "showdown"
    site_config = get_site_config(
        site,
        contest_type=format_key,
    )
    season_value = int(parsed["season"])
    week_value = parsed.get("week")
    if week_value is None:
        week_value = _resolve_week(None, season=season_value)
    kind = str(parsed.get("kind") or "main")

    windows = _slate_windows_for_week(
        season=season_value,
        week=int(week_value),
    )
    team_filter, opponents, games, label, start_label = (
        _resolve_slate_window(
            parsed=parsed,
            kind=kind,
            week=int(week_value),
            windows=windows,
            contest_type=format_key,
        )
    )

    from app.analysis.insights.player_snapshot import (
        list_fantasy_players,
    )

    # Prefer uploaded DK/FD salaries when available for this week.
    salary_map: dict[str, int] = {}
    salary_updated_at: str | None = None
    try:
        from app.canonical.fact_dfs_salary import (
            latest_salary_upload_timestamp,
            load_dfs_salary_map,
        )

        salary_map = load_dfs_salary_map(
            site=site_config["id"],
            contest_type=format_key,
            season=season_value,
            week=int(week_value),
        )
        if salary_map:
            salary_updated_at = latest_salary_upload_timestamp(
                site=site_config["id"],
                contest_type=format_key,
                season=season_value,
                week=int(week_value),
            )
    except Exception:
        salary_map = {}

    # Pull a wide pool, then restrict to slate teams when known.
    fetch_limit = max(50, min(int(limit), 500))
    if team_filter:
        fetch_limit = max(fetch_limit, 1500)

    raw_players = list_fantasy_players(
        season=season_value,
        limit=fetch_limit,
    )
    players = [
        _to_dfs_player(
            player,
            site=site_config["id"],
            opponents=opponents,
            contest_type=format_key,
            salary_map=salary_map,
        )
        for player in raw_players
        if _eligible_position(
            player.get("position"),
            contest_type=format_key,
        )
    ]
    players = [player for player in players if player is not None]

    if team_filter:
        players = [
            player
            for player in players
            if str(player.get("team") or "").strip().upper()
            in team_filter
        ]
    elif kind not in {"main"}:
        # Primetime / showdown windows with no games stay empty
        # instead of falling back to the full season pool.
        players = []

    players.sort(
        key=lambda item: (
            -(float(item.get("projection") or 0.0)),
            str(item.get("name") or ""),
        )
    )
    if limit and len(players) > int(limit):
        players = players[: int(limit)]

    # Always assign DFS projected ownership (never season-long
    # player-overview ownership — those scales are unrelated).
    _assign_dfs_ownership(
        players,
        contest_type=format_key,
    )
    _apply_ownership_signals(players)

    salary_hits = sum(
        1
        for player in players
        if player.get("salary_source") == "uploaded"
    )
    now = datetime.now(timezone.utc).isoformat()
    salaries_updated_at = salary_updated_at or now
    if salary_hits > 0:
        note = (
            f"Using {salary_hits} uploaded "
            f"{site_config['name']} {format_key} salaries "
            f"for week {int(week_value)}"
            + (
                " (showdown)."
                if format_key == "showdown"
                else f" ({start_label.lower()})."
            )
        )
    else:
        note = (
            "Synthetic salaries from InsightPilot projections "
            "(upload a DK/FD salary CSV for real prices)"
            + (
                " for a single-game showdown."
                if format_key == "showdown"
                else f", filtered to {start_label.lower()}."
            )
        )

    return {
        "slate_id": parsed["slate_id"],
        "sport": "NFL",
        "label": label,
        "season": season_value,
        "week": int(week_value),
        "kind": kind,
        "contest_type": format_key,
        "start_label": start_label,
        "site": site_config["id"],
        "site_name": site_config["name"],
        "salary_cap": site_config["salary_cap"],
        "roster": site_config["roster"],
        "captain_multiplier": site_config.get(
            "captain_multiplier", 1.0
        ),
        "games": games,
        "teams": sorted(team_filter),
        "players": players,
        "player_count": len(players),
        "salary_coverage": {
            "uploaded": salary_hits,
            "total": len(players),
            "source": (
                "uploaded" if salary_hits > 0 else "synthetic"
            ),
        },
        "freshness": {
            "projections_updated_at": now,
            "ownership_updated_at": now,
            "salaries_updated_at": salaries_updated_at,
            "note": note,
        },
    }


def _resolve_season(season: int | None) -> int:
    if season is not None:
        return int(season)
    try:
        import nflreadpy as nfl

        return int(nfl.get_current_season())
    except Exception:
        return datetime.now(timezone.utc).year


def _resolve_week(
    week: int | None,
    *,
    season: int,
) -> int:
    if week is not None:
        return max(1, int(week))
    try:
        import nflreadpy as nfl

        current_season = int(nfl.get_current_season())
        if int(season) == current_season:
            return max(1, int(nfl.get_current_week()))
    except Exception:
        pass
    return 1


def _slate_id(season: int, week: int, kind: str) -> str:
    return f"nfl-{int(season)}-{int(week)}-{kind}"


def _showdown_slate_id(
    season: int,
    week: int,
    *,
    away: str,
    home: str,
) -> str:
    return (
        f"nfl-{int(season)}-{int(week)}-sd-"
        f"{away.upper()}-{home.upper()}"
    )


def _list_showdown_slates(
    *,
    season: int,
    week: int,
    windows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    seen: set[str] = set()
    for kind in ("thu", "main", "snf", "mnf"):
        for game in (windows.get(kind) or {}).get("games") or []:
            game_id = str(game.get("game_id") or "")
            key = game_id or (
                f"{game.get('away_team')}-{game.get('home_team')}"
            )
            if key in seen:
                continue
            seen.add(key)
            games.append(game)

    slates: list[dict[str, Any]] = []
    for game in games:
        away = str(game.get("away_team") or "").upper()
        home = str(game.get("home_team") or "").upper()
        if not away or not home:
            continue
        weekday = str(game.get("weekday") or "").strip()
        gametime = str(game.get("gametime") or "").strip()
        when = " · ".join(
            part for part in (weekday, gametime) if part
        )
        slates.append(
            {
                "slate_id": _showdown_slate_id(
                    season,
                    week,
                    away=away,
                    home=home,
                ),
                "sport": "NFL",
                "label": f"Showdown — {away} @ {home}",
                "season": season,
                "week": week,
                "kind": "sd",
                "contest_type": "showdown",
                "start_label": when or "Single-game showdown",
                "game_count": 1,
                "player_count_estimate": None,
                "teams": sorted({away, home}),
                "games": [game],
            }
        )
    return slates


def _resolve_slate_window(
    *,
    parsed: dict[str, Any],
    kind: str,
    week: int,
    windows: dict[str, dict[str, Any]],
    contest_type: str,
) -> tuple[
    set[str],
    dict[str, str],
    list[dict[str, Any]],
    str,
    str,
]:
    if kind == "sd" or (
        contest_type == "showdown"
        and parsed.get("away_team")
        and parsed.get("home_team")
    ):
        away = str(parsed.get("away_team") or "").upper()
        home = str(parsed.get("home_team") or "").upper()
        game = _find_game(
            windows,
            away=away,
            home=home,
        )
        teams = {away, home} if away and home else set()
        opponents = {}
        if away and home:
            opponents[away] = home
            opponents[home] = away
        games = [game] if game else []
        label = f"Showdown — {away} @ {home}"
        start = "Single-game showdown"
        if game:
            weekday = str(game.get("weekday") or "").strip()
            gametime = str(game.get("gametime") or "").strip()
            start = " · ".join(
                part for part in (weekday, gametime) if part
            ) or start
        return teams, opponents, games, label, start

    window = windows.get(kind) or {
        "teams": set(),
        "games": [],
        "opponents": {},
    }
    teams = set(window.get("teams") or set())
    opponents = dict(window.get("opponents") or {})
    games = list(window.get("games") or [])

    if contest_type == "showdown":
        if len(games) != 1:
            raise ValueError(
                "Showdown contests require a single-game slate. "
                "Pick a Showdown game from the slate list."
            )
        game = games[0]
        away = str(game.get("away_team") or "").upper()
        home = str(game.get("home_team") or "").upper()
        label = f"Showdown — {away} @ {home}"
        start = SLATE_KINDS.get(kind, {}).get(
            "start_label", "Single-game showdown"
        )
        return teams, opponents, games, label, start

    kind_meta = SLATE_KINDS.get(kind, SLATE_KINDS["main"])
    label = f"{kind_meta['label']} — Week {week}"
    return (
        teams,
        opponents,
        games,
        label,
        kind_meta["start_label"],
    )


def _find_game(
    windows: dict[str, dict[str, Any]],
    *,
    away: str,
    home: str,
) -> dict[str, Any] | None:
    away_u = away.upper()
    home_u = home.upper()
    for kind in ("thu", "main", "snf", "mnf"):
        for game in (windows.get(kind) or {}).get("games") or []:
            if (
                str(game.get("away_team") or "").upper() == away_u
                and str(game.get("home_team") or "").upper()
                == home_u
            ):
                return game
    return None


def _parse_slate_id(
    slate_id: str,
    fallback_season: int,
) -> dict[str, Any]:
    """
    Accept:
      nfl-{season}-main
      nfl-{season}-{kind}
      nfl-{season}-{week}-{kind}
      nfl-{season}-{week}-sd-{away}-{home}
      nfl-current-main (legacy)
    """

    text = str(slate_id or "").strip() or (
        f"nfl-{fallback_season}-main"
    )
    parts = [part for part in text.split("-") if part]
    season = fallback_season
    week: int | None = None
    kind = "main"
    away_team: str | None = None
    home_team: str | None = None
    contest_type: str | None = None

    # Drop leading sport token.
    if parts and parts[0].lower() == "nfl":
        parts = parts[1:]

    if parts:
        if parts[0].isdigit():
            season = int(parts[0])
            parts = parts[1:]
        elif parts[0].lower() == "current":
            parts = parts[1:]

    if parts and parts[0].isdigit():
        week = int(parts[0])
        parts = parts[1:]

    if parts:
        candidate = parts[0].lower()
        aliases = {
            "main": "main",
            "thu": "thu",
            "thursday": "thu",
            "tnf": "thu",
            "snf": "snf",
            "sunday": "snf",
            "sundaynight": "snf",
            "mnf": "mnf",
            "monday": "mnf",
            "mondaynight": "mnf",
            "sd": "sd",
            "showdown": "sd",
        }
        # Handle sunday-night / monday-night split tokens.
        joined = "-".join(parts).lower().replace("_", "")
        if joined in {"sunday-night", "sundaynight"}:
            kind = "snf"
        elif joined in {"monday-night", "mondaynight"}:
            kind = "mnf"
        elif joined in {"thursday-night", "thursdaynight"}:
            kind = "thu"
        elif candidate in {"sd", "showdown"} and len(parts) >= 3:
            kind = "sd"
            contest_type = "showdown"
            away_team = parts[1].upper()
            home_team = parts[2].upper()
        else:
            kind = aliases.get(candidate, "main")

    label = f"{SLATE_KINDS.get(kind, SLATE_KINDS['main'])['label']} — {season}"
    if kind == "sd" and away_team and home_team:
        label = f"Showdown — {away_team} @ {home_team}"
    elif week is not None:
        label = (
            f"{SLATE_KINDS.get(kind, SLATE_KINDS['main'])['label']}"
            f" — Week {week}"
        )

    return {
        "slate_id": text,
        "season": season,
        "week": week,
        "kind": kind,
        "label": label,
        "away_team": away_team,
        "home_team": home_team,
        "contest_type": contest_type,
    }


def _slate_windows_for_week(
    *,
    season: int,
    week: int,
) -> dict[str, dict[str, Any]]:
    """
    Classify REG games in a week into main / thu / snf / mnf.

    Returns per-kind: teams, games, opponents (abbr → opp abbr).
    """

    empty = {
        kind: {"teams": set(), "games": [], "opponents": {}}
        for kind in SLATE_KINDS
    }
    try:
        import nflreadpy as nfl

        schedules = nfl.load_schedules([int(season)])
        if hasattr(schedules, "to_pandas"):
            schedules = schedules.to_pandas()
    except Exception:
        return empty

    if schedules is None or getattr(schedules, "empty", True):
        return empty

    windows = empty
    for row in schedules.to_dict(orient="records"):
        if not _is_reg_game(row):
            continue
        try:
            game_week = int(row.get("week"))
        except (TypeError, ValueError):
            continue
        if game_week != int(week):
            continue

        kind = _classify_game(row)
        if kind is None:
            continue

        home = _team_abbr(row.get("home_team"))
        away = _team_abbr(row.get("away_team"))
        if not home or not away:
            continue

        game = {
            "game_id": str(row.get("game_id") or ""),
            "gameday": str(row.get("gameday") or ""),
            "gametime": str(row.get("gametime") or ""),
            "weekday": str(row.get("weekday") or ""),
            "home_team": home,
            "away_team": away,
            "kind": kind,
        }
        bucket = windows[kind]
        bucket["games"].append(game)
        bucket["teams"].add(home)
        bucket["teams"].add(away)
        bucket["opponents"][home] = away
        bucket["opponents"][away] = home

    return windows


def _is_reg_game(row: dict[str, Any]) -> bool:
    game_type = str(row.get("game_type") or "").strip().upper()
    if game_type and game_type not in {"REG", "REGULAR"}:
        return False
    return True


def _classify_game(row: dict[str, Any]) -> str | None:
    weekday = str(row.get("weekday") or "").strip().lower()
    hour = _gametime_hour(row.get("gametime"))

    if weekday.startswith("thu"):
        return "thu"
    if weekday.startswith("mon"):
        return "mnf"
    if weekday.startswith("sun"):
        if hour is not None and hour >= _SUNDAY_NIGHT_HOUR:
            return "snf"
        return "main"
    # Saturday / international midweek → treat as main when present.
    if weekday.startswith("sat") or weekday.startswith("fri"):
        return "main"
    return "main"


def _gametime_hour(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text or ":" not in text:
        return None
    try:
        return int(text.split(":", 1)[0])
    except ValueError:
        return None


def _team_abbr(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _eligible_position(
    position: Any,
    *,
    contest_type: str = "classic",
) -> bool:
    pos = str(position or "").strip().upper()
    allowed = {
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "PK",
        "DEF",
        "DST",
        "FB",
        "HB",
    }
    if contest_type != "showdown":
        # Classic skill slate still lists K in eligibility
        # checks; kickers are dropped later in _to_dfs_player.
        pass
    return pos in allowed


def _normalize_position(position: Any) -> str:
    pos = str(position or "").strip().upper()
    if pos in {"PK"}:
        return "K"
    if pos in {"FB", "HB"}:
        return "RB"
    if pos in {"DST", "D/ST"}:
        return "DEF"
    return pos or "WR"


def _to_dfs_player(
    player: dict[str, Any],
    *,
    site: str,
    opponents: dict[str, str] | None = None,
    contest_type: str = "classic",
    salary_map: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    player_id = str(player.get("player_id") or "").strip()
    if not player_id:
        return None
    position = _normalize_position(player.get("position"))
    # Classic NFL DFS skill slate excludes kickers on DK/FD main.
    # Showdown allows any player from the game, including K.
    if position == "K" and contest_type != "showdown":
        return None

    projection = _num(player.get("fppg"))
    if projection is None:
        projection = _num(player.get("fantasy_points"))
    if projection is None:
        # Keep zero-projection players out of the primary pool.
        games = player.get("games")
        if not games:
            return None
        projection = 0.0

    uploaded_salary = None
    if salary_map:
        uploaded_salary = salary_map.get(player_id)
    if uploaded_salary is not None:
        salary = int(uploaded_salary)
        salary_source = "uploaded"
    else:
        salary = _synthetic_salary(
            position=position,
            projection=float(projection),
            site=site,
            contest_type=contest_type,
        )
        salary_source = "synthetic"
    # Season-long ownership from player overview is intentionally
    # ignored — DFS projected ownership is assigned at the slate level.

    value = None
    if salary and salary > 0 and projection is not None:
        value = round(float(projection) / (salary / 1000.0), 2)

    floor = round(float(projection) * 0.65, 1)
    ceiling = round(float(projection) * 1.45, 1)
    matchup = _matchup_from_assessment(
        player.get("overall_assessment")
    )
    signals = _signals_for_player(player, value=value)

    team = str(player.get("team") or "").strip().upper() or None
    opponent = None
    if team and opponents:
        opponent = opponents.get(team)

    eligible = _eligible_slots(position, contest_type=contest_type)

    return {
        "dfs_player_id": f"{site}:{player_id}",
        "player_id": player_id,
        "name": str(player.get("name") or player_id),
        "position": position,
        "eligible_positions": eligible,
        "team": team,
        "opponent": opponent,
        "salary": salary,
        "salary_source": salary_source,
        "projection": round(float(projection), 1),
        "floor": floor,
        "ceiling": ceiling,
        "projected_ownership": None,
        "ownership_label": None,
        "value": value,
        "matchup_rating": matchup,
        "matchup_label": matchup,
        "opportunity_rating": _num(
            player.get("opportunity_score")
        ),
        "efficiency_rating": None,
        "risk_level": _risk_from_assessment(
            player.get("overall_assessment")
        ),
        "volatility": "moderate",
        "status": player.get("status") or "Active",
        "injury_status": player.get("injury_status"),
        "injury_type": player.get("injury_type"),
        "signals": signals,
        "primary_signal": signals[0] if signals else None,
        "overall_assessment": player.get(
            "overall_assessment"
        ),
        "is_team_defense": bool(
            player.get("is_team_defense")
            or position == "DEF"
        ),
    }


def _eligible_slots(
    position: str,
    *,
    contest_type: str = "classic",
) -> list[str]:
    if contest_type == "showdown":
        return ["CPT", "FLEX"]
    if position == "DEF":
        return ["DST", "DEF"]
    if position == "K":
        return ["K"]
    if position in {"RB", "WR", "TE"}:
        return [position, "FLEX"]
    return [position]


def _synthetic_salary(
    *,
    position: str,
    projection: float,
    site: str,
    contest_type: str = "classic",
) -> int:
    """
    Map projection → salary so strong players cost more and
    total lineups can still fit under the site cap.

    Classic salaries run lower than showdown — showdown pools
    are smaller and captain pricing needs more salary room.
    """

    floors = {
        "QB": 4500,
        "RB": 4000,
        "WR": 3500,
        "TE": 3000,
        "DEF": 2400,
        "K": 3500,
    }
    ceilings = {
        "QB": 9000,
        "RB": 9500,
        "WR": 9200,
        "TE": 7500,
        "DEF": 4200,
        "K": 5500,
    }
    # Rough FPPG bands by position.
    proj_floors = {
        "QB": 8.0,
        "RB": 4.0,
        "WR": 4.0,
        "TE": 3.0,
        "DEF": 3.0,
        "K": 4.0,
    }
    proj_ceils = {
        "QB": 28.0,
        "RB": 26.0,
        "WR": 24.0,
        "TE": 18.0,
        "DEF": 14.0,
        "K": 14.0,
    }
    low = floors.get(position, 3500)
    high = ceilings.get(position, 8000)
    p_low = proj_floors.get(position, 4.0)
    p_high = proj_ceils.get(position, 22.0)
    if p_high <= p_low:
        ratio = 0.5
    else:
        ratio = (projection - p_low) / (p_high - p_low)
    ratio = max(0.0, min(1.0, ratio))
    salary = low + (high - low) * ratio
    # Classic vs showdown pricing (classic cheaper overall).
    if contest_type == "showdown":
        salary *= 1.22
    else:
        salary *= 0.90
    # FanDuel salaries tend slightly higher for the same roles.
    if site == "fanduel":
        salary *= 1.12
    # Round to nearest $100.
    return int(round(salary / 100.0) * 100)


def _assign_dfs_ownership(
    players: list[dict[str, Any]],
    *,
    contest_type: str,
) -> None:
    """
    Synthetic DFS projected ownership from slate projection rank.

    Classic main-slate chalk is typically mid-teens to low-20s,
    not season-long roster rates near 100%. Showdown chalk runs
    higher because the pool is a single game.
    """

    ranked = [
        player
        for player in players
        if player.get("projection") is not None
    ]
    count = max(len(ranked), 1)
    showdown = contest_type == "showdown"
    for index, player in enumerate(ranked):
        # Position within slate (0 = highest projected).
        rank_ratio = index / max(count - 1, 1)
        if showdown:
            # ~48% chalk → ~6% punches on a 2-team pool.
            share = 0.48 - rank_ratio * 0.42
            share = max(0.05, min(0.55, share))
        else:
            # ~22% chalk → ~1.5% punches across a full slate.
            share = 0.22 - rank_ratio * 0.205
            share = max(0.015, min(0.28, share))
        # Slight bump for elite value (more likely to be chalk).
        value = float(player.get("value") or 0.0)
        if value >= 3.2:
            share = min(0.55 if showdown else 0.30, share + 0.02)
        player["projected_ownership"] = round(share, 3)
        player["ownership_label"] = _ownership_label(share)


def _apply_ownership_signals(players: list[dict[str, Any]]) -> None:
    for player in players:
        ownership = player.get("projected_ownership")
        value = float(player.get("value") or 0.0)
        if ownership is None or ownership > 0.06 or value < 2.4:
            continue
        signals = list(player.get("signals") or [])
        if any(item.get("id") == "leverage" for item in signals):
            continue
        leverage = {
            "id": "leverage",
            "label": "Leverage",
            "tone": "positive",
        }
        signals = [leverage, *signals][:2]
        player["signals"] = signals
        player["primary_signal"] = signals[0]


def _ownership_label(value: float | None) -> str | None:
    if value is None:
        return None
    share = float(value)
    if share >= 0.20:
        return "Chalk"
    if share >= 0.12:
        return "High"
    if share >= 0.07:
        return "Mid"
    if share >= 0.03:
        return "Low"
    return "Contrarian"


def _matchup_from_assessment(assessment: Any) -> str:
    label = str(assessment or "").strip().lower()
    if label in {"elite", "strong"}:
        return "Very Favorable"
    if label == "solid":
        return "Favorable"
    if label == "cautious":
        return "Neutral"
    if label == "weak":
        return "Difficult"
    return "Neutral"


def _risk_from_assessment(assessment: Any) -> str:
    label = str(assessment or "").strip().lower()
    if label in {"elite", "strong"}:
        return "low"
    if label == "solid":
        return "moderate"
    if label in {"cautious", "weak"}:
        return "high"
    return "moderate"


def _signals_for_player(
    player: dict[str, Any],
    *,
    value: float | None,
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    assessment = str(
        player.get("overall_assessment") or ""
    ).strip().lower()
    if assessment in {"elite", "strong"}:
        signals.append(
            {
                "id": "strong_profile",
                "label": "Strong Profile",
                "tone": "positive",
            }
        )
    if value is not None and value >= 3.0:
        signals.append(
            {
                "id": "strong_value",
                "label": "Strong Value",
                "tone": "positive",
            }
        )
    opportunity = _num(player.get("opportunity_score"))
    if opportunity is not None and opportunity >= 65:
        signals.append(
            {
                "id": "opportunity",
                "label": "Rising Opp",
                "tone": "positive",
            }
        )
    if not signals:
        signals.append(
            {
                "id": "stable",
                "label": "Stable",
                "tone": "neutral",
            }
        )
    return signals[:2]


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number
