# PROPOSED: bounded local GPU diagnostic contract and first run plan

Status: **PROPOSED — NOT ACTIVATED, NOT RATIFIED.**
Recorded 2026-09-20 under programme #209, ticket C-CORE-18.

Nothing in this document approves a run, installs a grant, registers an
observation source or ratifies a security contract. Merging it activates
nothing: `require_local_diagnostic_dispatch()` refuses unconditionally, and a
regression asserts that. GPU execution remains **NOT EXECUTED**.

## 1. The observed host, stated with its limits

| Property | Observation |
| --- | --- |
| Device | NVIDIA GeForce RTX 3060 Laptop GPU, 6144 MiB, driver 581.95, CUDA 13.0 |
| Platform | Windows 11 host, Ubuntu 24.04 under WSL2, kernel `6.18.33.2-microsoft-standard-WSL2` |
| Driver model | `WDDM` |
| Display | `display_active = Disabled` on the discrete GPU (panel on the Intel iGPU under Optimus) |
| Docker | Engine 29.8.0, default runtime `runc`, `nvidia` registered but not default |

**Known telemetry limitation, observed directly.** Two sources queried for the
same GPU UUID seconds apart disagreed: the Windows side reported an attached
non-Carbon graphics/compute process with per-process memory
`Not available in WDDM driver model`, while the WSL side returned an empty
compute-process list formatted exactly like a supported "none". There is no
in-band discriminator between "nothing attached" and "cannot see what is
attached". Device-level `memory.used = 0` is likewise not a measurement of
absence, because per-process attribution is unavailable under WDDM.

### What may and may not be claimed

| Claim | Status |
| --- | --- |
| A task-owned container exists, its identity, and its exit status | **Observable** |
| A task-owned container was created and removed by this task | **Observable** |
| Wall-clock timing of a task-owned process, with explicit synchronization | **Observable** |
| Device identity, capacity, driver, display state | **Observable** |
| Whole-device exclusivity | **UNESTABLISHED** — cannot be observed on this host |
| No other process holds device memory | **UNESTABLISHED** |
| A hard VRAM cap or memory partition | **NOT ENFORCED** — an allocator ceiling moves with the allocator setting and does not partition the device |
| Device memory sanitization between tenants | **UNESTABLISHED** |
| Whole-device release after a run | **UNESTABLISHED** |

A development diagnostic must therefore describe only task-owned properties and
must record the whole-device properties as unestablished.

## 2. How this differs structurally from strict admission

The strict accelerator contract requires established compute-process
enumeration before it records `other_compute_processes: []` and admits. After
C-CORE-17, `enumeration_capability()` returns `UNSUPPORTED` for `WDDM` before
any contract is consulted, and `UNESTABLISHED` for everything else while
`ESTABLISHED_OBSERVATION_CONTRACTS` is empty. That is correct and is preserved.

| | Strict admission | Proposed development diagnostic |
| --- | --- | --- |
| Exclusivity | asserted, from an established source | **never asserted**; recorded `UNESTABLISHED_DEVELOPMENT_OBSERVATION` |
| Foreign processes | recorded as `[]` | recorded as unknown, never `[]` |
| Approval | operator-installed host grant | host-owned approval of one exact plan |
| Evidence | eligible for acceptance | `official_eligible` fixed `False`, no promotion path |
| Inputs | registered plan under the strict contract | fixed public/synthetic only, protected phases refused |
| Score | applicable | `None` |

The development mode is **not** a relaxed strict mode. It produces a weaker,
differently-labelled observation and cannot be promoted.

## 3. The exact seam, and the decision it needs

**A local diagnostic cannot reuse the strict path without redefining that
path's security contract.** `IsolatedReconstructionController.execute()` reaches
`inspect_gpu_device()`, which now refuses unless enumeration capability is
`ESTABLISHED`. On this host it is `UNSUPPORTED`. The registry is empty, so even
a non-WDDM host is `UNESTABLISHED`. No approved plan, grant or campaign scope
changes that.

None of these is an acceptable route, and none was taken:

- registering a real entry in `ESTABLISHED_OBSERVATION_CONTRACTS` — would assert
  a capability this host does not have;
- installing a strict grant or adding an operator Boolean;
- monkeypatching the live validator;
- admitting the work and relying on quarantine afterwards — quarantine can only
  prevent reuse after an uncertain cleanup, it cannot establish that the
  required conditions held beforehand.

### Proposed narrow versioned extension, to be activated only by owner decision

Add a second, explicitly weaker observation outcome to `inspect_gpu_device()`,
reachable **only** when the controller stages a development worker profile
carrying an owner-approved plan digest:

- it does **not** claim exclusivity and never records `other_compute_processes: []`;
- it records `other_compute_processes: null`, `exclusivity:
  UNESTABLISHED_DEVELOPMENT_OBSERVATION`, and
  `evidence: DEVELOPMENT_ONLY_NOT_SECURITY_QUALIFIED`;
- it leaves every strict rejection path, the TPU rejection, the CPU contract,
  the grant, lease, journal and quarantine behaviour untouched;
- a positively reported foreign process still blocks it, since that is
  counter-evidence rather than absence of evidence.

Migration: the strict outcome keeps its current schema; the development outcome
is a new versioned variant, so no existing record changes meaning. Tests would
extend the existing `tests/cpu/test_accelerator_telemetry_capability.py` matrix
to assert that the development outcome can never satisfy a strict caller and
that the strict outcome still requires `ESTABLISHED`.

**This extension is described, not implemented.** It changes the meaning of a
security boundary, so it is returned as a decision rather than merged.

## 4. Host-owned approval boundary

An approval covers exactly one plan and binds: source commit and tree digest,
image ID, environment lock digest, profile digest, input phase and input digest,
operation, every bound below, a single-use nonce, and an expiry. It is supplied
by the host owner, never self-issued by a caller, and naming a registered
contract is not evidence that the observation source satisfies it.

Implemented and tested today in
`carbon/development_session/local_diagnostic_plan.py`:

- exact field set; any unexpected or execution-control field is refused, never
  sanitized (commands, mounts, devices, `--gpus`, privileged, URLs, packages,
  env, role, grant, host paths, tolerance, score, `official_eligible`);
- every identity must equal the repository-pinned value;
- protected input phases (`exam`, `final`, `evaluation`, `customer`,
  `protected`, `live`) are refused;
- integer-exact bounds, with `bool` refused as an integer;
- approval must bind this plan digest and this nonce, and must be unexpired;
- a replayed nonce is refused;
- an ambiguous previous cleanup blocks the next diagnostic and never clears,
  reuses or reinterprets strict quarantine, and never reports a released device;
- `require_local_diagnostic_dispatch()` refuses unconditionally.

## 5. Lifecycle controls

| Control | Proposal |
| --- | --- |
| Concurrency | one diagnostic at a time; the existing single shared host slot is not duplicated |
| Deadline | enforced independently of the workload, per process and for the whole task |
| Interruption | cancellation observed at existing chunk/step boundaries; no destructive host action |
| Failure accounting | a failed or unknown dispatch retains its reservation; no refund is fabricated |
| Crash / restart | a restart may not create a second slot or reset the record of consumed work |
| Cleanup | task-owned containers only; ambiguous cleanup blocks the next run rather than asserting release |
| Quarantine | strict quarantine is never created, cleared or reused by this mode |

## 6. Proposed first run plan

**Recipe.** The existing registered public diagnostic recipe already defined for
C-CORE-14: assembly `burgers_gpu_diagnostic_assembly`, catalogue
`carbon.burgers-gpu-diagnostic-recipes.v1`, public TRAIN research cases. It is
suitable because it is already registered, public/synthetic, small, and bounded
by an existing scope that fixes `productive_seconds = 600`,
`validation_cleanup_seconds = 120`, `score = None` and
`official_eligible = False`. No C-CORE-15 workload is copied, and no frozen
acceptance workload is shrunk.

**Baseline.** The registered `Trainer.fit()` path — not `fit_chunks(1)`, which
is an opt-in experiment arm and was previously mislabelled as the baseline in a
local report. `Trainer.fit` is present in the retained image, verified by
metadata inspection.

**Device.** The retained image defaults to `JAX_PLATFORMS=cpu`. The run must
apply the registered GPU overlay from
`worker_environment(GPU_PROFILE, MINER_RESEARCH)` — all eight entries, including
`JAX_COMPILATION_CACHE_DIR`, which a previous local comparison did not exercise.
Positive evidence that computation executed on the requested device is required;
a successful CPU computation is **not** GPU success, and silent CPU fallback is
a failure, not a result.

### Proposed limits — values proposed, not approved

| Bound | Proposed value | Basis |
| --- | --- | --- |
| Operation | `registered_trainer_fit` only | one registered path |
| Max invocations | 1 | no sweep |
| Max retries | 0 | no unspecified retry loop |
| Max training steps | 32 | matches the registered small recipe shape |
| Per-process wall deadline | 600 s | existing scope `productive_seconds` |
| Whole-task wall deadline | 1800 s | conservative DEVELOPMENT proposal covering startup, the run and cleanup |
| Cleanup reserve | 120 s | existing scope `validation_cleanup_seconds` |
| Max output bytes | 64 MiB | conservative DEVELOPMENT proposal |
| Host RAM ceiling | worker container limited well below the 15 GiB visible to WSL | conservative DEVELOPMENT proposal |
| Network in the numerical worker | none | no dependency resolution at run time |
| Paid spend | zero | no rental, no provider call |

The 600 s and 120 s figures derive from the existing registered scope. The
1800 s, 64 MiB and RAM ceiling are **conservative DEVELOPMENT proposals**, not
ratified tolerances, not enforceable VRAM quotas and not production criteria.
There is no enforceable device-memory limit on this host; that stays
`NOT_ENFORCED_BY_THIS_PLAN`.

A cancellation or failure-control case is **not** included in this first run. It
would require lifecycle support that the approved contract does not yet have,
and no destructive host action is acceptable to obtain it.

### Evidence to retain

Captured **before** execution: source commit and tree digest, image ID, lock,
profile, input identities, the approved plan digest and nonce. Captured during
and after: exact commands, start and end times, real process exit codes, full
stdout and stderr, and per-run measurements. Timing must separate compile,
execution, host transfer and total, with explicit synchronization, because
asynchronous dispatch otherwise reports misleading figures. Observations that
the platform cannot support must be recorded as unsupported rather than
converted into a result.

### Explicitly excluded from this first run

Chunk-size sweeps, allocator tuning, persistent or shared compilation caches,
framework changes, multi-GPU, and independent-validator qualification. Any later
reconstruction must start from the submitted recipe under its own registered
environment, not from a universal checkpoint-portability assumption.

## 7. Image status

The retained image `sha256:728a6bf3…` was built from `df26e757`, which already
contains the merged C-CORE-17 repair: inside the image,
`ESTABLISHED_OBSERVATION_CONTRACTS` is empty, `WDDM` classifies as `UNSUPPORTED`
and `N/A` as `UNESTABLISHED`. **No rebuild is required for the safety contract.**

`carbon.development_session.local_diagnostic_plan` is **not** in the image,
which is correct: it is a host-side control that runs before dispatch. A rebuild
would be required only if a future decision moves plan validation inside the
worker, or if the proposed development observation outcome in §3 is ratified and
its worker-visible bytes change. **No rebuild is authorized by this ticket**, and
the existing image keeps its original identity.

## 8. Remaining host risks

- Exclusivity and device release stay unobservable on this platform; a
  development run cannot fix that and must not claim otherwise.
- The retained image is protected from dangling-image collection by a tag, but a
  tag does **not** protect against `docker image prune -a` or an explicit
  deletion.
- Another process may hold the GPU during a diagnostic without being visible
  from WSL. Results may therefore be affected by unobserved contention, which is
  a reason to treat timings as indicative only.
