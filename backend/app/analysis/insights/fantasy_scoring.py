"""
Shared fantasy-point scoring helpers.

Standard skill scoring + distance-based kicker scoring:
  FG 0–39: 3, FG 40–49: 4, FG 50+: 5, PAT: 1
"""

from __future__ import annotations

from typing import Any

from app.canonical.analytics.common import normalize_float


def _reception_points(scoring: str | None) -> float:
    key = str(scoring or "ppr").strip().lower()
    if key in {"standard", "non_ppr", "non-ppr"}:
        return 0.0
    if key in {"half", "half_ppr", "half-ppr"}:
        return 0.5
    return 1.0


def kicking_points_sql(*, alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return f"""
        (
          (
            COALESCE({prefix}fg_made_0_19, 0)
            + COALESCE({prefix}fg_made_20_29, 0)
            + COALESCE({prefix}fg_made_30_39, 0)
          ) * 3.0
          + COALESCE({prefix}fg_made_40_49, 0) * 4.0
          + (
            COALESCE({prefix}fg_made_50_59, 0)
            + COALESCE({prefix}fg_made_60_, 0)
          ) * 5.0
          + COALESCE({prefix}pat_made, 0) * 1.0
        )
    """


def fantasy_points_sql(
    scoring: str | None = "ppr",
    *,
    alias: str = "",
) -> str:
    """SQL expression for one game of fantasy points."""

    prefix = f"{alias}." if alias else ""
    rec = _reception_points(scoring)
    return f"""
        (
          COALESCE({prefix}pass_yards, 0) / 25.0
          + COALESCE({prefix}pass_tds, 0) * 4.0
          - COALESCE({prefix}interceptions, 0) * 2.0
          + COALESCE({prefix}rush_yards, 0) / 10.0
          + COALESCE({prefix}rush_tds, 0) * 6.0
          + COALESCE({prefix}receptions, 0) * {rec}
          + COALESCE({prefix}receiving_yards, 0) / 10.0
          + COALESCE({prefix}receiving_tds, 0) * 6.0
          + {kicking_points_sql(alias=alias)}
        )
    """


def fantasy_points_from_row(
    row: dict[str, Any],
    *,
    scoring: str | None = "ppr",
) -> float | None:
    """Python equivalent of fantasy_points_sql for one game row."""

    skill = [
        normalize_float(row.get("pass_yards")),
        normalize_float(row.get("pass_tds")),
        normalize_float(row.get("interceptions")),
        normalize_float(row.get("rush_yards")),
        normalize_float(row.get("rush_tds")),
        normalize_float(row.get("receptions")),
        normalize_float(row.get("receiving_yards")),
        normalize_float(row.get("receiving_tds")),
    ]
    kicking = [
        normalize_float(row.get("fg_made_0_19")),
        normalize_float(row.get("fg_made_20_29")),
        normalize_float(row.get("fg_made_30_39")),
        normalize_float(row.get("fg_made_40_49")),
        normalize_float(row.get("fg_made_50_59")),
        normalize_float(row.get("fg_made_60_")),
        normalize_float(row.get("pat_made")),
        # Fallback when distance buckets are missing.
        normalize_float(row.get("fg_made")),
    ]
    if all(value is None for value in skill + kicking):
        return None

    pass_yards = skill[0] or 0.0
    pass_tds = skill[1] or 0.0
    interceptions = skill[2] or 0.0
    rush_yards = skill[3] or 0.0
    rush_tds = skill[4] or 0.0
    receptions = skill[5] or 0.0
    receiving_yards = skill[6] or 0.0
    receiving_tds = skill[7] or 0.0

    fg_0_39 = (
        (kicking[0] or 0.0)
        + (kicking[1] or 0.0)
        + (kicking[2] or 0.0)
    )
    fg_40_49 = kicking[3] or 0.0
    fg_50_plus = (kicking[4] or 0.0) + (kicking[5] or 0.0)
    pat_made = kicking[6] or 0.0

    # If distance buckets are absent but fg_made is present, score at 3/make.
    if (
        all(kicking[i] is None for i in range(6))
        and kicking[7] is not None
    ):
        fg_0_39 = float(kicking[7])
        fg_40_49 = 0.0
        fg_50_plus = 0.0

    rec = _reception_points(scoring)
    points = (
        (pass_yards / 25.0)
        + (pass_tds * 4.0)
        - (interceptions * 2.0)
        + (rush_yards / 10.0)
        + (rush_tds * 6.0)
        + (receptions * rec)
        + (receiving_yards / 10.0)
        + (receiving_tds * 6.0)
        + (fg_0_39 * 3.0)
        + (fg_40_49 * 4.0)
        + (fg_50_plus * 5.0)
        + (pat_made * 1.0)
    )
    return round(float(points), 1)


def dst_points_allowed_points(points_allowed: Any) -> float:
    """ESPN-style points-allowed fantasy scoring."""

    value = normalize_float(points_allowed)
    if value is None:
        return 0.0
    if value <= 0:
        return 10.0
    if value <= 6:
        return 7.0
    if value <= 13:
        return 4.0
    if value <= 20:
        return 1.0
    if value <= 27:
        return 0.0
    if value <= 34:
        return -1.0
    return -4.0


def dst_touchdowns(row: dict[str, Any]) -> float:
    """Defensive + special-teams touchdowns for DST scoring."""

    return (
        (normalize_float(row.get("defensive_tds")) or 0.0)
        + (normalize_float(row.get("special_teams_tds")) or 0.0)
        + (normalize_float(row.get("fumble_recovery_tds")) or 0.0)
        + (normalize_float(row.get("pt_return_tds")) or 0.0)
        + (normalize_float(row.get("kick_return_tds")) or 0.0)
    )


def dst_game_fantasy_points(row: dict[str, Any]) -> float:
    """
    Standard fantasy team-defense scoring for one game.

    Points allowed brackets + sacks / turnovers / scores / blocks.
    """

    points = dst_points_allowed_points(row.get("points_allowed"))
    points += (normalize_float(row.get("sacks")) or 0.0) * 1.0
    points += (normalize_float(row.get("interceptions")) or 0.0) * 2.0
    points += (
        normalize_float(row.get("fumbles_recovered")) or 0.0
    ) * 2.0
    points += (normalize_float(row.get("safeties")) or 0.0) * 2.0
    points += dst_touchdowns(row) * 6.0
    points += (normalize_float(row.get("def_2pt_made")) or 0.0) * 2.0
    blocked = (
        (normalize_float(row.get("blocked_kicks")) or 0.0)
        + (normalize_float(row.get("def_punt_blocks")) or 0.0)
        + (normalize_float(row.get("def_fg_blocks")) or 0.0)
        + (normalize_float(row.get("def_pat_blocks")) or 0.0)
        + (normalize_float(row.get("pt_blocked")) or 0.0)
        + (normalize_float(row.get("fg_blocked")) or 0.0)
        + (normalize_float(row.get("pat_blocked")) or 0.0)
    )
    points += blocked * 2.0
    return round(float(points), 1)
