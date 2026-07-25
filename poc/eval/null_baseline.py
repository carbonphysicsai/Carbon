"""Null baseline: untrained init under the same eval batch.

A strategy may only claim train quality if it beats this null by a margin.
"""

from __future__ import annotations

from typing import Any, Dict

from poc.models.fno1d import FNO1dConfig, init_params
from poc.eval.metrics import evaluate
from poc.generators.burgers1d import BurgersBatch

# Trained model must beat null rel_l2 by at least this relative margin
NULL_MARGIN = 0.05  # 5% relative improvement vs null


def null_eval(
    cfg: FNO1dConfig,
    batch: BurgersBatch,
    init_seed: int,
) -> Dict[str, float]:
    params = init_params(cfg, seed=init_seed)
    m = evaluate(params, cfg, batch)
    return {
        "rel_l2": float(m["rel_l2"]),
        "residual_mean": float(m["residual_mean"]),
        "conservation_error": float(m["conservation_error"]),
        "finite_ok": float(m["finite_ok"]),
    }


def beats_null(
    trained_rel_l2: float,
    null_rel_l2: float,
    margin: float = NULL_MARGIN,
) -> bool:
    """True if trained error is strictly better than null by `margin` relative."""
    if not (null_rel_l2 == null_rel_l2):  # NaN
        return False
    if not (trained_rel_l2 == trained_rel_l2):
        return False
    # absolute floor: must be lower
    if trained_rel_l2 >= null_rel_l2:
        return False
    # relative improvement
    improvement = (null_rel_l2 - trained_rel_l2) / max(null_rel_l2, 1e-12)
    return bool(improvement >= margin)


def train_quality_verdict(
    *,
    backend: str,
    loss_improved: bool,
    eval_rel_l2: float,
    null_rel_l2: float,
    eval_rel_l2_max: float = 0.50,
) -> Dict[str, Any]:
    """Single source of truth for train_quality_claim.

    All of:
      - backend == jax
      - loss dropped ≥5% during train
      - eval_rel_l2 < eval_rel_l2_max
      - beats null baseline by NULL_MARGIN
    """
    reasons = []
    if backend != "jax":
        reasons.append("backend_not_jax")
    if not loss_improved:
        reasons.append("loss_not_improved")
    if eval_rel_l2 >= eval_rel_l2_max:
        reasons.append(f"eval_rel_l2>={eval_rel_l2_max}")
    if not beats_null(eval_rel_l2, null_rel_l2):
        reasons.append("does_not_beat_null")

    claim = len(reasons) == 0
    return {
        "train_quality_claim": claim,
        "reasons": reasons,
        "eval_rel_l2": eval_rel_l2,
        "null_rel_l2": null_rel_l2,
        "eval_rel_l2_max": eval_rel_l2_max,
        "null_margin": NULL_MARGIN,
    }
