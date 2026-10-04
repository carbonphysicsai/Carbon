# AI accelerator cooling decision study

Evidence class: **ANALYTICAL_FIXTURE**. Material: **DEVELOPMENT**.

This study is synthetic and remains inside the periodic straight-channel cell. It is not customer acceptance, scientific qualification, production qualification, or a global-optimality claim.

## Arms

| Arm | Selection | Queries | Reference verdicts | Regret status | Regret (W) |
|---|---|---:|---|---|---:|
| analytic-v1/fixed_grid | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 48 | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 |
| analytic-v1/screen_then_confirm | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 13 | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 |
| learned-krr-v1/fixed_grid | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 48 | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 |
| learned-krr-v1/screen_then_confirm | `{"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}` | 18 | `{'FEASIBLE': 6, 'INFEASIBLE': 0, 'REFERENCE_UNAVAILABLE': 0}` | DEFINED_FINITE_SET | 0.0 |

## Finite-set comparator

Best-known only within the declared finite eight-design, six-condition set and periodic-cell scope; it is not a global optimum.

Best comparator: `{"design_id": "d03", "geometry": {"channel_depth_mm": 2.5, "channel_width_mm": 0.25, "fin_width_mm": 0.3, "flow_lpm_per_kw": 1.25}, "reference_feasible_all_conditions": true, "resolved_all_conditions": true, "worst_reference_hydraulic_w": 0.12466262629494432}`

## Decision metrics

```json
{
  "abstention_rate": 0.0,
  "abstentions": 0,
  "arms": 4,
  "decision_coverage": 1.0,
  "false_feasible_condition_decisions": 0,
  "false_feasible_condition_denominator": 24,
  "false_feasible_condition_wilson_95": {
    "high": 0.13797620467498017,
    "low": 0.0
  },
  "false_feasible_proposal_denominator": 4,
  "false_feasible_proposal_wilson_95": {
    "high": 0.4898908364545973,
    "low": 0.0
  },
  "false_feasible_proposals": 0,
  "groups": {
    "BOUNDARY_STRESS": {
      "false_feasible": 0,
      "false_feasible_denominator": 8,
      "false_feasible_wilson_95": {
        "high": 0.32440756488388023,
        "low": 0.0
      },
      "proposed_condition_decisions": 8,
      "reference_available": 8,
      "reference_confirmed_feasible": 8
    },
    "REPRESENTATIVE": {
      "false_feasible": 0,
      "false_feasible_denominator": 16,
      "false_feasible_wilson_95": {
        "high": 0.1936076805344365,
        "low": 0.0
      },
      "proposed_condition_decisions": 16,
      "reference_available": 16,
      "reference_confirmed_feasible": 16
    }
  },
  "resolved_proposals": 4,
  "unavailable_or_invalid_reference_evidence": 0,
  "unavailable_reference_statuses": {},
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
  "model_inference_wall_s": 0.2539131829980761,
  "model_query_attempts": 127,
  "monetary_cost_status": "NO_OWNER_APPROVED_RESOURCE_RATE",
  "monetary_cost_usd": null,
  "per_decision_wall_s_by_arm": {
    "analytic-v1/fixed_grid": 0.20335279599385103,
    "analytic-v1/screen_then_confirm": 0.05892699999822071,
    "learned-krr-v1/fixed_grid": 0.007189671996457037,
    "learned-krr-v1/screen_then_confirm": 0.003788393994909711
  },
  "reference_campaign_wall_s": 0.0,
  "reference_condition_evaluations": 72,
  "reference_cpu_limit_per_execution": 2,
  "reference_executions": 0,
  "reference_retries": 0,
  "reference_solver_wall_s": 0.0,
  "study_end_to_end_wall_s": 2.981603759995778,
  "training_and_reconstruction": {
    "analytic-v1": {
      "kind": "ANALYTICAL_BASELINE"
    },
    "learned-krr-v1": {
      "cpu_s": 41.630316543,
      "historical_cost_status": "NOT_RECORDED_IN_PINNED_BASELINE_ARTIFACT",
      "historical_training_and_tuning_cost": null,
      "kind": "LEARNED_RECONSTRUCTION",
      "training_records": 400,
      "wall_s": 2.1773103730010916
    }
  }
}
```

Representative and boundary-stress results remain separate; no combined weighting or pass threshold is asserted.
