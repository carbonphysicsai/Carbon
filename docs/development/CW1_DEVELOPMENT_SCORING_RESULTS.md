# Carbon DEVELOPMENT measurement and scoring review

Rule: burgers-development-balanced-v2 (`sha256:e248bae48e64f4ff5565e462bd798c912326adef1e7a301f4b559d8668879f70`).
**Disposition: RETROSPECTIVE_DEVELOPMENT_RANKING**. No accepted real improvement, payment or network change is implied.

Baseline construction: `{"backbone": "fno", "challenge_id": "burgers-dynamics-v1", "parameters": {"steps": 40}, "schema_version": "1.0"}`.
Challenger construction: `{"backbone": "fno", "challenge_id": "burgers-dynamics-v1", "parameters": {"steps": 48}, "schema_version": "1.0"}`.

Both are retained authentic results on the seen 12 TRAIN / 12 EVAL / 12 STRESS development subset. New derived measurements preserve original signed receipts. No fresh training or model calls occurred. Historical agent feedback use is recorded in the prior session; this measurement task ran no new agent.

| Role | Metric (lower is better) | FNO-40 mean | FNO-48 mean | Difference | Baseline replica SD | Challenger replica SD |
|---|---|---:|---:|---:|---:|---:|
| EVAL | conserved_mean | 0.0073381283 | 0.010522015 | +0.0031838866 | 0.0076031 | 0.0017584 |
| EVAL | energy_path_max | 0.82627975 | 0.80491236 | -0.021367394 | 0.022334 | 0.0079643 |
| EVAL | energy_path_rms | 0.65345003 | 0.64089407 | -0.012555957 | 0.013277 | 0.0047288 |
| EVAL | field_time_rms | 0.73850786 | 0.7327835 | -0.0057243657 | 0.0060284 | 0.0022488 |
| EVAL | initial_condition | 9.6199454e-08 | 9.6199454e-08 | +0 | 0 | 0 |
| EVAL | integrated_energy_balance | 4.1936519 | 4.1174339 | -0.076218049 | 0.085581 | 0.02846 |
| EVAL | maximum_principle | 4.5854781e-08 | 4.5854781e-08 | +0 | 0 | 0 |
| STRESS | conserved_mean | 0.011170466 | 0.011801545 | +0.00063107893 | 0.011095 | 0.0019346 |
| STRESS | energy_path_max | 0.85192696 | 0.82708254 | -0.02484442 | 0.024945 | 0.014669 |
| STRESS | energy_path_rms | 0.6698389 | 0.65551613 | -0.014322772 | 0.014322 | 0.0082447 |
| STRESS | field_time_rms | 0.76895494 | 0.76253933 | -0.0064156119 | 0.0062873 | 0.0037311 |
| STRESS | initial_condition | 1.0011866e-07 | 1.0011866e-07 | +0 | 0 | 0 |
| STRESS | integrated_energy_balance | 4.2167549 | 4.1398485 | -0.076906438 | 0.079061 | 0.043522 |
| STRESS | maximum_principle | 4.0741333e-08 | 0.00097316192 | +0.00097312117 | 0 | 0.00090787 |

## Decision and limits

Descriptive scores: 0.557866892 -> 0.560526325. These are inadmissible diagnostic ranks, not accepted winner scores.
Finite-replica/reference score-difference envelope: [-0.003636521337663859, 0.008483928299982638]. This is not a confidence interval.
Baseline mandatory failures: EVAL:conserved_mean, EVAL:energy_path_max, STRESS:conserved_mean, STRESS:energy_path_max.
Challenger mandatory failures: EVAL:conserved_mean, EVAL:energy_path_max, STRESS:conserved_mean, STRESS:energy_path_max, STRESS:maximum_principle.
Reference sensitivity: `{"basis": "SHARED_METHOD_SPATIAL_REFINEMENT_NOT_QUALIFIED_BOUND", "energy": 3.4923317223582456e-05, "field": 0.0013757536776505602}`.
Three reconstructions and twelve cases per role are separate dependence dimensions. No independent case-by-replica sample count or population superiority is claimed. Shared-method refinement is an empirical indicator, not an independent reference witness or qualified error bound.

## Why the old scalar diagnostics did not change

baseline: sampled compression maximum at t=0 in 71/72; peak dissipation at t=0 in 72/72; absent half-energy crossing in 72/72. Exact artifact associations were checked against signed request hashes. The old fourfold spatial compression differs in spatial interpolation, but shared initial conditions/time-extremum domination and horizon clipping explain the repeated outputs; they do not prove identical trajectories.
challenger: sampled compression maximum at t=0 in 72/72; peak dissipation at t=0 in 72/72; absent half-energy crossing in 72/72. Exact artifact associations were checked against signed request hashes. The old fourfold spatial compression differs in spatial interpolation, but shared initial conditions/time-extremum domination and horizon clipping explain the repeated outputs; they do not prove identical trajectories.

## Execution accounting

Numerical task ledger: `[{"elapsed": 4.029116868972778, "id": "calibration-1", "kind": "numerical", "reserved": 600.0, "state": "COMPLETE"}, {"elapsed": 3.902911424636841, "id": "verification-1", "kind": "numerical", "reserved": 600.0, "state": "COMPLETE"}, {"elapsed": 4.924927234649658, "id": "derived-measurements", "kind": "numerical", "reserved": 600.0, "state": "COMPLETE"}, {"elapsed": 4.729476451873779, "id": "reference-resolution-recovery", "kind": "numerical", "reserved": 600.0, "state": "COMPLETE"}, {"elapsed": 2.469736337661743, "id": "verification-2", "kind": "numerical", "reserved": 600.0, "state": "COMPLETE"}, {"elapsed": 3.191124439239502, "id": "iteration-2/derived-measurements", "kind": "numerical", "reserved": 600.0, "state": "COMPLETE"}]`.
New retained artifacts before this report: 14,043,574 bytes. Each numerical carrier uses the accepted 2-CPU/4-GiB/no-swap, no-network controls; one worker at a time. Required repository acceptance is separate.
New provider calls: 0. New provider charges: USD 0. Fresh training: 0. Public-network transactions: 0. Synthetic reward checks are software/control evidence, not real winners.

## Retained evidence

Baseline source: $PRIVATE_CARBON_ROOT/burgers-session-20260916-prediction-inputs/source-8d7ad861-49e4-4cf8-a7be-483fd2ada0c5.json
Challenger source: $PRIVATE_CARBON_ROOT/burgers-comparison-20260916/source-a487e6f4-36a9-4d26-9b02-0db7e50f5992.json
Derived signed report: $PRIVATE_CARBON_ROOT/development-scoring-20260916/iteration-2/development-acceptance.json
Report digest: sha256:3b0b84e9655ad0d40803c822d2f0647864aa64d53928c4a695c10e605b3be2fe
Calibration and verification: $PRIVATE_CARBON_ROOT/development-scoring-20260916

## Calibration, verification and implementation evidence

Iteration 1: 17/17 analytic calibration checks and 17/17 previously untouched
V1 verification checks passed. Seen retained results then revealed inadequate
time-quadrature resolution for a mandatory energy-balance gate. V1 verification
was retired to development evidence before revision; its signed report remains.
Iteration 2: the energy-path maximum replaces that gate; all 21/21 fresh V2
verification checks passed. No third design iteration occurred.

The learning log records the falsifiers, value bases, retained errors and limits.
Public rule and aggregate feedback are C-07-owned. New C-06 domain-separated
signatures bind the rule and original receipts; lifecycle and C-10 quarantine
are rechecked before use. No old signed receipt or official flag was changed.

Synthetic reward adapter tests observed: opening 0.8 -> accepted 0.9 gives half
the allocation; after 24 hours it is one quarter. Self-improvement increases
remaining credit; takeover transfers the holder; copies, regression, conflicting
replay clocks and stale/ineligible evidence reject. These are synthetic inputs,
not real accepted winners or wallet payments. C-REWARD arithmetic is unchanged.

Baseline comparison/A5 checks passed 309 tests; final combined focused checks
passed 331 before the additional signature/lifecycle regression cases. The
expanded scoring suite passed 31 tests. Required PR acceptance remains a separate
delivery gate; its exact result belongs in the completion comment.

## Resource summary

Numerical wall time: **23.247293 seconds** in six sequential isolated carriers.
Observed CPU: **19.104448 seconds**. Maximum observed carrier memory: **180,670,464 bytes**.
Retained artifacts at owner-report seal: **14,043,574 bytes**.
No OOM, pending numerical dispatch, model call, fresh training or public transaction.

Report-generation defects were retained and repaired: the first numerical output
omitted already computed reference indicators; one reference-only recovery
produced the missing evidence without repeating training or measurements.
A scalar component wrapper and canonical tuple/list readback were repaired from
retained outputs. A duplicated accounting name was rejected before dispatch.
All actual numerical work, including recovery, is included above.

## Interpretation and next prerequisite

Carbon can make a bounded DEVELOPMENT acceptance decision under the exact v2
rule, but this historical pair cannot earn one. Both candidates are inadmissible
and predate rule registration. A future admissible opening baseline and fresh
challenger must satisfy the prospective-use and finite-cohort robustness rules.
See CW1_DEVELOPMENT_SCORING_NEXT_EXPERIMENT.md for one complete resource request.
Non-burn testnet additionally needs a winner-capable checked publication profile,
finalized identity-to-UID evidence and new exact transaction authority. Official
scientific, protected, production and settlement qualification remain unearned.
Recommend Harshdeep review the choices; no independent approval is claimed.
