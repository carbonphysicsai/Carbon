# neurons/scoring/carbon_scorer.py

"""
CarbonScorer — SPEC-aligned multi-objective scoring with stress integration.

Hard Gate Rule (SPEC §8): any hard gate FAIL → combined_score = 0.
Weights: physics 45% / robustness 30% / accuracy 25%.
"""

from typing import Any, Dict, List, Optional

from carbon.common.scoring import compute_combined_score, score_from_metrics
from neurons.stress.stress_evaluator import StressEvaluator
from neurons.stress.stress_models import StressTestSet
from carbon.common.seeds import derive_pipeline_seeds
from neurons.utils.determinism import setup_determinism_for_component


class CarbonScorer:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.stress_evaluator = StressEvaluator(self)

    def compute_physics_fidelity(self, metrics: Dict[str, float]) -> float:
        return float(metrics.get("physics_fidelity", 0.0))

    def compute_robustness(self, metrics: Dict[str, float]) -> float:
        return float(metrics.get("robustness", 0.0))

    def compute_accuracy(self, metrics: Dict[str, float]) -> float:
        return float(metrics.get("accuracy", 0.0))

    def check_hard_gates(self, metrics: Dict[str, float]) -> List[str]:
        """Return list of failed hard-gate IDs (SPEC thresholds)."""
        violations: List[str] = []
        if metrics.get("mass_conservation_error", 0) > 1e-6:
            violations.append("mass_conservation")
        if metrics.get("energy_stability_error", metrics.get("energy_dissipation_rate", 0)) > 1e-6:
            violations.append("energy_stability")
        if metrics.get("boundary_error", 0) > 1e-4:
            violations.append("boundary")
        if metrics.get("rollout_rel_drift", 0) > 0.01:
            violations.append("rollout_stability")
        if abs(metrics.get("uq_coverage_error", 0)) > 0.02:
            violations.append("uq_calibration")
        if metrics.get("finite_ok", 1) == 0:
            violations.append("finite")
        return violations

    def evaluate_with_stress(
        self,
        model: Any,
        stress_set: StressTestSet,
        base_metrics: Optional[Dict[str, float]] = None,
        master_seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        if master_seed is not None:
            sub_seeds = derive_pipeline_seeds(master_seed)
            setup_determinism_for_component("scoring", master_seed, sub_seeds)

        stress_results = self.stress_evaluator.evaluate(model, stress_set)
        hard_failures = list(stress_results.get("hard_gate_failures") or [])

        base = dict(base_metrics or {})
        # Merge explicit gate failures from base metrics
        hard_failures.extend(self.check_hard_gates(base))
        # Dedupe
        hard_failures = sorted(set(hard_failures))

        physics = self.compute_physics_fidelity(base) or 0.0
        robustness = self.compute_robustness(base) or 0.0
        accuracy = self.compute_accuracy(base) or 0.0

        # If components missing, derive from stress contribution only when gates pass
        if not base.get("physics_fidelity") and not hard_failures:
            physics = float(stress_results.get("physics_component", physics))
        if not base.get("robustness") and not hard_failures:
            robustness = float(
                stress_results.get("stress_score_contribution", robustness)
            )

        scored = compute_combined_score(
            physics_fidelity=physics,
            robustness=robustness,
            accuracy=accuracy,
            hard_gate_failures=hard_failures,
        )
        scored["stress_results"] = stress_results
        return scored

    def score_strategy(
        self,
        model: Any,
        stress_set: Optional[StressTestSet] = None,
        base_metrics: Optional[Dict[str, float]] = None,
        master_seed: Optional[int] = None,
        gate_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if stress_set is not None:
            return self.evaluate_with_stress(model, stress_set, base_metrics, master_seed)

        base = dict(base_metrics or {})
        if gate_results is not None:
            return score_from_metrics(base, gate_results)

        failures = self.check_hard_gates(base)
        return compute_combined_score(
            physics_fidelity=self.compute_physics_fidelity(base),
            robustness=self.compute_robustness(base),
            accuracy=self.compute_accuracy(base),
            hard_gate_failures=failures,
        )
