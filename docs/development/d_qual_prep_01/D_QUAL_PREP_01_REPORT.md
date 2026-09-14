# D-QUAL-PREP-01 reference and measurement qualification-readiness report

**Date:** 2026-09-14

**Scope:** detached public DEVELOPMENT evidence only

**Scientific source revision:** `ed6047d03cf60db6ce52f03e63040d95c1ea78e4`

**Frozen protocol digest:** `sha256:ff2a730838fad9ae0b3148ed149ecd6021cb5ae0d381ca3f3f71c69871e2e99d`

**Final recommendation:** `WAIT_FOR_D02_GENERATOR_CONFORMANCE`

## Outcome

The frozen twelve-cell EVAL sample produced complete diagnostic histories for
the accepted Cole-Hopf primary and finite-volume Rusanov/SSPRK3 witness. All
96 same-method study states completed: four primary quadrature grids and four
witness spatial grids for each case. The 12 accepted three-role C-04 runs and
12 additional witness requested-time-partition runs also completed.

This is useful owner-review evidence, not scientific qualification. D-03 and
D-04 each remain `MORE_PUBLIC_EVIDENCE_NEEDED`. D-05 is `BLOCKED_INPUT`: D-02
is unselected and unstarted, and the accepted C-05 record does not retain the
two-recipe 3-replica-by-12-case result matrix or a reference-settings
perturbation matrix from which numerical floors could be estimated.

GOAL-WORKBENCH-04 commit
`0ea0ad8116ae4d912e866d11c52d6775a37d9813` is not an ancestor of the observed
main revision. No importable workbench projection was emitted; the explicit
projection status is `BLOCKED_INPUT`.

## Evidence taxonomy

| Class | Material in this packet |
|---|---|
| External scientific result | None introduced or claimed. |
| Carbon hypothesis | The accepted primary, witness and development cross-check are expected to provide mutually informative numerical evidence over the declared fixed-viscosity Burgers envelope. |
| Proposed Carbon experiment | Missing alternate-precision/transform, controlled CFL refinement, limiting-case, failure-boundary, D-02 conformance and C-05 measurement-matrix campaigns. |
| Qualified Carbon evidence | None. All observations remain public DEVELOPMENT qualification-candidate evidence. |

## Frozen campaign

The protocol reuses the smallest accepted C-04/C-05 sample: EVAL cells 0-11,
ordinal 0, build 0. It spans the three registered source shape families and
four Reynolds strata. Each case uses 64 periodic output points and times
`0`, `0.1 tc`, and `0.25 tc`.

The primary history evaluates 512, 1024, 2048 and 4096 Fourier quadrature
points without changing the accepted runtime. The witness history evaluates
128, 256, 512 and 1024 conservative internal cells at the accepted CFL 0.35.
A separate five-target request probes sensitivity to output-time partitioning;
it is not represented as controlled time refinement. Every supported and
failed slot is retained. No difficult case was excluded.

## D-03 primary-reference readiness

| Observation across 12 cases | Minimum | Maximum | Disposition |
|---|---:|---:|---|
| Initial-condition recovery, max absolute | 4.005129561335252e-14 | 7.929642895782019e-08 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Analytic periodic closure, absolute | 0 | 9.159339953157541e-16 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Accepted 1024 to 2048 quadrature change, max absolute | 1.0430545316353346e-13 | 1.6311709215982573e-07 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Primary to ETDRK4 discrepancy, max absolute | 4.96269692007445e-14 | 2.822468077035012e-07 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Minimum stabilized Cole-Hopf phi | 6.402823860950785e-09 | 4.386356016694295e-01 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Primary mean drift over all tested grids, max absolute | 2.7755575615628914e-17 | 6.74623762610127e-07 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |

The full consecutive quadrature curve is:

| Transition | Minimum change | Maximum change |
|---|---:|---:|
| 512 to 1024 | 5.5788706987414116e-14 | 7.608350482968262e-08 |
| 1024 to 2048 | 1.0430545316353346e-13 | 1.6311709215982573e-07 |
| 2048 to 4096 | 1.7709445021552028e-13 | 2.0598144549049957e-07 |

Cell 7 (`localized_packet`, Reynolds stratum 3, observed Reynolds number
6.541859968297311) has both the smallest retained phi and the largest finest
quadrature change. The change is not monotonically decreasing at the finest
transition. That does not establish failure, but it prevents this packet from
presenting a converged error floor.

What the evidence can support: exact-case review of initial recovery,
periodicity, stabilized-phi conditioning, same-method quadrature sensitivity,
mean behavior and a separate ETDRK4 discrepancy. What it cannot support:
alternate-precision sensitivity, an alternate Cole-Hopf transform,
owner-approved applicability/conditioning boundaries, valid limiting cases,
an empirical instability boundary, an uncertainty model or a scientific
acceptance limit.

## D-04 witness readiness

| Observation across 12 cases | Minimum | Maximum | Disposition |
|---|---:|---:|---|
| Accepted witness 256 to 512 spatial change, max absolute | 3.3937066058159493e-04 | 2.4794353361268007e-02 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Witness mean drift at accepted setting, max absolute | 6.220359533015696e-09 | 4.116953144081559e-05 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Primary-to-witness discrepancy, max absolute | 6.924803093417975e-04 | 5.1533975708916824e-02 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |
| Requested-time-partition sensitivity at shared times | 6.3257177274067544e-12 | 1.7902626880950123e-08 | `EVIDENCE_READY_FOR_HUMAN_REVIEW` |

The spatial-refinement curve is:

| Transition | Minimum change | Maximum change |
|---|---:|---:|
| 128 to 256 | 6.489364878253245e-04 | 4.5165075365286134e-02 |
| 256 to 512 | 3.3937066058159493e-04 | 2.4794353361268007e-02 |
| 512 to 1024 | 1.748406532783023e-04 | 1.3095769412061475e-02 |

All tested cases show decreasing consecutive spatial changes, but no rate or
acceptance rule is inferred. Cell 6 (`localized_packet`, Reynolds stratum 2)
has the largest 512-to-1024 change. The 1024-cell runs required 407 to 12,016
SSPRK3 steps across the sample. No nonconvergence was observed, so the
nonconvergence boundary remains unmeasured.

The independence matrix records ten dimensions without a synthetic percentage.
Mathematical formulation and code are `PARTIALLY_SHARED`; discretization, time
integration and representation are `DISTINCT`; libraries, generator,
environment and validation data are `SHARED`; personnel is `UNKNOWN`.

What the evidence can support: case-level spatial refinement, conservation,
same-case discrepancy, fixed-setting steps and requested-time-partition
sensitivity. What it cannot support: controlled CFL/time refinement, a
nonconvergence boundary, an independently owned personnel record, a qualified
uncertainty estimate, or an accepted primary/witness discrepancy rule.

## D-05 measurement readiness

| Observable | Floor candidate | Reference-setting sensitivity | Replica/case variation | Rank reversals | Current disposition |
|---|---|---|---|---|---|
| `field_phase_rms` | unavailable | unavailable | unavailable | unavailable | `BLOCKED_INPUT` |
| `maximum_compression` | unavailable | unavailable | unavailable | unavailable | `BLOCKED_INPUT` |
| `peak_dissipation` | unavailable | unavailable | unavailable | unavailable | `BLOCKED_INPUT` |
| `energy_half_time` | unavailable; right-censor rule exists | unavailable | unavailable | unavailable | `BLOCKED_INPUT` |

The accepted C-05 harness can compute within-case reconstruction standard
deviation, across-case standard deviation after replica means, and paired rank
reversals when supplied the exact 72-result matrix. The repository retains the
frozen campaign design and accepted harness, not that numerical matrix. It also
contains no paired measurement matrix across primary reference resolutions or
settings. Consequently, none of the requested floor, sensitivity, uncertainty,
rank reversal or minimum-distinguishable-difference values is estimable from
retained accepted records. Zero observed error would remain
`UNRESOLVED_NO_QUALIFIED_LIMIT` under the C-05 contract.

No observed minimum is promoted to a threshold. No mandatory limit, soft
threshold, alpha, repeat count, stopping rule, acceptable instability,
production tolerance or ScorePack weight is selected.

## Generator dependency

| Population | Current state |
|---|---|
| Public DEVELOPMENT source population | Defined, not qualified: 72 TRAIN, 48 EVAL, 120 STRESS. |
| Realized readiness sample | 12 EVAL cases: cells 0-11, ordinal 0. |
| Qualified target population | Undefined and unqualified; `BLOCKED_INPUT`. |
| Stress/diagnostic population | 120 public STRESS cases exist; zero are represented in the accepted C-04/C-05 campaigns. |

C-07 has accepted bounded DEVELOPMENT orchestration. D-02 nevertheless remains
`future_reserved`, unselected and unstarted. Missing D-02 evidence is named in
`generator_dependency.json`: support/exclusions; marginal, joint and
conditional conformance; stratum mass/coverage; duplicates; retry/censoring;
intended-versus-realized population; and exact manifests, seeds, exclusions,
failures, weights and coverage. D-05 must remain blocked until this evidence is
supplied and reviewed.

## Authority, Workbench and CPES boundaries

No Wave D ticket was selected, activated or completed. No reference,
measurement or scientific qualification was minted. `ScoreInput` is absent;
score, protected, reward, network, production and LIVE eligibility remain
false. Production reference and measurement runtime semantics and the active
Wave C selection are unchanged. The controlling board continues to name C-08's
bounded authenticated DEVELOPMENT composition as the active selection; this
detached study neither edits nor advances that state.

Because GOAL-WORKBENCH-04 is not merged, this campaign emits only a
non-importable projection-status record. A later eligible projection may be
typed only as `DEVELOPMENT_QUALIFICATION_CANDIDATE_EVIDENCE`, must require a
human scientific decision, and cannot mint authority.

CPES is unchanged. Variant A remains the DEVELOPMENT baseline; Variant B
remains conditional research. AT-09, AT-16, AT-19, AT-22 and AT-30 remain
unresolved. Reference evidence does not clear secrecy, lineage,
honest-execution or adaptive-leakage blockers.

## Reproduction and verification

The numerical run used CPython 3.11.11, NumPy 2.4.6 on
`macOS-15.6-arm64-arm-64bit`. It matched the C-04 dependency identity
`sha256:914e6e0aab72edd55854fbfd25ccce7a05d271da4bde3e6a88a49609c07d65a0`,
but is explicitly classified as `NATIVE_MACOS_DIAGNOSTIC`, not canonical Linux
execution.

From the repository root:

```bash
env PYTHONPATH=. /private/tmp/carbon-goal04-venv/bin/python docs/development/d_qual_prep_01/run_campaign.py
env PYTHONPATH=. /private/tmp/carbon-goal04-venv/bin/python -m pytest -q tests/cpu/test_d_qual_prep_01.py
```

The tests cover exact source/case/environment identity, retained failure slots,
absence of thresholds and qualification, matrix completeness, case-level
histories, D-02 blocking, DEVELOPMENT authority boundaries, Workbench
non-authority and byte-identical replay.

Observed focused results:

- D-QUAL-PREP-01: 8 passed.
- D-QUAL-PREP-01 plus accepted C-04/C-05 CPU suites: 56 passed.
- C-04/C-05/B-04/B-05 authority-boundary suites: 32 passed.
- Black 26.5.1 and Ruff 0.16.3: passed for both added Python files.
- Delivery hygiene: passed; change classifier: `RUNTIME_FULL`.

A broader native diagnostic first produced 5,379 passed, 34 skipped, 15 failed
and 2 errors because the temporary environment lacked the installed Carbon
distribution and pinned wheel-build tools. After installing those exact pinned
inputs, all 92 directly affected tests passed. A clean fail-fast rerun then
exposed one separate existing macOS/pyenv no-dependency-wheel isolation failure
after 384 passes: its disposable venv reported a successful wheel install but
could not import `carbon`. That host-specific full-suite result is retained as
non-acceptance diagnostic evidence; it does not alter the green focused results
or confer canonical Linux acceptance.
