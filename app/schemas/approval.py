"""Pydantic v2 schemas for the ``/v1/approvals`` endpoints.

Covers the human action request payload, the approval ticket response DTO,
and the paginated list wrapper.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────


class ApprovalAction(StrEnum):
    """Actions a human reviewer can take on an approval ticket."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


class TicketStatus(StrEnum):
    """Lifecycle states of an approval ticket."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


# ── Request ──────────────────────────────────────────────────────────────


class ApprovalActionRequest(BaseModel):
    """Payload submitted by a human reviewer to resolve an approval ticket."""

    action: ApprovalAction = Field(
        ...,
        description="The reviewer's decision: APPROVE, REJECT, or MODIFY.",
    )
    reviewer_notes: str | None = Field(
        default=None,
        max_length=2048,
        description="Optional notes from the reviewer.",
    )
    modified_payload: str | None = Field(
        default=None,
        max_length=4096,
        description="Modified action payload (required when action is MODIFY).",
    )

    model_config = {"str_strip_whitespace": True}


# ── Response ─────────────────────────────────────────────────────────────


class ApprovalTicketResponse(BaseModel):
    """Single approval ticket representation."""

    id: str
    evaluation_id: str
    agent_id: str
    action_type: str
    tool_name: str
    payload_summary: str
    status: str
    reviewer_notes: str | None = None
    modified_payload: str | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalActionResponse(BaseModel):
    """Result returned after a reviewer acts on an approval ticket."""

    approval_id: str
    evaluation_id: str
    new_status: str
    updated_multiplier: float = Field(
        description="The recalibrated bias multiplier for this action type.",
    )
    message: str


# ── Paginated Wrapper ────────────────────────────────────────────────────


class PaginatedApprovals(BaseModel):
    """Paginated list of approval tickets."""

    items: list[ApprovalTicketResponse]
    total: int
    page: int
    page_size: int
