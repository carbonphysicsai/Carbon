# Motor synthetic decision pilot

Evidence class: **COUNTED_GETDP**.

## Arms

| Arm | Selection | Queries | Outcome | Regret status | Exact regret |
|---|---|---:|---|---|---:|
| analytic-v1:fixed_grid | `{"airgap_mm": 0.4, "embrace": 0.85, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 48 | CONFIRMED_INFEASIBLE | INFEASIBLE_SELECTION | N/A |
| analytic-v1:screen_then_confirm | `{"airgap_mm": 0.4, "embrace": 0.85, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 48 | CONFIRMED_INFEASIBLE | INFEASIBLE_SELECTION | N/A |
| learned-krr-v1:fixed_grid | `{"airgap_mm": 0.8, "embrace": 0.65, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 48 | CONFIRMED_FEASIBLE | DEFINED_FINITE_SET | 0.019246665311291544 |
| learned-krr-v1:screen_then_confirm | `{"airgap_mm": 0.8, "embrace": 0.65, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 43 | CONFIRMED_FEASIBLE | DEFINED_FINITE_SET | 0.019246665311291544 |

## Comparator

Best-known only within the registered eight geometries, six current commands and 2D magnetostatic scope; it is not a global optimum.

Status: **COMPLETE_FINITE_SET**.

## Controlled comparisons

```json
{
  "model_value_same_fixed_grid": {
    "left": "analytic-v1:fixed_grid",
    "left_outcome": "CONFIRMED_INFEASIBLE",
    "left_regret": {
      "status": "INFEASIBLE_SELECTION",
      "value_fraction": null
    },
    "query_attempt_difference_right_minus_left": 0,
    "right": "learned-krr-v1:fixed_grid",
    "right_outcome": "CONFIRMED_FEASIBLE",
    "right_regret": {
      "comparator_design_id": "d04",
      "comparator_worst_reference_ripple_fraction": 0.245102140586187,
      "selected_worst_reference_ripple_fraction": 0.26434880589747856,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.019246665311291544
    },
    "same_declared_query_budget": true,
    "selected_geometry_same": false
  },
  "search_value_analytic_model": {
    "left": "analytic-v1:fixed_grid",
    "left_outcome": "CONFIRMED_INFEASIBLE",
    "left_regret": {
      "status": "INFEASIBLE_SELECTION",
      "value_fraction": null
    },
    "query_attempt_difference_right_minus_left": 0,
    "right": "analytic-v1:screen_then_confirm",
    "right_outcome": "CONFIRMED_INFEASIBLE",
    "right_regret": {
      "status": "INFEASIBLE_SELECTION",
      "value_fraction": null
    },
    "same_declared_query_budget": true,
    "selected_geometry_same": true
  },
  "search_value_learned_model": {
    "left": "learned-krr-v1:fixed_grid",
    "left_outcome": "CONFIRMED_FEASIBLE",
    "left_regret": {
      "comparator_design_id": "d04",
      "comparator_worst_reference_ripple_fraction": 0.245102140586187,
      "selected_worst_reference_ripple_fraction": 0.26434880589747856,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.019246665311291544
    },
    "query_attempt_difference_right_minus_left": -5,
    "right": "learned-krr-v1:screen_then_confirm",
    "right_outcome": "CONFIRMED_FEASIBLE",
    "right_regret": {
      "comparator_design_id": "d04",
      "comparator_worst_reference_ripple_fraction": 0.245102140586187,
      "selected_worst_reference_ripple_fraction": 0.26434880589747856,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.019246665311291544
    },
    "same_declared_query_budget": true,
    "selected_geometry_same": true
  }
}
```

## Metrics

```json
{
  "abstention_rate": 0.0,
  "arm_condition_uses": 24,
  "arms": 4,
  "decision_coverage_count": 4,
  "decision_coverage_denominator": 4,
  "false_feasible_proposal_denominator": 4,
  "false_feasible_proposals": 2,
  "groups": {
    "BOUNDARY_STRESS": {
      "arm_condition_uses": 8,
      "evidence_reuses": 4,
      "unique_design_condition_reference_cases": 4,
      "unique_reference_verdicts": {
        "FEASIBLE": 4,
        "INFEASIBLE": 0,
        "REFERENCE_UNAVAILABLE": 0
      }
    },
    "REPRESENTATIVE": {
      "arm_condition_uses": 16,
      "evidence_reuses": 8,
      "unique_design_condition_reference_cases": 8,
      "unique_reference_verdicts": {
        "FEASIBLE": 5,
        "INFEASIBLE": 3,
        "REFERENCE_UNAVAILABLE": 0
      }
    }
  },
  "proposal_outcomes": {
    "ABSTAIN": 0,
    "CONFIRMED_FEASIBLE": 2,
    "CONFIRMED_INFEASIBLE": 2,
    "UNRESOLVED": 0
  },
  "selected_reference_evidence_reuses": 12,
  "statistical_interpretation": {
    "future_uncertainty_requirement": "An approved sampling design and a justified independent-observation unit.",
    "mode": "DESCRIPTIVE_FIXED_PILOT",
    "population_reliability_or_generalisation_confidence": false,
    "reason": "The four arms share one decision problem and may reuse the same design-condition evidence; uses are not independent samples."
  },
  "unavailable_or_invalid_reference_evidence_uses": 0,
  "unique_selected_design_condition_reference_cases": 12,
  "unique_selected_reference_verdicts": {
    "FEASIBLE": 9,
    "INFEASIBLE": 3,
    "REFERENCE_UNAVAILABLE": 0
  },
  "worst_case_reference_ripple_fraction_for_feasible_proposals": {
    "analytic-v1:fixed_grid": null,
    "analytic-v1:screen_then_confirm": null,
    "learned-krr-v1:fixed_grid": 0.26434880589747856,
    "learned-krr-v1:screen_then_confirm": 0.26434880589747856
  }
}
```

## Cost and resource accounting

```json
{
  "compute_envelope": {
    "configured_hard_cap_allocated_core_hour_ceiling": 120.0,
    "configured_initial_allocated_core_hour_ceiling": 96.0,
    "cpus_per_solver_execution": 2,
    "hard_solver_execution_cap": 60,
    "initial_solver_executions": 48,
    "parallel_solver_executions": 6,
    "planning_hard_cap_core_hours": 120.0,
    "planning_initial_core_hours": 96.0,
    "retry_reserve": 12,
    "solver_timeout_seconds": 3600
  },
  "construction_search_wall_s": 0.033680475025903434,
  "construction_wall_s": 0.2877663809922524,
  "evaluation_wall_s": 0.009212659002514556,
  "model_inference_wall_s": 0.025377799960551783,
  "model_query_attempts": 187,
  "monetary_cost_status": "NO_APPROVED_OR_RECORDED_RESOURCE_RATE",
  "monetary_cost_usd": null,
  "per_arm_search_plus_evaluation_wall_s": {
    "analytic-v1:fixed_grid": 0.003858430020045489,
    "analytic-v1:screen_then_confirm": 0.00727753498358652,
    "learned-krr-v1:fixed_grid": 0.01791087002493441,
    "learned-krr-v1:screen_then_confirm": 0.008197455026675016
  },
  "reference_campaign_wall_s": 9973.9,
  "reference_condition_evaluations": 72,
  "reference_executions": 48,
  "reference_retries": 0,
  "reference_solver_wall_s": 59599.40000000001,
  "study_end_to_end_wall_s": 0.29697903999476694,
  "training_and_reconstruction": {
    "analytic-v1": {
      "kind": "ANALYTICAL_BASELINE"
    },
    "learned-krr-v1": {
      "cpu_s": 3.642817033,
      "historical_cost_status": "NOT_RECORDED_IN_PINNED_BASELINE_ARTIFACT",
      "historical_training_and_tuning_cost": null,
      "kind": "LEARNED_RECONSTRUCTION",
      "length": 4.0,
      "ridge": 0.0001,
      "training_records": 150,
      "wall_s": 0.1900515129964333
    }
  }
}
```

Representative and boundary-stress groups are reported separately. This fixed pilot supports no population reliability claim.

## Interpretation

The registered model/search arms selected different geometries.

No customer acceptance, global optimality, population reliability, 3D/thermal/dynamic performance, scientific qualification or LIVE readiness.
