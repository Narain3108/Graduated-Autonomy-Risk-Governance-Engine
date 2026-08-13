"""Evaluation Service — Orchestrates the complete governance evaluation workflow.

Responsibilities:
  1. Fetch the current EWMA bias multiplier for the action type.
  2. Compute composite risk score via the scoring engine.
  3. Route to an execution tier via the decision router.
  4. Persist an immutable audit log record.
  5. If CONFIRM or FULL_REVIEW, create an approval ticket.
  6. Return the structured evaluation response.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from autonomy_guard.core.router import ExecutionTier, build_decision_reason, determine_execution_tier
from autonomy_guard.core.scoring import compute_composite_score
from autonomy_guard.db.models import ApprovalTicket, AuditLog
from autonomy_guard.db.repository import ActionBiasRepository, ApprovalRepository, AuditRepository
from autonomy_guard.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    ScoreBreakdownResponse,
)

logger = structlog.get_logger(__name__)


class EvaluationService:
    """High-level service coordinating risk evaluation, routing, and persistence."""

    def __init__(
        self,
        audit_repo: AuditRepository,
        approval_repo: ApprovalRepository,
        bias_repo: ActionBiasRepository,
    ) -> None:
        self._audit_repo = audit_repo
        self._approval_repo = approval_repo
        self._bias_repo = bias_repo

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResponse:
        """Run the full governance evaluation pipeline.

        Args:
            request: Validated evaluation request from the API layer.

        Returns:
            Structured evaluation response with score breakdown, tier, and optional ticket.
        """
        trace_id = f"eval_{uuid.uuid4().hex[:12]}"
        log = logger.bind(trace_id=trace_id, agent_id=request.agent_id)

        # Step 1: Fetch adaptive bias multiplier
        multiplier = await self._bias_repo.get_multiplier(request.action_type)
        log.info(
            "bias_multiplier_fetched",
            action_type=request.action_type,
            multiplier=multiplier,
        )

        # Step 2: Compute composite risk score
        breakdown = compute_composite_score(
            reversibility=request.reversibility,
            records_affected=request.records_affected,
            regulatory_category=request.regulatory_category.value,
            llm_confidence=request.llm_confidence,
            bias_multiplier=multiplier,
        )
        log.info(
            "risk_score_computed",
            raw_score=breakdown.raw_score,
            final_score=breakdown.final_score,
        )

        # Step 3: Determine execution tier
        tier = determine_execution_tier(breakdown.final_score)
        reason = build_decision_reason(tier, breakdown.final_score)
        log.info("execution_tier_determined", tier=tier.value)

        # Step 4: Determine lifecycle status
        status = (
            "EXECUTED"
            if tier == ExecutionTier.AUTONOMOUS
            else "PENDING_APPROVAL"
        )

        # Step 5: Persist audit log
        audit_log = AuditLog(
            id=trace_id,
            trace_id=trace_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            tool_name=request.tool_name,
            reversibility_score=breakdown.reversibility,
            data_scope_count=request.records_affected,
            regulatory_category=request.regulatory_category.value,
            llm_confidence=request.llm_confidence,
            composite_score=breakdown.final_score,
            bias_multiplier_used=multiplier,
            execution_tier=tier.value,
            decision_reason=reason,
            status=status,
        )
        await self._audit_repo.create(audit_log)
        log.info("audit_log_persisted", evaluation_id=trace_id)

        # Step 6: Create approval ticket if needed
        approval_id: str | None = None
        if tier in (ExecutionTier.CONFIRM, ExecutionTier.FULL_REVIEW):
            ticket = ApprovalTicket(
                id=f"appr_{uuid.uuid4().hex[:12]}",
                evaluation_id=trace_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                tool_name=request.tool_name,
                payload_summary=request.payload_summary,
                status="PENDING",
            )
            await self._approval_repo.create(ticket)
            approval_id = ticket.id
            log.info("approval_ticket_created", approval_id=approval_id)

        # Step 7: Build and return response
        return EvaluationResponse(
            evaluation_id=trace_id,
            execution_tier=tier.value,
            decision_reason=reason,
            score_breakdown=ScoreBreakdownResponse(
                reversibility=breakdown.reversibility,
                data_scope=breakdown.data_scope,
                regulatory=breakdown.regulatory,
                confidence_risk=breakdown.confidence_risk,
                raw_score=breakdown.raw_score,
                bias_multiplier=breakdown.bias_multiplier,
                final_score=breakdown.final_score,
            ),
            status=status,
            approval_id=approval_id,
            created_at=audit_log.created_at or datetime.now(timezone.utc),
        )
