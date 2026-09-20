"""
Reproducible calculation specs for findings and Insights.

Retains enough structured information for the engine to
reproduce a result — distinct from narrative methodology
strings. Not required to be end-user-facing yet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# Canonical keys for the reproducibility contract.
REQUIRED_CALCULATION_KEYS: frozenset[str] = frozenset(
    {
        "analysis_type",
        "measure",
        "dimension",
        "aggregation",
        "grouping",
        "ranking",
        "top_n",
        "comparison",
        "filters",
        "source_columns",
        "parameters",
    }
)

# Common aggregation aliases → uppercase canonical form.
_AGGREGATION_ALIASES: dict[str, str] = {
    "sum": "SUM",
    "total": "SUM",
    "avg": "AVG",
    "average": "AVG",
    "mean": "AVG",
    "count": "COUNT",
    "n": "COUNT",
    "min": "MIN",
    "max": "MAX",
    "median": "MEDIAN",
    "share": "SHARE",
    "ratio": "RATIO",
}


@dataclass
class CalculationSpec:
    """
    Machine-readable recipe to reproduce an analytical result.

    Example (customer concentration):

        analysis_type: customer_concentration
        measure: revenue
        dimension: customer
        aggregation: SUM
        grouping: customer_id
        ranking: descending revenue
        top_n: 10
        comparison: top_n / total
    """

    analysis_type: str | None = None
    measure: str | None = None
    dimension: str | None = None
    aggregation: str | None = None
    grouping: str | list[str] | None = None
    ranking: str | None = None
    top_n: int | None = None
    comparison: str | None = None
    filters: list[dict[str, Any]] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    # Free-form extras (windows, thresholds, join keys, etc.).
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        grouping = self.grouping
        if isinstance(grouping, list):
            grouping = [
                str(item).strip()
                for item in grouping
                if str(item).strip()
            ]
        elif grouping is not None:
            grouping = str(grouping).strip() or None

        return {
            "analysis_type": self.analysis_type,
            "measure": self.measure,
            "dimension": self.dimension,
            "aggregation": self.aggregation,
            "grouping": grouping,
            "ranking": self.ranking,
            "top_n": self.top_n,
            "comparison": self.comparison,
            "filters": [dict(item) for item in self.filters],
            "source_columns": list(self.source_columns),
            "parameters": dict(self.parameters),
        }

    @property
    def is_populated(self) -> bool:
        """True when at least one reproducibility field is set."""

        return any(
            [
                self.analysis_type,
                self.measure,
                self.dimension,
                self.aggregation,
                self.grouping,
                self.ranking,
                self.top_n is not None,
                self.comparison,
                bool(self.filters),
                bool(self.source_columns),
                bool(self.parameters),
            ]
        )


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_aggregation(value: Any) -> str | None:
    text = _clean_str(value)
    if text is None:
        return None
    return _AGGREGATION_ALIASES.get(text.lower(), text.upper())


def _normalize_grouping(value: Any) -> str | list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _clean_str(value)
    if isinstance(value, (list, tuple)):
        items = [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        return items
    return _clean_str(value)


def _normalize_top_n(value: Any) -> int | None:
    if value is None or value is False:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _normalize_filters(values: Any) -> list[dict[str, Any]]:
    if not values:
        return []
    if isinstance(values, dict):
        values = [values]
    result: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, dict):
            result.append(dict(item))
        elif isinstance(item, str) and item.strip():
            result.append(
                {
                    "expression": item.strip(),
                    "label": item.strip(),
                }
            )
    return result


def _normalize_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    return [
        str(item).strip()
        for item in values
        if str(item).strip()
    ]


def build_calculation_spec(
    *,
    analysis_type: str | None = None,
    measure: str | None = None,
    dimension: str | None = None,
    aggregation: str | None = None,
    grouping: str | list[str] | None = None,
    ranking: str | None = None,
    top_n: int | None = None,
    comparison: str | None = None,
    filters: list[Any] | None = None,
    source_columns: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
    existing: CalculationSpec | dict[str, Any] | None = None,
) -> CalculationSpec:
    """
    Assemble a calculation spec, merging explicit fields over
    an existing payload. Empty fields stay null / [].
    """

    base: dict[str, Any] = {}
    if isinstance(existing, CalculationSpec):
        base = existing.to_dict()
    elif isinstance(existing, dict):
        base = dict(existing)

    resolved_analysis = _clean_str(analysis_type) or _clean_str(
        base.get("analysis_type")
    )
    resolved_measure = _clean_str(measure) or _clean_str(
        base.get("measure")
    )
    resolved_dimension = _clean_str(dimension) or _clean_str(
        base.get("dimension")
    )
    resolved_aggregation = _normalize_aggregation(
        aggregation if aggregation is not None else base.get("aggregation")
    )
    resolved_grouping = _normalize_grouping(
        grouping if grouping is not None else base.get("grouping")
    )
    resolved_ranking = _clean_str(ranking) or _clean_str(
        base.get("ranking")
    )
    resolved_top_n = _normalize_top_n(
        top_n if top_n is not None else base.get("top_n")
    )
    resolved_comparison = _clean_str(comparison) or _clean_str(
        base.get("comparison")
    )

    resolved_filters = _normalize_filters(filters)
    if not resolved_filters:
        resolved_filters = _normalize_filters(base.get("filters"))

    resolved_columns = _normalize_string_list(source_columns)
    if not resolved_columns:
        resolved_columns = _normalize_string_list(
            base.get("source_columns")
        )

    resolved_params = dict(base.get("parameters") or {})
    if isinstance(parameters, dict) and parameters:
        resolved_params.update(dict(parameters))

    return CalculationSpec(
        analysis_type=resolved_analysis,
        measure=resolved_measure,
        dimension=resolved_dimension,
        aggregation=resolved_aggregation,
        grouping=resolved_grouping,
        ranking=resolved_ranking,
        top_n=resolved_top_n,
        comparison=resolved_comparison,
        filters=resolved_filters,
        source_columns=resolved_columns,
        parameters=resolved_params,
    )


def serialize_calculation_spec(
    spec: CalculationSpec | dict[str, Any] | None,
    *,
    analysis_type: str | None = None,
    measure: str | None = None,
    dimension: str | None = None,
    aggregation: str | None = None,
    grouping: str | list[str] | None = None,
    ranking: str | None = None,
    top_n: int | None = None,
    comparison: str | None = None,
    filters: list[Any] | None = None,
    source_columns: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize any calculation shape into the canonical JSON dict."""

    structured = build_calculation_spec(
        analysis_type=analysis_type,
        measure=measure,
        dimension=dimension,
        aggregation=aggregation,
        grouping=grouping,
        ranking=ranking,
        top_n=top_n,
        comparison=comparison,
        filters=filters,
        source_columns=source_columns,
        parameters=parameters,
        existing=spec,
    )
    return structured.to_dict()


def infer_calculation_spec(
    *,
    analysis_type: str | None = None,
    metric: str | None = None,
    dimensions: list[str] | None = None,
    source_columns: list[str] | None = None,
    filters: list[Any] | None = None,
    comparison: str | None = None,
    existing: CalculationSpec | dict[str, Any] | None = None,
) -> CalculationSpec:
    """
    Best-effort defaults when a rule omits an explicit recipe.

    Prefer explicit ``existing`` fields; only fill gaps from
    finding context so reproducibility is retained even for
    lightly annotated analyses.
    """

    base: dict[str, Any] = {}
    if isinstance(existing, CalculationSpec):
        base = existing.to_dict()
    elif isinstance(existing, dict):
        base = dict(existing)

    dims = _normalize_string_list(dimensions)
    columns = _normalize_string_list(source_columns)
    metric_name = _clean_str(metric)

    inferred_dimension = dims[0] if dims else None
    inferred_measure = None
    inferred_grouping = None
    inferred_aggregation = None

    # Prefer a measure-like source column when present.
    for column in columns:
        lowered = column.lower()
        if any(
            token in lowered
            for token in (
                "revenue",
                "sales",
                "amount",
                "profit",
                "margin",
                "qty",
                "quantity",
            )
        ):
            inferred_measure = column
            break

    for column in columns:
        lowered = column.lower()
        if lowered.endswith("_id") or lowered in {
            "customer",
            "product",
            "region",
            "segment",
        }:
            inferred_grouping = column
            break

    if metric_name:
        lowered_metric = metric_name.lower()
        if "share" in lowered_metric or "ratio" in lowered_metric:
            inferred_aggregation = "SHARE"
        elif "count" in lowered_metric:
            inferred_aggregation = "COUNT"
        elif inferred_measure or base.get("measure"):
            inferred_aggregation = "SUM"

    # Only pass inferred values for gaps — never clobber an
    # explicit recipe supplied by the analysis rule.
    return build_calculation_spec(
        analysis_type=analysis_type,
        measure=None if base.get("measure") else inferred_measure,
        dimension=(
            None if base.get("dimension") else inferred_dimension
        ),
        aggregation=(
            None
            if base.get("aggregation")
            else inferred_aggregation
        ),
        grouping=None if base.get("grouping") else inferred_grouping,
        comparison=comparison,
        filters=filters,
        source_columns=columns,
        parameters=(
            {"metric": metric_name}
            if metric_name and "metric" not in (base.get("parameters") or {})
            else None
        ),
        existing=existing,
    )
