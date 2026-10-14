# ScoreLab accuracy-only championship bridge

`championship_bridge.accuracy_round` is a pure, synthetic-only adapter to
`carbon.championship_stats.rev5.select_rev5_winner`. It supplies no policy
defaults, draws no cases and launches no computation. It accepts:

- A named nonnegative per-case accuracy measurement with unit and source digest.
- The caller's existing `Rev5Rule` with every threshold and identity explicit.
- One shared tuple of drawn case IDs, possibly including exact duplicates.
- Distinct contender IDs and an incumbent in the same measured artifact pool.
- Named G-FEAS and important-region receipts bound to the evidence/rule/batch.
  The receipt hash is integrity only; it is not independent qualification.

Missing measurements or unresolved guards make the round unscored. They do not
remove a contender selectively or count as its failure. Settled failed guards
are passed to the existing hard-gate implementation. An unqualified incumbent,
fewer than two independent blocks or zero incumbent error is explicit unscored
evidence. Negative/nonfinite errors, aggregate scores and non-synthetic scope
are refused. Current rev-5 duplicate collapse, fixed K correction, strict
statistical test and incumbent tie rule are reused unchanged.

The adapter returns a committed round before `value_diagnostic` reads the value
panel. Changing value outcomes cannot change that round. The diagnostic uses a
common resolved mask for the compared finite pool, reports missing coverage and
names its regret reference as the best compared member. It does not claim the
physical optimum. The committed actual score-case IDs must be disjoint from the
diagnostic's value-case IDs, even if its separate score-side metadata differs.
Disjoint IDs do not establish semantic independence; these remain synthetic
diagnostics. `trajectory_diagnostic` checks a chain of already committed
fresh batch IDs and incumbent/winner transitions; it never carries statistical
evidence between rounds. Unique batch IDs alone do not establish independent
draws. A supplied trajectory is not a power estimate.

## Remaining full-candidate decision

**NEW_OWNER_DECISION_REQUIRED**, already specified by
`.agent/decisions/2026-10-11-CHAMPIONSHIP-REV5-RULE-01.md`'s reversibility note:
a composite q leg requires separate question-level resampling and a newly sized
margin. The ten ScoreLab proxies include signed gain, products, nonlinear
rankings and whole-panel gates. Their outputs are not per-case accuracy errors.
The old `incentive_mechanism_sim.py` is an explicitly Gaussian screen/final
surrogate and is not used as the current rev-5 selector.

### Concrete counterexample

Suppose the king's signed gain score is -1 and the challenger's is -0.9, with
identical differences on every case and passing guards. Both candidate maps
`loss = C - score` preserve the same ordering:

| Arbitrary offset C | King loss | Challenger loss | Relative improvement |
|---|---:|---:|---:|
| 0 | 1 | 0.9 | 10% |
| 9 | 10 | 9.9 | 1% |

A posted margin between 1% and 10% makes opposite takeover decisions, although
the underlying scores and their difference are unchanged. At C=-1 the incumbent
denominator becomes zero. Therefore choosing a convenient offset is choosing
championship semantics, not plumbing. The focused test demonstrates the opposite
outcomes at a labelled fixture margin; it does not implement this conversion.

### Minimal prospective method proposal for the scientific owner

1. Keep the current accuracy-only rule and this adapter unchanged.
2. For any composite candidate, register its estimand, beneficial direction,
   case/question contributions, valid resampling unit and mandatory hard guards.
3. Register whether the practical margin is an absolute buyer-unit difference
   or a relative difference with a fixed, meaningful denominator. If relative,
   specify zero/negative-baseline behavior; do not derive a shift from results.
4. Specify how whole-panel nonlinear aggregations are recomputed under paired
   resampling, then size the fresh batch and margin from independent development
   evidence before use. Keep that prospective version separate from rev-5.

Smallest unresolved decision: which registered composite comparator and margin
scale govern the full ten-proxy championship study. No default is inferred.
The readiness supplement records this gate. No holdout, real model or new
simulation campaign has been run for this adapter.

## Validation status

Focused test code covers direct library parity, deterministic replay, hard-guard
negative controls, ties, duplicate collapse, unresolved measurement/guard refusal,
metric/scope/receipt rejection, commit-before-value, shared masks and trajectory
binding. It also carries the offset counterexample. At initial preparation the
Root operator interlock prohibits local execution: these tests are **not yet run**.
Canonical validation must precede a tested-candidate claim and PR handoff.

## Finish-line gap inventory and smallest measurement proposal

This is a proposal, not an executed experiment or a population adequacy claim.
It supplements the existing finish-line manifest; it does not rewrite historical
readiness or promote any blocked stage. The 126-cell synthetic measurement study
in #1364 supplies synthetic evidence only. The earlier real-data gaps remain.

### Reuse available now

Root supplied the existing public Graphite result with SHA-256
`db6335db1d424cc8c4d288610b4b7575db5bca09b154d819bf5a14c29a954dd7`
and public export manifest with SHA-256
`aabdc612d27537e439f55a2e8fdfb4412a95c0e21dc10b8d58791d465eae1862`.
The local read-only source is
`codex-queue/inputs/operator/public-standalone-db6335db-20261014/`;
the input directory is not committed. These identities are supplied by Root;
this static preparation has not independently revalidated the entire export.

The result records one submission
`sha256:20015d9a74083b0d3e8400252a9d51a981b30072dfa39d310d8d4472894332b6`,
two replicas with the same state digest
`sha256:a0995d730e11acee2575c1c101a09ff252052003a61d59112ea606440eb4b916`,
and exact prediction parity on four inference cases. It explicitly records
`graphite_campaign: false`, `combined_086_proved: false`, and qualification false.
It is one actual standalone specimen, not two independent models or a completed
Graphite campaign. No reconstruction or inference has been repeated here.

| Needed evidence | Existing receipt supports | Still missing for this comparison |
|---|---|---|
| Model identity | Submission, state, source and reconstruction identities | Distinct incumbent on the same measured cases; cohort/family provenance for population claims |
| Accuracy | Prediction parity and a training final-loss scalar | Per-case reference-defined errors, metric/reduction/units and reference applicability; training loss is not evaluation accuracy |
| Scientific guards | Graph validation and process watchdog receipts | Named G-FEAS and important-region outcomes under the comparison contract; watchdog completion is not scientific feasibility |
| Decision value | No decision-value result in the inspected export | Separate public decision cases, verified picks, feasible/missed-opportunity outcomes and buyer-unit loss |
| Costs | Per-operation resource observations and fit timings | Complete matched workflow ledger; timings/resource limits are not total acquisition/screen/verification cost |
| Campaign | Standalone operation history, cleanup and two-replica parity | Actual campaign record if one exists; assembled documents are not executed campaigns |

### Minimum prospective receipt, before any additional measurement

1. **Graphite supplies existing outputs first.** Bind the actual specimen and a
   distinct existing incumbent to their state/recipe/source digests. Keep the
   replicas as repeatability evidence only. Identify available prediction arrays,
   query definitions, reference version and role receipts; list absent arrays
   explicitly rather than recreating a run.
2. **Validator/Test Lead registers the measurement.** Pin one accuracy metric,
   its units and reduction, the public case list and actual draw/block design,
   G-FEAS and important-region definitions and settled receipts, plus every
   existing rev-5 rule parameter. No default N, margin or guard threshold is
   supplied by this proposal. Two distinct artifacts are the minimum to exercise
   the comparator, not a sufficient cohort for an alignment/power claim.
3. **Bind a separate value diagnostic.** Register public decision cases, exact
   action menu and reference applicability, buyer-unit objective, hard limits,
   verification/abstention treatment and P/Q/w. Preserve the full registered menu
   and common unresolved mask. The current EV4 admission receipt admits no common
   full-menu questions; it cannot currently furnish this diagnostic. The intended
   battery-v3 job requires its own job/law/reference receipt, not EV4 relabelling.
4. **Use existing arrays where available.** Only after the receipt is complete,
   compute paired errors and invoke the unchanged selector, commit its result,
   then read value. If arrays or references are absent, return their exact missing
   fields to their owner. Root alone decides any execution and accounts for it
   within the shared cap; this document authorizes no run or spend.
5. **Keep the first claim narrow.** A single comparison can demonstrate transport,
   guard handling and agreement on its supplied cases. Estimating best-model win
   probability or takeover delay requires separately registered independent
   rounds and a cohort; no probability follows from the four parity queries.

The bridge remains synthetic-only. Public specimen metadata is an inventory,
not an input relabelled SYNTHETIC to bypass that boundary. A public measurement
adapter needs its explicit provenance/role contract before that path is added.

Other existing finish-line gaps are complete paired Q3/VERIFY-R inputs, matched
cheap/control workflow costs, a finite registered full-family search/selection
procedure, untouched independent validation and the final custodian-only result.
The full ten-proxy championship additionally needs the comparator decision above.
None is filled by the standalone specimen or by this proposed receipt.

### One decision for the owner: first public paired measurement

**Recommendation:** approve registration of a descriptive public EV4 accuracy
comparison of the existing standalone L4 specimen above against existing
`mlp-s0`. This is an archival development measurement, not a fresh championship,
an EV battery-v3 result or a scoring-rule selection. It reuses the known public
baseline and the established error calculation, so missing inputs are exposed
without changing the scientific job to match the available data.

| Registration field | Concrete proposed choice and remaining gap |
|---|---|
| Challenge/job | `battery-fastcharge-ageing-development-v1`, `ev4-dev-proof-v1`; CV-onset job, not time-to-SOC or the battery-v3 five-band map |
| Candidate | Submission `20015d9a74083b0d3e8400252a9d51a981b30072dfa39d310d8d4472894332b6`; public standalone state `a0995d730e11acee2575c1c101a09ff252052003a61d59112ea606440eb4b916` |
| Baseline | Public member `mlp-s0`; compressed bundle `7c2ddf542abeff71625d21d4c1e3ae9ecb6d94594b86e9f5403f8039ce160c6f`; declared recipe `68928efe9d60e4f1cc65c6008f3cb5df12bde962cd85cc616a09eddc9cedf867` from the existing public crosswalk. Training-cohort/seed-role equivalence is not established |
| Accuracy metric | Reuse `carbon.battery.exam.case_components` then `case_error`: equal mean of normalized voltage, temperature, plating and capacity components, dimensionless/lower-is-better. Pin public TRAIN-derived scales and source revision; do not fit scales to this comparison or use transformed `1/(1+E)` as the rev-5 error |
| Reference | Public EV4 trajectory outputs only, with Data Collection's explicit version/applicability receipt, including plating-v2 applicability. A binary v2 plating verdict cannot supply a missing voltage, thermal or capacity trajectory. Never call `value.scoring.scoring_set`, which loads private-role references |
| Available case definitions | The 12 committed D scenarios: temperatures 5/14/24/34 C crossed with SOC 0.12/0.33/0.48, each with the contract's seven c1 by five c2 actions. These define 420 requested rows, not 420 usable observations or a chosen statistical N. The four standalone inference query definitions/arrays are not included in the inspected 18-file export; overlap is unknown |
| Role and grouping | Descriptive reuse of public D only; no claim of an untouched set. Retain scenario grouping for any later uncertainty design. Do not label the fixed grid independent uniform case draws or feed it as a current battery rev-5 round |
| Scientific gates | Validator supplies named settled G-FEAS and important-region receipts on the same contract/rows. Unknown stays unknown; compilation, parity, watchdogs and configuration weights cannot supply PASS |
| Decision value | Deferred until the full 35-action menu has applicable references on common questions. Current v2 admission has no such common question; no smaller menu or original near-onset label is substituted |

**Bounded cost proposal (ASSUMPTION, not a measurement):** if both prediction
arrays, complete applicable references and scale receipts already exist, one
arithmetic-only audit of at most 420 paired rows is capped at **60 CPU-seconds,
120 wall-seconds, 2 GiB, zero provider dollars**, with a partial/unscored result
on exhaustion and no automatic retry. This is an execution safety cap, not a
sample-size or precision recommendation. It excludes dependency installation.
No training, inference or reference solve is included. If any required arrays
must be produced, their additional cost is **unestimated and blocked** pending
the existing executor's bounded quote; the two observed training timings alone
do not justify a new-run estimate. Root alone allocates any part of the shared
test budget. This document makes no reservation or charge.

**Decision wording:** approve this public archival comparison and existing metric
as the first receipt to complete, conditional on the listed inputs; otherwise
name the replacement job/pair. No N, takeover margin, scientific gate threshold
or full-proxy conversion is proposed or adopted. The requested registration is
not yet approved and no measurement described here has been executed.

## First TEST-window validation command

Run only after Root explicitly releases TEST mode, on this candidate's exact
commit in the existing native Linux checkout. The source worktree's Windows Git
metadata cannot be used directly by WSL; reuse the established canonical clone.
No source arrays, model state or external data enter these fixture tests.

```sh
CARBON_UV_GROUPS=science-jax timeout 300 ./scripts/dev/canonical.sh \
  /usr/bin/bash -euc '
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
.venv/bin/python -m pytest -q tests/cpu/test_score_lab_championship_bridge.py tests/cpu/test_championship_rev5.py
.venv/bin/python -m black --check scripts/dev/score_lab/championship_bridge.py tests/cpu/test_score_lab_championship_bridge.py
.venv/bin/python -m ruff check scripts/dev/score_lab/championship_bridge.py tests/cpu/test_score_lab_championship_bridge.py
.venv/bin/python scripts/dev/check_delivery_hygiene.py --base 42f875c23f391cf11582b655de85dd487cc2c431
'
```

The exact head and checkout command are delivered in the local lane report once
the source is committed. This command has been prepared, **not executed**.
