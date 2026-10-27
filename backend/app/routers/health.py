from fastapi import APIRouter

router = APIRouter()


@router.get("")
@router.get("/")
def health():
    return {
        "status": "healthy",
        "application": "InsightPilot"
    }