# Exam-design campaign 1: pilot results and costed remaining run matrix

Checkpoint under the owner direction of 2026-09-24, recorded **before** any large
reference-generation job is admitted.

The campaign is described in `EXAM_DESIGN_CAMPAIGN_SPECIFICATION.md`, and its
evidence is under `docs/development/evidence/exam-design-2026-09-24/`.

**What this evidence is:**
- Public/synthetic DEVELOPMENT research only.
- Its execution class is *direct execution inside the pinned study image plus a
  hash-locked wheel overlay; not `validator_launch`; containment from the
  provider's runtime.*

**What it is not:** nothing here is scientifically, security or production
qualified.

## 1. Execution status

| Item | Value |
|---|---|
| Active pod | `6dto4gg26hes1y`, 1 × A40 Secure, USD 0.49/hr, created 21:06:06Z, deadline 01:06:05Z |
| Revision on the pod | `da1a55b2f0094fee29cf83bcc41438eabb0b839e` (hash-pinned code manifest) |
| Battery (refs A, 1016 jobs) | see §8 (measured at the decision point) |
| Photonic pilot (16 jobs) | 0 complete after 15 min; GPU utilization 0 % throughout (see §5) |
| Spend | USD 0.63 by account balance (22.24 → 21.60); elapsed-time estimate USD 0.65 |
| Discarded attempts | USD 0.23 (see below) |
| Ceiling | USD 20.00 (min(20, balance − 2) at start); cleanup reserve USD 0.25 per pod |

**The three discarded attempts,** retained as evidence, not re-labelled:

| Pod | Cost | What went wrong |
|---|---|---|
| `9qhyoniu04hdte` | USD 0.005 | superseded by a combined plan |
| `d8jfjlw2bucnoz` | USD 0.114 | the plan's own name collided with the runtime `plan` key, so the battery child exited |
| `c45fer91e5645o` | USD 0.114 | every worker sized its thread pools to 96 visible cores, which ran about 10× slow with the GPU idle |

There were also two create refusals, neither of which created a pod or cost
anything: one schema error (CUDA 13.2 is not accepted by the API) and one "no
instances available". Each was reconciled with a pod listing before the next
request.

## 2. Battery reference pilot

### Configuration

| Setting | Value |
|---|---|
| Model and parameter set | PyBaMM 26.8 DFN, OKane2022 unmodified |
| Solver | IDAKLU at rtol 1e-5 |
| Mesh | 20 points per domain |
| Refinement | 40 points per domain and rtol 1e-6 |

### Results

| Measure | Pilot 1 (`8pvvoc80p67k2l`) | Pilot 2 (`3tvflrs1asrzia`) |
|---|---|---|
| Jobs | 12 LHS cases + 4 refined, 40 cycles | 4 refined + 5 normal, 40 cycles (memory-bounded extraction) |
| Normal wall per case | median 100 s (7 workers) | median 88 s (4 workers) |
| Refined wall per case | 439 s (one finished) | 284–311 s |
| Peak memory per worker | 6.3 GB normal, 32 GB refined | 0.94 GB normal, 1.3 GB refined |
| Failures | 3 refined OOM-killed (exit −9); `pilot-0007` segfault (exit −11); all typed `FAILED_INFRA` | none |
| Host driver | 580.159.03 | 580.159.04 |

**Reduced-memory extraction preserves the required outputs.** The fix stores only
the needed variables and keeps only the checkpoint cycles. Four cases solved with
full storage (pilot 1) and with reduced storage on a different A40 host (pilot 2)
agree **bit for bit** on:
- voltage and temperature trajectories;
- capacity at all nine checkpoints;
- the plating margin.

One *diagnostic*, the peak cell temperature over the whole experiment, differs by
0.006 °C in one case. The reduced run computes diagnostics over saved cycles only,
and that diagnostic is not a scored output.

**The segfault is not explained.** `pilot-0007` crashed with exit −11 on pilot 1,
while the pod was near its 50 GB memory limit (7 workers × 6.3 GB, plus 32 GB
refined solves). It completed normally when rerun on pilot 2. That is
*consistent with* a failure under memory pressure, but the cause is **not
proven**. The record stays `FAILED_INFRA` and is not reclassified, and the case
stays in coverage through its rerun record.

### 30-cycle horizon evidence

The table compares matched coarse and refined runs at 30 cycles. Fade is the
capacity loss from cycle 1 to cycle 30.

| Case | Regime | Fade, coarse / refined (mAh) | Abs. discrepancy (mAh) | Plating margin shift (mV) | V RMS / T RMS shift |
|---|---|---|---|---|---|
| pilot-0010 | 37.9 °C, 0.69C | 7.23 / 7.23 | 0.01 | 0.4 | 0.2 mV / 0.004 K |
| pilot-0003 | 11.6 °C, 0.55C | 7.59 / 7.51 | 0.08 | 0.4 | 0.6 mV / 0.004 K |
| pilot-0009 | 7.5 °C, 1.50C | 7.26 / 6.99 | 0.26 | 1.6 | 1.1 mV / 0.026 K |
| pilot-0002 | 10.1 °C, 1.90C | 7.27 / 7.24 | 0.03 | 1.4 | 2.1 mV / 0.084 K |

**Signal sizes** across the 12 pilot cases:

| Signal | Range |
|---|---|
| 30-cycle fade | 5.67–7.59 mAh (case-to-case spread about 1.9 mAh) |
| Plating margin | −0.061 V to +0.038 V; 5 of 12 cases reach plating conditions (margin ≤ 0) |
| Peak temperature | 27.7–51.5 °C |

The largest refinement discrepancy is 0.26 mAh, in the coldest fast-charge case,
against 1.9 mAh of case-to-case spread. The horizon rule (signal above refinement
disagreement in the majority of cases) is met in all 4 of 4 cases.

**The cost rule selects 30 cycles.** 40 cycles would be about 7.6 pod-hours for
about 2200 cases, while 30 cycles is about 5.7.

**Limits of this evidence:**
- Four refinement pairs sample the regimes; they do not bound every case. A
  16-case refinement sample is part of refs A.
- The mesh (not solver tolerance) dominates discrepancy. Tolerance changes moved
  outputs by under 0.02 mAh.

### What the first voltage sample is

At zero terminal current during the opening rest:
- PyBaMM's own open-circuit voltage equals the published OCV table to 1e-15 V.
- The **terminal voltage is 0.003–0.44 mV below it**, and relaxes toward it.

The first sample is therefore a zero-current rest voltage, **not** the
open-circuit voltage. The exact-initial-value premise is withdrawn:
- The `initial_voltage` gate is a bounded-offset probe, with its tolerance set at
  2 × the measured reference offset.
- The recipes' "V(0) = OCV table" is a declared construction choice that carries
  up to 0.44 mV of error.

## 3. Corrections applied before training

| Owner item | Change |
|---|---|
| Clamping | Removed. Recipes no longer clip voltage to [2.5, 4.2] V; the ceiling and floor gates see raw predictions. |
| Construction choices | V(0) from the OCV table and T(0) = T_amb are declared construction choices; passing a gate because of them is not physics evidence. |
| Scoring | Each normalization scale is floored at reference uncertainty (median refinement disagreement), so near-zero spread cannot amplify errors the reference cannot resolve. The equal weights are documented as an engineering choice. |
| Regional regression | Affects eligibility: only `IMPROVEMENT` is promotable; a significant important-region regression blocks promotion (TRADE_OFF or REGRESSION); screening nomination applies the same guard. Equivalence requires the whole interval to sit inside the margin, never mere failure to detect a difference. |
| Secrecy | Roles derived from the public campaign string (TRAIN, PRACTICE, FINAL, VERIFY in refs A) are **offline development evidence**, preserved and not regenerated. New private cases use `carbon.seeding` (`MockContext`/`derive_mock_seed`) from a 32-byte root outside the repository; the public commitment `7ff9e2b2…` is recorded before any private case exists; inputs reach pods only as a committed ciphertext whose key is in the pod environment. |
| Churn | Thread pools are bounded per worker. The CPU quota is read under cgroup v1 and v2. The plan key no longer collides. Pod creation is refused while any pod exists, and an ambiguous create is reconciled first. No broad `pkill`. |

## 4. Reuse audit

Summary of the repository machinery inspected, and what new code remains:

| Need | Existing machinery | Decision |
|---|---|---|
| Final comparison outcomes | `carbon.scoring.development.compare` (dispositions, hard limits, replica envelope) | Its dispositions are mirrored, and the adapter reports both names. Its Burgers-bound 12-case × 3-replica shape and its lack of paired per-case or regional logic mean it cannot take battery evidence without parameterizing a signed owner module, so that is **not** done here. |
| Failure typing | `measurement.enums.MeasurementMaterialState`, `execution.model.ExecutionState` | Reuse the vocabulary (reference failed / non-finite / infra). |
| Measurement | C-05 `measure()` is Burgers-only | New battery measurement is justified. |
| Quarantine | C-10 quarantines whole sources after re-execution disagreement | Not case exposure; the pool's exposure and rotation are new. |
| Freeze before final | `write_once` + digest manifests (`research_final`) | Reuse the pattern for the freeze record. |
| Seeds and commitments | `carbon.seeding` | Reused directly for private cases. |
| Reward simulation | `development_comparison.reward.simulate_synthetic` | Available if reward effects are needed; not re-implemented. |
| Pools, rotation, prediction bank, attack simulations | none | New, experiment-only code in `scripts/dev/exam_design`, separate from validator integration. |

## 5. Photonics: feasibility only

**Measured so far:**
- **The −x source.** fdtdx 0.6.2 returns NaN normalization for a mode source
  travelling −x. Port 3 is therefore excited in the x-mirrored scene. **This is a
  change requiring verification.**
- **Calibration (local, 60 nm).** A straight guide transmits |S31|² = 1.0000 with
  zero crosstalk, and the mirrored excitation returns S13 = S31 exactly. That
  checks normalization and the mirrored-scene plumbing (port-name mapping, phase
  reference planes), but *not* asymmetric-scene correctness.
- **Coarse coupler sums.** At 60 nm, summed port power on the coupler is
  0.54–0.60. That is radiation plus discretization at a deliberately coarse mesh;
  **it is not passivity or reciprocity evidence.**
- **On the A40.** The pilot child has not completed a case in 15 min, with the GPU
  at 0 %. The cause is not established. The child now records JAX's device list
  and per-run progress.

**Allocation:** USD 1.50, on a separate short pod.

**Required measurements:**
- the straight-guide calibration at production resolution;
- a 40/30/20 nm convergence ladder on one coupler case;
- reciprocity |S31 − S13| on the asymmetric coupler, under one normalization and
  phase convention;
- per-run GPU time and memory.

**Stop rule:** if the device placement or convergence cannot be resolved within
the allocation, photonics stays at documented infeasibility for this campaign,
and nothing is inferred from coarse sums.

## 6. Costed remaining run matrix

**The rates used:**
- USD 0.49 /hr, plus 20 GB container disk (about USD 0.003 /hr).
- A 30-cycle battery case at about 66 s, uncontended (scaled from the measured
  88 s at 40 cycles).
- 7 workers on the measured 7.65-CPU quota, which gives about 6.4 cases /min.
- A refined case at about 3× the normal cost.
- Pod boot takes 1–8 min on the measured pods.

| Pod | Content | Jobs | Est. wall | Est. cost |
|---|---|---|---|---|
| X: refs A, remainder (battery only) | TRAIN 400, PRACTICE 200, FINAL 200, VERIFY 200 (public-seed development roles) + remaining refinements | ≈1004 | 2.7 h | USD 1.35 |
| Y: refs B (private) + reconstruction | 6 screening batches × (198 + 2 hidden duplicates), private finalist 200, private verification 200 on CPU; beside them on the GPU, reconstructions on TRAIN v1 (kNN; three recipes × 3 seeds; 2 same-seed repeats) and predictions | 1588 + 13 fits | 4.3 h | USD 2.10 |
| Z: photonic diagnosis | device placement check, straight-guide calibration, 40/30/20 nm ladder on one coupler, reciprocity | ≤ 12 runs | ≤ 1 h | ≤ USD 0.50 (allocation 1.50) |
| Contingency | one failed pod, reruns of `FAILED_INFRA` cases | | | USD 1.50 |
| **Remaining total** | | | | **≈ USD 5.5** |

With about USD 0.8 spent by the time pod X starts, the projected total is about
**USD 6.3 of the USD 20 ceiling**. The stages after reconstruction are CPU-only
and need no rental:
- the learning curve, on PRACTICE (local);
- the batch-size and rotation replay;
- the simulations;
- the freeze;
- verification.

**Admission and stop rules:**
- **Deadline.** Each pod's deadline is its content estimate × 1.5, and admission
  closes 10 min before it.
- **Resume.** Completed records are exported before termination. A resumed pod
  skips them by `case_id` (`skip_case_keys`), so no finished case is paid for
  twice.
- **Throughput floor.** A pod whose measured throughput is under half its
  estimate after its first 20 normal cases is investigated before more work is
  admitted. It is not terminated merely to improve utilization.
- **Scope.** Photonics runs only on pod Z and never shares a pod with battery
  references again, because its CPU use starved battery workers on the shared
  pod.
