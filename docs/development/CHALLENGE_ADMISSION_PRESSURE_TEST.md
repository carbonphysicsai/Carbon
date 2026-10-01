# Admission protocol pressure test, 2026-10-01

**Class:** retrospective DEVELOPMENT diagnostic and engineering regression tests.
No new numerical training/reference campaign, hostile arbitrary-code execution,
scientific acceptance, security acceptance or score change occurred.

## Findings and dispositions

| Finding | Retained evidence | Hardening |
|---|---|---|
| Current battery score can prefer unsafe decisions | EV1/EV2 `boundary_optimist`; EV2 current rule at or above all 14 eligible reconstructed members | Both admission tracks require known-bad controls, score-exploitation attacks and a separate unsafe/tail criterion. No score formula was changed. |
| Real-model ranking includes a gate-ineligible member | EV1/EV2 `experiment.evaluate` builds `reconstructed` from kind only; `mlp_raw-s0` fails eligibility | Supplemental audit excludes ineligible members; protocol requires separate admissibility reporting. Historical results remain unchanged. |
| Means use different resolved subsets | `experiment._mean` drops None per member; audit finds 2 common resolved verification scenarios of 3 in EV1, and 3 of 8 in EV2 | Report every denominator; common-case diagnostics plus prospective unresolved-outcome sensitivity are required. Common-case deletion alone is not a repair for informative missingness. |
| Seed replicas can overstate panel diversity | EV1 has 10 eligible members but 6 recipe groups; EV2 has 14 and 9 | Report recipe-group sensitivity and require preregistered independent-family/dependence treatment. These recipe groups do not prove architecture independence. |
| EV1 cannot test useful-design regret on verification | No feasible design in any verification scenario; all eligible models tie on the common resolved scenarios | Mark the relationship unresolved on this diagnostic; require outcome coverage and sufficient decision resolution. |
| EV2's defence addresses one constructed failure | Decision-aware profiles demote the optimist but do not establish improved real-model ranking | Keep controls separate from the primary claim; require fresh hidden attacks and real-model effect/uncertainty evidence. |
| EV3 draft reuses EV2's now-published conditions | PR #457 EV3 draft section 2 | Do not call those untouched confirmation. Freeze a new confirmation set before claiming admission. EV3 remains draft, not executed or rewritten here. |
| In-process studies cannot establish hostile-code containment | EV1 run inventory | Require actual isolated construction/inference integration tests for the exact permission/runtime profile. Unsupported levels remain NOT_RUN. |
| A readiness state could omit both new studies | Existing v2 records have no two-track requirement | v3 requires both tracks (readiness-record wiring lands with #458; until then no record can be launch-approved without the owner). Accepted evidence needs exact scope, preregistration, report, raw-artifact hashes and scoped review binding. Failure/absence blocks a launch-approved readiness record. |

## Audit results

The read-only adapter consumed the retained EV1 results on main and the pinned
EV2 results from PR #457. Source commits, paths and SHA-256 values are in
`evidence/admission-pressure-2026-10-01/sources.json`; derived audits are adjacent.
These outputs do not replace the experiments' summaries.

| Diagnostic | EV1 | EV2 |
|---|---:|---:|
| Eligible reconstructed members | 10 | 14 |
| Recipe groups under existing name/seed grouping | 6 | 9 |
| Scheduled verification scenarios/conditions | 3 | 8 |
| Common resolved scenarios/conditions across eligible members | 2 | 3 |
| Current-rule tau on those common cases | undefined: all decision outcomes tied | 0.423 |
| EV2 development-selected decision-aware rule tau on common cases | not applicable | 0.150 |

The changed denominator changes the question. These descriptive coefficients
have no qualified uncertainty analysis and cannot select a score formula or
establish a customer claim. Known unsafe selections outside the common mask
remain in each model's coverage report; they do not disappear from the evidence.
The audit reports NOT_ESTABLISHED even if every descriptive statistic is positive.

## Adversarial regression coverage

Tests include known high-score/worse-outcome data, a dropped bad outcome,
nonfinite and invalid losses, all-tied/no-observation panels, ineligible members,
control contamination and duplicate recipe seeds. Evidence-gate tests include
missing tracks/checks, schema downgrade, empty PASS claims, failed/inconclusive
checks, open blockers, foreign scope, every changed material pin, tampered bytes,
path/symlink escape, duplicate JSON keys and nonfinite JSON. Positive fixtures
prove the same checks admit a structurally complete record; fixture acceptance
is not a scientific/security result.

The retained EV1 regression proves the source document stays unchanged after the read-only audit. No historical formula or metric was changed.
Canonical CI supplies acceptance; native-host pytest results are diagnostics.

## Amendment of 2026-10-01: findings, not per-change review

OWNER-CHALLENGE-ADMISSION-01 as amended moves review from every change to every
finding (internal development only, never mainnet). The detector
`carbon.battery.value.divergence` turns the first finding above into an emitted
condition. On the retained results (`ev1-conditions.json`, `ev2-conditions.json`
in this evidence folder):
- **EV2:** the boundary-optimist control fires `SCORE_VALUE_DIVERGENCE` on both
  splits, scoring at or above all 14 eligible real members. `control-oracle`
  never fires. Six real members fire on the development split and one on
  verification. Those are findings to investigate, not verdicts. `mlp_raw-s0`
  emits `GATE_ANOMALY`.
- **EV1:** the boundary-optimist control fires on both splits, and
  `mlp_raw-s0` emits `GATE_ANOMALY`.
- **Noise bands** (basis: `seed_variation`, and τ over every
  one-seed-per-recipe panel):
  - decision loss: EV2 1.694 (development) and 1.675 (verification);
  - progress τ: EV2 0.260 over 24 panels, EV1 0.365 over 12.
- **Audit caveat.** EV2's τ figures (0.202 proposed against 0.298 deciding,
  verification) carry the caveat above: gate-ineligible models in the panel,
  unequal denominators from unresolved outcomes, and seed repeats that do not
  establish method diversity.

## Required next execution

Prepare the battery admission sheet using the real challenge and EV infrastructure.
The science owner must define practical effect, uncertainty/coverage and unsafe
outcome criteria. The security owner must approve the actual isolation/attacker
scope. Freeze fresh EV3 confirmation conditions, run Level 0 through the real
worker, then compare one bounded permission expansion and its ablation. Retest
combined permissions before proposing any wider profile. Include a recipient
rebuild and the promised continued-training path.

The new file validator checks maintainer-held evidence completeness and bindings.
It cannot authenticate a reviewer, prove a claimed experiment occurred or inspect
arbitrary code for all hidden knowledge. No runtime activation consumer was added;
release review and existing qualification mechanisms retain that authority.
