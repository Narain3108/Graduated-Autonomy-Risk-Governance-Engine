"""AutonomyGuard — FastAPI Application Entrypoint.

Sets up:
  - Application lifecycle (DB init / shutdown)
  - Correlation ID middleware for per-request tracing
  - Structured JSON logging via structlog
  - Health check endpoint
  - API v1 router aggregation
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings
from app.db.session import dispose_engine, init_db

# ── Structlog Configuration ──────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
        if settings.debug
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        structlog.get_config()
        .get("wrapper_class", structlog.BoundLogger)
        .__module__
        and 0  # Always log everything; filtering is external
    )
    if False
    else structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("autonomy_guard")


# ── Application Lifecycle ────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown side-effects."""
    logger.info("starting_up", app=settings.app_name, version=settings.app_version)
    await init_db()
    logger.info("database_initialized")
    yield
    await dispose_engine()
    logger.info("shutdown_complete")


# ── Application Factory ──────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Construct and wire the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Centralized Graduated Autonomy & Risk Governance Engine for AI Agents. "
            "Evaluates agent action payloads, calculates dynamic risk scores, "
            "routes to execution tiers, and manages human approval workflows."
        ),
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Correlation ID Middleware ─────────────────────────────────────
    app.add_middleware(CorrelationIDMiddleware)

    # ── Route Registration ───────────────────────────────────────────
    _register_routes(app)

    return app


# ── Correlation ID Middleware ────────────────────────────────────────────


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique ``X-Correlation-ID`` into every request/response cycle.

    The ID is also bound to structlog's context variables so it appears in
    all log entries for the duration of the request.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = request.headers.get(
            "X-Correlation-ID", f"req_{uuid.uuid4().hex[:12]}"
        )
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


# ── Route Registration ───────────────────────────────────────────────────


def _register_routes(app: FastAPI) -> None:
    """Import and register all API routers."""
    from app.api.v1.approvals import router as approvals_router
    from app.api.v1.audit import router as audit_router
    from app.api.v1.evaluate import router as evaluate_router

    app.include_router(evaluate_router)
    app.include_router(approvals_router)
    app.include_router(audit_router)

    # ── Health Check ─────────────────────────────────────────────────

    @app.get(
        "/healthz",
        tags=["Health"],
        summary="System health check",
        description="Returns database connection status and application metadata.",
    )
    async def healthz() -> dict:
        """Report system health."""
        db_ok = True
        db_error: str | None = None
        try:
            from app.db.session import engine

            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        except Exception as exc:
            db_ok = False
            db_error = str(exc)

        return {
            "status": "healthy" if db_ok else "degraded",
            "app": settings.app_name,
            "version": settings.app_version,
            "database": {"connected": db_ok, "error": db_error},
        }


# ── Module-level app instance (for uvicorn) ─────────────────────────────

app = create_app()
