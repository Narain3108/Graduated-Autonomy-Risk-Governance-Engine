"""Approval endpoints — POST & GET /v1/approvals.

- POST /v1/approvals/{approval_id}/action — Resolve a pending approval ticket.
- GET  /v1/approvals/pending               — List pending approval tickets (paginated).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from autonomy_guard.api.dependencies import get_approval_service
from autonomy_guard.schemas.approval import (
    ApprovalActionRequest,
    ApprovalActionResponse,
    ApprovalTicketResponse,
    PaginatedApprovals,
)
from autonomy_guard.services.approval_service import (
    ApprovalAlreadyResolvedError,
    ApprovalNotFoundError,
    ApprovalService,
)

router = APIRouter(prefix="/v1/approvals", tags=["Approvals"])


@router.post(
    "/{approval_id}/action",
    response_model=ApprovalActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve an approval ticket",
    description=(
        "Submit a human reviewer's decision (APPROVE / REJECT / MODIFY) "
        "for a pending approval ticket. Triggers adaptive EWMA recalibration."
    ),
)
async def resolve_approval(
    approval_id: str,
    request: ApprovalActionRequest,
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalActionResponse:
    """Process a reviewer's decision and trigger adaptive calibration."""
    try:
        return await service.resolve(approval_id, request)
    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ApprovalAlreadyResolvedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/pending",
    response_model=PaginatedApprovals,
    status_code=status.HTTP_200_OK,
    summary="List pending approval tickets",
    description="Paginated list of approval tickets awaiting human review.",
)
async def list_pending_approvals(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page."),
    service: ApprovalService = Depends(get_approval_service),
) -> PaginatedApprovals:
    """Return paginated pending approval tickets."""
    tickets, total = await service._approval_repo.list_pending(
        page=page, page_size=page_size
    )
    return PaginatedApprovals(
        items=[
            ApprovalTicketResponse(
                id=t.id,
                evaluation_id=t.evaluation_id,
                agent_id=t.agent_id,
                action_type=t.action_type,
                tool_name=t.tool_name,
                payload_summary=t.payload_summary,
                status=t.status,
                reviewer_notes=t.reviewer_notes,
                modified_payload=t.modified_payload,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tickets
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
