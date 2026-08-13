"""Execution Tier Decision Router.

Maps a final composite risk score to one of three execution tiers:
  - AUTONOMOUS   (score < threshold_autonomous)
  - CONFIRM      (threshold_autonomous ≤ score < threshold_confirm)
  - FULL_REVIEW  (score ≥ threshold_confirm)
"""

from __future__ import annotations

from enum import StrEnum

from autonomy_guard.config import Settings, settings


class ExecutionTier(StrEnum):
    """The three graduated autonomy levels."""

    AUTONOMOUS = "AUTONOMOUS"
    CONFIRM = "CONFIRM"
    FULL_REVIEW = "FULL_REVIEW"


def determine_execution_tier(
    final_score: float,
    *,
    cfg: Settings | None = None,
) -> ExecutionTier:
    """Route a risk score to the appropriate execution tier.

    Args:
        final_score: Composite score ∈ [0.0, 1.0] (after bias multiplier).
        cfg: Optional settings override (useful in tests).

    Returns:
        The ``ExecutionTier`` that the score falls into.
    """
    cfg = cfg or settings

    if final_score < cfg.threshold_autonomous:
        return ExecutionTier.AUTONOMOUS
    if final_score < cfg.threshold_confirm:
        return ExecutionTier.CONFIRM
    return ExecutionTier.FULL_REVIEW


def build_decision_reason(tier: ExecutionTier, final_score: float) -> str:
    """Generate a human-readable explanation for the routing decision."""
    reasons: dict[ExecutionTier, str] = {
        ExecutionTier.AUTONOMOUS: (
            f"Risk score {final_score:.3f} is below the autonomous threshold. "
            "Action is safe for immediate execution."
        ),
        ExecutionTier.CONFIRM: (
            f"Risk score {final_score:.3f} falls in the confirmation band. "
            "Action requires human confirmation before execution."
        ),
        ExecutionTier.FULL_REVIEW: (
            f"Risk score {final_score:.3f} exceeds the review threshold. "
            "Action is blocked pending full human review and signoff."
        ),
    }
    return reasons[tier]
