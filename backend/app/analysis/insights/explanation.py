"""
AI Insight Contract — interpretive layer over deterministic Insights.

Architectural boundary:

    Deterministic Insight (facts)
        e.g. "Top 10 customers represent 47% of revenue."

            ↓

    AI Interpretation (this contract — never invents numbers)
        e.g. "Revenue is highly concentrated among a small group
              of customers, which may increase exposure to
              customer loss."

            ↓

    Recommendation
        e.g. "Review the top 10 accounts for renewal risk and
              identify opportunities to diversify revenue."

The contract is attached to selected Insights as
``ai_interpretation``. It must never replace or live inside
``finding`` / StructuredEvidence.

Anti-hallucination: the AI receives only structured insight,
evidence, dataset context, and data-quality limitations — never
the raw dataset by default. Output is sanitized so it cannot
invent numbers, claim unsupported causation, or alter calculated
values. Drivers use potential language
("Potential drivers include...").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import re

from .evidence import EXPLANATION_LAYER


# Canonical AI Insight Contract fields.
REQUIRED_AI_INSIGHT_KEYS: frozenset[str] = frozenset(
    {
        "summary",
        "why_it_matters",
        "potential_drivers",
        "recommended_action",
        "caveats",
        "layer",
        "source",
    }
)

# ---------------------------------------------------------------------------
# Anti-hallucination contract (most important requirement)
# ---------------------------------------------------------------------------

# Inputs the AI may receive for insight interpretation.
AI_INSIGHT_ALLOWED_INPUT_SECTIONS: frozenset[str] = frozenset(
    {
        "constraints",
        "structured_insight",
        "evidence",
        "dataset_context",
        "data_quality_limitations",
        "evidence_supported_drivers",
    }
)

# Never send these to the AI for insight interpretation.
AI_INSIGHT_FORBIDDEN_INPUT_KEYS: frozenset[str] = frozenset(
    {
        "dataframe",
        "raw_dataset",
        "raw_rows",
        "rows",
        "records",
        "supporting_records",
        "full_dataset",
        "csv",
        "upload_bytes",
    }
)

AI_INSIGHT_CONSTRAINTS: dict[str, Any] = {
    "role": "insight_explanation",
    "may_invent_numbers": False,
    "may_invent_trends": False,
    "may_claim_causation_without_evidence": False,
    "may_introduce_unsupported_entity_facts": False,
    "may_alter_calculated_values": False,
    "may_manufacture_business_context": False,
    "may_receive_raw_dataset": False,
    "must_use_only_provided_facts": True,
    "driver_language": "potential",
    "forbidden_causal_phrases": [
        "this happened because",
        "happened because",
        "caused by",
        "was caused by",
        "is caused by",
        "as a result of",
        "resulting from",
        "due to the fact that",
        "the reason is",
        "the root cause is",
        "driven solely by",
    ],
    "preferred_driver_preamble": "Potential drivers include",
    "allowed_input_sections": sorted(AI_INSIGHT_ALLOWED_INPUT_SECTIONS),
    "forbidden_input_keys": sorted(AI_INSIGHT_FORBIDDEN_INPUT_KEYS),
}

_CAUSAL_PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("this happened because", "potential drivers include"),
    ("happened because", "may relate to"),
    ("was caused by", "may relate to"),
    ("is caused by", "may relate to"),
    ("caused by", "may relate to"),
    ("as a result of", "with possible contribution from"),
    ("resulting from", "with possible contribution from"),
    ("due to the fact that", "with possible contribution from"),
    ("the reason is", "a potential factor is"),
    ("the root cause is", "a potential factor is"),
    ("driven solely by", "potentially related to"),
)

_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?"
)

# Backward-compatible aliases from the prior explanation shape.
_LEGACY_SUMMARY_KEYS = ("summary", "what_happened")
_LEGACY_DRIVERS_KEYS = ("potential_drivers", "drivers")
_LEGACY_ACTION_KEYS = (
    "recommended_action",
    "next_action",
    "recommendation",
)

# Default investigation suggestions by insight type — not facts.
_DEFAULT_ACTIONS: dict[str, str] = {
    "concentration": (
        "Review the top accounts for renewal risk and identify "
        "opportunities to diversify revenue."
    ),
    "growth_decline": (
        "Investigate the largest period-over-period movers and "
        "confirm whether the change is sustained."
    ),
    "trend": (
        "Validate the trend across recent periods and identify "
        "segments contributing most to the movement."
    ),
    "anomaly": (
        "Inspect the anomalous entities or periods and confirm "
        "data quality before acting on the signal."
    ),
    "comparison": (
        "Compare the observed value against the baseline "
        "segments and document material gaps for follow-up."
    ),
    "segment_difference": (
        "Investigate the under- and over-performing segments "
        "and test whether the gap is actionable."
    ),
    "opportunity": (
        "Prioritize the highest-evidence opportunities and "
        "define an owner for next-step validation."
    ),
    "risk": (
        "Assess exposure and define a mitigation or monitoring "
        "plan with the responsible business owner."
    ),
    "contribution": (
        "Review the top contributors and confirm whether "
        "concentration or mix shifts require action."
    ),
    "distribution": (
        "Inspect the distribution tails and material buckets "
        "for operational or commercial follow-up."
    ),
    "relationship": (
        "Validate the relationship with domain stakeholders "
        "before changing process or targeting."
    ),
}

_GENERIC_ACTION = (
    "Review the supporting evidence with the business owner "
    "and decide whether further investigation is warranted."
)

_NO_DRIVER_EVIDENCE = (
    "Insufficient evidence in the current analysis to identify "
    "specific drivers."
)


def build_ai_insight_constraints() -> dict[str, Any]:
    """Copy of anti-hallucination constraints for prompts / tests."""

    return dict(AI_INSIGHT_CONSTRAINTS)


def fact_pack_contains_forbidden_inputs(fact_pack: dict[str, Any]) -> list[str]:
    """Return forbidden raw-data keys found anywhere in a fact pack."""

    found: list[str] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_text = str(key)
                next_path = f"{path}.{key_text}" if path else key_text
                if key_text in AI_INSIGHT_FORBIDDEN_INPUT_KEYS:
                    found.append(next_path)
                walk(value, next_path)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(fact_pack)
    return found


def assert_ai_insight_fact_pack_safe(fact_pack: dict[str, Any]) -> None:
    """Raise if a fact pack includes raw dataset material."""

    forbidden = fact_pack_contains_forbidden_inputs(fact_pack)
    if forbidden:
        raise ValueError(
            "AI Insight fact pack must not include raw dataset inputs: "
            + ", ".join(forbidden)
        )

    extra_sections = sorted(
        set(fact_pack) - AI_INSIGHT_ALLOWED_INPUT_SECTIONS
    )
    if extra_sections:
        raise ValueError(
            "AI Insight fact pack has unsupported top-level sections: "
            + ", ".join(extra_sections)
        )


def _normalize_number_token(token: str) -> str:
    text = token.strip().replace(",", "")
    if text.endswith("%"):
        try:
            return f"{float(text[:-1]) / 100:.6g}"
        except ValueError:
            return text.lower()
    try:
        return f"{float(text):.6g}"
    except ValueError:
        return text.lower()


def collect_allowed_number_tokens(*parts: Any) -> set[str]:
    """Numbers the AI is allowed to restate from provided facts."""

    allowed: set[str] = set()

    def add_from(value: Any) -> None:
        if value is None or isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            allowed.add(f"{float(value):.6g}")
            return
        if isinstance(value, dict):
            for nested in value.values():
                add_from(nested)
            return
        if isinstance(value, list):
            for nested in value:
                add_from(nested)
            return
        text = str(value)
        for match in _NUMBER_PATTERN.findall(text):
            allowed.add(_normalize_number_token(match))

    for part in parts:
        add_from(part)
    return allowed


def hedge_causal_language(text: str | None) -> str:
    """Rewrite causal certainty into hedged / potential language."""

    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    lowered = cleaned.lower()
    for phrase, replacement in _CAUSAL_PHRASE_REPLACEMENTS:
        index = lowered.find(phrase)
        if index < 0:
            continue
        cleaned = (
            cleaned[:index]
            + replacement
            + cleaned[index + len(phrase) :]
        )
        lowered = cleaned.lower()

    # Soften leading hard-cause claims.
    if lowered.startswith("because "):
        cleaned = "A potential factor is " + cleaned[8:]
    return cleaned.strip()


def hedge_potential_drivers(drivers: list[str] | None) -> list[str]:
    """
    Keep drivers as potential factors — never established causes.

    Items are phrased as candidates; UI/prompt use
    "Potential drivers include...".
    """

    hedged: list[str] = []
    for item in drivers or []:
        text = hedge_causal_language(item)
        if not text:
            continue
        lowered = text.lower()
        if lowered.startswith("potential drivers include"):
            text = text.split(":", 1)[-1].strip() or text
        if "because" in lowered:
            text = hedge_causal_language(
                text.replace("Because", "A potential factor is")
                .replace("because", "a potential factor is")
            )
        hedged.append(text)
    return hedged


def _number_is_allowed(token: str, allowed_numbers: set[str]) -> bool:
    """Allow exact matches plus ratio ↔ percent restatements of known facts."""

    normalized = _normalize_number_token(token)
    if normalized in allowed_numbers:
        return True
    try:
        value = float(normalized)
    except ValueError:
        return False

    # "55%" already normalizes to 0.55; also accept "55" when 0.55 is known.
    if not token.strip().endswith("%") and abs(value) >= 1:
        as_ratio = f"{value / 100:.6g}"
        if as_ratio in allowed_numbers:
            return True
    if abs(value) <= 1:
        as_percent = f"{value * 100:.6g}"
        if as_percent in allowed_numbers:
            return True
    return False


def strip_invented_numbers(
    text: str | None,
    *,
    allowed_numbers: set[str],
) -> str:
    """
    Drop sentences that introduce numeric tokens not in the fact pack.

    Prevents inventing or altering calculated values.
    """

    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    kept: list[str] = []
    for part in parts:
        tokens = _NUMBER_PATTERN.findall(part)
        if tokens and any(
            not _number_is_allowed(token, allowed_numbers)
            for token in tokens
        ):
            continue
        kept.append(part)
    return " ".join(kept).strip()
_TYPE_INTERPRETATIONS: dict[str, str] = {
    "concentration": (
        "Results appear concentrated among a small set of "
        "contributors, which may increase exposure if those "
        "accounts change."
    ),
    "growth_decline": (
        "The observed movement suggests a meaningful shift in "
        "performance that may warrant commercial attention."
    ),
    "trend": (
        "The pattern points to a directional change that may "
        "affect planning if it continues."
    ),
    "anomaly": (
        "The observation looks unusual relative to expectations "
        "and may signal an operational or data issue."
    ),
    "comparison": (
        "The gap versus the baseline appears material enough "
        "to review with the responsible owner."
    ),
    "segment_difference": (
        "Performance differs across segments in a way that may "
        "highlight under-served or over-performing areas."
    ),
    "opportunity": (
        "The finding suggests a potential upside if the evidence "
        "is validated with the business team."
    ),
    "risk": (
        "The finding suggests elevated exposure that may deserve "
        "monitoring or mitigation."
    ),
    "contribution": (
        "A small set of contributors appears to drive a large "
        "share of the outcome, which may concentrate outcomes."
    ),
    "distribution": (
        "The distribution shape may reveal pockets of "
        "under- or over-performance worth investigating."
    ),
    "relationship": (
        "The linked measures appear associated in a way that "
        "may inform targeting or process decisions."
    ),
}


@dataclass
class AIInsightContract:
    """
    Structured AI interpretation for a deterministic Insight.

    Separate from facts: never invents metric values.
    """

    summary: str = ""
    why_it_matters: str = ""
    potential_drivers: list[str] = field(default_factory=list)
    recommended_action: str = ""
    caveats: list[str] = field(default_factory=list)
    layer: str = EXPLANATION_LAYER
    source: str = "fallback"  # fallback | ai

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
            "potential_drivers": list(self.potential_drivers),
            "recommended_action": self.recommended_action,
            "caveats": list(self.caveats),
            "layer": self.layer or EXPLANATION_LAYER,
            "source": self.source or "fallback",
        }


# Legacy name kept for imports during transition.
InsightExplanation = AIInsightContract
REQUIRED_EXPLANATION_KEYS = REQUIRED_AI_INSIGHT_KEYS


def empty_ai_insight(*, source: str = "fallback") -> dict[str, Any]:
    return AIInsightContract(source=source).to_dict()


empty_explanation = empty_ai_insight


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def serialize_ai_insight(
    value: AIInsightContract | dict[str, Any] | str | None,
) -> dict[str, Any] | None:
    """Normalize any AI-insight / legacy explanation shape."""

    if value is None:
        return None

    if isinstance(value, AIInsightContract):
        return value.to_dict()

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return AIInsightContract(summary=text, source="fallback").to_dict()

    if not isinstance(value, dict):
        return None

    summary = _first_text(
        *(value.get(key) for key in _LEGACY_SUMMARY_KEYS),
        value.get("finding"),
    )
    why_it_matters = _first_text(
        value.get("why_it_matters"),
        value.get("business_impact"),
    )
    drivers = _as_string_list(
        value.get("potential_drivers")
        if value.get("potential_drivers") is not None
        else value.get("drivers")
    )
    recommended_action = _first_text(
        *(value.get(key) for key in _LEGACY_ACTION_KEYS)
    )
    caveats = _as_string_list(value.get("caveats"))

    if not any(
        [summary, why_it_matters, drivers, recommended_action, caveats]
    ):
        return None

    return AIInsightContract(
        summary=summary,
        why_it_matters=why_it_matters,
        potential_drivers=drivers,
        recommended_action=recommended_action,
        caveats=caveats,
        layer=_first_text(value.get("layer")) or EXPLANATION_LAYER,
        source=_first_text(value.get("source")) or "fallback",
    ).to_dict()


# Legacy alias.
serialize_insight_explanation = serialize_ai_insight


def _as_insight_dict(insight: Any) -> dict[str, Any] | None:
    if insight is None:
        return None
    if isinstance(insight, dict):
        return dict(insight)
    if hasattr(insight, "to_dict"):
        payload = insight.to_dict()
        return payload if isinstance(payload, dict) else None
    return None


def _evidence_dict(insight: dict[str, Any]) -> dict[str, Any]:
    evidence = insight.get("evidence")
    if hasattr(evidence, "to_dict"):
        evidence = evidence.to_dict()
    return evidence if isinstance(evidence, dict) else {}


def _format_number(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or None
    if number == int(number) and abs(number) >= 1:
        return f"{int(number):,}"
    if abs(number) <= 1:
        return f"{number:.1%}"
    return f"{number:,.4g}"


def extract_evidence_supported_drivers(
    insight: dict[str, Any],
    *,
    max_drivers: int = 3,
) -> list[str]:
    """
    Derive driver statements only from evidence / existing overlays.

    Never invents causes that are not present in the payload.
    """

    drivers: list[str] = []
    seen: set[str] = set()

    def add(text: str | None) -> None:
        cleaned = str(text or "").strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        drivers.append(cleaned)

    for item in insight.get("potential_drivers") or []:
        add(str(item))

    for key in ("ai_interpretation", "explanation"):
        existing = insight.get(key)
        if isinstance(existing, dict):
            for item in (
                existing.get("potential_drivers")
                or existing.get("drivers")
                or []
            ):
                add(str(item))

    evidence = _evidence_dict(insight)
    show = evidence.get("show_evidence")
    if not isinstance(show, dict):
        show = {}

    breakdown = show.get("breakdown") if isinstance(show, dict) else {}
    if not isinstance(breakdown, dict):
        breakdown = {}

    entities = breakdown.get("entities") or evidence.get("entities") or []
    if isinstance(entities, list):
        ranked: list[tuple[float, str]] = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            label = str(
                entity.get("label") or entity.get("id") or ""
            ).strip()
            if not label:
                continue
            share = entity.get("share")
            value = entity.get("value")
            share_text = None
            if share is not None:
                try:
                    share_num = float(share)
                    share_text = (
                        f"{share_num:.1%}"
                        if abs(share_num) <= 1
                        else _format_number(share_num)
                    )
                except (TypeError, ValueError):
                    share_text = _format_number(share)
            value_text = _format_number(value)
            detail_parts = [
                part for part in (value_text, share_text) if part
            ]
            detail = (
                f" ({', '.join(detail_parts)})" if detail_parts else ""
            )
            try:
                rank_key = (
                    float(share)
                    if share is not None
                    else float(value) if value is not None else 0.0
                )
            except (TypeError, ValueError):
                rank_key = 0.0
            ranked.append(
                (
                    abs(rank_key),
                    f"{label} is a material contributor{detail}",
                )
            )
        ranked.sort(key=lambda item: item[0], reverse=True)
        for _, statement in ranked[:max_drivers]:
            add(statement)

    distribution = None
    if isinstance(breakdown.get("distribution"), dict):
        distribution = breakdown["distribution"].get("buckets")
    if distribution is None:
        distribution = evidence.get("distribution") or []
    if isinstance(distribution, list) and not drivers:
        for bucket in distribution[:max_drivers]:
            if not isinstance(bucket, dict):
                continue
            label = str(
                bucket.get("label") or bucket.get("id") or ""
            ).strip()
            if not label:
                continue
            share_text = None
            if bucket.get("share") is not None:
                try:
                    share_num = float(bucket.get("share"))
                    share_text = (
                        f"{share_num:.1%}"
                        if abs(share_num) <= 1
                        else _format_number(share_num)
                    )
                except (TypeError, ValueError):
                    share_text = _format_number(bucket.get("share"))
            add(
                f"{label} appears in the supporting distribution"
                + (f" ({share_text})" if share_text else "")
            )

    metrics = evidence.get("metrics") or []
    if isinstance(metrics, list) and not drivers:
        for metric in metrics[:max_drivers]:
            if not isinstance(metric, dict):
                continue
            key = str(metric.get("key") or "").lower()
            if key in {
                "difference",
                "percentage_change",
                "magnitude",
                "baseline",
                "observed_value",
                "threshold",
            }:
                continue
            label = str(
                metric.get("label") or metric.get("key") or ""
            ).strip()
            value_text = _format_number(metric.get("value"))
            if label and value_text:
                add(f"{label} measured {value_text}")

    return drivers[:max_drivers]


def extract_caveats(insight: dict[str, Any]) -> list[str]:
    """Build caveats from data-quality / sample limitations only."""

    caveats: list[str] = []
    seen: set[str] = set()

    def add(text: str | None) -> None:
        cleaned = str(text or "").strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        caveats.append(cleaned)

    for key in ("ai_interpretation", "explanation"):
        existing = insight.get(key)
        if isinstance(existing, dict):
            for item in existing.get("caveats") or []:
                add(str(item))

    evidence = _evidence_dict(insight)
    data_quality = evidence.get("data_quality") or {}
    if not isinstance(data_quality, dict):
        data_quality = {}

    for issue in data_quality.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        description = str(issue.get("description") or "").strip()
        if description:
            add(description)
            continue
        label = str(issue.get("label") or issue.get("type") or "").strip()
        if label:
            add(f"Data-quality limitation: {label}")

    for note in data_quality.get("notes") or []:
        add(str(note))

    if data_quality.get("affects_reliability"):
        add(
            "Data-quality limitations may affect the reliability "
            "of this interpretation."
        )

    confidence = str(insight.get("confidence") or "").strip().lower()
    if confidence == "low":
        add(
            "Confidence in the underlying finding is low; "
            "treat this interpretation cautiously."
        )

    return caveats


def _summary_from_insight(insight: dict[str, Any]) -> str:
    """Interpretive summary — not a restatement of raw metrics."""

    for key in ("ai_interpretation", "explanation"):
        existing = insight.get(key)
        if isinstance(existing, dict):
            summary = _first_text(
                existing.get("summary"),
                existing.get("what_happened"),
            )
            if summary:
                return summary

    insight_type = str(insight.get("insight_type") or "").strip().lower()
    interpreted = _TYPE_INTERPRETATIONS.get(insight_type)
    if interpreted:
        return interpreted

    title = str(insight.get("title") or "This finding").strip()
    return (
        f"{title} may have business significance based on the "
        "deterministic analysis result."
    )


def _why_it_matters_from_insight(insight: dict[str, Any]) -> str:
    impact = str(insight.get("business_impact") or "").strip()
    if impact:
        return impact

    for key in ("ai_interpretation", "explanation"):
        existing = insight.get(key)
        if isinstance(existing, dict):
            text = str(existing.get("why_it_matters") or "").strip()
            if text:
                return text

    importance = str(insight.get("importance") or "").strip().lower()
    insight_type = str(insight.get("insight_type") or "finding").strip()
    title = str(insight.get("title") or "This finding").strip()

    significance = {
        "high": "high business importance",
        "medium": "moderate business importance",
        "low": "lower relative importance",
    }.get(importance, "notable business relevance")

    return (
        f"{title} is a {insight_type.replace('_', ' ')} signal with "
        f"{significance}. Review whether the exposure or opportunity "
        "warrants action."
    )


def _action_from_insight(insight: dict[str, Any]) -> str:
    recommendation = str(insight.get("recommendation") or "").strip()
    if recommendation:
        return recommendation

    for key in ("ai_interpretation", "explanation"):
        existing = insight.get(key)
        if isinstance(existing, dict):
            action = _first_text(
                existing.get("recommended_action"),
                existing.get("next_action"),
                existing.get("recommendation"),
            )
            if action:
                return action

    insight_type = str(insight.get("insight_type") or "").strip().lower()
    return _DEFAULT_ACTIONS.get(insight_type, _GENERIC_ACTION)


def _compact_entities(entities: Any, *, limit: int = 10) -> list[dict[str, Any]]:
    """Evidence entity labels/shares only — never raw transaction rows."""

    if not isinstance(entities, list):
        return []
    compacted: list[dict[str, Any]] = []
    for entity in entities[:limit]:
        if not isinstance(entity, dict):
            continue
        label = str(entity.get("label") or entity.get("id") or "").strip()
        if not label:
            continue
        item: dict[str, Any] = {"label": label}
        if entity.get("id") is not None:
            item["id"] = entity.get("id")
        if entity.get("value") is not None:
            item["value"] = entity.get("value")
        if entity.get("share") is not None:
            item["share"] = entity.get("share")
        if entity.get("unit") is not None:
            item["unit"] = entity.get("unit")
        compacted.append(item)
    return compacted


def _dataset_context_from_insight(payload: dict[str, Any]) -> dict[str, Any]:
    """Relevant dataset metadata only — not the raw dataset."""

    traceability = payload.get("traceability")
    dataset = None
    if isinstance(traceability, dict):
        dataset = traceability.get("dataset")
    if not isinstance(dataset, dict):
        dataset = {}

    return {
        "dataset_id": dataset.get("dataset_id"),
        "dataset_version": dataset.get("dataset_version")
        or dataset.get("version"),
        "dataset_label": dataset.get("dataset_label")
        or dataset.get("label")
        or dataset.get("identity"),
        "analyzed_at": dataset.get("analyzed_at"),
        "source_columns": list(
            dataset.get("source_columns")
            or payload.get("source_columns")
            or []
        ),
        "filters": dataset.get("filters") or [],
        "records_excluded": dataset.get("records_excluded"),
        "analytical_method": dataset.get("analytical_method")
        or payload.get("analysis_type"),
    }


def _data_quality_limitations(
    payload: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Data-quality limitations the AI may cite — not invent."""

    dq = evidence.get("data_quality")
    if not isinstance(dq, dict):
        show = evidence.get("show_evidence")
        if isinstance(show, dict) and isinstance(show.get("data_quality"), dict):
            dq = show["data_quality"]
        else:
            dq = {}

    return {
        "issues": list(dq.get("issues") or []),
        "affects_reliability": bool(dq.get("affects_reliability")),
        "caveats": extract_caveats(payload),
        "confidence": payload.get("confidence"),
    }


def build_ai_insight_fact_pack(insight: Any) -> dict[str, Any]:
    """
    Allowed AI inputs only:

    - structured_insight
    - evidence
    - dataset_context
    - data_quality_limitations

    Never includes the raw dataset / dataframe rows.
    """

    payload = _as_insight_dict(insight) or {}
    evidence = _evidence_dict(payload)
    show = evidence.get("show_evidence")
    entities = evidence.get("entities") or []
    if not entities and isinstance(show, dict):
        breakdown = show.get("breakdown") or {}
        if isinstance(breakdown, dict):
            entities = breakdown.get("entities") or []

    methodology = evidence.get("methodology") or []
    if not methodology and isinstance(show, dict):
        methodology = show.get("methodology") or []

    fact_pack = {
        "constraints": build_ai_insight_constraints(),
        "structured_insight": {
            "insight_id": payload.get("insight_id"),
            "title": payload.get("title"),
            "category": payload.get("category"),
            "insight_type": payload.get("insight_type"),
            "finding": payload.get("finding"),
            "metric": payload.get("metric"),
            "observed_value": payload.get("observed_value"),
            "baseline": payload.get("baseline"),
            "magnitude": payload.get("magnitude"),
            "magnitude_unit": payload.get("magnitude_unit"),
            "importance": payload.get("importance"),
            "confidence": payload.get("confidence"),
            "tier": payload.get("tier"),
            "business_impact": payload.get("business_impact"),
            "dimensions": list(payload.get("dimensions") or []),
            "analysis_type": payload.get("analysis_type"),
        },
        "evidence": {
            "summary": evidence.get("summary"),
            "metrics": evidence.get("metrics") or [],
            "entities": _compact_entities(entities),
            "methodology": methodology,
        },
        "dataset_context": _dataset_context_from_insight(payload),
        "data_quality_limitations": _data_quality_limitations(
            payload, evidence
        ),
        "evidence_supported_drivers": extract_evidence_supported_drivers(
            payload
        ),
    }
    assert_ai_insight_fact_pack_safe(fact_pack)
    return fact_pack


build_insight_explanation_fact_pack = build_ai_insight_fact_pack


def sanitize_ai_insight_contract(
    value: AIInsightContract | dict[str, Any] | None,
    *,
    insight: Any = None,
    fact_pack: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """
    Enforce anti-hallucination rules on an AI Insight Contract.

    - hedges causal language
    - drops invented numeric claims
    - keeps drivers as potential factors
    """

    serialized = serialize_ai_insight(value) or empty_ai_insight(
        source=source or "fallback"
    )
    pack = fact_pack or build_ai_insight_fact_pack(insight or {})
    allowed_numbers = collect_allowed_number_tokens(
        pack.get("structured_insight"),
        pack.get("evidence"),
        pack.get("dataset_context"),
        pack.get("data_quality_limitations"),
        pack.get("evidence_supported_drivers"),
    )

    summary = strip_invented_numbers(
        hedge_causal_language(serialized.get("summary")),
        allowed_numbers=allowed_numbers,
    )
    why = strip_invented_numbers(
        hedge_causal_language(serialized.get("why_it_matters")),
        allowed_numbers=allowed_numbers,
    )
    drivers = hedge_potential_drivers(
        [
            strip_invented_numbers(
                item,
                allowed_numbers=allowed_numbers,
            )
            for item in (serialized.get("potential_drivers") or [])
        ]
    )
    drivers = [item for item in drivers if item]
    if not drivers:
        drivers = [_NO_DRIVER_EVIDENCE]

    action = strip_invented_numbers(
        hedge_causal_language(serialized.get("recommended_action")),
        allowed_numbers=allowed_numbers,
    )
    caveats = [
        strip_invented_numbers(
            hedge_causal_language(item),
            allowed_numbers=allowed_numbers,
        )
        for item in (serialized.get("caveats") or [])
    ]
    caveats = [item for item in caveats if item]

    return AIInsightContract(
        summary=summary,
        why_it_matters=why,
        potential_drivers=drivers,
        recommended_action=action,
        caveats=caveats,
        layer=str(serialized.get("layer") or EXPLANATION_LAYER),
        source=str(
            source or serialized.get("source") or "fallback"
        ),
    ).to_dict()


def build_fallback_ai_insight(insight: Any) -> dict[str, Any]:
    """
    Deterministic AI-contract fallback from Insight facts + evidence.

    Used until an LLM is wired. Does not invent metric values.
    """

    payload = _as_insight_dict(insight)
    if payload is None:
        return empty_ai_insight(source="fallback")

    drivers = extract_evidence_supported_drivers(payload)
    if not drivers:
        drivers = [_NO_DRIVER_EVIDENCE]

    draft = AIInsightContract(
        summary=_summary_from_insight(payload),
        why_it_matters=_why_it_matters_from_insight(payload),
        potential_drivers=drivers,
        recommended_action=_action_from_insight(payload),
        caveats=extract_caveats(payload),
        layer=EXPLANATION_LAYER,
        source="fallback",
    ).to_dict()
    return sanitize_ai_insight_contract(
        draft,
        insight=payload,
        source="fallback",
    )


build_fallback_insight_explanation = build_fallback_ai_insight


def apply_ai_insight_to_insight(
    insight: Any,
    ai_insight: AIInsightContract | dict[str, Any] | None,
    *,
    sync_legacy_fields: bool = True,
) -> dict[str, Any] | None:
    """
    Attach the AI Insight Contract onto a serialized Insight.

    Deterministic ``finding`` is left untouched. Optional legacy
    mirrors fill empty ``potential_drivers`` / ``recommendation``.
    """

    payload = _as_insight_dict(insight)
    if payload is None:
        return None

    serialized = serialize_ai_insight(ai_insight)
    if serialized is None:
        serialized = build_fallback_ai_insight(payload)
    else:
        serialized = sanitize_ai_insight_contract(
            serialized,
            insight=payload,
            source=str(serialized.get("source") or "fallback"),
        )

    payload["ai_interpretation"] = serialized
    # Keep legacy key temporarily so older UI clients still render.
    payload["explanation"] = {
        "what_happened": serialized.get("summary") or "",
        "why_it_matters": serialized.get("why_it_matters") or "",
        "drivers": list(serialized.get("potential_drivers") or []),
        "next_action": serialized.get("recommended_action") or "",
        "layer": serialized.get("layer"),
        "source": serialized.get("source"),
        # Forward-compatible mirrors.
        "summary": serialized.get("summary") or "",
        "potential_drivers": list(
            serialized.get("potential_drivers") or []
        ),
        "recommended_action": serialized.get("recommended_action") or "",
        "caveats": list(serialized.get("caveats") or []),
    }

    if sync_legacy_fields:
        existing_drivers = [
            str(item).strip()
            for item in (payload.get("potential_drivers") or [])
            if str(item).strip()
        ]
        if not existing_drivers:
            synced = [
                item
                for item in serialized.get("potential_drivers") or []
                if item and item != _NO_DRIVER_EVIDENCE
            ]
            payload["potential_drivers"] = synced

        if not str(payload.get("recommendation") or "").strip():
            payload["recommendation"] = (
                serialized.get("recommended_action") or None
            )

    return payload


apply_explanation_to_insight = apply_ai_insight_to_insight


def attach_ai_insights_to_insights(
    insights: list[Any] | None,
    *,
    insight_ids: set[str] | None = None,
    generator: Any = None,
    sync_legacy_fields: bool = True,
) -> list[dict[str, Any]]:
    """Generate / attach AI contracts for selected Insights."""

    generate = generator or build_fallback_ai_insight
    updated: list[dict[str, Any]] = []

    for item in insights or []:
        payload = _as_insight_dict(item)
        if payload is None:
            continue

        insight_id = str(payload.get("insight_id") or "").strip()
        if insight_ids is not None and insight_id not in insight_ids:
            updated.append(payload)
            continue

        existing = serialize_ai_insight(
            payload.get("ai_interpretation") or payload.get("explanation")
        )
        if existing and existing.get("summary"):
            applied = apply_ai_insight_to_insight(
                payload,
                existing,
                sync_legacy_fields=sync_legacy_fields,
            )
            if applied is not None:
                updated.append(applied)
            continue

        applied = apply_ai_insight_to_insight(
            payload,
            generate(payload),
            sync_legacy_fields=sync_legacy_fields,
        )
        if applied is not None:
            updated.append(applied)

    return updated


attach_explanations_to_insights = attach_ai_insights_to_insights


def explain_recommended_insights(
    *,
    promoted_insights: list[Any] | None,
    initial_results: dict[str, Any] | None = None,
    generator: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Attach AI Insight Contracts to the recommended set.

    Returns ``(promoted_insights, initial_results)``.
    """

    from .initial_results import build_initial_results

    results = dict(initial_results or {})
    if not results:
        results = build_initial_results(promoted_insights)

    recommended_ids = {
        str(item).strip()
        for item in (results.get("recommended_insight_ids") or [])
        if str(item).strip()
    }
    if not recommended_ids:
        for item in results.get("recommended_insights") or []:
            if isinstance(item, dict) and item.get("insight_id"):
                recommended_ids.add(str(item["insight_id"]))

    promoted = attach_ai_insights_to_insights(
        promoted_insights,
        insight_ids=recommended_ids or None,
        generator=generator,
    )

    by_id = {
        str(item.get("insight_id") or ""): item
        for item in promoted
        if item.get("insight_id")
    }

    recommended: list[dict[str, Any]] = []
    for item in results.get("recommended_insights") or []:
        if not isinstance(item, dict):
            continue
        insight_id = str(item.get("insight_id") or "")
        recommended.append(dict(by_id.get(insight_id) or item))

    if recommended_ids and not recommended:
        recommended = [
            by_id[insight_id]
            for insight_id in results.get("recommended_insight_ids") or []
            if insight_id in by_id
        ]

    if not recommended_ids:
        recommended = attach_ai_insights_to_insights(
            recommended or results.get("recommended_insights"),
            generator=generator,
        )

    results["recommended_insights"] = recommended
    results["recommended_insight_ids"] = [
        str(item.get("insight_id") or "")
        for item in recommended
        if item.get("insight_id")
    ]
    results["recommended_count"] = len(recommended)
    return promoted, results
