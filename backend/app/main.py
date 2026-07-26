from fastapi import FastAPI

from .database import engine
from .database import Base
from . import models


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="InsightPilot API",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "application": "InsightPilot",
        "status": "running",
        "database": "connected"
    }