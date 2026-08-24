from typing import List, Optional

from .definitions import DATASET_TYPES
from .models import DatasetTypeDefinition


def get_dataset_types() -> List[DatasetTypeDefinition]:
    return DATASET_TYPES


def get_dataset_type(
    dataset_type_id: str,
) -> Optional[DatasetTypeDefinition]:

    for dataset_type in DATASET_TYPES:

        if dataset_type.id == dataset_type_id:
            return dataset_type

    return None


def get_products_for_dataset_type(
    dataset_type_id: str,
) -> List[str]:

    dataset_type = get_dataset_type(
        dataset_type_id
    )

    if dataset_type is None:
        return []

    return dataset_type.product_ids