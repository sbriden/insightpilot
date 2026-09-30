"""
Player Snapshot — deterministic Player Overview header.

Built from engine outputs (player_fantasy_profile + fantasy_signal)
plus identity/injury joins. Assessment text is templated from scores
and signal types — not freeform LLM prose.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


ASSESSMENT_BANDS: tuple[tuple[float, str], ...] = (
    (75.0, "Elite"),
    (60.0, "Strong"),
    (45.0, "Solid"),
    (30.0, "Cautious"),
    (0.0, "Weak"),
)

# Player Overview search is for fantasy roster positions,
# including team Defense / Special Teams (DEF).
FANTASY_SEARCH_POSITIONS = frozenset(
    {
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "PK",
        "FB",
        "HB",
        "DEF",
        "DST",
    }
)

# Positions stored on dim_player (team defenses are synthesized).
FANTASY_SKILL_POSITIONS = frozenset(
    {
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "PK",
        "FB",
        "HB",
    }
)


def is_fantasy_search_position(
    position: Any,
) -> bool:
    value = str(position or "").strip().upper()
    if not value:
        return False
    # Handle values like "WR/RB" or "RB-WR".
    tokens = [
        token
        for token in value.replace("-", "/").split("/")
        if token
    ]
    return any(
        token in FANTASY_SEARCH_POSITIONS
        for token in tokens
    )


def overall_assessment_label(
    fantasy_value_score: float | None,
) -> str:
    if fantasy_value_score is None:
        return "Insufficient data"
    score = float(fantasy_value_score)
    for threshold, label in ASSESSMENT_BANDS:
        if score >= threshold:
            return label
    return "Weak"


def assessment_score_for_position(
    *,
    position: str | None,
    fantasy_value_score: float | None,
    fppg: float | None = None,
    fantasy_points: float | None = None,
    games: int | None = None,
) -> float | None:
    """
    Map production into the 0–100 assessment scale.

    Kickers score fewer fantasy points per game than skill
    positions, so stale / skill-tuned profile scores read as
    "Weak" for every kicker. Prefer season pace for K/PK.
    """

    pos = str(position or "").strip().upper()
    if pos in {"K", "PK"}:
        pace = _num(fppg)
        if pace is None:
            points = _num(fantasy_points)
            if points is not None:
                if games is not None and int(games) > 0:
                    pace = points / float(games)
                else:
                    pace = points
        if pace is None:
            return fantasy_value_score
        # ~8 FPPG → Solid, ~10 → Strong, ~11+ → Elite
        return min(100.0, max(0.0, float(pace) * 7.0))
    return fantasy_value_score


def overall_assessment_for_player(
    *,
    position: str | None,
    fantasy_value_score: float | None,
    fppg: float | None = None,
    fantasy_points: float | None = None,
    games: int | None = None,
) -> str:
    return overall_assessment_label(
        assessment_score_for_position(
            position=position,
            fantasy_value_score=fantasy_value_score,
            fppg=fppg,
            fantasy_points=fantasy_points,
            games=games,
        )
    )


def _season_production_score(
    *,
    position: str | None,
    fppg: float | None,
) -> float | None:
    """Map season FPPG onto the 0–100 production scale."""

    pace = _num(fppg)
    if pace is None:
        return None
    pos = str(position or "").strip().upper()
    multiplier = 6.0 if pos in {"K", "PK"} else 3.0
    return max(0.0, min(100.0, float(pace) * multiplier))


def _mean_profile_score(
    profiles: list[dict[str, Any]],
    field: str,
) -> float | None:
    values: list[float] = []
    for row in profiles:
        value = _num(row.get(field))
        if value is not None:
            values.append(float(value))
    if not values:
        return None
    return sum(values) / float(len(values))


def _select_profile_for_snapshot(
    profiles: list[dict[str, Any]],
    *,
    season: int | None,
    week: int | None,
) -> dict[str, Any]:
    """
    Choose the profile week for signals / matchup context.

    Prefer the latest week with opportunity filled (same rule as
    the player list) so sparse upcoming weeks do not wipe season
    context. Fall back to production, then absolute latest week.
    """

    if not profiles:
        return {}

    scoped = profiles
    if season is not None:
        matched = []
        for row in profiles:
            try:
                if int(row.get("season")) == int(season):
                    matched.append(row)
            except (TypeError, ValueError):
                continue
        if matched:
            scoped = matched

    if week is not None:
        for row in scoped:
            try:
                if int(row.get("week")) == int(week):
                    return row
            except (TypeError, ValueError):
                continue

    def sort_key(row: dict[str, Any]) -> tuple:
        try:
            week_value = int(row.get("week") or 0)
        except (TypeError, ValueError):
            week_value = 0
        has_opp = 0 if _num(row.get("opportunity_score")) is None else 1
        has_prod = 0 if _num(row.get("production_score")) is None else 1
        return (has_opp, has_prod, week_value)

    return max(scoped, key=sort_key)


def _seasonize_profile_scores(
    profile: dict[str, Any],
    *,
    position: str | None,
    season_stats: dict[str, Any] | None,
    season_profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Align displayed production / opportunity / value with season
    fantasy points so Compare and Overview match season totals.

    Single-game profile weeks can otherwise invert rankings when
    one player had a hot game and the other has missing opportunity
    on the absolute latest week.
    """

    out = dict(profile or {})
    season_fppg = None
    if isinstance(season_stats, dict):
        season_fppg = _num(season_stats.get("fppg"))

    season_production = _season_production_score(
        position=position,
        fppg=season_fppg,
    )
    if season_production is not None:
        out["production_score"] = season_production

    profiles = list(season_profiles or [])
    if profiles:
        avg_opportunity = _mean_profile_score(
            profiles,
            "opportunity_score",
        )
        if avg_opportunity is not None:
            out["opportunity_score"] = avg_opportunity
        elif _num(out.get("opportunity_score")) is None:
            # Keep null only when no week has opportunity.
            pass
        for field in (
            "efficiency_score",
            "trend_score",
            "matchup_score",
            "environment_score",
            "risk_score",
        ):
            if _num(out.get(field)) is None:
                avg = _mean_profile_score(profiles, field)
                if avg is not None:
                    out[field] = avg

    try:
        from app.canonical.analytics.player_fantasy_profile import (
            _fantasy_value_score,
        )
    except Exception:
        return out

    recomputed = _fantasy_value_score(
        production=_num(out.get("production_score")),
        opportunity=_num(out.get("opportunity_score")),
        efficiency=_num(out.get("efficiency_score")),
        trend=_num(out.get("trend_score")),
        matchup=_num(out.get("matchup_score")),
        environment=_num(out.get("environment_score")),
        risk=_num(out.get("risk_score")),
    )
    if recomputed is not None:
        out["fantasy_value_score"] = recomputed
    return out


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _depth_chart_label(
    position: str | None,
    depth_order: int | None,
    *,
    depth_position: str | None = None,
) -> str | None:
    label_position = (
        (position or depth_position or "").strip().upper()
        or None
    )
    if not label_position or depth_order is None:
        return None
    return f"{label_position}{int(depth_order)}"


def _parse_depth_order(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(number)


def _depth_chart_for_player(
    player_id: str,
    *,
    position: str | None = None,
) -> dict[str, Any]:
    """
    Latest fantasy-relevant depth rank for one player.

    Returns depth_order / depth_position / depth_chart (e.g. RB1).
    """

    pid = str(player_id or "").strip()
    empty = {
        "depth_order": None,
        "depth_position": None,
        "depth_chart": None,
    }
    if not pid:
        return empty

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return empty

    params: dict[str, Any] = {"player_id": pid}
    position_filter = str(position or "").strip().upper() or None
    if position_filter:
        params["position"] = position_filter

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    WITH latest_season AS (
                      SELECT MAX(season) AS season
                      FROM {FANTASY_SCHEMA}.fact_depth_chart
                      WHERE season IS NOT NULL
                    ),
                    {_depth_chart_bounds_cte(schema=FANTASY_SCHEMA)}
                    SELECT
                      d.position AS depth_position,
                      d.depth_order
                    FROM {FANTASY_SCHEMA}.fact_depth_chart d
                    INNER JOIN latest_season ls
                      ON d.season = ls.season
                    INNER JOIN bounds b
                      ON TRUE
                    WHERE d.player_id = :player_id
                      AND d.depth_order IS NOT NULL
                      AND UPPER(COALESCE(d.position, '')) IN (
                        'QB', 'RB', 'WR', 'TE', 'FB', 'HB', 'K', 'PK'
                      )
                      AND (
                        (
                          b.week IS NOT NULL
                          AND d.week = b.week
                        )
                        OR (
                          b.week IS NULL
                          AND (
                            b.effective_date IS NULL
                            OR d.effective_date = b.effective_date
                          )
                        )
                      )
                    ORDER BY
                      CASE
                        WHEN :position IS NULL THEN 2
                        WHEN UPPER(d.position) = :position THEN 0
                        WHEN UPPER(d.position) IN ('HB', 'FB')
                          AND :position = 'RB' THEN 1
                        WHEN UPPER(d.position) = 'PK'
                          AND :position = 'K' THEN 1
                        ELSE 2
                      END,
                      d.depth_order ASC NULLS LAST
                    LIMIT 1
                    """
                ),
                connection,
                params={
                    "player_id": pid,
                    "position": position_filter,
                },
            )
    except Exception:
        return empty

    if frame.empty:
        return empty

    row = frame.iloc[0]
    depth_position = (
        str(row.get("depth_position")).strip().upper()
        if row.get("depth_position") is not None
        else None
    )
    depth_order = _parse_depth_order(row.get("depth_order"))
    return {
        "depth_order": depth_order,
        "depth_position": depth_position,
        "depth_chart": _depth_chart_label(
            position_filter,
            depth_order,
            depth_position=depth_position,
        ),
    }


def _depth_position_aliases(position: str | None) -> list[str]:
    group = str(position or "").strip().upper()
    if not group:
        return []
    if group == "RB":
        return ["RB", "HB", "FB"]
    if group == "HB":
        return ["HB", "RB", "FB"]
    if group == "FB":
        return ["FB", "RB", "HB"]
    if group == "K":
        return ["K", "PK"]
    if group == "PK":
        return ["PK", "K"]
    return [group]


def _depth_chart_bounds_cte(
    *,
    schema: str,
    team_predicate: str = "",
) -> str:
    """
    SQL CTEs that pick a depth-chart week with real coverage.

    ``MAX(week)`` alone can land on sparse placeholder / offseason
    weeks (e.g. week 22 with a few hundred rows) and drop active
    roster depth for almost everyone. Prefer the most recent week
    whose row count is at least half of the busiest week (and at
    least 50 rows), then fall back to the busiest week, then to
    effective_date matching.
    """

    team_filter = f"\n        {team_predicate}" if team_predicate else ""
    return f"""
                    week_counts AS (
                      SELECT
                        d.week,
                        COUNT(*)::int AS n
                      FROM {schema}.fact_depth_chart d
                      INNER JOIN latest_season ls
                        ON d.season = ls.season
                      WHERE d.week IS NOT NULL
                        AND d.depth_order IS NOT NULL
                        {team_filter}
                      GROUP BY d.week
                    ),
                    bounds AS (
                      SELECT
                        COALESCE(
                          (
                            SELECT MAX(wc.week)
                            FROM week_counts wc
                            WHERE wc.n >= GREATEST(
                              50,
                              COALESCE(
                                (
                                  SELECT CAST(MAX(n) * 0.5 AS int)
                                  FROM week_counts
                                ),
                                0
                              )
                            )
                          ),
                          (
                            SELECT wc.week
                            FROM week_counts wc
                            ORDER BY wc.n DESC, wc.week DESC
                            LIMIT 1
                          )
                        ) AS week,
                        (
                          SELECT MAX(d.effective_date)
                          FROM {schema}.fact_depth_chart d
                          INNER JOIN latest_season ls
                            ON d.season = ls.season
                          WHERE 1 = 1
                            {team_filter}
                        ) AS effective_date
                    )
    """


def _team_position_depth_chart(
    *,
    team_id: str | None,
    position: str | None,
    highlight_player_id: str | None = None,
) -> dict[str, Any]:
    """
    Latest depth chart for one team at the player's position group.
    """

    empty = {
        "position": (
            str(position or "").strip().upper() or None
        ),
        "season": None,
        "week": None,
        "as_of": None,
        "players": [],
    }
    tid = str(team_id or "").strip()
    aliases = _depth_position_aliases(position)
    if not tid or not aliases:
        return empty

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return empty

    position_params = {
        f"pos_{index}": value
        for index, value in enumerate(aliases)
    }
    position_sql = ", ".join(
        f":pos_{index}" for index in range(len(aliases))
    )
    params: dict[str, Any] = {
        "team_id": tid,
        **position_params,
    }

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    WITH latest_season AS (
                      SELECT COALESCE(
                        (
                          SELECT MAX(season)
                          FROM {FANTASY_SCHEMA}.fact_depth_chart
                          WHERE team_id = :team_id
                            AND season IS NOT NULL
                        ),
                        (
                          SELECT MAX(season)
                          FROM {FANTASY_SCHEMA}.fact_depth_chart
                          WHERE season IS NOT NULL
                        )
                      ) AS season
                    ),
                    {_depth_chart_bounds_cte(
                        schema=FANTASY_SCHEMA,
                        team_predicate="AND d.team_id = :team_id",
                    )}
                    SELECT DISTINCT ON (d.player_id)
                      d.position,
                      d.depth_order,
                      d.role,
                      d.season,
                      d.week,
                      d.effective_date,
                      p.player_id,
                      p.name
                    FROM {FANTASY_SCHEMA}.fact_depth_chart d
                    INNER JOIN latest_season ls
                      ON d.season = ls.season
                    INNER JOIN bounds b
                      ON TRUE
                    INNER JOIN {FANTASY_SCHEMA}.dim_player p
                      ON p.player_id = d.player_id
                    WHERE d.team_id = :team_id
                      AND d.depth_order IS NOT NULL
                      AND UPPER(COALESCE(d.position, '')) IN (
                        {position_sql}
                      )
                      AND (
                        (
                          b.week IS NOT NULL
                          AND d.week = b.week
                        )
                        OR (
                          b.week IS NULL
                          AND (
                            b.effective_date IS NULL
                            OR d.effective_date = b.effective_date
                          )
                        )
                      )
                    ORDER BY
                      d.player_id,
                      d.depth_order ASC NULLS LAST
                    """
                ),
                connection,
                params=params,
            )
    except Exception:
        return empty

    if frame.empty:
        return empty

    players: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in frame.to_dict(orient="records"):
        player_id = str(row.get("player_id") or "").strip()
        if not player_id or player_id in seen:
            continue
        seen.add(player_id)
        depth_order = _parse_depth_order(row.get("depth_order"))
        depth_position = (
            str(row.get("position")).strip().upper()
            if row.get("position") is not None
            else None
        )
        players.append(
            {
                "player_id": player_id,
                "name": (
                    str(row.get("name")).strip()
                    if row.get("name") is not None
                    else None
                ),
                "depth_order": depth_order,
                "depth_position": depth_position,
                "depth_chart": _depth_chart_label(
                    depth_position,
                    depth_order,
                ),
                "role": (
                    str(row.get("role")).strip()
                    if row.get("role") is not None
                    else None
                ),
                "is_current_player": (
                    highlight_player_id is not None
                    and player_id == str(highlight_player_id).strip()
                ),
            }
        )

    players.sort(
        key=lambda item: (
            item.get("depth_order") is None,
            item.get("depth_order")
            if item.get("depth_order") is not None
            else 99,
            str(item.get("name") or ""),
        )
    )

    first = frame.iloc[0]
    as_of = first.get("effective_date")
    return {
        "position": aliases[0],
        "season": _parse_depth_order(first.get("season")),
        "week": _parse_depth_order(first.get("week")),
        "as_of": (
            str(as_of)[:10] if as_of is not None else None
        ),
        "players": players,
    }


def build_assessment_narrative(
    *,
    profile: dict[str, Any] | None,
    signals: list[dict[str, Any]],
) -> str:
    """
    Compose a short assessment from profile scores and emitted signals.

    Sentences are gated on the same metrics the signal engine uses.
    """

    profile = profile or {}
    opportunity = _num(profile.get("opportunity_score"))
    production = _num(profile.get("production_score"))
    efficiency = _num(profile.get("efficiency_score"))
    trend = _num(profile.get("trend_score"))
    risk = _num(profile.get("risk_score"))

    signal_types = {
        str(item.get("signal_type") or "").upper()
        for item in signals
    }

    sentences: list[str] = []

    if opportunity is not None and opportunity >= 70:
        if trend is not None and trend >= 60:
            sentences.append(
                "Usage remains elite and has increased "
                "over the past three weeks."
            )
        else:
            sentences.append(
                "Usage remains elite based on current "
                "opportunity score."
            )
    elif opportunity is not None and opportunity >= 55:
        if trend is not None and trend >= 60:
            sentences.append(
                "Opportunity is solid and trending up "
                "over the past three weeks."
            )
        elif trend is not None and trend <= 35:
            sentences.append(
                "Opportunity is average but trending down "
                "over the past three weeks."
            )

    if (
        opportunity is not None
        and production is not None
        and opportunity - production >= 15
    ):
        sentences.append(
            "Production has lagged behind opportunity, "
            "suggesting potential positive regression."
        )
    elif (
        production is not None
        and opportunity is not None
        and production - opportunity >= 15
    ):
        sentences.append(
            "Production is outpacing opportunity, "
            "raising regression risk if usage does not hold."
        )
    elif "BUY_LOW" in signal_types:
        sentences.append(
            "Engine buy-low signal: opportunity and efficiency "
            "exceed recent production."
        )

    if "OPPORTUNITY_SURGE" in signal_types and not any(
        "increased over the past three weeks" in sentence
        for sentence in sentences
    ):
        sentences.append(
            "Opportunity surge signal: recent usage trend "
            "is elevated versus baseline."
        )

    if "BREAKOUT_CANDIDATE" in signal_types and not any(
        "positive regression" in sentence
        for sentence in sentences
    ):
        sentences.append(
            "Breakout signal: elevated opportunity and trend "
            "with room for production to catch up."
        )

    if efficiency is not None and efficiency >= 70 and risk is not None and risk <= 35:
        sentences.append(
            "Efficiency is strong with limited injury/usage risk."
        )
    elif risk is not None and risk >= 65:
        sentences.append(
            "Risk score is elevated — check injury and "
            "usage volatility before locking a lineup."
        )

    if "SIT" in signal_types or "OPPORTUNITY_DECLINE" in signal_types:
        sentences.append(
            "Near-term signals favor caution on weekly start "
            "decisions."
        )
    elif "START" in signal_types:
        sentences.append(
            "Start signal is active for the current week."
        )

    if not sentences:
        value = _num(profile.get("fantasy_value_score"))
        if value is not None:
            return (
                f"Fantasy value score is {value:.0f} from "
                "production, opportunity, efficiency, trend, "
                "matchup, environment, and risk."
            )
        if signals:
            primary = str(
                signals[0].get("signal_type") or "signal"
            ).replace("_", " ").title()
            return (
                f"Primary engine signal: {primary} "
                f"(strength {float(signals[0].get('signal_strength') or 0):.0f})."
            )
        return (
            "Not enough profile or signal evidence yet "
            "for a grounded assessment."
        )

    return " ".join(sentences[:3])


def build_key_takeaways(
    *,
    profile: dict[str, Any] | None,
    signals: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Structured Key Takeaways for the Snapshot UI.

    Each item: type, headline, body. Sourced from the same
    engine gates as the narrative — InsightPilot interpretation.
    """

    narrative = build_assessment_narrative(
        profile=profile,
        signals=signals,
    )
    profile = profile or {}
    production = _num(profile.get("production_score"))
    opportunity = _num(profile.get("opportunity_score"))
    value = _num(profile.get("fantasy_value_score"))
    trend = _num(profile.get("trend_score"))

    takeaways: list[dict[str, str]] = []
    sentences = [
        part.strip()
        for part in narrative.replace(". ", ".\n").split("\n")
        if part.strip()
    ]
    # Prefer sentence-split on periods for multi-sentence narratives.
    if len(sentences) <= 1 and "." in narrative:
        sentences = [
            f"{part.strip()}."
            for part in narrative.split(".")
            if part.strip()
        ]

    type_hints = (
        ("usage", "Usage", ("usage", "opportunity", "workload")),
        ("trend", "Trend", ("trend", "surge", "increased", "down")),
        ("performance", "Performance", ("production", "regression", "efficiency")),
        ("availability", "Availability", ("injury", "risk", "availability")),
        ("recommendation", "Recommendation", ("start", "sit", "buy-low", "breakout")),
    )

    for sentence in sentences[:4]:
        lower = sentence.lower()
        insight_type = "insight"
        headline = "InsightPilot analysis"
        for type_id, label, keywords in type_hints:
            if any(keyword in lower for keyword in keywords):
                insight_type = type_id
                headline = label
                break
        # Short headline from first clause
        short = sentence.split(",")[0].strip()
        if len(short) > 8 and len(short) < 72:
            headline = short.rstrip(".")
        takeaways.append(
            {
                "type": insight_type,
                "headline": headline,
                "body": sentence if sentence.endswith(".") else f"{sentence}.",
                "source": "insightpilot",
            }
        )

    if not takeaways and value is not None:
        takeaways.append(
            {
                "type": "performance",
                "headline": overall_assessment_label(value),
                "body": (
                    f"Fantasy value score is {value:.0f} from "
                    "production, opportunity, and supporting factors."
                ),
                "source": "insightpilot",
            }
        )

    # Ensure score context appears when we have room.
    if (
        len(takeaways) < 3
        and production is not None
        and opportunity is not None
    ):
        takeaways.append(
            {
                "type": "performance",
                "headline": "Production vs opportunity",
                "body": (
                    f"Production score {production:.0f} with "
                    f"opportunity score {opportunity:.0f}"
                    + (
                        f"; trend {trend:.0f}."
                        if trend is not None
                        else "."
                    )
                ),
                "source": "insightpilot",
            }
        )

    return takeaways[:4]


def build_recommendation(
    *,
    profile: dict[str, Any] | None,
    signals: list[dict[str, Any]],
    assessment: str,
) -> dict[str, str] | None:
    profile = profile or {}
    value = _num(profile.get("fantasy_value_score"))
    production = _num(profile.get("production_score"))
    opportunity = _num(profile.get("opportunity_score"))
    primary = signals[0] if signals else None
    primary_type = (
        str(primary.get("signal_type") or "").upper()
        if primary
        else ""
    )

    if value is None and not primary_type:
        return None

    if assessment in {"Elite", "Strong"}:
        headline = "Premium fantasy asset"
    elif assessment == "Solid":
        headline = "Viable roster contributor"
    elif assessment == "Cautious":
        headline = "Situational / monitor closely"
    elif assessment == "Weak":
        headline = "Limited fantasy outlook"
    else:
        headline = "Insufficient data for a recommendation"

    reasons: list[str] = []
    if production is not None and opportunity is not None:
        reasons.append(
            f"Production {production:.0f} with opportunity "
            f"{opportunity:.0f}."
        )
    if primary_type:
        reasons.append(
            f"Primary signal: {primary_type.replace('_', ' ').title()}."
        )

    return {
        "headline": headline,
        "body": " ".join(reasons)
        or "Based on current InsightPilot profile scores.",
        "source": "insightpilot",
    }


def _parse_source_ids(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            import json

            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _espn_headshot_url(source_ids: Any) -> str | None:
    ids = _parse_source_ids(source_ids)
    espn_id = ids.get("espn_id")
    if espn_id is None:
        return None
    text = str(espn_id).strip()
    if not text or not text.replace(".", "", 1).isdigit():
        # allow pure digits; strip trailing .0
        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]
        elif not text.isdigit():
            return None
    return (
        "https://a.espncdn.com/i/headshots/nfl/"
        f"players/full/{text}.png"
    )


def _player_age(birth_date: Any) -> int | None:
    if birth_date is None:
        return None
    try:
        from datetime import date, datetime

        if hasattr(birth_date, "year"):
            born = birth_date
        else:
            born = datetime.strptime(
                str(birth_date)[:10], "%Y-%m-%d"
            ).date()
        today = date.today()
        return (
            today.year
            - born.year
            - (
                (today.month, today.day)
                < (born.month, born.day)
            )
        )
    except Exception:
        return None


def build_player_snapshots_for_frame(
    signal_rows: list[dict[str, Any]],
    *,
    player_id_key: str = "player_id",
    season: int | None = None,
    week: int | None = None,
    max_players: int = 8,
) -> list[dict[str, Any]]:
    """
    Enrich top signal players into Player Snapshot rows.

    Loads profile, identity, injury, and opponent from the
    canonical fantasy layer when available.
    """

    if not signal_rows:
        return []

    by_player: dict[str, list[dict[str, Any]]] = {}
    for row in signal_rows:
        player_id = str(
            row.get(player_id_key)
            or row.get("player_id")
            or ""
        ).strip()
        if not player_id:
            continue
        by_player.setdefault(player_id, []).append(row)

    ranked_players = sorted(
        by_player.items(),
        key=lambda item: max(
            float(signal.get("signal_strength") or signal.get("_strength") or 0)
            for signal in item[1]
        ),
        reverse=True,
    )[:max_players]

    if not ranked_players:
        return []

    seasons = [season] if season is not None else None
    try:
        from app.canonical.analytics.player_fantasy_profile import (
            get_player_fantasy_profile,
        )
        from app.canonical.dim_player import get_dim_player
        from app.canonical.dim_team import get_dim_team
        from app.canonical.fact_injury import get_fact_injury

        profiles = get_player_fantasy_profile(seasons=seasons)
        players = get_dim_player()
        teams = get_dim_team()
        injuries = get_fact_injury(seasons=seasons)
    except Exception:
        profiles = None
        players = None
        teams = None
        injuries = None

    profile_lookup: dict[tuple[str, int, int], dict[str, Any]] = {}
    if profiles is not None and not profiles.empty:
        for row in profiles.to_dict(orient="records"):
            pid = str(row.get("player_id") or "").strip()
            try:
                s = int(row.get("season"))
                w = int(row.get("week"))
            except (TypeError, ValueError):
                continue
            if pid:
                profile_lookup[(pid, s, w)] = row

    player_lookup: dict[str, dict[str, Any]] = {}
    if players is not None and not players.empty:
        for row in players.to_dict(orient="records"):
            pid = str(row.get("player_id") or "").strip()
            if pid:
                player_lookup[pid] = row

    team_abbr: dict[str, str] = {}
    if teams is not None and not teams.empty:
        for row in teams.to_dict(orient="records"):
            tid = str(row.get("team_id") or "").strip()
            abbr = row.get("team_abbreviation")
            if tid and abbr:
                team_abbr[tid] = str(abbr)

    injury_lookup: dict[tuple[str, int, int], dict[str, Any]] = {}
    if injuries is not None and not injuries.empty:
        for row in injuries.to_dict(orient="records"):
            pid = str(row.get("player_id") or "").strip()
            try:
                s = int(row.get("season"))
                w = int(row.get("week"))
            except (TypeError, ValueError):
                continue
            if pid:
                injury_lookup[(pid, s, w)] = row

    snapshots: list[dict[str, Any]] = []
    injury_period = _current_injury_report_period()
    injury_season = (
        injury_period[0]
        if injury_period is not None
        else season
    )
    injury_week = (
        injury_period[1]
        if injury_period is not None
        else week
    )

    for player_id, player_signals in ranked_players:
        sample = player_signals[0]
        try:
            s = int(
                season
                if season is not None
                else sample.get("season")
            )
            w = int(
                week
                if week is not None
                else sample.get("week")
            )
        except (TypeError, ValueError):
            s = season
            w = week

        identity = player_lookup.get(player_id, {})
        profile = (
            profile_lookup.get((player_id, int(s), int(w)), {})
            if s is not None and w is not None
            else {}
        )
        injury = {}
        if (
            injury_season is not None
            and injury_week is not None
        ):
            injury = injury_lookup.get(
                (player_id, int(injury_season), int(injury_week)),
                {},
            )

        team_id = identity.get("current_team_id") or injury.get("team_id")
        team_label = (
            team_abbr.get(str(team_id), str(team_id))
            if team_id
            else None
        )
        injury_type = _list_injury_type(injury.get("injury_type"))
        injury_status = _list_injury_status(
            injury.get("game_status"),
            injury.get("practice_status"),
        )

        normalized_signals = []
        for signal in player_signals:
            normalized_signals.append(
                {
                    "signal_type": (
                        signal.get("signal_type")
                        or signal.get("_signal_type")
                    ),
                    "signal_strength": (
                        signal.get("signal_strength")
                        or signal.get("_strength")
                    ),
                    "confidence": (
                        signal.get("confidence")
                        or signal.get("_confidence")
                    ),
                    "direction": signal.get("direction"),
                    "supporting_metrics": signal.get(
                        "supporting_metrics"
                    ),
                }
            )

        snapshots.append(
            build_player_snapshot(
                player_id=player_id,
                name=identity.get("name"),
                position=identity.get("position"),
                team=team_label,
                season=s,
                week=w,
                status=identity.get("status"),
                injury_type=injury_type,
                injury_status=injury_status,
                profile=profile,
                signals=normalized_signals,
                include_performance=False,
            )
        )

    return snapshots


def build_player_snapshot(
    *,
    player_id: str,
    name: str | None = None,
    position: str | None = None,
    team: str | None = None,
    season: int | None = None,
    week: int | None = None,
    status: str | None = None,
    injury_type: str | None = None,
    injury_status: str | None = None,
    profile: dict[str, Any] | None = None,
    signals: list[dict[str, Any]] | None = None,
    include_performance: bool = True,
    birth_date: Any = None,
    rookie_season: Any = None,
    headshot_url: str | None = None,
    espn_id: str | None = None,
    season_stats: dict[str, Any] | None = None,
    position_rank: int | None = None,
    overall_rank: int | None = None,
    position_pool_size: int | None = None,
    overall_pool_size: int | None = None,
    replacements: list[dict[str, Any]] | None = None,
    ownership: float | None = None,
    depth_order: int | None = None,
    depth_chart: str | None = None,
    position_depth_chart: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or {}
    signals = list(signals or [])
    signals_sorted = sorted(
        signals,
        key=lambda item: (
            float(item.get("signal_strength") or 0),
            float(item.get("confidence") or 0),
        ),
        reverse=True,
    )

    season_fppg = None
    season_points = None
    season_games = None
    if isinstance(season_stats, dict):
        season_fppg = _num(season_stats.get("fppg"))
        season_points = _num(season_stats.get("fantasy_points"))
        games_raw = season_stats.get("games")
        try:
            season_games = (
                int(games_raw) if games_raw is not None else None
            )
        except (TypeError, ValueError):
            season_games = None

    # Align production with season FPPG when available so Compare
    # and Overview do not invert players based on one profile week.
    if season_fppg is not None:
        profile = _seasonize_profile_scores(
            profile,
            position=position,
            season_stats=season_stats,
            season_profiles=None,
        )

    value_score = _num(profile.get("fantasy_value_score"))
    assessment = overall_assessment_for_player(
        position=position,
        fantasy_value_score=value_score,
        fppg=season_fppg,
        fantasy_points=season_points,
        games=season_games,
    )
    narrative = build_assessment_narrative(
        profile=profile,
        signals=signals_sorted,
    )
    takeaways = build_key_takeaways(
        profile=profile,
        signals=signals_sorted,
    )
    recommendation = build_recommendation(
        profile=profile,
        signals=signals_sorted,
        assessment=assessment,
    )

    primary = signals_sorted[0] if signals_sorted else None

    age = _player_age(birth_date)
    experience = None
    try:
        if rookie_season is not None and season is not None:
            experience = max(
                0,
                int(season) - int(rookie_season) + 1,
            )
    except (TypeError, ValueError):
        experience = None

    if depth_chart is None and depth_order is not None:
        depth_chart = _depth_chart_label(position, depth_order)

    snapshot = {
        "player_id": player_id,
        "name": name or player_id,
        "position": position,
        "depth_order": depth_order,
        "depth_chart": depth_chart,
        "position_depth_chart": position_depth_chart or {
            "position": (
                str(position or "").strip().upper() or None
            ),
            "season": None,
            "week": None,
            "as_of": None,
            "players": [],
        },
        "team": team,
        "status": status,
        "injury_type": injury_type,
        "injury_status": injury_status,
        "season": season,
        "week": week,
        "birth_date": (
            str(birth_date)[:10]
            if birth_date is not None
            else None
        ),
        "age": age,
        "rookie_season": (
            int(rookie_season)
            if rookie_season is not None
            else None
        ),
        "experience_years": experience,
        "headshot_url": headshot_url,
        "espn_id": espn_id,
        "overall_assessment": assessment,
        "assessment_narrative": narrative,
        "key_takeaways": takeaways,
        "recommendation": recommendation,
        "fantasy_value_score": value_score,
        "production_score": _num(profile.get("production_score")),
        "opportunity_score": _num(profile.get("opportunity_score")),
        "efficiency_score": _num(profile.get("efficiency_score")),
        "trend_score": _num(profile.get("trend_score")),
        "matchup_score": _num(profile.get("matchup_score")),
        "environment_score": _num(profile.get("environment_score")),
        "risk_score": _num(profile.get("risk_score")),
        "season_stats": season_stats or None,
        "position_rank": position_rank,
        "overall_rank": overall_rank,
        "position_pool_size": position_pool_size,
        "overall_pool_size": overall_pool_size,
        "ownership": ownership,
        "replacements": replacements or [],
        "primary_signal_type": (
            primary.get("signal_type") if primary else None
        ),
        "primary_signal_strength": (
            _num(primary.get("signal_strength"))
            if primary
            else None
        ),
        "primary_signal_confidence": (
            _num(primary.get("confidence"))
            if primary
            else None
        ),
        "signal_types": [
            str(item.get("signal_type"))
            for item in signals_sorted
            if item.get("signal_type")
        ],
        "evidence_source": "player_fantasy_profile+fantasy_signal",
        "data_updated": None,
    }

    if include_performance:
        from app.analysis.insights.player_performance import (
            build_performance_and_opportunity,
        )

        snapshot["performance"] = build_performance_and_opportunity(
            player_id,
            position=position,
            season=season,
            week=week,
        )

    return snapshot


def _normalize_list_position(value: str | None) -> str | None:
    if not value:
        return None
    key = str(value).strip().upper()
    if key in {"DST", "D/ST", "D-ST", "TEAM DEF", "DEFENSE"}:
        return "DEF"
    if key == "PK":
        return "K"
    return key


def _dst_points_allowed_sql(*, alias: str = "d") -> str:
    """ESPN-style points-allowed fantasy scoring for team defenses."""

    return f"""
        CASE
          WHEN {alias}.points_allowed IS NULL THEN 0
          WHEN {alias}.points_allowed <= 0 THEN 10
          WHEN {alias}.points_allowed <= 6 THEN 7
          WHEN {alias}.points_allowed <= 13 THEN 4
          WHEN {alias}.points_allowed <= 20 THEN 1
          WHEN {alias}.points_allowed <= 27 THEN 0
          WHEN {alias}.points_allowed <= 34 THEN -1
          ELSE -4
        END
    """


_DST_SCORE_CACHE: dict[int, dict[str, dict[str, Any]]] = {}


def _defense_player_id(team_abbr: str) -> str:
    from app.canonical.ids import make_player_id

    return make_player_id(
        f"fantasy_dst:{str(team_abbr).strip().upper()}"
    )


def resolve_team_defense(
    player_id: str,
) -> dict[str, Any] | None:
    """
    Map a synthetic defense player_id back to dim_team.
    """

    pid = str(player_id or "").strip()
    if not pid:
        return None
    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      team_id,
                      team_name,
                      team_abbreviation,
                      conference,
                      division
                    FROM {FANTASY_SCHEMA}.dim_team
                    WHERE team_abbreviation IS NOT NULL
                    """
                ),
                connection,
            )
    except Exception:
        return None

    for row in frame.to_dict(orient="records"):
        abbr = str(row.get("team_abbreviation") or "").strip().upper()
        if not abbr:
            continue
        try:
            if _defense_player_id(abbr) == pid:
                return {
                    "player_id": pid,
                    "team_id": row.get("team_id"),
                    "team_name": row.get("team_name"),
                    "team": abbr,
                    "conference": row.get("conference"),
                    "division": row.get("division"),
                    "name": (
                        f"{str(row.get('team_name') or abbr).strip()} D/ST"
                    ),
                    "position": "DEF",
                }
        except ValueError:
            continue
    return None


def _dst_season_scores(
    season: int,
) -> dict[str, dict[str, Any]]:
    """
    Season totals for team defenses using points-allowed +
    sack / turnover / TD / block scoring from nflverse team_stats.
    """

    cached = _DST_SCORE_CACHE.get(int(season))
    if cached is not None:
        return cached

    from app.analysis.insights.fantasy_scoring import (
        dst_game_fantasy_points,
        dst_touchdowns,
    )

    scores: dict[str, dict[str, Any]] = {}
    try:
        import nflreadpy as nfl
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine

        team_stats = nfl.load_team_stats([int(season)])
        if hasattr(team_stats, "to_pandas"):
            team_stats = team_stats.to_pandas()

        # Map nflverse game_id → our game may differ; team_stats uses
        # nflverse game_id. Prefer matching via week+team when needed.
        points_by_week: dict[tuple[str, int], float] = {}
        with engine.connect() as connection:
            weekly = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      t.team_abbreviation AS team,
                      d.week,
                      AVG(d.points_allowed) AS points_allowed
                    FROM {FANTASY_SCHEMA}.fact_defensive_game d
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team t
                      ON t.team_id = d.defensive_team_id
                    WHERE d.season = :season
                      AND d.week IS NOT NULL
                    GROUP BY t.team_abbreviation, d.week
                    """
                ),
                connection,
                params={"season": int(season)},
            )
        for row in weekly.to_dict(orient="records"):
            abbr = str(row.get("team") or "").strip().upper()
            try:
                week = int(row.get("week"))
            except (TypeError, ValueError):
                continue
            if abbr:
                points_by_week[(abbr, week)] = row.get(
                    "points_allowed"
                )

        for row in team_stats.to_dict(orient="records"):
            abbr = str(row.get("team") or "").strip().upper()
            if not abbr:
                continue
            try:
                week = int(row.get("week"))
            except (TypeError, ValueError):
                week = None
            points_allowed = None
            # team_stats game_id is nflverse; fact uses ip_game_*.
            # Match on week + team.
            if week is not None:
                points_allowed = points_by_week.get((abbr, week))
            game_row = {
                "points_allowed": points_allowed,
                "sacks": row.get("def_sacks"),
                "interceptions": row.get("def_interceptions"),
                "fumbles_recovered": row.get(
                    "fumble_recovery_opp"
                ),
                "safeties": row.get("def_safeties"),
                "defensive_tds": row.get("def_tds"),
                "special_teams_tds": row.get(
                    "special_teams_tds"
                ),
                "fumble_recovery_tds": row.get(
                    "fumble_recovery_tds"
                ),
                "pt_return_tds": row.get("pt_return_tds"),
                "def_2pt_made": row.get("def_2pt_made"),
                "def_punt_blocks": row.get("def_punt_blocks"),
                "def_fg_blocks": row.get("def_fg_blocks"),
                "def_pat_blocks": row.get("def_pat_blocks"),
                "pt_blocked": row.get("pt_blocked"),
                "fg_blocked": row.get("fg_blocked"),
                "pat_blocked": row.get("pat_blocked"),
            }
            game_points = dst_game_fantasy_points(game_row)
            current = scores.setdefault(
                abbr,
                {
                    "fantasy_points": 0.0,
                    "games": 0,
                    "sacks": 0.0,
                    "interceptions": 0.0,
                    "fumbles_recovered": 0.0,
                    "defensive_tds": 0.0,
                    "safeties": 0.0,
                    "blocked_kicks": 0.0,
                    "points_allowed_avg": [],
                    "game_log": [],
                },
            )
            current["fantasy_points"] = (
                float(current["fantasy_points"]) + float(game_points)
            )
            current["games"] = int(current["games"]) + 1
            current["sacks"] = float(current["sacks"]) + float(
                row.get("def_sacks") or 0
            )
            current["interceptions"] = float(
                current["interceptions"]
            ) + float(row.get("def_interceptions") or 0)
            current["fumbles_recovered"] = float(
                current["fumbles_recovered"]
            ) + float(row.get("fumble_recovery_opp") or 0)
            current["defensive_tds"] = float(
                current["defensive_tds"]
            ) + float(dst_touchdowns(game_row))
            current["safeties"] = float(
                current["safeties"]
            ) + float(row.get("def_safeties") or 0)
            blocked = (
                float(row.get("def_punt_blocks") or 0)
                + float(row.get("def_fg_blocks") or 0)
                + float(row.get("def_pat_blocks") or 0)
                + float(row.get("pt_blocked") or 0)
                + float(row.get("fg_blocked") or 0)
                + float(row.get("pat_blocked") or 0)
            )
            current["blocked_kicks"] = (
                float(current["blocked_kicks"]) + blocked
            )
            if points_allowed is not None:
                current["points_allowed_avg"].append(
                    float(points_allowed)
                )
            opponent = (
                str(
                    row.get("opponent_team")
                    or row.get("opponent")
                    or row.get("opp")
                    or ""
                ).strip().upper()
                or None
            )
            current["game_log"].append(
                {
                    "week": week,
                    "opponent": opponent,
                    "fantasy_points": game_points,
                    "points_allowed": (
                        float(points_allowed)
                        if points_allowed is not None
                        else None
                    ),
                    "sacks": float(row.get("def_sacks") or 0),
                    "interceptions": float(
                        row.get("def_interceptions") or 0
                    ),
                    "fumbles_recovered": float(
                        row.get("fumble_recovery_opp") or 0
                    ),
                }
            )
    except Exception:
        scores = {}

    for abbr, payload in scores.items():
        games = int(payload.get("games") or 0)
        total = float(payload.get("fantasy_points") or 0.0)
        payload["fantasy_points"] = round(total, 1)
        payload["fppg"] = (
            round(total / games, 1) if games else None
        )
        allowed_vals = payload.pop("points_allowed_avg", [])
        payload["points_allowed_avg"] = (
            round(sum(allowed_vals) / len(allowed_vals), 1)
            if allowed_vals
            else None
        )
        game_log = list(payload.get("game_log") or [])
        game_log.sort(
            key=lambda item: (
                item.get("week") is None,
                -(int(item.get("week") or 0)),
            )
        )
        payload["game_log"] = game_log

    _DST_SCORE_CACHE[int(season)] = scores
    return scores


def _list_team_defenses(
    *,
    query: str = "",
    team: str | None = None,
    season: int | None = None,
    limit: int = 32,
) -> list[dict[str, Any]]:
    """
    Synthetic fantasy roster entries for each NFL team defense.
    """

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return []

    if season is None:
        try:
            import nflreadpy as nfl

            season = int(nfl.get_current_season())
        except Exception:
            season = None

    params: dict[str, Any] = {}
    clauses = ["t.team_abbreviation IS NOT NULL"]
    if query:
        params["needle"] = f"%{query}%"
        clauses.append(
            """
            (
              LOWER(COALESCE(t.team_name, '')) LIKE :needle
              OR LOWER(COALESCE(t.team_abbreviation, '')) LIKE :needle
              OR LOWER(COALESCE(t.team_abbreviation, '') || ' def') LIKE :needle
              OR LOWER(COALESCE(t.team_abbreviation, '') || ' d/st') LIKE :needle
              OR 'def' LIKE :needle
              OR 'dst' LIKE :needle
            )
            """
        )
    if team:
        params["team"] = str(team).strip().upper()
        clauses.append(
            "UPPER(COALESCE(t.team_abbreviation, '')) = :team"
        )
    where_sql = " AND ".join(clauses)

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                      t.team_id,
                      t.team_name,
                      t.team_abbreviation AS team
                    FROM {FANTASY_SCHEMA}.dim_team t
                    WHERE {where_sql}
                    ORDER BY t.team_abbreviation
                    """
                ),
                connection,
                params=params,
            )
    except Exception:
        return []

    scores = (
        _dst_season_scores(int(season))
        if season is not None
        else {}
    )

    defenses: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        abbr = (
            str(row.get("team") or "").strip().upper() or None
        )
        if not abbr:
            continue
        team_name = (
            str(row.get("team_name") or "").strip() or abbr
        )
        try:
            player_id = _defense_player_id(abbr)
        except ValueError:
            continue
        score = scores.get(abbr) or {}
        fantasy_points = _num(score.get("fantasy_points"))
        games = (
            int(score["games"])
            if score.get("games") is not None
            else None
        )
        defenses.append(
            {
                "player_id": player_id,
                "name": f"{team_name} D/ST",
                "position": "DEF",
                "depth_order": 1,
                "depth_chart": "DEF",
                "team": abbr,
                "status": "Active",
                "injury_type": None,
                "injury_status": None,
                "fantasy_points": fantasy_points,
                "games": games,
                "fppg": _num(score.get("fppg")),
                "production_score": None,
                "opportunity_score": None,
                "fantasy_value_score": None,
                "ownership": None,
                "overall_assessment": (
                    "Insufficient data"
                    if fantasy_points is None
                    else overall_assessment_label(
                        min(100.0, max(0.0, (fantasy_points or 0) * 4.0))
                    )
                ),
                "is_team_defense": True,
            }
        )

    defenses.sort(
        key=lambda item: (
            item.get("fantasy_points") is None,
            -(float(item.get("fantasy_points") or 0.0)),
            str(item.get("name") or ""),
        )
    )
    return defenses[: max(1, min(int(limit), 32))]


def build_team_defense_snapshot(
    player_id: str,
    *,
    season: int | None = None,
) -> dict[str, Any] | None:
    """Player-overview snapshot for a synthetic team defense."""

    defense = resolve_team_defense(player_id)
    if defense is None:
        return None

    try:
        import nflreadpy as nfl
    except Exception:
        nfl = None

    resolved_season = season
    if resolved_season is None and nfl is not None:
        try:
            resolved_season = int(nfl.get_current_season())
        except Exception:
            resolved_season = None

    score = (
        _dst_season_scores(int(resolved_season)).get(
            str(defense["team"])
        )
        if resolved_season is not None
        else None
    ) or {}

    fantasy_points = _num(score.get("fantasy_points"))
    games = score.get("games")
    fppg = _num(score.get("fppg"))
    assessment = (
        "Insufficient data"
        if fantasy_points is None
        else overall_assessment_label(
            min(100.0, max(0.0, float(fantasy_points) * 4.0))
        )
    )

    takeaways = []
    if fantasy_points is not None:
        takeaways.append(
            {
                "type": "production",
                "headline": f"{fantasy_points:.1f} fantasy points",
                "body": (
                    f"{defense['name']} has scored "
                    f"{fantasy_points:.1f} fantasy points"
                    + (
                        f" across {games} games ({fppg:.1f} PPG)."
                        if games and fppg is not None
                        else "."
                    )
                ),
                "source": "dst_scoring",
            }
        )
    if score.get("sacks"):
        takeaways.append(
            {
                "type": "pressure",
                "headline": f"{float(score['sacks']):.0f} sacks",
                "body": (
                    "Sack production is included in the "
                    "team-defense fantasy score."
                ),
                "source": "dst_scoring",
            }
        )
    turnovers = float(score.get("interceptions") or 0) + float(
        score.get("fumbles_recovered") or 0
    )
    if turnovers:
        takeaways.append(
            {
                "type": "turnovers",
                "headline": f"{turnovers:.0f} takeaways",
                "body": (
                    "Interceptions and opponent fumble recoveries "
                    "are scored as turnovers."
                ),
                "source": "dst_scoring",
            }
        )

    metrics = []
    for key, label, value in (
        ("fantasy_points", "Fantasy Pts", fantasy_points),
        ("fppg", "FPPG", fppg),
        ("sacks", "Sacks", _num(score.get("sacks"))),
        (
            "interceptions",
            "INTs",
            _num(score.get("interceptions")),
        ),
        (
            "fumbles_recovered",
            "Fum Rec",
            _num(score.get("fumbles_recovered")),
        ),
        (
            "defensive_tds",
            "Def/ST TDs",
            _num(score.get("defensive_tds")),
        ),
        (
            "points_allowed_avg",
            "Pts Allowed",
            _num(score.get("points_allowed_avg")),
        ),
    ):
        if value is None:
            continue
        metrics.append(
            {"key": key, "label": label, "value": value}
        )

    recent_games = []
    for game in list(score.get("game_log") or [])[:8]:
        week = game.get("week")
        try:
            week_int = int(week) if week is not None else None
        except (TypeError, ValueError):
            week_int = None
        if week_int is None or resolved_season is None:
            continue
        recent_games.append(
            {
                "season": int(resolved_season),
                "week": week_int,
                "label": f"Week {week_int}",
                "opponent": game.get("opponent"),
                "opponent_label": game.get("opponent"),
                "home_away": None,
                "production": {
                    "fantasy_points": game.get("fantasy_points"),
                    "points_allowed": game.get("points_allowed"),
                    "sacks": game.get("sacks"),
                    "interceptions": game.get("interceptions"),
                    "fumbles_recovered": game.get(
                        "fumbles_recovered"
                    ),
                },
                "opportunity": {},
            }
        )

    return {
        "player_id": defense["player_id"],
        "name": defense["name"],
        "position": "DEF",
        "depth_order": None,
        "depth_chart": None,
        "position_depth_chart": None,
        "team": defense["team"],
        "season": resolved_season,
        "week": None,
        "status": "Active",
        "injury_type": None,
        "injury_status": None,
        "age": None,
        "experience": None,
        "headshot_url": None,
        "ownership": None,
        "overall_assessment": assessment,
        "assessment_summary": (
            f"{defense['name']} is tracked as a fantasy "
            "team defense / special teams unit."
        ),
        "key_takeaways": takeaways,
        "recommendation": {
            "headline": "Team defense outlook",
            "body": (
                "Defense scoring uses points allowed, sacks, "
                "takeaways, defensive/ST touchdowns, safeties, "
                "2-pt returns, and blocked kicks."
            ),
            "source": "dst_scoring",
        },
        "season_stats": {
            "season": resolved_season,
            "games": int(games or 0),
            "fantasy_points": fantasy_points,
            "metrics": metrics,
            "fppg": fppg,
            "sacks": _num(score.get("sacks")),
            "interceptions": _num(score.get("interceptions")),
            "fumbles_recovered": _num(
                score.get("fumbles_recovered")
            ),
            "defensive_tds": _num(score.get("defensive_tds")),
            "points_allowed_avg": _num(
                score.get("points_allowed_avg")
            ),
        },
        "profile": {},
        "signals": [],
        "performance": {
            "position_group": "DEF",
            "production_fields": [
                {"key": "points_allowed", "label": "Pts Allowed"},
                {"key": "sacks", "label": "Sacks"},
                {"key": "interceptions", "label": "INTs"},
                {"key": "fumbles_recovered", "label": "Fum Rec"},
                {"key": "fantasy_points", "label": "Fantasy Pts"},
            ],
            "opportunity_fields": [],
            "recent_games": recent_games,
            "season_totals": {
                "fantasy_points": fantasy_points,
                "games": games,
            },
        },
        "is_team_defense": True,
    }


def build_team_defense_tab_payload(
    player_id: str,
    *,
    season: int | None = None,
    tab: str = "stats",
) -> dict[str, Any] | None:
    """
    Minimal Stats / Usage / Matchups / News payload for a
    synthetic team defense so those tabs do not 404.
    """

    defense = resolve_team_defense(player_id)
    if defense is None:
        return None

    try:
        import nflreadpy as nfl
    except Exception:
        nfl = None

    resolved_season = season
    if resolved_season is None and nfl is not None:
        try:
            resolved_season = int(nfl.get_current_season())
        except Exception:
            resolved_season = None

    score = (
        _dst_season_scores(int(resolved_season)).get(
            str(defense["team"])
        )
        if resolved_season is not None
        else None
    ) or {}

    season_value = (
        int(resolved_season) if resolved_season is not None else 0
    )
    seasons = [season_value] if season_value else []

    key = str(tab or "stats").strip().lower()
    if key == "stats":
        games = int(score.get("games") or 0)
        fantasy_points = _num(score.get("fantasy_points"))
        fppg = _num(score.get("fppg"))
        return {
            "player_id": defense["player_id"],
            "name": defense["name"],
            "position": "DEF",
            "position_group": "DEF",
            "team": defense["team"],
            "season": season_value,
            "scoring": "dst",
            "available_seasons": seasons,
            "is_team_defense": True,
            "fantasy_production": {
                "fantasy_points": fantasy_points,
                "fppg": fppg,
                "games": games,
                "games_context": (
                    f"{games} game{'s' if games != 1 else ''}"
                    if games
                    else None
                ),
                "position_rank_label": None,
            },
            "production_breakdown": [
                {
                    "title": "Defense / ST",
                    "metrics": [
                        {
                            "key": key,
                            "label": label,
                            "value": value,
                        }
                        for key, label, value in (
                            (
                                "sacks",
                                "Sacks",
                                _num(score.get("sacks")),
                            ),
                            (
                                "interceptions",
                                "INTs",
                                _num(score.get("interceptions")),
                            ),
                            (
                                "fumbles_recovered",
                                "Fum Rec",
                                _num(
                                    score.get(
                                        "fumbles_recovered"
                                    )
                                ),
                            ),
                            (
                                "defensive_tds",
                                "Def/ST TDs",
                                _num(
                                    score.get("defensive_tds")
                                ),
                            ),
                            (
                                "points_allowed_avg",
                                "Pts Allowed",
                                _num(
                                    score.get(
                                        "points_allowed_avg"
                                    )
                                ),
                            ),
                        )
                        if value is not None
                    ],
                }
            ],
            "volume": [],
            "efficiency": [],
            "consistency": None,
            "season_history": [],
            "game_log": [
                {
                    "season": season_value,
                    "week": game.get("week"),
                    "opponent": game.get("opponent"),
                    "fantasy_points": game.get("fantasy_points"),
                    "points_allowed": game.get("points_allowed"),
                    "sacks": game.get("sacks"),
                    "interceptions": game.get("interceptions"),
                }
                for game in list(score.get("game_log") or [])
            ],
            "empty_message": None,
            "data_note": (
                "Team-defense scoring: points allowed brackets, "
                "sacks, takeaways, TDs, safeties, 2-pt returns, "
                "and blocked kicks."
            ),
        }
    if key == "usage":
        return {
            "player_id": defense["player_id"],
            "name": defense["name"],
            "position": "DEF",
            "position_group": "DEF",
            "team": defense["team"],
            "season": season_value,
            "period": "full_season",
            "period_games": 0,
            "scoring": "dst",
            "available_seasons": seasons,
            "sample_size": 0,
            "role_opportunity": [],
            "chart_metrics": [],
            "weekly_usage": [],
            "signals": [],
            "is_team_defense": True,
            "empty_message": (
                f"{defense['name']} does not have player usage "
                "trends. Use Snapshot or Stats for team-defense "
                "fantasy production."
            ),
        }
    if key == "matchups":
        return {
            "player_id": defense["player_id"],
            "name": defense["name"],
            "position": "DEF",
            "position_group": "DEF",
            "team": defense["team"],
            "season": season_value,
            "view": "next_8",
            "scoring": "dst",
            "available_seasons": seasons,
            "signals": [],
            "upcoming_matchups": [],
            "timeline": [],
            "is_team_defense": True,
            "empty_message": (
                f"Opponent matchup context for "
                f"{defense['name']} is coming soon."
            ),
        }
    if key == "news":
        return {
            "player_id": defense["player_id"],
            "name": defense["name"],
            "position": "DEF",
            "team": defense["team"],
            "season": season_value,
            "lookback": "last_30d",
            "available_seasons": seasons,
            "featured": None,
            "important_developments": [],
            "developments": [],
            "counts": {
                "total": 0,
                "high": 0,
                "moderate": 0,
                "low": 0,
            },
            "is_team_defense": True,
            "empty_message": (
                f"No curated news items for "
                f"{defense['name']} yet."
            ),
        }
    return {
        "player_id": defense["player_id"],
        "name": defense["name"],
        "position": "DEF",
        "team": defense["team"],
        "season": season_value,
        "is_team_defense": True,
    }


def list_fantasy_players(
    *,
    query: str = "",
    position: str | None = None,
    team: str | None = None,
    limit: int = 500,
    season: int | None = None,
    scoring: str | None = "ppr",
) -> list[dict[str, Any]]:
    """
    List fantasy roster positions for the overview table.

    Includes skill players from dim_player plus synthetic team
    Defense / Special Teams (DEF) entries.
    """

    from app.analysis.insights.fantasy_scoring import (
        fantasy_points_sql,
        normalize_scoring,
    )

    scoring_key = normalize_scoring(scoring)
    q = str(query or "").strip().lower()
    position_filter = _normalize_list_position(
        str(position or "").strip().upper() or None
    )
    team_filter = str(team or "").strip().upper() or None
    resolved_limit = max(1, min(int(limit), 2000))

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return []

    if season is None:
        try:
            import nflreadpy as nfl

            season = int(nfl.get_current_season())
        except Exception:
            season = None

    include_defenses = True
    if position_filter:
        if position_filter not in FANTASY_SEARCH_POSITIONS:
            return []
        if position_filter == "DEF":
            return _list_team_defenses(
                query=q,
                team=team_filter,
                season=season,
                limit=min(resolved_limit, 32),
            )
        include_defenses = False

    allowed = sorted(FANTASY_SKILL_POSITIONS)
    if position_filter:
        if position_filter == "K":
            allowed = ["K", "PK"]
        else:
            allowed = [position_filter]

    position_params = {
        f"pos_{index}": value
        for index, value in enumerate(allowed)
    }
    position_sql = ", ".join(
        f":pos_{index}" for index in range(len(allowed))
    )

    params: dict[str, Any] = {
        "limit": resolved_limit,
        **position_params,
    }
    clauses = [f"p.position IN ({position_sql})"]

    if q:
        params["needle"] = f"%{q}%"
        clauses.append(
            """
            (
              LOWER(COALESCE(p.name, '')) LIKE :needle
              OR LOWER(COALESCE(p.position, '')) LIKE :needle
              OR LOWER(COALESCE(t.team_abbreviation, '')) LIKE :needle
            )
            """
        )

    if team_filter:
        params["team"] = team_filter
        clauses.append(
            "UPPER(COALESCE(t.team_abbreviation, '')) = :team"
        )

    where_sql = " AND ".join(clauses)

    season_clause = ""
    profile_season_clause = ""
    ownership_season_clause = ""
    if season is not None:
        params["season"] = int(season)
        season_clause = "AND g.season = :season"
        profile_season_clause = "AND pf.season = :season"
        ownership_season_clause = "AND m.season = :season"
    else:
        season_clause = """
            AND g.season = (
              SELECT MAX(season)
              FROM {schema}.fact_player_game
            )
        """.format(schema=FANTASY_SCHEMA)
        profile_season_clause = """
            AND pf.season = (
              SELECT MAX(season)
              FROM {schema}.player_fantasy_profile
            )
        """.format(schema=FANTASY_SCHEMA)
        ownership_season_clause = """
            AND m.season = (
              SELECT MAX(season)
              FROM {schema}.fact_market
              WHERE ownership IS NOT NULL
            )
        """.format(schema=FANTASY_SCHEMA)

    points_expr = fantasy_points_sql(scoring_key, alias="g")

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                        p.player_id,
                        p.name,
                        p.position,
                        p.status,
                        t.team_abbreviation AS team,
                        pts.fantasy_points,
                        pts.games,
                        pts.fppg,
                        prof.production_score,
                        prof.opportunity_score,
                        prof.fantasy_value_score,
                        own.ownership,
                        depth.depth_position,
                        depth.depth_order,
                        inj.injury_type,
                        inj.game_status AS injury_game_status,
                        inj.practice_status AS injury_practice_status
                    FROM {FANTASY_SCHEMA}.dim_player p
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team t
                      ON t.team_id = p.current_team_id
                    LEFT JOIN (
                      SELECT
                        g.player_id,
                        ROUND(SUM({points_expr})::numeric, 1)
                          AS fantasy_points,
                        COUNT(*)::int AS games,
                        ROUND(
                          (
                            SUM({points_expr})
                            / NULLIF(COUNT(*), 0)
                          )::numeric,
                          1
                        ) AS fppg
                      FROM {FANTASY_SCHEMA}.fact_player_game g
                      WHERE 1 = 1
                        {season_clause}
                      GROUP BY g.player_id
                    ) pts
                      ON pts.player_id = p.player_id
                    LEFT JOIN (
                      SELECT DISTINCT ON (pf.player_id)
                        pf.player_id,
                        pf.production_score,
                        pf.opportunity_score,
                        pf.fantasy_value_score
                      FROM {FANTASY_SCHEMA}.player_fantasy_profile pf
                      WHERE 1 = 1
                        {profile_season_clause}
                      ORDER BY
                        pf.player_id,
                        (pf.opportunity_score IS NULL) ASC,
                        pf.week DESC
                    ) prof
                      ON prof.player_id = p.player_id
                    LEFT JOIN (
                      SELECT DISTINCT ON (m.player_id)
                        m.player_id,
                        m.ownership
                      FROM {FANTASY_SCHEMA}.fact_market m
                      WHERE m.ownership IS NOT NULL
                        {ownership_season_clause}
                      ORDER BY
                        m.player_id,
                        m.week DESC NULLS LAST,
                        m.updated_at DESC NULLS LAST
                    ) own
                      ON own.player_id = p.player_id
                    LEFT JOIN (
                      WITH latest_season AS (
                        SELECT MAX(season) AS season
                        FROM {FANTASY_SCHEMA}.fact_depth_chart
                        WHERE season IS NOT NULL
                      ),
                      {_depth_chart_bounds_cte(schema=FANTASY_SCHEMA)},
                      latest_depth AS (
                        SELECT
                          d.player_id,
                          d.position,
                          d.depth_order
                        FROM {FANTASY_SCHEMA}.fact_depth_chart d
                        INNER JOIN latest_season ls
                          ON d.season = ls.season
                        INNER JOIN bounds b
                          ON TRUE
                        WHERE d.depth_order IS NOT NULL
                          AND UPPER(COALESCE(d.position, '')) IN (
                            'QB', 'RB', 'WR', 'TE', 'FB', 'HB', 'K', 'PK'
                          )
                          AND (
                            (
                              b.week IS NOT NULL
                              AND d.week = b.week
                            )
                            OR (
                              b.week IS NULL
                              AND (
                                b.effective_date IS NULL
                                OR d.effective_date = b.effective_date
                              )
                            )
                          )
                      )
                      SELECT DISTINCT ON (ld.player_id)
                        ld.player_id,
                        ld.position AS depth_position,
                        ld.depth_order
                      FROM latest_depth ld
                      INNER JOIN {FANTASY_SCHEMA}.dim_player dp
                        ON dp.player_id = ld.player_id
                      ORDER BY
                        ld.player_id,
                        CASE
                          WHEN UPPER(ld.position) = UPPER(
                            COALESCE(dp.position, '')
                          ) THEN 0
                          WHEN UPPER(ld.position) IN ('HB', 'FB')
                            AND UPPER(COALESCE(dp.position, '')) = 'RB'
                            THEN 1
                          WHEN UPPER(ld.position) = 'PK'
                            AND UPPER(COALESCE(dp.position, '')) = 'K'
                            THEN 1
                          ELSE 2
                        END,
                        ld.depth_order ASC NULLS LAST
                    ) depth
                      ON depth.player_id = p.player_id
                    LEFT JOIN (
                      WITH current_season AS (
                        SELECT MAX(season) AS season
                        FROM {FANTASY_SCHEMA}.fact_injury
                        WHERE season IS NOT NULL
                      ),
                      week_counts AS (
                        SELECT i.week, COUNT(*)::int AS n
                        FROM {FANTASY_SCHEMA}.fact_injury i
                        INNER JOIN current_season cs
                          ON i.season = cs.season
                        WHERE i.week IS NOT NULL
                        GROUP BY i.week
                      ),
                      chosen AS (
                        SELECT
                          cs.season,
                          COALESCE(
                            (
                              SELECT wc.week
                              FROM week_counts wc
                              WHERE wc.n >= 50
                              ORDER BY wc.week DESC
                              LIMIT 1
                            ),
                            (
                              SELECT MAX(wc.week)
                              FROM week_counts wc
                            )
                          ) AS week
                        FROM current_season cs
                      )
                      SELECT
                        i.player_id,
                        i.injury_type,
                        i.game_status,
                        i.practice_status
                      FROM {FANTASY_SCHEMA}.fact_injury i
                      INNER JOIN chosen c
                        ON i.season = c.season
                       AND i.week = c.week
                    ) inj
                      ON inj.player_id = p.player_id
                    WHERE {where_sql}
                    ORDER BY
                      (depth.depth_order IS NULL) ASC,
                      CASE
                        WHEN depth.depth_order IS NOT NULL
                          AND depth.depth_order <= 2
                        THEN 0
                        ELSE 1
                      END ASC,
                      depth.depth_order ASC NULLS LAST,
                      pts.fantasy_points DESC NULLS LAST,
                      p.name
                    LIMIT :limit
                    """
                ),
                connection,
                params=params,
            )
    except Exception:
        return []

    players: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        player_id = str(row.get("player_id") or "").strip()
        if not player_id:
            continue
        fantasy_points = _num(row.get("fantasy_points"))
        value_score = _num(row.get("fantasy_value_score"))
        production_score = _num(row.get("production_score"))
        opportunity_score = _num(row.get("opportunity_score"))
        position = (
            str(row.get("position")).strip()
            if row.get("position") is not None
            else None
        )
        if position == "PK":
            position = "K"
        depth_order_raw = row.get("depth_order")
        depth_order = _parse_depth_order(depth_order_raw)

        depth_position = (
            str(row.get("depth_position")).strip().upper()
            if row.get("depth_position") is not None
            else None
        )
        depth_chart = _depth_chart_label(
            position,
            depth_order,
            depth_position=depth_position,
        )

        players.append(
            {
                "player_id": player_id,
                "name": str(row.get("name") or player_id).strip(),
                "position": position,
                "depth_order": depth_order,
                "depth_chart": depth_chart,
                "team": (
                    str(row.get("team")).strip()
                    if row.get("team") is not None
                    else None
                ),
                "status": (
                    str(row.get("status")).strip()
                    if row.get("status") is not None
                    else None
                ),
                "injury_type": _list_injury_type(
                    row.get("injury_type")
                ),
                "injury_status": _list_injury_status(
                    row.get("injury_game_status"),
                    row.get("injury_practice_status"),
                ),
                "fantasy_points": fantasy_points,
                "games": (
                    int(row["games"])
                    if row.get("games") is not None
                    and _num(row.get("games")) is not None
                    else None
                ),
                "fppg": _num(row.get("fppg")),
                "projection": None,
                "scoring": scoring_key,
                "production_score": production_score,
                "opportunity_score": opportunity_score,
                "fantasy_value_score": value_score,
                "ownership": _num(row.get("ownership")),
                "overall_assessment": overall_assessment_for_player(
                    position=position,
                    fantasy_value_score=value_score,
                    fppg=_num(row.get("fppg")),
                    fantasy_points=fantasy_points,
                    games=(
                        int(row["games"])
                        if row.get("games") is not None
                        and _num(row.get("games")) is not None
                        else None
                    ),
                ),
            }
        )

    _attach_list_projections(
        players,
        season=season,
        scoring=scoring_key,
    )

    if include_defenses:
        players.extend(
            _list_team_defenses(
                query=q,
                team=team_filter,
                season=season,
                limit=32,
            )
        )
        players.sort(
            key=lambda item: (
                item.get("depth_order") is None,
                0
                if (
                    item.get("depth_order") is not None
                    and int(item.get("depth_order") or 99) <= 2
                )
                else 1,
                int(item.get("depth_order") or 99),
                item.get("fantasy_points") is None,
                -(float(item.get("fantasy_points") or 0.0)),
                str(item.get("name") or ""),
            )
        )
        return players[:resolved_limit]

    return players


def _attach_list_projections(
    players: list[dict[str, Any]],
    *,
    season: int | None,
    scoring: str,
) -> None:
    """
    Attach InsightPilot projections for overview.

    Uses the same pipeline as DFS: calibrate season FPPG, then
    apply current-week opponent matchup / environment scaling.
    Scoring format only changes reception points (QBs match DFS
    when overview is on PPR).
    """

    if not players or season is None:
        return

    try:
        from app.analysis.insights.dfs.projection_baselines import (
            load_player_projection_baselines,
        )
        from app.analysis.insights.dfs.projection_calibration import (
            calibrate_projection,
        )
        from app.analysis.insights.dfs.slate import (
            _load_week_context_maps,
            _normalize_position,
            _opponent_adjusted_projection,
            _resolve_player_week_context,
            _resolve_week,
            _slate_windows_for_week,
            _team_abbr,
        )
    except Exception:
        return

    season_value = int(season)
    try:
        baselines = load_player_projection_baselines(
            season=season_value,
            player_ids=[
                str(player.get("player_id") or "")
                for player in players
                if player.get("player_id")
            ],
            scoring=scoring,
        )
    except Exception:
        baselines = {}

    week_value = _resolve_week(None, season=season_value)
    week_context = _load_week_context_maps(
        season=season_value,
        week=int(week_value),
    )
    opponents: dict[str, str] = {}
    try:
        windows = _slate_windows_for_week(
            season=season_value,
            week=int(week_value),
        )
        for bucket in windows.values():
            for team, opp in (bucket.get("opponents") or {}).items():
                if team and opp:
                    opponents[str(team)] = str(opp)
    except Exception:
        opponents = {}

    for player in players:
        raw = _num(player.get("fppg"))
        if raw is None:
            games = _num(player.get("games"))
            total = _num(player.get("fantasy_points"))
            if total is not None and games and games > 0:
                raw = float(total) / float(games)
        try:
            depth_order = (
                int(player.get("depth_order"))
                if player.get("depth_order") is not None
                else None
            )
        except (TypeError, ValueError):
            depth_order = None
        # Depth-chart starters / backups with no season sample still
        # need a projection (seed at 0 so calibration uses priors).
        if raw is None:
            if depth_order is not None and depth_order <= 2:
                raw = 0.0
            else:
                continue
        baseline = baselines.get(
            str(player.get("player_id") or "")
        ) or {}
        position = _normalize_position(player.get("position"))
        try:
            calibrated = calibrate_projection(
                raw_projection=float(raw),
                position=position,
                current_season_games=int(
                    _num(player.get("games")) or 0
                ),
                historical_baseline=_num(
                    baseline.get("historical_baseline")
                ),
                historical_games=int(
                    baseline.get("historical_games") or 0
                ),
                historical_p90=_num(baseline.get("historical_p90")),
                opportunity_score=_num(
                    player.get("opportunity_score")
                ),
                depth_order=depth_order,
                roster_status=(
                    str(player.get("status"))
                    if player.get("status") is not None
                    else None
                ),
            )
            base = float(calibrated.insightpilot_projection)
            team = _team_abbr(player.get("team"))
            opponent = (
                opponents.get(team) if team else None
            )
            context = _resolve_player_week_context(
                player_id=str(player.get("player_id") or ""),
                opponent=opponent,
                week_context=week_context,
            )
            adjusted = _opponent_adjusted_projection(
                base=base,
                position=position,
                context=context,
                has_opponent=bool(opponent),
            )
            player["projection"] = round(
                float(adjusted["projection"]),
                1,
            )
        except Exception:
            player["projection"] = round(float(raw), 1)


def _list_injury_type(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text_value = str(value).strip()
    if not text_value or text_value.lower() == "nan":
        return None
    lowered = text_value.lower()
    if lowered.startswith("not injury related"):
        return None
    return text_value


def _list_injury_status(
    game_status: Any,
    practice_status: Any,
) -> str | None:
    def _clean(raw: Any) -> str | None:
        if raw is None:
            return None
        try:
            if pd.isna(raw):
                return None
        except (TypeError, ValueError):
            pass
        text = str(raw).strip()
        if not text or text.lower() == "nan":
            return None
        return text

    return _clean(game_status) or _clean(practice_status)


def _current_injury_report_period() -> tuple[int, int] | None:
    """
    Latest injury-report (season, week) to treat as current.

    Prefers the most recent week in the latest season that has a
    full-sized report (>= 50 rows). Falls back to that season's
    max week when reports are still sparse.
    """

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    sql = f"""
        WITH current_season AS (
          SELECT MAX(season) AS season
          FROM {FANTASY_SCHEMA}.fact_injury
          WHERE season IS NOT NULL
        ),
        week_counts AS (
          SELECT i.week, COUNT(*)::int AS n
          FROM {FANTASY_SCHEMA}.fact_injury i
          INNER JOIN current_season cs
            ON i.season = cs.season
          WHERE i.week IS NOT NULL
          GROUP BY i.week
        ),
        chosen AS (
          SELECT
            cs.season,
            COALESCE(
              (
                SELECT wc.week
                FROM week_counts wc
                WHERE wc.n >= 50
                ORDER BY wc.week DESC
                LIMIT 1
              ),
              (SELECT MAX(wc.week) FROM week_counts wc)
            ) AS week
          FROM current_season cs
        )
        SELECT season, week
        FROM chosen
        WHERE season IS NOT NULL
          AND week IS NOT NULL
    """
    try:
        with engine.connect() as connection:
            row = connection.execute(text(sql)).mappings().first()
    except Exception:
        return None
    if not row:
        return None
    try:
        return int(row["season"]), int(row["week"])
    except (TypeError, ValueError, KeyError):
        return None


def _injury_fields_for_period(
    injuries: Any,
    *,
    season: int | None,
    week: int | None,
) -> tuple[str | None, str | None]:
    """
    Return (injury_type, injury_status) for one report period.
    """

    if (
        injuries is None
        or getattr(injuries, "empty", True)
        or season is None
        or week is None
    ):
        return None, None

    injury: dict[str, Any] = {}
    for row in injuries.to_dict(orient="records"):
        try:
            if (
                int(row.get("season")) == int(season)
                and int(row.get("week")) == int(week)
            ):
                injury = row
                break
        except (TypeError, ValueError):
            continue

    injury_type = _list_injury_type(injury.get("injury_type"))
    injury_status = _list_injury_status(
        injury.get("game_status"),
        injury.get("practice_status"),
    )
    return injury_type, injury_status


def search_players(
    query: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Search fantasy roster entries by name / position / team.

    Includes skill players and synthetic team defenses (DEF).
    """

    q = str(query or "").strip().lower()
    if len(q) < 2:
        return []

    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return []

    position_list = sorted(FANTASY_SKILL_POSITIONS)
    position_params = {
        f"pos_{index}": value
        for index, value in enumerate(position_list)
    }
    position_sql = ", ".join(
        f":pos_{index}" for index in range(len(position_list))
    )

    params: dict[str, Any] = {
        "needle": f"%{q}%",
        "limit": max(1, min(int(limit), 50)),
        **position_params,
    }

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                        p.player_id,
                        p.name,
                        p.position,
                        p.status,
                        p.current_team_id,
                        t.team_abbreviation
                    FROM {FANTASY_SCHEMA}.dim_player p
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team t
                      ON t.team_id = p.current_team_id
                    WHERE p.position IN ({position_sql})
                      AND (
                        LOWER(COALESCE(p.name, '')) LIKE :needle
                        OR LOWER(COALESCE(p.position, '')) LIKE :needle
                        OR LOWER(COALESCE(t.team_abbreviation, '')) LIKE :needle
                        OR LOWER(COALESCE(p.player_id, '')) LIKE :needle
                      )
                    ORDER BY
                      CASE
                        WHEN LOWER(COALESCE(p.name, '')) LIKE :prefix THEN 0
                        ELSE 1
                      END,
                      p.name
                    LIMIT :limit
                    """
                ),
                connection,
                params={
                    **params,
                    "prefix": f"{q}%",
                },
            )
    except Exception:
        # Fallback to in-memory scan if SQL path is unavailable.
        return _search_players_fallback(q, limit=limit)

    matches: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        player_id = str(row.get("player_id") or "").strip()
        if not player_id:
            continue
        position = (
            str(row.get("position")).strip()
            if row.get("position") is not None
            else None
        )
        if position == "PK":
            position = "K"
        matches.append(
            {
                "player_id": player_id,
                "name": str(row.get("name") or player_id).strip(),
                "position": position,
                "team": (
                    str(row.get("team_abbreviation")).strip()
                    if row.get("team_abbreviation") is not None
                    else None
                ),
                "status": (
                    str(row.get("status")).strip()
                    if row.get("status") is not None
                    else None
                ),
            }
        )

    remaining = max(0, int(limit) - len(matches))
    if remaining > 0:
        for defense in _list_team_defenses(query=q, limit=32):
            if remaining <= 0:
                break
            matches.append(
                {
                    "player_id": defense["player_id"],
                    "name": defense["name"],
                    "position": "DEF",
                    "team": defense.get("team"),
                    "status": defense.get("status"),
                }
            )
            remaining -= 1

    return matches[:limit]


def _search_players_fallback(
    query: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    q = str(query or "").strip().lower()
    if len(q) < 2:
        return []

    try:
        from app.canonical.dim_player import get_dim_player
        from app.canonical.dim_team import get_dim_team

        players = get_dim_player()
        teams = get_dim_team()
    except Exception:
        return []

    if players is None or players.empty:
        return []

    team_abbr: dict[str, str] = {}
    if teams is not None and not teams.empty:
        for row in teams.to_dict(orient="records"):
            tid = str(row.get("team_id") or "").strip()
            abbr = row.get("team_abbreviation")
            if tid and abbr:
                team_abbr[tid] = str(abbr)

    matches: list[dict[str, Any]] = []
    for row in players.to_dict(orient="records"):
        player_id = str(row.get("player_id") or "").strip()
        if not player_id:
            continue

        name = str(row.get("name") or "").strip()
        position = str(row.get("position") or "").strip()
        if not is_fantasy_search_position(position):
            continue

        team_id = str(row.get("current_team_id") or "").strip()
        team = team_abbr.get(team_id, team_id) if team_id else ""
        status = str(row.get("status") or "").strip()

        haystack = " ".join(
            [
                name.lower(),
                position.lower(),
                team.lower(),
                player_id.lower(),
            ]
        )
        if q not in haystack:
            continue

        matches.append(
            {
                "player_id": player_id,
                "name": name or player_id,
                "position": position or None,
                "team": team or None,
                "status": status or None,
            }
        )
        if len(matches) >= limit:
            break

    matches.sort(
        key=lambda item: (
            0 if item["name"].lower().startswith(q) else 1,
            item["name"].lower(),
        )
    )
    return matches[:limit]


def _season_stats_for_player(
    player_id: str,
    *,
    position: str | None,
    season: int | None,
) -> dict[str, Any] | None:
    if season is None:
        return None
    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    from app.analysis.insights.fantasy_scoring import (
        fantasy_points_sql,
    )
    ppr_expr = fantasy_points_sql("ppr", alias="")
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT
                        COUNT(*) AS games,
                        ROUND(SUM({ppr_expr})::numeric, 1)
                          AS fantasy_points,
                        SUM(pass_yards) AS pass_yards,
                        SUM(pass_tds) AS pass_tds,
                        SUM(interceptions) AS interceptions,
                        SUM(rush_attempts) AS rush_attempts,
                        SUM(rush_yards) AS rush_yards,
                        SUM(rush_tds) AS rush_tds,
                        SUM(targets) AS targets,
                        SUM(receptions) AS receptions,
                        SUM(receiving_yards) AS receiving_yards,
                        SUM(receiving_tds) AS receiving_tds,
                        SUM(fg_made) AS fg_made,
                        SUM(fg_att) AS fg_att,
                        SUM(fg_made_50_59) AS fg_made_50_59,
                        SUM(fg_made_60_) AS fg_made_60_,
                        SUM(pat_made) AS pat_made
                    FROM {FANTASY_SCHEMA}.fact_player_game
                    WHERE player_id = :player_id
                      AND season = :season
                    """
                ),
                connection,
                params={
                    "player_id": player_id,
                    "season": int(season),
                },
            )
    except Exception:
        return None

    if frame.empty:
        return None
    row = frame.to_dict(orient="records")[0]
    games = int(row.get("games") or 0)
    if games <= 0:
        return None

    metrics: list[dict[str, Any]] = [
        {
            "key": "fantasy_points",
            "label": "Fantasy Points",
            "value": _num(row.get("fantasy_points")),
        },
    ]
    pos = str(position or "").upper()
    if pos in {"RB", "FB", "HB"}:
        metrics.extend(
            [
                {
                    "key": "rush_yards",
                    "label": "Rushing Yards",
                    "value": _num(row.get("rush_yards")),
                },
                {
                    "key": "receptions",
                    "label": "Receptions",
                    "value": _num(row.get("receptions")),
                },
                {
                    "key": "receiving_yards",
                    "label": "Receiving Yards",
                    "value": _num(row.get("receiving_yards")),
                },
                {
                    "key": "touchdowns",
                    "label": "Touchdowns",
                    "value": _num(
                        (row.get("rush_tds") or 0)
                        + (row.get("receiving_tds") or 0)
                    ),
                },
            ]
        )
    elif pos in {"WR", "TE"}:
        metrics.extend(
            [
                {
                    "key": "targets",
                    "label": "Targets",
                    "value": _num(row.get("targets")),
                },
                {
                    "key": "receptions",
                    "label": "Receptions",
                    "value": _num(row.get("receptions")),
                },
                {
                    "key": "receiving_yards",
                    "label": "Receiving Yards",
                    "value": _num(row.get("receiving_yards")),
                },
                {
                    "key": "touchdowns",
                    "label": "Touchdowns",
                    "value": _num(row.get("receiving_tds")),
                },
            ]
        )
    elif pos == "QB":
        metrics.extend(
            [
                {
                    "key": "pass_yards",
                    "label": "Pass Yards",
                    "value": _num(row.get("pass_yards")),
                },
                {
                    "key": "pass_tds",
                    "label": "Pass TDs",
                    "value": _num(row.get("pass_tds")),
                },
                {
                    "key": "interceptions",
                    "label": "INTs",
                    "value": _num(row.get("interceptions")),
                },
                {
                    "key": "rush_yards",
                    "label": "Rush Yards",
                    "value": _num(row.get("rush_yards")),
                },
            ]
        )
    elif pos in {"K", "PK"}:
        metrics.extend(
            [
                {
                    "key": "fg_made",
                    "label": "FG Made",
                    "value": _num(row.get("fg_made")),
                },
                {
                    "key": "fg_att",
                    "label": "FG Attempts",
                    "value": _num(row.get("fg_att")),
                },
                {
                    "key": "fg_made_50_plus",
                    "label": "Made 50+",
                    "value": _num(
                        (row.get("fg_made_50_59") or 0)
                        + (row.get("fg_made_60_") or 0)
                    )
                    if (
                        row.get("fg_made_50_59") is not None
                        or row.get("fg_made_60_") is not None
                    )
                    else None,
                },
                {
                    "key": "pat_made",
                    "label": "XP Made",
                    "value": _num(row.get("pat_made")),
                },
            ]
        )

    return {
        "season": int(season),
        "games": games,
        "fantasy_points": _num(row.get("fantasy_points")),
        "fppg": (
            round(
                float(row.get("fantasy_points") or 0) / games,
                1,
            )
            if _num(row.get("fantasy_points")) is not None
            else None
        ),
        "metrics": [
            item
            for item in metrics
            if item.get("value") is not None
        ],
    }


def _ranks_for_player(
    player_id: str,
    *,
    position: str | None,
    season: int | None,
) -> dict[str, int | None]:
    empty = {
        "position_rank": None,
        "overall_rank": None,
        "position_pool_size": None,
        "overall_pool_size": None,
    }
    if season is None:
        return empty
    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return empty

    from app.analysis.insights.fantasy_scoring import (
        fantasy_points_sql,
    )
    ppr_expr = fantasy_points_sql("ppr", alias="g")
    position_list = sorted(FANTASY_SKILL_POSITIONS)
    position_params = {
        f"pos_{index}": value
        for index, value in enumerate(position_list)
    }
    position_sql = ", ".join(
        f":pos_{index}" for index in range(len(position_list))
    )
    params: dict[str, Any] = {
        "season": int(season),
        "player_id": player_id,
        **position_params,
    }
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    WITH scored AS (
                      SELECT
                        g.player_id,
                        p.position,
                        SUM({ppr_expr}) AS fantasy_points
                      FROM {FANTASY_SCHEMA}.fact_player_game g
                      JOIN {FANTASY_SCHEMA}.dim_player p
                        ON p.player_id = g.player_id
                      WHERE g.season = :season
                        AND p.position IN ({position_sql})
                      GROUP BY g.player_id, p.position
                    ),
                    ranked AS (
                      SELECT
                        player_id,
                        position,
                        fantasy_points,
                        RANK() OVER (
                          ORDER BY fantasy_points DESC
                        ) AS overall_rank,
                        RANK() OVER (
                          PARTITION BY position
                          ORDER BY fantasy_points DESC
                        ) AS position_rank,
                        COUNT(*) OVER () AS overall_pool_size,
                        COUNT(*) OVER (
                          PARTITION BY position
                        ) AS position_pool_size
                      FROM scored
                    )
                    SELECT *
                    FROM ranked
                    WHERE player_id = :player_id
                    LIMIT 1
                    """
                ),
                connection,
                params=params,
            )
    except Exception:
        return empty

    if frame.empty:
        return empty
    row = frame.to_dict(orient="records")[0]
    return {
        "position_rank": (
            int(row["position_rank"])
            if row.get("position_rank") is not None
            else None
        ),
        "overall_rank": (
            int(row["overall_rank"])
            if row.get("overall_rank") is not None
            else None
        ),
        "position_pool_size": (
            int(row["position_pool_size"])
            if row.get("position_pool_size") is not None
            else None
        ),
        "overall_pool_size": (
            int(row["overall_pool_size"])
            if row.get("overall_pool_size") is not None
            else None
        ),
    }


# Free-agent replacements: only players below this ownership %.
FREE_AGENT_OWNERSHIP_MAX = 50.0


def _replacement_candidates(
    *,
    player_id: str,
    position: str | None,
    season: int | None,
    week: int | None = None,
    limit: int = 5,
    max_ownership: float = FREE_AGENT_OWNERSHIP_MAX,
) -> list[dict[str, Any]]:
    """
    Same-position free-agent alternatives.

    Requires market ownership below ``max_ownership`` (default 50%)
    from the latest weekly ``fact_market`` row for the season.
    Ranked by fantasy value / season PPR points.
    """

    if not position or season is None:
        return []
    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return []

    from app.analysis.insights.fantasy_scoring import (
        fantasy_points_sql,
    )
    ppr_expr = fantasy_points_sql("ppr", alias="g")
    params: dict[str, Any] = {
        "season": int(season),
        "position": str(position).upper(),
        "player_id": player_id,
        "limit": max(1, min(int(limit), 10)),
        "max_ownership": float(max_ownership),
    }

    ownership_week_filter = ""
    if week is not None:
        params["week"] = int(week)
        ownership_week_filter = "AND m.week = :week"
    else:
        ownership_week_filter = """
            AND m.week = (
              SELECT MAX(m2.week)
              FROM {schema}.fact_market m2
              WHERE m2.season = :season
                AND m2.week IS NOT NULL
                AND m2.ownership IS NOT NULL
            )
        """.format(schema=FANTASY_SCHEMA)

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    WITH pts AS (
                      SELECT
                        g.player_id,
                        ROUND(SUM({ppr_expr})::numeric, 1)
                          AS fantasy_points
                      FROM {FANTASY_SCHEMA}.fact_player_game g
                      WHERE g.season = :season
                      GROUP BY g.player_id
                    ),
                    latest_profile AS (
                      SELECT DISTINCT ON (pf.player_id)
                        pf.player_id,
                        pf.fantasy_value_score,
                        pf.opportunity_score,
                        pf.production_score
                      FROM {FANTASY_SCHEMA}.player_fantasy_profile pf
                      WHERE pf.season = :season
                      ORDER BY
                        pf.player_id,
                        (pf.opportunity_score IS NULL) ASC,
                        pf.week DESC
                    ),
                    ownership AS (
                      SELECT DISTINCT ON (m.player_id)
                        m.player_id,
                        m.ownership,
                        m.week AS ownership_week
                      FROM {FANTASY_SCHEMA}.fact_market m
                      WHERE m.season = :season
                        AND m.ownership IS NOT NULL
                        {ownership_week_filter}
                      ORDER BY
                        m.player_id,
                        m.week DESC NULLS LAST,
                        m.updated_at DESC NULLS LAST
                    )
                    SELECT
                      p.player_id,
                      p.name,
                      p.position,
                      t.team_abbreviation AS team,
                      pts.fantasy_points,
                      lp.fantasy_value_score,
                      lp.opportunity_score,
                      lp.production_score,
                      own.ownership,
                      p.source_ids
                    FROM {FANTASY_SCHEMA}.dim_player p
                    LEFT JOIN {FANTASY_SCHEMA}.dim_team t
                      ON t.team_id = p.current_team_id
                    INNER JOIN pts
                      ON pts.player_id = p.player_id
                    INNER JOIN ownership own
                      ON own.player_id = p.player_id
                    LEFT JOIN latest_profile lp
                      ON lp.player_id = p.player_id
                    WHERE UPPER(COALESCE(p.position, '')) = :position
                      AND p.player_id <> :player_id
                      AND own.ownership < :max_ownership
                    ORDER BY
                      lp.fantasy_value_score DESC NULLS LAST,
                      pts.fantasy_points DESC NULLS LAST,
                      own.ownership ASC,
                      p.name
                    LIMIT :limit
                    """
                ),
                connection,
                params=params,
            )
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        pid = str(row.get("player_id") or "").strip()
        if not pid:
            continue
        rows.append(
            {
                "player_id": pid,
                "name": str(row.get("name") or pid),
                "position": row.get("position"),
                "team": row.get("team"),
                "fantasy_points": _num(row.get("fantasy_points")),
                "fantasy_value_score": _num(
                    row.get("fantasy_value_score")
                ),
                "opportunity_score": _num(
                    row.get("opportunity_score")
                ),
                "production_score": _num(
                    row.get("production_score")
                ),
                "ownership": _num(row.get("ownership")),
                "headshot_url": _espn_headshot_url(
                    row.get("source_ids")
                ),
                "overall_assessment": overall_assessment_label(
                    _num(row.get("fantasy_value_score"))
                ),
            }
        )
    return rows


def _ownership_for_player(
    player_id: str,
    *,
    season: int | None,
    week: int | None = None,
) -> float | None:
    if season is None:
        return None
    try:
        from sqlalchemy import text

        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
    except Exception:
        return None

    params: dict[str, Any] = {
        "player_id": player_id,
        "season": int(season),
    }
    week_clause = ""
    if week is not None:
        params["week"] = int(week)
        week_clause = "AND week = :week"
    else:
        week_clause = """
            AND week = (
              SELECT MAX(week)
              FROM {schema}.fact_market
              WHERE season = :season
                AND week IS NOT NULL
                AND ownership IS NOT NULL
            )
        """.format(schema=FANTASY_SCHEMA)

    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT ownership
                    FROM {FANTASY_SCHEMA}.fact_market
                    WHERE player_id = :player_id
                      AND season = :season
                      AND ownership IS NOT NULL
                      {week_clause}
                    ORDER BY week DESC NULLS LAST, updated_at DESC NULLS LAST
                    LIMIT 1
                    """
                ),
                connection,
                params=params,
            )
    except Exception:
        return None

    if frame.empty:
        return None
    return _num(frame.iloc[0].get("ownership"))


def get_player_snapshot_by_id(
    player_id: str,
    *,
    season: int | None = None,
    week: int | None = None,
) -> dict[str, Any] | None:
    """
    Build one Player Snapshot for a selected player from
    canonical profile + signals (+ identity/injury).

    Loads are scoped to the player_id so the overview search
    path stays fast enough for the browser.
    """

    pid = str(player_id or "").strip()
    if not pid:
        return None

    defense_snapshot = build_team_defense_snapshot(
        pid,
        season=season,
    )
    if defense_snapshot is not None:
        return defense_snapshot

    try:
        import nflreadpy as nfl
        from app.canonical.analytics.fantasy_signal import (
            FANTASY_SIGNAL_COLUMNS,
        )
        from app.canonical.analytics.persist import load_rows
        from app.canonical.analytics.player_fantasy_profile import (
            PLAYER_FANTASY_PROFILE_COLUMNS,
        )
        from app.canonical.dim_player import (
            DIM_PLAYER_COLUMNS,
            get_dim_player,
        )
        from app.canonical.dim_team import get_dim_team
        from app.canonical.fact_injury import FACT_INJURY_COLUMNS
        from app.canonical.schema import FANTASY_SCHEMA
        from app.database import engine
        from sqlalchemy import text
    except Exception:
        return None

    resolved_season = season
    if resolved_season is None:
        try:
            resolved_season = int(nfl.get_current_season())
        except Exception:
            resolved_season = None

    injury_period = _current_injury_report_period()
    injury_seasons = (
        [int(injury_period[0])]
        if injury_period is not None
        else (
            [int(resolved_season)]
            if resolved_season is not None
            else None
        )
    )

    seasons = (
        [int(resolved_season)]
        if resolved_season is not None
        else None
    )

    try:
        profiles = load_rows(
            "player_fantasy_profile",
            PLAYER_FANTASY_PROFILE_COLUMNS,
            seasons=seasons,
            player_id=pid,
            order_by="season, week",
        )
        signals = load_rows(
            "fantasy_signal",
            FANTASY_SIGNAL_COLUMNS,
            seasons=seasons,
            player_id=pid,
            order_by="season, week, signal_type",
        )
        injuries = load_rows(
            "fact_injury",
            FACT_INJURY_COLUMNS,
            seasons=injury_seasons,
            player_id=pid,
            order_by="season, week, report_date",
        )
    except Exception:
        profiles = None
        signals = None
        injuries = None

    identity: dict[str, Any] = {}
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    f"""
                    SELECT {", ".join(DIM_PLAYER_COLUMNS)}
                    FROM {FANTASY_SCHEMA}.dim_player
                    WHERE player_id = :player_id
                    LIMIT 1
                    """
                ),
                connection,
                params={"player_id": pid},
            )
        if not frame.empty:
            identity = frame.to_dict(orient="records")[0]
        else:
            # Fallback to in-memory dim_player if DB miss.
            players = get_dim_player()
            if players is not None and not players.empty:
                for row in players.to_dict(orient="records"):
                    if str(row.get("player_id") or "").strip() == pid:
                        identity = row
                        break
    except Exception:
        try:
            players = get_dim_player()
            if players is not None and not players.empty:
                for row in players.to_dict(orient="records"):
                    if str(row.get("player_id") or "").strip() == pid:
                        identity = row
                        break
        except Exception:
            identity = {}

    if not identity:
        return None

    player_profiles = (
        profiles.to_dict(orient="records")
        if profiles is not None and not profiles.empty
        else []
    )
    player_signals = (
        signals.to_dict(orient="records")
        if signals is not None and not signals.empty
        else []
    )

    # Prefer the same profile week rule as the player list:
    # latest week with opportunity filled, unless the caller
    # pinned an explicit week.
    requested_week = week
    profile = _select_profile_for_snapshot(
        player_profiles,
        season=resolved_season,
        week=requested_week,
    )

    resolved_week = requested_week
    if profile:
        try:
            if resolved_season is None:
                resolved_season = int(profile.get("season"))
            if resolved_week is None:
                resolved_week = int(profile.get("week"))
        except (TypeError, ValueError):
            pass

    if resolved_season is None or resolved_week is None:
        if player_signals:
            latest = max(
                player_signals,
                key=lambda row: (
                    int(row.get("season") or 0),
                    int(row.get("week") or 0),
                ),
            )
            try:
                if resolved_season is None:
                    resolved_season = int(latest.get("season"))
                if resolved_week is None:
                    resolved_week = int(latest.get("week"))
            except (TypeError, ValueError):
                pass

    season_profiles = []
    for row in player_profiles:
        if resolved_season is None:
            season_profiles.append(row)
            continue
        try:
            if int(row.get("season")) == int(resolved_season):
                season_profiles.append(row)
        except (TypeError, ValueError):
            continue

    signal_rows: list[dict[str, Any]] = []
    for row in player_signals:
        try:
            if (
                resolved_season is not None
                and resolved_week is not None
                and int(row.get("season")) == int(resolved_season)
                and int(row.get("week")) == int(resolved_week)
            ):
                signal_rows.append(row)
        except (TypeError, ValueError):
            continue

    team_abbr: dict[str, str] = {}
    try:
        teams = get_dim_team()
        if teams is not None and not teams.empty:
            for row in teams.to_dict(orient="records"):
                tid = str(row.get("team_id") or "").strip()
                abbr = row.get("team_abbreviation")
                if tid and abbr:
                    team_abbr[tid] = str(abbr)
    except Exception:
        team_abbr = {}

    injury: dict[str, Any] = {}
    injury_season = (
        injury_period[0] if injury_period is not None else None
    )
    injury_week = (
        injury_period[1] if injury_period is not None else None
    )
    # Fall back to the snapshot's resolved week when the global
    # injury period cannot be resolved.
    if injury_season is None:
        injury_season = resolved_season
    if injury_week is None:
        injury_week = resolved_week
    injury_type, injury_status = _injury_fields_for_period(
        injuries,
        season=injury_season,
        week=injury_week,
    )

    team_id = identity.get("current_team_id")
    if not team_id and injuries is not None and not injuries.empty:
        # Prefer team from the matched injury row when available.
        for row in injuries.to_dict(orient="records"):
            try:
                if (
                    injury_season is not None
                    and injury_week is not None
                    and int(row.get("season")) == int(injury_season)
                    and int(row.get("week")) == int(injury_week)
                ):
                    injury = row
                    break
            except (TypeError, ValueError):
                continue
        team_id = injury.get("team_id") or team_id
    team_label = (
        team_abbr.get(str(team_id), str(team_id))
        if team_id
        else None
    )

    source_ids = identity.get("source_ids")
    ids = _parse_source_ids(source_ids)
    espn_id = ids.get("espn_id")
    if espn_id is not None:
        espn_id = str(espn_id).strip()
        if espn_id.endswith(".0") and espn_id[:-2].isdigit():
            espn_id = espn_id[:-2]

    season_stats = _season_stats_for_player(
        pid,
        position=identity.get("position"),
        season=resolved_season,
    )
    profile = _seasonize_profile_scores(
        profile,
        position=identity.get("position"),
        season_stats=season_stats,
        season_profiles=season_profiles,
    )
    ranks = _ranks_for_player(
        pid,
        position=identity.get("position"),
        season=resolved_season,
    )
    replacements = _replacement_candidates(
        player_id=pid,
        position=identity.get("position"),
        season=resolved_season,
        week=resolved_week,
        limit=5,
    )
    ownership = _ownership_for_player(
        pid,
        season=resolved_season,
        week=resolved_week,
    )
    depth = _depth_chart_for_player(
        pid,
        position=identity.get("position"),
    )
    position_depth = _team_position_depth_chart(
        team_id=identity.get("current_team_id") or team_id,
        position=identity.get("position"),
        highlight_player_id=pid,
    )

    return build_player_snapshot(
        player_id=pid,
        name=identity.get("name"),
        position=identity.get("position"),
        team=team_label,
        season=resolved_season,
        week=resolved_week,
        status=identity.get("status"),
        injury_type=injury_type,
        injury_status=(
            str(injury_status)
            if injury_status is not None
            else None
        ),
        profile=profile,
        signals=signal_rows,
        include_performance=True,
        birth_date=identity.get("birth_date"),
        rookie_season=identity.get("rookie_season"),
        headshot_url=_espn_headshot_url(source_ids),
        espn_id=espn_id,
        season_stats=season_stats,
        position_rank=ranks.get("position_rank"),
        overall_rank=ranks.get("overall_rank"),
        position_pool_size=ranks.get("position_pool_size"),
        overall_pool_size=ranks.get("overall_pool_size"),
        replacements=replacements,
        ownership=ownership,
        depth_order=depth.get("depth_order"),
        depth_chart=depth.get("depth_chart"),
        position_depth_chart=position_depth,
    )
