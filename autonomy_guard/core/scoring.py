"""4-Dimensional Risk Scoring Engine.

Calculates a composite risk score S_risk ∈ [0.0, 1.0] by combining:
  1. Reversibility   (weight: 0.35)
  2. Data Scope      (weight: 0.25, logarithmic scale)
  3. Regulatory Cat.  (weight: 0.25)
  4. LLM Confidence  (weight: 0.15, inverted)

The raw weighted sum is then multiplied by a per-action-type bias multiplier
(learned via EWMA adaptive calibration) and clamped to [0.0, 1.0].
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from autonomy_guard.config import Settings, settings


# ── Dimension Score Calculators ──────────────────────────────────────────


def compute_reversibility_score(reversibility: float) -> float:
    """Clamp the raw reversibility value to [0.0, 1.0].

    0.0 = Fully reversible / read-only.
    1.0 = Irreversible / hard delete.
    """
    return max(0.0, min(1.0, reversibility))


def compute_data_scope_score(records_affected: int) -> float:
    """Logarithmic scaling of affected record count.

    Formula:  S_scope = min(1.0, log10(max(1, N)) / 4.0)

    Reference points:
        1       → 0.00
        10      → 0.25
        100     → 0.50
        1,000   → 0.75
        10,000+ → 1.00
    """
    if records_affected <= 1:
        return 0.0
    return min(1.0, math.log10(max(1, records_affected)) / 4.0)


def compute_regulatory_score(
    category: str,
    score_map: dict[str, float] | None = None,
) -> float:
    """Map a regulatory category string to its risk score.

    Uses the canonical mapping from ``Settings.REGULATORY_SCORES`` by default.
    Unknown categories are treated conservatively as ``0.5``.
    """
    mapping = score_map or Settings.REGULATORY_SCORES
    return mapping.get(category.upper(), 0.5)


def compute_confidence_risk(confidence: float | None) -> float:
    """Invert LLM confidence to a risk value.

    High confidence → low risk; ``None`` defaults to the conservative fallback.
    """
    if confidence is None:
        confidence = settings.default_confidence
    return 1.0 - max(0.0, min(1.0, confidence))


# ── Composite Score ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Immutable container for a full risk evaluation result."""

    reversibility: float
    data_scope: float
    regulatory: float
    confidence_risk: float
    raw_score: float
    bias_multiplier: float
    final_score: float


def compute_composite_score(
    reversibility: float,
    records_affected: int,
    regulatory_category: str,
    llm_confidence: float | None,
    bias_multiplier: float = 1.0,
    *,
    cfg: Settings | None = None,
) -> ScoreBreakdown:
    """Calculate the composite risk score across all four dimensions.

    Args:
        reversibility: Raw reversibility value [0.0, 1.0].
        records_affected: Number of records the action will touch.
        regulatory_category: One of PII, HIPAA, FINANCIAL, AUTH, INTERNAL, PUBLIC, NON_SENSITIVE.
        llm_confidence: Agent's self-reported confidence [0.0, 1.0] or ``None``.
        bias_multiplier: EWMA-learned action-type multiplier (default 1.0).
        cfg: Optional settings override (useful in tests).

    Returns:
        ``ScoreBreakdown`` with individual dimension scores, raw score, and final adjusted score.
    """
    cfg = cfg or settings

    s_rev = compute_reversibility_score(reversibility)
    s_scope = compute_data_scope_score(records_affected)
    s_reg = compute_regulatory_score(regulatory_category)
    s_conf = compute_confidence_risk(llm_confidence)

    raw = (
        cfg.weight_reversibility * s_rev
        + cfg.weight_data_scope * s_scope
        + cfg.weight_regulatory * s_reg
        + cfg.weight_confidence * s_conf
    )

    final = min(1.0, max(0.0, raw * bias_multiplier))

    return ScoreBreakdown(
        reversibility=s_rev,
        data_scope=s_scope,
        regulatory=s_reg,
        confidence_risk=s_conf,
        raw_score=round(raw, 6),
        bias_multiplier=bias_multiplier,
        final_score=round(final, 6),
    )
