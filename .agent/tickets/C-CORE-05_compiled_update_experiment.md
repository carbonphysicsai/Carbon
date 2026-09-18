# C-CORE-05: bounded compiled update experiment

Status: working implementation; programme #209 v3, dependent on C-CORE-02.
Primary Development Hub map_ref: SYSTEM/AGENT-EXECUTION; map_structural.
Affects WAVE-C/C-02 and C-03. Authority: root constitution/invariants, current
delivery/delegation protocols, Research_Resource_Policy_Contract and
Isolated_Reconstruction_Worker; the v3 owner directs measured optimization.

KEEP existing vendored Trainer, checkpoint format, source identities and accepted
CPU runtime. WRAP its existing update function in a separately named DEVELOPMENT
experiment. Do not alter its optimizer, RNG draws, physics objective, nonfinite
acceptance or historical recipe. No new scheduler, budget, grant or score rule.

C-CORE-05-D1 selects bounded chunks of 1, 4 or 16 updates for comparison against
the current per-update host synchronization. Device state stays resident during a
chunk; host history transfers once per chunk. Preserve every accepted update and
the first rejected nonfinite boundary. Cancellation is checked between chunks;
the existing independent worker watchdog still owns the hard wall deadline.
Report measured cancellation latency, not an invented universal limit.

Owned files: carbon/reconstruction/compiled_updates.py,
tests/science/test_compiled_updates.py and scripts/dev/benchmark_update_chunks.py.
No execution profile selects this helper by installation. A measured experiment
can reject it; controller/runtime integration requires its prospective execution
identity rather than silently changing existing plans.

Baseline inspected: existing Trainer.fit synchronizes every update, converts all
scalar diagnostics on host, and checks cancellation per step. Existing NPZ
checkpoints already retain parameter/optimizer/EMA leaves, RNG, progress, physical
scaling, data/source/environment identities and integrity checks; training resume
is environment-strict and cross-environment inference is explicit. Preserve those
contracts. Full backend-changing continuation/sharding metadata remains a later
bounded portability slice; do not claim it from this optimization experiment.

Acceptance: same input/RNG/update histories and state within declared engineering
comparison precision, exact discrete RNG/progress, partial chunk and nonfinite
handling, cancellation before dispatch and between chunks; bounded CPU workload
sweep reporting cold compile/warm execution/total time. Keep quality-vs-budget and
fixed-work throughput distinct. GPU/TPU measurement awaits actual granted hardware.
Canonical tests/quality/package/Hub and normal expected-head merge govern delivery.

Initial local CPU result (JAX 0.10.2; synthetic 16-update FNO with physical losses):
9 comparison/cancellation/nonfinite tests passed. For 16/64/128 spatial points,
baseline compile+train was 1.579/1.365/1.172 seconds; chunk16 was
2.304/2.217/2.280 seconds. Chunk16 execution plus host diagnostics was
0.024/0.026/0.032 seconds versus baseline 0.100/0.039/0.046 seconds. Final losses
were equal in this observation; this is not a scientific equivalence claim.
Cold compilation outweighed warm savings for these short workloads. Keep the
existing default. Retain the helper for larger fixed-work experiments; measure
accelerators only after admission. Setup was order/cache-sensitive and is reported
separately; one-process observations do not establish statistical speedup.

The subsequent provenance-complete observation is retained in
`.agent/evidence/wave_c/c-core-05-cpu-update-observation.json`. It binds exact
benchmark/helper/vendor source hashes, configurations, data identity and numerical
environment. The identical 16/64/128-point sweep observed baseline totals of
1.546/1.335/1.364 seconds and chunk16 totals of 2.334/2.287/2.705 seconds.
Checkpoint serialization took 0.143-0.174 seconds for roughly 35 KB states.
This shared local WSL host, fixed execution order and single observation do not
establish an isolated hardware performance distribution. Both observations
support retaining the current default for this short workload; neither proves
that chunking is unsuitable for larger workloads. No external cost was incurred.

Reproduce in the pinned numerical environment from the repository root:

```sh
python -m scripts.dev.benchmark_update_chunks \
  --output .carbon-artifacts/new-chunk-observation.json
python -m pytest tests/science/test_compiled_updates.py -q
```

The observation file is immutable: the command rejects an existing path. A new
run must receive a new filename and cannot overwrite the recorded observation.

The final local regression collection passed ten actual JAX tests in 47.5
seconds, including partial-chunk checkpoint resume with exact RNG/progress.
Repository strict Python 3.10-target Ruff/Black checks passed. These results
are native WSL diagnostics, not canonical acceptance. Preserve the observation's
source hashes as recorded; no commit identity or isolated timing distribution
is inferred from them. Completion remains conditional on the full required
canonical scope, package and Hub checks and normal tested-head delivery.

Integrated acceptance repair: the first exact-head canonical job in run
35287194537 reached the end of its checks but was cancelled at the 45-minute
job deadline; the targeted retry passed. The portable-state candidate's
canonical and clean-image jobs in run 35287598474 also exhausted that deadline.
The two job limits are now 60 minutes, retaining the full test commands,
classification, isolated-worker limits and all acceptance assertions. This
provides room for the existing full regression and teardown; it is not a test
exemption or authority to extend numerical worker/campaign budgets.
