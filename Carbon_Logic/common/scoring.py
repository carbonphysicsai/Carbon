"""Official scoring — SPEC §8 / appendices/Scoring.md (45/30/25 + hard gates).

Hard Gate Rule: any FAIL → combined_score = 0. No partial credit.
Components only matter when all critical gates pass.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


PHYSICS_WEIGHT = 0.45
ROBUSTNESS_WEIGHT = 0.30
ACCURACY_WEIGHT = 0.25


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def margin_linear_clip(error: float, tau: float) -> float:
    """Score Pack default: m(e, τ) = clip(1 - e/τ, 0, 1). Higher is better."""
    t = max(float(tau), 1e-12)
    return _clamp01(1.0 - float(error) / t)


def norm_map_error(error: float, scale: float = 1.0) -> float:
    """Smooth map error → [0,1] score (higher is better). Legacy helper."""
    e = max(0.0, float(error))
    return _clamp01(1.0 / (1.0 + e / max(scale, 1e-12)))


def compute_combined_score(
    *,
    physics_fidelity: float,
    robustness: float,
    accuracy: float,
    hard_gate_failures: Optional[List[str]] = None,
    weights: Optional[Tuple[float, float, float]] = None,
) -> Dict[str, Any]:
    """SPEC multi-objective score.

    If any hard gate failed, combined_score is forced to 0.0.
    """
    failures = list(hard_gate_failures or [])
    physics = _clamp01(physics_fidelity)
    robust = _clamp01(robustness)
    acc = _clamp01(accuracy)

    if weights is not None:
        w_p, w_r, w_a = (float(weights[0]), float(weights[1]), float(weights[2]))
    else:
        w_p, w_r, w_a = PHYSICS_WEIGHT, ROBUSTNESS_WEIGHT, ACCURACY_WEIGHT

    if failures:
        combined = 0.0
        gate_failed = True
    else:
        combined = w_p * physics + w_r * robust + w_a * acc
        gate_failed = False

    return {
        "physics_fidelity": physics,
        "robustness": robust,
        "accuracy": acc,
        "combined_score": combined,
        "hard_gate_failures": failures,
        "gate_failed": gate_failed,
        "weights": {
            "physics": w_p,
            "robustness": w_r,
            "accuracy": w_a,
        },
    }


def score_from_metrics(
    metrics: Dict[str, float],
    gate_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build score from metric dict + optional gate result list.

    Expected metric keys (optional, with defaults):
      physics_fidelity, robustness, accuracy
      OR residual_mean / conservation_error / eval_rel_l2 / stress_rel_l2
    """
    failures: List[str] = []
    if gate_results:
        for g in gate_results:
            if not g.get("pass", g.get("passed", True)):
                failures.append(str(g.get("id", g.get("gate_id", "unknown"))))

    if "physics_fidelity" in metrics:
        physics = float(metrics["physics_fidelity"])
    else:
        residual = float(metrics.get("residual_mean", metrics.get("physics_residual", 0.1)))
        cons = float(metrics.get("conservation_error", 0.0))
        physics = 0.5 * margin_linear_clip(residual, 2.0) + 0.5 * margin_linear_clip(
            cons, 0.08
        )

    if "robustness" in metrics:
        robust = float(metrics["robustness"])
    else:
        stress_err = float(metrics.get("stress_rel_l2", metrics.get("stress_error", 0.2)))
        robust = margin_linear_clip(stress_err, 0.5)

    if "accuracy" in metrics:
        acc = float(metrics["accuracy"])
    else:
        eval_err = float(metrics.get("eval_rel_l2", metrics.get("accuracy_error", 0.1)))
        acc = margin_linear_clip(eval_err, 0.5)

    return compute_combined_score(
        physics_fidelity=physics,
        robustness=robust,
        accuracy=acc,
        hard_gate_failures=failures,
    )
