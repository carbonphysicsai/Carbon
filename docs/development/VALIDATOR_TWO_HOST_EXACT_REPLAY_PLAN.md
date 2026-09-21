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

## 0. Run this only after the cheaper study

`GPU_NEXT_EXPERIMENTS_SPECIFICATION.md` experiment 2 repeats the same-device
determinism characterization at the scale N3 unblocked. **It should run first.**

Everything below assumes pinned determinism holds at a representative workload.
It has only been shown at two training steps on 4,696 parameters. If it fails at
scale, the validator policy's central claim weakens and this study is premature -
you would be measuring cross-device agreement of a configuration that is not
even reproducible on one device. That result would outrank this study and should
stop it.

The CPU scale measurement is a direct warning against assuming scale is
uneventful: over 2 to 32 steps, absolute divergence grew about 5x while
**relative divergence did not grow monotonically**, and at 32 steps the parameter
figure was *below* its 2-step value. Scale did not behave as the earlier evidence
assumed. There is no reason to expect a GPU to be more obliging.

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
| Worker image | one digest, **byte-identical on both hosts**, verified by label |
| Device model / class | `HUMAN_INPUT` |
| Driver version | `HUMAN_INPUT` - recorded per host; not pinned by Carbon |
| Orchestration | `validator_launch.launch()` (C-CORE-20) |

**The CPU side must be matched or recorded as differing.** W3 established that
the host CPU instruction-set level changes the weights. A two-host GPU study run
on hosts with different CPU feature levels cannot attribute a difference to the
device and would be a wasted study. Either match the CPU ISA across hosts, or pin
`--xla_cpu_max_isa` identically on both. Record which was done.

---

## 2. Hosts

| Field | Value |
| --- | --- |
| Provider | `HUMAN_INPUT` |
| Region / partition | `HUMAN_INPUT` |
| Host count | **2**, same declared class |
| Host CPU model and ISA level | `HUMAN_INPUT`, per host |
| Host memory, cores allocated | `HUMAN_INPUT`, per host |
| Container runtime and version | `HUMAN_INPUT`, per host |
| Device count per host | 1 |

A host that does not match its declared class on arrival is **released, not
substituted**, and the class is not adjusted to fit what arrived.

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
| Total wall-clock per host | `REQUIRES_QUOTE` once instance speed is known |
| Output per invocation | ≤ 64 MiB |
| Output per host | ≤ 256 MiB |
| Retained | every weight digest, every numerics record, every manifest, per-layer comparison tables, and the full identity set per run |
| Not retained | raw checkpoints beyond one representative per (strategy, scale, host) - digests and comparisons are the evidence |
| Cleanup | both hosts released together; `validator_launch.recover()` run and its report retained before release |

Stage the work so both hosts are provisioned and released together: a two-host
study bills **both** for the duration of the slower one, plus any human time
between stages.

---

## 6. Costs - no comparative claim without a quote

| Line | Amount |
| --- | --- |
| Provisioning, per host | `REQUIRES_QUOTE` |
| Image transfer / download | `REQUIRES_QUOTE` |
| Setup time, billed | `REQUIRES_QUOTE` |
| Productive compute | `REQUIRES_QUOTE` |
| Idle between stages | `REQUIRES_QUOTE` |
| Cleanup and teardown | `REQUIRES_QUOTE` |
| Storage and egress | `REQUIRES_QUOTE` |
| **All-in total** | `REQUIRES_QUOTE` |

No provider is named and no figure is estimated here, in either direction. **No
comparative cost claim may be made without a quote** - including that one option
is cheaper than another, and including any claim that the cost is small.
Obtaining quotes is an owner action. This document authorizes no rental.

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

1. Owner acceptance of this specification.
2. MQ-008 domain acceptance (SCI + SRE).
3. Same-device representative-scale determinism completed and reported.
4. Quotes obtained, so the cost table contains numbers rather than
   `REQUIRES_QUOTE`.
5. δ stated for every candidate pair, and the smallest effect this study could
   detect stated with it.

## 10. Status

`SPECIFIED`. Not implemented, not accepted, not funded, not run.

No formal journaled C-CORE accelerator attempt has been consumed against this
study, and this study is not one of the four authorized attempts - it would need
its own authority, its own quotes and its own acceptance.
