# Deploying a validator: the operator sequence

Ticket C-CORE-19, work package N item N4. Written 2026-09-20.

Everything below is inferable from source today and written down nowhere, which
is the gap this closes. It documents the path through commands that already
exist; it adds no mechanism, grants no authority and qualifies no host.

**What this is not.** Not a qualification, not an acceptance, not a production
runbook for a network that does not yet exist. A host that completes every step
here is IMPLEMENTED and TESTED for reconstruction. It is not
SCIENTIFICALLY_QUALIFIED, SECURITY_QUALIFIED or PRODUCTION_QUALIFIED, and no
sequence of operator commands can make it any of those.

---

## 0. The shape of it

A validator does two separable things, and they have almost nothing in common:

| Piece | Needs | Envelope |
| --- | --- | --- |
| **Reconstruction** | container runtime, pinned image; a GPU only for the GPU backend | `CPU_COUNT` 2, `MEMORY_BYTES` 4 GiB, 600 s productive |
| **Scoring** | nothing | negligible |

They are separate because the worker does not score. It has no scoring imports at
all: it reconstructs and exports an artifact. A5 scoring is dependency-free
float64 (`carbon/scoring/engine.py` imports `math` and carbon modules, nothing
else) and runs **outside** the container, on the artifact the worker produced.

The practical consequence: **scoring needs no GPU, no container and no special
host.** If you are sizing a validator, you are sizing reconstruction.

---

## 1. Prerequisites

### For CPU reconstruction - the fully deployable path today

1. Linux with a working **Docker daemon** the operator can reach. This is a hard
   requirement, not a preference: the worker's containment (network `none`,
   read-only root, dropped capabilities, non-root user, seccomp, cgroup limits)
   is the isolation boundary, and there is no un-containerised execution path.
2. The repository, and the worker image built from it (§3).
3. Enough host capacity for the declared envelope: at least `CPU_COUNT` cores and
   `MEMORY_BYTES` + 1 GiB of memory. `doctor` checks both.

No host grant. No exclusivity. No admission record. A CPU reconstruction carries
no accelerator role and reaches `_execute_bound()` directly - there is no
admission ceremony on this path and never was.

### Additionally for GPU reconstruction

4. An NVIDIA GPU, a driver, and the **NVIDIA container runtime registered with
   the Docker daemon**. `doctor` reports `container_device_runtime: BLOCKED` if
   the daemon does not list an `nvidia` runtime.
5. An installed `HostDeviceRecord` describing the device (§2).

The driver build is not pinned by Carbon and is not part of the declared
execution class. State it honestly in any evidence: a GPU result is
reproducible-so-far against the driver it ran on, and
`VALIDATOR_GPU_DETERMINISM_POLICY.md` documents what pinning does and does not
achieve.

---

## 2. Check the host

```bash
scripts/dev/carbon_accelerator.py inspect     # what this workload needs, what is installed
scripts/dev/carbon_accelerator.py doctor      # every blocker, or none
```

`doctor` is read-only. It changes no daemon setting, installs nothing and reboots
nothing. Every finding is `READY`, `BLOCKED` with a reason, or `UNKNOWN` -
`UNKNOWN` is used wherever the host cannot be read, rather than being folded into
`READY`, because "we could not see a problem" is not "there is no problem". It
exits non-zero if any check is not ready.

The checks: `container_runtime`, `container_device_runtime`, `container_daemon`,
`host_device_record`, `device_quarantine`, `compute_process_enumeration`,
`display_output`, `installed_authority`, `attempt_accounting`.

For a GPU host, record the device first:

```bash
scripts/dev/carbon_accelerator.py observe                      # read-only vendor query
scripts/dev/carbon_accelerator.py prepare --record-id <name> \
    --provider <who-provides-this-host>                        # writes the host record
```

`observe` never writes. `prepare --dry-run` shows the record without installing
it. Nothing machine-specific belongs in Carbon's source: it goes in this record,
which is why running Carbon on new hardware never means editing Carbon.

> **`doctor` reports `installed_authority: BLOCKED` when no grant or development
> approval is installed.** On the CPU path this finding is irrelevant - that path
> consults no authority record. See §7 for what it means on the GPU path.

### Sizing

Since N2, sizing is a **cost and throughput** decision rather than a
reproducibility one. Usable core count (1, 2, 4, 8), memory ceiling (2, 4, 8 GiB)
and two simultaneous runs on disjoint cpusets all produced byte-identical weights
across eighteen runs. The cpuset is resolved from the host rather than fixed at
cores 0 and 1, so **two concurrent reconstructions are possible**; before N1 they
were not, because both demanded the same two cores.

The declared envelope itself is unchanged at 2 CPUs and 4 GiB per launch. N2 says
widening it would not change results on this evidence; it does not widen it.
Details in `.agent/evidence/wave_c/c-core-19-host-resource-allocation.md`.

---

## 3. Obtain and verify the image

```bash
scripts/dev/accelerator_worker_image.sh     # GPU worker (builds the CPU parent first)
scripts/dev/c03_worker_image.sh             # CPU worker alone
```

The build writes a manifest to `.carbon-artifacts/`. Verification is **not
optional and not manual**: `verify_image_and_toolkit()` compares the image's
labels against the profile a launch is admitted under, and refuses a mismatch.
This is why the image had to be rebuilt when the portable profile's digest moved
- the retained image carried the old digest and was correctly refused.

Check the manifest's `image_id`, `source_tree_digest` and accelerator profile
label match the revision you intend to run. A worker image is immutable and its
identity is bound into every launch; an image that "looks right" but carries a
different label will be rejected at dispatch rather than silently accepted.

---

## 4. Run a reconstruction

```bash
scripts/dev/carbon_accelerator.py run <manifest> --state-root <dir>
scripts/dev/carbon_accelerator.py status --state-root <dir>
```

`run` claims from the queue through the controller that already exists - there is
no second scheduler - and cross-checks the manifest's digests against the claim's
binding before executing. It returns the launch digest, the output snapshot
digest, the effective controls and the timings.

It also returns, on every run:

```json
{"lane": "MINER_CONTAINED", "official_eligible": false,
 "authority": "MINER_LANE_RUN_NOT_EVIDENCE"}
```

That is deliberate and it is not decoration. A run establishes that the run
happened. It does not establish scientific merit, and the command says so at the
point an operator reads it.

`status` reports what has been consumed and what is outstanding, including attempt
accounting against any authorized batch.

---

## 5. Score the artifact

Scoring does not go through any of the above. It reads the artifact the worker
exported and runs A5 scoring in-process, in float64, with no accelerator
libraries and no container. There is no GPU step, no image, no host record and no
envelope to speak of.

Two consequences worth stating plainly:

- A host that cannot reconstruct can still score.
- Scoring is not where hardware divergence enters. It enters during training and
  is *inherited* by the metrics scoring computes - which is why the divergence
  figures that matter are measured on predictions rather than parameters. See
  `.agent/evidence/wave_c/c-core-19-gate-margin-analysis.md`.

---

## 6. Recover from an interruption

```bash
scripts/dev/carbon_accelerator.py cancel <execution-id> --state-root <dir>
scripts/dev/carbon_accelerator.py recover --state-root <dir> --dry-run
scripts/dev/carbon_accelerator.py recover --state-root <dir>
```

`cancel` is a **cooperative stop request, not a kill**. It writes a request; the
run stops at its own next boundary and performs its own cleanup. The response
says `COOPERATIVE_STOP_REQUEST_NOT_TERMINATION` for exactly that reason. If you
need a process gone immediately, this is not that command.

`recover` removes containers that unfinished launches still own, and releases
their allocation records. Run `--dry-run` first; it reports without removing.
It exits non-zero if anything could not be removed.

Why this matters more than it looks: on a laptop a leaked container wastes
nothing, but on rented compute it **bills until someone notices**. Cleanup and
settlement are cost control. A finished run that leaves its attempt blocking was
a production cost bug before it was anything else.

---

## 7. The one thing this document cannot tell you to do

N4's instruction is that the deployment path carries **no host grant, no
exclusivity and no admission ceremony**. That is satisfied end to end for CPU
reconstruction, which is the fully deployable path today.

It is **not** satisfied for a GPU reconstruction carrying
`AcceleratorRole.VALIDATOR_RECONSTRUCTION`. That role still dispatches through
`AcceleratorHostAdmission.load()` and `exclusive_lease()` in
`controller.execute()` - the strict apparatus, requiring an owner-signed grant
and an exclusive device lease.

This is recorded as a seam rather than resolved, because resolving it either way
is outside what this work package authorizes:

- Removing the strict gate from the validator role would be building validator-
  side machinery, which the scope correction explicitly forbids, and would take a
  position on validator exclusivity that MQ-008 owns empirically.
- Documenting the grant ceremony as the validator path would contradict N4 and
  would build on the strict apparatus, also forbidden.

**Classification:** `NEW_OWNER_DECISION_REQUIRED`.

**Smallest decision required:** whether `VALIDATOR_RECONSTRUCTION` on a GPU should
continue to require an owner-signed grant and an exclusive lease, or whether it
should use the same host-record-plus-`doctor` admission the miner lane uses. Until
that is decided, a GPU validator deployment is blocked at admission by design, and
no operator sequence can route around it. CPU reconstruction and scoring are
unaffected and complete.

---

## Related

- `VALIDATOR_EXAM_ENVIRONMENT.md` - what the declared environment pins, and the
  CPU instruction-set divergence it does not fix.
- `VALIDATOR_GPU_DETERMINISM_POLICY.md` - the pinned GPU configuration, what it
  delivers, what it costs.
- `.agent/evidence/wave_c/c-core-19-host-resource-allocation.md` - N1/N2/N3.
