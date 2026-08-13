"""SDK for AI Agents to integrate with AutonomyGuard.

Provides the ``@governed_tool`` Python decorator, allowing agents to seamlessly
wrap their existing function calls with real-time governance evaluation.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
from typing import Any, Callable, TypeVar, cast

import httpx

logger = logging.getLogger("autonomy_guard.sdk")

F = TypeVar("F", bound=Callable[..., Any])


class GovernanceApprovalRequired(Exception):
    """Raised when an action requires human approval before it can execute."""
    
    def __init__(self, message: str, evaluation_id: str, approval_id: str) -> None:
        super().__init__(message)
        self.evaluation_id = evaluation_id
        self.approval_id = approval_id


class GovernanceRejectedError(Exception):
    """Raised when an action is outright rejected or blocked by governance."""


class AutonomyGuardClient:
    """Async HTTP client for AutonomyGuard."""

    def __init__(self, base_url: str = "https://j8iwpsnxq1.execute-api.us-east-1.amazonaws.com") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    async def evaluate(
        self,
        agent_id: str,
        action_type: str,
        tool_name: str,
        reversibility: float,
        records_affected: int,
        regulatory_category: str,
        llm_confidence: float | None = None,
        payload_summary: str = "{}",
    ) -> dict[str, Any]:
        """Call the /v1/evaluate endpoint."""
        payload = {
            "agent_id": agent_id,
            "action_type": action_type,
            "tool_name": tool_name,
            "reversibility": reversibility,
            "records_affected": records_affected,
            "regulatory_category": regulatory_category,
            "llm_confidence": llm_confidence,
            "payload_summary": payload_summary,
        }
        
        response = await self._client.post("/v1/evaluate", json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def governed_tool(
    agent_id: str,
    action_type: str,
    reversibility: float,
    regulatory_category: str,
    client: AutonomyGuardClient | None = None,
    # These could also be dynamically extracted from kwargs in a real implementation
    extract_records_affected: Callable[[tuple[Any, ...], dict[str, Any]], int] | None = None,
    extract_confidence: Callable[[tuple[Any, ...], dict[str, Any]], float | None] | None = None,
) -> Callable[[F], F]:
    """Decorator to enforce AutonomyGuard governance on an agent tool.

    Args:
        agent_id: Unique identifier for the agent calling the tool.
        action_type: Canonical category of this action (e.g., 'bulk_delete').
        reversibility: Risk score 0.0 (read-only) to 1.0 (irreversible).
        regulatory_category: e.g., 'PII', 'FINANCIAL', 'PUBLIC'.
        client: Optional configured AutonomyGuardClient.
        extract_records_affected: Callable to dynamically determine affected records from args.
        extract_confidence: Callable to dynamically determine confidence from args.
    """
    ag_client = client or AutonomyGuardClient()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tool_name = func.__name__
            
            # 1. Dynamically extract runtime metrics from args if provided
            records = 1
            if extract_records_affected:
                records = extract_records_affected(args, kwargs)
                
            conf: float | None = None
            if extract_confidence:
                conf = extract_confidence(args, kwargs)

            # Build a simple payload summary
            payload_summary = json.dumps({"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}})
            if len(payload_summary) > 4000:
                payload_summary = payload_summary[:4000] + "...(truncated)"

            # 2. Evaluate risk
            logger.info(f"Evaluating {tool_name} for agent {agent_id}...")
            try:
                eval_resp = await ag_client.evaluate(
                    agent_id=agent_id,
                    action_type=action_type,
                    tool_name=tool_name,
                    reversibility=reversibility,
                    records_affected=records,
                    regulatory_category=regulatory_category,
                    llm_confidence=conf,
                    payload_summary=payload_summary,
                )
            except httpx.HTTPError as e:
                logger.error(f"Failed to contact AutonomyGuard: {e}")
                raise RuntimeError("Governance check failed due to network error.") from e

            tier = eval_resp["execution_tier"]
            eval_id = eval_resp["evaluation_id"]
            
            logger.info(f"Evaluation complete: Tier={tier}, Final Score={eval_resp['score_breakdown']['final_score']}")

            # 3. Route based on execution tier
            if tier == "AUTONOMOUS":
                # Safe to execute immediately
                return await func(*args, **kwargs)
                
            elif tier == "CONFIRM" or tier == "FULL_REVIEW":
                approval_id = eval_resp["approval_id"]
                raise GovernanceApprovalRequired(
                    f"Action '{tool_name}' requires human approval (Tier: {tier}). Ticket ID: {approval_id}",
                    evaluation_id=eval_id,
                    approval_id=approval_id,
                )
            
            else:
                raise GovernanceRejectedError(f"Unknown execution tier: {tier}")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Simple sync wrapper for non-async tools if needed
            raise NotImplementedError("governed_tool currently only supports async functions.")

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator
