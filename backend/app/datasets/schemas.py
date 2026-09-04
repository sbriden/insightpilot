from typing import List, Optional

from pydantic import BaseModel, Field


class FieldOpportunitySchema(BaseModel):

    field: str

    description: str = ""

    analyses: List[str] = Field(
        default_factory=list
    )

    metrics: List[str] = Field(
        default_factory=list
    )

    priority: str = "medium"

    required: bool = False


class DataProductRequirement(BaseModel):

    id: str

    name: str

    description: str

    grain: str

    required_fields: List[str]

    optional_fields: List[str]

    analyses: List[str]

    field_opportunities: List[
        FieldOpportunitySchema
    ] = Field(
        default_factory=list
    )


class DatasetTypeRequirementsResponse(BaseModel):

    dataset_type: str

    data_products: List[
        DataProductRequirement
    ]


class SavedFieldMappingItem(BaseModel):

    requiredField: str

    uploadedField: Optional[str] = None

    matchType: str = "manual"

    confidence: float = 0

    required: bool = False

    valid: bool = False


class SaveFieldMappingsRequest(BaseModel):

    uploaded_columns: List[str]

    mappings: List[SavedFieldMappingItem]


class SavedFieldMappingsResponse(BaseModel):

    dataset_type_id: str

    uploaded_columns: List[str]

    mappings: List[SavedFieldMappingItem]

    updated_at: Optional[str] = None


class DatasetColumnInput(BaseModel):

    name: str

    dataType: Optional[str] = None

    sampleValue: Optional[str] = None


class BusinessConceptSchema(BaseModel):

    concept: str

    sourceColumn: str

    dataType: str

    confidence: float

    role: str


class ConceptIdentificationResponse(BaseModel):

    concepts: List[BusinessConceptSchema]

    columnCount: int

    identifiedCount: int


class IdentifyConceptsRequest(BaseModel):

    columns: List[DatasetColumnInput]


class AnalyticalCapabilitySchema(BaseModel):

    capability: str

    label: str

    supported: bool

    confidence: float

    required_concepts: List[str]

    explanation: str

    matched_columns: List[str] = Field(
        default_factory=list
    )


class CapabilityDetectionResponse(BaseModel):

    capabilities: List[AnalyticalCapabilitySchema]

    supported_count: int

    total_count: int


class DetectCapabilitiesRequest(BaseModel):

    concepts: List[BusinessConceptSchema]


# ── Dataset classification ────────────────────────────────────

class ClassifyDatasetRequest(BaseModel):

    concepts: List[BusinessConceptSchema]


class AlternativeArchetype(BaseModel):

    archetype: str

    label: str

    confidence: float


class ArchetypeScore(BaseModel):

    archetype: str

    label: str

    score: float


class ClassifyDatasetResponse(BaseModel):

    primary_archetype: Optional[str] = None

    label: str

    confidence: float

    supporting_concepts: List[str] = Field(default_factory=list)

    explanation: str

    alternative_archetypes: List[AlternativeArchetype] = Field(
        default_factory=list
    )

    all_scores: List[ArchetypeScore] = Field(default_factory=list)


# ── Dataset grain determination ───────────────────────────────

class ColumnStatInput(BaseModel):

    name: str

    unique_ratio: Optional[float] = None

    unique_count: Optional[int] = None

    row_count: Optional[int] = None


class DetermineGrainRequest(BaseModel):

    concepts: List[BusinessConceptSchema]

    column_stats: List[ColumnStatInput] = Field(
        default_factory=list
    )


class GrainEvidence(BaseModel):

    signal: str

    columns: List[str] = Field(default_factory=list)

    detail: str = ""


class AlternativeGrain(BaseModel):

    grain: str

    label: str

    confidence: float


class GrainScore(BaseModel):

    grain: str

    label: str

    score: float


class DetermineGrainResponse(BaseModel):

    grain: str

    label: str

    confidence: float

    supporting_evidence: List[GrainEvidence] = Field(
        default_factory=list
    )

    explanation: str

    alternative_grains: List[AlternativeGrain] = Field(
        default_factory=list
    )

    all_scores: List[GrainScore] = Field(
        default_factory=list
    )


# ── Semantic understanding (developer debug) ──────────────────

class SemanticUnderstandingRequest(BaseModel):

    columns: List[DatasetColumnInput]

    column_stats: List[ColumnStatInput] = Field(
        default_factory=list
    )


class DatasetArchetypeSchema(BaseModel):

    primary: Optional[str] = None

    confidence: float = 0.0

    alternatives: List[AlternativeArchetype] = Field(
        default_factory=list
    )

    label: str = "Unknown"

    explanation: str = ""

    supporting_concepts: List[str] = Field(
        default_factory=list
    )


class SemanticModelSchema(BaseModel):

    concepts: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    dimensions: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    measures: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    entities: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    dates: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    identifiers: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    statuses: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    geography: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    grain: DetermineGrainResponse


class SemanticUnderstandingView(BaseModel):

    detected_concepts: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    source_columns: List[str] = Field(
        default_factory=list
    )

    inferred_grain: DetermineGrainResponse

    detected_measures: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    detected_dimensions: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    detected_dates: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    detected_entities: List[BusinessConceptSchema] = Field(
        default_factory=list
    )

    detected_capabilities: List[
        AnalyticalCapabilitySchema
    ] = Field(
        default_factory=list
    )

    archetype_classification: DatasetArchetypeSchema


class SemanticUnderstandingResponse(BaseModel):

    semantic_model: SemanticModelSchema

    capabilities: List[AnalyticalCapabilitySchema] = Field(
        default_factory=list
    )

    dataset_archetype: DatasetArchetypeSchema

    semantic_understanding: SemanticUnderstandingView
