import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .database import Base, engine
from . import models

from .routers import health
from .routers import upload
from .routers import admin_auth

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

from app.applications.public_router import (
    router as public_applications_router,
)

from app.auth import (
    ADMIN_TOKEN_HEADER,
    admin_auth_enabled,
    extract_admin_token,
    is_admin_only_path,
    is_public_path,
    verify_admin_token,
)

load_dotenv()


# Create database tables
Base.metadata.create_all(bind=engine)
ensure_data_products_schema()
ensure_datasets_schema()
ensure_canonical_schema()
ensure_applications_schema()


def _cors_origins() -> list[str]:
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    if not raw:
        return defaults
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    for origin in defaults:
        if origin not in origins:
            origins.append(origin)
    return origins


app = FastAPI(
    title="InsightPilot API",
    version="0.1.0",
    description="AI-powered business intelligence platform"
)

class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not admin_auth_enabled():
            return await call_next(request)

        path = request.url.path
        method = request.method
        if is_public_path(path, method):
            return await call_next(request)
        if not is_admin_only_path(path, method):
            return await call_next(request)

        token = extract_admin_token(
            request,
            request.headers.get(ADMIN_TOKEN_HEADER),
        )
        if not verify_admin_token(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Admin authentication required."},
            )
        return await call_next(request)


# Auth is inner; CORS is outermost so 401s still get ACAO headers.
app.add_middleware(AdminAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", ADMIN_TOKEN_HEADER],
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
app.include_router(public_applications_router)
app.include_router(admin_auth.router)
