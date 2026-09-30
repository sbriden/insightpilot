from fastapi import APIRouter, HTTPException

from app.applications.repository import (
    create_application,
    delete_application,
    get_application,
    list_applications,
    update_application,
)

router = APIRouter(
    prefix="/api/applications",
    tags=["analytical-applications"],
)


@router.get("")
def get_applications():
    try:
        return list_applications()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("")
def post_application(payload: dict):
    try:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(
                status_code=400,
                detail="Application name is required.",
            )
        analyses = payload.get("analyses") or []
        if not isinstance(analyses, list) or not analyses:
            raise HTTPException(
                status_code=400,
                detail="Select at least one analysis.",
            )
        return create_application(payload)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/{application_id}")
def get_one(application_id: str):
    app = get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Not found")
    return app


@router.put("/{application_id}")
def put_application(application_id: str, payload: dict):
    try:
        updated = update_application(application_id, payload)
        if not updated:
            raise HTTPException(status_code=404, detail="Not found")
        return updated
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.delete("/{application_id}")
def remove_application(application_id: str):
    try:
        ok = delete_application(application_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
