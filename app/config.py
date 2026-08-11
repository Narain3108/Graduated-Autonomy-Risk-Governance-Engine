"""Application configuration loaded from environment variables with sensible defaults.

All risk weights, thresholds, and adaptive learning parameters are centralised here
so that tuning never requires touching business logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Immutable application-wide settings sourced from environment variables."""

    # ── Application ──────────────────────────────────────────────────────
    app_name: str = "AutonomyGuard"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./autonomy_guard.db",
        description="Async SQLAlchemy connection string.",
    )

    # ── Risk Scoring Weights (must sum to 1.0) ───────────────────────────
    weight_reversibility: float = 0.35
    weight_data_scope: float = 0.25
    weight_regulatory: float = 0.25
    weight_confidence: float = 0.15

    # ── Decision Router Thresholds ───────────────────────────────────────
    threshold_autonomous: float = 0.35
    threshold_confirm: float = 0.70  # Score >= this → FULL_REVIEW

    # ── Adaptive Calibration ─────────────────────────────────────────────
    learning_rate: float = 0.10
    default_bias_multiplier: float = 1.0
    min_bias_multiplier: float = 0.5
    max_bias_multiplier: float = 3.0

    # ── Adaptive Outcome Deltas ──────────────────────────────────────────
    delta_approve: float = -1.0
    delta_modify: float = 0.5
    delta_reject: float = 2.0

    # ── LLM Confidence Defaults ──────────────────────────────────────────
    default_confidence: float = 0.50

    # ── Pagination ───────────────────────────────────────────────────────
    default_page_size: int = 20
    max_page_size: int = 100

    # ── Regulatory Category Score Mapping ────────────────────────────────
    REGULATORY_SCORES: ClassVar[dict[str, float]] = {
        "PII": 1.0,
        "HIPAA": 1.0,
        "FINANCIAL": 1.0,
        "AUTH": 1.0,
        "INTERNAL": 0.5,
        "PUBLIC": 0.0,
        "NON_SENSITIVE": 0.0,
    }

    model_config = {
        "env_prefix": "AG_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Module-level singleton — import this everywhere.
settings = Settings()
