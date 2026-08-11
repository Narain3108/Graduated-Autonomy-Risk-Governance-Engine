"""Unit tests for the EWMA Adaptive Calibration Engine."""

import pytest

from app.core.adaptive import ApprovalOutcome, compute_new_multiplier
from app.config import Settings


def test_compute_new_multiplier_approve():
    # APPROVE (delta = -1.0), rate = 0.10 -> new = old * (1 - 0.1) = 0.9 * old
    cfg = Settings(learning_rate=0.10, delta_approve=-1.0, min_bias_multiplier=0.1)
    new_mult = compute_new_multiplier(1.0, ApprovalOutcome.APPROVE, cfg=cfg)
    assert new_mult == pytest.approx(0.90)


def test_compute_new_multiplier_modify():
    # MODIFY (delta = +0.5), rate = 0.10 -> new = old * (1 + 0.05) = 1.05 * old
    cfg = Settings(learning_rate=0.10, delta_modify=0.5)
    new_mult = compute_new_multiplier(1.0, ApprovalOutcome.MODIFY, cfg=cfg)
    assert new_mult == pytest.approx(1.05)


def test_compute_new_multiplier_reject():
    # REJECT (delta = +2.0), rate = 0.10 -> new = old * (1 + 0.20) = 1.20 * old
    cfg = Settings(learning_rate=0.10, delta_reject=2.0)
    new_mult = compute_new_multiplier(1.0, ApprovalOutcome.REJECT, cfg=cfg)
    assert new_mult == pytest.approx(1.20)


def test_multiplier_clamping():
    # Ensure it doesn't drop below min
    cfg_min = Settings(min_bias_multiplier=0.5, learning_rate=0.5, delta_approve=-2.0)
    # raw_new = 1.0 * (1 + (0.5 * -2.0)) = 1.0 * 0.0 = 0.0
    new_mult = compute_new_multiplier(1.0, ApprovalOutcome.APPROVE, cfg=cfg_min)
    assert new_mult == 0.5  # Clamped to min

    # Ensure it doesn't exceed max
    cfg_max = Settings(max_bias_multiplier=3.0, learning_rate=0.5, delta_reject=10.0)
    # raw_new = 1.0 * (1 + (0.5 * 10.0)) = 1.0 * 6.0 = 6.0
    new_mult2 = compute_new_multiplier(1.0, ApprovalOutcome.REJECT, cfg=cfg_max)
    assert new_mult2 == 3.0  # Clamped to max
