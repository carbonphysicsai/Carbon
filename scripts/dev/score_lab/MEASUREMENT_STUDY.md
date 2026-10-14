# Fixed-population measurement study

This is a synthetic section-E experiment under SCORE-LAB-EXPERIMENT-PLAN-01.
It measures how the sampling design changes uncertainty on a fixed toy task.
It does not recommend a real Challenge sample count, choose a scoring rule,
or use the private final holdout. All settings are labelled ASSUMPTION.

## Reused implementation

- `physics.build`: the unchanged six-score / 36-value-question finite profile.
- `campaign_goodhart` and `synthetic`: cached-map and always-abstain probes.
  The cached map has no measured build cost or physical traits; physics is OFF.
- `campaign_gate`: the existing historical public aggregate and toy controls.
- `campaign_reference`: model-independent draw-level outages.
- `campaign_blocks`: whole complete-block masks, shared by every model/probe.
- `core.analyze` / `score_proof.bootstrap`: crossed recipe and question/block
  resampling. The original scorer receives only its fixed score half.
- The external, digest-pinned ten Validator toy proxies. No policy is adopted.

Increasing `physics.questions_per_side` would also increase its context range.
This study instead samples with replacement from a fixed 36-question support.
Six model traits and four probes stay fixed; sampling seeds are not model seeds.
There are 126 prospective cells, each with the same ten candidates:

| Study | Draw rows | Independent blocks | Within-block law | Other dimensions |
|---|---|---|---|---|
| Sample/block | 30, 300, 3000 | 3, 10, 30 | iid or replicated single draw | Three sampling seeds, uniform P=Q, buyer w=1 |
| Proposal/outage | 300 | 10 | iid or replicated single draw | Three seeds; 0/1/5% outages; strict/exclude blocks; separate Q/P targets |

The second study gives extrapolated questions half the proposal probability Q.
Population P remains uniform. Raw Q estimates `E_Q[w*loss]`; the P measure uses
the unnormalised Horvitz-Thompson mean `mean(P/Q*w*loss)`. These are separate
reported measures, with P, Q, w and each correction retained in draw identity.
Neither report secretly substitutes Q for P or normalises by the sample weights.

Cases and blocks use exactly the same complete-block mask. One unresolved draw
excludes its entire block under exclusion, including otherwise-resolved draws.
Strict completeness makes the whole cell unscored. Fewer than three remaining
blocks also makes it unscored. Exclusion reports a conditional retained-draw
estimand, with no unconditional population coverage claim. Stable block names
keep bootstrap ordering fixed when only the number of replicated rows changes.

The 95% intervals use 60 replicates of the existing crossed bootstrap. Three
draw seeds give descriptions, not a reliable empirical coverage estimate. Even
3000 rows cannot remove uncertainty from six illustrative recipe clusters.
Case-level intervals can be overconfident under replication, but joint intervals
can also remain wide because recipe resampling dominates. Undefined tau is
retained as undefined, never replaced by zero.

## Registration, execution and readout

`measurement_run register` writes a prospective plan without importing or
evaluating the external candidate module. Commit it together with its pinned
source before execution. The candidate file is trusted developer input, never
miner input. It stays outside tracked code.

```bash
python -m scripts.dev.score_lab.measurement_run register \
  --candidates "$CANDIDATES" --plan "$PLAN"
# Commit the new prospective registration before running it.
./scripts/dev/canonical.sh python -m scripts.dev.score_lab.measurement_run run \
  --candidates "$CANDIDATES" --plan "$PLAN" --output "$FRESH_OUTPUT"
python -m scripts.dev.score_lab.measurement_run readout \
  --plan "$PLAN" --output "$FRESH_OUTPUT" > "$SUMMARY"
```

Use paths present in the canonical validation copy. Its disposable output must
be exported before the container exits; the established campaign export wrapper
can transport bytes but does not create scientific identity. The driver writes
START and the copied plan before controls or scorers, checkpoints each cell, and
emits IDENTITY over the artifacts. Readout checks all pins and refuses a stopped
or partial run. Hashes establish integrity, not independent review or authority.

Execution is sequential, with a 1800 CPU-second / 1900 wall-second hard cap,
2 GiB address-space cap and 60 CPU-second reservation before each complete cell.
The OS hard cap also bounds a cell that exceeds its reservation. Any refusal or
limit stops the run; earlier outputs remain explicitly partial. Cost includes
controls, population construction, scorers and analysis in the evaluator process;
dependency setup, tests, transport and readout are separate overhead. The scorer
is called once per member/candidate, then frozen calls enforce score-input identity.

Remaining section-E work is explicit: alternative aggregations/normalisations,
score-side failure modes, real population calibration and the championship
bridge. These are not completed by this mean-only sampling study.
