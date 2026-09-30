"""
fact_player_usage — position-aware opportunity / participation.

Grain: one player × one game.
InsightPilot owns player_id and game_id. Metrics are nullable
by design (RB/WR/TE/QB fields share one table).
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.canonical.dim_game import (
    game_id_lookup_from_dim,
    get_dim_game,
)
from app.canonical.dim_player import (
    get_dim_player,
    player_id_lookup_from_dim,
)
from app.canonical.ids import (
    game_resolution_key,
    make_game_id,
    make_player_id,
    make_team_id,
    player_resolution_key,
)
from app.canonical.schema import FANTASY_SCHEMA
from app.database import engine


_FACT_PLAYER_USAGE_CACHE: pd.DataFrame | None = None
_FACT_PLAYER_USAGE_CACHE_WITH_KEYS: pd.DataFrame | None = None
_FACT_PLAYER_USAGE_CACHE_SEASONS: tuple[int, ...] | None = None

SKILL_POSITIONS = {"QB", "RB", "WR", "TE", "FB"}

FACT_PLAYER_USAGE_COLUMNS = [
    "player_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "team_id",
    "position",
    # Participation
    "snap_count",
    "offensive_snap_share",
    "routes_run",
    "route_participation_rate",
    # RB opportunity
    "rush_share",
    "touches",
    "touch_share",
    "red_zone_touches",
    "goal_line_carries",
    "inside_5_carries",
    # WR/TE opportunity
    "target_share",
    "air_yards",
    "air_yard_share",
    "red_zone_targets",
    "end_zone_targets",
    # QB opportunity
    "dropbacks",
    "designed_rush_attempts",
    "scrambles",
    "qb_rush_share",
    "deep_pass_attempts",
    "source_ids",
]


def _to_pandas(frame: Any) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    raise TypeError("Expected a pandas or polars DataFrame.")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _normalize_text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text_value = str(value).strip()
    if not text_value or text_value.lower() in {
        "nan",
        "none",
        "nat",
        "<na>",
    }:
        return None
    return text_value


def _sql_null_if_missing(value: Any) -> Any:
    if _is_missing(value):
        return None
    return value


def _normalize_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _season_type(value: Any) -> str | None:
    raw = _normalize_text(value)
    if raw is None:
        return None
    return raw.upper()


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    num = _normalize_float(numerator)
    den = _normalize_float(denominator)
    if num is None or den is None or den == 0:
        return None
    return num / den


def _load_player_stats(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(
        nfl.load_player_stats(
            seasons=seasons,
            summary_level="week",
        )
    )


def _load_snap_counts(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_snap_counts(seasons=seasons))


def _load_pbp(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    return _to_pandas(nfl.load_pbp(seasons=seasons))


def _load_participation(seasons: list[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    try:
        return _to_pandas(
            nfl.load_participation(seasons=seasons)
        )
    except Exception:
        return pd.DataFrame()


def _pfr_to_gsis_lookup(
    dim_player: pd.DataFrame | None = None,
) -> dict[str, str]:
    lookup: dict[str, str] = {}

    if dim_player is not None and not dim_player.empty:
        for record in dim_player.to_dict(orient="records"):
            source_ids = record.get("source_ids") or {}
            if isinstance(source_ids, str):
                try:
                    source_ids = json.loads(source_ids)
                except json.JSONDecodeError:
                    source_ids = {}
            if not isinstance(source_ids, dict):
                continue
            pfr_id = _normalize_text(source_ids.get("pfr_id"))
            gsis_id = _normalize_text(source_ids.get("gsis_id"))
            if pfr_id and gsis_id:
                lookup[pfr_id] = gsis_id

    if lookup:
        return lookup

    import nflreadpy as nfl

    ids = _to_pandas(nfl.load_ff_playerids())
    if ids.empty:
        return lookup
    pfr_col = next(
        (
            column
            for column in ("pfr_id", "pfr")
            if column in ids.columns
        ),
        None,
    )
    gsis_col = next(
        (
            column
            for column in ("gsis_id", "gsis")
            if column in ids.columns
        ),
        None,
    )
    if not pfr_col or not gsis_col:
        return lookup
    for record in ids.to_dict(orient="records"):
        pfr_id = _normalize_text(record.get(pfr_col))
        gsis_id = _normalize_text(record.get(gsis_col))
        if pfr_id and gsis_id:
            lookup[pfr_id] = gsis_id
    return lookup


def _snap_frame(
    snap_counts: pd.DataFrame,
    *,
    pfr_to_gsis: dict[str, str],
) -> pd.DataFrame:
    if snap_counts.empty:
        return pd.DataFrame(
            columns=[
                "gsis_id",
                "nflverse_game_id",
                "snap_count",
                "offensive_snap_share",
            ]
        )

    working = snap_counts.copy()
    working["pfr_player_id"] = working["pfr_player_id"].map(
        _normalize_text
    )
    working["gsis_id"] = working["pfr_player_id"].map(
        pfr_to_gsis
    )
    working = working[working["gsis_id"].notna()].copy()
    working["nflverse_game_id"] = working["game_id"].map(
        _normalize_text
    )
    working["snap_count"] = pd.to_numeric(
        working.get("offense_snaps"),
        errors="coerce",
    )
    working["offensive_snap_share"] = pd.to_numeric(
        working.get("offense_pct"),
        errors="coerce",
    )
    return (
        working[
            [
                "gsis_id",
                "nflverse_game_id",
                "snap_count",
                "offensive_snap_share",
            ]
        ]
        .drop_duplicates(
            subset=["gsis_id", "nflverse_game_id"],
            keep="last",
        )
        .reset_index(drop=True)
    )


def _snap_only_skill_spine(
    snap_counts: pd.DataFrame,
    *,
    pfr_to_gsis: dict[str, str],
    existing: pd.DataFrame,
) -> pd.DataFrame:
    """
    Skill players with offensive snaps but no box-score stats row.

    These are active zero-production weeks. Inactive players
    (no offensive snaps) are not invented.
    """

    if snap_counts is None or snap_counts.empty:
        return pd.DataFrame()

    working = snap_counts.copy()
    working["pfr_player_id"] = working.get(
        "pfr_player_id",
        pd.Series(dtype="object"),
    ).map(_normalize_text)
    working["gsis_id"] = working["pfr_player_id"].map(pfr_to_gsis)
    working["nflverse_game_id"] = working.get(
        "game_id",
        pd.Series(dtype="object"),
    ).map(_normalize_text)
    working["offense_snaps"] = pd.to_numeric(
        working.get("offense_snaps"),
        errors="coerce",
    ).fillna(0)
    working["position"] = (
        working.get("position", pd.Series(dtype="object"))
        .map(_normalize_text)
        .astype("string")
        .str.upper()
    )

    working = working[
        working["gsis_id"].notna()
        & working["nflverse_game_id"].notna()
        & (working["offense_snaps"] > 0)
        & working["position"].isin(SKILL_POSITIONS)
    ].copy()
    if working.empty:
        return pd.DataFrame()

    if not existing.empty:
        existing_keys = {
            f"{_normalize_text(gsis)}|{_normalize_text(game)}"
            for gsis, game in zip(
                existing["gsis_id"].tolist(),
                existing["nflverse_game_id"].tolist(),
            )
            if _normalize_text(gsis) and _normalize_text(game)
        }
        working["_key"] = (
            working["gsis_id"].map(_normalize_text).astype(str)
            + "|"
            + working["nflverse_game_id"]
            .map(_normalize_text)
            .astype(str)
        )
        working = working[
            ~working["_key"].isin(existing_keys)
        ].drop(columns=["_key"])
    if working.empty:
        return pd.DataFrame()

    working = working.drop_duplicates(
        subset=["gsis_id", "nflverse_game_id"],
        keep="last",
    )
    # Shape like nflverse weekly stats spine fields used downstream.
    out = pd.DataFrame(
        {
            "player_id": working["gsis_id"],
            "game_id": working["nflverse_game_id"],
            "gsis_id": working["gsis_id"],
            "nflverse_game_id": working["nflverse_game_id"],
            "season": working.get("season"),
            "week": working.get("week"),
            "season_type": working.get(
                "game_type",
                working.get("season_type"),
            ),
            "team": working.get("team"),
            "position": working["position"],
            "carries": 0,
            "receptions": 0,
            "targets": 0,
            "target_share": None,
            "receiving_air_yards": None,
            "air_yards_share": None,
        }
    )
    return out.reset_index(drop=True)


def _aggregate_pbp_usage(
    pbp: pd.DataFrame,
) -> pd.DataFrame:
    if pbp.empty:
        return pd.DataFrame()

    plays = pbp.copy()
    plays["game_id"] = plays["game_id"].map(_normalize_text)
    plays["yardline_100"] = pd.to_numeric(
        plays.get("yardline_100"),
        errors="coerce",
    )
    plays["air_yards"] = pd.to_numeric(
        plays.get("air_yards"),
        errors="coerce",
    )
    for flag in (
        "rush_attempt",
        "pass_attempt",
        "qb_dropback",
        "qb_scramble",
        "complete_pass",
    ):
        if flag in plays.columns:
            plays[flag] = pd.to_numeric(
                plays[flag],
                errors="coerce",
            ).fillna(0)

    # Rushing opportunity (RB / anyone who rushes).
    rush = plays[
        (plays.get("rush_attempt", 0) == 1)
        & plays["rusher_player_id"].notna()
    ].copy()
    if not rush.empty:
        rush["gsis_id"] = rush["rusher_player_id"].map(
            _normalize_text
        )
        rush["is_red_zone"] = rush["yardline_100"] <= 20
        rush["is_goal_line"] = rush["yardline_100"] <= 10
        rush["is_inside_5"] = rush["yardline_100"] <= 5
        rush_group = (
            rush.groupby(["gsis_id", "game_id"], dropna=True)
            .agg(
                rush_attempts=("gsis_id", "size"),
                red_zone_rushes=("is_red_zone", "sum"),
                goal_line_carries=("is_goal_line", "sum"),
                inside_5_carries=("is_inside_5", "sum"),
            )
            .reset_index()
        )
    else:
        rush_group = pd.DataFrame(
            columns=[
                "gsis_id",
                "game_id",
                "rush_attempts",
                "red_zone_rushes",
                "goal_line_carries",
                "inside_5_carries",
            ]
        )

    # Receiving targets.
    targets = plays[
        (plays.get("pass_attempt", 0) == 1)
        & plays["receiver_player_id"].notna()
    ].copy()
    if not targets.empty:
        targets["gsis_id"] = targets["receiver_player_id"].map(
            _normalize_text
        )
        targets["is_red_zone"] = targets["yardline_100"] <= 20
        targets["is_end_zone"] = (
            targets["air_yards"].notna()
            & targets["yardline_100"].notna()
            & (targets["air_yards"] >= targets["yardline_100"])
        )
        target_group = (
            targets.groupby(["gsis_id", "game_id"], dropna=True)
            .agg(
                targets=("gsis_id", "size"),
                red_zone_targets=("is_red_zone", "sum"),
                end_zone_targets=("is_end_zone", "sum"),
                receptions=(
                    "complete_pass",
                    "sum",
                ),
            )
            .reset_index()
        )
    else:
        target_group = pd.DataFrame(
            columns=[
                "gsis_id",
                "game_id",
                "targets",
                "red_zone_targets",
                "end_zone_targets",
                "receptions",
            ]
        )

    # QB opportunity.
    dropbacks = plays[
        (plays.get("qb_dropback", 0) == 1)
        & plays["passer_player_id"].notna()
    ].copy()
    if not dropbacks.empty:
        dropbacks["gsis_id"] = dropbacks["passer_player_id"].map(
            _normalize_text
        )
        dropback_group = (
            dropbacks.groupby(["gsis_id", "game_id"], dropna=True)
            .size()
            .reset_index(name="dropbacks")
        )
    else:
        dropback_group = pd.DataFrame(
            columns=["gsis_id", "game_id", "dropbacks"]
        )

    deep = plays[
        (plays.get("pass_attempt", 0) == 1)
        & plays["passer_player_id"].notna()
        & (plays["air_yards"] >= 20)
    ].copy()
    if not deep.empty:
        deep["gsis_id"] = deep["passer_player_id"].map(
            _normalize_text
        )
        deep_group = (
            deep.groupby(["gsis_id", "game_id"], dropna=True)
            .size()
            .reset_index(name="deep_pass_attempts")
        )
    else:
        deep_group = pd.DataFrame(
            columns=["gsis_id", "game_id", "deep_pass_attempts"]
        )

    scrambles = plays[
        (plays.get("qb_scramble", 0) == 1)
        & plays["rusher_player_id"].notna()
    ].copy()
    if not scrambles.empty:
        scrambles["gsis_id"] = scrambles["rusher_player_id"].map(
            _normalize_text
        )
        scramble_group = (
            scrambles.groupby(["gsis_id", "game_id"], dropna=True)
            .size()
            .reset_index(name="scrambles")
        )
    else:
        scramble_group = pd.DataFrame(
            columns=["gsis_id", "game_id", "scrambles"]
        )

    # Designed QB rushes: non-scramble rushes by a player who
    # also had dropbacks in the same game (QB identity proxy).
    designed_group = pd.DataFrame(
        columns=[
            "gsis_id",
            "game_id",
            "designed_rush_attempts",
        ]
    )
    if not rush.empty and not dropbacks.empty:
        qb_by_game = (
            dropbacks.assign(
                gsis_id=dropbacks["passer_player_id"].map(
                    _normalize_text
                )
            )[["gsis_id", "game_id"]]
            .dropna()
            .drop_duplicates()
        )
        designed_qb = rush[
            (rush.get("qb_scramble", 0) != 1)
        ].copy()
        designed_qb["gsis_id"] = designed_qb[
            "rusher_player_id"
        ].map(_normalize_text)
        designed_qb = designed_qb.merge(
            qb_by_game,
            on=["gsis_id", "game_id"],
            how="inner",
        )
        if not designed_qb.empty:
            designed_group = (
                designed_qb.groupby(
                    ["gsis_id", "game_id"],
                    dropna=True,
                )
                .size()
                .reset_index(name="designed_rush_attempts")
            )

    # Team rush totals for shares.
    team_rush = (
        rush.groupby(["game_id", "posteam"], dropna=True)
        .size()
        .reset_index(name="team_rush_attempts")
        if not rush.empty and "posteam" in rush.columns
        else pd.DataFrame(
            columns=[
                "game_id",
                "posteam",
                "team_rush_attempts",
            ]
        )
    )

    merged = rush_group.merge(
        target_group,
        on=["gsis_id", "game_id"],
        how="outer",
    )
    for frame in (
        dropback_group,
        deep_group,
        scramble_group,
        designed_group,
    ):
        merged = merged.merge(
            frame,
            on=["gsis_id", "game_id"],
            how="outer",
        )

    # Attach posteam from any role for team share joins.
    identity_parts = []
    for role_col, frame in (
        ("rusher_player_id", rush),
        ("receiver_player_id", targets),
        ("passer_player_id", dropbacks),
    ):
        if frame.empty or "posteam" not in frame.columns:
            continue
        part = frame[
            [role_col, "game_id", "posteam"]
        ].copy()
        part["gsis_id"] = part[role_col].map(_normalize_text)
        identity_parts.append(
            part[["gsis_id", "game_id", "posteam"]]
        )
    if identity_parts:
        identity = (
            pd.concat(identity_parts, ignore_index=True)
            .dropna(subset=["gsis_id", "game_id"])
            .drop_duplicates(
                subset=["gsis_id", "game_id"],
                keep="last",
            )
        )
        merged = merged.merge(
            identity,
            on=["gsis_id", "game_id"],
            how="left",
        )
        if not team_rush.empty:
            merged = merged.merge(
                team_rush,
                on=["game_id", "posteam"],
                how="left",
            )

    # Red-zone touches = RZ rushes + RZ receptions (completed targets).
    if "red_zone_rushes" not in merged.columns:
        merged["red_zone_rushes"] = 0
    if "receptions" not in merged.columns:
        merged["receptions"] = 0
    if "red_zone_targets" not in merged.columns:
        merged["red_zone_targets"] = 0

    # Approximate RZ receptions from complete passes in RZ via targets frame.
    if not targets.empty:
        rz_rec = targets[
            targets["is_red_zone"]
            & (targets.get("complete_pass", 0) == 1)
        ].copy()
        if not rz_rec.empty:
            rz_rec_group = (
                rz_rec.groupby(
                    ["gsis_id", "game_id"],
                    dropna=True,
                )
                .size()
                .reset_index(name="red_zone_receptions")
            )
            merged = merged.merge(
                rz_rec_group,
                on=["gsis_id", "game_id"],
                how="left",
            )
        else:
            merged["red_zone_receptions"] = 0
    else:
        merged["red_zone_receptions"] = 0

    merged["red_zone_touches"] = (
        merged["red_zone_rushes"].fillna(0)
        + merged["red_zone_receptions"].fillna(0)
    )

    return merged


def _aggregate_routes(
    participation: pd.DataFrame,
    pbp: pd.DataFrame,
) -> pd.DataFrame:
    """
    Proxy routes_run: offensive pass plays where the player
    appears in participation.offense_players.
    """

    if participation.empty or pbp.empty:
        return pd.DataFrame(
            columns=[
                "gsis_id",
                "game_id",
                "routes_run",
                "team_pass_plays",
            ]
        )

    pass_plays = pbp[
        (pd.to_numeric(pbp.get("pass"), errors="coerce").fillna(0) == 1)
        | (pd.to_numeric(pbp.get("qb_dropback"), errors="coerce").fillna(0) == 1)
    ][["game_id", "play_id", "posteam"]].copy()
    pass_plays["game_id"] = pass_plays["game_id"].map(
        _normalize_text
    )
    pass_plays["play_id"] = pd.to_numeric(
        pass_plays["play_id"],
        errors="coerce",
    )

    part = participation.copy()
    game_col = (
        "nflverse_game_id"
        if "nflverse_game_id" in part.columns
        else "game_id"
    )
    part["game_id"] = part[game_col].map(_normalize_text)
    part["play_id"] = pd.to_numeric(
        part.get("play_id"),
        errors="coerce",
    )
    part = part.merge(
        pass_plays,
        on=["game_id", "play_id"],
        how="inner",
    )
    if part.empty or "offense_players" not in part.columns:
        return pd.DataFrame(
            columns=[
                "gsis_id",
                "game_id",
                "routes_run",
                "team_pass_plays",
            ]
        )

    part["offense_players"] = part["offense_players"].fillna("")
    exploded = part.assign(
        gsis_id=part["offense_players"].str.split(";")
    ).explode("gsis_id")
    exploded["gsis_id"] = exploded["gsis_id"].map(_normalize_text)
    exploded = exploded[exploded["gsis_id"].notna()]

    routes = (
        exploded.groupby(["gsis_id", "game_id"], dropna=True)
        .size()
        .reset_index(name="routes_run")
    )
    team_pass = (
        pass_plays.groupby(["game_id", "posteam"], dropna=True)
        .size()
        .reset_index(name="team_pass_plays")
    )
    # Attach posteam for rate.
    posteam_map = (
        exploded.groupby(["gsis_id", "game_id"], dropna=True)[
            "posteam"
        ]
        .agg(lambda values: values.dropna().iloc[0] if len(values.dropna()) else None)
        .reset_index()
    )
    routes = routes.merge(
        posteam_map,
        on=["gsis_id", "game_id"],
        how="left",
    ).merge(
        team_pass,
        on=["game_id", "posteam"],
        how="left",
    )
    return routes


def build_fact_player_usage(
    seasons: list[int],
    *,
    persist: bool = True,
    source_frames: dict[str, pd.DataFrame] | None = None,
    player_id_lookup: dict[str, str] | None = None,
    game_id_lookup: dict[str, str] | None = None,
) -> pd.DataFrame:
    if not seasons:
        raise ValueError("At least one season is required.")

    resolved_seasons = sorted({int(season) for season in seasons})
    raw = source_frames or {}
    stats = raw.get("player_stats")
    if stats is None:
        stats = _load_player_stats(resolved_seasons)
    else:
        stats = stats.copy()
    if stats.empty:
        raise ValueError(
            "Unable to build fact_player_usage: no player "
            "stats rows were available."
        )

    snap_counts = raw.get("snap_counts")
    if snap_counts is None:
        snap_counts = _load_snap_counts(resolved_seasons)
    else:
        snap_counts = snap_counts.copy()

    pbp = raw.get("pbp")
    if pbp is None:
        pbp = _load_pbp(resolved_seasons)
    else:
        pbp = pbp.copy()

    participation = raw.get("participation")
    if participation is None and source_frames is None:
        participation = _load_participation(resolved_seasons)
    elif participation is None:
        participation = pd.DataFrame()
    else:
        participation = participation.copy()

    dim_player = None
    if player_id_lookup is None:
        dim_player = get_dim_player(
            force_refresh=False,
            persist=persist,
        )
        player_lookup = player_id_lookup_from_dim(dim_player)
    else:
        player_lookup = player_id_lookup

    if game_id_lookup is None:
        dim_game = get_dim_game(
            seasons=resolved_seasons,
            force_refresh=False,
            persist=persist,
        )
        game_lookup = game_id_lookup_from_dim(dim_game)
    else:
        game_lookup = game_id_lookup

    pfr_to_gsis = _pfr_to_gsis_lookup(dim_player)
    snaps = _snap_frame(snap_counts, pfr_to_gsis=pfr_to_gsis)
    pbp_usage = _aggregate_pbp_usage(pbp)
    route_usage = _aggregate_routes(participation, pbp)

    # Spine: skill-position weekly rows from box-score stats,
    # plus snap-active players missing from stats (active zeros).
    spine = stats.copy()
    if "position" in spine.columns:
        spine = spine[
            spine["position"]
            .astype("string")
            .str.upper()
            .isin(SKILL_POSITIONS)
        ].copy()

    spine["gsis_id"] = spine["player_id"].map(_normalize_text)
    spine["nflverse_game_id"] = spine["game_id"].map(
        _normalize_text
    )
    spine = spine[
        spine["gsis_id"].notna()
        & spine["nflverse_game_id"].notna()
    ].copy()

    snap_only = _snap_only_skill_spine(
        snap_counts,
        pfr_to_gsis=pfr_to_gsis,
        existing=spine,
    )
    if not snap_only.empty:
        spine = pd.concat(
            [spine, snap_only],
            ignore_index=True,
            sort=False,
        )

    if spine.empty:
        raise ValueError(
            "Unable to build fact_player_usage: no skill-position "
            "player×game rows."
        )

    spine = spine.merge(
        snaps,
        on=["gsis_id", "nflverse_game_id"],
        how="left",
    )
    if not pbp_usage.empty:
        spine = spine.merge(
            pbp_usage.rename(
                columns={"game_id": "nflverse_game_id"}
            ),
            on=["gsis_id", "nflverse_game_id"],
            how="left",
            suffixes=("", "_pbp"),
        )
    if not route_usage.empty:
        spine = spine.merge(
            route_usage.rename(
                columns={"game_id": "nflverse_game_id"}
            ),
            on=["gsis_id", "nflverse_game_id"],
            how="left",
            suffixes=("", "_route"),
        )

    # Team totals from weekly stats for rush/touch share.
    spine["carries"] = pd.to_numeric(
        spine.get("carries"),
        errors="coerce",
    ).fillna(0)
    spine["receptions_stat"] = pd.to_numeric(
        spine.get("receptions"),
        errors="coerce",
    ).fillna(0)
    spine["touches_stat"] = (
        spine["carries"] + spine["receptions_stat"]
    )
    team_totals = (
        spine.groupby(
            ["nflverse_game_id", "team"],
            dropna=True,
        )
        .agg(
            team_carries=("carries", "sum"),
            team_touches=("touches_stat", "sum"),
        )
        .reset_index()
    )
    spine = spine.merge(
        team_totals,
        on=["nflverse_game_id", "team"],
        how="left",
    )

    records: list[dict[str, Any]] = []
    for row in spine.to_dict(orient="records"):
        gsis_id = _normalize_text(row.get("gsis_id"))
        nflverse_game_id = _normalize_text(
            row.get("nflverse_game_id")
        )
        if not gsis_id or not nflverse_game_id:
            continue

        player_id = player_lookup.get(gsis_id)
        if player_id is None:
            try:
                player_id = make_player_id(
                    player_resolution_key(gsis_id=gsis_id)
                )
            except ValueError:
                continue

        game_id = game_lookup.get(nflverse_game_id)
        if game_id is None:
            try:
                game_id = make_game_id(
                    game_resolution_key(
                        nflverse_game_id=nflverse_game_id,
                    )
                )
            except ValueError:
                continue

        team_abbr = (
            _normalize_text(row.get("team")) or ""
        ).upper() or None
        position = (
            _normalize_text(row.get("position")) or ""
        ).upper() or None

        carries = _normalize_float(row.get("carries")) or 0.0
        receptions = (
            _normalize_float(row.get("receptions_stat")) or 0.0
        )
        touches = carries + receptions
        team_carries = _normalize_float(row.get("team_carries"))
        team_touches = _normalize_float(row.get("team_touches"))
        team_rush_attempts = _normalize_float(
            row.get("team_rush_attempts")
        )
        routes_run = _normalize_int(row.get("routes_run"))
        team_pass_plays = _normalize_float(
            row.get("team_pass_plays")
        )

        qb_rushes = (
            (_normalize_float(row.get("designed_rush_attempts")) or 0.0)
            + (_normalize_float(row.get("scrambles")) or 0.0)
        )

        records.append(
            {
                "player_id": player_id,
                "game_id": game_id,
                "season": _normalize_int(row.get("season")),
                "week": _normalize_int(row.get("week")),
                "season_type": _season_type(
                    row.get("season_type")
                ),
                "team_id": (
                    make_team_id(team_abbr)
                    if team_abbr
                    else None
                ),
                "position": position,
                "snap_count": _normalize_int(
                    row.get("snap_count")
                ),
                "offensive_snap_share": _normalize_float(
                    row.get("offensive_snap_share")
                ),
                "routes_run": routes_run,
                "route_participation_rate": _safe_div(
                    routes_run,
                    team_pass_plays,
                ),
                "rush_share": _safe_div(
                    carries,
                    team_carries,
                ),
                "touches": _normalize_int(touches),
                "touch_share": _safe_div(
                    touches,
                    team_touches,
                ),
                "red_zone_touches": _normalize_int(
                    row.get("red_zone_touches")
                ),
                "goal_line_carries": _normalize_int(
                    row.get("goal_line_carries")
                ),
                "inside_5_carries": _normalize_int(
                    row.get("inside_5_carries")
                ),
                "target_share": _normalize_float(
                    row.get("target_share")
                ),
                "air_yards": _normalize_int(
                    row.get("receiving_air_yards")
                ),
                "air_yard_share": _normalize_float(
                    row.get("air_yards_share")
                ),
                "red_zone_targets": _normalize_int(
                    row.get("red_zone_targets")
                ),
                "end_zone_targets": _normalize_int(
                    row.get("end_zone_targets")
                ),
                "dropbacks": _normalize_int(
                    row.get("dropbacks")
                ),
                "designed_rush_attempts": _normalize_int(
                    row.get("designed_rush_attempts")
                ),
                "scrambles": _normalize_int(
                    row.get("scrambles")
                ),
                "qb_rush_share": _safe_div(
                    qb_rushes,
                    team_rush_attempts
                    if team_rush_attempts is not None
                    else team_carries,
                ),
                "deep_pass_attempts": _normalize_int(
                    row.get("deep_pass_attempts")
                ),
                "source_ids": {
                    "gsis_id": gsis_id,
                    "nflverse_game_id": nflverse_game_id,
                },
                "resolution_key": (
                    f"{gsis_id}:{nflverse_game_id}"
                ),
            }
        )

    if not records:
        raise ValueError(
            "Unable to build fact_player_usage: no resolvable "
            "player×game rows."
        )

    fact = pd.DataFrame.from_records(records)
    for column in FACT_PLAYER_USAGE_COLUMNS + ["resolution_key"]:
        if column == "source_ids" or column not in fact.columns:
            continue
        fact[column] = fact[column].astype("object")
        fact[column] = fact[column].where(
            fact[column].notna(),
            None,
        )

    fact = fact.drop_duplicates(
        subset=["player_id", "game_id"],
        keep="last",
    ).reset_index(drop=True)

    global _FACT_PLAYER_USAGE_CACHE
    global _FACT_PLAYER_USAGE_CACHE_WITH_KEYS
    global _FACT_PLAYER_USAGE_CACHE_SEASONS
    _FACT_PLAYER_USAGE_CACHE_WITH_KEYS = fact.copy()
    _FACT_PLAYER_USAGE_CACHE_SEASONS = tuple(resolved_seasons)

    if persist:
        upsert_fact_player_usage(fact)

    output = fact[FACT_PLAYER_USAGE_COLUMNS].copy()
    output["source_ids"] = output["source_ids"].map(
        lambda value: json.dumps(value, sort_keys=True)
        if isinstance(value, dict)
        else value
    )
    output = output.sort_values(
        ["season", "week", "player_id", "game_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    _FACT_PLAYER_USAGE_CACHE = output.copy()
    return output


def fact_player_usage_count() -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {FANTASY_SCHEMA}.fact_player_usage"
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


def get_fact_player_usage(
    seasons: list[int] | None = None,
    *,
    force_refresh: bool = False,
    persist: bool = False,
) -> pd.DataFrame:
    global _FACT_PLAYER_USAGE_CACHE
    global _FACT_PLAYER_USAGE_CACHE_SEASONS

    import nflreadpy as nfl

    current = int(nfl.get_current_season())
    if seasons is None:
        resolved = [current]
    else:
        resolved = sorted({int(season) for season in seasons})

    if (
        not force_refresh
        and _FACT_PLAYER_USAGE_CACHE is not None
        and not _FACT_PLAYER_USAGE_CACHE.empty
        and _FACT_PLAYER_USAGE_CACHE_SEASONS == tuple(resolved)
    ):
        return _FACT_PLAYER_USAGE_CACHE.copy()

    if not force_refresh and fact_player_usage_count() > 0:
        frame = load_fact_player_usage_from_db(seasons=resolved)
        if not frame.empty:
            _FACT_PLAYER_USAGE_CACHE = frame.copy()
            _FACT_PLAYER_USAGE_CACHE_SEASONS = tuple(resolved)
            return frame

    return build_fact_player_usage(
        resolved,
        persist=persist,
    )


def upsert_fact_player_usage(
    fact: pd.DataFrame,
) -> None:
    if fact.empty:
        return

    statement = text(
        f"""
        INSERT INTO {FANTASY_SCHEMA}.fact_player_usage (
            player_id,
            game_id,
            season,
            week,
            season_type,
            team_id,
            position,
            snap_count,
            offensive_snap_share,
            routes_run,
            route_participation_rate,
            rush_share,
            touches,
            touch_share,
            red_zone_touches,
            goal_line_carries,
            inside_5_carries,
            target_share,
            air_yards,
            air_yard_share,
            red_zone_targets,
            end_zone_targets,
            dropbacks,
            designed_rush_attempts,
            scrambles,
            qb_rush_share,
            deep_pass_attempts,
            source_ids,
            resolution_key,
            updated_at
        ) VALUES (
            :player_id,
            :game_id,
            :season,
            :week,
            :season_type,
            :team_id,
            :position,
            :snap_count,
            :offensive_snap_share,
            :routes_run,
            :route_participation_rate,
            :rush_share,
            :touches,
            :touch_share,
            :red_zone_touches,
            :goal_line_carries,
            :inside_5_carries,
            :target_share,
            :air_yards,
            :air_yard_share,
            :red_zone_targets,
            :end_zone_targets,
            :dropbacks,
            :designed_rush_attempts,
            :scrambles,
            :qb_rush_share,
            :deep_pass_attempts,
            CAST(:source_ids AS JSONB),
            :resolution_key,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (resolution_key) DO UPDATE SET
            player_id = EXCLUDED.player_id,
            game_id = EXCLUDED.game_id,
            season = EXCLUDED.season,
            week = EXCLUDED.week,
            season_type = EXCLUDED.season_type,
            team_id = EXCLUDED.team_id,
            position = EXCLUDED.position,
            snap_count = EXCLUDED.snap_count,
            offensive_snap_share = EXCLUDED.offensive_snap_share,
            routes_run = EXCLUDED.routes_run,
            route_participation_rate = EXCLUDED.route_participation_rate,
            rush_share = EXCLUDED.rush_share,
            touches = EXCLUDED.touches,
            touch_share = EXCLUDED.touch_share,
            red_zone_touches = EXCLUDED.red_zone_touches,
            goal_line_carries = EXCLUDED.goal_line_carries,
            inside_5_carries = EXCLUDED.inside_5_carries,
            target_share = EXCLUDED.target_share,
            air_yards = EXCLUDED.air_yards,
            air_yard_share = EXCLUDED.air_yard_share,
            red_zone_targets = EXCLUDED.red_zone_targets,
            end_zone_targets = EXCLUDED.end_zone_targets,
            dropbacks = EXCLUDED.dropbacks,
            designed_rush_attempts = EXCLUDED.designed_rush_attempts,
            scrambles = EXCLUDED.scrambles,
            qb_rush_share = EXCLUDED.qb_rush_share,
            deep_pass_attempts = EXCLUDED.deep_pass_attempts,
            source_ids = EXCLUDED.source_ids,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    rows = []
    for record in fact.to_dict(orient="records"):
        source_ids = record.get("source_ids") or {}
        if not isinstance(source_ids, str):
            source_ids = json.dumps(
                source_ids,
                sort_keys=True,
            )
        row = {
            "player_id": record["player_id"],
            "game_id": record["game_id"],
            "resolution_key": record["resolution_key"],
            "source_ids": source_ids,
        }
        for column in FACT_PLAYER_USAGE_COLUMNS:
            if column in {
                "player_id",
                "game_id",
                "source_ids",
            }:
                continue
            row[column] = _sql_null_if_missing(
                record.get(column)
            )
        rows.append(row)

    batch_size = 1000
    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            connection.execute(
                statement,
                rows[start:start + batch_size],
            )


def load_fact_player_usage_from_db(
    seasons: list[int] | None = None,
) -> pd.DataFrame:
    columns = ", ".join(FACT_PLAYER_USAGE_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {FANTASY_SCHEMA}.fact_player_usage
        ORDER BY season, week, player_id, game_id
    """

    with engine.connect() as connection:
        frame = pd.read_sql_query(
            text(query),
            connection,
        )

    if seasons and not frame.empty and "season" in frame.columns:
        allowed = {int(season) for season in seasons}
        frame = frame[
            frame["season"].map(
                lambda value: (
                    int(value) in allowed
                    if not _is_missing(value)
                    else False
                )
            )
        ].reset_index(drop=True)

    if "source_ids" in frame.columns:
        frame["source_ids"] = frame["source_ids"].map(
            lambda value: (
                json.dumps(value, sort_keys=True)
                if isinstance(value, dict)
                else value
            )
        )
    return frame
