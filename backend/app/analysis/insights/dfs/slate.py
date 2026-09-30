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


def list_dfs_weeks(
    *,
    season: int | None = None,
) -> dict[str, Any]:
    """Weeks with REG games for the season, plus the default week."""

    resolved_season = _resolve_season(season)
    weeks = _weeks_with_games(resolved_season)
    current = _resolve_week(None, season=resolved_season)
    if current not in weeks and weeks:
        # Prefer the latest scheduled week when current is ahead
        # of published games, else keep nflverse current week.
        if current > max(weeks):
            current = max(weeks)
        else:
            weeks = sorted({*weeks, current})
    elif not weeks:
        weeks = [current]
    return {
        "season": resolved_season,
        "weeks": weeks,
        "current_week": current,
    }


def list_dfs_slates(
    *,
    season: int | None = None,
    week: int | None = None,
    contest_type: str | None = "classic",
) -> list[dict[str, Any]]:
    resolved_season = _resolve_season(season)
    resolved_week = _resolve_week(
        week,
        season=resolved_season,
    )
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
                "label": meta["label"],
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
    scoring: str | None = "ppr",
    limit: int = 250,
) -> dict[str, Any]:
    # DFS projections stay on full PPR. Scoring format switches
    # live on Player Overview only.
    scoring_key = "ppr"
    _ = scoring  # accepted for API compatibility; ignored
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
        scoring=scoring_key,
        limit=fetch_limit,
    )
    week_context = _load_week_context_maps(
        season=season_value,
        week=int(week_value),
    )
    try:
        from app.analysis.insights.dfs.projection_baselines import (
            load_player_projection_baselines,
        )

        baseline_by_player = load_player_projection_baselines(
            season=season_value,
            scoring=scoring_key,
            player_ids=[
                str(player.get("player_id") or "")
                for player in raw_players
                if player.get("player_id")
            ],
        )
    except Exception:
        baseline_by_player = {}

    players = [
        _to_dfs_player(
            player,
            site=site_config["id"],
            opponents=opponents,
            contest_type=format_key,
            salary_map=salary_map,
            week_context=week_context,
            baseline=baseline_by_player.get(
                str(player.get("player_id") or "")
            ),
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
            if _team_abbr(player.get("team")) in team_filter
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
        # Never drop uploaded-salary players — backups priced on
        # the DK/FD file must remain searchable / force-includable.
        uploaded = [
            player
            for player in players
            if player.get("salary_source") == "uploaded"
        ]
        rest = [
            player
            for player in players
            if player.get("salary_source") != "uploaded"
        ]
        room = max(0, int(limit) - len(uploaded))
        players = uploaded + rest[:room]
        players.sort(
            key=lambda item: (
                -(float(item.get("projection") or 0.0)),
                str(item.get("name") or ""),
            )
        )

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
    note = (
        "PPR InsightPilot calibrated projections "
        "(sample-size regression + opportunity/distribution "
        "guardrails) × weekly matchup/environment"
        + (
            "; upload a DK/FD salary CSV for real prices"
            if salary_hits == 0
            else ""
        )
        + (
            " (showdown)."
            if format_key == "showdown"
            else f" ({start_label.lower()})."
        )
    )
    if salary_hits > 0:
        note = (
            f"Using {salary_hits} uploaded "
            f"{site_config['name']} {format_key} salaries "
            f"for week {int(week_value)}. {note}"
        )

    return {
        "slate_id": parsed["slate_id"],
        "sport": "NFL",
        "label": label,
        "season": season_value,
        "week": int(week_value),
        "kind": kind,
        "contest_type": format_key,
        "scoring": scoring_key,
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
            current_week = max(1, int(nfl.get_current_week()))
            scheduled = _weeks_with_games(int(season))
            if scheduled and current_week not in scheduled:
                # nflverse can report a week before games land;
                # prefer the latest week that has REG games.
                if current_week > max(scheduled):
                    return max(scheduled)
            return current_week
    except Exception:
        pass
    scheduled = _weeks_with_games(int(season))
    if scheduled:
        return max(scheduled)
    return 1


def _weeks_with_games(season: int) -> list[int]:
    """REG weeks present in the nflverse schedule for a season."""

    try:
        import nflreadpy as nfl

        schedules = nfl.load_schedules([int(season)])
        if hasattr(schedules, "to_pandas"):
            schedules = schedules.to_pandas()
    except Exception:
        return []

    if schedules is None or getattr(schedules, "empty", True):
        return []

    weeks: set[int] = set()
    for row in schedules.to_dict(orient="records"):
        if not _is_reg_game(row):
            continue
        try:
            weeks.add(int(row.get("week")))
        except (TypeError, ValueError):
            continue
    return sorted(weeks)


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
    from app.canonical.ids import canonicalize_team_abbreviation

    return canonicalize_team_abbreviation(value)


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
    week_context: dict[str, Any] | None = None,
    matchup_context: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    player_id = str(player.get("player_id") or "").strip()
    if not player_id:
        return None
    position = _normalize_position(player.get("position"))
    # Classic NFL DFS skill slate excludes kickers on DK/FD main.
    # Showdown allows any player from the game, including K.
    if position == "K" and contest_type != "showdown":
        return None

    raw_projection = _num(player.get("fppg"))
    if raw_projection is None:
        # Prefer per-game rate; season totals inflate projections.
        games = _num(player.get("games"))
        total = _num(player.get("fantasy_points"))
        if total is not None and games and games > 0:
            raw_projection = float(total) / float(games)
        elif total is not None:
            raw_projection = float(total)
    try:
        depth_order = (
            int(player.get("depth_order"))
            if player.get("depth_order") is not None
            else None
        )
    except (TypeError, ValueError):
        depth_order = None

    uploaded_salary = None
    if salary_map:
        uploaded_salary = salary_map.get(player_id)

    if raw_projection is None:
        # Keep DFS-relevant players even with no logged FPPG:
        # Active depth-chart players (incl. QB3 like Case Keenum)
        # and anyone priced on an uploaded salary file.
        games = player.get("games")
        status_key = str(player.get("status") or "Active").strip().lower()
        active_roster = status_key in {"active", "a", ""}
        if uploaded_salary is not None or (
            depth_order is not None and active_roster
        ):
            raw_projection = 0.0
        elif not games:
            return None
        else:
            raw_projection = 0.0

    current_games = int(_num(player.get("games")) or 0)
    baseline_row = baseline or {}
    from app.analysis.insights.dfs.projection_calibration import (
        calibrate_projection,
    )

    calibrated = calibrate_projection(
        raw_projection=float(raw_projection),
        position=position,
        current_season_games=current_games,
        historical_baseline=_num(
            baseline_row.get("historical_baseline")
        ),
        historical_games=int(
            baseline_row.get("historical_games") or 0
        ),
        historical_p90=_num(baseline_row.get("historical_p90")),
        opportunity_score=_num(player.get("opportunity_score")),
        depth_order=depth_order,
        roster_status=(
            str(player.get("status"))
            if player.get("status") is not None
            else None
        ),
    )
    # Optimizer / analyzer consume calibrated median before
    # weekly matchup scaling.
    base_projection = float(calibrated.insightpilot_projection)

    team = _team_abbr(player.get("team"))
    opponent = None
    if team and opponents:
        opponent = opponents.get(team)

    if matchup_context is None and week_context is not None:
        matchup_context = _resolve_player_week_context(
            player_id=player_id,
            opponent=opponent,
            week_context=week_context,
        )

    adjusted = _opponent_adjusted_projection(
        base=float(base_projection),
        position=position,
        context=matchup_context,
        has_opponent=bool(opponent),
    )
    projection = float(adjusted["projection"])
    matchup_score = adjusted.get("matchup_score")
    environment_score = adjusted.get("environment_score")
    matchup_factor = adjusted.get("adjustment_factor")

    if uploaded_salary is not None:
        salary = int(uploaded_salary)
        salary_source = "uploaded"
    else:
        # Keep synthetic salaries on calibrated baseline so
        # matchup edge shows up in projection/value, not price.
        salary = _synthetic_salary(
            position=position,
            projection=float(base_projection),
            site=site,
            contest_type=contest_type,
        )
        salary_source = "synthetic"

    value = None
    if salary and salary > 0:
        value = round(float(projection) / (salary / 1000.0), 2)

    # Prefer calibration range, then apply matchup factor so
    # floor/ceiling move with the weekly outlook.
    range_factor = float(matchup_factor) if matchup_factor else 1.0
    floor = round(
        float(calibrated.projection_floor) * range_factor,
        1,
    )
    ceiling = round(
        float(calibrated.projection_ceiling) * range_factor,
        1,
    )
    if matchup_score is not None:
        matchup = _matchup_label_from_score(float(matchup_score))
    else:
        matchup = _matchup_from_assessment(
            player.get("overall_assessment")
        )
    signals = _signals_for_player(player, value=value)

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
        "raw_projection": calibrated.raw_projection,
        "insightpilot_projection": round(float(projection), 1),
        "base_projection": round(float(base_projection), 1),
        "projection_adjustment": calibrated.projection_adjustment,
        "projection_adjustment_reason": (
            calibrated.projection_adjustment_reason
        ),
        "projection_confidence": calibrated.projection_confidence,
        "sample_size_confidence": (
            calibrated.sample_size_confidence
        ),
        "current_season_games": calibrated.current_season_games,
        "historical_games": calibrated.historical_games,
        "historical_baseline": calibrated.historical_baseline,
        "matchup_adjustment_factor": (
            round(float(matchup_factor), 3)
            if matchup_factor is not None
            else None
        ),
        "floor": floor,
        "ceiling": ceiling,
        "projected_ownership": None,
        "ownership_label": None,
        "value": value,
        "matchup_rating": matchup,
        "matchup_label": matchup,
        "matchup_score": matchup_score,
        "environment_score": environment_score,
        "opportunity_rating": _num(
            player.get("opportunity_score")
        ),
        "efficiency_rating": None,
        "risk_level": _risk_from_assessment(
            player.get("overall_assessment")
        ),
        "volatility": (
            "high"
            if calibrated.projection_confidence
            in {"Very Low", "Low"}
            else "moderate"
        ),
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
        "calibration_flags": list(calibrated.flags),
    }


def _load_week_context_maps(
    *,
    season: int,
    week: int,
) -> dict[str, Any]:
    """
    Weekly projection context:
      by_player  — environment (+ stored matchup when available)
      by_opponent — prospective matchup scores from latest
                    defensive priors, keyed by team abbr
    """

    by_player: dict[str, dict[str, Any]] = {}
    by_opponent: dict[str, dict[str, Any]] = {}

    try:
        from app.canonical.analytics.player_matchup import (
            get_player_matchup,
        )

        matchups = get_player_matchup(
            [int(season)],
            force_refresh=False,
            persist=False,
        )
        if matchups is not None and not matchups.empty:
            week_frame = matchups[
                (matchups["season"].astype(int) == int(season))
                & (matchups["week"].astype(int) == int(week))
            ]
            for row in week_frame.to_dict(orient="records"):
                player_id = str(row.get("player_id") or "").strip()
                if not player_id:
                    continue
                # Skip empty / NaN matchup rows (common for
                # upcoming weeks that lack defense game facts).
                if _num(row.get("matchup_score")) is None and (
                    _num(row.get("pass_matchup_score")) is None
                    and _num(row.get("rush_matchup_score"))
                    is None
                    and _num(row.get("receiving_matchup_score"))
                    is None
                ):
                    continue
                by_player.setdefault(player_id, {})[
                    "matchup"
                ] = row
    except Exception:
        pass

    try:
        from app.canonical.analytics.player_environment import (
            get_player_environment,
        )

        environments = get_player_environment(
            [int(season)],
            force_refresh=False,
            persist=False,
        )
        if environments is not None and not environments.empty:
            week_frame = environments[
                (
                    environments["season"].astype(int)
                    == int(season)
                )
                & (environments["week"].astype(int) == int(week))
            ]
            for row in week_frame.to_dict(orient="records"):
                player_id = str(row.get("player_id") or "").strip()
                if not player_id:
                    continue
                by_player.setdefault(player_id, {})[
                    "environment"
                ] = row
    except Exception:
        pass

    by_opponent = _opponent_matchup_priors(season=int(season))

    return {
        "by_player": by_player,
        "by_opponent": by_opponent,
    }


def _opponent_matchup_priors(
    *,
    season: int,
) -> dict[str, dict[str, Any]]:
    """team abbr → matchup score dict from season-to-date defense."""

    try:
        import pandas as pd
        from app.analysis.insights.player_matchups import (
            _score_matchup_from_priors,
        )
        from app.canonical.dim_team import get_dim_team
        from app.canonical.fact_defensive_game import (
            get_fact_defensive_game,
        )
    except Exception:
        return {}

    try:
        defense = get_fact_defensive_game(
            [int(season)],
            force_refresh=False,
            persist=False,
        )
    except Exception:
        return {}
    if defense is None or defense.empty:
        return {}

    metric_cols = [
        "pass_epa_allowed",
        "rush_epa_allowed",
        "pass_yards_allowed",
        "rush_yards_allowed",
        "receiving_yards_allowed",
        "targets_allowed",
        "pressure_rate",
        "sack_rate",
    ]
    working = defense.copy()
    for column in metric_cols:
        if column not in working.columns:
            working[column] = None
        working[column] = pd.to_numeric(
            working[column],
            errors="coerce",
        )

    # Season-to-date averages — usable for upcoming weeks when
    # shift()-based priors are empty (early season / unplayed week).
    grouped = working.groupby("defensive_team_id", sort=False)
    means = grouped[metric_cols].mean(numeric_only=True)
    if means.empty:
        return {}

    team_abbr_by_id: dict[str, str] = {}
    try:
        teams = get_dim_team(force_refresh=False, persist=False)
        if teams is not None and not teams.empty:
            for row in teams.to_dict(orient="records"):
                team_id = str(row.get("team_id") or "").strip()
                abbr = _team_abbr(row.get("team_abbreviation"))
                if team_id and abbr:
                    team_abbr_by_id[team_id] = abbr
    except Exception:
        pass

    by_opponent: dict[str, dict[str, Any]] = {}
    for team_id, row in means.iterrows():
        abbr = team_abbr_by_id.get(str(team_id))
        if not abbr:
            continue
        prior_row = {
            f"prior_{column}": (
                float(row[column])
                if row[column] == row[column]
                else None
            )
            for column in metric_cols
        }
        scores = _score_matchup_from_priors(prior_row)
        if all(value is None for value in scores.values()):
            continue
        by_opponent[abbr] = {
            "matchup_score": scores.get("matchup_score"),
            "pass_matchup_score": scores.get(
                "pass_matchup_score"
            ),
            "rush_matchup_score": scores.get(
                "rush_matchup_score"
            ),
            "receiving_matchup_score": scores.get(
                "receiving_matchup_score"
            ),
            "opponent_team_id": str(team_id),
            "source": "season_defense_avg",
        }
    return by_opponent


def _resolve_player_week_context(
    *,
    player_id: str,
    opponent: str | None,
    week_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not week_context:
        return None
    by_player = week_context.get("by_player") or {}
    by_opponent = week_context.get("by_opponent") or {}
    context = dict(by_player.get(str(player_id) or "") or {})

    stored = context.get("matchup")
    usable = (
        stored is not None
        and (
            _num(stored.get("matchup_score")) is not None
            or _num(stored.get("pass_matchup_score")) is not None
            or _num(stored.get("rush_matchup_score")) is not None
            or _num(stored.get("receiving_matchup_score"))
            is not None
        )
    )
    if not usable and opponent:
        opp_key = _team_abbr(opponent)
        opp_matchup = by_opponent.get(opp_key) if opp_key else None
        if opp_matchup:
            context["matchup"] = opp_matchup

    return context or None


def _position_matchup_score(
    position: str,
    matchup: dict[str, Any] | None,
) -> float | None:
    if not matchup:
        return None
    overall = _num(matchup.get("matchup_score"))
    pass_score = _num(matchup.get("pass_matchup_score"))
    rush_score = _num(matchup.get("rush_matchup_score"))
    recv_score = _num(matchup.get("receiving_matchup_score"))
    if position == "QB":
        return pass_score if pass_score is not None else overall
    if position == "RB":
        parts = [
            value
            for value in (rush_score, recv_score)
            if value is not None
        ]
        if not parts:
            return overall
        if rush_score is None:
            return recv_score
        if recv_score is None:
            return rush_score
        return (0.65 * rush_score) + (0.35 * recv_score)
    if position in {"WR", "TE"}:
        return recv_score if recv_score is not None else overall
    if position == "DEF":
        # Soft matchups for offenses are harder for defenses.
        if overall is None:
            return None
        return 100.0 - float(overall)
    return overall


def _opponent_adjusted_projection(
    *,
    base: float,
    position: str,
    context: dict[str, Any] | None,
    has_opponent: bool,
) -> dict[str, Any]:
    """
    Scale season FPPG by weekly opponent matchup / environment.

    matchup_score 50 ≈ neutral → factor 1.0
    30 → 0.90, 70 → 1.10 (clamped ~0.80–1.20)
    """

    matchup_row = (context or {}).get("matchup")
    env_row = (context or {}).get("environment")
    matchup_score = _position_matchup_score(position, matchup_row)
    environment_score = _num(
        (env_row or {}).get("game_environment_score")
    )

    factor = 1.0
    if has_opponent and matchup_score is not None:
        factor *= 0.75 + (0.50 * (float(matchup_score) / 100.0))
    if has_opponent and environment_score is not None:
        factor *= 0.95 + (
            0.10 * (float(environment_score) / 100.0)
        )
    factor = max(0.80, min(1.20, float(factor)))
    projection = float(base) * factor
    return {
        "projection": projection,
        "matchup_score": (
            round(float(matchup_score), 1)
            if matchup_score is not None
            else None
        ),
        "environment_score": (
            round(float(environment_score), 1)
            if environment_score is not None
            else None
        ),
        "adjustment_factor": factor if has_opponent else None,
    }


def _matchup_label_from_score(score: float) -> str:
    if score >= 65:
        return "Very Favorable"
    if score >= 55:
        return "Favorable"
    if score >= 45:
        return "Neutral"
    return "Difficult"


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
