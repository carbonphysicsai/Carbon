# C-EP2 measurement and replay evidence

**Status:** bounded DEVELOPMENT tooling and study complete; automated acceptance pending
**Baseline:** `d783c2c7209c7eea2d46dd395c4eaaf8094a9e71`
**Frozen executable revision:** `bb009a2d8a3045fd29ea2c2c8c46aed2218c5c76`
**Primary Hub map_ref:** `WAVE-C/C-EP2`
**Recommendation:** `COLLECT MISSING INPUTS FIRST`

## Evidence result

The frozen Mac-host study ran to its preregistered stop. It observed 49 distinct
admitted jobs and 49 packs: 41 fixture completions, four terminal incompletes,
and four reconciliation-required pending jobs. It separately retained 12
deduplicated requests, four infrastructure retries, 53 attempts/reconstruction
partials, 41 results/summaries, and four each post-result and post-closure
replays. Twenty-four ordinary outcomes were `SCORED`; four intentional
conclusive fixture outcomes were `MANDATORY_GATE_FAILED`. No replay created a
pack or completed proposal.

No eligible numerical probe ran. Actual physical reference cases, reference
attempts, candidate inference and accelerator time remain unknown because the
C-EP1 A8 backend is a scalar stub. The seven-scenario detached replay is
explicitly uncalibrated and preserves unknown B overhead. It supplies
conditional arithmetic only, so no B implementation is selected.

The queued-work probe reproduced a C-EP1 composition defect and validates the
narrow C-01 repair: exact claim leaves an older unrelated attempt `QUEUED` and
executes only the expected already-admitted binding. General `claim_next`
behavior remains compatible.

## Focused requirement-to-test map

| Requirement | Exercised by |
|---|---|
| Observation parity and privacy | `test_observation_privacy_and_diagnostic_sink_noninterference`, `test_disabled_observer_executes_once_without_trace`, frozen harness parity block |
| Job/pack/attempt association | C-EP1 suite plus `test_c_ep1_service_leaves_unrelated_queued_attempt_untouched` |
| Replay dedup/no double charge | `test_hand_computable_singleton_and_replay_dedup_accounting`, frozen ordinary blocks |
| Missing phases stay unknown | `test_unknown_model_quantity_remains_unknown`, frozen missing records |
| Invalid unit/nonfinite/clock/missing span | `test_observation_rejects_clock_unit_nonfinite_and_missing_errors` |
| Nested/transaction accounting | `test_root_span_accounting_does_not_double_charge_nested_or_precommit` |
| Observer overhead/sink failure | sink non-interference test and eight frozen parity pairs |
| C-EP1/C-01 failure/retry/restart | `test_frozen_harness_accounts_failure_retry_restart_and_keeps_layers_distinct` |
| Hand-computable singleton | `test_hand_computable_singleton_and_replay_dedup_accounting` |
| B reduces to A without sharing | `test_b_reduces_to_a_when_compatibility_is_unavailable` |
| Bounds/underfill/compatibility/no future use | `test_b_groups_only_ready_compatible_same_challenge_jobs` |
| Slow/failed/unresolved closure delay | `test_shared_closure_waits_for_slow_or_unresolved_member_without_global_barrier` |
| Multiple Challenges/no global barrier | same closure test plus multiple-Challenge frozen scenario |
| Unknown B overhead blocks unconditional claim | `test_unknown_b_overhead_prevents_unconditional_savings_claim` |
| Evidence-layer labels | frozen harness test and closed enums/schema validation |
| Singleton/private/closure/identity/production/reward exclusions | C-EP1 suite, public-safe projection checks, `reference_sharing_implemented=false`, no runtime membership API |

These simulator tests are not durable multi-member runtime tests. Any separately
authorized B implementation must add admission-race, immutable-membership,
shared-reference completeness, per-member failure/cancellation, last-member
closure, restart/stale-write and TRAIN/EVAL randomness-separation tests.

## Current local commands

```text
python -m pytest -q tests/cpu/test_c_ep2_measurement_study.py tests/cpu/test_c_ep1_evaluation_packs.py tests/cpu/test_c01_durable_execution.py
58 passed in 0.67s
```

The exact runtime command and host manifest are retained in
`docs/development/C_EP2_STUDY_RUNBOOK.md` and the machine-readable study folder.
Black 26.5.1 and Ruff 0.16.3 pass the changed Python paths. Canonical PR
acceptance remains pending and is not inferred from the local run.

## Output inventory

- `C_EP2_MEASUREMENT_PROTOCOL.md`: frozen boundary and observation map.
- `C-EP2_measurement_study_v1.json`: scenario/repetition configuration.
- `public_safe_trace_v1.jsonl`: 131 records without associations or clocks.
- `variant_a_observations_v1.json`: aggregate observed execution/accounting.
- `variant_b_replay_v1.json`: detached uncalibrated counterfactual results.
- `profiler_summary_v1.json`: unqualified, machine-readable decision summary.
- `environment_manifest_v1.json`: source/config/host identity.
- `C_EP2_VARIANT_B_DECISION_REPORT.md`: owner-facing report.

The locally retained private trace SHA-256 is
`a60619a97829112e6e0fa3de141ddf6586fa44317ac0ebf83de3a9f54e759a8d`.
It is excluded from the repository.

## Authority ceiling

C-EP2 earns no scientific, reference, security, archive, network, reward,
production, LIVE or Variant-B runtime authority. AT-09, AT-16, AT-19, AT-22 and
AT-30 remain blocked. PR #140 remains design input only; issue #141 remains
unrelated and open.
