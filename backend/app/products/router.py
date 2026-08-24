from fastapi import APIRouter, HTTPException

from .repository import (
    archive_data_product,
    create_data_product,
    get_data_product,
    get_data_products,
    list_data_products,
    update_data_product,    
)

from app.products.schemas import (
    DataCoverageRequest,
)

from app.products.coverage import (
    calculate_data_coverage,
)

from app.products.catalog import (
    DATA_PRODUCT_CATALOG,
)


router = APIRouter(
    prefix="/api/data-products",
    tags=["data-products"],
)

@router.get("")
def list_products():
    return get_data_products()


@router.post("/")
def create_product(
    product: dict,
):
    try:

        return create_data_product(
            product
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@router.get("/")
def get_products():

    try:

        return list_data_products()

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@router.get("/{product_id}")
def get_product(
    product_id: str,
):

    product = get_data_product(
        product_id
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Data product not found",
        )

    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: str,
):

    product = archive_data_product(
        product_id
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Data product not found",
        )

    return product


@router.put("/{product_id}")
def update_product(
    product_id: str,
    product: dict,
) -> dict:
    """
    Update an existing persisted data product.
    """

    existing = get_data_product(
        product_id
    )

    if existing is None:
        raise HTTPException(
            status_code=404,
            detail="Data product not found",
        )

    return update_data_product(
        product_id,
        product,
    )


@router.post(
    "/coverage"
)
def calculate_coverage(
    request: DataCoverageRequest,
):

    product = next(
        (
            product
            for product in DATA_PRODUCT_CATALOG
            if product.get("id")
            == request.product_id
        ),
        None,
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail=(
                "Data product not found"
            ),
        )

    mappings = [
        mapping.model_dump()
        for mapping in request.mappings
    ]

    result = calculate_data_coverage(
        product=product,
        uploaded_fields=
            request.uploaded_fields,
        mappings=mappings,
    )

    return result