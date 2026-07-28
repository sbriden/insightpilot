from fastapi import APIRouter, File, UploadFile

import pandas as pd

from ..services.profiler import profile_dataframe

router = APIRouter()


@router.post("/")
async def upload(file: UploadFile = File(...)):

    df = pd.read_csv(file.file)

    return profile_dataframe(df)