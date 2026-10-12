# Battery Level 1 Q1, public EV4 development study

**Status:** registered and ready for public input bundles; the actual L1 Q1
report is **not measured**. This is not a Level 0 report, hidden evaluation,
readiness acceptance, or a new score rule. The Graphite Test executor owns the
prediction and score inputs; the Test Lead owns the resource decision. The
executor's pod run is separate from this development PR; no pod is dispatched
by the contract or tests.

The contract is
[`ev4-dev-proof-l1-v1.json`](../../../../carbon/battery/value/contracts/ev4-dev-proof-l1-v1.json).
It inherits EV4's public decision, cases and reference. Its panel has the
eleven Level 0 proof anchors and exactly nine counted Level 1 members from
`proof-panel-levels-v1.json`, each pinned by member digest. Lane G rows with
`counts_for_level: false` are absent. Both source files are pinned by SHA-256.
The runner verifies the committed public EV4 reference digest. The historical
private-role scoring set is never opened on this path.

## Estimate first, then Test Lead resource review

```bash
cd ~/Carbon
python -m scripts.dev.battery.l1_decision_q1
```

The existing CPU planning proxy estimates **3.232 CPU-hours** for 20 rebuilds
(1.447 Level 0, 1.784 Level 1). This is not a measured Level 1 runtime.
Prediction cost and peak memory are unmeasured. The executor must establish
both before starting reconstruction; if the credible full estimate exceeds
roughly 6 CPU-hours or 10 GB, stop and route the run to Data Collection's
host for Test Lead disposition. No solver run is needed: the EV4 references
are already committed.

## Public prediction pod plan

The executor can generate a `value_panel` plan for the registered L1 contract:

```bash
python -m scripts.dev.exam_design.value_plans panel --study ev4-l1 --shards 1
```

This plan ships the public EV4 references and public TRAIN/calibration files;
it does not ship the historical private-role scoring set. The panel phase
checks the exact L1 contract digest. For each registered Level 1 member it
applies `level_compile` to the full strategy, compiles the resulting base
recipe, reconstructs, then predicts. The bundle's recipe digest must match
the frozen experiment's level-aware digest check. A Level 1 member sent
through the uncompiled base path, a changed registered strategy, or a
different contract is refused. The executor reviews the provider's pod-hour
estimate and cost before any dispatch; this repository command only writes a
plan.

## Executor inputs and command

`<PREDICTIONS>` is a directory containing exactly one `NAME.json.gz` bundle
for each of the 20 registered members. Bundles carry the registered member,
seed, recipe digest and predictions on the public EV4 cases. The Level 1
bundles come from their own registered construction level; the decision
runner will not retrain them as Level 0. `<SCORES>` is a JSON document:

```json
{
  "classification": "PUBLIC_SYNTHETIC_DEVELOPMENT",
  "score_direction": "higher_is_better",
  "scoring_rule_digest": "sha256:<current development rule>",
  "members": {"<every registered member>": {"score": 0.0, "eligible": true}}
}
```

The score is the public practice/pod score expressed higher-is-better, as in
the existing Level 0 Q1 mapping; it is a **stand-in for alignment measurement**,
not an official exam score. Never substitute a toy score for the real report.
Supply all 20 rows, including ineligible members, and the current rule digest.
The script refuses missing or extra bundles or score rows before freeze.

After the public prediction bundles and score records exist, on WSL CPU under
the executor's resource review, run with one process, a
positive nice value, and a 10 GiB address-space cap:

```bash
cd ~/Carbon
ulimit -v 10485760
nice -n 10 python -m scripts.dev.battery.l1_decision_q1 \
  --root <PUBLIC_WORK>/l1-experiment \
  --predictions <PREDICTIONS> --scores <SCORES> \
  --panel-out <PUBLIC_WORK>/q1-panel.L1.json \
  --report-out carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/q1_report.L1.json
```

The command prints the estimate first, then freezes the contract, imports
only the digest-bound public EV4 references and the supplied bundles,
evaluates decisions, and calls `readiness.q1 build --level 1`. It writes no
Level 0 report. The report records the common resolved development mask;
unresolved selections never silently improve a member's outcome. V1 and V2
at L1 read only `q1_report.L1.json`.

## Current gap

The public `shared/evidence/tuning-standin` has aggregate tuning curves, not
the 20 prediction bundles or current per-member score records. The committed
EV4 references are present. The dry-run fixture tests exercise the L1 Q1
mapping and V1/V2 level routing; they are **not** evidence of actual member
value. Graphite Test must supply the public bundles and score records and
measure memory before a real L1 report can be written. Do not use hidden,
sealed, tuning-role, or AX42 material to fill the gap.
