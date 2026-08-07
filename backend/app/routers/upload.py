from fastapi import APIRouter, File, HTTPException, UploadFile

import pandas as pd

from ..services.analysis import analyze_dataframe

router = APIRouter()


@router.post("/")
async def upload(file: UploadFile = File(...)):
    try:
        # Read uploaded CSV
        try:
            df = pd.read_csv(
                file.file,
                encoding="utf-8"
            )

        except UnicodeDecodeError:
            file.file.seek(0)

            df = pd.read_csv(
                file.file,
                encoding="latin-1"
            )

        context = analyze_dataframe(df)

        return context.to_api_response()

    except Exception as e:
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=400,
            detail=f"Unable to process uploaded file: {str(e)}",
        )