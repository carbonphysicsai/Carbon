# Exam-design campaign 1: results

**Owner direction, 2026-09-24.** First bounded exam-design research campaign.

**Status of this evidence:** public/synthetic DEVELOPMENT research.
- **Execution class:** *direct execution inside the pinned study image plus a
  hash-locked wheel overlay; not `validator_launch`; containment from the
  provider's runtime.*
- **Qualification:** nothing here is scientifically, security or production
  qualified.
- **No official action:** no reward, chain or official-exam state was touched.

**Related documents:**
- Specification: `EXAM_DESIGN_CAMPAIGN_SPECIFICATION.md`.
- Pilot and costed matrix: `EXAM_DESIGN_CAMPAIGN_PILOT.md`.
- Evidence: `docs/development/evidence/exam-design-2026-09-24/`.

## Bottom line

- **Battery is the stronger launch candidate**, and the only complete study.
  - **References:** all 2,604 jobs in the main runs (2,588 cases + 16 refinements) solved without a failure.
  - **Gates:** every authored fault is rejected by its own gate, and correct
    predictions of plating and hot operating conditions are never failed.
  - **Frozen rule:** it promoted a real improvement, blocked a regression, a
    regional regression and a memorized-screening candidate, and did not promote
    an equal-quality control. Every pre-registered criterion passed on 200 fresh
    private verification cases.
- **Recommended settings:**
  - TRAIN v1 of 400 cases;
  - screening batches of **100** parent cases, 3 active;
  - rotation after **3** admitted submissions;
  - a 5.7 % equivalence margin;
  - only `IMPROVEMENT` promotable, with important-region regressions blocking.
- **Photonics remains at feasibility.**
  - **Two execution faults found and fixed:** the overlay dropped the bundled
    ffmpeg binary's execute bit, and the image defaults JAX to CPU.
  - **Normalization calibration:** local straight-guide calibration is exact.
  - **GPU run:** reciprocity holds to 0.4 % at 20 nm, but coupled power and
    phase are not converged, and a mode-sign phase ambiguity is unresolved
    (§9). Photonics is not expanded.
- **Correction to earlier statements.** The battery reconstructions ran on the
  A40 pod's **CPU backend**: the image selects CPU unless `JAX_PLATFORMS` is set,
  and that was found late. Their results, the freeze and the verification are
  internally consistent. A GPU re-reconstruction is reported separately in §5.
- **Spend:** USD 4.80 billed (balance 22.24 → 17.44) against the USD 20 ceiling,
  well inside the USD 4 pilot allocation plus the costed matrix. USD 0.23 went
  to three wholly discarded pods; the others yielded retained evidence,
  including diagnosed failures.

## 1. What ran

### Pods

| Pod | Work | Minutes | Cost (est.) |
|---|---|---|---|
| `8pvvoc80p67k2l` | battery pilot 1 (12 + 4 refined, 40 cycles) | 14.3 | 0.118 |
| `3tvflrs1asrzia` | pilot 2 (battery refinements; photonic import fault) | 16.5 | 0.135 |
| `9qhyoniu04hdte` | superseded before work | 0.6 | 0.005 |
| `d8jfjlw2bucnoz` | aborted: plan-key collision | 13.9 | 0.114 |
| `c45fer91e5645o` | aborted: thread thrash on 96 visible cores | 13.9 | 0.114 |
| `6dto4gg26hes1y` | 12 refined TRAIN cases; photonic child starved battery | 25.4 | 0.209 |
| `xtkoy5q53e8uao` | refs A: TRAIN 400, PRACTICE 200, public-seed FINAL/VERIFY 200 + 200, 4 refined | 175.7 | 1.443 |
| `gvbul5monct3nl` | refs B: private screening 6 × 198, `pfinal` 200, `pverify` 200 + 19 reconstructions | 282.0 | 2.316 |
| `lsj6gwe29se5wg` | photonic diagnosis, found on the CPU backend and stopped | 6.1 | 0.050 |
| `n6lrqwc5hik1hn` | GPU attempt: `ptxas` could not write the image's `/scratch/tmp` | 5.4 | 0.044 |
| `ripykoc913imwx` | GPU re-reconstruction (19 fits); photonic mode solver needed a CPU device | 6.3 | 0.051 |
| `1s9yhraivqlorz` | photonic diagnosis on the GPU, 6 of 6 | 25.2 | 0.207 |

Every pod was terminated with verification, and no volume was ever created.

### Reference solves

**Battery reference:**
- PyBaMM 26.8 DFN with OKane2022, unmodified.
- SEI and partially reversible plating, lumped thermal.
- Two-stage CC charge, CV, rest, 1C discharge.
- **30 cycles**, with capacity at cycles 1, 10, 20 and 30.
- Voltage and temperature every 30 s over the first hour.
- A plating margin (the minimum plating overpotential during the cycle-1 charge).

**Outcome:**
- **All 2,604 main-run jobs `OK`** (2,588 cases + 16 refinement pairs), with no failures.
- A normal case takes a median **71 s** (p90 77 s) per worker, at under 1 GB.
- Every reference passes the gates it anchors, so no case had to be withdrawn.

### Data roles

| Role | Cases | Status |
|---|---|---|
| TRAIN v1 | 400 | public, fixed |
| PRACTICE | 200 | public |
| `final`, `verify` | 200 + 200 | **offline development evidence**: seeds derived from a public string |
| `pscreen-B00…B05` | 6 × (198 + 2 hidden duplicates) | private screening batches |
| `pfinal` | 200 | private fresh finalist cases |
| `pverify` | 200 | private verification cases |

The private roles come from a root outside the repository, via
`carbon.seeding`, with public commitment `7ff9e2b2…`. They reached pods only as
an encrypted job list.

## 2. How much public training data is a useful starting point?

The learning curve evaluates on PRACTICE (200 cases), locally on CPU, with a
diagnostic label. The score is the case error, lower is better; 1.0 means
"predicts no better than the TRAIN mean".

| TRAIN cases | kNN | Competent MLP (2 seeds) | MLP with PCA heads |
|---|---|---|---|
| 25 | 0.384 | 0.236 / 0.234 | 0.263 / 0.259 |
| 50 | 0.324 | 0.203 / 0.192 | 0.241 / 0.224 |
| 100 | 0.246 | 0.128 / 0.137 | 0.187 / 0.188 |
| 200 | 0.207 | 0.081 / 0.086 | 0.151 / 0.145 |
| 400 | 0.172 | 0.054 / 0.057 | 0.088 / 0.090 |

**Recommendation: TRAIN v1 = 400.**
- **The curve has not flattened.** The competent recipe still improves 34 %
  from 200 to 400.
- **400 cases are cheap:** about USD 0.58 of A40 time.

**Policy:**
- One fixed TRAIN per challenge version.
- PRACTICE stays public.
- Retired screening batches enter TRAIN only through a named version update
  (`exam.TrainVersions`); none was published in this campaign.
- A later study should extend the curve beyond 400 before fixing a production
  version.

## 3. Gates: behaviour, failures and coverage gaps

Tolerances come from reference evidence only (600 calibration references).

| Gate | Tolerance |
|---|---|
| `initial_voltage` | ±0.99 mV. The reference's first sample is a zero-current rest voltage up to 0.49 mV below OCV, so this is a bounded-offset probe, not an exact constraint. |
| `voltage_ceiling`, `voltage_floor` | 32 float32 ulp (the reference never overshoots) |
| `initial_temperature` | 32 ulp |
| `capacity_bound` | 5.83 Ah (parameter set) |
| `paired_repeat` | 32 ulp on hidden duplicates |

### On the three screening batches (600 cases), prediction set `mlp-s0`

| Control (authored unless noted) | Expected gate | Result |
|---|---|---|
| Reference as prediction (oracle), including plating and >55 °C cases | none | eligible, score 0 |
| NaN / wrong shape | `schema_finite` | 600 / 600 fail |
| +20 mV on the 4.2 V hold | `voltage_ceiling` | 600 / 600 fail |
| +5 mV at t = 0 | `initial_voltage` | 600 / 600 fail |
| +0.5 °C at t = 0 | `initial_temperature` | 600 / 600 fail |
| capacity above the bound | `capacity_bound` | 600 / 600 fail |
| fresh noise per call | `paired_repeat` | 12 / 12 duplicates fail; the noise also crosses 4.2 V (376 ceiling fails) |
| 60 s time shift | none (soft) | eligible, score 0.111 against 0.052: caught by the score only |
| **trained** MLP with an unconstrained voltage head (`mlp_raw`) | `voltage_ceiling` | 350 / 600 fail. Its soft score (0.058) looks competitive, but it predicts impossible voltages. |

**Not gated, by design:**
- **Heat sign.** Heat is signed, so there is no non-negative-heat gate.
- **Sub-ambient temperature.** Entropic cooling can take the cell below ambient,
  so there is no temperature ≥ ambient gate.
- **Unsafe-limit crossings.** Correct plating and high-temperature predictions are
  scored, never failed.
- **Charge conservation.** Current is not an output, so conservation cannot be
  established from the outputs.
- **Monotone capacity.** The reference itself is not monotone.

### Coverage gaps

1. **Nondeterminism is only checkable where hidden duplicates exist.** The
   verification set carried none, so the nondeterministic fault there was caught
   only incidentally, by the ceiling. **Every private evaluation set should carry
   duplicates.**
2. **The voltage gates pass by construction.** They are protocol-control gates,
   and the recipes pass them only through a declared construction choice (a soft
   ceiling head). Passing them is not physics evidence.
3. **No gate tests the plating margin's physics.** Its sign is scored, not
   checked.
4. **Refinement uncertainty is material for plating.** The median is 0.04 of the
   TRAIN spread, so score differences below about 0.015 case error sit inside
   reference uncertainty.

## 4. Screening versus fresh finalist outcomes

### Rank agreement

Across 16 trained models, screening-pool rank agreed with rank on the private
fresh `pfinal` cases:

| Batch size | Kendall τ |
|---|---|
| 50 | 0.88 |
| 100 | **0.93** |
| 200 | 0.92 |

### The exam loop, replayed

The replay covers 9 settings: batch size 50, 100 or 200, crossed with rotation
after 1, 3 or 10 submissions. Each setting runs 18 scripted submissions,
including three authored "pool-leak" candidates that memorize the current
screening references. In each:
- screening feeds a regional-guarded nomination;
- nominees face the frozen final comparison on `pfinal`;
- truth labels come from about 1,800 development cases.

| Decision (truth) | Outcome across the 9 settings |
|---|---|
| Real improvement `mlp` over `mlp_half` (−36.5 %) | promoted 9 / 9 |
| Pool-leak memorization (truth: equivalent) | nominated 27 / 27 (screening is fooled); **promoted 0 / 27**; the fresh final comparison catches it |
| Regression `mlp_plus` (+62 %) | never nominated |
| Regional regression `mlp_localized` (overall +4.4 %, important region worse) | never nominated |
| Equal-quality reseeds | never nominated |
| Marginal improvement `mlp_ens3` (−6.2 %, at the 5.7 % margin) | promoted 4 / 9; `INSUFFICIENT_EVIDENCE` 1 / 9; not nominated 4 / 9 (a **missed** improvement) |
| **False promotions** | **0** |

**Interpretation:**
- Screening ranks well but is fooled by memorized references.
- The fresh finalist comparison is what makes promotion safe.
- Improvements at about 1× the margin are found about half the time. That is the
  price of the 5.7 % margin, which exists because reseeding alone moves scores by
  up to 2.9 %.

### Verification

The rule, criteria and code digests were frozen in `freeze.json`, commit
`a0318d9`. The 200 private `pverify` cases were then opened: **all 7
pre-registered criteria passed** (`verification.json`).

| Criterion | Outcome |
|---|---|
| V1 equal-quality control | `INSUFFICIENT_EVIDENCE`, not promoted. 200 cases cannot establish equivalence at 5.7 %, and the rule does not claim it. |
| V2 authored faults | every fault fired its gate (nondeterminism caveat above) |
| V3 real improvement | `IMPROVEMENT` (Δ −0.035, 95 % CI [−0.040, −0.030]) |
| V4 regression | `REGRESSION` |
| V5 localized control | `REGRESSION`, **blocked by the important region** (CI [+0.001, +0.010]) while overall was unresolved |
| V6 memorized screening | `NO_IMPROVEMENT` |
| V7 oracle | passes every gate |
| R1 small ensemble (report only) | `IMPROVEMENT` (−8 %) |

**What this does not show:**
- A small physical campaign cannot establish a rare false-promotion rate. The
  loop saw 0 false promotions in 28 finals whose challenger was not truly
  better (27 pool leaks, 1 unclear). The upper 95 % bound (rule of three) is
  about 11 %, and it holds for these scripted candidates only.
- The candidates are not adaptive miners.

## 5. Reconstruction variability

**Backend.** These are the **CPU-backend** reconstructions on the A40 host (see
the bottom line), with the pinned XLA configuration.

| Recipe | Seed-to-seed relative SD (large-sample score) |
|---|---|
| mlp | 2.2 % |
| mlp_ens3 | 1.8 % |
| mlp_plus | 2.6 % |
| mlp_localized | 2.8 % |
| mlp_half | about 1 % |

**Same-seed repeats** of `mlp` and `mlp_plus` are **bit-identical**, in both
parameters and predictions.

**The equivalence margin** is 2 × the largest seed SD, which is **5.7 %**.

**Resampling of screening pools** separated two equal-quality seeds beyond the
margin in:

| Pool (3 × batch) | Separated |
|---|---|
| 150 | 9.6 % |
| 300 | 3.5 % |
| 600 | 0.5 % |

Authored improvements of 10 % and 20 % were always detected; 2 % and 5 % were
never separated.

**Three seeds are diagnostic, not a reliability guarantee.**

**GPU re-reconstruction** (pod `ripykoc913imwx`; same 19 fits,
`JAX_PLATFORMS=cuda`, pinned XLA; recorded in `backend_comparison.json`):

- **Same-seed repeats are bit-identical on the GPU** too, for `mlp` and
  `mlp_plus`: parameters and predictions.
- **GPU and CPU reconstructions are *not* bit-identical.** Their parameters
  differ, and single-sample voltage predictions differ by up to 20 mV for some
  models.
- **The exam does not notice the difference.**
  - Fresh-case scores agree within **0.4 %**.
  - Eligibility is unchanged (`mlp_raw` is still rejected).
  - **Every frozen verification decision is identical** on both backends.
- **So the backend changes the numerics, not the exam's decisions, in this
  campaign.** A validator must still pin and record the backend, because the
  prediction bytes differ.
- **Cost:** GPU fits take **3–12 s**, against 41–106 s on the CPU backend.

## 6. Rotation behaviour

**The attack.** A scripted attacker mixes two equal-quality seed predictions,
case by case, keeping each mix only if the aggregate pool score improves. Only
the aggregate score is fed back, over 30 submissions.

Mean pool-score gain as a fraction of the pool score (the 90th-percentile gain is
in `analysis.json`):

| Batch | Rotate after 1 | Rotate after 3 | Rotate after 10 |
|---|---|---|---|
| 50 | 0.3 % | 0.5 % | 1.0 % |
| 100 | 0.1 % | 0.3 % | 0.3 % |
| 200 | 0.0 % | 0.1 % | 0.2 % |

All of these sit far below the 5.7 % margin. Memorization (pool leak) is the
stronger threat, and the fresh finalist comparison, not rotation, is what stops
it.

**Recommendation: batch 100, rotate after 3.** Rotation is set conservatively for
adaptive agents, which were not measured (§8).

**Exposure into time**, from traffic assumptions rather than measurement:

| Submissions per day | Rotation interval | Reference build per rotation |
|---|---|---|
| 10 | 7.2 h | 100 cases, about 17 min on one A40 pod |
| 50 | 1.4 h | same |

**Accelerated replay does not establish a real-world interval.**

## 7. Cost

These are measured on one A40 Secure pod at USD 0.49/hr, 7.65 CPUs.

| Item | Measured | Cost |
|---|---|---|
| Reference case (30 cycles) | 71 s median per worker, 7 workers; 1,004 cases in 176 pod-min including boot | **USD 0.0014 / case** |
| Refined reference | about 240 s | about USD 0.005 |
| Reconstruction, GPU backend (one recipe) | **3–12 s** (median about 5 s) on the A40 | **about USD 0.001** at the full pod rate |
| Reconstruction, CPU backend (the frozen results) | 41–106 s (median 80 s) while sharing the pod | about USD 0.011 |
| Inference, stored model on a new batch | about 5 ms per 200 cases | negligible |
| Gates + score | 0.04 s per 600 cases (local) | negligible |
| **Screening one submission** (batch 100, pool 300) | one GPU reconstruction + inference + scoring | **≈ USD 0.001** (USD 0.011 on the CPU backend) |
| **Batch build** | 100 references | **USD 0.14**, amortized over 3 submissions = USD 0.047 |
| **Finalist comparison** | 2 reconstructions + 200 fresh references + inference | **≈ USD 0.29**, dominated by the fresh references |

At the chosen setting, 6 of 18 scripted submissions were nominated, and 3 of
those were adversarial pool leaks.

### Submission fee estimate

These are traffic assumptions, not measurements.

**Fee components:**
- screening: USD 0.001 on the GPU backend;
- batch amortization: USD 0.047;
- nomination probability × finalist cost;
- pod overhead (boot, idle, failed jobs): +50 %.

| Assumed nomination rate | Estimated fee |
|---|---|
| 10 % | ≈ **USD 0.12** |
| 33 % (as in this replay) | ≈ **USD 0.22** |

This covers compute only, with no operator margin, and fee policy is
owner-reserved. **Fees never enter the score.**

## 8. What did not run, and why

- **Burgers control.** The per-case Burgers development evidence is private
  (`$PRIVATE_CARBON_ROOT`) and absent from this container. No new Burgers runs
  were commissioned.
- **Adaptive agents.** The harness is prepared (`adaptive_agent.py`) and refuses
  without an owner-authorized model-provider budget. None exists, so it is
  **unrun**, and the scripted candidates are not autonomous miners.
- **Photonics** was stopped at feasibility; see §9.

## 9. GPU re-reconstruction and photonic feasibility

### Photonics: feasibility only, not expanded

**Execution faults, found and fixed.** Five faults stood between the photonic
reference and a GPU:
1. The overlay dropped the bundled ffmpeg's execute bit.
2. The image defaults JAX to the CPU.
3. The image's `TMPDIR` (`/scratch/tmp`) is unwritable, which broke `ptxas`.
4. fdtdx's mode solver needs a CPU device beside the GPU:
   `JAX_PLATFORMS=cuda,cpu`.
5. fdtdx returns NaN normalization for −x sources. Port 3 is therefore excited
   in the mirrored scene; the device is asymmetric, so reciprocity is a real
   test.

**Diagnosis on the A40** (pod `1s9yhraivqlorz`: 6 of 6 runs, 1.55 µm unless
noted; `photonic-diagnostic/`):

| Check | Result |
|---|---|
| Straight-guide normalization, 30 nm | \|S31\|² = **0.9996**, zero crosstalk, S31 = S13 exactly |
| Summed port power | 0.96–0.98 at every resolution, never above 1 |
| Reciprocity \|S31 − S13\|/\|S31\| on the asymmetric coupler | 0.97 % (40 nm), 0.47 % (30 nm), **0.42 %** (20 nm); 0.14–0.78 % across 1.50–1.60 µm at 30 nm |
| Coupled power \|S41\|² | 0.052 / 0.070 / 0.060 at 40 / 30 / 20 nm: **not converged** (about 15 % of the coupled fraction) |
| Absolute phase of S31 | 2.37 / 2.09 / 1.11 rad: **not converged** |
| Relative phase arg(S41/S31) | −1.66 / **+1.53** / −1.63 rad: flips sign across resolutions, a π **mode-sign ambiguity** |
| Cost per run | 30 nm: about 76 s, 4 GB; 20 nm: about 265 s, 10.9 GB |

**What the diagnosis does not establish:**
- Summed port power staying below 1 is **not** a validated passivity result.
  Radiation is not separately accounted for, and the two excitations differ by
  about 0.8 %.
- Reciprocity agreeing to about 0.4 % supports the mirrored-excitation
  implementation within numerical tolerance. It does not validate a reciprocity
  gate tolerance, which would need a convergence study.

**Why it stops here.** A complex port response is **not well defined** until the
mode-sign phase convention is fixed. Coupled-power magnitudes are uncertain by
about 15 % even at 20 nm, where one 5-wavelength parent case costs about
USD 0.36, so a 100-case screening batch alone would cost about USD 36.
Photonics therefore stays at documented feasibility for this campaign, with no
2D substitute. Before any photonic exam, three things are needed:
- a fixed mode-sign and phase convention;
- a convergence study to 10–15 nm, or a mode-expansion reference;
- a radiation or absorption account to support a passivity tolerance.

## 10. What can enter validator shadow mode now

- **Battery reference generation.** The pinned DFN, typed failures, the memory
  bound, the resume logic and the cost model are all measured, and results were
  bit-reproducible across A40 hosts.
- **Gates and score as a shadow judge.** The published gates, the score with
  reference-uncertainty floors, and the important region can score shadow
  submissions **without affecting rewards**.
- **Screening machinery.** Pools, rotation, pool versions, prediction bank and
  nomination can run over real submission traffic, in shadow, to measure real
  exposure and adaptive behaviour.
- **The final-comparison rule**, as a shadow decision recorded beside, not
  instead of, the existing DEVELOPMENT comparison (its dispositions are mapped).

## 11. What still prevents reward-bearing use

1. **Owner decisions.** No scientific, security or production qualification
   exists, and none is claimed. Thresholds (important region, margin, weights,
   tolerances) are provisional development choices, and production values are
   owner-reserved.
2. **Isolation.** Execution was provider-contained direct execution, not
   `validator_launch`; the isolation acceptance is still owed.
3. **Secrecy.** The private root lived in a container home directory, and its
   revealed-after-use protocol is not yet an official seed service.
4. **Backend pinning.** The frozen results used the CPU backend. GPU reconstruction reproduces every decision, but not the bytes (§5), so a validator must pin and record the backend.
5. **Adaptive miners** are unmeasured. Rare-event false-promotion rates cannot be
   bounded by a campaign this size.
6. **Duplicates in every private set.** Every private evaluation set needs hidden
   duplicates for the nondeterminism gate.
7. **Real cells.** Agreement is with the specified PyBaMM model, not with
   real-cell lifetime or safety.

## 12. Next implementation step

**Wire the battery exam into validator shadow mode as a separate adapter:**
- a shadow scorer that consumes submissions through the existing development
  submission path;
- the published gates and score, from `scripts/dev/exam_design` promoted into a
  reviewed module;
- a private-root seed service replacing the container-local root;
- GPU reconstruction with `JAX_PLATFORMS=cuda` recorded per run;
- hidden duplicates in every private set;
- exposure and nomination statistics logged per pool version.

No reward path is touched until the owner decisions in §11 are made.

## Operator commands

```bash
python -m scripts.dev.exam_design.runpod.pod_control status          # balance, pods, committed spend, cap
python -m scripts.dev.exam_design.runpod.pod_control dispatch ...    # see EXAM_DESIGN_CAMPAIGN_PILOT.md
python -m scripts.dev.exam_design.runpod.pod_control poll | fetch DEST | terminate | reconcile
python -m scripts.dev.exam_design.campaign prepare | learning-curve | train-plan --n 400 | analyze
python -m scripts.dev.exam_design.campaign freeze --batch-size 100 --rotate-after 3 --rationale "..."
python -m scripts.dev.exam_design.campaign verify | retain | photonic
```

A resumed pod skips completed cases (`--skip-from records.jsonl`). The API key
is read from `~/.runpod/api_key` only, and the private root and job keys from
`~/.carbon-exam-design/`.
