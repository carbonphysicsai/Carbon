## 2026-10-05 — GRAPHITE-POD-GPU-PROBE-01: probe the pod's GPU before candidate code, and stop charging CUDA initialisation failures to the candidate

**Authority.** OWNER-GRAPHITE-TEST-WAVE-02 §3 (#564): the owner delegated the
pod failure-attribution decision ("your recommendation"). Under that
delegation the Test Lead approved this fix on 2026-10-05, after Graphite R2
runs 4 and 5, with five conditions (below), and required it to land before the
next live phase-3 or phase-4 run. The Carbon Validator session, which owns
`pod_outcome.py` and the attribution policy (#573), set seven binding
constraints on `pod-attribution-v2` (below). This record sets no scientific
value: no score, gate, comparison rule or threshold changes. It changes which
party a pod's failure is attributed to, within the delegated authority, by a
new registered policy version. `.agent/DECISIONS.md` is not edited.

Ticket: `.agent/tickets/GRAPHITE-01_in_house_testing_agent.md`.

**Root cause (R2 runs 4 and 5).** Failed pods exited 1. The `program.log` kept
since #580 ends with `RuntimeError: Unable to initialize backend 'cuda':
INTERNAL: no supported devices found for platform CUDA`. `pods._env` sets
`JAX_PLATFORMS=cuda,cpu`, so a CUDA backend that fails to initialise is fatal.
It was intermittent across hosts: run 4's MLP baseline failed this way, and
other recipes failed on one pod and scored on another. The pods were created
without `allowedCudaVersions` (`RunPodAdapter.create_body` never sent it, while
EV4's `pod_control.cmd_dispatch` sent `["13.0"]`), so a pod could land on a host
whose driver the image's CUDA 13 plugin cannot use. Under `pod-attribution-v1`
a Level 0-3 `program` claim is `CANDIDATE_FAILED`, so the host's failure was
charged to the agent (invariant 7).

As a side check (evidence only), the two run-5 DeepONet recipes that failed
this way were run through Carbon's real compile and pod-phase program on the
CPU (`JAX_PLATFORMS=cpu`, full 10,000 steps, from an `origin/main` export).
Both exited 0 with 200 finite predictions. This rules out a recipe defect on
that path; GPU numerics were not tested.

**Decision 1: a GPU probe before any candidate code** (`pod_phase.py`).
- `pod_phase.run` first runs `probe_environment`: Carbon's probe (`PROBE`)
  runs in a child of the same interpreter, with the same `-I` flag, a fresh
  `work` directory and the inherited environment the program gets (`_python`
  runs both, so `JAX_PLATFORMS` is the same). It initialises the backends
  `JAX_PLATFORMS` names; when they name a GPU platform it requires a GPU device,
  `default_backend() == "gpu"` and a small computation on that device. It
  writes its result from its own process, and its traceback goes to the phase
  log. It is bounded by `PROBE_SECONDS` (180 s, an engineering allowance within
  the pod's 15-minute start-up allowance).
- On failure the phase writes `failure.json` stage `environment`, exits 6 and
  stops. The strategy is not compiled and the program never starts.
- The probe's record goes into the supervisor report
  (`supervisor.json`, `pod_outcome.SUPERVISOR_SCHEMA`), which the phase writes
  at every stage. After the program ends, the phase rewrites the report and
  `failure.json` from its own memory, or removes `failure.json` on success.
  Anything the program left there is replaced.
- `bootstrap.py` is unchanged.

**Decision 2: `pod-attribution-v2`** (`attribution_policies/pod-attribution-v2.json`,
registered beside v1). v1's document and digest are byte-unchanged
(`sha256:a349dbf8...`), and `current` switches explicitly to v2. Every outcome
records the version and digest it was typed under. v2 keeps every v1 outcome
and adds the following.

| `environment` claim | v2 outcome |
| --- | --- |
| Host saw the phase run at least the worker allowance | `FAILED_INFRA` `environment_claim_contradicts_host_timing`, OTHER_SIGNAL finding, no retry |
| Levels 4-5 or an unknown level, image without a separation record | evidence only: `FAILED_INFRA` `candidate_failure_unattributed`, no retry |
| Export shows the program started, or no failed-before-program probe record | `FAILED_INFRA` `environment_claim_unattributed`, OTHER_SIGNAL finding, no retry |
| Admissible and consistent, first time, retry left | `FAILED_INFRA` `pod_environment`, one relaunch |
| Admissible and consistent, after an earlier relaunch | `FAILED_INFRA` `pod_environment_repeated`, session stops |
| Admissible and consistent, the proposal's one retry already spent on a timeout | `FAILED_INFRA` `infra_retry_cap_reached`, no retry |

- "Consistent" means no `program.log`, `predictions.json`, `built.json` or
  `DONE.json` in the export, and a supervisor report naming stage
  `environment` whose probe record failed before the program.
- `infra_retries.max` is 1: one counter for timeout retries and relaunches
  together. A first timeout after a relaunch is `infra_retry_cap_reached`,
  never the candidate's. A host-confirmed repeated timeout stays
  `CANDIDATE_RESOURCE_EXCEEDED`.
- The loader refuses any document in which an environment outcome is not
  `FAILED_INFRA`, `relaunches` or `max` exceeds 1, timeout retries exceed the
  cap, the tests are not the module's own, a repeat does not stop the session,
  or a key set is not closed.
- `classify` stays pure. Host timing is read first, then admissibility, then
  consistency, then the cap.

**Decision 3: one relaunch** (`experiment.py`).
- The relaunch runs on a fresh pod under a distinct intent (`-r1`), reserved
  against the run's budget. It is admitted by `_admit_pod` (session pod limit,
  run money cap), by the remaining elapsed time (`_fits_time`) and by the pod
  launch gate (`pods.launch`). A refusal is
  `pod_environment_relaunch_refused:<code>`.
- Both attempts are ledgered: `pod_reserved`, `pod_attempt_typed`, and a
  `pod_environment_relaunch` row.
- The attempt loop is bounded by `pod_attempts(policy)` (at most 2 pods),
  whatever a verdict asks for.
- A second environment failure records `session-stop.json` (write-once), a
  `session_stopped` ledger row and event, and closes the proposal
  `FAILED_INFRA` `pod_environment_repeated`. A waiting proposal is then closed
  `REFUSED_SESSION_STOPPED` with no pod; the tool rejects new proposals before
  dispatch; the next model reservation raises `SessionStopped`; and the
  provider ends the session `failed` with
  `{"code": "failed_infra", "reason_code": "pod_environment_repeated", "candidate_charged": false}`.
  There is no delivery and no stall escalation.
- Composition with #580: the session baseline gets at most one extra pod. A
  baseline that used a relaunch is not retried by `baseline-retry-v1`
  (`baseline_retry.ENVIRONMENT_RELAUNCH_USED`), and the baseline retry's own
  environment failure is not relaunched (`baseline_retry_used`). A
  `pod_environment` outcome is not in `baseline-retry-v1`'s `retry_on_reasons`,
  so a single failure can never use both.

**Decision 4: `allowedCudaVersions`** (`pods.allowed_cuda_versions`).
- The list is `["13.0"]`. It is derived deterministically, when `RunPodPods` is
  built, from the pinned image's accelerator lock
  `.devcontainer/accelerators/cuda13-py311.txt`, which pins `jax-cuda13-plugin==0.10.2`,
  `jax-cuda13-pjrt==0.10.2` and `nvidia-cuda-runtime==13.0.48`.
- The derivation takes every CUDA version from the plugin's runtime (13.0) up to
  RunPod's REST create-schema ceiling. That ceiling is 13.0, as recorded in
  `pod_control.cmd_dispatch`, where EV4 created every pod with `["13.0"]`.
- `uv.lock` (read only) pins the same `jax` and `jaxlib` 0.10.2.
- The accelerator README records JAX's requirement of driver >= 580 for CUDA 13.
  The connectivity receipt of 2026-09-24 shows this image on an A40 with driver
  580.159.04 and CUDA driver 13.0, with JAX backend `gpu`.
- A test pins the image digest, the lock lines and the derived list together.
- The list is recorded in each job's `pod-job.json`, and the create request
  uses the recorded value. A replay therefore keeps its create-request digest.
  A record written before this change has no list, and its replay sends none,
  as its first create did.
- `PodSpec.allowed_cuda_versions` is absent from the canonical form when it is
  empty, so earlier request digests are unchanged.
- `RunPodAdapter.create_body` sends `allowedCudaVersions`. `real_path_check`
  fails unless every in-memory create carried the derived list.
- **The disposable-pod check is not run now.** It runs inside an existing
  grant's next run, coordinated with the executor. Until then the probe and the
  relaunch carry the fix, whatever the host.

**Decision 5: withheld-log diagnostics** (`pod_logs.py`).
- A log withheld for protected material records `marker_classes`: the class
  names in `protected_material.MARKER_CLASSES` (`seed_material`,
  `draw_material`, `exam_material`, `reference_material`, `validator_state`,
  `tripwire`), or `checkout_deny_rule`.
- It never records the marker or the matched text. Every marker has exactly
  one class, and no class name trips the check.

**Decision 6: the Attacker probe** (`attack/pod_attribution.py`).
- It is construction-neutral and is wired into battery's `resource_accounting`
  family. `attack/adapters/cooling.py` is not touched.
- Ten attacks dress a construction's own failure as `environment`. They include
  the Validator's case: Level 4, a crash, and `failure.json` and the report
  rewritten after the probe passed.
- The specimen is a classifier that trusts the pod's `environment` claim, and
  it fires on every attack. Under v2 every attack is HELD.
- The honest probe failure is the control, and the real boundary relaunches it.

**Test Lead's conditions → where met.**
1. Probe first, from its own process, same environment → `pod_phase.run`,
   `probe_environment`, `_python`; tests
   `test_the_probe_runs_before_any_candidate_code`,
   `test_the_probe_and_the_program_share_one_interpreter_and_environment`,
   `test_a_candidate_cannot_write_the_environment_claim`,
   `test_a_forged_environment_export_is_still_typed_by_v2`.
2. `allowedCudaVersions` derived and recorded; disposable-pod check deferred
   (above).
3. One relaunch, within caps, ledgered, never a loop, composed with the
   baseline retry and the timeout retry → `experiment.Experiment.run`.
4. Marker class only → `pod_logs._withheld`.
5. Attacker probe with a vulnerable specimen → `attack/pod_attribution.py`.

**Carbon Validator's constraints → where met.**
1. Registration → registry entry, v1 unchanged, replay test.
2. Admissible only at trusted levels → `classify`, Level 4 tests, Attacker.
3. Consistency check → `environment_export`, `environment_consistent`.
4. Host timing first → `_environment`, `host_ran_full_allowance`.
5. One relaunch, a shared retry counter, a stop → `retry_left`, `pod_attempts`,
   `_stop_session`.
6. Supervisor report → `pod_phase._report`. A separated image's report is
   admissible at Level 4 with no policy change.
7. Deterministic CUDA versions in the pod record → `RunPodPods._record`.

Each has a test and a mutation in `tests/cpu/test_graphite_pod_gpu_probe.py`
and `tests/cpu/test_graphite_pod_gpu_probe_mutations.py`.

**Dry run.** `experiment.failure_path_check`, which `phase3 run --dry-run`
requires OK, gains two scenarios:
- a baseline's pod and a proposal's pod each fail at the probe, are relaunched
  once and score, with no baseline retry;
- a baseline's pod fails at the probe twice, the session stops `FAILED_INFRA`,
  the waiting and later proposals are refused, and two pods were launched.

**Not done here.** No live pod, no spend, no key read. The disposable-pod check
of `allowedCudaVersions` waits for a grant's next run. This is not a security
audit (AGENTS.md §13).
