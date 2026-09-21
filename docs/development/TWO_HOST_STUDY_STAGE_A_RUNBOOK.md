# Stage A runbook - single chassis, pod-native

Executable procedure for the stage A comparison defined in
`TWO_HOST_STUDY_ACCEPTANCE.md`. It assumes the pod-native execution path in
`VALIDATOR_TWO_HOST_EXACT_REPLAY_PLAN.md`, which was exercised inside the pinned
image before any hardware was rented.

> **Authorized by amendment 2** to `TWO_HOST_STUDY_ACCEPTANCE.md`, recorded
> 2026-09-21: stage A runs pod-native, with the deviation recorded. The
> acceptance's original orchestration through `validator_launch.launch()` needs a
> Docker daemon the provider does not give a pod. Read the amendment before
> running anything - it fixes the words the result must be reported in, and this
> runbook is procedure, not authority.

## What this path is, in the words the result must carry

*Direct execution inside the pinned image; not `validator_launch`; containment
from the provider's runtime.* Admission, the worker profile, the device lease and
task-owned cleanup are absent, as are `--network none`, a read-only root, dropped
capabilities and a cgroup ceiling. The numerics are unchanged - the pod path
reproduces the containerised path's weights digest exactly on the same device -
and that is the whole of what stage A compares.

## Why two pods

The pinned worker image has no `git`, no `curl`, no `wget` and no CA bundle, so
it cannot fetch Carbon and could only download over a channel it cannot
authenticate. A **separate staging pod** on a standard image therefore populates
a network volume, and the GPU pod mounts it read-only. The staging pod runs no
part of the study and is terminated before the GPU pod starts.

The volume must carry two things:

| Item | Why |
|---|---|
| The Carbon checkout at the study revision | the image predates C-CORE-20 and does not contain the current code |
| `pytest`, importable | material derivation reaches a test module: `prepare.py` -> `c02_fixtures` -> `b02b_fixtures` -> `test_b02a_contract_models` -> `pytest`. The interpreter has to find the package, and the pinned image has no `pytest` |

### Which revision, exactly

**The study revision must contain all three of** `run_on_pod.sh`,
`stage_manifest.py` and `device_identity.py`, not only the runner. This is not
hypothetical: a revision exists with the runner and without its helpers, and
staging it would produce a session that fails on the first line of the revision
check, on a rented pod, having proved nothing. Confirm all three are present in
the checkout before terminating the staging pod.

So the revision is a **merged commit on `main` at or after the pod-path fix**,
recorded in the execution class alongside the image digest. Neither pin
substitutes for the other: the image predates the current code, so the digest
does not pin what executed, and the revision does not pin the interpreter or the
CUDA stack.

### What the tree digest does not cover

`stage_manifest` digests the **checkout**. It does not digest `/vol/site-packages`,
so the `pytest` installed beside it is outside the pin: a different `pytest`
would not move the tree digest and would not be refused. Install a pinned version
rather than a floating one, and record which. The pod-path verification that
produced the digests in the plan used **pytest 9.1.1**, so that is the version
pinned below; changing it changes an input the manifest cannot see. This is a real limit of the
provenance claim and is stated here rather than left for a reader to assume the
digest covers everything importable.

## Step 1 - network volume

One volume, smallest size that holds the checkout plus `pytest` (10 GB is ample).
Same datacenter as the GPU pod, or it cannot be mounted.

## Step 2 - staging pod

Cheapest CPU pod on a standard image with `git`. Mount the volume read-write.

The repository is public, so this needs **no credential** - which matters,
because it means no token is written to a rented machine.

```bash
git clone https://github.com/carbonphysicsai/Carbon.git /vol/carbon
git -C /vol/carbon checkout <STUDY_REVISION>

# All three must be present, or the GPU pod cannot run.
ls /vol/carbon/scripts/dev/gpu_determinism_study/{run_on_pod.sh,stage_manifest.py,device_identity.py}

rm -rf /vol/carbon/.git          # not part of the tree under test
pip install --target /vol/site-packages 'pytest==9.1.1'   # pin it; see above

python /vol/carbon/scripts/dev/gpu_determinism_study/stage_manifest.py \
    write /vol/carbon <STUDY_REVISION>
```

`write` records the revision and a digest of the tree beside the checkout. Do not
touch the checkout afterwards: any edit moves the digest and the GPU pod will
refuse, which is the intended behaviour and not something to work around.

**Terminate the staging pod** before provisioning the GPU pod. It is billing and
it has write access to the volume.

## Step 3 - GPU pod

One **2-GPU** pod of the class under test, both devices in one chassis. The
pinned image **by digest, never by tag**:

```
ghcr.io/carbonphysicsai/carbon-accelerator-worker@sha256:e4a2014daa9abc4e3df0bb890bc031a6a859ae21f42d4bec0a0494e25d949794
```

The image is public; no registry credential is required. Mount the volume
read-only. Re-verify availability at the moment of provisioning - stock is live
and an earlier read is not evidence.

**Pin the host CUDA line to 13.0.** The accelerator profile is
`carbon_jax_cuda13_nvidia_development_v1`, so the host must serve CUDA 13, and a
read of Secure Cloud availability on 2026-09-21 showed **L40S offers 13.0 only** -
12.8 and 13.2 were both UNAVAILABLE - while A40 offered 12.8, 13.0 and 13.2. So
13.0 is the one line both classes can serve, and selecting it for both keeps the
host CUDA identical across classes rather than leaving it to whatever the
provider allocates. Requesting a line a class cannot serve simply fails to
provision, which wastes an attempt rather than money.

That read also showed **both classes at `Low` stock**, at `$2.18/hr` for the
2-GPU L40S pod and `$0.98/hr` for the 2-GPU A40 pod. Those figures are the whole
pod, not per device. They are recorded as a planning estimate and **not** as
availability: stock is live, `Low` moves, and the acceptance requires confirming
it at the moment of provisioning.

Before running anything, confirm the pod is what was asked for: two devices, the
expected class, and **matching driver builds across both**.

## Step 4 - sessions

Four cells: two devices x two conditions. Each cell is **three sessions**, and a
session is **one invocation of the runner** - not `STUDY_RUNS=3` in one process.
Unpinned, the autotuner chooses kernels once per process and reuses them, so
in-session repeats reproduce bit-identically where fresh processes do not. Nine
runs in one process would be confident and worthless.

```bash
export CARBON_REPO=/vol/carbon
export CARBON_REVISION=<STUDY_REVISION>
export PYTHONPATH=/vol/site-packages
export STUDY_MATERIALS=/tmp/materials
export STUDY_RESULTS=/tmp/results
export STUDY_RUNS=3

for device in 0 1; do
  for session in 1 2 3; do
    STUDY_DEVICE_INDEX=$device STUDY_PINNED=1 \
      /vol/carbon/scripts/dev/gpu_determinism_study/run_on_pod.sh \
      "pinned-d${device}-s${session}"
    STUDY_DEVICE_INDEX=$device STUDY_PINNED=0 \
      /vol/carbon/scripts/dev/gpu_determinism_study/run_on_pod.sh \
      "unpinned-d${device}-s${session}"
  done
done
```

Materials are derived in-pod on first use, from the pinned revision, and reused
after. The plan digest is asserted, so a compilation that somehow differed is
found rather than carried.

## Step 5 - copy the records out, then release

Each session prints its record between `RECORD_BEGIN` and `RECORD_END` before
writing the file, so a failed write cannot discard a paid-for result. Capture the
console output as well as `/tmp/results`.

**Release the pod as soon as the records are off it.** Then repeat steps 1-5 for
the second class.

## Refusals

A refusal is a result. The runner stops, with exit 2 and a named reason, when:

| Refusal | Meaning |
|---|---|
| staged checkout mismatch | the volume is not the named revision, or was edited after staging |
| device UUID unreadable | the device cannot be named, so a per-device result cannot be attributed |
| `REFUSED_WRONG_ENVIRONMENT` | interpreter, `jax`, `jaxlib` or CUDA line disagree with the profile |
| `REFUSED_UNPINNED` | the determinism configuration is not actually in effect |

**Never relax a guard, edit a threshold, or set `STUDY_PINNED=0` to get a run
through.** `STUDY_PINNED=0` is the contrast condition and nothing else. If a
refusal blocks the study, record it and stop - a refusal costs one pod-minute,
and a run that was forced past a guard costs the whole study's credibility.

## Reporting

Stage A establishes **whether two same-class devices agree when nothing else
differs**. It establishes **nothing about whether the validator orchestration
agrees** - amendment 2 fixes that wording and it is not to be softened. It is
also **not** a two-host test, says nothing about host CPU or driver variation,
and says nothing about whether validators on different machines agree.

`validator_launch` remains **`HARDWARE_EXERCISED: no`**. Running stage A does not
change that, and no stage A result may be read as having exercised it. If the devices disagree, **stop and report**: stage B
is gated on stage A, and a two-host study whose devices do not agree in one
chassis would be measuring several things at once.
