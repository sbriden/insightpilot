from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models

from .routers import health
from .routers import upload


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
        "http://localhost:3000"
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
