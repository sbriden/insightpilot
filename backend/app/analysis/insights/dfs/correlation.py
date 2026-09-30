"""
DFS Player Correlation Engine
=============================

Reusable pairwise correlation for lineup construction and
portfolio analysis. Sport-agnostic API; NFL structural rules
are the first concrete implementation (Showdown + classic).

Pipeline
--------
    Slate players (+ optional game script)
            │
            ▼
    build_correlation_context(...)
      • structural NFL rules (QB↔WR, RB committee, …)
      • optional empirical overlays (historical)
      • confidence from evidence quality
            │
            ▼
    selection_boost / score_lineup_correlation
            │
            ▼
    Optimizer fill + portfolio reporting

Score convention
----------------
    -1.0  strongly negative
     0.0  neutral / unrelated
    +1.0  strongly positive

Design rules
------------
1. Never binary-ban combinations — correlation is a weighted
   input, not a hard filter (unless a caller adds constraints).
2. Prefer structural relationships when sample size is thin.
3. Empirical overlays must carry confidence and can be
   invalidated when teammates / teams change.
4. Explain every non-neutral edge via ``correlation_reason``.

Tunable weights live in ``CorrelationConfig``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrelationConfig:
    """Tunable correlation engine parameters."""

    # Structural NFL magnitudes (before confidence dampening).
    qb_own_wr1: float = 0.78
    qb_own_wr2: float = 0.62
    qb_own_wr_depth: float = 0.42
    qb_own_te1: float = 0.58
    qb_own_te_depth: float = 0.32
    qb_opp_pass_catcher: float = 0.38
    qb_opp_dst: float = -0.68
    skill_opp_dst: float = -0.48
    rb_committee: float = -0.55
    rb_own_dst: float = 0.36
    wr_opp_wr: float = 0.32
    wr_same_team_compete: float = -0.18
    kicker_own_offense: float = 0.22
    qb_own_dst: float = 0.12  # mild / context-dependent

    # Selection boost: maps mean pair score [-1,1] → opt-score units
    # before strategy correlation weight is applied by the caller.
    selection_scale: float = 55.0

    # Lineup aggregate: soft-penalize over-concentration on one axis.
    concentration_pair_threshold: float = 0.55
    concentration_penalty_per_extra: float = 0.08
    max_concentration_penalty: float = 0.35

    # Confidence labels from continuous score.
    confidence_high: float = 0.75
    confidence_moderate: float = 0.45

    # Empirical blend (when historical rows present).
    empirical_weight_cap: float = 0.55
    min_empirical_games: int = 6

    # Soft lineup preference knobs (penalties, not hard bans).
    max_same_team_soft: int | None = 4
    max_same_game_soft: int | None = None  # showdown: all same game
    soft_constraint_penalty: float = 0.12


# Contest-type preference profiles (documentation + callers).
CORRELATION_CONSTRAINT_PROFILES: dict[str, dict[str, Any]] = {
    "cash": {
        "max_same_team_soft": 3,
        "prefer_positive": False,
        "notes": "Projection / floor first; mild correlation.",
    },
    "gpp": {
        "max_same_team_soft": 4,
        "prefer_positive": True,
        "notes": "Ceiling stacks + leverage; allow concentration.",
    },
    "showdown": {
        "max_same_team_soft": 5,
        "prefer_positive": True,
        "notes": "Game-script correlation + CPT relationships.",
    },
}


DEFAULT_CORRELATION_CONFIG = CorrelationConfig()


PASS_CATCHERS = frozenset({"WR", "TE"})
SKILL = frozenset({"QB", "RB", "WR", "TE", "K"})
DST = frozenset({"DEF", "DST"})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CorrelationEdge:
    player_id: str
    correlated_player_id: str
    correlation_type: str  # positive | negative | neutral
    correlation_score: float
    correlation_reason: str
    confidence: str  # High | Moderate | Low | Very Low
    confidence_score: float
    source: str  # structural | empirical | blended
    game_id: str | None = None
    season: int | None = None
    week: int | None = None
    rule_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CorrelationContext:
    """Precomputed pair matrix for one slate / game window."""

    edges: dict[tuple[str, str], CorrelationEdge] = field(
        default_factory=dict
    )
    players_by_id: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )
    config: CorrelationConfig = field(
        default_factory=lambda: DEFAULT_CORRELATION_CONFIG
    )
    sport: str = "nfl"
    game_script_id: str | None = None

    def get_edge(
        self,
        left_id: str,
        right_id: str,
    ) -> CorrelationEdge | None:
        a, b = str(left_id), str(right_id)
        if a == b:
            return None
        return self.edges.get(_pair_key(a, b))

    def selection_delta(
        self,
        candidate: dict[str, Any],
        selected: list[dict[str, Any]],
        *,
        correlation_weight: float = 1.0,
    ) -> float:
        """
        Opt-score adjustment for adding ``candidate`` given
        already-selected players. Positive when the candidate
        stacks well; negative when it conflicts.
        """

        if not selected or correlation_weight <= 0:
            return 0.0
        cid = str(candidate.get("player_id") or "")
        if not cid:
            return 0.0
        scored: list[float] = []
        for other in selected:
            oid = str(other.get("player_id") or "")
            edge = self.get_edge(cid, oid)
            if edge is None:
                continue
            scored.append(
                float(edge.correlation_score)
                * float(edge.confidence_score)
            )
        if not scored:
            return 0.0
        mean = sum(scored) / float(len(scored))
        return (
            mean
            * self.config.selection_scale
            * float(correlation_weight)
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_correlation_context(
    players: list[dict[str, Any]],
    *,
    sport: str = "nfl",
    season: int | None = None,
    week: int | None = None,
    game_id: str | None = None,
    game_script_id: str | None = None,
    empirical_rows: list[dict[str, Any]] | None = None,
    config: CorrelationConfig | None = None,
) -> CorrelationContext:
    """
    Build a reusable correlation matrix for the given player pool.

    Structural NFL rules always run. Empirical rows (optional)
    blend in when confidence-worthy.
    """

    cfg = config or DEFAULT_CORRELATION_CONFIG
    sport_key = str(sport or "nfl").strip().lower()
    by_id = {
        str(player.get("player_id")): player
        for player in players
        if player.get("player_id")
    }
    ctx = CorrelationContext(
        players_by_id=by_id,
        config=cfg,
        sport=sport_key,
        game_script_id=(
            str(game_script_id).strip() if game_script_id else None
        ),
    )
    ids = list(by_id.keys())
    for i, left_id in enumerate(ids):
        for right_id in ids[i + 1 :]:
            left = by_id[left_id]
            right = by_id[right_id]
            if sport_key == "nfl":
                edge = _structural_nfl_pair(
                    left,
                    right,
                    season=season,
                    week=week,
                    game_id=game_id,
                    game_script_id=ctx.game_script_id,
                    config=cfg,
                )
            else:
                edge = _neutral_edge(
                    left_id,
                    right_id,
                    reason=(
                        f"No structural rules for sport={sport_key}."
                    ),
                    season=season,
                    week=week,
                    game_id=game_id,
                )
            if edge is not None and abs(edge.correlation_score) >= 0.05:
                ctx.edges[_pair_key(left_id, right_id)] = edge

    if empirical_rows:
        _apply_empirical_overlays(
            ctx,
            empirical_rows,
            config=cfg,
            season=season,
            week=week,
            game_id=game_id,
        )

    # Mild game-script amplification for known archetypes.
    if ctx.game_script_id:
        _apply_script_modifiers(ctx, config=cfg)

    return ctx


def score_lineup_correlation(
    players: list[dict[str, Any]],
    context: CorrelationContext,
) -> dict[str, Any]:
    """
    Aggregate pairwise relationships inside one lineup.

    Returns net score plus explainable positive / negative pairs
    and a soft concentration penalty (not a hard ban).
    """

    ids = [
        str(player.get("player_id"))
        for player in players
        if player.get("player_id")
    ]
    pairs: list[dict[str, Any]] = []
    positive_sum = 0.0
    negative_sum = 0.0
    strong_positive = 0

    for i, left_id in enumerate(ids):
        for right_id in ids[i + 1 :]:
            edge = context.get_edge(left_id, right_id)
            if edge is None:
                continue
            payload = {
                "player_id": left_id,
                "correlated_player_id": right_id,
                "player_name": _name(context, left_id),
                "correlated_player_name": _name(context, right_id),
                "correlation_type": edge.correlation_type,
                "correlation_score": round(edge.correlation_score, 3),
                "confidence": edge.confidence,
                "confidence_score": round(edge.confidence_score, 3),
                "correlation_reason": edge.correlation_reason,
                "source": edge.source,
                "rule_id": edge.rule_id,
            }
            pairs.append(payload)
            if edge.correlation_score > 0:
                positive_sum += edge.correlation_score * edge.confidence_score
                if (
                    edge.correlation_score
                    >= context.config.concentration_pair_threshold
                ):
                    strong_positive += 1
            elif edge.correlation_score < 0:
                negative_sum += edge.correlation_score * edge.confidence_score

    extras = max(0, strong_positive - 2)
    concentration = min(
        context.config.max_concentration_penalty,
        extras * context.config.concentration_penalty_per_extra,
    )
    soft_penalty = _soft_constraint_penalty(players, context)
    net = positive_sum + negative_sum - concentration - soft_penalty
    pairs.sort(
        key=lambda row: (
            -abs(float(row["correlation_score"])),
            str(row["player_name"] or ""),
        )
    )
    return {
        "lineup_correlation_score": round(net, 3),
        "positive_correlation": round(positive_sum, 3),
        "negative_correlation": round(negative_sum, 3),
        "concentration_penalty": round(concentration, 3),
        "soft_constraint_penalty": round(soft_penalty, 3),
        "pair_count": len(pairs),
        "pairs": pairs,
        "positive_pairs": [
            row for row in pairs if float(row["correlation_score"]) > 0
        ][:12],
        "negative_pairs": [
            row for row in pairs if float(row["correlation_score"]) < 0
        ][:12],
    }


def summarize_portfolio_correlations(
    lineups: list[dict[str, Any]],
    context: CorrelationContext,
) -> dict[str, Any]:
    """
    Portfolio-level exposure of notable positive / negative pairs.
    """

    n = max(len(lineups), 1)
    pos_counts: dict[tuple[str, str], dict[str, Any]] = {}
    neg_counts: dict[tuple[str, str], dict[str, Any]] = {}

    for lineup in lineups:
        players = list(lineup.get("players") or [])
        scored = score_lineup_correlation(players, context)
        seen_pos: set[tuple[str, str]] = set()
        seen_neg: set[tuple[str, str]] = set()
        for row in scored.get("pairs") or []:
            key = _pair_key(
                str(row["player_id"]),
                str(row["correlated_player_id"]),
            )
            score = float(row["correlation_score"])
            if score >= 0.25 and key not in seen_pos:
                seen_pos.add(key)
                bucket = pos_counts.setdefault(
                    key,
                    {
                        "player_id": row["player_id"],
                        "correlated_player_id": row[
                            "correlated_player_id"
                        ],
                        "player_name": row["player_name"],
                        "correlated_player_name": row[
                            "correlated_player_name"
                        ],
                        "correlation_score": score,
                        "correlation_reason": row[
                            "correlation_reason"
                        ],
                        "lineups": 0,
                    },
                )
                bucket["lineups"] += 1
                bucket["correlation_score"] = max(
                    float(bucket["correlation_score"]), score
                )
            elif score <= -0.25 and key not in seen_neg:
                seen_neg.add(key)
                bucket = neg_counts.setdefault(
                    key,
                    {
                        "player_id": row["player_id"],
                        "correlated_player_id": row[
                            "correlated_player_id"
                        ],
                        "player_name": row["player_name"],
                        "correlated_player_name": row[
                            "correlated_player_name"
                        ],
                        "correlation_score": score,
                        "correlation_reason": row[
                            "correlation_reason"
                        ],
                        "lineups": 0,
                    },
                )
                bucket["lineups"] += 1
                bucket["correlation_score"] = min(
                    float(bucket["correlation_score"]), score
                )

    def _rows(
        raw: dict[tuple[str, str], dict[str, Any]],
        *,
        reverse: bool,
    ) -> list[dict[str, Any]]:
        out = []
        for item in raw.values():
            exposure = item["lineups"] / float(n)
            out.append(
                {
                    **item,
                    "exposure": round(exposure, 4),
                    "exposure_pct": round(exposure * 100.0, 1),
                    "correlation_score": round(
                        float(item["correlation_score"]), 3
                    ),
                }
            )
        out.sort(
            key=lambda row: (
                -float(row["exposure"]),
                -abs(float(row["correlation_score"]))
                if reverse
                else abs(float(row["correlation_score"])),
            )
        )
        return out[:16]

    positive = _rows(pos_counts, reverse=True)
    negative = _rows(neg_counts, reverse=False)
    narrative = None
    if positive:
        top = positive[0]
        narrative = (
            f"Your portfolio is concentrated around "
            f"{top['player_name']} / {top['correlated_player_name']} "
            f"({top['exposure_pct']:.0f}% of lineups). "
            f"{top['correlation_reason']}"
        )

    return {
        "lineup_count": len(lineups),
        "positive_correlation_exposure": positive,
        "negative_correlation_exposure": negative,
        "narrative": narrative,
    }


def edges_for_player(
    context: CorrelationContext,
    player_id: str,
) -> list[dict[str, Any]]:
    """UI helper: all notable edges involving one player."""

    pid = str(player_id or "")
    out: list[dict[str, Any]] = []
    for (a, b), edge in context.edges.items():
        if pid not in {a, b}:
            continue
        other = b if a == pid else a
        out.append(
            {
                "player_id": pid,
                "correlated_player_id": other,
                "correlated_player_name": _name(context, other),
                "correlation_type": edge.correlation_type,
                "correlation_score": round(edge.correlation_score, 3),
                "confidence": edge.confidence,
                "correlation_reason": edge.correlation_reason,
                "source": edge.source,
                "rule_id": edge.rule_id,
            }
        )
    out.sort(key=lambda row: -abs(float(row["correlation_score"])))
    return out


# ---------------------------------------------------------------------------
# Structural NFL rules
# ---------------------------------------------------------------------------


def _structural_nfl_pair(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    season: int | None,
    week: int | None,
    game_id: str | None,
    game_script_id: str | None,
    config: CorrelationConfig,
) -> CorrelationEdge | None:
    left_id = str(left.get("player_id") or "")
    right_id = str(right.get("player_id") or "")
    if not left_id or not right_id or left_id == right_id:
        return None

    pos_l = _norm_pos(left.get("position"))
    pos_r = _norm_pos(right.get("position"))
    team_l = _team(left)
    team_r = _team(right)
    opp_l = _team_opp(left)
    opp_r = _team_opp(right)

    same_team = bool(team_l and team_r and team_l == team_r)
    opposing = bool(
        team_l
        and team_r
        and (
            (opp_l and opp_l == team_r)
            or (opp_r and opp_r == team_l)
            or (opp_l and opp_r and team_l == opp_r and team_r == opp_l)
        )
    )

    depth_l = _depth(left)
    depth_r = _depth(right)

    # Order roles for rule matching (QB first when present, etc.).
    a, b, pos_a, pos_b, depth_a, depth_b = (
        left,
        right,
        pos_l,
        pos_r,
        depth_l,
        depth_r,
    )
    if pos_r == "QB" and pos_l != "QB":
        a, b = right, left
        pos_a, pos_b = pos_r, pos_l
        depth_a, depth_b = depth_r, depth_l
        team_a, team_b = team_r, team_l
        same_team_ab = same_team
        opposing_ab = opposing
    else:
        team_a, team_b = team_l, team_r
        same_team_ab = same_team
        opposing_ab = opposing

    rule: tuple[str, float, str, float] | None = None

    # QB + own pass catcher
    if pos_a == "QB" and pos_b in PASS_CATCHERS and same_team_ab:
        if pos_b == "WR":
            if depth_b == 1:
                mag, conf = config.qb_own_wr1, 0.88
                rid = "qb_own_wr1"
            elif depth_b == 2:
                mag, conf = config.qb_own_wr2, 0.78
                rid = "qb_own_wr2"
            else:
                mag, conf = config.qb_own_wr_depth, 0.55
                rid = "qb_own_wr_depth"
            rule = (
                rid,
                mag,
                (
                    "QB passing production positively correlates "
                    "with receiving production from his own "
                    "pass catchers."
                ),
                conf,
            )
        else:  # TE
            if depth_b == 1 or depth_b is None:
                mag, conf = config.qb_own_te1, 0.72
                rid = "qb_own_te1"
            else:
                mag, conf = config.qb_own_te_depth, 0.50
                rid = "qb_own_te_depth"
            rule = (
                rid,
                mag,
                (
                    "QB passing volume positively correlates with "
                    "tight-end receiving production."
                ),
                conf,
            )

    # QB + opposing pass catcher (shootout / competitive game)
    elif (
        pos_a == "QB"
        and pos_b in PASS_CATCHERS
        and opposing_ab
    ):
        mag = config.qb_opp_pass_catcher
        if game_script_id in {
            "shootout",
            "underdog_comeback",
            "close_game",
        }:
            mag = min(0.85, mag + 0.12)
        rule = (
            "qb_opp_pass_catcher",
            mag,
            (
                "In competitive / high-scoring games, QB production "
                "can positively correlate with opposing pass "
                "catchers via sustained passing volume on both sides."
            ),
            0.62,
        )

    # QB + opposing DST
    elif pos_a == "QB" and pos_b in DST and opposing_ab:
        rule = (
            "qb_opp_dst",
            config.qb_opp_dst,
            (
                "Strong QB / passing success generally reduces "
                "the opposing defense's fantasy opportunity."
            ),
            0.82,
        )

    # Skill vs opposing DST
    elif (
        pos_a in {"RB", "WR", "TE", "K"}
        and pos_b in DST
        and opposing_ab
    ) or (
        pos_b in {"RB", "WR", "TE", "K"}
        and pos_a in DST
        and opposing_ab
    ):
        rule = (
            "skill_opp_dst",
            config.skill_opp_dst,
            (
                "Offensive production against a defense generally "
                "works against that defense's fantasy scoring."
            ),
            0.70,
        )

    # RB committee (same team)
    elif pos_a == "RB" and pos_b == "RB" and same_team_ab:
        rule = (
            "rb_committee",
            config.rb_committee,
            (
                "Same-team running backs often compete for a "
                "shared rushing / receiving workload."
            ),
            0.80 if {depth_a, depth_b} <= {1, 2, None} else 0.55,
        )

    # RB + own DST
    elif (
        (pos_a == "RB" and pos_b in DST and same_team_ab)
        or (pos_b == "RB" and pos_a in DST and same_team_ab)
    ):
        mag = config.rb_own_dst
        if game_script_id in {
            "favorite_controls",
            "blowout_favorite",
            "low_scoring",
        }:
            mag = min(0.75, mag + 0.10)
        rule = (
            "rb_own_dst",
            mag,
            (
                "A team that controls games on the ground often "
                "creates favorable conditions for its defense."
            ),
            0.58,
        )

    # Opposing WRs (shootout bring-backs)
    elif pos_a == "WR" and pos_b == "WR" and opposing_ab:
        mag = config.wr_opp_wr
        if game_script_id in {"shootout", "underdog_comeback"}:
            mag = min(0.70, mag + 0.12)
        rule = (
            "wr_opp_wr",
            mag,
            (
                "In an expected shootout, pass catchers on both "
                "sides can benefit from elevated passing volume."
            ),
            0.55,
        )

    # Competing WRs same team (soft negative — not automatic ban)
    elif (
        pos_a == "WR"
        and pos_b == "WR"
        and same_team_ab
        and depth_a in {1, 2, None}
        and depth_b in {1, 2, None}
    ):
        rule = (
            "wr_same_team_compete",
            config.wr_same_team_compete,
            (
                "Primary pass catchers on the same team can "
                "mildly compete for a finite target share."
            ),
            0.48,
        )

    # Kicker + own offense
    elif (
        (pos_a == "K" and pos_b in {"QB", "RB", "WR", "TE"} and same_team_ab)
        or (pos_b == "K" and pos_a in {"QB", "RB", "WR", "TE"} and same_team_ab)
    ):
        rule = (
            "kicker_own_offense",
            config.kicker_own_offense,
            (
                "Kickers share the same scoring environment as "
                "their offense, with a mild positive relationship."
            ),
            0.40,
        )

    # QB + own DST (mild / context-dependent)
    elif (
        (pos_a == "QB" and pos_b in DST and same_team_ab)
        or (pos_b == "QB" and pos_a in DST and same_team_ab)
    ):
        mag = config.qb_own_dst
        if game_script_id in {"favorite_controls", "low_scoring"}:
            mag = min(0.35, mag + 0.10)
        elif game_script_id == "shootout":
            mag = max(-0.15, mag - 0.20)
        rule = (
            "qb_own_dst",
            mag,
            (
                "Same-team QB and DST relationship is mild and "
                "depends on game script (control vs shootout)."
            ),
            0.42,
        )

    if rule is None:
        if not same_team and not opposing:
            return _neutral_edge(
                left_id,
                right_id,
                reason="Players are not linked by team/game context.",
                season=season,
                week=week,
                game_id=game_id,
            )
        return None

    rule_id, score, reason, conf = rule
    score = max(-1.0, min(1.0, float(score)))
    conf = max(0.05, min(1.0, float(conf)))
    return CorrelationEdge(
        player_id=left_id,
        correlated_player_id=right_id,
        correlation_type=_type_from_score(score),
        correlation_score=round(score, 4),
        correlation_reason=reason,
        confidence=_confidence_label(conf, config),
        confidence_score=round(conf, 4),
        source="structural",
        game_id=game_id,
        season=season,
        week=week,
        rule_id=rule_id,
    )


def _apply_script_modifiers(
    context: CorrelationContext,
    *,
    config: CorrelationConfig,
) -> None:
    """Light amplify of script-aligned structural edges."""

    script = str(context.game_script_id or "")
    if not script:
        return
    boost = 0.0
    if script in {"shootout", "underdog_comeback"}:
        boost = 0.06
        target_rules = {
            "qb_opp_pass_catcher",
            "wr_opp_wr",
            "qb_own_wr1",
            "qb_own_wr2",
        }
    elif script in {"favorite_controls", "low_scoring", "blowout_favorite"}:
        boost = 0.06
        target_rules = {"rb_own_dst", "qb_own_dst", "rb_committee"}
    else:
        return

    for edge in context.edges.values():
        if edge.rule_id in target_rules and edge.source == "structural":
            edge.correlation_score = max(
                -1.0,
                min(1.0, edge.correlation_score + boost),
            )
            edge.correlation_type = _type_from_score(
                edge.correlation_score
            )


def _apply_empirical_overlays(
    context: CorrelationContext,
    rows: list[dict[str, Any]],
    *,
    config: CorrelationConfig,
    season: int | None,
    week: int | None,
    game_id: str | None,
) -> None:
    """
    Blend historical correlation rows into the matrix.

    Expected row keys: player_id, correlated_player_id,
    correlation_score, games_together (optional), same_team_seasons
    (optional), invalidated (optional bool).
    """

    for row in rows:
        a = str(row.get("player_id") or "").strip()
        b = str(row.get("correlated_player_id") or "").strip()
        if not a or not b or a == b:
            continue
        if bool(row.get("invalidated")):
            continue
        if a not in context.players_by_id or b not in context.players_by_id:
            continue
        try:
            emp = float(row.get("correlation_score"))
        except (TypeError, ValueError):
            continue
        emp = max(-1.0, min(1.0, emp))
        games = int(row.get("games_together") or 0)
        emp_conf = _empirical_confidence(games, config=config)
        if emp_conf < 0.2:
            continue

        key = _pair_key(a, b)
        existing = context.edges.get(key)
        if existing is None:
            context.edges[key] = CorrelationEdge(
                player_id=a,
                correlated_player_id=b,
                correlation_type=_type_from_score(emp),
                correlation_score=round(emp, 4),
                correlation_reason=str(
                    row.get("correlation_reason")
                    or "Historical fantasy co-movement."
                ),
                confidence=_confidence_label(emp_conf, config),
                confidence_score=round(emp_conf, 4),
                source="empirical",
                game_id=game_id,
                season=season,
                week=week,
                rule_id="empirical",
            )
            continue

        # Confidence-weighted blend; empirical capped.
        w_emp = min(config.empirical_weight_cap, emp_conf)
        w_struct = max(0.0, 1.0 - w_emp) * existing.confidence_score
        denom = w_emp + w_struct
        if denom <= 0:
            continue
        blended = (
            emp * w_emp + existing.correlation_score * w_struct
        ) / denom
        blended_conf = min(
            1.0,
            0.5 * emp_conf + 0.5 * existing.confidence_score,
        )
        existing.correlation_score = round(
            max(-1.0, min(1.0, blended)), 4
        )
        existing.correlation_type = _type_from_score(
            existing.correlation_score
        )
        existing.confidence_score = round(blended_conf, 4)
        existing.confidence = _confidence_label(blended_conf, config)
        existing.source = "blended"
        existing.correlation_reason = (
            f"{existing.correlation_reason} Blended with historical "
            f"co-movement (n={games})."
        )


def _empirical_confidence(
    games: int,
    *,
    config: CorrelationConfig,
) -> float:
    if games <= 0:
        return 0.0
    if games < config.min_empirical_games:
        return max(0.15, games / float(config.min_empirical_games) * 0.4)
    # Saturates toward ~0.9 by ~24 games.
    return min(0.9, 0.45 + (games - config.min_empirical_games) * 0.025)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _soft_constraint_penalty(
    players: list[dict[str, Any]],
    context: CorrelationContext,
) -> float:
    """Mild score haircut when soft team/game caps are exceeded."""

    cfg = context.config
    penalty = 0.0
    teams: dict[str, int] = {}
    games: dict[str, int] = {}
    for player in players:
        team = _team(player)
        if team:
            teams[team] = teams.get(team, 0) + 1
        game = str(
            player.get("game_id")
            or player.get("game")
            or ""
        ).strip()
        if game:
            games[game] = games.get(game, 0) + 1

    if cfg.max_same_team_soft is not None:
        for count in teams.values():
            extra = count - int(cfg.max_same_team_soft)
            if extra > 0:
                penalty += extra * cfg.soft_constraint_penalty

    if cfg.max_same_game_soft is not None:
        for count in games.values():
            extra = count - int(cfg.max_same_game_soft)
            if extra > 0:
                penalty += extra * cfg.soft_constraint_penalty

    return penalty


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _type_from_score(score: float) -> str:
    if score > 0.05:
        return "positive"
    if score < -0.05:
        return "negative"
    return "neutral"


def _confidence_label(
    score: float,
    config: CorrelationConfig,
) -> str:
    if score >= config.confidence_high:
        return "High"
    if score >= config.confidence_moderate:
        return "Moderate"
    if score >= 0.25:
        return "Low"
    return "Very Low"


def _neutral_edge(
    left_id: str,
    right_id: str,
    *,
    reason: str,
    season: int | None,
    week: int | None,
    game_id: str | None,
) -> CorrelationEdge:
    return CorrelationEdge(
        player_id=left_id,
        correlated_player_id=right_id,
        correlation_type="neutral",
        correlation_score=0.0,
        correlation_reason=reason,
        confidence="High",
        confidence_score=0.9,
        source="structural",
        game_id=game_id,
        season=season,
        week=week,
        rule_id="neutral",
    )


def _norm_pos(value: Any) -> str:
    pos = str(value or "").strip().upper()
    if pos in {"DST", "D/ST"}:
        return "DEF"
    if pos in {"HB", "FB"}:
        return "RB"
    if pos == "PK":
        return "K"
    return pos


def _team(player: dict[str, Any]) -> str | None:
    raw = player.get("team") or player.get("team_abbreviation")
    text = str(raw or "").strip().upper()
    return text or None


def _team_opp(player: dict[str, Any]) -> str | None:
    raw = player.get("opponent")
    text = str(raw or "").strip().upper()
    if text.startswith("VS "):
        text = text[3:].strip()
    if text.startswith("@"):
        text = text[1:].strip()
    return text or None


def _depth(player: dict[str, Any]) -> int | None:
    raw = player.get("depth_order")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _name(context: CorrelationContext, player_id: str) -> str | None:
    row = context.players_by_id.get(player_id) or {}
    name = row.get("name")
    return str(name) if name else None


def correlation_edges_as_rows(
    context: CorrelationContext,
) -> list[dict[str, Any]]:
    """Flatten context edges for optional persistence."""

    rows = []
    for edge in context.edges.values():
        if edge.correlation_type == "neutral":
            continue
        rows.append(edge.as_dict())
    return rows
