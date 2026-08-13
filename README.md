# AutonomyGuard

AutonomyGuard is a centralized **Graduated Autonomy & Risk Governance Engine** designed to wrap AI Agents with an inline control plane. It dynamically calculates risk scores in real-time, routes execution based on dynamic thresholds, manages human approval queues, and recalibrates itself based on human feedback using Exponential Weighted Moving Average (EWMA) calibration.

## Core Features

1. **4-Dimensional Risk Engine**:
   - Reversibility (0.0 to 1.0)
   - Data Scope (Logarithmic scaling based on records affected)
   - Regulatory Category (PII, HIPAA, FINANCIAL, INTERNAL, PUBLIC)
   - LLM Confidence (Confidence inversion)

2. **Graduated Autonomy Router**:
   - **AUTONOMOUS**: Risk is low, execute immediately.
   - **CONFIRM**: Medium risk, paused for human confirmation.
   - **FULL_REVIEW**: High risk, blocked pending full review signoff.

3. **Adaptive EWMA Calibration**:
   - Learns from human feedback.
   - Approvals lower the risk bias multiplier for an action type.
   - Rejections heavily increase the multiplier to restrict future autonomous behavior.

4. **Agent Integration SDK**:
   - Provides a drop-in `@governed_tool` Python decorator.

5. **Built for Production**:
   - Asynchronous FastAPI architecture.
   - SQLAlchemy 2.0 with Async SQLite (easily swappable to PostgreSQL).
   - Strict Pydantic v2 schemas.
   - Clean DI architecture via FastAPI `Depends()`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Service

Start the FastAPI server:

```bash
uvicorn autonomy_guard.main:app --reload
```

## Running Tests

Run the full async integration test suite:

```bash
pytest -v
```

## Using the SDK

Wrap your AI tools with the SDK decorator:

```python
from autonomy_guard.sdk.decorator import governed_tool

@governed_tool(
    agent_id="agent-v1",
    action_type="record_update",
    reversibility=0.5,
    regulatory_category="INTERNAL"
)
async def my_ai_action(user_id: int, new_data: dict):
    # This will only execute if AutonomyGuard returns AUTONOMOUS.
    # Otherwise, it raises GovernanceApprovalRequired.
    pass
```
