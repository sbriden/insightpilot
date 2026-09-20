"""
Canonical data-quality checks for fantasy ingestion.

A successful download is not enough — ingestion reports whether
loaded data passed validation before derived analytics run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from app.canonical.ids import (
    is_game_id,
    is_player_id,
    is_team_id,
)


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

EXPECTED_SKILL_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
    "FB",
    "HB",
}
# Broader roster positions that may appear on dim_player.
EXPECTED_ROSTER_POSITIONS = EXPECTED_SKILL_POSITIONS | {
    "T",
    "G",
    "C",
    "OL",
    "OT",
    "OG",
    "DE",
    "DT",
    "NT",
    "DL",
    "LB",
    "ILB",
    "OLB",
    "CB",
    "S",
    "FS",
    "SS",
    "DB",
    "K",
    "P",
    "LS",
    "KR",
    "PR",
    "DEF",
    "DST",
}

STAT_NON_NEGATIVE = (
    "pass_attempts",
    "pass_completions",
    "pass_yards",
    "pass_tds",
    "interceptions",
    "rush_attempts",
    "rush_yards",
    "rush_tds",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
)


@dataclass
class QualityCheck:
    check_id: str
    label: str
    severity: str
    passed: bool
    message: str
    dataset_id: str | None = None
    count: int = 0
    sample: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QualityReport:
    passed: bool
    status: str
    message: str
    error_count: int
    warning_count: int
    checks: list[QualityCheck] = field(default_factory=list)
    seasons: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "message": self.message,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "seasons": list(self.seasons),
            "checks": [check.to_dict() for check in self.checks],
        }


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "<na>"}


def _frame(frames: dict[str, pd.DataFrame], key: str) -> pd.DataFrame:
    value = frames.get(key)
    if value is None or not isinstance(value, pd.DataFrame):
        return pd.DataFrame()
    return value


def _check(
    *,
    check_id: str,
    label: str,
    severity: str,
    passed: bool,
    message: str,
    dataset_id: str | None = None,
    count: int = 0,
    sample: list[Any] | None = None,
) -> QualityCheck:
    return QualityCheck(
        check_id=check_id,
        label=label,
        severity=severity,
        passed=passed,
        message=message,
        dataset_id=dataset_id,
        count=int(count),
        sample=list(sample or [])[:5],
    )


def _duplicate_key_check(
    frame: pd.DataFrame,
    *,
    check_id: str,
    label: str,
    dataset_id: str,
    keys: list[str],
    severity: str = SEVERITY_ERROR,
) -> QualityCheck:
    if frame.empty:
        return _check(
            check_id=check_id,
            label=label,
            severity=severity,
            passed=True,
            message=f"No {dataset_id} rows to check for duplicates.",
            dataset_id=dataset_id,
        )
    missing_cols = [key for key in keys if key not in frame.columns]
    if missing_cols:
        return _check(
            check_id=check_id,
            label=label,
            severity=severity,
            passed=False,
            message=(
                f"{dataset_id} missing key columns for duplicate "
                f"check: {', '.join(missing_cols)}."
            ),
            dataset_id=dataset_id,
        )
    duplicated = frame.duplicated(subset=keys, keep=False)
    count = int(duplicated.sum())
    sample: list[Any] = []
    if count:
        sample = (
            frame.loc[duplicated, keys]
            .astype(str)
            .drop_duplicates()
            .head(5)
            .to_dict(orient="records")
        )
    return _check(
        check_id=check_id,
        label=label,
        severity=severity,
        passed=count == 0,
        message=(
            f"No duplicate {dataset_id} rows on {keys}."
            if count == 0
            else f"Found {count} duplicate {dataset_id} rows on {keys}."
        ),
        dataset_id=dataset_id,
        count=count,
        sample=sample,
    )


def _missing_id_check(
    frame: pd.DataFrame,
    *,
    check_id: str,
    label: str,
    dataset_id: str,
    column: str,
    validator,
) -> QualityCheck:
    if frame.empty or column not in frame.columns:
        return _check(
            check_id=check_id,
            label=label,
            severity=SEVERITY_ERROR,
            passed=frame.empty,
            message=(
                f"No {dataset_id} rows to validate {column}."
                if frame.empty
                else f"{dataset_id} missing column {column}."
            ),
            dataset_id=dataset_id,
            count=0 if frame.empty else len(frame),
        )
    bad_mask = frame[column].map(
        lambda value: _is_missing(value) or not validator(value)
    )
    count = int(bad_mask.sum())
    sample = (
        frame.loc[bad_mask, column]
        .head(5)
        .tolist()
        if count
        else []
    )
    return _check(
        check_id=check_id,
        label=label,
        severity=SEVERITY_ERROR,
        passed=count == 0,
        message=(
            f"All {dataset_id}.{column} values are present and valid."
            if count == 0
            else (
                f"Found {count} missing/invalid {dataset_id}.{column} "
                "values."
            )
        ),
        dataset_id=dataset_id,
        count=count,
        sample=sample,
    )


def _season_week_check(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    current_season: int | None = None,
) -> QualityCheck:
    if frame.empty:
        return _check(
            check_id=f"{dataset_id}.season_week",
            label="Season / week validity",
            severity=SEVERITY_ERROR,
            passed=True,
            message=f"No {dataset_id} rows to validate season/week.",
            dataset_id=dataset_id,
        )
    if "season" not in frame.columns or "week" not in frame.columns:
        return _check(
            check_id=f"{dataset_id}.season_week",
            label="Season / week validity",
            severity=SEVERITY_ERROR,
            passed=False,
            message=f"{dataset_id} missing season/week columns.",
            dataset_id=dataset_id,
        )

    max_season = (
        int(current_season) + 1
        if current_season is not None
        else 2100
    )

    def invalid(row: dict[str, Any]) -> bool:
        season = row.get("season")
        week = row.get("week")
        try:
            season_i = int(season)
            week_i = int(week)
        except (TypeError, ValueError):
            return True
        if season_i < 1999 or season_i > max_season:
            return True
        if week_i < 1 or week_i > 22:
            return True
        return False

    records = frame[["season", "week"]].to_dict(orient="records")
    bad = [row for row in records if invalid(row)]
    count = len(bad)
    return _check(
        check_id=f"{dataset_id}.season_week",
        label="Season / week validity",
        severity=SEVERITY_ERROR,
        passed=count == 0,
        message=(
            f"All {dataset_id} season/week values look valid."
            if count == 0
            else (
                f"Found {count} invalid season/week combinations "
                f"in {dataset_id}."
            )
        ),
        dataset_id=dataset_id,
        count=count,
        sample=bad[:5],
    )


def _position_check(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    allowed: set[str],
    severity: str = SEVERITY_WARNING,
) -> QualityCheck:
    if frame.empty or "position" not in frame.columns:
        return _check(
            check_id=f"{dataset_id}.positions",
            label="Unexpected positions",
            severity=severity,
            passed=True,
            message=f"No {dataset_id} positions to validate.",
            dataset_id=dataset_id,
        )
    positions = frame["position"].dropna().map(
        lambda value: str(value).strip().upper()
    )
    unexpected = sorted(
        {
            position
            for position in positions.tolist()
            if position and position not in allowed
        }
    )
    count = len(unexpected)
    return _check(
        check_id=f"{dataset_id}.positions",
        label="Unexpected positions",
        severity=severity,
        passed=count == 0,
        message=(
            f"All {dataset_id} positions are recognized."
            if count == 0
            else (
                f"Found {count} unexpected positions in "
                f"{dataset_id}: {', '.join(unexpected[:8])}."
            )
        ),
        dataset_id=dataset_id,
        count=count,
        sample=unexpected[:5],
    )


def _missing_team_check(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    team_column: str = "team_id",
) -> QualityCheck:
    if frame.empty or team_column not in frame.columns:
        return _check(
            check_id=f"{dataset_id}.missing_teams",
            label="Missing teams",
            severity=SEVERITY_WARNING,
            passed=True,
            message=f"No {dataset_id} team values to validate.",
            dataset_id=dataset_id,
        )
    bad_mask = frame[team_column].map(
        lambda value: _is_missing(value) or not is_team_id(value)
    )
    count = int(bad_mask.sum())
    return _check(
        check_id=f"{dataset_id}.missing_teams",
        label="Missing teams",
        severity=SEVERITY_WARNING,
        passed=count == 0,
        message=(
            f"All {dataset_id}.{team_column} values are present."
            if count == 0
            else (
                f"Found {count} missing/invalid "
                f"{dataset_id}.{team_column} values."
            )
        ),
        dataset_id=dataset_id,
        count=count,
        sample=frame.loc[bad_mask, team_column].head(5).tolist(),
    )


def _invalid_stats_check(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
) -> QualityCheck:
    if frame.empty:
        return _check(
            check_id=f"{dataset_id}.stats",
            label="Null / invalid statistics",
            severity=SEVERITY_WARNING,
            passed=True,
            message=f"No {dataset_id} stats to validate.",
            dataset_id=dataset_id,
        )
    issues: list[str] = []
    count = 0
    for column in STAT_NON_NEGATIVE:
        if column not in frame.columns:
            continue
        series = pd.to_numeric(frame[column], errors="coerce")
        negative = series < 0
        neg_count = int(negative.fillna(False).sum())
        if neg_count:
            count += neg_count
            issues.append(f"{column}:{neg_count} negative")
    # Completions cannot exceed attempts when both present.
    if (
        "pass_completions" in frame.columns
        and "pass_attempts" in frame.columns
    ):
        completions = pd.to_numeric(
            frame["pass_completions"],
            errors="coerce",
        )
        attempts = pd.to_numeric(
            frame["pass_attempts"],
            errors="coerce",
        )
        bad = (completions > attempts) & completions.notna() & attempts.notna()
        bad_count = int(bad.sum())
        if bad_count:
            count += bad_count
            issues.append(
                f"pass_completions>pass_attempts:{bad_count}"
            )
    return _check(
        check_id=f"{dataset_id}.stats",
        label="Null / invalid statistics",
        severity=SEVERITY_WARNING,
        passed=count == 0,
        message=(
            f"No invalid statistics detected in {dataset_id}."
            if count == 0
            else (
                f"Found {count} invalid statistic values in "
                f"{dataset_id} ({'; '.join(issues[:4])})."
            )
        ),
        dataset_id=dataset_id,
        count=count,
        sample=issues[:5],
    )


def _row_count_check(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    minimum: int = 1,
    severity: str = SEVERITY_ERROR,
) -> QualityCheck:
    count = 0 if frame is None else int(len(frame))
    passed = count >= minimum
    return _check(
        check_id=f"{dataset_id}.row_count",
        label="Row-count anomaly",
        severity=severity,
        passed=passed,
        message=(
            f"{dataset_id} row count {count} is within expectations."
            if passed
            else (
                f"{dataset_id} row count {count} is below minimum "
                f"expected ({minimum})."
            )
        ),
        dataset_id=dataset_id,
        count=count,
    )


def _referential_check(
    child: pd.DataFrame,
    parent: pd.DataFrame,
    *,
    check_id: str,
    label: str,
    child_dataset: str,
    parent_dataset: str,
    column: str,
) -> QualityCheck:
    if child.empty:
        return _check(
            check_id=check_id,
            label=label,
            severity=SEVERITY_ERROR,
            passed=True,
            message=(
                f"No {child_dataset} rows for referential check "
                f"against {parent_dataset}."
            ),
            dataset_id=child_dataset,
        )
    if column not in child.columns:
        return _check(
            check_id=check_id,
            label=label,
            severity=SEVERITY_ERROR,
            passed=False,
            message=f"{child_dataset} missing {column}.",
            dataset_id=child_dataset,
        )
    if parent.empty or column not in parent.columns:
        return _check(
            check_id=check_id,
            label=label,
            severity=SEVERITY_ERROR,
            passed=False,
            message=(
                f"Cannot validate {child_dataset}.{column} — "
                f"{parent_dataset} is empty or missing {column}."
            ),
            dataset_id=child_dataset,
            count=int(len(child)),
        )
    parent_ids = {
        value
        for value in parent[column].tolist()
        if not _is_missing(value)
    }
    orphan_mask = child[column].map(
        lambda value: (
            not _is_missing(value) and value not in parent_ids
        )
    )
    count = int(orphan_mask.sum())
    return _check(
        check_id=check_id,
        label=label,
        severity=SEVERITY_ERROR,
        passed=count == 0,
        message=(
            f"All {child_dataset}.{column} values exist in "
            f"{parent_dataset}."
            if count == 0
            else (
                f"Found {count} {child_dataset}.{column} values "
                f"missing from {parent_dataset}."
            )
        ),
        dataset_id=child_dataset,
        count=count,
        sample=child.loc[orphan_mask, column].head(5).tolist(),
    )


def validate_canonical_frames(
    frames: dict[str, pd.DataFrame],
    *,
    seasons: list[int] | None = None,
    current_season: int | None = None,
    require_core_facts: bool = True,
) -> QualityReport:
    """
    Run ingestion data-quality checks on canonical frames.
    """

    checks: list[QualityCheck] = []
    dim_team = _frame(frames, "dim_team")
    dim_player = _frame(frames, "dim_player")
    dim_game = _frame(frames, "dim_game")
    fact_player_game = _frame(frames, "fact_player_game")
    fact_player_usage = _frame(frames, "fact_player_usage")

    # Row-count anomalies
    if require_core_facts:
        checks.append(
            _row_count_check(
                dim_team,
                dataset_id="dim_team",
                minimum=32,
            )
        )
        checks.append(
            _row_count_check(
                dim_player,
                dataset_id="dim_player",
                minimum=100,
            )
        )
        checks.append(
            _row_count_check(
                dim_game,
                dataset_id="dim_game",
                minimum=1,
            )
        )
        checks.append(
            _row_count_check(
                fact_player_game,
                dataset_id="fact_player_game",
                minimum=1,
            )
        )

    # Duplicate games / player-game
    checks.append(
        _duplicate_key_check(
            dim_game,
            check_id="dim_game.duplicate_games",
            label="Duplicate games",
            dataset_id="dim_game",
            keys=["game_id"],
        )
    )
    checks.append(
        _duplicate_key_check(
            fact_player_game,
            check_id="fact_player_game.duplicate_player_game",
            label="Duplicate player/game records",
            dataset_id="fact_player_game",
            keys=["player_id", "game_id"],
        )
    )
    if not fact_player_usage.empty:
        checks.append(
            _duplicate_key_check(
                fact_player_usage,
                check_id="fact_player_usage.duplicate_player_game",
                label="Duplicate player/game usage records",
                dataset_id="fact_player_usage",
                keys=["player_id", "game_id"],
            )
        )

    # Missing / invalid IDs
    checks.append(
        _missing_id_check(
            dim_player,
            check_id="dim_player.player_ids",
            label="Missing player IDs",
            dataset_id="dim_player",
            column="player_id",
            validator=is_player_id,
        )
    )
    checks.append(
        _missing_id_check(
            fact_player_game,
            check_id="fact_player_game.player_ids",
            label="Missing player IDs",
            dataset_id="fact_player_game",
            column="player_id",
            validator=is_player_id,
        )
    )
    checks.append(
        _missing_id_check(
            fact_player_game,
            check_id="fact_player_game.game_ids",
            label="Missing game IDs",
            dataset_id="fact_player_game",
            column="game_id",
            validator=is_game_id,
        )
    )

    # Season / week
    for dataset_id, frame in (
        ("dim_game", dim_game),
        ("fact_player_game", fact_player_game),
        ("fact_player_usage", fact_player_usage),
    ):
        if not frame.empty:
            checks.append(
                _season_week_check(
                    frame,
                    dataset_id=dataset_id,
                    current_season=current_season,
                )
            )

    # Positions
    if not dim_player.empty:
        checks.append(
            _position_check(
                dim_player,
                dataset_id="dim_player",
                allowed=EXPECTED_ROSTER_POSITIONS,
                severity=SEVERITY_WARNING,
            )
        )
    if not fact_player_usage.empty:
        checks.append(
            _position_check(
                fact_player_usage,
                dataset_id="fact_player_usage",
                allowed=EXPECTED_SKILL_POSITIONS,
                severity=SEVERITY_WARNING,
            )
        )

    # Missing teams
    checks.append(
        _missing_team_check(
            fact_player_game,
            dataset_id="fact_player_game",
        )
    )
    if "current_team_id" in dim_player.columns:
        # Null current_team_id is allowed (FA); invalid IDs are not.
        invalid_team = dim_player["current_team_id"].map(
            lambda value: (
                not _is_missing(value) and not is_team_id(value)
            )
        )
        count = int(invalid_team.sum())
        checks.append(
            _check(
                check_id="dim_player.current_team_id",
                label="Missing teams",
                severity=SEVERITY_WARNING,
                passed=count == 0,
                message=(
                    "dim_player current_team_id values are valid "
                    "or null."
                    if count == 0
                    else (
                        f"Found {count} invalid "
                        "dim_player.current_team_id values."
                    )
                ),
                dataset_id="dim_player",
                count=count,
            )
        )

    # Stats
    checks.append(
        _invalid_stats_check(
            fact_player_game,
            dataset_id="fact_player_game",
        )
    )

    # Referential integrity
    checks.append(
        _referential_check(
            fact_player_game,
            dim_player,
            check_id="ref.fact_player_game.player_id",
            label="Referential integrity (player)",
            child_dataset="fact_player_game",
            parent_dataset="dim_player",
            column="player_id",
        )
    )
    checks.append(
        _referential_check(
            fact_player_game,
            dim_game,
            check_id="ref.fact_player_game.game_id",
            label="Referential integrity (game)",
            child_dataset="fact_player_game",
            parent_dataset="dim_game",
            column="game_id",
        )
    )
    if not fact_player_usage.empty:
        checks.append(
            _referential_check(
                fact_player_usage,
                dim_player,
                check_id="ref.fact_player_usage.player_id",
                label="Referential integrity (usage player)",
                child_dataset="fact_player_usage",
                parent_dataset="dim_player",
                column="player_id",
            )
        )
        checks.append(
            _referential_check(
                fact_player_usage,
                dim_game,
                check_id="ref.fact_player_usage.game_id",
                label="Referential integrity (usage game)",
                child_dataset="fact_player_usage",
                parent_dataset="dim_game",
                column="game_id",
            )
        )
    if (
        not fact_player_game.empty
        and "team_id" in fact_player_game.columns
        and not dim_team.empty
    ):
        checks.append(
            _referential_check(
                fact_player_game,
                dim_team.rename(
                    columns={"team_id": "team_id"}
                ),
                check_id="ref.fact_player_game.team_id",
                label="Referential integrity (team)",
                child_dataset="fact_player_game",
                parent_dataset="dim_team",
                column="team_id",
            )
        )

    errors = [
        check
        for check in checks
        if not check.passed and check.severity == SEVERITY_ERROR
    ]
    warnings = [
        check
        for check in checks
        if not check.passed and check.severity == SEVERITY_WARNING
    ]
    passed = len(errors) == 0
    if passed and not warnings:
        status = "passed"
        message = (
            "The data loaded successfully and passed validation."
        )
    elif passed:
        status = "passed_with_warnings"
        message = (
            "The data loaded successfully and passed validation "
            f"with {len(warnings)} warning"
            f"{'' if len(warnings) == 1 else 's'}."
        )
    else:
        status = "failed"
        message = (
            "The data loaded but failed validation "
            f"({len(errors)} error"
            f"{'' if len(errors) == 1 else 's'}"
            f", {len(warnings)} warning"
            f"{'' if len(warnings) == 1 else 's'})."
        )

    return QualityReport(
        passed=passed,
        status=status,
        message=message,
        error_count=len(errors),
        warning_count=len(warnings),
        checks=checks,
        seasons=list(seasons or []),
    )


def load_frames_for_validation(
    seasons: list[int],
) -> dict[str, pd.DataFrame]:
    """Load persisted canonical tables used by quality checks."""

    from app.canonical.dim_game import get_dim_game
    from app.canonical.dim_player import get_dim_player
    from app.canonical.dim_team import get_dim_team
    from app.canonical.fact_player_game import get_fact_player_game
    from app.canonical.fact_player_usage import get_fact_player_usage

    return {
        "dim_team": get_dim_team(
            force_refresh=False,
            persist=False,
        ),
        "dim_player": get_dim_player(
            force_refresh=False,
            persist=False,
        ),
        "dim_game": get_dim_game(
            seasons,
            force_refresh=False,
            persist=False,
        ),
        "fact_player_game": get_fact_player_game(
            seasons,
            force_refresh=False,
            persist=False,
        ),
        "fact_player_usage": get_fact_player_usage(
            seasons,
            force_refresh=False,
            persist=False,
        ),
    }


def validate_ingested_seasons(
    seasons: list[int],
    *,
    current_season: int | None = None,
    require_core_facts: bool = True,
    frames: dict[str, pd.DataFrame] | None = None,
) -> QualityReport:
    loaded = frames or load_frames_for_validation(seasons)
    return validate_canonical_frames(
        loaded,
        seasons=seasons,
        current_season=current_season,
        require_core_facts=require_core_facts,
    )
