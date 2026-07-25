"""45/30/25 scoring for Burgers PoC — hard gates zero the combined score."""

from __future__ import annotations

from typing import Any, Dict, List

from carbon.common.scoring import compute_combined_score, norm_map_error
from poc.eval.gates import all_passed


def score_run(
    eval_metrics: Dict[str, float],
    stress_metrics: Dict[str, float],
    gate_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ok, failures = all_passed(gate_results)

    accuracy = norm_map_error(float(eval_metrics.get("rel_l2", 1.0)), scale=0.5)
    robustness = norm_map_error(float(stress_metrics.get("rel_l2", 1.0)), scale=0.5)
    physics = 0.5 * norm_map_error(
        float(eval_metrics.get("residual_mean", 10.0)), scale=2.0
    ) + 0.5 * norm_map_error(
        float(eval_metrics.get("conservation_error", 1.0)), scale=0.05
    )

    scored = compute_combined_score(
        physics_fidelity=physics,
        robustness=robustness,
        accuracy=accuracy,
        hard_gate_failures=failures if not ok else [],
    )
    # Card-friendly aliases
    return {
        "physics": scored["physics_fidelity"],
        "robustness": scored["robustness"],
        "accuracy": scored["accuracy"],
        "combined": scored["combined_score"],
        "gate_failed": scored["gate_failed"],
        "hard_gate_failures": scored["hard_gate_failures"],
        "weights": scored["weights"],
    }
