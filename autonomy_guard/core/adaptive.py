"""Adaptive Threshold Calibration via Exponential Weighted Moving Average (EWMA).

After each human approval interaction, the per-action-type bias multiplier is
recalibrated using the formula:

    Multiplier_new = Multiplier_old × (1.0 + η × Δ_outcome)

Where:
    η = learning_rate (default 0.10)
    Δ_outcome:
        APPROVE  (unmodified)  = -1.0  → Gradually lowers multiplier
        MODIFY   (manual edit) = +0.5  → Slightly raises multiplier
        REJECT   (unsafe)      = +2.0  → Spikes multiplier

The multiplier is clamped to [min_bias_multiplier, max_bias_multiplier] to
prevent runaway growth or collapse.
"""

from __future__ import annotations

from enum import StrEnum

from autonomy_guard.config import Settings, settings


class ApprovalOutcome(StrEnum):
    """Possible outcomes of a human approval decision."""

    APPROVE = "APPROVE"
    MODIFY = "MODIFY"
    REJECT = "REJECT"


def get_outcome_delta(
    outcome: ApprovalOutcome,
    *,
    cfg: Settings | None = None,
) -> float:
    """Map an approval outcome to its calibration delta.

    Returns:
        The Δ_outcome value for the EWMA update.
    """
    cfg = cfg or settings
    deltas: dict[ApprovalOutcome, float] = {
        ApprovalOutcome.APPROVE: cfg.delta_approve,
        ApprovalOutcome.MODIFY: cfg.delta_modify,
        ApprovalOutcome.REJECT: cfg.delta_reject,
    }
    return deltas[outcome]


def compute_new_multiplier(
    current_multiplier: float,
    outcome: ApprovalOutcome,
    *,
    cfg: Settings | None = None,
) -> float:
    """Calculate the updated bias multiplier after a human decision.

    Args:
        current_multiplier: The existing EWMA multiplier for the action type.
        outcome: The human reviewer's decision.
        cfg: Optional settings override (useful in tests).

    Returns:
        The recalibrated multiplier, clamped to configured bounds.
    """
    cfg = cfg or settings

    delta = get_outcome_delta(outcome, cfg=cfg)
    raw_new = current_multiplier * (1.0 + cfg.learning_rate * delta)

    return max(
        cfg.min_bias_multiplier,
        min(cfg.max_bias_multiplier, round(raw_new, 6)),
    )
