"""Integration tests covering the core AutonomyGuard API endpoints and 3 main scenarios."""

import pytest
from httpx import AsyncClient

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from autonomy_guard.db.models import ActionBias

pytestmark = pytest.mark.asyncio


async def test_healthz(async_client: AsyncClient):
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["connected"] is True


async def test_scenario_3_read_only_query_autonomous(async_client: AsyncClient):
    """Scenario 3: Read-Only Query -> Must evaluate as AUTONOMOUS."""
    payload = {
        "agent_id": "agent-123",
        "action_type": "query",
        "tool_name": "search_public_records",
        "reversibility": 0.0,
        "records_affected": 1,
        "regulatory_category": "PUBLIC",
        "llm_confidence": 1.0,  # 1.0 confidence -> 0.0 risk
        "payload_summary": '{"query": "hello"}'
    }
    
    response = await async_client.post("/v1/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["execution_tier"] == "AUTONOMOUS"
    assert data["status"] == "EXECUTED"
    assert data["approval_id"] is None
    
    # Verify score breakdown (0.0 everything -> raw score 0.0)
    assert data["score_breakdown"]["raw_score"] == 0.0


async def test_scenario_2_single_record_update_confirm(async_client: AsyncClient):
    """Scenario 2: Single Record Update -> Must evaluate as CONFIRM."""
    # To get score >= 0.35 but < 0.70:
    # Rev=0.5 -> 0.175
    # Data Scope (1) -> 0.0
    # Reg (INTERNAL) -> 0.125
    # Conf (0.5) -> risk 0.5 * 0.15 = 0.075
    # Total = 0.175 + 0.125 + 0.075 = 0.375
    payload = {
        "agent_id": "agent-123",
        "action_type": "record_update",
        "tool_name": "update_user_settings",
        "reversibility": 0.5,
        "records_affected": 1,
        "regulatory_category": "INTERNAL",
        "llm_confidence": 0.5,
    }
    
    response = await async_client.post("/v1/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["execution_tier"] == "CONFIRM"
    assert data["status"] == "PENDING_APPROVAL"
    assert data["approval_id"] is not None
    assert data["approval_id"].startswith("appr_")


async def test_scenario_1_bulk_delete_full_review(async_client: AsyncClient, db_session: AsyncSession):
    """Scenario 1: Bulk Delete (10,000 PII records) -> Must evaluate as FULL_REVIEW."""
    payload = {
        "agent_id": "agent-123",
        "action_type": "bulk_delete",
        "tool_name": "delete_all_users",
        "reversibility": 1.0,  # 0.35
        "records_affected": 10000, # 0.25
        "regulatory_category": "PII", # 0.25
        "llm_confidence": 0.1, # risk 0.9 * 0.15 = 0.135
        # Total = 0.985
    }
    
    response = await async_client.post("/v1/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["execution_tier"] == "FULL_REVIEW"
    assert data["status"] == "PENDING_APPROVAL"
    approval_id = data["approval_id"]
    assert approval_id is not None
    
    # Let's resolve the approval ticket to test the adaptive calibration flow
    resolve_payload = {
        "action": "APPROVE",
        "reviewer_notes": "Looks good, approved."
    }
    resolve_response = await async_client.post(f"/v1/approvals/{approval_id}/action", json=resolve_payload)
    assert resolve_response.status_code == 200
    resolve_data = resolve_response.json()
    
    assert resolve_data["new_status"] == "APPROVED"
    assert resolve_data["updated_multiplier"] < 1.0  # Since we approved, it should drop (approx 0.9)
    
    # Verify DB persistence of the new multiplier
    result = await db_session.execute(select(ActionBias).where(ActionBias.action_type == "bulk_delete"))
    bias = result.scalar_one()
    assert bias.multiplier == resolve_data["updated_multiplier"]


async def test_audit_logs_pagination(async_client: AsyncClient):
    """Test retrieving audit logs via GET /v1/audit/logs."""
    # Seed a log first since DB is isolated per test
    payload = {
        "agent_id": "agent-123",
        "action_type": "query",
        "tool_name": "search_public_records",
        "reversibility": 0.0,
        "records_affected": 1,
        "regulatory_category": "PUBLIC",
        "llm_confidence": 1.0,
    }
    await async_client.post("/v1/evaluate", json=payload)

    response = await async_client.get("/v1/audit/logs?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 1
