"""
Projection Calibration / Guardrail Layer
========================================

Purpose
-------
Convert a *raw* DFS projection (typically current-season FPPG)
into an InsightPilot projection that is statistically
reasonable early in the season, without hard-capping
legitimate elite ceilings.

Pipeline
--------
    Raw projection (season FPPG / model output)
            │
            ▼
    Projection Calibration / Guardrails
      • Sample-size regression toward historical baseline
      • Opportunity-support validation
      • Historical / positional distribution checks
      • Confidence + floor / ceiling range
            │
            ▼
    InsightPilot projection (pre-matchup)
            │
            ▼
    Weekly matchup / environment multiplier (slate)
            │
            ▼
    Final DFS projection consumed by analyzer / optimizer

Design rules
------------
1. Never overwrite the raw projection — always emit both
   ``raw_projection`` and ``insightpilot_projection``.
2. Weights and thresholds live in ``CalibrationConfig`` so
   methodology can be tuned without rewriting DFS code.
3. Do not hard-cap projections. Extreme outcomes that are
   *supported by opportunity + history* may remain high;
   small-sample spikes are regressed.
4. Position-agnostic API — Josh Allen is a test case, not
   special-cased logic.

Blend (documented, configurable)
--------------------------------
    adjusted =
        historical_baseline × historical_weight
      + current_season_signal × current_season_weight

Current-season weight rises with ``current_season_games``
per ``sample_weight_schedule``. When no historical baseline
exists (rookies), a positional prior is used instead.

Opportunity check
-----------------
If current FPPG heavily exceeds what opportunity scores
imply relative to the baseline, pull toward an
opportunity-supported estimate.

Distribution check
------------------
If the candidate sits above a high historical percentile
*and* sample size is small, soft-regress toward that
percentile. Supported elite projections (large sample or
strong opportunity) are left alone.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


# ---------------------------------------------------------------------------
# Configuration (tune here — do not scatter magic numbers)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SampleWeightBand:
    """Inclusive max games for this current-season weight."""

    max_games: int | None
    current_season_weight: float


@dataclass(frozen=True)
class CalibrationConfig:
    """
    Tunable projection guardrail parameters.

    ``sample_weight_schedule`` is ordered ascending by
    ``max_games`` (``None`` = catch-all / 10+ games).
    """

    sample_weight_schedule: tuple[SampleWeightBand, ...] = (
        SampleWeightBand(max_games=2, current_season_weight=0.20),
        SampleWeightBand(max_games=5, current_season_weight=0.40),
        SampleWeightBand(max_games=9, current_season_weight=0.60),
        SampleWeightBand(max_games=None, current_season_weight=0.80),
    )

    # Positional prior FPPG when no player history exists.
    positional_priors: dict[str, float] = field(
        default_factory=lambda: {
            "QB": 18.5,
            "RB": 12.5,
            "WR": 11.5,
            "TE": 8.5,
            "DEF": 7.0,
            "DST": 7.0,
            "K": 8.0,
        }
    )

    # Soft upper reference for distribution / ceiling math
    # (not hard caps — used as regression anchors).
    positional_soft_ceilings: dict[str, float] = field(
        default_factory=lambda: {
            "QB": 34.0,
            "RB": 28.0,
            "WR": 26.0,
            "TE": 20.0,
            "DEF": 14.0,
            "DST": 14.0,
            "K": 14.0,
        }
    )

    # Opportunity: map score 0–100 → support multiplier on baseline.
    opportunity_support_floor: float = 0.70
    opportunity_support_span: float = 0.60
    # If raw exceeds supported × this and sample is small, pull in.
    opportunity_spike_ratio: float = 1.25
    opportunity_pull_strength: float = 0.55

    # Historical distribution soft regression.
    distribution_percentile: float = 0.90
    distribution_spike_games: int = 5
    distribution_pull_strength: float = 0.50

    # Floor / ceiling multipliers by confidence label.
    range_by_confidence: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "Very Low": (0.55, 1.55),
            "Low": (0.60, 1.45),
            "Moderate": (0.65, 1.40),
            "High": (0.70, 1.35),
            "Very High": (0.75, 1.30),
        }
    )

    # Absolute sanity clamps only for non-finite / absurd inputs.
    absolute_min_projection: float = 0.0
    absolute_max_projection: float = 55.0


DEFAULT_CALIBRATION_CONFIG = CalibrationConfig()


# ---------------------------------------------------------------------------
# Public result
# ---------------------------------------------------------------------------


@dataclass
class CalibratedProjection:
    raw_projection: float
    insightpilot_projection: float
    projection_floor: float
    projection_ceiling: float
    projection_confidence: str
    projection_adjustment: float
    projection_adjustment_reason: str
    sample_size_confidence: str
    current_season_games: int
    historical_games: int
    historical_baseline: float | None
    current_season_weight: float
    historical_weight: float
    opportunity_supported_projection: float | None
    distribution_reference: float | None
    flags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def calibrate_projection(
    *,
    raw_projection: float,
    position: str,
    current_season_games: int = 0,
    historical_baseline: float | None = None,
    historical_games: int = 0,
    historical_p90: float | None = None,
    opportunity_score: float | None = None,
    depth_order: int | None = None,
    roster_status: str | None = None,
    config: CalibrationConfig | None = None,
) -> CalibratedProjection:
    """
    Apply sample-size, opportunity, and distribution guardrails.

    Parameters
    ----------
    raw_projection:
        Uncalibrated signal (usually current-season FPPG).
    position:
        Player position (QB/RB/WR/TE/DEF/…).
    current_season_games / historical_games:
        Sample sizes driving blend weights and confidence.
    historical_baseline:
        Established FPPG (prior seasons preferred).
    historical_p90:
        Player historical ~90th percentile game (optional).
    opportunity_score:
        Canonical opportunity score 0–100 (optional).
    depth_order:
        Latest depth-chart rank (1 = starter). Used so QB1/RB1
        with no season stats still get a prior-based projection,
        while deep backups are not inflated to positional averages.
    roster_status:
        Dim-player status (Active / Reserve / …). Non-active
        statuses suppress positional-prior inflation.
    """

    cfg = config or DEFAULT_CALIBRATION_CONFIG
    pos = _normalize_position(position)
    raw = _finite(raw_projection, fallback=0.0)
    cur_games = max(0, int(current_season_games or 0))
    hist_games = max(0, int(historical_games or 0))
    try:
        depth = (
            int(depth_order)
            if depth_order is not None
            else None
        )
    except (TypeError, ValueError):
        depth = None
    status_key = str(roster_status or "").strip().lower()
    inactive_roster = status_key in {
        "reserve",
        "inactive",
        "practice squad",
        "practice_squad",
        "cut",
        "waived",
        "suspended",
        "physically unable to perform",
        "pup",
        "nfi",
        "ir",
        "injured reserve",
    }

    reasons: list[str] = []
    flags: list[str] = []

    baseline = historical_baseline
    if baseline is None or baseline <= 0:
        baseline = cfg.positional_priors.get(pos)
        if hist_games <= 0:
            flags.append("positional_prior")
            reasons.append(
                "No established player baseline; used positional "
                "prior as the historical anchor."
            )
        else:
            flags.append("weak_historical_baseline")
    baseline = float(baseline or cfg.positional_priors.get(pos, 10.0))

    cur_w, hist_w = _sample_weights(
        current_games=cur_games,
        has_historical=hist_games > 0 or "positional_prior" in flags,
        config=cfg,
    )
    if hist_games <= 0 and "positional_prior" in flags:
        # Rookies: even less trust in tiny current samples —
        # unless they are depth-chart starters expected to play.
        if cur_games <= 2 and not (depth is not None and depth <= 2):
            cur_w = min(cur_w, 0.15)
            hist_w = 1.0 - cur_w

    # Expected #1 starters with little/no season sample: lean on
    # historical / positional prior rather than a near-zero raw.
    # Depth-2 backups with weak opportunity should NOT get this
    # prop-up — active zero weeks must pull the projection down.
    true_starter = depth is not None and depth == 1
    primary_backup = depth is not None and depth == 2
    if true_starter and cur_games <= 2 and raw <= 3.0 and not inactive_roster:
        flags.append("depth_starter_prior")
        # Keep enough prior weight that QB1/RB1 is not crushed
        # to ~0 when they have not produced yet this season.
        hist_w = max(hist_w, 0.75)
        cur_w = 1.0 - hist_w
        reasons.append(
            f"Depth-chart rank {depth} with limited current-season "
            "production; projection leans on the established "
            "baseline / positional prior."
        )

    # Deep depth chart + near-zero production: do not invent
    # positional-average projections (e.g. QB4 / WR6).
    # Also covers TE2/WR2 with weak opportunity after active
    # zero-production weeks so historical FPPG cannot dominate.
    deep_depth = depth is not None and depth >= 3
    try:
        opp_value = (
            float(opportunity_score)
            if opportunity_score is not None
            else None
        )
    except (TypeError, ValueError):
        opp_value = None
    weak_opportunity = opp_value is None or opp_value < 20.0
    backup_without_role = (
        primary_backup and (opp_value is None or opp_value < 30.0)
    )
    prior_ref = float(cfg.positional_priors.get(pos, 10.0))
    # One catch / short sample can land mid-single-digit FPPG
    # without implying a real weekly role — treat that as dormant
    # when depth, opportunity, or roster status say reserve.
    low_production = (
        raw <= 3.0
        or (
            cur_games >= 2
            and baseline > 0
            and raw <= baseline * 0.45
        )
        or (
            cur_games <= 3
            and raw <= max(6.0, prior_ref * 0.55)
            and (
                deep_depth
                or weak_opportunity
                or backup_without_role
                or inactive_roster
            )
        )
    )
    dormant = (
        (
            cur_games >= 1
            or (
                # No logged games yet but clearly not a starter —
                # do not invent career/positional averages.
                cur_games == 0
                and raw <= 3.0
                and (deep_depth or inactive_roster)
            )
        )
        and low_production
        and (
            deep_depth
            or weak_opportunity
            or backup_without_role
            or inactive_roster
        )
        and not true_starter
        and "depth_starter_prior" not in flags
    )
    if dormant:
        flags.append("dormant_usage")
        if inactive_roster:
            flags.append("inactive_roster")
        cur_w = max(cur_w, 0.95)
        hist_w = 1.0 - cur_w
        if hist_games <= 0 or "positional_prior" in flags:
            baseline = min(float(baseline), max(float(raw), 1.0))
        reasons.append(
            "Near-zero / sharply depressed production with weak "
            "opportunity or non-starter depth; projection stays "
            "anchored to the observed signal instead of historical "
            "or positional averages."
        )

    blended = (baseline * hist_w) + (raw * cur_w)
    if (
        "dormant_usage" not in flags
        and "depth_starter_prior" not in flags
    ):
        reasons.append(
            f"Blended current-season signal ({cur_w:.0%}) with "
            f"historical baseline ({hist_w:.0%}) given "
            f"{cur_games} current-season game"
            f"{'' if cur_games == 1 else 's'}."
        )

    opportunity_supported: float | None = None
    if opportunity_score is not None:
        opportunity_supported = _opportunity_supported(
            baseline=baseline,
            opportunity_score=float(opportunity_score),
            config=cfg,
        )
        if (
            cur_games <= cfg.distribution_spike_games
            and raw
            > opportunity_supported * cfg.opportunity_spike_ratio
        ):
            pull = cfg.opportunity_pull_strength
            before = blended
            blended = (blended * (1.0 - pull)) + (
                opportunity_supported * pull
            )
            flags.append("opportunity_regression")
            reasons.append(
                "Recent fantasy production exceeds opportunity-"
                "supported expectation; projection pulled toward "
                f"opportunity estimate ({opportunity_supported:.1f} "
                f"from {before:.1f})."
            )

    # Dormant players with tiny opportunity: a single chunk play
    # (e.g. one 30-yard catch) must not set the weekly projection.
    if (
        dormant
        and opp_value is not None
        and opp_value < 15.0
        and raw > 0
    ):
        role_cap = max(
            0.5,
            float(raw)
            * (0.25 + 0.75 * min(1.0, float(opp_value) / 20.0)),
        )
        if blended > role_cap + 1e-9:
            blended = role_cap
            flags.append("dormant_opportunity_cap")
            reasons.append(
                "Limited opportunity caps the dormant-usage "
                f"projection at {role_cap:.1f}."
            )

    distribution_ref = historical_p90
    if distribution_ref is None:
        soft = cfg.positional_soft_ceilings.get(pos)
        distribution_ref = soft
    if (
        distribution_ref is not None
        and cur_games <= cfg.distribution_spike_games
        and blended > float(distribution_ref)
        and raw > float(distribution_ref) * 1.05
    ):
        # Distinguish supported elite vs small-sample spike.
        opp_ok = (
            opportunity_supported is not None
            and raw
            <= opportunity_supported * cfg.opportunity_spike_ratio
        )
        if opp_ok and cur_games >= 6:
            flags.append("elite_supported")
            reasons.append(
                "Projection sits in an elite range but is "
                "supported by opportunity and sample size."
            )
        else:
            pull = cfg.distribution_pull_strength
            before = blended
            blended = (blended * (1.0 - pull)) + (
                float(distribution_ref) * pull
            )
            flags.append("distribution_regression")
            reasons.append(
                "Projection exceeded historical/positional "
                f"reference ({float(distribution_ref):.1f}) with "
                "a limited sample; soft-regressed "
                f"from {before:.1f}."
            )

    blended = max(
        cfg.absolute_min_projection,
        min(cfg.absolute_max_projection, float(blended)),
    )

    sample_label = _sample_size_confidence(cur_games, hist_games)
    confidence = _projection_confidence(
        sample_label=sample_label,
        current_games=cur_games,
        historical_games=hist_games,
        flags=flags,
    )
    floor_m, ceil_m = cfg.range_by_confidence.get(
        confidence, (0.65, 1.40)
    )
    floor = round(max(0.0, blended * floor_m), 1)
    ceiling = round(
        min(cfg.absolute_max_projection, blended * ceil_m),
        1,
    )
    # Prefer historical p90 as ceiling anchor when higher and
    # sample is mature enough that upside is earned.
    if (
        historical_p90 is not None
        and cur_games >= 6
        and float(historical_p90) > ceiling
    ):
        ceiling = round(min(cfg.absolute_max_projection, float(historical_p90)), 1)

    adjustment = round(blended - raw, 1)
    if abs(adjustment) < 0.05 and not reasons:
        reasons.append("No material calibration adjustment applied.")

    reason = " ".join(reasons)
    if cur_games <= 2 and abs(adjustment) >= 3:
        if adjustment < 0:
            reason = (
                "Recent performance heavily exceeds established "
                "baseline; projection regressed toward historical "
                "expectation due to limited current-season sample. "
                + reason
            )
        elif "dormant_usage" not in flags:
            reason = (
                "Early-season production sits well below the "
                "historical baseline; projection was partially "
                "supported by established expectation. "
                + reason
            )

    return CalibratedProjection(
        raw_projection=round(raw, 1),
        insightpilot_projection=round(blended, 1),
        projection_floor=floor,
        projection_ceiling=ceiling,
        projection_confidence=confidence,
        projection_adjustment=adjustment,
        projection_adjustment_reason=reason.strip(),
        sample_size_confidence=sample_label,
        current_season_games=cur_games,
        historical_games=hist_games,
        historical_baseline=round(baseline, 1),
        current_season_weight=round(cur_w, 3),
        historical_weight=round(hist_w, 3),
        opportunity_supported_projection=(
            round(opportunity_supported, 1)
            if opportunity_supported is not None
            else None
        ),
        distribution_reference=(
            round(float(distribution_ref), 1)
            if distribution_ref is not None
            else None
        ),
        flags=flags,
    )


def current_season_weight_for_games(
    games: int,
    *,
    config: CalibrationConfig | None = None,
) -> float:
    """Expose schedule lookup for docs / tests."""

    cfg = config or DEFAULT_CALIBRATION_CONFIG
    weight, _ = _sample_weights(
        current_games=games,
        has_historical=True,
        config=cfg,
    )
    return weight


def with_config(**overrides: Any) -> CalibrationConfig:
    """Return a config copy with selected fields replaced."""

    base = DEFAULT_CALIBRATION_CONFIG
    return replace(base, **overrides)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _normalize_position(position: Any) -> str:
    pos = str(position or "").strip().upper()
    if pos in {"DST", "D/ST", "DEFENSE"}:
        return "DEF"
    return pos or "WR"


def _finite(value: Any, *, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number:  # NaN
        return fallback
    return number


def _sample_weights(
    *,
    current_games: int,
    has_historical: bool,
    config: CalibrationConfig,
) -> tuple[float, float]:
    cur_w = config.sample_weight_schedule[-1].current_season_weight
    for band in config.sample_weight_schedule:
        if band.max_games is None or current_games <= band.max_games:
            cur_w = band.current_season_weight
            break
    if not has_historical:
        cur_w = min(1.0, cur_w + 0.15)
    cur_w = max(0.0, min(1.0, float(cur_w)))
    return cur_w, 1.0 - cur_w


def _opportunity_supported(
    *,
    baseline: float,
    opportunity_score: float,
    config: CalibrationConfig,
) -> float:
    score = max(0.0, min(100.0, float(opportunity_score)))
    mult = config.opportunity_support_floor + (
        config.opportunity_support_span * (score / 100.0)
    )
    return float(baseline) * mult


def _sample_size_confidence(
    current_games: int,
    historical_games: int,
) -> str:
    if current_games <= 2:
        return "Very Low"
    if current_games <= 5:
        return "Low"
    if current_games <= 9:
        return "Moderate"
    if historical_games >= 16 or current_games >= 12:
        return "High"
    return "Moderate"


def _projection_confidence(
    *,
    sample_label: str,
    current_games: int,
    historical_games: int,
    flags: list[str],
) -> str:
    if "opportunity_regression" in flags or "distribution_regression" in flags:
        if sample_label in {"Very Low", "Low"}:
            return sample_label
        return "Low"
    if sample_label == "Very Low":
        return "Very Low"
    if sample_label == "Low":
        return "Low"
    if current_games >= 10 and historical_games >= 16:
        return "Very High"
    if current_games >= 10 or historical_games >= 24:
        return "High"
    return "Moderate"
