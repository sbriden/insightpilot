from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models

from .routers import health
from .routers import upload

from app.sources.router import (
    router as sources_router,
)

from app.products.router import (
    router as data_products_router,
)

from app.datasets.router import router as dataset_types_router

from dotenv import load_dotenv

from app.products.schema import (
    ensure_data_products_schema,
)

from app.datasets.schema import (
    ensure_datasets_schema,
)

from app.canonical.schema import (
    ensure_canonical_schema,
)

from app.applications.schema import (
    ensure_applications_schema,
)

from app.applications.router import (
    router as applications_router,
)

load_dotenv()


# Create database tables
Base.metadata.create_all(bind=engine)
ensure_data_products_schema()
ensure_datasets_schema()
ensure_canonical_schema()
ensure_applications_schema()


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

app.include_router(
    sources_router,
    prefix="/api/sources",
    tags=["Sources"],
)

app.include_router(applications_router)
