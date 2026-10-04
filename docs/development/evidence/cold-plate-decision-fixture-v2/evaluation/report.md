# AI accelerator cooling decision study

Evidence class: **ANALYTICAL_FIXTURE**. Material: **DEVELOPMENT**.

This study is synthetic and remains inside the periodic straight-channel cell. It is not customer acceptance, scientific qualification, production qualification, or a global-optimality claim.

## Arms

| Arm | Selection | Queries | Proposal outcome | Reference verdicts | Regret status | Exact regret (W) | Best-observed difference (W) |
|---|---|---:|---|---|---|---:|---:|
| analytic-v1/fixed_grid | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 48 | CONFIRMED_FEASIBLE | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 | N/A |
| analytic-v1/screen_then_confirm | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 13 | CONFIRMED_FEASIBLE | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 | N/A |
| learned-krr-v1/fixed_grid | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 48 | CONFIRMED_FEASIBLE | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 | N/A |
| learned-krr-v1/screen_then_confirm | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 18 | CONFIRMED_FEASIBLE | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 | N/A |

## Finite-set comparator

Best-known only within the declared finite eight-design, six-condition set and periodic-cell scope; it is not a global optimum.

Comparator status: **COMPLETE_FINITE_SET**.

Best observed reference-feasible design: `{"design_id": "d03", "geometry": {"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}, "proposal_outcome": "CONFIRMED_FEASIBLE", "reference_feasible_all_conditions": true, "resolved_all_conditions": true, "verdicts": {"FEASIBLE": 6, "INFEASIBLE": 0, "REFERENCE_UNAVAILABLE": 0}, "worst_reference_hydraulic_w": 0.12466262629494432}`

Best reference-feasible design in a sufficiently resolved complete set: `{"design_id": "d03", "geometry": {"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}, "proposal_outcome": "CONFIRMED_FEASIBLE", "reference_feasible_all_conditions": true, "resolved_all_conditions": true, "verdicts": {"FEASIBLE": 6, "INFEASIBLE": 0, "REFERENCE_UNAVAILABLE": 0}, "worst_reference_hydraulic_w": 0.12466262629494432}`

## Decision metrics

```json
{
  "abstention_rate": 0.0,
  "abstentions": 0,
  "arm_condition_uses": 24,
  "arms": 4,
  "decision_coverage": 1.0,
  "decision_coverage_count": 4,
  "decision_coverage_denominator": 4,
  "false_feasible_proposal_denominator": 4,
  "false_feasible_proposals": 0,
  "groups": {
    "BOUNDARY_STRESS": {
      "arm_condition_uses": 8,
      "evidence_reuses": 6,
      "unique_design_condition_reference_cases": 2,
      "unique_reference_available": 2,
      "unique_reference_confirmed_feasible": 2,
      "unique_reference_confirmed_infeasible": 0,
      "unique_reference_unavailable": 0
    },
    "REPRESENTATIVE": {
      "arm_condition_uses": 16,
      "evidence_reuses": 12,
      "unique_design_condition_reference_cases": 4,
      "unique_reference_available": 4,
      "unique_reference_confirmed_feasible": 4,
      "unique_reference_confirmed_infeasible": 0,
      "unique_reference_unavailable": 0
    }
  },
  "proposal_outcomes": {
    "ABSTAIN": 0,
    "CONFIRMED_FEASIBLE": 4,
    "CONFIRMED_INFEASIBLE": 0,
    "UNRESOLVED": 0
  },
  "selected_reference_evidence_reuses": 18,
  "statistical_interpretation": {
    "future_uncertainty_requirement": "An approved sampling design and a justified unit of independent observation.",
    "mode": "DESCRIPTIVE_FIXED_PILOT",
    "population_reliability_or_generalisation_confidence": false,
    "reason": "The four arms share one decision problem and may reuse the same design-condition evidence; arm and condition uses are not independent samples."
  },
  "unavailable_or_invalid_reference_evidence": 0,
  "unavailable_reference_statuses": {},
  "unique_selected_design_condition_reference_cases": 6,
  "unique_selected_reference_verdicts": {
    "FEASIBLE": 6,
    "INFEASIBLE": 0,
    "REFERENCE_UNAVAILABLE": 0
  },
  "worst_case_reference_hydraulic_w_for_feasible_proposals": {
    "analytic-v1/fixed_grid": 0.12466262629494432,
    "analytic-v1/screen_then_confirm": 0.12466262629494432,
    "learned-krr-v1/fixed_grid": 0.12466262629494432,
    "learned-krr-v1/screen_then_confirm": 0.12466262629494432
  }
}
```

## Cost and limits

```json
{
  "compute_envelope": {
    "accounting_description": {
      "actual_cpu_use_limitation": "The CPU flag is an allocation limit, not a measurement of CPU time consumed; actual CPU use requires host or container accounting and is reported only when measured.",
      "configured_ceiling_basis": "Allocation ceiling equals executions multiplied by 2 CPUs and 3600 seconds: 96 allocated core-hours initially and 120 allocated core-hours including the retry reserve.",
      "estimate_basis": "Planning estimate of 0.4 core-hours per solver execution: 19.2 core-hours for 48 initial executions and 24.0 core-hours at the 60-execution hard cap.",
      "overhead_limitation": "Orchestration, container startup, storage, artifact processing and host overhead are outside the per-execution solver CPU allocation and must be reported separately when measured."
    },
    "configured_hard_cap_allocated_core_hour_ceiling": 120.0,
    "configured_initial_allocated_core_hour_ceiling": 96.0,
    "estimated_hard_cap_core_hours": 24.0,
    "estimated_initial_core_hours": 19.2,
    "hard_solver_execution_cap": 60,
    "initial_solver_executions": 48,
    "retry_reserve": 12
  },
  "construction_wall_s": 0.896583899972029,
  "evaluation_wall_s": 0.19074680004268885,
  "model_inference_wall_s": 0.22619350004242733,
  "model_query_attempts": 127,
  "monetary_cost_status": "NO_OWNER_APPROVED_RESOURCE_RATE",
  "monetary_cost_usd": null,
  "per_decision_wall_s_by_arm": {
    "analytic-v1/fixed_grid": 0.20551600004546344,
    "analytic-v1/screen_then_confirm": 0.04914319998351857,
    "learned-krr-v1/fixed_grid": 0.006255799962673336,
    "learned-krr-v1/screen_then_confirm": 0.0038627999601885676
  },
  "reference_campaign_wall_s": 0.0,
  "reference_condition_evaluations": 72,
  "reference_cpu_limit_per_execution": 2,
  "reference_executions": 0,
  "reference_retries": 0,
  "reference_solver_wall_s": 0.0,
  "study_end_to_end_wall_s": 1.0873307000147179,
  "training_and_reconstruction": {
    "analytic-v1": {
      "kind": "ANALYTICAL_BASELINE"
    },
    "learned-krr-v1": {
      "cpu_s": 6.875,
      "historical_cost_status": "NOT_RECORDED_IN_PINNED_BASELINE_ARTIFACT",
      "historical_training_and_tuning_cost": null,
      "kind": "LEARNED_RECONSTRUCTION",
      "training_records": 400,
      "wall_s": 0.5045740000205114
    }
  }
}
```

The fixed pilot is descriptive. The four arms share one decision problem and may reuse the same reference cases; no population-level reliability or generalisation confidence is claimed. A future uncertainty estimate requires an approved sampling design and a justified unit of independent observation.

Representative and boundary-stress results remain separate; no combined weighting or pass threshold is asserted.

## Interpretation

All four registered model/search arms selected the same geometry in this fixed pilot. This is agreement, not evidence of a learned-model design-quality advantage.

The pilot asks whether selected designs satisfy the registered constraints according to reference CFD, how they compare with the finite-set comparator, whether registered search methods reduce queries or cost, and whether the learned model changes or improves the decision in this particular study.

This evidence does not establish: Customer acceptance, global optimality, full cold-plate behavior, transient/controller performance, scientific qualification, or LIVE readiness.
