from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Literal, Optional, Dict


# Origin of a data product in the catalog / on a persisted instance.
# user_created — built from a user's dataset (e.g. upload sales → Customer Intelligence)
# native       — defined and maintained by InsightPilot (e.g. Fantasy Football)
ProductType = Literal["user_created", "native"]

PRODUCT_TYPE_USER_CREATED: ProductType = "user_created"
PRODUCT_TYPE_NATIVE: ProductType = "native"

# Legacy persisted value before native rename.
_LEGACY_PRE_CANNED = "pre_canned"


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
    Catalog template for a reusable data product.

    product_type distinguishes user-created products
    (from a user's dataset) from native products
    maintained by InsightPilot.
    """

    id: str

    name: str

    description: str

    business_purpose: str = ""

    product_type: ProductType = (
        PRODUCT_TYPE_USER_CREATED
    )

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
    A materialized data product instance.

    May be user-created (from an uploaded dataset) or
    native (InsightPilot-maintained), per product_type.
    """

    id: str

    name: str

    description: str

    business_purpose: str = ""

    product_type: ProductType = (
        PRODUCT_TYPE_USER_CREATED
    )

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

    # Aggregated from dashboards; also nested inside
    # dashboards JSONB for persistence without a new column.
    candidate_findings: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # Validated subset of candidates (structural gate).
    validated_findings: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # Insights from insight-eligible validated findings only.
    # Rebuilt on read from dashboards (same pattern as findings).
    promoted_insights: List[Dict[str, Any]] = field(
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
