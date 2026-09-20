"""
SME rules for fantasy signal insights.

A useful fantasy insight is an actionable, typed signal
(breakout, buy-low, start/sit, etc.) with sufficient strength
and confidence — not every raw score row.
"""

from __future__ import annotations

from .models import InsightRule


CATEGORY = "Fantasy Signals"

# Minimum signal_strength (0–100 scale) by signal type.
STRENGTH_FLOORS: dict[str, float] = {
    "BREAKOUT_CANDIDATE": 60.0,
    "BUY_LOW": 55.0,
    "SELL_HIGH": 55.0,
    "START": 50.0,
    "SIT": 50.0,
    "WAIVER_TARGET": 55.0,
    "REGRESSION_RISK": 55.0,
    "OPPORTUNITY_SURGE": 60.0,
    "OPPORTUNITY_DECLINE": 60.0,
}

CONFIDENCE_FLOOR = 50.0

SIGNAL_TITLES: dict[str, str] = {
    "BREAKOUT_CANDIDATE": "Breakout candidate",
    "BUY_LOW": "Buy-low opportunity",
    "SELL_HIGH": "Sell-high candidate",
    "START": "Start recommendation",
    "SIT": "Sit recommendation",
    "WAIVER_TARGET": "Waiver target",
    "REGRESSION_RISK": "Regression risk",
    "OPPORTUNITY_SURGE": "Opportunity surge",
    "OPPORTUNITY_DECLINE": "Opportunity decline",
}

SIGNAL_ACTIONS: dict[str, str] = {
    "BREAKOUT_CANDIDATE": (
        "Prioritize this player in lineup or acquisition "
        "decisions while opportunity remains elevated."
    ),
    "BUY_LOW": (
        "Consider acquiring before market price catches up "
        "to underlying opportunity."
    ),
    "SELL_HIGH": (
        "Explore trading while production outpaces sustainable "
        "opportunity."
    ),
    "START": (
        "Favor this player in weekly lineups given current "
        "signal strength."
    ),
    "SIT": (
        "Avoid starting this player this week relative to "
        "safer options."
    ),
    "WAIVER_TARGET": (
        "Add from waivers before the rest of the league reacts."
    ),
    "REGRESSION_RISK": (
        "Temper expectations or reduce exposure while "
        "efficiency looks unsustainable."
    ),
    "OPPORTUNITY_SURGE": (
        "Lean into rising usage and target share in the "
        "near term."
    ),
    "OPPORTUNITY_DECLINE": (
        "Reduce reliance until opportunity volume stabilizes."
    ),
}


def _signal_evidence(facts: dict) -> list[dict]:
    return [
        {
            "key": "signal_type",
            "label": "Signal type",
            "value": facts.get("signal_type"),
            "unit": "category",
        },
        {
            "key": "signal_strength",
            "label": "Signal strength",
            "value": facts.get("signal_strength"),
            "unit": "score",
        },
        {
            "key": "confidence",
            "label": "Confidence",
            "value": facts.get("confidence"),
            "unit": "score",
        },
        {
            "key": "season",
            "label": "Season",
            "value": facts.get("season"),
            "unit": "count",
        },
        {
            "key": "week",
            "label": "Week",
            "value": facts.get("week"),
            "unit": "count",
        },
        {
            "key": "player_id",
            "label": "Player",
            "value": facts.get("player_label")
            or facts.get("player_id"),
            "unit": "entity",
        },
    ]


def _signal_calculation(signal_type: str) -> dict:
    return {
        "analysis_type": "fantasy_signals",
        "measure": "signal_strength",
        "dimension": "player",
        "aggregation": "NONE",
        "grouping": "player_id",
        "ranking": "descending signal_strength",
        "comparison": "vs_strength_floor",
        "parameters": {
            "signal_type": signal_type,
            "strength_floor": STRENGTH_FLOORS.get(
                signal_type,
                55.0,
            ),
            "confidence_floor": CONFIDENCE_FLOOR,
        },
    }


def _make_signal_rule(signal_type: str) -> InsightRule:
    floor = STRENGTH_FLOORS.get(signal_type, 55.0)
    title = SIGNAL_TITLES.get(
        signal_type,
        signal_type.replace("_", " ").title(),
    )
    action = SIGNAL_ACTIONS.get(
        signal_type,
        "Review this fantasy signal against roster needs.",
    )

    return InsightRule(
        id=f"fantasy_signal_{signal_type.lower()}",
        severity="high" if floor >= 60 else "medium",
        title=title,
        condition=lambda f, st=signal_type, fl=floor: (
            str(f.get("signal_type") or "").upper() == st
            and float(f.get("signal_strength") or 0) >= fl
            and float(f.get("confidence") or 0)
            >= CONFIDENCE_FLOOR
        ),
        message=lambda f, t=title: (
            f"{t}: {f.get('player_label') or f.get('player_id')} "
            f"in {f.get('season')} week {f.get('week')} "
            f"(strength {float(f.get('signal_strength') or 0):.0f}, "
            f"confidence {float(f.get('confidence') or 0):.0f})."
        ),
        category=CATEGORY,
        recommended_action=action,
        metric="signal_strength",
        observed=lambda f: f.get("signal_strength"),
        baseline=floor,
        comparison="vs_threshold",
        magnitude=lambda f, fl=floor: (
            float(f.get("signal_strength") or 0) - fl
        ),
        magnitude_unit="score",
        confidence=lambda f: f.get("confidence"),
        importance="high" if floor >= 60 else "medium",
        dimensions=["player", "week"],
        filters=lambda f, st=signal_type, fl=floor: [
            {
                "field": "signal_type",
                "op": "=",
                "value": st,
            },
            {
                "field": "signal_strength",
                "op": ">=",
                "value": fl,
            },
            {
                "field": "confidence",
                "op": ">=",
                "value": CONFIDENCE_FLOOR,
            },
        ],
        calculations=[
            "load fantasy_signal rows for season/week",
            f"filter signal_type = {signal_type}",
            f"require signal_strength >= {floor}",
            f"require confidence >= {CONFIDENCE_FLOOR}",
        ],
        calculation=_signal_calculation(signal_type),
        row_scope="player × week fantasy signals meeting SME floors",
        input_values=lambda f, fl=floor: {
            "player_id": f.get("player_id"),
            "signal_type": f.get("signal_type"),
            "signal_strength": f.get("signal_strength"),
            "confidence": f.get("confidence"),
            "season": f.get("season"),
            "week": f.get("week"),
            "strength_floor": fl,
            "confidence_floor": CONFIDENCE_FLOOR,
        },
        evidence_metrics=_signal_evidence,
        require_material=True,
        min_abs_magnitude=0.0,
        insight_eligible=True,
    )


RULES = [
    _make_signal_rule(signal_type)
    for signal_type in STRENGTH_FLOORS
]
