"""GET /v1/audit/logs — Paginated audit log endpoint.

Returns past governance evaluation records with full score breakdowns,
filterable by agent_id and action_type.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from autonomy_guard.api.dependencies import get_audit_repo
from autonomy_guard.db.repository import AuditRepository
from autonomy_guard.schemas.evaluation import ScoreBreakdownResponse

router = APIRouter(prefix="/v1/audit", tags=["Audit"])


# ── Response DTOs (audit-specific) ───────────────────────────────────────


class AuditLogEntry(BaseModel):
    """Single audit log entry for API responses."""

    evaluation_id: str
    trace_id: str
    agent_id: str
    action_type: str
    tool_name: str
    reversibility_score: float
    data_scope_count: int
    regulatory_category: str
    llm_confidence: float | None
    composite_score: float
    bias_multiplier_used: float
    execution_tier: str
    decision_reason: str
    status: str
    created_at: datetime


class PaginatedAuditLogs(BaseModel):
    """Paginated wrapper for audit log entries."""

    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


# ── Endpoint ─────────────────────────────────────────────────────────────


@router.get(
    "/logs",
    response_model=PaginatedAuditLogs,
    status_code=status.HTTP_200_OK,
    summary="Retrieve paginated audit logs",
    description=(
        "Returns historical governance evaluation records with score breakdowns. "
        "Supports optional filtering by agent_id and action_type."
    ),
)
async def list_audit_logs(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page."),
    agent_id: str | None = Query(default=None, description="Filter by agent ID."),
    action_type: str | None = Query(default=None, description="Filter by action type."),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> PaginatedAuditLogs:
    """Return paginated and optionally filtered audit logs."""
    logs, total = await audit_repo.list_logs(
        page=page,
        page_size=page_size,
        agent_id=agent_id,
        action_type=action_type,
    )
    return PaginatedAuditLogs(
        items=[
            AuditLogEntry(
                evaluation_id=log.id,
                trace_id=log.trace_id,
                agent_id=log.agent_id,
                action_type=log.action_type,
                tool_name=log.tool_name,
                reversibility_score=log.reversibility_score,
                data_scope_count=log.data_scope_count,
                regulatory_category=log.regulatory_category,
                llm_confidence=log.llm_confidence,
                composite_score=log.composite_score,
                bias_multiplier_used=log.bias_multiplier_used,
                execution_tier=log.execution_tier,
                decision_reason=log.decision_reason,
                status=log.status,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
