"""POST /v1/evaluate — Governance evaluation endpoint.

Accepts an agent action payload, runs it through the risk scoring pipeline,
and returns the execution tier decision with a full score breakdown.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_evaluation_service
from app.schemas.evaluation import EvaluationRequest, EvaluationResponse
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/v1", tags=["Evaluation"])


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate an agent action for governance routing",
    description=(
        "Accepts tool metadata, records affected, reversibility, confidence, "
        "and regulatory category. Returns a risk score breakdown and execution "
        "tier (AUTONOMOUS / CONFIRM / FULL_REVIEW). Creates an approval ticket "
        "when human review is required."
    ),
)
async def evaluate_action(
    request: EvaluationRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationResponse:
    """Run the full governance evaluation pipeline for the submitted action."""
    return await service.evaluate(request)
