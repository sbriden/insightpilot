from fastapi import APIRouter, HTTPException

from .service import (
    get_dataset_types,
    get_dataset_type,
    get_products_for_dataset_type,
)

from .schemas import (
    DatasetTypeRequirementsResponse,
)

from app.products.catalog import (
    get_products_for_dataset_type,
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

    products = get_products_for_dataset_type(
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

            {
                "id": product.id,

                "name": product.name,

                "description":
                    product.description,

                "grain":
                    product.grain,

                "required_fields":
                    product.required_fields,

                "optional_fields":
                    product.optional_fields,

                "analyses":
                    product.analyses,

            }

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