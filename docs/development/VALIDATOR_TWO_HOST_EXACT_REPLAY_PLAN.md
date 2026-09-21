# Two-host exact replay: the proposed MQ-008 basis

Ticket C-CORE-20. Written 2026-09-21. **Nothing here has been run.**

This is the study the whole exactness strategy rests on, and nothing to date
touches it. Every determinism result Carbon holds is from **one device**. Two
container configurations on one device are not two hosts; two names for one
device are not two devices; simulating a narrower CPU feature set on one machine
is not a second machine.

The quantity that matters - **do two same-class devices produce the same
result?** - is unmeasured. Not small, not bounded, not estimated. Unmeasured.

> **No attempt is spent until this specification is accepted by the owner and the
> MQ-008 domain owners (SCI + SRE). P7 governs. Acceptance is not implied by this
> document existing, and not by C-CORE-20 merging.**

---

## 0. The cheaper study ran first, and it passed

This plan required same-device determinism to be re-measured at a representative
workload before cross-device agreement was worth paying to measure. **That has
now been done and pinned determinism held.**

C-CORE-21, on the owner's device, at `width=32`, `n_modes=16`, 32 steps -
**100,680 parameters against the 4,696 every prior result used**, and therefore
different tensor shapes and different fixed kernels under
`--xla_gpu_autotune_level=0`:

| Condition | Runs | Across 3 fresh processes |
| --- | --- | --- |
| **Pinned** | 9/9 | **1 weight digest** |
| Unpinned | 9/9 | 3 digests, one per session |
| Baseline control, `width=8`/`n_modes=8`/2 steps | 3/3 | reproduces D3's pinned digest exactly |

The baseline control matters: it establishes the harness was unchanged, so the
scale result is a comparison rather than an artefact of a rebuilt rig.

So the precondition is satisfied and this study is no longer premature. Had it
failed, that result would have outranked this study and stopped it.

The warning that motivated running it first still stands as a caution about
extrapolation generally: on CPU, over 2 to 32 steps, absolute divergence grew
about 5x while **relative divergence did not grow monotonically**, and at 32
steps the parameter figure was *below* its 2-step value. Scale did not behave as
the earlier evidence assumed. Cross-device behaviour is likewise not predictable
from same-device behaviour, which is the entire reason this study exists.

---

## 1. Execution class

The class is what the study is *about*: two hosts are comparable only if they
present the same declared class, and **class identity and per-run identity are
different things**. Neither may be erased to make a comparison pass.

| Field | Value |
| --- | --- |
| Backend profile | `carbon_jax_cuda13_nvidia_development_v1` |
| Profile digest | `sha256:e1d8aefd79a540de086a293e430f4b6b255c749b60dc7bd8d3c51235534671cf` |
| Environment lock | `sha256:a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434` |
| python / jax / jaxlib | 3.11.16 / 0.10.2 / 0.10.2 |
| Parameter dtype | float32, `x64` off, matmul precision `highest` |
| Determinism flags | `--xla_gpu_deterministic_ops=true`, `--xla_gpu_exclude_nondeterministic_ops=true`, `--xla_gpu_autotune_level=0` |
| Environment | `NVIDIA_TF32_OVERRIDE=0`, `CUBLAS_WORKSPACE_CONFIG=:4096:8` |
| Worker image | `ghcr.io/carbonphysicsai/carbon-accelerator-worker@sha256:e4a2014daa9abc4e3df0bb890bc031a6a859ae21f42d4bec0a0494e25d949794` - public, pullable with no credential, **by digest never by tag** |
| Carbon revision | recorded per run, and **must contain `scripts/dev/gpu_determinism_study/run_on_pod.sh`**; the image digest does not pin it (see below). Not `6d630d4f` - that is the C-CORE-21 merge and predates the pod-native runner, so a study run at it could not have executed on a pod at all |
| Device model / class | **L40S** declared, **A40** as second class (`TWO_HOST_STUDY_ACCEPTANCE.md` §3, §7) |
| Driver version | `HUMAN_INPUT` - recorded per host; not pinned by Carbon; **must match across compared units** |
| Orchestration | see below - **not** `validator_launch.launch()` on a container-as-a-service provider |

### Two things the image digest does not settle

**It does not pin the Carbon code.** The published image was built from source
tree `sha256:16709159…`, which predates C-CORE-20 and does not contain
`validator_launch`. A run that mounts a repository and sets `PYTHONPATH` executes
the mounted code, not the image's copy - which is what the C-CORE-21 same-device
measurement did. So the execution class records the **image digest and the Carbon
revision**, and a comparison is only like-for-like when both match.

**It does not settle how the container is launched, and on a rented pod neither
docker-based path is available.** `validator_launch.launch()` spawns a container
through the Docker CLI, and the study harness is itself `docker run`. RunPod
pods use custom images and cannot build or run containers, so on that provider
**the pod image is the execution vehicle** and the reconstruction runs directly
inside it.

What that preserves is what this study measures: the pinned numerics environment
(XLA flags, TF32 override, cuBLAS workspace, matmul precision, device selection),
the image bytes, the plan, archive and seed identities, and `reconstruct()`
itself. What it does not preserve is Carbon's containment - network isolation,
read-only root, dropped capabilities, seccomp, cgroup limits - nor admission, the
worker profile, the device lease or task-owned cleanup, all of which come from
the provider's runtime instead.

**The pod-native runner exists.** `scripts/dev/gpu_determinism_study/run_on_pod.sh`
runs a session directly inside the pod image with no daemon: it exports the
numerics environment, pins the device, checks the Carbon checkout is the exact
revision the execution class names and is clean, and executes the same
`repeat_gpu.py` the docker path uses.

**It refuses to run unpinned.** Under `docker run` the determinism flags arrived
as `-e` arguments the daemon applied, so a missing one produced a failed
container. On a pod there is no daemon and nothing fails - the run proceeds
unpinned and looks pinned in every respect except the numbers, which would put
process-level divergence into a cross-device comparison and invite blaming the
device. So the run reads its own numerics record back and stops before any
reconstruction if the three XLA flags, `NVIDIA_TF32_OVERRIDE=0`,
`CUBLAS_WORKSPACE_CONFIG=:4096:8` or the GPU backend are not actually in effect,
emitting a `REFUSED_UNPINNED` record naming each one.

**It also refuses the wrong environment, by properties rather than by digest.**
Under `docker run` the image was named by digest in the command, so the daemon
enforced it. On a pod it is whatever was selected at provisioning, and a tag
instead of a digest resolves to something else silently. So the run checks the
interpreter, `jax` and `jaxlib` versions and the CUDA line against what the
profile declares, and refuses with `REFUSED_WRONG_ENVIRONMENT` on a mismatch.

**This is strictly weaker than comparing the image digest and must be recorded in
those words.** A container cannot read its own image digest - labels and digests
are registry and daemon metadata, not filesystem - so what is checked are the
properties the digest was pinning, never byte identity with the published image.
Where a property cannot be read at all, as the CUDA runtime version cannot be on
some plugin builds, the run records it as **unverifiable** and proceeds rather
than refusing: treating "could not check" as "wrong" would be the same error as
treating "could not observe" as "nothing was there". The record carries which
properties were verified and which were not, so the evidence never implies a
check that did not happen.

**Materials are derived in the pod**, from the pinned revision, rather than
shipped in. Copying them would introduce a third thing to trust - the machine
that staged them - whose state is not part of the execution class and is recorded
nowhere. Deriving them in place means the execution class already describes them,
and the plan digest is asserted either way.

> **Record the path actually used**, in these words where they apply: *direct
> execution inside the pinned image; not `validator_launch`; containment from the
> provider's runtime.* A study that measured a different path than the one it
> claims is not an exact replay of anything.

This is a constraint on Carbon's deployment design and worth stating as such:
**the worker assumes its host can spawn containers**, so container-as-a-service
providers cannot host a Carbon validator as currently built. That bears on the
provider freedom D3 promises, and it is not a finding about this study.

**The CPU side must be matched or recorded as differing.** W3 established that
the host CPU instruction-set level changes the weights. A two-host GPU study run
on hosts with different CPU feature levels cannot attribute a difference to the
device and would be a wasted study. Either match the CPU ISA across hosts, or pin
`--xla_cpu_max_isa` identically on both. Record which was done.

---

## 2. Hosts

| Field | Value |
| --- | --- |
| Provider | standardized datacenter hardware — **not a heterogeneous marketplace** (see below) |
| Region / partition | `HUMAN_INPUT` |
| Host count | **2 per class**, same declared class within a pair |
| Declared class | **L40S**, with **A40** as the second class (`TWO_HOST_STUDY_ACCEPTANCE.md` §3, §7). Availability of a co-located pair re-verified at provisioning, never trusted from an earlier read |
| Host CPU model and ISA level | `HUMAN_INPUT`, per host — **matched or recorded as differing** |
| Driver build | `HUMAN_INPUT`, per host — **verified identical before running** |
| Host memory, cores allocated | `HUMAN_INPUT`, per host |
| Container runtime and version | `HUMAN_INPUT`, per host |
| Device count per host | 1 |

A host that does not match its declared class on arrival is **released, not
substituted**, and the class is not adjusted to fit what arrived.

### The provider constraint, and why it is a design constraint

Procurement research found that a heterogeneous GPU marketplace is the wrong
instrument for this study, on evidence rather than on preference. One
Bittensor-native provider lists two pods of the *same* GPU at the *same* price
whose **host CPUs differ** — an EPYC 9355 in one region, an EPYC 9335 in another.

W3 established that the host CPU instruction-set level changes the weights. A
pair like that confounds precisely the question this study exists to answer: a
difference could be the GPU, the CPU, or both, and the design could not separate
them. So the requirement in §1 that the CPU side be matched or recorded is not
satisfiable by picking two listings of the same GPU model.

**Two mitigations, and they are complementary rather than alternatives.**

1. **Procure standardized hardware** where GPU model *and* host configuration are
   specified. This removes the confound at the source.
2. **Pin `--xla_cpu_max_isa` identically on both hosts** regardless. This is
   cheap, works even where host CPUs differ, and should be done in addition —
   procurement can be wrong about what it delivered, and a pinned ceiling makes
   that visible instead of silent.

This constrains how Carbon procures **its own evidence**. It does not narrow
validator provider freedom, which is about who may run Carbon.

**Driver builds are recorded, not pinned**, so verify both hosts report the same
build before running. If they differ, re-provision or record it as a named
limitation — otherwise a driver difference is indistinguishable from a device
difference.

---

## 3. Workload set

Not one baseline. Repeated runs of a single strategy cannot detect the effect
that matters: two devices may agree on a reference model and still favour
different submissions.

| Axis | Value |
| --- | --- |
| Strategies | **at least 4 admissible**, spanning both registered backbones (`fno`, `deeponet`) |
| Step counts | 2 (comparable to all prior evidence) and 32 (envelope maximum per invocation) |
| Sessions per host per strategy per scale | 3, each a **fresh process** |
| Invocations per session | 3 |
| Total invocations | 4 x 2 x 2 x 3 x 3 = **144** |

**Fresh processes are the axis that matters.** D3 found unpinned runs
bit-identical *within* a process and divergent *across* processes; a study that
repeated inside one process would have found nothing and concluded wrongly.

Compilation is included in every session and never shared or cached between
sessions.

### The power condition, stated before running

> If the candidates' score separation δ is much larger than the observed
> divergence ε, the study reports "no ranking change" **by construction** and has
> ruled out nothing.

So the strategy set must include **at least one pair whose δ is on the order of
the ε measured in the same-device work**, and δ for every pair must be stated in
advance. A study that could not have found a decision-changing effect has not
ruled one out, and must not be reported as if it had.

Four constraints on how that pair is chosen. The first is a soundness hole rather
than a refinement:

**δ is never derived from the results being tested.** The target scale must come
from previously retained same-device evidence or public calibration, fixed and
written down before the two-host comparison runs. Choosing the separation after
seeing the comparison rigs the study - in *either* direction, since a δ chosen
too wide manufactures a null and one chosen too narrow manufactures a finding.

**Calibration uses public or synthetic DEVELOPMENT material only.** Never hidden
exam cases, seeds, traces or protected outputs. This is not a procedural nicety:
selecting a pair *by its distance to a protected threshold* discloses that
threshold, so the selection step itself would be the leak. The near-margin pair
is chosen against a named development fixture and nothing else.

**Larger-margin controls are retained beside the near-margin cases.** Without
them a null result cannot be distinguished from a study that looked only where
nothing could be seen, and a positive one cannot be distinguished from an
artefact of sitting on a boundary.

**Every pair and its δ are fixed before the comparison runs**, recorded with the
evidence, and not revised afterwards.

---

## 4. What is compared, at every layer

A weight-digest comparison answers "identical or not" and nothing else. It cannot
say whether a difference would have changed a decision.

| Layer | Quantity | Why separate |
| --- | --- | --- |
| 1 | `checkpoint/state.npz` digest, then element-wise parameters | where divergence originates |
| 2 | Model predictions on a fixed grid | what downstream metrics inherit; 2-3 orders of magnitude smaller than parameter divergence on CPU |
| 3 | Physical measurements a Score Pack consumes | the gate acts on these, not on predictions |
| 4 | Gate outcomes | a step function: a tiny difference either flips it or does not |
| 5 | Ordering between the 4 strategies **under a named development fixture** | the shape a decision would take, if one existed |

Layers 3 to 5 are reported against underlying predictions and physical
measurements, not only against a development comparison outcome. And the language
matters: Carbon has **qualified no production rank and no production gate**, so
nothing in this study's report may imply that one exists. What layer 5 measures
is whether two hosts order the same candidates differently under a stated
development fixture - which is the shape the problem would take, not a production
ranking.

Also compared: `artifact_digest`, `environment_digest`, `observed_environment_digest`,
`profile_digest`, `plan_digest`, and the full
`carbon.reconstruction.numerics-environment.v2` record including the new
contention block.

**A known obstruction, stated rather than worked around:** no production Score
Pack exists - only synthetic A5 fixtures with a `less_than 1.0` mandatory gate.
Layers 3 to 5 must therefore be reported against a **named** fixture pack, and the
report must say plainly that the gate margin in a real pack is unknown. Do not
invent a threshold to make layers 4 and 5 computable.

---

## 5. Bounds, evidence and cleanup

| | |
| --- | --- |
| Wall-clock per invocation | ≤ 600 s productive, 120 s cleanup reserve |
| Wall-clock per session | ≤ 1800 s |
| Total wall-clock per host | ~54 min run time, ~4 h billed with margin (§6, estimated) |
| Output per invocation | ≤ 64 MiB |
| Output per host | ≤ 256 MiB |
| Retained | every weight digest, every numerics record, every manifest, per-layer comparison tables, and the full identity set per run |
| Not retained | raw checkpoints beyond one representative per (strategy, scale, host) - digests and comparisons are the evidence |
| Cleanup | both hosts released together; `validator_launch.recover()` run and its report retained before release |

Stage the work so both hosts are provisioned and released together: a two-host
study bills **both** for the duration of the slower one, plus any human time
between stages.

---

## 6. Costs - quoted rates and an estimated runtime

Quoted 2026-09-21 from RunPod Secure Cloud list prices. **Observed list prices,
not commitments**, superseded by whatever is actually offered at purchase.

| Class | VRAM | $/hr | 2 hosts x 4 h |
| --- | --- | --- | --- |
| RTX A5000 | 24 GB | 0.27 | $2.16 |
| A40 | 48 GB | 0.49 | $3.92 |
| L4 | 24 GB | 0.49 | $3.92 |
| RTX 3090 | 24 GB | 0.50 | $4.00 |
| RTX A6000 | 48 GB | 0.53 | $4.24 |
| RTX 4090 | 24 GB | 0.74 | $5.92 |
| L40S | 48 GB | 1.09 | $8.72 |
| A100 PCIe / SXM | 80 GB | 1.59 | $12.72 |

Container disk at $0.10/GB/month is negligible at these durations.

### Runtime: estimated, not quoted

Derived from the stage-1 same-device measurements - compile median 2.63 s pinned,
training median 0.467 s at width 32 / modes 16 / 32 steps - so the compute line is
measured and everything around it is an estimate.

| Line | Estimate | Basis |
| --- | --- | --- |
| Compute per invocation | ~3.1 s | **measured** |
| Container lifecycle per invocation | ~30-45 s | estimated |
| Invocations per host | 72 | this plan's matrix |
| Run time per host | ~54 min | 72 x 45 s |
| Image pull and verify | 10-25 min | image size not yet measured |
| Setup, verification, recover, release | ~30 min | estimated |
| **Billed per host, with margin** | **~4 h** | includes idle, which bills both hosts |

**The dominant cost is container lifecycle and idle, not compute.** The science
occupies about **3.7 minutes per host**; everything else is overhead. Worth
knowing before optimising the wrong thing.

### Two classes rather than one

Agreement on a single class establishes that those two devices agree. Agreement
across **two classes** is materially stronger evidence that the pinned
configuration delivers cross-device reproducibility as a *property* rather than
as a coincidence of one kernel set - the same reasoning that made the stage-1
width and modes increase worth doing, since changing shape changed which fixed
kernels ran.

**A40 plus L40S: $3.92 + $8.72 = $12.64**, four hosts at four billed hours.

> A source quote document gave this as "~$11". It is **$12.64**. Immaterial to
> the decision; corrected because an uncorrected cost figure propagates.

A 50% runtime overrun moves these by a few dollars. **The study is not
cost-constrained at any class** - which is the useful finding, because it means
the class should be chosen by which one the declared exam environment ought to
be, not by price.

### Still not quoted

- Image size, so transfer time is a range rather than a figure.
- Whether a provider can guarantee two simultaneously available units of one
  class in one region at purchase time.
- Human time between stages, which bills both hosts.

**The declared class remains `HUMAN_INPUT` and pricing does not decide it.** If
the exam environment is eventually an L40S or A100 class, the study should
include that class rather than infer it from a cheaper one.

No comparative cost claim is made beyond the quoted arithmetic above. This
document authorizes no rental.

---

## 7. Stop conditions

Stop and report rather than continuing:

- **Same-device pinned determinism fails at representative scale.** That result
  outranks this study and makes it premature.
- **Any identity mismatch between the hosts** in image, profile, lock or
  orchestration. A study on two different software stacks measures the stack.
- **A device that cannot be confirmed idle at start**, where the host can be
  asked. Where it cannot be asked, that is recorded as `UNAVAILABLE` and is not
  a stop condition - it is the honest state of the observation.
- **A host that does not match its declared class.** Release it.
- **Divergence large enough to flip a gate at layer 4** on any strategy, under
  the named development fixture. That is the decision-changing finding; stop and
  report it rather than completing the matrix for tidiness.

**This study must be able to return a result that blocks the execution class.**
If no outcome of it could do that, it is not an experiment. A finding that two
same-class hosts disagree at layer 4 or 5 is a reason the class is not yet fit to
grade with, and the study is designed to be capable of saying so.

## 8. What a mismatch is, and is not

A mismatch is **an incident with cause unestablished**. Diagnose it.

Never average it away. Never select a favourable repeat. Never relabel a fresh
reconstruction as the original artifact. Never relax an R0 check, erase a device
or run identity, or choose a tolerance to make two hosts agree - MQ-008
explicitly rejects broadening hardware support by loosening tolerances.

## 9. Required acceptance before any spend

| | Gate | State |
| --- | --- | --- |
| 1 | Owner acceptance of this specification | **outstanding** |
| 2 | MQ-008 domain acceptance (SCI + SRE) | **outstanding** |
| 3 | Same-device representative-scale determinism completed and reported | **satisfied** - C-CORE-21, §0 |
| 4 | Quotes obtained, so costs are numbers rather than `REQUIRES_QUOTE` | **satisfied** - §6 |
| 5 | Declared class chosen | **outstanding** - `HUMAN_INPUT`, and pricing does not decide it |
| 6 | Matched-hardware provider identified, driver builds verified equal | **outstanding** - §2 |
| 7 | δ stated for every candidate pair, with the smallest detectable effect | **outstanding**, and it must come from prior evidence, never from this study's own results |

Gates 3 and 4 are met. **The five that remain are human decisions, and none of
them is engineering work.** P7 governs: no attempt is spent until gates 1 and 2
are satisfied, and neither the quote document nor this plan is that acceptance.

## 10. Status

`SPECIFIED`, and **quoted**. Not accepted, not funded, not run.

Two of the seven acceptance gates are now met: the same-device precondition was
measured and passed, and the costs are numbers. The remaining five are human
decisions rather than engineering work - owner acceptance, domain acceptance,
the declared class, a matched-hardware provider, and the candidate separations.

No formal journaled C-CORE accelerator attempt has been consumed against this
study, and this study is not one of the four authorized attempts - it would need
its own authority and its own acceptance. Nothing has been rented or reserved.
