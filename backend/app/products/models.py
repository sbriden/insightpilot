from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Dict


@dataclass
class FieldOpportunity:
    field: str

    description: str = ""

    analyses: List[str] = field(
        default_factory=list
    )

    metrics: List[str] = field(
        default_factory=list
    )

    priority: str = "medium"

    required: bool = False


@dataclass
class DataProductDefinition:
    """
    Defines a reusable data product that InsightPilot
    can create from a compatible dataset.
    """

    id: str

    name: str

    description: str

    business_purpose: str = ""

    dataset_types: List[str] = field(
        default_factory=list
    )

    grain: str = ""

    required_fields: List[str] = field(
        default_factory=list
    )

    optional_fields: List[str] = field(
        default_factory=list
    )

    analyses: List[str] = field(
        default_factory=list
    )

    field_opportunities: List[
        FieldOpportunity
    ] = field(
        default_factory=list
    )


@dataclass
class DataProduct:
    """
    Represents an actual data product generated
    from an uploaded dataset.
    """

    id: str

    name: str

    description: str

    business_purpose: str = ""

    source_dataset: str = ""

    status: str = "draft"

    coverage: int = 0

    version: int = 1

    definition_id: str = ""

    dataset_identity: str = ""

    previous_product_id: str | None = None

    analyses: List[Any] = field(
        default_factory=list
    )

    metrics: List[Dict[str, Any]] = field(
        default_factory=list
    )

    insights: List[Dict[str, Any]] = field(
        default_factory=list
    )

    dashboards: List[Dict[str, Any]] = field(
        default_factory=list
    )

    change_summary: Dict[str, Any] | None = None

    executive_summary: Dict[str, Any] | None = None

    health: Dict[str, Any] | None = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime | None = None

    updated_at: datetime | None = None


@dataclass
class DataProductAnalysis:
    """
    An analysis included in a data product.
    """

    id: str
    title: str
    description: str = ""


@dataclass
class DataProductMetric:
    """
    KPI or metric exposed by a data product.
    """

    id: str
    name: str
    value: Any = None
    description: str = ""
    unit: Optional[str] = None


@dataclass
class DataProductInsight:
    """
    Insight surfaced by a data product.
    """

    id: str
    title: str
    message: str
    severity: str = "low"
    priority: str = "low"
    category: Optional[str] = None
    what_happened: str = ""
    why_it_matters: str = ""
    recommended_action: str = ""


@dataclass
class DataCoverageResult:
    product_id: str

    product_name: str

    coverage_percent: int

    required_coverage_percent: int = 0

    required_fields: List[str] = field(
        default_factory=list
    )

    mapped_required_fields: List[str] = field(
        default_factory=list
    )

    missing_required_fields: List[str] = field(
        default_factory=list
    )

    available_optional_fields: List[str] = field(
        default_factory=list
    )

    missing_optional_fields: List[str] = field(
        default_factory=list
    )

    opportunities: List[Dict[str, Any]] = field(
        default_factory=list
    )

    can_analyze: bool = False

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )
