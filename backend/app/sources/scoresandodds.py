"""
ScoresAndOdds odds source (Action Network scoreboard).

ScoresAndOdds.com renders the Action Network scoreboard. This
module pulls the same live JSON feed used by those pages:

  GET https://api.actionnetwork.com/web/v1/scoreboard/{league}

Week-based leagues (NCAAF, NFL) accept ``?week=N``. Slate leagues
(NBA, NHL, MLB, NCAAB) return the current dated slate.

Normalized consensus lines feed fact_game_market ingestion:
  NCAAF → college_football
  NFL → fantasy_football
  NBA / NHL / MLB / NCAAB → sports_odds
"""

from __future__ import annotations

import json
import re
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

LeagueId = Literal["ncaaf", "nfl", "nba", "nhl", "mlb", "ncaab"]
ScheduleMode = Literal["week", "slate"]

SOURCE_LABEL = "scoresandodds"

# Prefer Action Network "core" books when present; fall back to
# median across remaining game-level quotes.
PREFERRED_BOOK_IDS = (15, 30, 69, 75)

WEEK_BASED_LEAGUES: frozenset[str] = frozenset({"ncaaf", "nfl"})
SLATE_LEAGUES: frozenset[str] = frozenset(
    {"nba", "nhl", "mlb", "ncaab"}
)


@dataclass(frozen=True)
class LeagueConfig:
    id: LeagueId
    homepage: str
    scoreboard_path: str
    # Action Network abbr → canonical dim_team abbreviation.
    abbr_aliases: dict[str, str]
    # week: football weeks; slate: current dated board.
    schedule_mode: ScheduleMode = "week"


LEAGUES: dict[LeagueId, LeagueConfig] = {
    "ncaaf": LeagueConfig(
        id="ncaaf",
        homepage="https://www.scoresandodds.com/ncaaf",
        scoreboard_path="ncaaf",
        schedule_mode="week",
        abbr_aliases={
            "AFA": "AF",
            "ARI": "ARIZ",
            "BAMA": "ALA",
            "BOISE": "BOIS",
            "BUFF": "BUF",
            # Action Network short codes → sportsdataverse.
            "CC": "CCU",
            "CHA": "CLT",
            "JVST": "JXST",
            "NCST": "NCSU",
            "NW": "NU",
            "RUT": "RUTG",
            "UCONN": "CONN",
            "UMASS": "MASS",
            "UMD": "MD",
            "WF": "WAKE",
        },
    ),
    "nfl": LeagueConfig(
        id="nfl",
        homepage="https://www.scoresandodds.com/nfl",
        scoreboard_path="nfl",
        schedule_mode="week",
        abbr_aliases={
            # Align with app.canonical.ids.TEAM_ABBREVIATION_ALIASES.
            "LAR": "LA",
            "WSH": "WAS",
            "JAC": "JAX",
            "ARZ": "ARI",
            "GNB": "GB",
            "KAN": "KC",
            "NOR": "NO",
            "NWE": "NE",
            "SFO": "SF",
            "TAM": "TB",
            "OAK": "LV",
            "SD": "LAC",
            "SDG": "LAC",
            # ScoresAndOdds logo filename quirks.
            "NYGD": "NYG",
        },
    ),
    "nba": LeagueConfig(
        id="nba",
        homepage="https://www.scoresandodds.com/nba",
        scoreboard_path="nba",
        schedule_mode="slate",
        abbr_aliases={
            "GS": "GSW",
            "GOLDEN STATE": "GSW",
            "NO": "NOP",
            "NOP": "NOP",
            "NY": "NYK",
            "SA": "SAS",
            "UTAH": "UTA",
            "WSH": "WAS",
            "PHO": "PHX",
            "BRK": "BKN",
            "BRO": "BKN",
        },
    ),
    "nhl": LeagueConfig(
        id="nhl",
        homepage="https://www.scoresandodds.com/nhl",
        scoreboard_path="nhl",
        schedule_mode="slate",
        abbr_aliases={
            # Keep ESPN-friendly short codes (la/nj/sj/tb).
            "NJD": "NJ",
            "TBL": "TB",
            "LAK": "LA",
            "SJS": "SJ",
            "VEGAS": "VGK",
            "MON": "MTL",
            "WAS": "WSH",
        },
    ),
    "mlb": LeagueConfig(
        id="mlb",
        homepage="https://www.scoresandodds.com/mlb",
        scoreboard_path="mlb",
        schedule_mode="slate",
        abbr_aliases={
            "AZ": "ARI",
            "ARZ": "ARI",
            "CWS": "CHW",
            "KAN": "KC",
            "SFG": "SF",
            "SDP": "SD",
            "TBR": "TB",
            "WAS": "WSH",
        },
    ),
    "ncaab": LeagueConfig(
        id="ncaab",
        homepage="https://www.scoresandodds.com/ncaab",
        scoreboard_path="ncaab",
        schedule_mode="slate",
        abbr_aliases={
            "UCONN": "CONN",
            "UMASS": "MASS",
            "NCST": "NCSU",
            "NW": "NU",
        },
    ),
}

# ScoresAndOdds team-page slug → canonical abbreviation.
NFL_TEAM_SLUGS: dict[str, str] = {
    "cardinals": "ARI",
    "falcons": "ATL",
    "ravens": "BAL",
    "bills": "BUF",
    "panthers": "CAR",
    "bears": "CHI",
    "bengals": "CIN",
    "browns": "CLE",
    "cowboys": "DAL",
    "broncos": "DEN",
    "lions": "DET",
    "packers": "GB",
    "texans": "HOU",
    "colts": "IND",
    "jaguars": "JAX",
    "chiefs": "KC",
    "raiders": "LV",
    "chargers": "LAC",
    "rams": "LA",
    "dolphins": "MIA",
    "vikings": "MIN",
    "patriots": "NE",
    "saints": "NO",
    "giants": "NYG",
    "jets": "NYJ",
    "eagles": "PHI",
    "steelers": "PIT",
    "49ers": "SF",
    "seahawks": "SEA",
    "buccaneers": "TB",
    "titans": "TEN",
    "commanders": "WAS",
}

# Back-compat aliases used by CFB ingest / tests.
SOURCE_HOMEPAGE = LEAGUES["ncaaf"].homepage
ACTION_SCOREBOARD_URL = (
    "https://api.actionnetwork.com/web/v1/scoreboard/ncaaf"
)
ABBR_ALIASES = LEAGUES["ncaaf"].abbr_aliases


def get_league(league: LeagueId | str) -> LeagueConfig:
    key = str(league or "").strip().lower()
    if key not in LEAGUES:
        raise ValueError(
            f"Unsupported ScoresAndOdds league: {league!r}. "
            f"Expected one of {sorted(LEAGUES)}."
        )
    return LEAGUES[key]  # type: ignore[index]


def fetch_scoreboard(
    league: LeagueId | str = "ncaaf",
    *,
    week: int | None = None,
    season: int | None = None,
    date: str | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    config = get_league(league)
    params: list[str] = []
    if (
        week is not None
        and config.schedule_mode == "week"
        and int(week) > 0
    ):
        params.append(f"week={int(week)}")
    if season is not None:
        params.append(f"season={int(season)}")
    if date:
        # Action Network dated slate: YYYYMMDD or YYYY-MM-DD.
        compact = str(date).strip().replace("-", "")
        if compact:
            params.append(f"date={compact}")
    url = (
        "https://api.actionnetwork.com/web/v1/scoreboard/"
        f"{config.scoreboard_path}"
    )
    if params:
        url = f"{url}?{'&'.join(params)}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "InsightPilot/1.0 (+https://insightpilot.local; "
                f"{config.id.upper()} odds refresh)"
            ),
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(
            f"ScoresAndOdds/Action Network {config.id} scoreboard "
            f"HTTP {exc.code}: {body}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Unable to fetch ScoresAndOdds {config.id} "
            f"scoreboard: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Unexpected ScoresAndOdds scoreboard payload."
        )
    return payload


def scoreboard_meta(
    payload: dict[str, Any],
    *,
    league: LeagueId | str = "ncaaf",
) -> dict[str, Any]:
    config = get_league(league)
    league_payload = payload.get("league") or {}
    week = _as_int(league_payload.get("current_week"))
    # Slate sports publish current_week=-1 when week is unused.
    if week is not None and week < 1:
        week = None
    return {
        "league": league_payload.get("name") or config.id,
        "season": _as_int(league_payload.get("current_season")),
        "week": week,
        "season_type": league_payload.get("current_season_type"),
        "schedule_mode": config.schedule_mode,
        "game_count": len(payload.get("games") or []),
        "source": SOURCE_LABEL,
        "homepage": config.homepage,
    }


def normalize_scoreboard_games(
    payload: dict[str, Any],
    *,
    league: LeagueId | str = "ncaaf",
) -> list[dict[str, Any]]:
    """
    Flatten scoreboard games into one consensus line row each.
    """

    config = get_league(league)
    league_payload = payload.get("league") or {}
    default_season = _as_int(league_payload.get("current_season"))
    rows: list[dict[str, Any]] = []

    for game in payload.get("games") or []:
        if not isinstance(game, dict):
            continue
        teams = {
            int(team["id"]): team
            for team in (game.get("teams") or [])
            if isinstance(team, dict) and team.get("id") is not None
        }
        home_id = _as_int(game.get("home_team_id"))
        away_id = _as_int(game.get("away_team_id"))
        home = teams.get(home_id or -1) or {}
        away = teams.get(away_id or -1) or {}
        if not home or not away:
            continue

        odds_list = game.get("odds") or []
        consensus = _consensus_game_odds(odds_list)
        if not consensus:
            latest = (
                ((game.get("boxscore") or {}).get("latest_odds") or {})
                .get("game")
            )
            if isinstance(latest, dict):
                consensus = _normalize_odds_dict(latest)

        if not consensus:
            continue

        opening = _opening_game_odds(odds_list)
        spread = consensus.get("spread_home")
        total = consensus.get("total")
        home_implied = None
        away_implied = None
        if spread is not None and total is not None:
            home_implied = (float(total) - float(spread)) / 2.0
            away_implied = (float(total) + float(spread)) / 2.0

        opening_spread = (
            opening.get("spread_home") if opening else None
        )
        opening_total = opening.get("total") if opening else None
        opening_home_implied = None
        opening_away_implied = None
        if opening_spread is not None and opening_total is not None:
            opening_home_implied = (
                float(opening_total) - float(opening_spread)
            ) / 2.0
            opening_away_implied = (
                float(opening_total) + float(opening_spread)
            ) / 2.0

        week = _as_int(game.get("week"))
        if week is not None and week < 1:
            week = None

        rows.append(
            {
                "provider_game_id": str(game.get("id") or ""),
                "season": _as_int(game.get("season")) or default_season,
                "week": week,
                "season_type": (
                    str(
                        game.get("type")
                        or league_payload.get("current_season_type")
                        or "reg"
                    ).lower()
                ),
                "start_time": game.get("start_time"),
                "status": game.get("status") or game.get("real_status"),
                "home_abbr": _clean_abbr(
                    home.get("abbr"),
                    aliases=config.abbr_aliases,
                ),
                "away_abbr": _clean_abbr(
                    away.get("abbr"),
                    aliases=config.abbr_aliases,
                ),
                "home_name": home.get("full_name") or home.get("display_name"),
                "away_name": away.get("full_name") or away.get("display_name"),
                "home_team_provider_id": str(home_id) if home_id else None,
                "away_team_provider_id": str(away_id) if away_id else None,
                "spread": spread,
                "over_under": total,
                "home_implied_total": home_implied,
                "away_implied_total": away_implied,
                "home_moneyline": consensus.get("ml_home"),
                "away_moneyline": consensus.get("ml_away"),
                "spread_price": consensus.get("spread_home_line"),
                "total_over_price": consensus.get("over"),
                "total_under_price": consensus.get("under"),
                "book_id": consensus.get("book_id"),
                "line_inserted_at": consensus.get("inserted"),
                "opening_spread": opening_spread,
                "opening_over_under": opening_total,
                "opening_home_implied_total": opening_home_implied,
                "opening_away_implied_total": opening_away_implied,
                "opening_home_moneyline": (
                    opening.get("ml_home") if opening else None
                ),
                "opening_away_moneyline": (
                    opening.get("ml_away") if opening else None
                ),
                "opening_captured_at": (
                    opening.get("inserted") if opening else None
                ),
                "opening_source": (
                    "actionnetwork_earliest" if opening else None
                ),
                "source": SOURCE_LABEL,
                "league": config.id,
            }
        )
    return rows


def fetch_odds_rows(
    league: LeagueId | str = "ncaaf",
    *,
    weeks: list[int] | None = None,
    season: int | None = None,
    dates: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Fetch odds for a league.

    Week-based leagues (NCAAF/NFL): when ``weeks`` is omitted, uses
    the league current week from the unfiltered scoreboard response.

    Slate leagues (NBA/NHL/MLB/NCAAB): pulls the current dated board
    (or explicit ``dates`` as YYYYMMDD / YYYY-MM-DD). ``weeks`` is
    ignored.

    Current lines come from the Action Network scoreboard JSON.
    Opening lines prefer the ScoresAndOdds.com Open column (HTML),
    falling back to the earliest Action Network game quote.
    """

    config = get_league(league)

    if config.schedule_mode == "slate":
        return _fetch_slate_odds_rows(
            config,
            season=season,
            dates=dates,
        )

    if weeks:
        all_rows: list[dict[str, Any]] = []
        meta: dict[str, Any] = {
            "source": SOURCE_LABEL,
            "homepage": config.homepage,
            "league": config.id,
            "schedule_mode": config.schedule_mode,
            "weeks": [],
        }
        for week in weeks:
            payload = fetch_scoreboard(
                config.id,
                week=week,
                season=season,
            )
            week_meta = scoreboard_meta(payload, league=config.id)
            meta["weeks"].append(week_meta)
            meta["season"] = week_meta.get("season") or season
            rows = normalize_scoreboard_games(
                payload,
                league=config.id,
            )
            rows = _attach_homepage_openings(
                rows,
                league=config.id,
                season=int(
                    season
                    or week_meta.get("season")
                    or datetime.now(timezone.utc).year
                ),
                week=int(week),
                season_type=str(
                    week_meta.get("season_type") or "reg"
                ),
            )
            all_rows.extend(rows)
        meta["row_count"] = len(all_rows)
        meta["opening_from_homepage"] = sum(
            1
            for row in all_rows
            if row.get("opening_source") == "scoresandodds_open"
        )
        return all_rows, meta

    payload = fetch_scoreboard(config.id, season=season)
    meta = scoreboard_meta(payload, league=config.id)
    rows = normalize_scoreboard_games(payload, league=config.id)
    resolved_season = int(
        season
        or meta.get("season")
        or datetime.now(timezone.utc).year
    )
    resolved_week = meta.get("week")
    rows = _attach_homepage_openings(
        rows,
        league=config.id,
        season=resolved_season,
        week=int(resolved_week) if resolved_week is not None else None,
        season_type=str(meta.get("season_type") or "reg"),
    )
    meta["row_count"] = len(rows)
    meta["opening_from_homepage"] = sum(
        1
        for row in rows
        if row.get("opening_source") == "scoresandodds_open"
    )
    return rows, meta


def _fetch_slate_odds_rows(
    config: LeagueConfig,
    *,
    season: int | None = None,
    dates: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    date_list = [str(d).strip() for d in (dates or []) if str(d).strip()]
    if not date_list:
        date_list = [""]  # current slate (no date filter)

    all_rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "source": SOURCE_LABEL,
        "homepage": config.homepage,
        "league": config.id,
        "schedule_mode": config.schedule_mode,
        "dates": [],
    }
    for date in date_list:
        payload = fetch_scoreboard(
            config.id,
            season=season,
            date=date or None,
        )
        date_meta = scoreboard_meta(payload, league=config.id)
        if date:
            date_meta = {**date_meta, "date": date}
        meta["dates"].append(date_meta)
        meta["season"] = date_meta.get("season") or season
        meta["season_type"] = date_meta.get("season_type")
        rows = normalize_scoreboard_games(
            payload,
            league=config.id,
        )
        rows = _attach_homepage_openings(
            rows,
            league=config.id,
            season=int(
                season
                or date_meta.get("season")
                or datetime.now(timezone.utc).year
            ),
            week=None,
            season_type=str(date_meta.get("season_type") or "reg"),
        )
        all_rows.extend(rows)

    # Deduplicate by provider game when multiple dates overlap.
    by_id: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        key = str(row.get("provider_game_id") or "")
        if key:
            by_id[key] = row
        else:
            by_id[f"anon:{len(by_id)}"] = row
    deduped = list(by_id.values())
    meta["row_count"] = len(deduped)
    meta["opening_from_homepage"] = sum(
        1
        for row in deduped
        if row.get("opening_source") == "scoresandodds_open"
    )
    return deduped, meta


def homepage_week_url(
    league: LeagueId | str,
    *,
    season: int,
    week: int,
    season_type: str = "reg",
) -> str:
    config = get_league(league)
    st = str(season_type or "reg").strip().lower()
    if st in {"reg", "regular", "regular_season"}:
        st = "reg"
    elif st in {"post", "postseason", "playoffs"}:
        st = "post"
    return (
        f"{config.homepage}?week={int(season)}-{st}-{int(week)}"
    )


def fetch_homepage_html(
    league: LeagueId | str,
    *,
    season: int | None = None,
    week: int | None = None,
    season_type: str = "reg",
    timeout_seconds: float = 30.0,
) -> str:
    config = get_league(league)
    if (
        config.schedule_mode == "week"
        and season is not None
        and week is not None
        and int(week) > 0
    ):
        url = homepage_week_url(
            config.id,
            season=int(season),
            week=int(week),
            season_type=season_type,
        )
    else:
        url = config.homepage
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; InsightPilot/1.0; "
                f"{config.id.upper()} opening-odds refresh)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        raise RuntimeError(
            f"Unable to fetch ScoresAndOdds homepage for "
            f"{config.id}: {exc}"
        ) from exc


def parse_homepage_openings(
    html: str,
    *,
    league: LeagueId | str = "ncaaf",
) -> list[dict[str, Any]]:
    """
    Parse the Open column from ScoresAndOdds event cards.

    SAO shows open total on one side (``o47.5``) and open spread
    on the other (``-1.5``). Spread is converted to home-team
    convention.
    """

    config = get_league(league)
    pattern = re.compile(
        rf'<div id="{re.escape(config.id)}\.(\d+)" class="event-card"',
        re.I,
    )
    starts = [m.start() for m in pattern.finditer(html)]
    if not starts:
        return []

    openings: list[dict[str, Any]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else start + 20000
        card = html[start:end]
        id_match = pattern.search(card)
        sao_game_id = id_match.group(1) if id_match else None
        sides: dict[str, dict[str, Any]] = {}
        for side in ("away", "home"):
            row_match = re.search(
                rf'<tr class="event-card-row[^"]*" data-side="{side}">'
                r"(.*?)</tr>",
                card,
                re.S | re.I,
            )
            if not row_match:
                continue
            row_html = row_match.group(1)
            abbr = _abbr_from_event_row(
                row_html,
                league=config.id,
                aliases=config.abbr_aliases,
            )
            open_match = re.search(
                r'class="event-card-open[^"]*"[\s\S]*?'
                r'<span class="data-value">\s*([^<]+?)\s*</span>',
                row_html,
                re.I,
            )
            token = (
                open_match.group(1).strip() if open_match else None
            )
            kind, value = _parse_open_token(token)
            sides[side] = {
                "abbr": abbr,
                "token": token,
                "kind": kind,
                "value": value,
            }

        opening_spread = None
        if sides.get("home", {}).get("kind") == "spread":
            opening_spread = sides["home"]["value"]
        elif sides.get("away", {}).get("kind") == "spread":
            opening_spread = -float(sides["away"]["value"])

        opening_total = None
        for side_data in sides.values():
            if side_data.get("kind") == "total":
                opening_total = side_data.get("value")
                break

        home_abbr = (sides.get("home") or {}).get("abbr")
        away_abbr = (sides.get("away") or {}).get("abbr")
        if not home_abbr or not away_abbr:
            continue
        if opening_spread is None and opening_total is None:
            continue

        opening_home_implied = None
        opening_away_implied = None
        if opening_spread is not None and opening_total is not None:
            opening_home_implied = (
                float(opening_total) - float(opening_spread)
            ) / 2.0
            opening_away_implied = (
                float(opening_total) + float(opening_spread)
            ) / 2.0

        openings.append(
            {
                "sao_game_id": sao_game_id,
                "home_abbr": home_abbr,
                "away_abbr": away_abbr,
                "opening_spread": opening_spread,
                "opening_over_under": opening_total,
                "opening_home_implied_total": opening_home_implied,
                "opening_away_implied_total": opening_away_implied,
                "opening_source": "scoresandodds_open",
            }
        )
    return openings


# --- NCAAF convenience wrappers (back-compat) ---

def fetch_ncaaf_scoreboard(
    *,
    week: int | None = None,
    season: int | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    return fetch_scoreboard(
        "ncaaf",
        week=week,
        season=season,
        timeout_seconds=timeout_seconds,
    )


def fetch_ncaaf_odds_rows(
    *,
    weeks: list[int] | None = None,
    season: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return fetch_odds_rows(
        "ncaaf",
        weeks=weeks,
        season=season,
    )


def fetch_nfl_odds_rows(
    *,
    weeks: list[int] | None = None,
    season: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return fetch_odds_rows(
        "nfl",
        weeks=weeks,
        season=season,
    )


def fetch_slate_odds_rows(
    league: LeagueId | str,
    *,
    season: int | None = None,
    dates: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convenience wrapper for NBA/NHL/MLB/NCAAB current-slate odds."""

    return fetch_odds_rows(
        league,
        season=season,
        dates=dates,
    )


def _attach_homepage_openings(
    rows: list[dict[str, Any]],
    *,
    league: LeagueId | str,
    season: int,
    week: int | None = None,
    season_type: str = "reg",
) -> list[dict[str, Any]]:
    """Overlay ScoresAndOdds Open-column values onto scoreboard rows."""

    if not rows:
        return rows
    try:
        html = fetch_homepage_html(
            league,
            season=season,
            week=week,
            season_type=season_type,
        )
        openings = parse_homepage_openings(html, league=league)
    except Exception:
        return rows

    by_matchup = {
        (
            str(item.get("home_abbr") or "").upper(),
            str(item.get("away_abbr") or "").upper(),
        ): item
        for item in openings
    }
    if not by_matchup:
        return rows

    updated: list[dict[str, Any]] = []
    for row in rows:
        home = str(row.get("home_abbr") or "").upper()
        away = str(row.get("away_abbr") or "").upper()
        opening = by_matchup.get((home, away))
        flipped = False
        if not opening:
            opening = by_matchup.get((away, home))
            flipped = bool(opening)
        if not opening:
            updated.append(row)
            continue

        merged = dict(row)
        spread = opening.get("opening_spread")
        total = opening.get("opening_over_under")
        if flipped and spread is not None:
            spread = -float(spread)
        home_implied = opening.get("opening_home_implied_total")
        away_implied = opening.get("opening_away_implied_total")
        if flipped:
            home_implied, away_implied = away_implied, home_implied
        if spread is not None and total is not None and (
            home_implied is None or away_implied is None
        ):
            home_implied = (float(total) - float(spread)) / 2.0
            away_implied = (float(total) + float(spread)) / 2.0

        merged["opening_spread"] = spread
        merged["opening_over_under"] = total
        merged["opening_home_implied_total"] = home_implied
        merged["opening_away_implied_total"] = away_implied
        merged["opening_source"] = "scoresandodds_open"
        merged["opening_captured_at"] = (
            merged.get("opening_captured_at")
            or datetime.now(timezone.utc).isoformat()
        )
        if opening.get("sao_game_id"):
            merged["sao_game_id"] = opening.get("sao_game_id")
        updated.append(merged)
    return updated


def _abbr_from_event_row(
    row_html: str,
    *,
    league: LeagueId | str,
    aliases: dict[str, str],
) -> str | None:
    config = get_league(league)
    # Logo filenames are preferred when present.
    for pattern in (
        rf"/teamlogos/{re.escape(config.id)}/\d+/([a-z0-9]+)\.png",
        r"/teamlogos/(?:nfl|ncaaf|ncaa|ncaab|nba|nhl|mlb)/\d+/([a-z0-9]+)\.png",
    ):
        logo = re.search(pattern, row_html, re.I)
        if logo:
            return _clean_abbr(logo.group(1), aliases=aliases)

    # ScoresAndOdds team page slug fallback (more reliable than logos).
    slug_match = re.search(
        rf"/{re.escape(config.id)}/teams/([a-z0-9-]+)",
        row_html,
        re.I,
    )
    if slug_match:
        slug = slug_match.group(1).lower()
        if config.id == "nfl" and slug in NFL_TEAM_SLUGS:
            return NFL_TEAM_SLUGS[slug]
        return _clean_abbr(slug, aliases=aliases)
    return None


def _parse_open_token(
    token: str | None,
) -> tuple[str | None, float | None]:
    raw = re.sub(r"\s+", "", str(token or "")).lower()
    if not raw or raw in {"-", "pk", "pick", "n/a", "tbd"}:
        return None, None
    match = re.match(r"([ou])?([+-]?\d+(?:\.\d+)?)", raw)
    if not match:
        return None, None
    kind = match.group(1)
    value = float(match.group(2))
    if kind in {"o", "u"}:
        return "total", value
    return "spread", value


def _opening_game_odds(
    odds: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Earliest game quote among preferred books (else any book).

    Used when the ScoresAndOdds Open column is unavailable.
    """

    game_odds = [
        o
        for o in odds
        if isinstance(o, dict)
        and str(o.get("type") or "").lower() == "game"
        and o.get("spread_home") is not None
        and o.get("total") is not None
    ]
    if not game_odds:
        return None
    preferred = [
        o
        for o in game_odds
        if _as_int(o.get("book_id")) in PREFERRED_BOOK_IDS
    ]
    pool = preferred or game_odds
    earliest = sorted(
        pool,
        key=lambda row: str(row.get("inserted") or ""),
    )[0]
    return _normalize_odds_dict(earliest)


def _consensus_game_odds(
    odds: list[dict[str, Any]],
) -> dict[str, Any] | None:
    game_odds = [
        o
        for o in odds
        if isinstance(o, dict)
        and str(o.get("type") or "").lower() == "game"
        and o.get("spread_home") is not None
        and o.get("total") is not None
    ]
    if not game_odds:
        game_odds = [
            o
            for o in odds
            if isinstance(o, dict)
            and str(o.get("type") or "").lower() == "game"
        ]
    if not game_odds:
        return None

    for book_id in PREFERRED_BOOK_IDS:
        preferred = [
            o for o in game_odds if _as_int(o.get("book_id")) == book_id
        ]
        if preferred:
            preferred = sorted(
                preferred,
                key=lambda row: str(row.get("inserted") or ""),
                reverse=True,
            )
            return _normalize_odds_dict(preferred[0])

    return _median_odds(game_odds)


def _median_odds(odds: list[dict[str, Any]]) -> dict[str, Any]:
    def med(key: str) -> float | None:
        values = [
            float(row[key])
            for row in odds
            if row.get(key) is not None
        ]
        if not values:
            return None
        return float(statistics.median(values))

    sample = sorted(
        odds,
        key=lambda row: str(row.get("inserted") or ""),
        reverse=True,
    )[0]
    return {
        "spread_home": med("spread_home"),
        "spread_away": med("spread_away"),
        "total": med("total"),
        "ml_home": med("ml_home"),
        "ml_away": med("ml_away"),
        "spread_home_line": med("spread_home_line"),
        "over": med("over"),
        "under": med("under"),
        "book_id": sample.get("book_id"),
        "inserted": sample.get("inserted")
        or datetime.now(timezone.utc).isoformat(),
        "type": "game",
    }


def _normalize_odds_dict(odds: dict[str, Any]) -> dict[str, Any]:
    return {
        "spread_home": _as_float(odds.get("spread_home")),
        "spread_away": _as_float(odds.get("spread_away")),
        "total": _as_float(odds.get("total")),
        "ml_home": _as_float(odds.get("ml_home")),
        "ml_away": _as_float(odds.get("ml_away")),
        "spread_home_line": _as_float(odds.get("spread_home_line")),
        "over": _as_float(odds.get("over")),
        "under": _as_float(odds.get("under")),
        "book_id": _as_int(odds.get("book_id")),
        "inserted": odds.get("inserted"),
        "type": odds.get("type") or "game",
    }


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_abbr(
    value: Any,
    *,
    aliases: dict[str, str] | None = None,
) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    mapping = aliases if aliases is not None else ABBR_ALIASES
    return mapping.get(text, text)


def canonical_abbr(
    value: Any,
    *,
    league: LeagueId | str = "ncaaf",
) -> str | None:
    """Public helper: normalize a provider abbr to dim_team form."""

    config = get_league(league)
    return _clean_abbr(value, aliases=config.abbr_aliases)
