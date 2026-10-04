# Motor synthetic decision pilot

Evidence class: **ANALYTICAL_FIXTURE**.

## Arms

| Arm | Selection | Queries | Outcome | Regret status | Exact regret |
|---|---|---:|---|---|---:|
| analytic-v1:fixed_grid | `{"airgap_mm": 0.4, "embrace": 0.85, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 48 | CONFIRMED_FEASIBLE | DEFINED_FINITE_SET | 0.0 |
| analytic-v1:screen_then_confirm | `{"airgap_mm": 0.4, "embrace": 0.85, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 48 | CONFIRMED_FEASIBLE | DEFINED_FINITE_SET | 0.0 |
| learned-krr-v1:fixed_grid | `{"airgap_mm": 0.8, "embrace": 0.65, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 48 | CONFIRMED_FEASIBLE | DEFINED_FINITE_SET | 0.0 |
| learned-krr-v1:screen_then_confirm | `{"airgap_mm": 0.8, "embrace": 0.65, "magnet_mm": 3.5, "slot_bottom_mm": 38.16, "slot_open_deg": 3.7, "tooth_mm": 3.5}` | 43 | CONFIRMED_FEASIBLE | DEFINED_FINITE_SET | 0.0 |

## Comparator

Best-known only within the registered eight geometries, six current commands and 2D magnetostatic scope; it is not a global optimum.

Status: **COMPLETE_FINITE_SET**.

## Controlled comparisons

```json
{
  "model_value_same_fixed_grid": {
    "left": "analytic-v1:fixed_grid",
    "left_outcome": "CONFIRMED_FEASIBLE",
    "left_regret": {
      "comparator_design_id": "d01",
      "comparator_worst_reference_ripple_fraction": 0.0,
      "selected_worst_reference_ripple_fraction": 0.0,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.0
    },
    "query_attempt_difference_right_minus_left": 0,
    "right": "learned-krr-v1:fixed_grid",
    "right_outcome": "CONFIRMED_FEASIBLE",
    "right_regret": {
      "comparator_design_id": "d01",
      "comparator_worst_reference_ripple_fraction": 0.0,
      "selected_worst_reference_ripple_fraction": 0.0,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.0
    },
    "same_declared_query_budget": true,
    "selected_geometry_same": false
  },
  "search_value_analytic_model": {
    "left": "analytic-v1:fixed_grid",
    "left_outcome": "CONFIRMED_FEASIBLE",
    "left_regret": {
      "comparator_design_id": "d01",
      "comparator_worst_reference_ripple_fraction": 0.0,
      "selected_worst_reference_ripple_fraction": 0.0,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.0
    },
    "query_attempt_difference_right_minus_left": 0,
    "right": "analytic-v1:screen_then_confirm",
    "right_outcome": "CONFIRMED_FEASIBLE",
    "right_regret": {
      "comparator_design_id": "d01",
      "comparator_worst_reference_ripple_fraction": 0.0,
      "selected_worst_reference_ripple_fraction": 0.0,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.0
    },
    "same_declared_query_budget": true,
    "selected_geometry_same": true
  },
  "search_value_learned_model": {
    "left": "learned-krr-v1:fixed_grid",
    "left_outcome": "CONFIRMED_FEASIBLE",
    "left_regret": {
      "comparator_design_id": "d01",
      "comparator_worst_reference_ripple_fraction": 0.0,
      "selected_worst_reference_ripple_fraction": 0.0,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.0
    },
    "query_attempt_difference_right_minus_left": -5,
    "right": "learned-krr-v1:screen_then_confirm",
    "right_outcome": "CONFIRMED_FEASIBLE",
    "right_regret": {
      "comparator_design_id": "d01",
      "comparator_worst_reference_ripple_fraction": 0.0,
      "selected_worst_reference_ripple_fraction": 0.0,
      "status": "DEFINED_FINITE_SET",
      "value_fraction": 0.0
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
  "false_feasible_proposals": 0,
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
        "FEASIBLE": 8,
        "INFEASIBLE": 0,
        "REFERENCE_UNAVAILABLE": 0
      }
    }
  },
  "proposal_outcomes": {
    "ABSTAIN": 0,
    "CONFIRMED_FEASIBLE": 4,
    "CONFIRMED_INFEASIBLE": 0,
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
    "FEASIBLE": 12,
    "INFEASIBLE": 0,
    "REFERENCE_UNAVAILABLE": 0
  },
  "worst_case_reference_ripple_fraction_for_feasible_proposals": {
    "analytic-v1:fixed_grid": 0.0,
    "analytic-v1:screen_then_confirm": 0.0,
    "learned-krr-v1:fixed_grid": 0.0,
    "learned-krr-v1:screen_then_confirm": 0.0
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
  "construction_search_wall_s": 0.03429465601220727,
  "construction_wall_s": 0.495204451988684,
  "evaluation_wall_s": 0.007309731998248026,
  "model_inference_wall_s": 0.026700617978349328,
  "model_query_attempts": 187,
  "monetary_cost_status": "NO_APPROVED_OR_RECORDED_RESOURCE_RATE",
  "monetary_cost_usd": null,
  "per_arm_search_plus_evaluation_wall_s": {
    "analytic-v1:fixed_grid": 0.0036252540012355894,
    "analytic-v1:screen_then_confirm": 0.0037714469945058227,
    "learned-krr-v1:fixed_grid": 0.01428879400191363,
    "learned-krr-v1:screen_then_confirm": 0.01527411601273343
  },
  "reference_campaign_wall_s": 0.0,
  "reference_condition_evaluations": 72,
  "reference_executions": 0,
  "reference_retries": 0,
  "reference_solver_wall_s": 0.0,
  "study_end_to_end_wall_s": 0.502514183986932,
  "training_and_reconstruction": {
    "analytic-v1": {
      "kind": "ANALYTICAL_BASELINE"
    },
    "learned-krr-v1": {
      "cpu_s": 8.048508288,
      "historical_cost_status": "NOT_RECORDED_IN_PINNED_BASELINE_ARTIFACT",
      "historical_training_and_tuning_cost": null,
      "kind": "LEARNED_RECONSTRUCTION",
      "length": 4.0,
      "ridge": 0.0001,
      "training_records": 150,
      "wall_s": 0.4237721390090883
    }
  }
}
```

Representative and boundary-stress groups are reported separately. This fixed pilot supports no population reliability claim.

## Interpretation

The registered model/search arms selected different geometries.

No customer acceptance, global optimality, population reliability, 3D/thermal/dynamic performance, scientific qualification or LIVE readiness.
