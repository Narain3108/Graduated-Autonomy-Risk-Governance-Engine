"""Clean Data Access Layer — Repository classes for AutonomyGuard persistence.

Each repository encapsulates all SQL queries for its respective model,
keeping the service layer free of ORM details.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ActionBias, ApprovalTicket, AuditLog


# ── Audit Repository ────────────────────────────────────────────────────


class AuditRepository:
    """Handles creation and paginated querying of immutable evaluation audit logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, audit_log: AuditLog) -> AuditLog:
        """Persist a new audit log record."""
        self._session.add(audit_log)
        await self._session.flush()
        return audit_log

    async def get_by_id(self, eval_id: str) -> AuditLog | None:
        """Retrieve a single audit log by evaluation ID."""
        result = await self._session.execute(
            select(AuditLog).where(AuditLog.id == eval_id)
        )
        return result.scalar_one_or_none()

    async def list_logs(
        self,
        page: int = 1,
        page_size: int | None = None,
        agent_id: str | None = None,
        action_type: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Return a paginated list of audit logs with total count.

        Returns:
            Tuple of (logs, total_count).
        """
        page_size = min(page_size or settings.default_page_size, settings.max_page_size)
        offset = (max(1, page) - 1) * page_size

        # Build base query
        query = select(AuditLog)
        count_query = select(func.count()).select_from(AuditLog)

        if agent_id:
            query = query.where(AuditLog.agent_id == agent_id)
            count_query = count_query.where(AuditLog.agent_id == agent_id)
        if action_type:
            query = query.where(AuditLog.action_type == action_type)
            count_query = count_query.where(AuditLog.action_type == action_type)

        query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        logs_result = await self._session.execute(query)
        logs = list(logs_result.scalars().all())

        return logs, total

    async def update_status(self, eval_id: str, status: str) -> AuditLog | None:
        """Update the status field of an existing audit log."""
        audit_log = await self.get_by_id(eval_id)
        if audit_log:
            audit_log.status = status
            await self._session.flush()
        return audit_log


# ── Approval Repository ─────────────────────────────────────────────────


class ApprovalRepository:
    """Handles creation, retrieval, and status transitions for approval tickets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, ticket: ApprovalTicket) -> ApprovalTicket:
        """Persist a new approval ticket."""
        self._session.add(ticket)
        await self._session.flush()
        return ticket

    async def get_by_id(self, approval_id: str) -> ApprovalTicket | None:
        """Retrieve a single approval ticket by its ID."""
        result = await self._session.execute(
            select(ApprovalTicket).where(ApprovalTicket.id == approval_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        approval_id: str,
        *,
        status: str,
        reviewer_notes: str | None = None,
        modified_payload: str | None = None,
    ) -> ApprovalTicket | None:
        """Transition an approval ticket to a new status."""
        ticket = await self.get_by_id(approval_id)
        if ticket is None:
            return None

        ticket.status = status
        ticket.updated_at = datetime.now(timezone.utc)
        if reviewer_notes is not None:
            ticket.reviewer_notes = reviewer_notes
        if modified_payload is not None:
            ticket.modified_payload = modified_payload

        await self._session.flush()
        return ticket

    async def list_pending(
        self,
        page: int = 1,
        page_size: int | None = None,
    ) -> tuple[list[ApprovalTicket], int]:
        """Return paginated list of pending approval tickets."""
        page_size = min(page_size or settings.default_page_size, settings.max_page_size)
        offset = (max(1, page) - 1) * page_size

        count_query = (
            select(func.count())
            .select_from(ApprovalTicket)
            .where(ApprovalTicket.status == "PENDING")
        )
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        query = (
            select(ApprovalTicket)
            .where(ApprovalTicket.status == "PENDING")
            .order_by(ApprovalTicket.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self._session.execute(query)
        tickets = list(result.scalars().all())

        return tickets, total


# ── Action Bias Repository ──────────────────────────────────────────────


class ActionBiasRepository:
    """Manages EWMA-learned per-action-type risk bias multipliers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_multiplier(self, action_type: str) -> float:
        """Return the current bias multiplier for an action type.

        Returns the configured default if no record exists yet.
        """
        result = await self._session.execute(
            select(ActionBias).where(ActionBias.action_type == action_type)
        )
        bias = result.scalar_one_or_none()
        return bias.multiplier if bias else settings.default_bias_multiplier

    async def get_or_create(self, action_type: str) -> ActionBias:
        """Return existing bias record or create a new one with defaults."""
        result = await self._session.execute(
            select(ActionBias).where(ActionBias.action_type == action_type)
        )
        bias = result.scalar_one_or_none()
        if bias is None:
            bias = ActionBias(
                action_type=action_type,
                multiplier=settings.default_bias_multiplier,
                sample_count=0,
            )
            self._session.add(bias)
            await self._session.flush()
        return bias

    async def update_multiplier(
        self,
        action_type: str,
        new_multiplier: float,
    ) -> ActionBias:
        """Set a new multiplier value and increment sample count."""
        bias = await self.get_or_create(action_type)

        # Clamp multiplier within configured bounds.
        bias.multiplier = max(
            settings.min_bias_multiplier,
            min(settings.max_bias_multiplier, new_multiplier),
        )
        bias.sample_count += 1
        bias.updated_at = datetime.now(timezone.utc)

        await self._session.flush()
        return bias
