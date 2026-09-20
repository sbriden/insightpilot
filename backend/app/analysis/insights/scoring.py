"""
Deterministic Insight scoring for consistent ranking.

Pipeline position (scoring does not replace gates):

    Raw Data → Candidate Finding → Validated Finding → Insight
                                                         ↓
                                                    InsightScore

Materiality and insight eligibility remain binary gates.
Scoring ranks Insights that already cleared those gates.

Factors (each 0–1; total is a weighted 0–100 score):

- magnitude      — size of the observed effect
- business_impact — financial / operational significance
- confidence     — strength of supporting evidence
- novelty        — how non-obvious the signal is
- relevance      — fit to business / analysis context
- actionability  — whether a reasonable next step exists
- data_quality   — trustworthiness of underlying data

Interesting ≠ important. Ranking prefers business findings
(e.g. concentration risk) over generic descriptive stats
(e.g. average revenue per transaction) unless the latter has
unusual business significance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .confidence import normalize_confidence
from .importance import normalize_importance


SCORING_VERSION = "v2"

# Weights sum to 1.0 — favor business significance over descriptive size.
FACTOR_WEIGHTS: dict[str, float] = {
    "magnitude": 0.14,
    "business_impact": 0.24,
    "confidence": 0.14,
    "novelty": 0.10,
    "relevance": 0.18,
    "actionability": 0.12,
    "data_quality": 0.08,
}

FACTOR_KEYS: tuple[str, ...] = tuple(FACTOR_WEIGHTS.keys())

BusinessSignal = Literal["business", "descriptive", "neutral"]

_CONFIDENCE_SCORES: dict[str, float] = {
    "high": 1.0,
    "medium": 0.65,
    "low": 0.35,
}

_IMPORTANCE_SCORES: dict[str, float] = {
    "high": 0.9,
    "medium": 0.6,
    "low": 0.35,
}

# Keep severity alias map for older call sites / payloads.
_SEVERITY_SCORES = _IMPORTANCE_SCORES

# Analytical shapes that tend to be less "obvious dashboard noise".
_NOVELTY_BY_TYPE: dict[str, float] = {
    "anomaly": 0.85,
    "opportunity": 0.8,
    "risk": 0.8,
    "concentration": 0.75,
    "segment_difference": 0.7,
    "relationship": 0.7,
    "contribution": 0.55,
    "growth_decline": 0.5,
    "comparison": 0.5,
    "distribution": 0.45,
    "trend": 0.4,
    "other": 0.4,
}

_RELEVANCE_BY_TYPE: dict[str, float] = {
    "concentration": 0.85,
    "anomaly": 0.8,
    "opportunity": 0.8,
    "risk": 0.85,
    "growth_decline": 0.7,
    "contribution": 0.7,
    "segment_difference": 0.65,
    "comparison": 0.6,
    "relationship": 0.55,
    "distribution": 0.5,
    "trend": 0.55,
    "other": 0.45,
}

_BUSINESS_TYPES = frozenset(
    {
        "concentration",
        "anomaly",
        "opportunity",
        "risk",
        "growth_decline",
        "contribution",
    }
)

_BUSINESS_RULE_HINTS = (
    "high_concentration",
    "moderate_concentration",
    "single_customer",
    "negative_",
    "loss",
    "decline",
    "anomaly",
    "drop",
    "opportunity",
    "cross_sell",
    "margin_gap",
    "high_negative",
    "profit_improvement",
    "risk",
    "churn",
)

_DESCRIPTIVE_RULE_HINTS = (
    "diversified",
    "low_concentration",
    "stable",
    "broad_adoption",
    "average",
    "mean",
    "per_transaction",
    "per_order",
    "modest_growth",
    "positive_trend",
    "accelerating_trend",
    "revenue_growth",
    "product_diversification",
    "customer_diversification",
)

_DESCRIPTIVE_METRIC_HINTS = (
    "average",
    "mean",
    "avg_",
    "per_transaction",
    "per_order",
    "aov",
)


@dataclass(frozen=True)
class InsightScoreFactors:
    """Per-factor scores on a shared 0–1 scale."""

    magnitude: float
    business_impact: float
    confidence: float
    novelty: float
    relevance: float
    actionability: float
    data_quality: float

    def to_dict(self) -> dict[str, float]:
        return {
            key: _clamp01(getattr(self, key))
            for key in FACTOR_KEYS
        }


@dataclass(frozen=True)
class InsightScore:
    """
    Deterministic ranking payload attached to a promoted Insight.

    ``total`` is 0–100 for stable sort keys. ``factors`` remain
    0–1 so weights and calibration stay transparent.
    """

    total: float
    factors: InsightScoreFactors
    version: str = SCORING_VERSION
    weights: dict[str, float] = field(
        default_factory=lambda: dict(FACTOR_WEIGHTS)
    )

    def to_dict(self) -> dict[str, Any]:
        return serialize_insight_score(self)


def score_insight(
    insight: Any = None,
    *,
    severity: str | None = None,
    data_quality_score: float | None = None,
    payload: dict[str, Any] | None = None,
) -> InsightScore:
    """
    Compute a deterministic InsightScore from an Insight-like object.

    Accepts an Insight dataclass, a serialized insight dict, or
    an explicit ``payload`` overlay. Optional ``severity`` and
    ``data_quality_score`` supply context not always on the Insight.
    """

    data = _as_mapping(insight)
    if payload:
        data = {**data, **payload}

    resolved_importance = normalize_importance(
        data.get("importance")
        if data.get("importance") is not None
        else (
            severity
            if severity is not None
            else data.get("severity") or data.get("priority")
        )
    )
    confidence = normalize_confidence(data.get("confidence"))
    insight_type = str(data.get("insight_type") or "other").strip().lower()
    magnitude_unit = str(data.get("magnitude_unit") or "").strip().lower()
    recommendation = data.get("recommendation")
    business_impact = data.get("business_impact")
    drivers = data.get("potential_drivers") or []
    source_columns = data.get("source_columns") or []
    evidence = data.get("evidence") or {}
    signal = classify_business_signal(data)

    factors = InsightScoreFactors(
        magnitude=_score_magnitude(
            magnitude=data.get("magnitude"),
            magnitude_unit=magnitude_unit,
            observed_value=data.get("observed_value"),
            baseline=data.get("baseline"),
            signal=signal,
        ),
        business_impact=_score_business_impact(
            business_impact=business_impact,
            importance=resolved_importance,
            insight_type=insight_type,
            magnitude=data.get("magnitude"),
            magnitude_unit=magnitude_unit,
            observed_value=data.get("observed_value"),
            signal=signal,
        ),
        confidence=_CONFIDENCE_SCORES.get(confidence, 0.65),
        novelty=_score_novelty(
            insight_type=insight_type,
            signal=signal,
        ),
        relevance=_score_relevance(
            importance=resolved_importance,
            insight_type=insight_type,
            signal=signal,
        ),
        actionability=_score_actionability(
            recommendation=recommendation,
            potential_drivers=drivers,
            insight_type=insight_type,
            signal=signal,
        ),
        data_quality=_score_data_quality(
            data_quality_score=data_quality_score
            if data_quality_score is not None
            else data.get("data_quality_score"),
            confidence=confidence,
            source_columns=source_columns,
            evidence=evidence,
        ),
    )

    total = _weighted_total(factors)
    return InsightScore(
        total=total,
        factors=factors,
        version=SCORING_VERSION,
        weights=dict(FACTOR_WEIGHTS),
    )


def attach_scoring(
    insight_payload: dict[str, Any] | None,
    *,
    severity: str | None = None,
    data_quality_score: float | None = None,
) -> dict[str, Any] | None:
    """Attach a scoring block onto a serialized Insight dict."""

    if insight_payload is None:
        return None

    payload = dict(insight_payload)
    score = score_insight(
        payload,
        severity=severity,
        data_quality_score=data_quality_score,
    )
    payload["scoring"] = score.to_dict()
    return payload


def sort_insights_by_score(
    insights: list[Any] | None,
) -> list[dict[str, Any]]:
    """
    Sort Insights by tier (Critical → Important → Supporting),
    then scoring.total descending (stable for ties).

    Non-dict / missing-score items sort last while preserving order.
    """

    from .tiers import resolve_insight_tier, tier_sort_key

    indexed: list[tuple[int, int, float, dict[str, Any]]] = []

    for index, item in enumerate(insights or []):
        if isinstance(item, dict):
            payload = dict(item)
        elif hasattr(item, "to_dict"):
            payload = item.to_dict() or {}
        else:
            continue

        scoring = payload.get("scoring")
        if not isinstance(scoring, dict) or "total" not in scoring:
            payload = attach_scoring(payload) or payload
            scoring = payload.get("scoring") or {}

        if not payload.get("tier"):
            payload["tier"] = resolve_insight_tier(payload)

        try:
            total = float(scoring.get("total", 0.0))
        except (TypeError, ValueError):
            total = 0.0

        indexed.append(
            (
                index,
                tier_sort_key(payload.get("tier")),
                total,
                payload,
            )
        )

    indexed.sort(key=lambda row: (row[1], -row[2], row[0]))
    return [row[3] for row in indexed]


def serialize_insight_score(
    score: InsightScore | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Normalize an InsightScore into a JSON-safe dict."""

    if score is None:
        return None

    if isinstance(score, InsightScore):
        factors = score.factors.to_dict()
        weights = dict(score.weights or FACTOR_WEIGHTS)
        total = float(score.total)
        version = str(score.version or SCORING_VERSION)
    elif isinstance(score, dict):
        raw_factors = score.get("factors") or {}
        factors = {
            key: _clamp01(raw_factors.get(key, 0.0))
            for key in FACTOR_KEYS
        }
        weights = {
            key: float(FACTOR_WEIGHTS[key])
            for key in FACTOR_KEYS
        }
        raw_weights = score.get("weights")
        if isinstance(raw_weights, dict):
            for key in FACTOR_KEYS:
                if key in raw_weights:
                    try:
                        weights[key] = float(raw_weights[key])
                    except (TypeError, ValueError):
                        pass
        try:
            total = float(score.get("total"))
        except (TypeError, ValueError):
            total = _weighted_total_from_dict(factors, weights)
        version = str(score.get("version") or SCORING_VERSION)
    else:
        return None

    return {
        "total": round(_clamp(total, 0.0, 100.0), 1),
        "factors": factors,
        "weights": weights,
        "version": version,
    }


def _weighted_total(factors: InsightScoreFactors) -> float:
    return _weighted_total_from_dict(factors.to_dict(), FACTOR_WEIGHTS)


def _weighted_total_from_dict(
    factors: dict[str, float],
    weights: dict[str, float],
) -> float:
    total = 0.0
    for key in FACTOR_KEYS:
        total += float(weights.get(key, 0.0)) * _clamp01(
            factors.get(key, 0.0)
        )
    return round(_clamp(total * 100.0, 0.0, 100.0), 1)


def classify_business_signal(insight: dict[str, Any]) -> BusinessSignal:
    """
    Classify whether an Insight is a business finding or a descriptive note.

    Business findings (concentration risk, losses, material declines,
    opportunities) should outrank generic observations (averages,
    diversified/all-clear health checks) unless the latter shows
    unusual business significance.
    """

    rule_id = _normalize_token(insight.get("rule_id"))
    metric = _normalize_token(insight.get("metric"))
    title = _normalize_token(insight.get("title"))
    finding = _normalize_token(insight.get("finding"))
    insight_type = _normalize_token(insight.get("insight_type")) or "other"
    # Rule/title drive all-clear detection. Metric names like
    # overall_revenue_growth also power decline findings.
    rule_title = " ".join(part for part in (rule_id, title) if part)
    metric_finding = " ".join(part for part in (metric, finding) if part)
    blob = " ".join(part for part in (rule_title, metric_finding) if part)

    if _has_token_hint(rule_title, _DESCRIPTIVE_RULE_HINTS) or _has_token_hint(
        metric, _DESCRIPTIVE_METRIC_HINTS
    ):
        if _has_unusual_business_significance(insight):
            return "business"
        return "descriptive"

    if _has_token_hint(blob, _BUSINESS_RULE_HINTS):
        return "business"

    if insight_type in _BUSINESS_TYPES and _has_unusual_business_significance(
        insight
    ):
        return "business"

    if insight_type in {"distribution", "comparison", "trend", "other"}:
        if _looks_like_descriptive_stat(blob):
            return "descriptive"

    return "neutral"


def _has_unusual_business_significance(insight: dict[str, Any]) -> bool:
    """Escape hatch: descriptive stats can still rank if unusually material."""

    importance = normalize_importance(
        insight.get("importance") or insight.get("severity")
    )
    if importance == "high":
        return True

    insight_type = _normalize_token(insight.get("insight_type"))
    observed = _as_float(insight.get("observed_value"))
    magnitude = _as_float(insight.get("magnitude"))
    unit = str(insight.get("magnitude_unit") or "").strip().lower()

    share = observed if observed is not None else magnitude
    if share is not None:
        if share > 1.5:
            share = share / 100.0
        # Material concentration / contribution levels.
        if insight_type in {"concentration", "contribution", "risk"} and share >= 0.35:
            return True
        if abs(share) >= 0.20 and insight_type in {
            "growth_decline",
            "anomaly",
            "trend",
        }:
            return True

    amount = abs(magnitude or observed or 0.0)
    if unit == "currency" and amount >= 25_000:
        return True
    if unit == "count" and amount >= 20 and insight_type in {
        "risk",
        "anomaly",
        "opportunity",
    }:
        return True

    rule_id = _normalize_token(insight.get("rule_id"))
    # High-concentration style rules are business even without extra cues.
    if any(
        token in rule_id
        for token in (
            "high_concentration",
            "single_customer",
            "negative_",
            "loss",
            "decline",
            "opportunity",
        )
    ):
        return True

    return False


def _looks_like_descriptive_stat(blob: str) -> bool:
    return _has_token_hint(
        blob,
        (
            "average",
            "mean",
            "per_transaction",
            "per_order",
            "median",
            "std_dev",
            "standard_deviation",
        ),
    )


def _has_token_hint(blob: str, hints: tuple[str, ...]) -> bool:
    """
    Match hints on underscore/token boundaries.

    Avoids false positives like mean ⊂ meaningful.
    Hints ending with ``_`` are treated as prefixes
    (e.g. ``negative_`` matches ``negative_product_rate``).
    """

    padded = f"_{_normalize_token(blob)}_"
    for hint in hints:
        token = _normalize_token(hint)
        if not token:
            continue
        if token.endswith("_"):
            if f"_{token}" in padded:
                return True
        elif f"_{token}_" in padded:
            return True
    return False


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    text = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    while "__" in text:
        text = text.replace("__", "_")
    return text


def _score_magnitude(
    *,
    magnitude: Any,
    magnitude_unit: str,
    observed_value: Any,
    baseline: Any,
    signal: BusinessSignal = "neutral",
) -> float:
    mag = _as_float(magnitude)
    if mag is None:
        observed = _as_float(observed_value)
        base = _as_float(baseline)
        if observed is not None and base is not None:
            mag = observed - base
        elif observed is not None:
            mag = observed

    if mag is None:
        score = 0.4
    else:
        abs_mag = abs(mag)
        unit = magnitude_unit

        if unit == "currency":
            # $1k floor materiality → ~0.2; $50k → 1.0
            score = _clamp01(abs_mag / 50_000.0)
        elif unit == "count":
            score = _clamp01(abs_mag / 20.0)
        elif unit in {"ratio", "percent", ""}:
            # Treat percent-like values > 1 as already percent points.
            if unit == "percent" or abs_mag > 1.5:
                abs_mag = abs_mag / 100.0
            # 5% materiality floor → 0.2; 25% → 1.0
            score = _clamp01(abs_mag / 0.25)
        else:
            score = _clamp01(abs_mag / max(abs_mag, 1.0))

    # Large descriptive averages should not dominate ranking.
    if signal == "descriptive":
        return _clamp01(score * 0.45)
    return score


def _score_business_impact(
    *,
    business_impact: Any,
    importance: str,
    insight_type: str,
    magnitude: Any,
    magnitude_unit: str,
    observed_value: Any,
    signal: BusinessSignal = "neutral",
) -> float:
    if signal == "descriptive":
        base = 0.25
        if importance == "high":
            base = 0.55
        return _clamp01(base)

    if business_impact is not None and str(business_impact).strip():
        base = 0.75
    else:
        base = _IMPORTANCE_SCORES.get(importance, 0.5)

    if insight_type in {"opportunity", "risk", "concentration"}:
        base = max(base, 0.75)

    if signal == "business":
        base = max(base, 0.8)

    if magnitude_unit == "currency":
        amount = abs(_as_float(magnitude) or _as_float(observed_value) or 0.0)
        if amount >= 25_000:
            base = max(base, 0.85)
        elif amount >= 5_000:
            base = max(base, 0.7)

    if magnitude_unit in {"ratio", ""}:
        share = abs(
            _as_float(observed_value)
            or _as_float(magnitude)
            or 0.0
        )
        if share > 1.5:
            share = share / 100.0
        if share >= 0.4:
            base = max(base, 0.85)
        elif share >= 0.2:
            base = max(base, 0.65)

    return _clamp01(base)


def _score_novelty(
    *,
    insight_type: str,
    signal: BusinessSignal = "neutral",
) -> float:
    score = _NOVELTY_BY_TYPE.get(insight_type, 0.45)
    if signal == "descriptive":
        return _clamp01(score * 0.35)
    if signal == "business":
        return _clamp01(max(score, 0.7))
    return score


def _score_relevance(
    *,
    importance: str,
    insight_type: str,
    signal: BusinessSignal = "neutral",
) -> float:
    importance_score = _IMPORTANCE_SCORES.get(importance, 0.5)
    type_score = _RELEVANCE_BY_TYPE.get(insight_type, 0.5)
    score = 0.35 + 0.35 * importance_score + 0.35 * type_score

    if signal == "descriptive":
        return _clamp01(score * 0.5)
    if signal == "business":
        return _clamp01(max(score, 0.8))
    return _clamp01(score)


def _score_actionability(
    *,
    recommendation: Any,
    potential_drivers: Any,
    insight_type: str,
    signal: BusinessSignal = "neutral",
) -> float:
    score = 0.35

    recommendation_text = (
        str(recommendation).strip()
        if recommendation is not None
        else ""
    )
    if recommendation_text:
        # Prefer concrete recommendations over empty interpretive slots.
        if len(recommendation_text) >= 24:
            score = 0.85
        else:
            score = 0.7

    driver_count = 0
    if isinstance(potential_drivers, str):
        driver_count = 1 if potential_drivers.strip() else 0
    elif isinstance(potential_drivers, list):
        driver_count = sum(
            1 for item in potential_drivers if str(item).strip()
        )

    if driver_count:
        score = min(1.0, score + 0.05 * min(driver_count, 3))

    if insight_type in {"opportunity", "risk"} and score < 0.65:
        score = 0.65

    # Canned recommendations on descriptive notes should not inflate rank.
    if signal == "descriptive":
        return _clamp01(min(score, 0.45))
    if signal == "business":
        return _clamp01(max(score, 0.7))
    return _clamp01(score)

def _score_data_quality(
    *,
    data_quality_score: Any,
    confidence: str,
    source_columns: Any,
    evidence: Any,
) -> float:
    explicit = _normalize_quality_score(data_quality_score)
    if explicit is not None:
        return explicit

    score = _CONFIDENCE_SCORES.get(confidence, 0.65)

    columns = [
        str(column).strip()
        for column in (source_columns or [])
        if str(column).strip()
    ]
    if columns:
        score = min(1.0, score + 0.1)
    else:
        score = max(0.2, score - 0.15)

    metrics = []
    if isinstance(evidence, dict):
        metrics = evidence.get("metrics") or []
    if metrics:
        score = min(1.0, score + 0.05)

    return _clamp01(score)


def _normalize_quality_score(value: Any) -> float | None:
    numeric = _as_float(value)
    if numeric is None:
        return None

    if numeric > 1.0:
        numeric = numeric / 100.0

    return _clamp01(numeric)


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return {}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:  # NaN
        return None
    return numeric


def _clamp01(value: Any) -> float:
    return _clamp(value, 0.0, 1.0)


def _clamp(value: Any, low: float, high: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return low
    if numeric != numeric:
        return low
    return max(low, min(high, numeric))
