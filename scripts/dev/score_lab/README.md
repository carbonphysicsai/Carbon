# Scorelab (OPT-15)

An offline **DEVELOPMENT** diagnostic for score/value alignment. It runs
without a model reconstruction, reference solver, network call, hidden bank or
AX42 access. Analytic surfaces have exact reference values; their shapes,
error populations and verification costs are assumptions, not Challenge
physics. No result changes a registered score or qualifies an exam.

## One-command synthetic loop

From the repository root, run through `./scripts/dev/canonical.sh` on a
noncanonical host. The default grid is 32 profiles: small-grid/continuous,
single/multiple optima, loose/tight coupled constraints, nominal/shifted
conditions and two assumed verification costs. `--quick` runs four smoke
profiles. Every profile has unbiased-low/medium/high members, boundary bias,
rare tails, a toy physics-law violator, overconfident uncertainty, a bilinear
lookup, always-abstain, an edge optimist and a score-path gamer. Model
predictions on score and value questions are disjoint.

```sh
# All ten Validator candidates in eight families, from the owner's read-only
# local copy. This file is not committed to the Score Lab PR.
python -m scripts.dev.score_lab synthetic \
  --candidates codex-queue/inputs/score-lab-candidates/candidates.py \
  --value-workflow v2-shortlist --buyer-cap 3 --buyer-unit 1.0 \
  --out /tmp/scorelab-all-ten.json

# A registry-v9 single-leg example. This executes score_tuning's candidate.
python -m scripts.dev.score_lab synthetic \
  --registry docs/development/evidence/battery-score-tuning/registry-v9.json \
  --candidate A --out /tmp/scorelab-v9-a.json

# Old in-force family, on analytic toys only. No historical rescore.
python -m scripts.dev.score_lab synthetic \
  --registry docs/development/evidence/battery-score-tuning/registry-v5.json \
  --candidate 'G-FEAS/A-Q>@0.05' --out /tmp/scorelab-old.json

# Prospective VALUE-METRIC-V2 rev 2. Every number below is an ASSUMPTION
# for sensitivity, not an owner-selected value. The gate is explicit.
python -m scripts.dev.score_lab synthetic \
  --v2-definition docs/development/value-metric-v2/definition.v2.json \
  --kappa 0.1 --cap 3 --unit 1.0 \
  --value-workflow v2-shortlist --verification-costs 0.1 \
  --gate-json '{"measure":"feasibility","cutoff":0.05,"comparison":"exceeds"}' \
  --out /tmp/scorelab-v2.json
```

The V2 definition path is supplied by PR #1253. Until that PR merges, pass a
read-only copy of its `definition.v2.json`; Scorelab does not change or copy
the definition. A missing definition, missing cost input or missing active
gate leaves V2 unscored. A custom trusted local score rule can be passed as
`--function path/to/rule.py:function_name`; it receives exactly
`(score_predictions, score_references, score_metadata)`, never the value
questions. That is local developer execution only, not a miner-facing plugin.
`--value-workflow v2-shortlist` matches the value calculation to the V2
shortlist and solve charge; `--verification-costs` selects explicit assumed
costs. The default one-pick buyer workflow is a separate stress test and
must not be read as a matched V2 score-to-value result.
The candidate-file rules run as **proxies** on synthetic data. The three
registry families use `score_tuning`'s exact scorer on public EV4 when the
corresponding registry id exists. Other candidate families remain unmeasured
there because EV4's compact replay does not contain the per-action margin
contract they require. The candidate file is trusted local developer code.

The printed verdict says whether the exploratory 95% τ interval is positive
on every tested profile, or which profiles fail/remain unresolved. The JSON
contains τ and its crossed member/question bootstrap interval, top-1 regret,
known-bad/adversarial top-half placement, always-abstain and cheap-baseline
ranks, and one row per knob profile. It is a diagnostic, not a pass criterion.

## Public EV4 replay, no new solves

The owner's explicitly public copy at `codex-queue/inputs/ev4-public-proof/`
is local and untracked. `prepare-ev4` checks the RES-08 public source digest,
all 100 member bundle digests and the EV4 public contract, then writes a local
compact cache. It uses EV4 development cases for scoring and EV4 verification
cases for decision value. Their historical use makes this **retrospective**.
The cache is never committed.

```sh
python -m scripts.dev.score_lab prepare-ev4 \
  --public-dir codex-queue/inputs/ev4-public-proof \
  --repository . --out /tmp/scorelab-ev4-public.json.gz
python -m scripts.dev.score_lab replay \
  --cache /tmp/scorelab-ev4-public.json.gz \
  --registry docs/development/evidence/battery-score-tuning/registry-v9.json \
  --candidate A --out /tmp/scorelab-ev4-a.json
```

`replay` also accepts any registry member set in the same
`carbon.dev.score-lab-panel.v1` cache shape. A future
`2026-10-12 public-dev-decisions` adapter may produce that shape when its
public files are fetched. The real EV4 public copy has no Q3 leg and no
full-output bilinear score bundle. A/Q-based rules and a bilinear score rank
are therefore **UNMEASURED** on that replay; the lab does not manufacture
them from value-side answers. EV4's CV-onset proxy is not battery v3's EV
buyer-job value.

## V2 bank check

`bank-check` accepts a V2 manifest, development-half JSONL records and the
exact `definition.v2.json` bytes. It refuses any confirmation-half record,
definition mismatch or inconsistent per-question class. It reports class
counts and the scored share before evaluating a development-only winnability
diagnostic: cheap-arm ceiling capture, a paired block-bootstrap net margin of
a reference development model over the cheap arm, always-abstain U = 0 and
the supplied TRAIN-size learnability evidence. The cheap-arm registration,
TRAIN separation, reference image and MMS linkage must be present.
For this prototype, the manifest must explicitly register
`objective_aggregation: worst_case`; other buyer objective aggregations refuse
until an adapter is written. It also requires declared neighbour tasks and
reports a missing neighbour stratum as insufficient evidence. These checks
follow #1253's amended BANK_SPEC; they do not inspect the sealed half.

For the winnability calculation pass `--cheap`, `--reference-model`,
`--learnability` JSON files, plus explicit `--cap`, `--kappa`, `--unit` and
`--ceiling-threshold`. These are lab assumptions. Without them the status is
`INSUFFICIENT_EVIDENCE`, never PASS. It cannot open or qualify the sealed
confirmation half. The owner/Validator chooses the actual V2 values and
bank acceptance after separate evidence.

## Reuse and measurement limits

- Registry candidates use `carbon.battery.value.score_tuning.load_registry`,
  `score_member` and `gate_verdict` unchanged.
- τ and crossed recipe/question uncertainty use `score_proof`'s existing
  methods; public EV4 decision values use `decision`'s original selection,
  reference assessment and outcome code.
- RES-07/08/09's public EV4 cohort and bundle manifest supply the real replay
  identity; V2's shortlist/cost/strict-bank concepts follow their committed
  research and PR #1253's prospective definition. Synthetic `a/r/p/q` rows
  are toy analogues, not battery measurements.
- A positive τ here is descriptive. The synthetic population is constructed;
  the public EV4 panel was previously inspected. Fresh sealed confirmation
  remains the only final gate under the owner's process.
