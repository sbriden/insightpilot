"""
Positional injury relevance for fantasy news.

A teammate or opposing defender is included only when their
absence can change this player's opportunity or efficiency.
Unknown positions are ignored. They are not treated as wide
receivers.
"""

from __future__ import annotations

from typing import Any


_ALIASES: dict[str, str] = {
    "QB": "QB",
    "RB": "RB",
    "HB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "OL": "OL",
    "OT": "OL",
    "OG": "OL",
    "C": "OL",
    "T": "OL",
    "G": "OL",
    "LT": "OL",
    "LG": "OL",
    "RG": "OL",
    "RT": "OL",
    "DE": "EDGE",
    "EDGE": "EDGE",
    "DT": "DT",
    "NT": "DT",
    "DL": "DL",
    "LB": "LB",
    "ILB": "LB",
    "OLB": "LB",
    "MLB": "LB",
    "WLB": "LB",
    "CB": "CB",
    "DB": "CB",
    "NB": "CB",
    "S": "S",
    "FS": "S",
    "SS": "S",
    "SAF": "S",
    "SAFETY": "S",
    "K": "K",
    "PK": "K",
    "P": "P",
    "DEF": "DEF",
    "DST": "DEF",
}

_SKILL = {"QB", "RB", "WR", "TE"}
_PASS_CATCHERS = {"WR", "TE", "RB"}
_DEFENSE = {"EDGE", "DT", "DL", "LB", "CB", "S"}


def canonical_news_position(position: str | None) -> str | None:
    if not position:
        return None
    raw = str(position).strip().upper().replace("-", "/")
    if not raw or raw in {"NAN", "NONE"}:
        return None
    token = raw.split("/")[0].strip()
    if token in _ALIASES:
        return _ALIASES[token]
    for alias, canonical in _ALIASES.items():
        if token.endswith(alias) and len(token) <= len(alias) + 1:
            return canonical
    return None


def _as_share(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    if number > 1.5:
        number = number / 100.0
    if number > 1.5:
        return None
    return number


def _absence_weight(game_status: str | None) -> float:
    game = (game_status or "").strip().lower()
    if not game:
        return 0.0
    if any(token in game for token in ("out", "ir", "pup", "suspend")):
        return 1.0
    if "doubt" in game:
        return 0.75
    if "question" in game:
        return 0.4
    return 0.0


def _cap_level(level: str, weight: float) -> str:
    if weight < 0.7 and level == "high":
        return "moderate"
    return level


def _effect(
    *,
    level: str,
    fantasy_impact: str,
    role_impact: str,
    summary: str,
    weight: float,
    confidence: str = "moderate",
) -> dict[str, Any]:
    resolved = _cap_level(level, weight)
    label = {
        "positive": "Opportunity increase",
        "negative": "Efficiency risk",
        "mixed": "Mixed fantasy impact",
    }.get(fantasy_impact, "Team context")
    if resolved == "high" and fantasy_impact == "positive":
        label = "High opportunity increase"
    elif resolved == "high" and fantasy_impact == "negative":
        label = "High fantasy impact"
    return {
        "level": resolved,
        "fantasy_impact": fantasy_impact,
        "role_impact": role_impact,
        "availability": "Available",
        "confidence": confidence if weight >= 0.7 else "low",
        "label": label,
        "summary": summary,
    }


def _share_sentence(
    *,
    injured_share: float | None,
    viewer_share: float | None,
    remaining_share: float | None,
    noun: str,
) -> str:
    injured = _as_share(injured_share)
    viewer = _as_share(viewer_share)
    remaining = _as_share(remaining_share)
    if (
        injured is None
        or viewer is None
        or remaining is None
        or remaining <= 0
        or injured <= 0
    ):
        return ""
    absorbed = injured * (viewer / remaining)
    return (
        f" Season {noun} suggests about {absorbed * 100:.0f} points "
        f"of the vacated {injured * 100:.0f}% could shift here, "
        f"before catch rate, yards per target, or touchdown rate change."
    )


def _ahead(injured_depth: int | None, viewer_depth: int | None) -> bool:
    if injured_depth is None:
        return False
    if viewer_depth is None:
        return injured_depth == 1
    return injured_depth < viewer_depth


def _frontline(depth: int | None) -> bool:
    return depth is not None and depth <= 2


def evaluate_injury_relevance(
    *,
    viewer_position: str | None,
    viewer_depth: int | None,
    injured_position: str | None,
    injured_depth: int | None,
    game_status: str | None,
    same_team: bool,
    injured_target_share: float | None = None,
    viewer_target_share: float | None = None,
    remaining_target_share: float | None = None,
    injured_air_yard_share: float | None = None,
    injured_rush_share: float | None = None,
    viewer_rush_share: float | None = None,
    remaining_rush_share: float | None = None,
    other_wr_out: int = 0,
    other_edge_out: int = 0,
    other_cb_out: int = 0,
    other_dt_out: int = 0,
    other_front_out: int = 0,
) -> dict[str, Any] | None:
    """
    Return an impact payload, or None when the absence should
    not appear in this player's news.
    """

    weight = _absence_weight(game_status)
    if weight <= 0:
        return None

    viewer = canonical_news_position(viewer_position)
    injured = canonical_news_position(injured_position)
    if viewer not in _SKILL or injured is None:
        return None

    if same_team:
        return _teammate_effect(
            viewer=viewer,
            viewer_depth=viewer_depth,
            injured=injured,
            injured_depth=injured_depth,
            weight=weight,
            injured_target_share=injured_target_share,
            viewer_target_share=viewer_target_share,
            remaining_target_share=remaining_target_share,
            injured_air_yard_share=injured_air_yard_share,
            injured_rush_share=injured_rush_share,
            viewer_rush_share=viewer_rush_share,
            remaining_rush_share=remaining_rush_share,
            other_wr_out=other_wr_out,
        )

    if injured not in _DEFENSE:
        return None
    # Questionable defensive designations are too thin to surface.
    if weight < 0.75:
        return None
    return _opponent_defense_effect(
        viewer=viewer,
        viewer_depth=viewer_depth,
        injured=injured,
        injured_depth=injured_depth,
        weight=weight,
        other_edge_out=other_edge_out,
        other_cb_out=other_cb_out,
        other_dt_out=other_dt_out,
        other_front_out=other_front_out,
    )


def _teammate_effect(
    *,
    viewer: str,
    viewer_depth: int | None,
    injured: str,
    injured_depth: int | None,
    weight: float,
    injured_target_share: float | None,
    viewer_target_share: float | None,
    remaining_target_share: float | None,
    injured_air_yard_share: float | None,
    injured_rush_share: float | None,
    viewer_rush_share: float | None,
    remaining_rush_share: float | None,
    other_wr_out: int,
) -> dict[str, Any] | None:
    if injured in _DEFENSE or injured in {"K", "P", "DEF"}:
        return None

    target_note = _share_sentence(
        injured_share=injured_target_share,
        viewer_share=viewer_target_share,
        remaining_share=remaining_target_share,
        noun="target share",
    )
    rush_note = _share_sentence(
        injured_share=injured_rush_share,
        viewer_share=viewer_rush_share,
        remaining_share=remaining_rush_share,
        noun="rush share",
    )
    air = _as_share(injured_air_yard_share)
    air_note = ""
    if air is not None and air >= 0.2:
        air_note = (
            f" That receiver has accounted for about {air * 100:.0f}% "
            "of air yards, so explosive plays and red-zone touchdowns "
            "are the piece that moves."
        )

    multiple_receivers = other_wr_out >= 1 and injured == "WR"

    if injured == "OL":
        if not _frontline(injured_depth):
            return None
        if viewer == "QB":
            return _effect(
                level="moderate",
                fantasy_impact="negative",
                role_impact="Reduced Opportunity",
                weight=weight,
                summary=(
                    "An offensive line starter is unavailable. Pressure "
                    "and sack risk can rise, which lowers QB efficiency "
                    "even when dropbacks stay similar."
                ),
            )
        if viewer == "RB":
            return _effect(
                level="moderate",
                fantasy_impact="negative",
                role_impact="Reduced Opportunity",
                weight=weight,
                summary=(
                    "An offensive line starter is unavailable. Rushing "
                    "efficiency can decline even if attempt volume holds."
                ),
            )
        return None

    if injured == "QB" and injured_depth == 1 and viewer in _PASS_CATCHERS:
        return _effect(
            level="moderate",
            fantasy_impact="negative",
            role_impact="Role Uncertain",
            weight=weight,
            summary=(
                "The starting quarterback is unavailable. Route usage "
                "can continue, but completion quality, yards per target, "
                "and touchdown expectation usually change with the backup."
            ),
        )

    if injured == "WR" and injured_depth == 1:
        if viewer == "WR" and _ahead(injured_depth, viewer_depth):
            level = "high" if viewer_depth in {None, 2} else "moderate"
            if multiple_receivers:
                level = "high"
            extra = (
                " Several wide receivers are out, so targets concentrate "
                "on the receivers and tight ends still on the field."
                if multiple_receivers
                else ""
            )
            why = (
                "Routes and target share can increase for the next "
                "wide receiver."
                if viewer_depth in {None, 2}
                else (
                    "Routes and target share can increase for a "
                    "deeper wide receiver."
                )
            )
            return _effect(
                level=level,
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                summary=why + extra + target_note,
            )
        if viewer == "TE":
            return _effect(
                level="high" if multiple_receivers else "moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                summary=(
                    "A top wide receiver is unavailable. Intermediate and "
                    "short targets can shift toward the tight end."
                    + (
                        " With multiple wide receivers out, that concentration is larger."
                        if multiple_receivers
                        else ""
                    )
                    + target_note
                ),
            )
        if viewer == "RB":
            return _effect(
                level="low" if viewer_depth and viewer_depth >= 3 else "moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                summary=(
                    "A top wide receiver is unavailable. Checkdowns and "
                    "short targets can increase for the running back."
                    + target_note
                ),
            )
        if viewer == "QB":
            return _effect(
                level="moderate",
                fantasy_impact="negative",
                role_impact="Reduced Opportunity",
                weight=weight,
                summary=(
                    "A top wide receiver is unavailable. Pass attempts can "
                    "stay similar while catch rate, yards per target, "
                    "explosive-play rate, and passing touchdown expectation "
                    "decline."
                    + air_note
                ),
            )

    if (
        injured == "WR"
        and injured_depth == 2
        and viewer == "WR"
        and viewer_depth == 3
    ):
        return _effect(
            level="moderate",
            fantasy_impact="positive",
            role_impact="Increased Opportunity",
            weight=weight,
            summary=(
                "The WR2 is unavailable. The next wide receiver can "
                "see a smaller route and target increase."
                + target_note
            ),
        )

    if injured == "TE" and injured_depth == 1 and viewer == "TE" and _ahead(
        injured_depth, viewer_depth
    ):
        return _effect(
            level="high" if viewer_depth in {None, 2} else "moderate",
            fantasy_impact="positive",
            role_impact="Increased Opportunity",
            weight=weight,
            summary=(
                "The starting tight end is unavailable. Routes and "
                "targets can move to the next tight end."
                + target_note
            ),
        )

    if injured == "RB" and injured_depth == 1:
        if viewer == "RB" and _ahead(injured_depth, viewer_depth):
            level = "high" if viewer_depth in {None, 2} else "moderate"
            return _effect(
                level=level,
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                summary=(
                    "The lead running back is unavailable. Rush attempts, "
                    "targets, and goal-line work can move to the next back."
                    + rush_note
                    + target_note
                ),
            )
        if viewer == "QB":
            return _effect(
                level="moderate",
                fantasy_impact="mixed",
                role_impact="Role Uncertain",
                weight=weight,
                summary=(
                    "The lead running back is unavailable. QB rushing can "
                    "rise if designed runs stay in the quarterback's hands, "
                    "while passing efficiency can fall if that back was a "
                    "checkdown outlet. The net fantasy effect depends on "
                    "which of those is larger."
                    + rush_note
                ),
            )

    return None


def _opponent_defense_effect(
    *,
    viewer: str,
    viewer_depth: int | None,
    injured: str,
    injured_depth: int | None,
    weight: float,
    other_edge_out: int,
    other_cb_out: int,
    other_dt_out: int,
    other_front_out: int,
) -> dict[str, Any] | None:
    if not _frontline(injured_depth):
        return None

    primary_wr = viewer == "WR" and viewer_depth in {None, 1}
    multiple_rushers = injured in {"EDGE", "DL"} and other_edge_out >= 1
    multiple_corners = injured == "CB" and other_cb_out >= 1
    multiple_front = injured in {"EDGE", "DT", "DL"} and other_front_out >= 1
    if injured_depth != 1 and not (
        multiple_rushers or multiple_corners or multiple_front
    ):
        return None

    if injured == "EDGE" or (injured == "DL" and viewer == "QB"):
        if viewer == "QB":
            return _effect(
                level="high" if multiple_rushers else "moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                confidence="low",
                summary=(
                    "An opposing pass rusher is unavailable. Less pressure "
                    "can lift completion rate and time to throw."
                    + (
                        " Multiple pass rushers are out, so the efficiency gain is larger."
                        if multiple_rushers
                        else " The gain is larger when that rusher is the one who usually faces this quarterback."
                    )
                ),
            )
        if viewer in {"WR", "TE"} and multiple_rushers:
            return _effect(
                level="moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                confidence="low",
                summary=(
                    "Multiple opposing pass rushers are unavailable. Extra "
                    "time to throw can raise wide receiver and tight end production."
                ),
            )

    if injured == "CB":
        if primary_wr or multiple_corners:
            return _effect(
                level="high" if multiple_corners and viewer == "WR" else "moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                confidence="low",
                summary=(
                    "An opposing corner is unavailable. This matters most "
                    "when that corner normally covers this receiver."
                    + (
                        " Multiple corners are out, so the passing game can rise more broadly."
                        if multiple_corners
                        else " If the corner plays the other side, the effect is smaller."
                    )
                ),
            )
        if viewer == "QB" and multiple_corners:
            return _effect(
                level="moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                confidence="low",
                summary=(
                    "Multiple opposing corners are unavailable. Passing "
                    "efficiency can rise across the offense."
                ),
            )
        if viewer == "TE" and multiple_corners:
            return _effect(
                level="moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                confidence="low",
                summary=(
                    "Multiple opposing corners are unavailable. Tight end "
                    "targets can benefit along with the wide receivers."
                ),
            )

    if injured == "S" and injured_depth == 1 and primary_wr:
        return _effect(
            level="moderate",
            fantasy_impact="positive",
            role_impact="Increased Opportunity",
            weight=weight,
            confidence="low",
            summary=(
                "An opposing coverage safety is unavailable. Deep targets "
                "can become easier, with a larger effect when that safety "
                "is the one who rotates to this receiver's side."
            ),
        )

    if injured == "LB" and injured_depth == 1 and viewer in {"RB", "TE"}:
        return _effect(
            level="moderate",
            fantasy_impact="positive",
            role_impact="Increased Opportunity",
            weight=weight,
            confidence="low",
            summary=(
                "An opposing linebacker is unavailable. Running back and "
                "tight end production can rise when that linebacker is the "
                "one who fits the run or covers the tight end."
            ),
        )

    if injured == "DT" and injured_depth == 1 and viewer == "RB":
        return _effect(
            level="high" if multiple_front else "moderate",
            fantasy_impact="positive",
            role_impact="Increased Opportunity",
            weight=weight,
            confidence="low",
            summary=(
                "An opposing interior defender is unavailable. Rushing "
                "efficiency can improve for the running back."
                + (
                    " Multiple defensive linemen are out, so the rushing path is wider."
                    if multiple_front
                    else ""
                )
            ),
        )

    if multiple_front and viewer in {"RB", "QB"} and injured in {"DT", "EDGE", "DL"}:
        if viewer == "QB":
            return _effect(
                level="moderate",
                fantasy_impact="positive",
                role_impact="Increased Opportunity",
                weight=weight,
                confidence="low",
                summary=(
                    "Multiple opposing defensive linemen are unavailable. "
                    "QB rushing and time to throw can both improve."
                ),
            )
        return _effect(
            level="high",
            fantasy_impact="positive",
            role_impact="Increased Opportunity",
            weight=weight,
            confidence="low",
            summary=(
                "Multiple opposing defensive linemen are unavailable. "
                "Rushing efficiency can rise for the running back."
            ),
        )

    return None
