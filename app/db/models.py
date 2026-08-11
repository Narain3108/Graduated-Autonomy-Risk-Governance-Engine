"""SQLAlchemy ORM models for AutonomyGuard persistence layer.

Three tables:
- ``audit_logs``     — Immutable evaluation records with full score breakdowns.
- ``approval_tickets`` — Human-in-the-loop approval queue entries.
- ``action_biases``  — EWMA-learned per-action-type risk bias multipliers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _generate_eval_id() -> str:
    return f"eval_{uuid.uuid4().hex[:12]}"


def _generate_appr_id() -> str:
    return f"appr_{uuid.uuid4().hex[:12]}"


# ── Declarative Base ─────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Shared declarative base for all AutonomyGuard models."""


# ── Audit Log ────────────────────────────────────────────────────────────


class AuditLog(Base):
    """Immutable record of every evaluation performed by the governance engine."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_generate_eval_id
    )
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    tool_name: Mapped[str] = mapped_column(String(128))

    # ── Raw dimension inputs ─────────────────────────────────────────
    reversibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    data_scope_count: Mapped[int] = mapped_column(Integer, default=1)
    regulatory_category: Mapped[str] = mapped_column(String(32), default="PUBLIC")
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Computed results ─────────────────────────────────────────────
    composite_score: Mapped[float] = mapped_column(Float)
    bias_multiplier_used: Mapped[float] = mapped_column(Float, default=1.0)
    execution_tier: Mapped[str] = mapped_column(String(16))  # AUTONOMOUS | CONFIRM | FULL_REVIEW
    decision_reason: Mapped[str] = mapped_column(Text, default="")

    # ── Lifecycle ────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(32), default="EXECUTED", index=True
    )  # EXECUTED | PENDING_APPROVAL | APPROVED | REJECTED | MODIFIED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id!r} tier={self.execution_tier!r} "
            f"score={self.composite_score:.3f}>"
        )


# ── Approval Ticket ──────────────────────────────────────────────────────


class ApprovalTicket(Base):
    """Tracks human-in-the-loop approval lifecycle for CONFIRM/FULL_REVIEW actions."""

    __tablename__ = "approval_tickets"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_generate_appr_id
    )
    evaluation_id: Mapped[str] = mapped_column(
        String(64), index=True
    )  # FK-like reference to AuditLog.id
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    action_type: Mapped[str] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(128))

    # ── Original payload snapshot ────────────────────────────────────
    payload_summary: Mapped[str] = mapped_column(Text, default="{}")

    # ── Approval lifecycle ───────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16), default="PENDING", index=True
    )  # PENDING | APPROVED | REJECTED | MODIFIED
    assigned_reviewer: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalTicket id={self.id!r} eval={self.evaluation_id!r} "
            f"status={self.status!r}>"
        )


# ── Action Bias (Adaptive Multiplier) ────────────────────────────────────


class ActionBias(Base):
    """Per-action-type EWMA bias multiplier learned from human feedback."""

    __tablename__ = "action_biases"

    action_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<ActionBias type={self.action_type!r} "
            f"multiplier={self.multiplier:.4f} samples={self.sample_count}>"
        )
