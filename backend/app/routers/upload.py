from fastapi import APIRouter, File, HTTPException, UploadFile

import pandas as pd

from ..services.profiler import profile_dataframe
from ..services.metrics import generate_metrics
from ..services.classifier import classify_dataset

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

        # Generate analysis
        profile = profile_dataframe(df)
        metrics = generate_metrics(df)
        classification = classify_dataset(df.columns.tolist())

        # Return unified response
        return {
            "profile": profile,
            "metrics": metrics,
            "classification": classification,
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to process uploaded file: {str(e)}",
        )