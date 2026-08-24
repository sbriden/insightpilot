from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models

from .routers import health
from .routers import upload

from app.products.router import (
    router as data_products_router,
)

from app.datasets.router import router as dataset_types_router

from dotenv import load_dotenv

load_dotenv()


# Create database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="InsightPilot API",
    version="0.1.0",
    description="AI-powered business intelligence platform"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "application": "InsightPilot",
        "status": "running",
        "database": "connected",
        "version": "0.1.0"
    }


# Register API routers
app.include_router(
    health.router,
    prefix="/api/health",
    tags=["Health"]
)

app.include_router(
    upload.router,
    prefix="/api/upload",
    tags=["Upload"]
)

app.include_router(
    data_products_router
)

app.include_router(
    dataset_types_router
)
