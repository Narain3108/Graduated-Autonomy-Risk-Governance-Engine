"""Clean Data Access Layer — Repository classes for AutonomyGuard persistence.

Each repository encapsulates all DynamoDB queries for its respective model,
keeping the service layer free of AWS details.
"""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

from autonomy_guard.config import settings
from autonomy_guard.db.models import ActionBias, ApprovalTicket, AuditLog


class AuditRepository:
    """Handles creation and querying of immutable evaluation audit logs in DynamoDB."""

    def __init__(self, table: Any) -> None:
        self._table = table

    async def create(self, audit_log: AuditLog) -> AuditLog:
        """Persist a new audit log record."""
        item = json.loads(audit_log.model_dump_json(), parse_float=Decimal)
        await self._table.put_item(Item=item)
        return audit_log

    async def get_by_id(self, eval_id: str) -> AuditLog | None:
        """Retrieve a single audit log by evaluation ID."""
        response = await self._table.get_item(Key={"id": eval_id})
        item = response.get("Item")
        if not item:
            return None
        return AuditLog(**item)

    async def list_logs(
        self,
        page: int = 1,
        page_size: int | None = None,
        agent_id: str | None = None,
        action_type: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Return a list of audit logs. (Simplified pagination for DynamoDB)"""
        # DynamoDB doesn't natively support SQL-like offset/limit pagination without LastEvaluatedKey.
        # For simplicity in this implementation, we will use a scan.
        # In production, a GSI on agent_id or action_type would be used.
        limit = min(page_size or settings.default_page_size, settings.max_page_size)
        
        # We will scan for now (not optimal for production, but satisfies the interface)
        scan_kwargs: dict[str, Any] = {"Limit": limit}
        
        response = await self._table.scan(**scan_kwargs)
        items = response.get("Items", [])
        
        logs = [AuditLog(**item) for item in items]
        logs.sort(key=lambda x: x.created_at, reverse=True)
        return logs, len(logs)

    async def update_status(self, eval_id: str, status: str) -> AuditLog | None:
        """Update the status field of an existing audit log."""
        response = await self._table.update_item(
            Key={"id": eval_id},
            UpdateExpression="SET #status = :s",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":s": status},
            ReturnValues="ALL_NEW"
        )
        return AuditLog(**response.get("Attributes", {}))


class ApprovalRepository:
    """Handles creation, retrieval, and status transitions for approval tickets."""

    def __init__(self, table: Any) -> None:
        self._table = table

    async def create(self, ticket: ApprovalTicket) -> ApprovalTicket:
        """Persist a new approval ticket."""
        item = json.loads(ticket.model_dump_json(), parse_float=Decimal)
        await self._table.put_item(Item=item)
        return ticket

    async def get_by_id(self, approval_id: str) -> ApprovalTicket | None:
        """Retrieve a single approval ticket by its ID."""
        response = await self._table.get_item(Key={"id": approval_id})
        item = response.get("Item")
        if not item:
            return None
        return ApprovalTicket(**item)

    async def update(
        self,
        approval_id: str,
        *,
        status: str,
        reviewer_notes: str | None = None,
        modified_payload: str | None = None,
    ) -> ApprovalTicket | None:
        """Transition an approval ticket to a new status."""
        update_expr = "SET #s = :s, updated_at = :u"
        expr_names = {"#s": "status"}
        expr_vals: dict[str, Any] = {
            ":s": status,
            ":u": datetime.now(timezone.utc).isoformat()
        }
        
        if reviewer_notes is not None:
            update_expr += ", reviewer_notes = :rn"
            expr_vals[":rn"] = reviewer_notes
        if modified_payload is not None:
            update_expr += ", modified_payload = :mp"
            expr_vals[":mp"] = modified_payload
            
        try:
            response = await self._table.update_item(
                Key={"id": approval_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_vals,
                ReturnValues="ALL_NEW"
            )
            return ApprovalTicket(**response.get("Attributes", {}))
        except Exception:
            return None

    async def list_pending(
        self,
        page: int = 1,
        page_size: int | None = None,
    ) -> tuple[list[ApprovalTicket], int]:
        """Return list of pending approval tickets."""
        limit = min(page_size or settings.default_page_size, settings.max_page_size)
        
        response = await self._table.scan(
            FilterExpression="#s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "PENDING"},
            Limit=limit
        )
        items = response.get("Items", [])
        
        tickets = [ApprovalTicket(**item) for item in items]
        tickets.sort(key=lambda x: x.created_at, reverse=True)
        return tickets, len(tickets)


class ActionBiasRepository:
    """Manages EWMA-learned per-action-type risk bias multipliers in DynamoDB."""

    def __init__(self, table: Any) -> None:
        self._table = table

    async def get_multiplier(self, action_type: str) -> float:
        """Return the current bias multiplier for an action type."""
        response = await self._table.get_item(Key={"action_type": action_type})
        item = response.get("Item")
        if item:
            # DynamoDB returns floats as Decimal, pydantic handles it, but let's be safe
            return float(item.get("multiplier", settings.default_bias_multiplier))
        return settings.default_bias_multiplier

    async def get_or_create(self, action_type: str) -> ActionBias:
        """Return existing bias record or create a new one with defaults."""
        response = await self._table.get_item(Key={"action_type": action_type})
        item = response.get("Item")
        if item:
            return ActionBias(**item)
            
        bias = ActionBias(
            action_type=action_type,
            multiplier=settings.default_bias_multiplier,
            sample_count=0,
        )
        item = json.loads(bias.model_dump_json(), parse_float=Decimal)
        await self._table.put_item(Item=item)
        return bias

    async def update_multiplier(
        self,
        action_type: str,
        new_multiplier: float,
    ) -> ActionBias:
        """Set a new multiplier value and increment sample count."""
        clamped_multiplier = max(
            settings.min_bias_multiplier,
            min(settings.max_bias_multiplier, new_multiplier),
        )
        
        # We need to do this carefully if multiple requests hit simultaneously. 
        # But for simplicity, we'll just read and update.
        bias = await self.get_or_create(action_type)
        
        response = await self._table.update_item(
            Key={"action_type": action_type},
            UpdateExpression="SET multiplier = :m, sample_count = sample_count + :inc, updated_at = :u",
            ExpressionAttributeValues={
                ":m": Decimal(str(clamped_multiplier)),
                ":inc": 1,
                ":u": datetime.now(timezone.utc).isoformat()
            },
            ReturnValues="ALL_NEW"
        )
        
        return ActionBias(**response.get("Attributes", {}))
