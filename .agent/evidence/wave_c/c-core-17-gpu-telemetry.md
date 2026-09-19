# Core GPU evidence packet: local RTX 3060 diagnostics and telemetry boundary

Recorded 2026-09-19 under programme #209, ticket C-CORE-17.
This is retained evidence, not a completion claim, an acceptance record, or
authorization to resume. Fixture success is not hardware acceptance.

## 1. Status vocabulary

| Statement | Status |
| --- | --- |
| Host toolkit | **OBSERVED** |
| Container device passthrough | **OBSERVED** |
| WSL JAX numerics | **OBSERVED** |
| Microbenchmark | **OBSERVED** |
| Carbon GPU worker image | **UNAVAILABLE** (not built; build is inside the controlling pause) |
| Admitted Carbon execution | **NOT EXECUTED** |
| Device exclusivity | **UNESTABLISHED** |
| Fresh validator reconstruction | **NOT EXECUTED** |
| Scientific / security / production qualification | **NOT ESTABLISHED** |

## 2. Source identities

Repair and tests in this packet are authored at
`ab3e922e09b942c84018416688f89b9493474b85` on branch
`agent/core-platform-17-telemetry-capability`, in an isolated worktree.

The earlier diagnostics were **not** executed against that revision and must not
be attributed to clean main. They ran with `PYTHONPATH` bound to worktree
`core-gpu-workflow`, branch `agent/core-platform-15-gpu-workflow`, HEAD
`3f3eec3b882090ea3ca87951a93eac52db4954d9` — four local commits ahead of main
`48ed47fc`, in a tree carrying three modified and eight untracked C-CORE-15
files. That tree is preserved unchanged and was not staged, reset, renamed,
committed or cleaned.

**No execution-time module digests exist.** What is retained instead is a
**later CPU-only import replay** (`JAX_PLATFORMS=cpu`, no device attached) that
re-imported the same entry points those scripts used, listed the 78 `carbon.*`
modules that replay loaded, and hashed each from the tree as it stands now.
Digests from that replay are in the private packet (§7). Representative entries:

| Module loaded by the replay | sha256 (read after the fact) |
| --- | --- |
| `carbon/reconstruction/accelerators.py` | `1207316b91da9c25ef1fec7e061b8fd250e7114af2a9bd550ee8d56438bdb1b8` |
| `carbon/reconstruction/compiled_updates.py` | `0cadd1ccd0a9ff5978dacaa31f760834992832e5e03894b49a684ec45c01c6b9` |
| `carbon/reconstruction/_vendor/carbon_jax_lab/training.py` | `d99dd51ec3333378dbd5a704617818fededb49b6f55f01dc40171ffc71f79532` |
| `carbon/reconstruction/worker/backend_probe.py` | `7b3d02b725395c4d40b895f0103817341b7f1ea580a227890f5949054c8d4dbe` |

Two limits apply, and neither is upgraded anywhere in this packet. The digests
were read after the fact from a tree verified unchanged by `git status`, not
captured while the original runs executed. And the replay shows what **the
replay** imported on CPU; it is not a record of every module the original GPU
runs loaded, since no such record was kept. In particular, the statement that
the three modified files were not imported holds **for the replay**, and is
consistent with — but does not prove — their absence from the original runs.

## 3. Corrections to the 2026-09-19 report

Three statements in the earlier pasted report are wrong and are corrected here.
The original record is retained as historical evidence.

1. **"All GPU dispatch is blocked by an unconditional raise" — incorrect.**
   `require_accelerator_admission()` is unconditional, but it is reached only
   from the discovery CLI `scripts/dev/accelerator_acceptance.py` and its
   intentional rejection tests. The controller-mediated route uses a different,
   **conditional** helper, `require_reconstruction_profile_admission()`. See §4.
2. **`GPU_PROFILE.requirements_digest` — no such property.** The field is
   `environment_lock_digest`. The compared value
   (`a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434`) was
   correct and does match the installed lock; the property name was asserted
   without verification.
3. **"7 / 7 environment variables identical" — incomplete.**
   `worker_environment()` returns **eight** entries for NVIDIA. The comparison
   script excluded `JAX_COMPILATION_CACHE_DIR` (a `/scratch/<role>` path absent
   outside the worker). Seven of eight were compared and matched; the eighth was
   not exercised.

## 4. Corrected admission map

| Route | Entry | Gate | Earliest blocking prerequisite |
| --- | --- | --- | --- |
| A. Discovery / unadmitted | `scripts/dev/accelerator_acceptance.py` | `require_accelerator_admission()` — unconditional raise | By design. Public CLI is discovery, never an admitted run. Rejection tests preserved. |
| B. Controller-mediated reconstruction | `IsolatedReconstructionController.execute()` GPU branch | `AcceleratorHostAdmission.load()` → `.verify(dispatch=True)` → digests → `exclusive_lease()` → `verify_image_and_toolkit()` → `reject_existing_device_containers()` | **Private host grant absent.** `/var/lib/carbon/accelerators/grant.json` does not exist, so `load()` fails first with `UNAVAILABLE`. Next after that: the GPU worker image (§6). |
| C. Public GPU research service | `carbon/development_session/gpu_research.py::PublicGPUPractice` | Route B plus campaign ledger, queue and runtime scope | Everything in B, plus a campaign GPU scope and fixed host grant, which the separate campaign pause withholds. |
| D. Proposed C-CORE-15 harness | `scripts/dev/gpu_engineering_worker.py`, `gpu_engineering_acceptance.py` | Route B against a bounded engineering grant | Local, uncommitted, unapproved and paused. Not delivered, not evaluated here. |

`require_reconstruction_profile_admission()` (callers: `reconstruction/service.py`,
`worker/protocol.py` ×2) admits CPU plans, **always** rejects TPU, and for GPU
requires a `DevelopmentWorkerProfile` whose `accelerator_grant_digest` is not
`None`. That profile is constructed only by the controller, only after the host
grant verifies. So GPU dispatch is gated, not unconditionally disabled.

Conclusion unchanged, reasoning corrected: no Carbon-controlled GPU execution
occurred, because the host grant and image prerequisites are genuinely unmet —
not because every route raises unconditionally. Code presence on a route is not
evidence of successful hardware execution.

## 5. Telemetry observation and repair

### Observation (live, not inferred)

Two sources queried for the same GPU UUID, seven seconds apart:

| Source | `--query-compute-apps` | Per-process memory |
| --- | --- | --- |
| Windows host | one non-Carbon graphics/compute process reported | `Not available in WDDM driver model` |
| WSL (`/usr/lib/wsl/lib/nvidia-smi`) | empty; `-q -d PIDS` prints `Processes : None` | n/a |

WSL's answer is formatted exactly like a supported "no processes" reply, so
**no in-band discriminator exists** between "none attached" and "cannot see
them". Device-level `memory.used` read `0` throughout; because per-process
attribution is unavailable under WDDM, that zero is not a measurement of absence.

This records inconsistent visibility. It does not measure hidden allocated bytes
and does not prove concurrent numerical execution. The observed process type was
combined graphics/compute, which is not evidence of a concurrent numerical
workload. Application identity is retained privately (§7), not published.

Vendor documentation was consulted for the platform generally; the live
observation above is the evidence relied on, and the two are kept distinct.

### Repair

#### A rejected first attempt, recorded

The first revision of this repair allowlisted the `driver_model.current` reading
(`N/A`, `TCC`) as establishing enumeration capability. **That was wrong and was
withdrawn before merge.** It replaced one unsupported positive assumption — that
an empty list means an idle device — with another: that a driver-model string
certifies visibility. It does not. `N/A` reports only that a Windows-only field
does not apply to the observing platform, and NVIDIA also uses `N/A` for
information that is unavailable; `TCC` names a driver model, not a guarantee
that every process holding the device is visible from the controller's
observation point. The replacement below carries no such inference.

#### The delivered rule

`enumeration_capability()` returns one of three outcomes, never a Boolean:

| Outcome | Meaning |
| --- | --- |
| `UNSUPPORTED` | The observing platform is documented as unable to enumerate. `WDDM` is rejected here, before any contract is consulted, and no contract can override it. |
| `UNESTABLISHED` | Nothing shows this source enumerates every relevant process. This is the default, including for `N/A`, `TCC`, absent, malformed and unrecognized readings. |
| `ESTABLISHED` | A registered observation contract covers this source. |

Only `ESTABLISHED` may support an exclusivity or device-release conclusion.
`ESTABLISHED_OBSERVATION_CONTRACTS` ships **empty**, and a grant field or caller
argument only names which contract is claimed — registration in that set, which
is reviewed code, is what certifies it. An operator assertion still cannot
certify capability.

- `inspect_gpu_device()` refuses instead of recording `other_compute_processes: []`.
- `verify_device_release()` stays unreconciled and preserves the existing
  quarantine behaviour instead of reporting a verified whole-device release.

`verify_device_release()` was **not** invoked as a diagnostic probe at any point,
because it can create quarantine state. All host diagnosis used the underlying
read-only queries. No quarantine marker was created, deleted or reset, and no
device reset was performed.

### Remaining limitation

Because the registry is empty, **strict admission and verified device release
are currently unavailable on every host**, not only this one. That is the
intended fail-closed state, not a capability and not a regression to work
around: no source has yet been shown to enumerate completely, so none may
certify exclusivity.

Registering the first contract is a separate owner decision requiring its own
evidence about that source's visibility and the controls around it. This packet
does not propose one, and nothing here establishes a working secure WSL profile.

**Returned for owner decision:** whether an engineering-grant run on an
unestablished source should be admitted at all (current repair: no) or admitted
and quarantined at cleanup. That is a security-contract definition, so it was
not decided here. Note that quarantine can only prevent reuse after an uncertain
cleanup; it cannot establish that the required conditions held before a run.

## 6. GPU worker image

**Not built.** The controlling pause states it is
`PAUSED BEFORE GPU ACQUISITION, NEW IMAGE BUILD, OR INTEGRATED ACCEPTANCE`.
"New image build" is named explicitly, so building was outside authority even
though the continuation requested preparation where permitted.

Permitted readiness checks were completed instead, and all builder preconditions
are satisfied apart from authority:

| Precondition | State |
| --- | --- |
| Builder `scripts/dev/accelerator_worker_image.sh` | present on base revision |
| Recipe `.devcontainer/accelerators/Dockerfile` | present |
| Lock `.devcontainer/accelerators/cuda13-py311.txt` | present, `a197af53…` |
| Docker daemon | active; `nvidia` runtime registered; default still `runc` |
| Disk on `/var/lib/docker` | 824 GB available |
| Concurrent jobs | none; zero running containers |

No accelerator image exists on the host; all local images are CPU workers or
Julia images. Package inspection and image construction would not in any case be
accelerator execution or isolation evidence.

## 7. Retained artifacts and what is missing

Reusable diagnostic environment, outside the repository, containing the venv,
the hash-locked requirements and four scripts:

| Artifact | sha256 |
| --- | --- |
| `gpu_numeric_probe.py` | `725defe59761c989727396a1a42ddeb94c362819f89ba582e50c525d062d0181` |
| `bench_chunks.py` | `bc9903afa9c282fbd21472fcd4f247fd4bbc324d80f9a83f3295a4a8466710fb` |
| `bench_scale.py` | `cefd1c4e9e407ddd01f0c73336d3733646b33b3b92d98424150640580de88693` |
| `carbon_checks.py` | `998cdc94449a4858dc607ed835646797c75bafcc5c49d57a0fd457f7bee22c34` |
| `lock.txt` (= `GPU_PROFILE.environment_lock_digest`) | `a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434` |

Interpreter `Python 3.11.16`; `jax` / `jaxlib` `0.10.2`, `numpy` `2.4.6`,
`scipy` `1.17.1`, `optax` `0.2.8`. Installed from the pinned lock with
`--require-hashes`, exit 0. The venv, CUDA binaries and compiler caches are
deliberately **not** committed.

Runtime identity observed: profile
`carbon_jax_cuda13_rtx3060_laptop_development_v1`, profile digest
`sha256:8408adc8c7a3650bbbfb8d188be7dadae2df1e3c851f5b72a0e086bdcc012e79`,
device UUID matching `GPU_PROFILE.device_uuid`, capacity 6144 MiB, driver
`581.95`, display reported disabled. `validate_worker_observation()` passed on a
real `BackendObservation`; `require_accelerator_admission()` refused, as designed.

### Missing historical evidence — not reconstructed

- **No stdout/stderr/exit-status logs were retained** for the original probe and
  benchmark runs. Only the rendered JSON in the session record survives.
- **`bench_scale.py` retained medians only.** Its per-repeat values for 32/128/512
  steps were never persisted and cannot be recovered.
- **`bench_chunks.py` retained per-repeat totals only** (three per arm); per-repeat
  compile / execution / host-diagnostic splits were not persisted.
- **No execution-time hashes** were captured; §2 digests are post hoc.
- **No wall-clock timestamps** were recorded per run.

These remain missing. Nothing above was reconstructed, back-dated or inferred.
Any replacement requires a new, separately labelled and separately permitted run.

### Resource use

Earlier probes consumed real device time under the original finite local
diagnostic permission. No instrumented total was kept; from the retained
per-arm figures the GPU-attached process wall time is estimated at roughly
four to six minutes across about ten processes, inclusive of per-process JAX
initialisation. That is an estimate with its basis stated, not a measurement.
No grant was installed, so no lease clock started; absence of a grant does not
mean the device time was free to repeat. No fresh benchmark sweep was run in
this continuation.

## 8. Benchmark scope and uncertainty

Corrections to the earlier presentation:

- **The "chunk 1" arm was `fit_chunks(chunk_size=1)`, not `Trainer.fit()`.** It is
  the experiment's own smallest-chunk arm, not the registered baseline. The
  registered `Trainer.fit()` path was never measured, so no comparison against
  the registered default exists.
- **The 32-step difference is not a demonstrated advantage in either direction.**
  Chunk 16 was 0.12 s slower at a median of ~4 s, while the same arm's observed
  spread reached 2.7 s on a first in-process run. The correct reading is *no
  material difference at 32 steps*, which is grounds to retain the default, not
  evidence of an optimum.
- **No universal threshold is claimed.** The 128- and 512-step results are
  workload-specific to this recipe, data, optimizer, precision and host.
- **"Bit-identical" was an overstatement.** What was compared: floating-point
  leaves of `jax.tree.leaves(trainer.state)` after each run, by maximum relative
  difference, which was `0.0` for 1-vs-4 and 1-vs-16. Integer leaves were not
  differenced, and history, RNG, EMA, progress and cancellation behaviour were
  not compared. Full-state or scientific equivalence is **not** established.
- **The ~4 s compilation figure is measured overhead for this tested setup**, not
  a universal irreducible cost. No persistent or shared executable cache was
  enabled; miner/validator cache separation and current precision are unchanged.

The registered runtime default and the `platform` allocator are retained. No
training default was changed by this work.

## 9. Preservation

The C-CORE-15 worktree is byte-identical to its pre-session state: the same
three modified and eight untracked files, contents preserved, verified by
`git status` before and after. No `git clean`, stash, reset, rename or commit
touched it. All other worktrees remain intact. No host mutation, install,
driver/kernel/OS change, Docker restart, reboot, grant, quarantine change,
device reset, campaign resumption or process termination occurred. No paid
resource, cloud rental, provider call or chain operation was used.
