"""FastAPI dependency injection providers.

Centralises all ``Depends()`` callables so that API route modules remain
thin and focused on HTTP concerns only.
"""

from __future__ import annotations

import aioboto3
from collections.abc import AsyncGenerator
from typing import Any
from fastapi import Depends

from autonomy_guard.config import settings
from autonomy_guard.db.repository import ActionBiasRepository, ApprovalRepository, AuditRepository
from autonomy_guard.services.approval_service import ApprovalService
from autonomy_guard.services.evaluation_service import EvaluationService


async def get_boto3_session() -> AsyncGenerator[aioboto3.Session, None]:
    """Yield a shared aioboto3 session."""
    # aioboto3 Session is generally cheap to create, but we can reuse it
    yield aioboto3.Session()


async def get_dynamodb_resource(
    session: aioboto3.Session = Depends(get_boto3_session),
) -> AsyncGenerator[Any, None]:
    """Yield a DynamoDB resource client."""
    async with session.resource(
        "dynamodb", 
        endpoint_url=settings.dynamodb_endpoint
    ) as ddb:
        yield ddb


# ── Repository Providers ─────────────────────────────────────────────────


async def get_audit_repo(
    ddb=Depends(get_dynamodb_resource),
) -> AuditRepository:
    """Provide an ``AuditRepository`` bound to the current DynamoDB resource."""
    table = await ddb.Table(settings.table_audit_logs)
    return AuditRepository(table)


async def get_approval_repo(
    ddb=Depends(get_dynamodb_resource),
) -> ApprovalRepository:
    """Provide an ``ApprovalRepository`` bound to the current DynamoDB resource."""
    table = await ddb.Table(settings.table_approval_tickets)
    return ApprovalRepository(table)


async def get_bias_repo(
    ddb=Depends(get_dynamodb_resource),
) -> ActionBiasRepository:
    """Provide an ``ActionBiasRepository`` bound to the current DynamoDB resource."""
    table = await ddb.Table(settings.table_action_biases)
    return ActionBiasRepository(table)


# ── Service Providers ────────────────────────────────────────────────────


async def get_evaluation_service(
    audit_repo: AuditRepository = Depends(get_audit_repo),
    approval_repo: ApprovalRepository = Depends(get_approval_repo),
    bias_repo: ActionBiasRepository = Depends(get_bias_repo),
) -> EvaluationService:
    """Provide a fully-wired ``EvaluationService``."""
    return EvaluationService(audit_repo, approval_repo, bias_repo)


async def get_approval_service(
    approval_repo: ApprovalRepository = Depends(get_approval_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    bias_repo: ActionBiasRepository = Depends(get_bias_repo),
) -> ApprovalService:
    """Provide a fully-wired ``ApprovalService``."""
    return ApprovalService(approval_repo, audit_repo, bias_repo)
