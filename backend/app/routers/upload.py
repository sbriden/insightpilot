import json
import traceback

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

import pandas as pd

from ..services.analysis import analyze_dataframe


router = APIRouter()


def parse_product_ids(
    product_ids: str,
) -> list[str]:
    """
    Parse the product_ids form field.

    The frontend sends product IDs as a JSON array:

        [
            "customer_intelligence",
            "revenue_intelligence"
        ]

    Returns a normalized list of non-empty strings.
    """

    try:

        parsed_product_ids = json.loads(
            product_ids
        )

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=400,
            detail="Invalid product IDs.",
        )

    if not isinstance(
        parsed_product_ids,
        list,
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Product IDs must be provided "
                "as a list."
            ),
        )

    normalized_product_ids = [
        str(product_id).strip()
        for product_id
        in parsed_product_ids
        if str(product_id).strip()
    ]

    if not normalized_product_ids:

        raise HTTPException(
            status_code=400,
            detail=(
                "At least one data product "
                "must be selected."
            ),
        )

    return normalized_product_ids


def parse_mappings(
    mappings: str,
) -> list:
    """
    Parse the mappings form field.

    The frontend sends field mappings as a JSON array.
    """

    try:

        parsed_mappings = json.loads(
            mappings
        )

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=400,
            detail="Invalid field mappings.",
        )

    if not isinstance(
        parsed_mappings,
        list,
    ):

        return []

    return parsed_mappings


@router.post("/")
async def upload(
    file: UploadFile = File(...),

    mappings: str = Form(
        default="[]"
    ),

    product_ids: str = Form(
        default="[]"
    ),
):

    try:

        # --------------------------------------------------
        # Parse selected product IDs
        # --------------------------------------------------

        selected_product_ids = (
            parse_product_ids(
                product_ids
            )
        )

        print(
            "Selected product IDs:",
            selected_product_ids,
        )


        # --------------------------------------------------
        # Read uploaded CSV
        # --------------------------------------------------

        try:

            df = pd.read_csv(
                file.file,
                encoding="utf-8",
            )

        except UnicodeDecodeError:

            file.file.seek(0)

            df = pd.read_csv(
                file.file,
                encoding="latin-1",
            )


        print(
            "Original columns:",
            df.columns.tolist(),
        )


        # --------------------------------------------------
        # Parse field mappings
        # --------------------------------------------------

        parsed_mappings = parse_mappings(
            mappings
        )

        print(
            "Received field mappings:",
            parsed_mappings,
        )


        # --------------------------------------------------
        # Run analysis
        # --------------------------------------------------
        #
        # Field mappings and selected product IDs are
        # passed into the analysis pipeline.
        #
        # The analysis service is responsible for:
        #
        #   1. Applying field mappings
        #   2. Running dataset analysis
        #   3. Building analysis dashboards
        #   4. Generating the executive brief
        #   5. Generating only the selected data products
        # --------------------------------------------------

        context = analyze_dataframe(
            df,
            field_mappings=parsed_mappings,
            selected_product_ids=(
                selected_product_ids
            ),
        )


        # --------------------------------------------------
        # Return API response
        # --------------------------------------------------

        return context.to_api_response()


    except HTTPException:

        raise


    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to process uploaded file: "
                f"{str(e)}"
            ),
        )