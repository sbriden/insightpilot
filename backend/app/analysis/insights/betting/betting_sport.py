"""
Sport configuration for the Sports Betting product.

NFL reads fantasy_football (nflverse).
CFB reads college_football (sportsdataverse).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.canonical.cfb.schema import COLLEGE_SCHEMA
from app.canonical.schema import FANTASY_SCHEMA


SPORT_NFL = "NFL"
SPORT_CFB = "CFB"

SUPPORTED_SPORTS = frozenset({SPORT_NFL, SPORT_CFB})


@dataclass(frozen=True)
class BettingSportConfig:
    id: str
    league: str
    schema: str
    source_label: str
    source_note: str
    slate_prefix: str
    label_sport: str
    league_avg_ppg: float
    has_opening_lines: bool
    has_injury_context: bool
    has_epa_features: bool


_SPORTS: dict[str, BettingSportConfig] = {
    SPORT_NFL: BettingSportConfig(
        id=SPORT_NFL,
        league=SPORT_NFL,
        schema=FANTASY_SCHEMA,
        source_label="nflverse_schedules",
        source_note=(
            "Market lines are nflverse schedule snapshots "
            "(not live multi-book sportsbook feeds). "
            "InsightPilot projection = market baseline + "
            "model residual (where the market is likely "
            "wrong). Residuals come from confidence-shrunk "
            "opponent-adjusted team-strength disagreement "
            "(including strength of schedule) plus "
            "situational injury / calibration layers."
        ),
        slate_prefix="nfl",
        label_sport="NFL",
        league_avg_ppg=22.5,
        has_opening_lines=True,
        has_injury_context=True,
        has_epa_features=True,
    ),
    SPORT_CFB: BettingSportConfig(
        id=SPORT_CFB,
        league=SPORT_CFB,
        schema=COLLEGE_SCHEMA,
        source_label="sportsdataverse_cfb",
        source_note=(
            "Market lines come from sportsdataverse CFB "
            "betting snapshots plus ScoresAndOdds live/"
            "opening odds. InsightPilot projection = market "
            "baseline + model residual from points/yards/"
            "plays team strength with strength-of-schedule "
            "scaling. Injury context is not yet available "
            "for College Football."
        ),
        slate_prefix="cfb",
        label_sport="CFB",
        league_avg_ppg=28.0,
        has_opening_lines=True,
        has_injury_context=False,
        has_epa_features=False,
    ),
}


def normalize_betting_sport(sport: str | None) -> str:
    raw = str(sport or SPORT_NFL).strip().upper()
    if raw in {"COLLEGE", "NCAAF", "NCAA", "COLLEGE_FOOTBALL"}:
        return SPORT_CFB
    if raw in SUPPORTED_SPORTS:
        return raw
    raise ValueError(
        f"Unsupported betting sport '{sport}'. "
        f"Use one of: {', '.join(sorted(SUPPORTED_SPORTS))}."
    )


def resolve_betting_sport(
    sport: str | None = None,
) -> BettingSportConfig:
    return _SPORTS[normalize_betting_sport(sport)]


def resolve_current_season(sport_config: BettingSportConfig) -> int:
    from datetime import datetime, timezone

    from sqlalchemy import text

    from app.database import engine

    # Prefer DB schedule season — avoids slow sportsdataverse /
    # nflreadpy imports on every weeks/slate request.
    try:
        with engine.connect() as connection:
            db_season = connection.execute(
                text(
                    f"""
                    SELECT MAX(season)
                    FROM {sport_config.schema}.dim_game
                    """
                )
            ).scalar()
            if db_season is not None:
                return int(db_season)
    except Exception:
        pass

    if sport_config.id == SPORT_CFB:
        try:
            from sportsdataverse.cfb import most_recent_cfb_season

            return int(most_recent_cfb_season())
        except Exception:
            return datetime.now(timezone.utc).year

    try:
        import nflreadpy as nfl

        return int(nfl.get_current_season())
    except Exception:
        return datetime.now(timezone.utc).year


def sport_payload(sport_config: BettingSportConfig) -> dict[str, Any]:
    return {
        "sport": sport_config.id,
        "league": sport_config.league,
        "source": sport_config.source_label,
    }
