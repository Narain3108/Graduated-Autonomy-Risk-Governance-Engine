"""Pydantic v2 schemas for the ``/v1/evaluate`` endpoint.

Defines strict request validation and structured response DTOs including
the full score breakdown, execution tier, and optional approval ticket reference.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────


class RegulatoryCategory(StrEnum):
    """Canonical regulatory classification for data touched by an action."""

    PII = "PII"
    HIPAA = "HIPAA"
    FINANCIAL = "FINANCIAL"
    AUTH = "AUTH"
    INTERNAL = "INTERNAL"
    PUBLIC = "PUBLIC"
    NON_SENSITIVE = "NON_SENSITIVE"


# ── Request ──────────────────────────────────────────────────────────────


class EvaluationRequest(BaseModel):
    """Payload submitted by an AI agent (or SDK) for governance evaluation."""

    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier of the calling agent.",
    )
    action_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Canonical action type (e.g., bulk_delete, record_update, query).",
    )
    tool_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Name of the tool/function to be executed.",
    )
    reversibility: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0.0 = fully reversible / read-only; 1.0 = irreversible.",
    )
    records_affected: int = Field(
        default=1,
        ge=0,
        description="Estimated number of records the action will affect.",
    )
    regulatory_category: RegulatoryCategory = Field(
        default=RegulatoryCategory.PUBLIC,
        description="Regulatory classification of the data involved.",
    )
    llm_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Agent's self-reported confidence [0.0, 1.0]. Defaults to 0.50 if omitted.",
    )
    payload_summary: str = Field(
        default="{}",
        max_length=4096,
        description="JSON string summarising the action payload for audit purposes.",
    )

    model_config = {"str_strip_whitespace": True}


# ── Response ─────────────────────────────────────────────────────────────


class ScoreBreakdownResponse(BaseModel):
    """Individual dimension scores plus the composite result."""

    reversibility: float
    data_scope: float
    regulatory: float
    confidence_risk: float
    raw_score: float
    bias_multiplier: float
    final_score: float


class EvaluationResponse(BaseModel):
    """Full governance evaluation result returned to the caller."""

    evaluation_id: str = Field(description="Unique evaluation trace ID (eval_xxxx).")
    execution_tier: str = Field(description="AUTONOMOUS | CONFIRM | FULL_REVIEW")
    decision_reason: str = Field(description="Human-readable routing explanation.")
    score_breakdown: ScoreBreakdownResponse
    status: str = Field(
        description="Current lifecycle status (EXECUTED | PENDING_APPROVAL).",
    )
    approval_id: str | None = Field(
        default=None,
        description="Approval ticket ID if action requires human review.",
    )
    created_at: datetime
