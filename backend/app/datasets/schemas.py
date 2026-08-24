from typing import List

from pydantic import BaseModel


class DataProductRequirement(BaseModel):

    id: str

    name: str

    description: str

    grain: str

    required_fields: List[str]

    optional_fields: List[str]

    analyses: List[str]


class DatasetTypeRequirementsResponse(BaseModel):

    dataset_type: str

    data_products: List[
        DataProductRequirement
    ]