from fastapi import APIRouter, HTTPException

from .service import (
    get_dataset_types,
)

from .schemas import (
    DatasetTypeRequirementsResponse,
    SaveFieldMappingsRequest,
    SavedFieldMappingsResponse,
)

from .mapping_memory import (
    get_field_mappings as repository_get_field_mappings,
    save_field_mappings as repository_save_field_mappings,
)

from app.products.catalog import (
    get_products_for_dataset_type as catalog_products_for_dataset_type,
    serialize_product_definition,
    DATA_PRODUCT_CATALOG,
)

from pydantic import BaseModel

from app.datasets.mapping import (
    suggest_field_mapping,
)

router = APIRouter(
    prefix="/api/datasets",
    tags=["datasets"],
)

@router.get("/types")
def get_types():
    return get_dataset_types()


@router.get(
    "/{dataset_type_id}/data-products",
    response_model=DatasetTypeRequirementsResponse,
)
def get_dataset_type_data_products(
    dataset_type_id: str,
):

    products = catalog_products_for_dataset_type(
        dataset_type_id
    )

    if not products:

        raise HTTPException(
            status_code=404,
            detail=(
                f"No data products found for "
                f"dataset type '{dataset_type_id}'"
            ),
        )

    return {
        "dataset_type": dataset_type_id,

        "data_products": [
            serialize_product_definition(
                product
            )
            for product in products
        ],
    }


class FieldMappingRequest(BaseModel):

    dataset_type: str

    product_id: str

    uploaded_fields: list[str]


@router.post("/field-mapping")
def map_fields(
    request: FieldMappingRequest,
):

    product = next(
        (
            product
            for product in DATA_PRODUCT_CATALOG
            if product.id == request.product_id
        ),
        None,
    )

    if product is None:

        raise HTTPException(
            status_code=404,
            detail="Data product not found",
        )

    result = suggest_field_mapping(

        uploaded_fields=
            request.uploaded_fields,

        required_fields=
            product.required_fields,

        optional_fields=
            product.optional_fields,
    )

    return {
        "datasetType":
            request.dataset_type,

        "productId":
            request.product_id,

        **result,
    }


@router.get(
    "/{dataset_type_id}/field-mappings",
    response_model=SavedFieldMappingsResponse,
)
def get_saved_field_mappings(
    dataset_type_id: str,
):

    record = repository_get_field_mappings(
        dataset_type_id
    )

    if record is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "No saved field mappings found "
                f"for dataset type '{dataset_type_id}'."
            ),
        )

    return {
        "dataset_type_id": (
            record["dataset_type_id"]
        ),

        "uploaded_columns": (
            record.get("uploaded_columns")
            or []
        ),

        "mappings": (
            record.get("mappings")
            or []
        ),

        "updated_at": (
            record.get("updated_at")
        ),
    }


@router.put(
    "/{dataset_type_id}/field-mappings",
    response_model=SavedFieldMappingsResponse,
)
def save_saved_field_mappings(
    dataset_type_id: str,
    request: SaveFieldMappingsRequest,
):

    record = repository_save_field_mappings(
        dataset_type_id,

        uploaded_columns=(
            request.uploaded_columns
        ),

        mappings=[
            mapping.model_dump()
            for mapping
            in request.mappings
        ],
    )

    return {
        "dataset_type_id": (
            record["dataset_type_id"]
        ),

        "uploaded_columns": (
            record.get("uploaded_columns")
            or []
        ),

        "mappings": (
            record.get("mappings")
            or []
        ),

        "updated_at": (
            record.get("updated_at")
        ),
    }