from typing import List, Optional
from pydantic import BaseModel


class FieldMappingRequest(BaseModel):

    requiredField: str

    uploadedField: Optional[str] = None

    matchType: Optional[str] = None

    confidence: Optional[float] = None


class DataCoverageRequest(BaseModel):

    product_id: str

    uploaded_fields: List[str]

    mappings: List[FieldMappingRequest]