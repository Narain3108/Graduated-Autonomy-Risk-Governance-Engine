"""Data models for AutonomyGuard DynamoDB persistence layer.

Three core models:
- ``AuditLog``     — Immutable evaluation records with full score breakdowns.
- ``ApprovalTicket`` — Human-in-the-loop approval queue entries.
- ``ActionBias``  — EWMA-learned per-action-type risk bias multipliers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _generate_eval_id() -> str:
    return f"eval_{uuid.uuid4().hex[:12]}"


def _generate_appr_id() -> str:
    return f"appr_{uuid.uuid4().hex[:12]}"


# ── Audit Log ────────────────────────────────────────────────────────────


class AuditLog(BaseModel):
    """Immutable record of every evaluation performed by the governance engine."""

    id: str = Field(default_factory=_generate_eval_id)
    trace_id: str
    agent_id: str
    action_type: str
    tool_name: str

    # ── Raw dimension inputs ─────────────────────────────────────────
    reversibility_score: float = 0.0
    data_scope_count: int = 1
    regulatory_category: str = "PUBLIC"
    llm_confidence: Optional[float] = None

    # ── Computed results ─────────────────────────────────────────────
    composite_score: float
    bias_multiplier_used: float = 1.0
    execution_tier: str  # AUTONOMOUS | CONFIRM | FULL_REVIEW
    decision_reason: str = ""

    # ── Lifecycle ────────────────────────────────────────────────────
    status: str = "EXECUTED"  # EXECUTED | PENDING_APPROVAL | APPROVED | REJECTED | MODIFIED
    created_at: datetime = Field(default_factory=_utcnow)


# ── Approval Ticket ──────────────────────────────────────────────────────


class ApprovalTicket(BaseModel):
    """Tracks human-in-the-loop approval lifecycle for CONFIRM/FULL_REVIEW actions."""

    id: str = Field(default_factory=_generate_appr_id)
    evaluation_id: str
    agent_id: str
    action_type: str
    tool_name: str

    # ── Original payload snapshot ────────────────────────────────────
    payload_summary: str = "{}"

    # ── Approval lifecycle ───────────────────────────────────────────
    status: str = "PENDING"  # PENDING | APPROVED | REJECTED | MODIFIED
    assigned_reviewer: Optional[str] = None
    reviewer_notes: Optional[str] = None
    modified_payload: Optional[str] = None

    # ── Timestamps ───────────────────────────────────────────────────
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


# ── Action Bias (Adaptive Multiplier) ────────────────────────────────────


class ActionBias(BaseModel):
    """Per-action-type EWMA bias multiplier learned from human feedback."""

    action_type: str
    multiplier: float = 1.0
    sample_count: int = 0
    updated_at: datetime = Field(default_factory=_utcnow)
