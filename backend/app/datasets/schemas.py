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
