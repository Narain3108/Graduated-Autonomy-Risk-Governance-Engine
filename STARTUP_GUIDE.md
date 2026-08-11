# AutonomyGuard — Startup & Operations Guide

This guide covers everything you need to start the AutonomyGuard server, test its functionality, and integrate it with your AI agents.

## 1. Prerequisites

Ensure you have Python 3.11 or higher installed on your machine.
AutonomyGuard uses Async SQLite by default, so no external database installation (like PostgreSQL) is required to run it locally.

## 2. Setup & Installation

Navigate into the project directory and set up an isolated Python virtual environment:

```bash
# 1. Navigate to the project root
cd /path/to/autonomy_guard

# 2. Create a virtual environment
python3 -m venv .venv

# 3. Activate the virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# 4. Install all dependencies
pip install -r requirements.txt
```

## 3. Starting the Server

The application is built on FastAPI and uses `uvicorn` as its asynchronous web server.

To start the server in development mode (with auto-reload enabled):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see logs indicating the application has started and the database has been initialized:
```text
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     starting_up app=AutonomyGuard version=0.1.0
INFO:     database_initialized
```

## 4. Viewing the API Documentation

FastAPI automatically generates an interactive API interface. Once the server is running, open your web browser and navigate to:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

From the Swagger UI, you can directly interact with the `/v1/evaluate` and `/v1/approvals` endpoints.

## 5. Testing the Server (cURL Examples)

Once the server is running, you can test it directly using `curl`.

### Check System Health
```bash
curl http://localhost:8000/healthz
```

### Scenario 1: A Low-Risk Autonomous Action (Read-Only Query)
This action should return `"execution_tier": "AUTONOMOUS"` and execute immediately.
```bash
curl -X POST http://localhost:8000/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test_agent",
    "action_type": "query_db",
    "tool_name": "fetch_user",
    "reversibility": 0.0,
    "records_affected": 1,
    "regulatory_category": "PUBLIC",
    "llm_confidence": 0.95
  }'
```

### Scenario 2: A High-Risk Action (Bulk Delete)
This action should return `"execution_tier": "FULL_REVIEW"` and return an `"approval_id"`.
```bash
curl -X POST http://localhost:8000/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test_agent",
    "action_type": "bulk_delete",
    "tool_name": "delete_all_users",
    "reversibility": 1.0,
    "records_affected": 5000,
    "regulatory_category": "PII",
    "llm_confidence": 0.20
  }'
```

## 6. How to Configure the Engine

By default, AutonomyGuard uses sensible default thresholds. However, you can configure these values by setting Environment Variables before starting the server.

You can create a `.env` file in the root directory (or set them in your terminal):

```env
# Application Settings
AG_DEBUG=True

# Override Risk Dimension Weights (must sum to 1.0)
AG_WEIGHT_REVERSIBILITY=0.40
AG_WEIGHT_DATA_SCOPE=0.20
AG_WEIGHT_REGULATORY=0.30
AG_WEIGHT_CONFIDENCE=0.10

# Routing Thresholds
AG_THRESHOLD_AUTONOMOUS=0.40
AG_THRESHOLD_CONFIRM=0.75
```
*AutonomyGuard will automatically pick up these environment variables on startup.*

## 7. Connecting AI Agents to the Server

Any agent running in a separate environment needs to send HTTP POST requests to `http://<your-server-ip>:8000/v1/evaluate`.

If the agent is written in Python, you can distribute the SDK found in `app/sdk/decorator.py`. The agent developer would instantiate the SDK client pointing to your server:

```python
from app.sdk.decorator import governed_tool, AutonomyGuardClient

# 1. Point the SDK to your running server
governance_client = AutonomyGuardClient(base_url="http://localhost:8000")

# 2. Wrap your agent tool
@governed_tool(
    client=governance_client,
    agent_id="my_agent",
    action_type="update_record",
    reversibility=0.5,
    regulatory_category="INTERNAL"
)
async def update_user(user_id: int):
    print("User updated!")
```
