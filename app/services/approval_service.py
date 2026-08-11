"""Approval Service — Manages the human-in-the-loop approval workflow.

Responsibilities:
  1. Validate that the approval ticket exists and is in PENDING state.
  2. Transition the ticket to the new status (APPROVED / REJECTED / MODIFIED).
  3. Update the corresponding audit log status.
  4. Trigger adaptive calibration (EWMA multiplier recalculation).
  5. Return the structured approval action response.
"""

from __future__ import annotations

import structlog

from app.core.adaptive import ApprovalOutcome, compute_new_multiplier
from app.db.repository import ActionBiasRepository, ApprovalRepository, AuditRepository
from app.schemas.approval import (
    ApprovalAction,
    ApprovalActionRequest,
    ApprovalActionResponse,
)

logger = structlog.get_logger(__name__)

# Map API action enum to the adaptive outcome enum.
_ACTION_TO_OUTCOME: dict[ApprovalAction, ApprovalOutcome] = {
    ApprovalAction.APPROVE: ApprovalOutcome.APPROVE,
    ApprovalAction.REJECT: ApprovalOutcome.REJECT,
    ApprovalAction.MODIFY: ApprovalOutcome.MODIFY,
}

# Map API action to the approval ticket status string.
_ACTION_TO_STATUS: dict[ApprovalAction, str] = {
    ApprovalAction.APPROVE: "APPROVED",
    ApprovalAction.REJECT: "REJECTED",
    ApprovalAction.MODIFY: "MODIFIED",
}

# Map API action to the audit log status string.
_ACTION_TO_AUDIT_STATUS: dict[ApprovalAction, str] = {
    ApprovalAction.APPROVE: "APPROVED",
    ApprovalAction.REJECT: "REJECTED",
    ApprovalAction.MODIFY: "MODIFIED",
}


class ApprovalNotFoundError(Exception):
    """Raised when an approval ticket cannot be found."""


class ApprovalAlreadyResolvedError(Exception):
    """Raised when attempting to act on a non-PENDING ticket."""


class ApprovalService:
    """High-level service coordinating approval resolution and adaptive learning."""

    def __init__(
        self,
        approval_repo: ApprovalRepository,
        audit_repo: AuditRepository,
        bias_repo: ActionBiasRepository,
    ) -> None:
        self._approval_repo = approval_repo
        self._audit_repo = audit_repo
        self._bias_repo = bias_repo

    async def resolve(
        self,
        approval_id: str,
        request: ApprovalActionRequest,
    ) -> ApprovalActionResponse:
        """Process a human reviewer's decision on an approval ticket.

        Args:
            approval_id: The ticket ID to resolve.
            request: The reviewer's action payload.

        Returns:
            Structured response including the updated multiplier.

        Raises:
            ApprovalNotFoundError: If the ticket does not exist.
            ApprovalAlreadyResolvedError: If the ticket is not in PENDING state.
        """
        log = logger.bind(approval_id=approval_id)

        # Step 1: Fetch and validate ticket
        ticket = await self._approval_repo.get_by_id(approval_id)
        if ticket is None:
            log.warning("approval_not_found")
            raise ApprovalNotFoundError(f"Approval ticket '{approval_id}' not found.")

        if ticket.status != "PENDING":
            log.warning("approval_already_resolved", current_status=ticket.status)
            raise ApprovalAlreadyResolvedError(
                f"Ticket '{approval_id}' is already resolved with status '{ticket.status}'."
            )

        new_status = _ACTION_TO_STATUS[request.action]
        log.info("resolving_approval", action=request.action.value, new_status=new_status)

        # Step 2: Update the approval ticket
        await self._approval_repo.update(
            approval_id,
            status=new_status,
            reviewer_notes=request.reviewer_notes,
            modified_payload=(
                request.modified_payload
                if request.action == ApprovalAction.MODIFY
                else None
            ),
        )

        # Step 3: Update the audit log status
        audit_status = _ACTION_TO_AUDIT_STATUS[request.action]
        await self._audit_repo.update_status(ticket.evaluation_id, audit_status)
        log.info("audit_log_status_updated", evaluation_id=ticket.evaluation_id)

        # Step 4: Adaptive EWMA calibration
        outcome = _ACTION_TO_OUTCOME[request.action]
        current_bias = await self._bias_repo.get_or_create(ticket.action_type)
        new_multiplier = compute_new_multiplier(current_bias.multiplier, outcome)
        updated_bias = await self._bias_repo.update_multiplier(
            ticket.action_type, new_multiplier
        )
        log.info(
            "adaptive_calibration_applied",
            action_type=ticket.action_type,
            old_multiplier=current_bias.multiplier,
            new_multiplier=updated_bias.multiplier,
            outcome=outcome.value,
        )

        # Step 5: Build response
        message_map: dict[ApprovalAction, str] = {
            ApprovalAction.APPROVE: "Action approved. Bias multiplier decreased (lower future risk).",
            ApprovalAction.REJECT: "Action rejected. Bias multiplier increased (higher future risk).",
            ApprovalAction.MODIFY: "Action modified. Bias multiplier slightly increased.",
        }

        return ApprovalActionResponse(
            approval_id=approval_id,
            evaluation_id=ticket.evaluation_id,
            new_status=new_status,
            updated_multiplier=updated_bias.multiplier,
            message=message_map[request.action],
        )
