# Motor and battery v3 cheap-comparator measurements

**BASELINE-AGREEMENT-01 / DEVELOPMENT.** Implements the canonical
[#864 baseline specifications](../../challenge_pipeline/cheap-baselines/README.md)
under the owner's 2026-10-09 fitting/measurement instruction. No reference
solve, paid dispatch, hidden/AX42 access, or official evaluation occurred.
This is a partial evidence return, not a V4 pass/fail or Challenge admission.

## Buyer question and current finding

Does an inexpensive existing method make the same supported design decisions
as Carbon, at lower total cost? Exact covered-bank lookup and held-out
prediction are different comparisons. A missing Carbon arm, unresolved
reference winner, or unsupported held-out point cannot establish agreement.

- **Motor:** exact replay covers 44 candidates and 20 questions. All 20
  canonical reference comparisons remain unresolved. The producer's proposed
  settlement simulation has 16 feasible questions and four NONE_FEASIBLE
  questions, but that simulation is not the export's accepted truth. Full-curve
  Gaussian/RBF code exists and is toy-tested; measurement is **HOLD** because
  the export contains ordinal design IDs and summary reductions, not physical
  coordinates and signed torque/cogging curves.
- **Battery v3:** 493 unique action/band rows, 226 distinct protocols, 25
  five-band questions. Whole-protocol holdout covers 276 rows (56.0%); whole-band
  holdout covers 108 (21.9%). Both conservative policies abstain from a
  complete five-band map on every question. All 25 reference decisions remain
  unresolved, so exact-pick agreement and regret are **null**, not zero or 100%.
- **V4 is not settled.** Closed-bank lookup is a real incumbent, not an
  independent predictive success. These sparse interpolation holdouts do not
  demonstrate a usable complete-map replacement, nor prove Carbon is better.
  No Carbon prediction/cost arm was supplied. Test Lead/owner retain disposition.

## Pins and support

The owner-designated WSL development files were read directly; no broader
host/home inventory or reference execution was needed. Byte identities:

| Input | SHA256 | Validated producer export digest |
| --- | --- | --- |
| motor-export.json | b6fe2086d95744efc64d2058f148622e1904a8be3d4df167fdd0cc15a5cbed0d | sha256:720e93a2d6bf4540119fa46c3d47478811a7f412dc80f6627ef228a6c5758569 |
| battery-v3-export.json | 31463626c13549916feffa4ef9917f520e1437eb24dc08c8c402b6926e4717d4 | sha256:2ec4da3ccfc358d412bd38648f4ca9fb6a010e838964a1e4e3f65a4a2b5f041d |

Public acquisition notes were inspected at
`claude/motor-feasibility-02@66ea509888e4ef0f5ac08750554db744b56b92bf`,
including `battery-feasibility-02/tier4-boundary.json`, its registry,
`v3-panel-export.json`, and the motor panel/registry/S3 notes. That branch's
battery export note pins different bytes/digest from the supplied shared file;
this report binds **only the bytes above**, not the older note or unreturned
later refinement. The public `v3-panel-export.json` is a provenance note, not
the solved panel itself.

Battery support: SOC 10% only; bands 5/15/25/35/40 C contain 80/42/147/147/77
rows. Cooling is only x1/x2/x4. Nine historical rows have a C-rate off the
prospective 0.01-C lattice; they remain clearly historical diagnostic support,
not adopted actions for the next question law. No task is silently filtered
or re-sealed. Registered voltage is 4.200001 V (the producer's numerical
tolerance); the buyer's 4.2-V hard limit is not amended by this analysis.
Missing aged-state, SOC, command or service coverage remains unsupported.

## Method and independence

KEEP the existing `producer_panels`, `tasks`, `indexed` and
`reference_resolution` validators, query accounting, optimizer, commitment,
limits/bands and judgment. No edits to these owners, score, power or readiness.
WRAP them with `carbon.development_comparison.cheap_baselines`.

Motor surfaces regress the **complete signed sampled curves**, then reduce
mean, absolute peak-to-peak, relative energized ripple and zero-current
cogging. Hold out whole physical geometries, including all skew siblings.
Never fit on numeric candidate IDs. Fixed Gaussian and multiquadric kernels:
epsilon 1, smoothing 1e-8, degree-zero trend; coordinate scaling uses training
rows only. The Gaussian is an ordinary-Kriging-style fixed-kernel response
surface, not a hyperparameter-optimized GP or qualified uncertainty model.
[SciPy's RBFInterpolator documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.RBFInterpolator.html)
defines these kernels and the vector-valued interpolation interface.

Battery interpolation partitions switch voltage and cooling, requires all
corners of a local rectangle in temperature/c1/c2, and refuses extrapolation.
When a held-out point lies exactly on a sampled coordinate, strict bracketing
can supply a complete alternative rectangle. This choice is coordinate-only,
never selected on residuals. Corner minima/maxima are **unqualified diagnostic
envelopes**, not nonlinear physical error bounds. The selection policy refuses
any envelope not strictly on the safe side of the registered bands.

Whole-protocol folds remove that recipe across **every** temperature band;
separate whole-band folds remove every recipe in that band. Endpoint bands
cannot be extrapolated. Requirement variants are deduplicated for fitting.
These are assembled out-of-fold bank predictions, not a single deployed
model's measured generalization or a new independent population sample.
Settings were not tuned on the resulting errors. No witness-based repair.

## Pointwise results on covered rows

| Observable | Protocol holdout MAE / max absolute | Band holdout MAE / max absolute |
| --- | --- | --- |
| Session time, min | 1.244 / 11.152 | 0.837 / 2.668 |
| Charging peak, C | 0.072 / 0.901 | 0.081 / 0.482 |
| Plating minimum, mV | 1.058 / 10.126 | 2.927 / 16.754 |
| Q30/Q1 | 0.0000241 / 0.000228 | 0.000112 / 0.000545 |

Uncovered rows: 217 protocol holdout, 385 band holdout. Voltage differences
are approximately numerical precision, not an independent credibility check.
The raw reports also contain RMSE, sample counts, per-temperature decisions,
query failures, point-prediction feasibility agreement and unresolved coverage.
Point-prediction verdicts are separate from conservative map selection.

Across the 25 reused requirement questions, protocol predictions yield 6,185
resolved candidate comparisons and 42 false-infeasible point verdicts; band
predictions yield 2,332 and 31 respectively. Both have zero false-feasible
**resolved point comparisons**, but 1,148 reference-unresolved candidate-question
rows are excluded in each arm. These repeated counts are not independent
safety evidence or statistical power. Best-pick agreement is unpriced in all
25 maps; it cannot be substituted by candidate-level agreement.

## Cost ledger (native diagnostic, not canonical acceptance)

Environment recorded in each report: Python 3.11.4, NumPy 1.24.3,
SciPy 1.10.1, Windows 10.0.26200 / AMD64. These differ from pinned canonical
CI dependencies. Each report retains the native comparator source-byte hash.
Host processor/RAM/thread allocation is not fully pinned; commercial latency
and cost must be remeasured on the intended platform.

| Operation | Measured CPU seconds | Wall seconds | Count / interpretation |
| --- | --- | --- | --- |
| Motor closed-bank search + reference arithmetic | 0.078 | 0.093 | 20 questions; median 3.28 ms, p95 7.58 ms |
| Battery closed-bank search + reference arithmetic | 3.109 | 3.219 | 25 maps; median 141.55 ms, p95 182.32 ms |
| Battery protocol-fold map construction | 1.219 | 1.264 | 226 folds, not one deployment fit |
| Battery protocol-fold prediction | 0.094 | 0.048 | 226 fold blocks, including refusals |
| Battery protocol-fold map search + reference arithmetic | 3.375 | 3.421 | 25 maps; median 135.73 ms |
| Battery band-fold map construction | 0.016 | 0.022 | 5 folds |
| Battery band-fold prediction | 0.016 | 0.016 | 5 fold blocks, including refusals |
| Battery band-fold map search + reference arithmetic | 3.281 | 3.396 | 25 maps; median 134.11 ms |

The arithmetic assessment above is **not retained solver verification**.
Acquisition, failed solves, reference refinement, retained verification,
peak RAM, input/output loading/storage, licences/money, deployment fitting,
Carbon rebuilding/inference and amortized reuse remain **NOT_MEASURED** here.
No zero-cost acquisition, EUR100 startup pass, or paid-compute savings claim.
The reported timings describe this script and data, not optimized vendor
lookup latency. The no-solves grant cannot fill a missing reference ledger.

## Reproduction and the remaining return

After entering the repository worktree, run the module with the explicitly
authorized development file and expected byte SHA; `--output` must be a new
path (exclusive creation). Example for battery:

```powershell
py -3.11 -X utf8 -m carbon.development_comparison.cheap_baselines --panel '\\wsl.localhost\Ubuntu-24.04\home\carbon\shared\design-panels\battery-v3-export.json' --expected-sha256 31463626c13549916feffa4ef9917f520e1437eb24dc08c8c402b6926e4717d4 --output battery-new-report.json
```

For motor, supply the motor path/SHA above. Missing curves produces an explicit
HOLD. Optional `--motor-curves` and `--curves-sha256` bind an analysis sidecar:
`export_digest`, `source_hashes`, `observer_version`,
`sampling=one-period-without-repeated-endpoint`, a uniform `angle_deg` array,
and one row per candidate with `geometry_id`, `coordinates`, `loaded_nm`,
`cogging_nm`. Coordinates are magnet_mm, coverage, airgap_mm, tooth_frac,
opening_frac, slot_bottom_mm, skew_deg. Groups cannot split identical physical
geometries; summary reductions must reproduce the bound export to numerical
roundoff (1e-12 comparison), not a new physical tolerance. Producer owns
source custody, the actual period/observer and release of these public rows.

Data Collection was asked for the development S1 design plan and S1/S2/S3
records paths or that digest-matched sidecar on
[#42](https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-6082538948).
It also owns settled export/refinement and retained-cost returns. Optimizer
Codex owns score/power/readiness; this PR does not infer settlement or run it.
A matched Carbon arm is still needed for an incremental-advantage conclusion.
No new owner science decision or paid execution is requested by this PR.

Current evidence is [motor revision 4](motor-measurement-v4.json) and
[battery revision 4](battery-measurement-v4.json). These are artifact revisions,
not new buyer contracts. Earlier local diagnostic files are
not part of this candidate. Historical outputs are not overwritten.

## Validation and maturity

Native diagnostic: 14 new toy tests plus task/producer/indexed/optimizer
regression, **67 passed**; Ruff and Black clean after repairing a closure
binding diagnostic. **28 pipeline tests also passed**, including lesson
validation. Final output portability repair: **14 comparator tests passed**,
Ruff/Black clean; generated reports use LF on every host. Tests cover grouped holdouts, incomplete rectangles,
no extrapolation, safety-band refusal, curve-summary identity, point verdicts,
indexed/abstention denominators, byte identity and exclusive output creation.
Canonical acceptance is delegated to the ready PR's pinned CI; local Docker
was already unavailable and was not repeatedly retried. CI status is external.

SPECIFIED / IMPLEMENTED / native toy-tested comparator scope only. Motor
measurement remains HOLD; decision V4, scientific/reference/security and
production qualification are not earned. Hub is retired/frozen. Battery EV5,
journal sequence 14, live contract and all runtime identities remain unchanged.
