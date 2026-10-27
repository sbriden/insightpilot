from fastapi import APIRouter, HTTPException

from app.applications.repository import (
    get_published_by_domain,
    get_published_by_slug,
)

router = APIRouter(
    prefix="/api/public/applications",
    tags=["public-applications"],
)


@router.get("/by-slug/{slug}")
def public_by_slug(slug: str):
    try:
        app = get_published_by_slug(slug)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if not app:
        raise HTTPException(status_code=404, detail="Not found")
    return app


@router.get("/by-domain/{host}")
def public_by_domain(host: str):
    app = get_published_by_domain(host)
    if not app:
        raise HTTPException(status_code=404, detail="Not found")
    return app
