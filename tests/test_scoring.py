"""Unit tests for the Risk Scoring Engine."""

import pytest

from autonomy_guard.core.scoring import (
    compute_composite_score,
    compute_data_scope_score,
    compute_reversibility_score,
    compute_regulatory_score,
    compute_confidence_risk,
)


def test_reversibility_clamping():
    assert compute_reversibility_score(0.5) == 0.5
    assert compute_reversibility_score(-1.0) == 0.0
    assert compute_reversibility_score(2.0) == 1.0


def test_data_scope_logarithmic_scale():
    assert compute_data_scope_score(1) == 0.0
    assert compute_data_scope_score(10) == 0.25
    assert compute_data_scope_score(100) == 0.50
    assert compute_data_scope_score(1000) == 0.75
    assert compute_data_scope_score(10000) == 1.0
    assert compute_data_scope_score(100000) == 1.0  # Clamped
    assert compute_data_scope_score(0) == 0.0
    assert compute_data_scope_score(-5) == 0.0


def test_regulatory_score():
    assert compute_regulatory_score("PII") == 1.0
    assert compute_regulatory_score("INTERNAL") == 0.5
    assert compute_regulatory_score("PUBLIC") == 0.0
    assert compute_regulatory_score("UNKNOWN_CATEGORY") == 0.5


def test_confidence_risk():
    assert compute_confidence_risk(1.0) == 0.0
    assert compute_confidence_risk(0.0) == 1.0
    assert compute_confidence_risk(None) == 0.5
    assert compute_confidence_risk(1.5) == 0.0  # Clamped


def test_compute_composite_score():
    # Weights: Rev(0.35) + Scope(0.25) + Reg(0.25) + Conf(0.15)
    # Total irreversible, max scope, PII, 0 confidence = 1.0
    breakdown = compute_composite_score(
        reversibility=1.0,
        records_affected=10000,
        regulatory_category="PII",
        llm_confidence=0.0,
    )
    assert breakdown.raw_score == 1.0
    assert breakdown.final_score == 1.0

    # Totally safe: fully reversible, 1 record, public, high confidence = 0.0
    breakdown_safe = compute_composite_score(
        reversibility=0.0,
        records_affected=1,
        regulatory_category="PUBLIC",
        llm_confidence=1.0,
    )
    assert breakdown_safe.raw_score == 0.0
    assert breakdown_safe.final_score == 0.0

    # Mixed with bias multiplier
    breakdown_mixed = compute_composite_score(
        reversibility=0.5,           # 0.5 * 0.35 = 0.175
        records_affected=100,        # 0.5 * 0.25 = 0.125
        regulatory_category="INTERNAL", # 0.5 * 0.25 = 0.125
        llm_confidence=0.5,          # risk=0.5 * 0.15 = 0.075
        bias_multiplier=1.2,         # raw sum = 0.500
    )
    assert breakdown_mixed.raw_score == 0.500
    assert breakdown_mixed.final_score == pytest.approx(0.600)  # 0.5 * 1.2
