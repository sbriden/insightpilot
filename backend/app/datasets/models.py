from dataclasses import dataclass, field
from typing import List


@dataclass
class DatasetTypeDefinition:
    id: str
    name: str
    description: str

    keywords: List[str] = field(
        default_factory=list
    )

    example_fields: List[str] = field(
        default_factory=list
    )

    product_ids: List[str] = field(
        default_factory=list
    )