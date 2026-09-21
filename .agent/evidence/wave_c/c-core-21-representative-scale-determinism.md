# Pinned GPU determinism holds at representative scale (C-CORE-21)

Ticket: C-CORE-21. Branch `agent/core-platform-21-model-scale-fixture`.
Base: `f2975761` on `main` (the C-CORE-20 merge), integrated with `1f4cb5e5`.
Authority: owner direction of 2026-09-21 authorizing representative-scale GPU
determinism runs on the owner's machine.

Measured on the owner's device under that authorization. Nothing here qualifies
a backend.

---

## 1. Result, stated first

**Pinned determinism holds at representative scale.** Nine runs across three
fresh processes produced one weight digest at a model shape 21.4x larger than
every prior Carbon determinism result.

| Condition | Shape | Runs | Within session | **Across 3 fresh processes** |
| --- | --- | --- | --- | --- |
| **Pinned** | w32 / m16 / 32 steps | 9/9 | 1 digest each | **1 digest** `83e523384fd44db6…` |
| Unpinned | w32 / m16 / 32 steps | 9/9 | 1 digest each | **3 digests**, one per session |
| Baseline control | w8 / m8 / 2 steps | 3/3 | 1 digest | `beffb28947778594…` |

**The baseline control is load-bearing.** It reproduces D3's pinned digest
*exactly*, which establishes the harness was unchanged and the scale comparison
is therefore a comparison rather than an artefact of a rebuilt rig. Without it,
a different result at the new shape could not be attributed to the shape.

The unpinned condition still diverges across processes at the new shape, exactly
as at the old one, so the contrast that makes the pinned result meaningful
survives the scale increase too.

## 2. Why this shape, and why it was the right question

Every determinism result Carbon held - the CPU instruction-set finding, the gate
margin figures, and the D3 GPU characterization - was measured at
**`width=8`, `n_modes=8`, 4,696 parameters**, because the C-02 fixture could
express no other model.

Step count and model shape are different dimensions and only one of them changes
kernels. With `--xla_gpu_autotune_level=0` pinned - which the validator
determinism policy requires - **the kernel is fixed per shape**. A larger step
count runs the *same* kernel more times; a different width or mode count selects
a **different fixed kernel whose determinism had never been measured**.

So a steps-only experiment would have exercised one kernel path more often and
said almost nothing about the paths a real workload takes. Widening the fixture
first cost nothing and was the difference between answering the question and
appearing to.

Measured parameter counts, from real CPU reconstructions at each shape:

| Shape | Leaves | Parameters |
| --- | --- | --- |
| `width=8, n_modes=8` | 71 | 4,696 |
| `width=32, n_modes=16` | 71 | **100,680** |

The target is defined in `docs/development/REPRESENTATIVE_SCALE_TARGET.md`
against the registered catalog `carbon.burgers-autoresearch-recipes.v1` and the
values Carbon's own research campaign configures - not against judgement about
what "bigger" means.

## 3. Secondary measurements

| | Pinned | Unpinned | Baseline pinned |
| --- | --- | --- | --- |
| Compile, median | 2.63 s | 1.61 s | 2.44 s |
| Training, median | 0.467 s | 0.481 s | 0.043 s |

**The pinning compile cost does not grow with shape.** 2.63 s at the target
against 2.44 s at the baseline, so disabling autotuning is a roughly fixed
overhead at these sizes rather than something that scales with the model.

**Training time is now non-negligible** - 0.467 s against the baseline's
0.043 s, about 11x. That matters for one specific reason: C-CORE-19 withdrew its
execution-overhead figure because training was too small to resolve the
difference. At this scale the pinned and unpinned training medians are 0.467 s
and 0.481 s, still within noise, but now for a measurable reason rather than an
unmeasurable one. **No execution-overhead figure is claimed here either.**

## 4. Method

Three fresh processes per condition, three invocations per process. Fresh
processes are the axis that matters: D3 found unpinned runs bit-identical
*within* a process and divergent *across* processes, so a study repeating inside
one process would have found nothing and concluded wrongly.

Pinned condition applies the registered determinism configuration:
`--xla_gpu_deterministic_ops=true`, `--xla_gpu_exclude_nondeterministic_ops=true`,
`--xla_gpu_autotune_level=0`, `NVIDIA_TF32_OVERRIDE=0`,
`CUBLAS_WORKSPACE_CONFIG=:4096:8`. The unpinned condition applies none of them
and is otherwise identical.

Harness committed at `scripts/dev/gpu_determinism_study/`, so the run is
reproducible from a revision rather than from a scratch directory.

## 5. Scope, stated as limits rather than caveats

**One device.** NVIDIA GeForce RTX 3060 Laptop GPU, driver 581.95, CUDA 13,
`jax`/`jaxlib` 0.10.2, inside the pinned worker image. A laptop GPU qualifies
nothing.

**16x short on training length.** The registered catalog's default step count is
512; this ran 32, the authorized envelope's per-invocation maximum. Shape selects
kernels and length repeats them, so shape was the load-bearing dimension under the
envelope - but the length question is not closed.

**Depth unchanged at 1**, against a catalog default of 2 and a campaign value of
3. Widening it was outside this ticket's scope. Depth adds layers of the same
shapes, closer in character to step count than to width.

**Cross-device agreement is untouched and remains unmeasured.** That is the
two-host study's question and this result does not anticipate it. What this does
is remove the reason that study was premature.

## 6. Hardware and spend

Two claims, kept separate.

**Journal.** `/var/lib/carbon/accelerators` is absent, so **0 formal journaled
C-CORE accelerator attempts were consumed.** An absent journal establishes that
the journal is absent, not that no GPU work ran.

**This ticket.** C-CORE-21 **did attach the device and create containers**: 7
sessions and 21 invocations on the owner's machine, under the owner's explicit
authorization, with **zero paid spend** and no rental. The four-attempt strict
batch is untouched and remains at zero consumed.

## 7. What this changes elsewhere

`VALIDATOR_GPU_DETERMINISM_POLICY.md` recorded its measurement scope as "two
training steps on a 4,696-parameter model". That scope is widened here and the
document is updated rather than left to imply the policy rests on less evidence
than it now does.

`VALIDATOR_TWO_HOST_EXACT_REPLAY_PLAN.md` required this measurement as a
precondition. It passed, so the study is no longer premature; its remaining gates
are recorded in `TWO_HOST_STUDY_ACCEPTANCE.md`.

`GPU_NEXT_EXPERIMENTS_SPECIFICATION.md` experiment 2 is the experiment this
ticket ran.

## 8. Maturity

| State | Earned |
| --- | --- |
| `SPECIFIED` | yes |
| `IMPLEMENTED` | yes - the fixture widening |
| `TESTED` | yes - 20 fixture cases |
| `HARDWARE_EXERCISED` | **yes**, on one device, for this measurement |
| `SCIENTIFICALLY_QUALIFIED` | **no** |
| `SECURITY_QUALIFIED` | **no** |
| `PRODUCTION_QUALIFIED` | **no** |

`compare_r1` still returns `BACKEND_UNSUPPORTED`; MQ-008 at G4 still owns backend
qualification. A determinism property measured on one device is evidence toward
that decision and is not that decision.
