from fastapi import APIRouter

from ..core.analysis_context import AnalysisContext
from ..schemas.executive_brief import (
    ExecutiveBriefRequest,
    ExecutiveBriefResponse,
)
from ..services.ai import generate_executive_brief

router = APIRouter()


@router.post(
    "/",
    response_model=ExecutiveBriefResponse,
)
async def executive_brief(
    request: ExecutiveBriefRequest,
):

    context = AnalysisContext(
        profile=request.profile,
        metrics=request.metrics,
        classification=request.classification,
        recommendations=request.recommendations,
        insights=request.insights,
    )

    brief = generate_executive_brief(context)

    return ExecutiveBriefResponse(
        **brief
    )