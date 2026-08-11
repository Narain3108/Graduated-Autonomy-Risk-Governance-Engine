"""FastAPI dependency injection providers.

Centralises all ``Depends()`` callables so that API route modules remain
thin and focused on HTTP concerns only.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import ActionBiasRepository, ApprovalRepository, AuditRepository
from app.db.session import get_async_session
from app.services.approval_service import ApprovalService
from app.services.evaluation_service import EvaluationService


async def get_db(
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped async database session."""
    async for session in get_async_session():
        yield session


# ── Repository Providers ─────────────────────────────────────────────────


async def get_audit_repo(
    session: AsyncSession = __import__("fastapi").Depends(get_db),
) -> AuditRepository:
    """Provide an ``AuditRepository`` bound to the current request session."""
    return AuditRepository(session)


async def get_approval_repo(
    session: AsyncSession = __import__("fastapi").Depends(get_db),
) -> ApprovalRepository:
    """Provide an ``ApprovalRepository`` bound to the current request session."""
    return ApprovalRepository(session)


async def get_bias_repo(
    session: AsyncSession = __import__("fastapi").Depends(get_db),
) -> ActionBiasRepository:
    """Provide an ``ActionBiasRepository`` bound to the current request session."""
    return ActionBiasRepository(session)


# ── Service Providers ────────────────────────────────────────────────────


async def get_evaluation_service(
    audit_repo: AuditRepository = __import__("fastapi").Depends(get_audit_repo),
    approval_repo: ApprovalRepository = __import__("fastapi").Depends(get_approval_repo),
    bias_repo: ActionBiasRepository = __import__("fastapi").Depends(get_bias_repo),
) -> EvaluationService:
    """Provide a fully-wired ``EvaluationService``."""
    return EvaluationService(audit_repo, approval_repo, bias_repo)


async def get_approval_service(
    approval_repo: ApprovalRepository = __import__("fastapi").Depends(get_approval_repo),
    audit_repo: AuditRepository = __import__("fastapi").Depends(get_audit_repo),
    bias_repo: ActionBiasRepository = __import__("fastapi").Depends(get_bias_repo),
) -> ApprovalService:
    """Provide a fully-wired ``ApprovalService``."""
    return ApprovalService(approval_repo, audit_repo, bias_repo)
