# CPU determinism across execution configurations (W3)

Recorded 2026-09-20 under programme #209, ticket C-CORE-19.
Measurement evidence. It qualifies nothing, sets no tolerance and authorizes no
attempt. No device was attached and no attempt of the authorized batch was spent.

The CPU determinism baseline established that repeated trainings on **one host in
one environment** are bit-identical. That is not the question validator consensus
turns on. Two *different* machines training the same registered strategy is, and
it was unmeasured.

A second host cannot be rented under this programme's zero-spend constraint. What
can be varied for free is the thing that actually reorders floating-point
reductions: the instruction set and threading strategy the CPU backend compiles
to. That is what was varied.

## 1. Result, stated first

**Weights diverge across CPU instruction-set levels.** The same registered
strategy, the same plan, archive, seed and execution reference, trained under
different maximum ISAs, produces different bytes:

The host is a 12th Gen Intel i7-12700H: AVX2 present, **AVX-512 absent**. So
capping at AVX2 or AVX512 is inert here - the CPU emits at most AVX2 either way -
and only the caps that are genuinely narrower than the hardware change anything.
That is exactly the point: the caps below simulate a *less capable* machine.

| Configuration | Effective | `checkpoint/state.npz` sha256 (first 16) |
| --- | --- | --- |
| default | AVX2 | `41b15c91a82214a6` |
| `--xla_cpu_max_isa=AVX512` | inert (no AVX-512 on this host) | `41b15c91a82214a6` |
| `--xla_cpu_max_isa=AVX2` | inert (already the maximum) | `41b15c91a82214a6` |
| `--xla_cpu_max_isa=AVX` | narrower | **`3f602e9d5457f81c`** |
| `--xla_cpu_max_isa=SSE4_2` | narrower | **`526428e05d0b7961`** |

Three distinct results, and every genuine narrowing produced a different one.
Reproduced on a second pass, digest for digest, and the same split appears for
the `deeponet` backbone (`e26457408144f579` at AVX2 versus `3c295bd0ef7c51bb` at
SSE4_2).

What is **not** shown, because this host cannot show it: whether a machine *more*
capable than AVX2 - one with AVX-512 actually available - would produce a fourth
result. On the evidence here it very plausibly would, and a validator on such a
host is an ordinary cloud instance rather than an exotic one. That is a gap a
second machine would close.

Each configuration is internally deterministic. Determinism is **per
configuration**, not global.

## 2. What does *not* move the weights

Worth recording, because it narrows the cause:

| Varied | Weights |
| --- | --- |
| `OMP_NUM_THREADS` / `OPENBLAS_NUM_THREADS` / `MKL_NUM_THREADS` = 1, 2, 4, 8 | unchanged |
| `--xla_force_host_platform_device_count` = 1, 4 | unchanged |
| `--xla_cpu_multi_thread_eigen=false` | **changed** (`a4e246562360c427`) |

Thread count alone does not perturb the result — these operations do not go
through the OpenMP/BLAS pools. What moves the numerics is how XLA compiles and
schedules the reductions: its Eigen threading mode, and the instruction set it is
permitted to emit. Both are properties of the machine and the toolchain, not of
anything Carbon currently pins.

## 3. The part that matters most

Every identity Carbon records is **identical** across the three divergent runs:

| Recorded field | AVX2 | AVX | SSE4_2 |
| --- | --- | --- | --- |
| `observed_environment_digest` | `b4aafdca4cde6105` | same | same |
| `environment_digest` | `2ed4187d9add70af` | same | same |
| `profile_digest` | `03a11936d9e838d2` | same | same |
| `plan_digest` | `cf927795afab440a` | same | same |
| **`checkpoint/state.npz`** | `41b15c91…` | **differs** | **differs** |

`observed_environment` captures backend, library versions, `machine: x86_64`,
Python and `x64`. It does not capture the CPU's feature level, and it does not
capture `XLA_FLAGS`.

> **Two hosts that produce different weights record the same environment
> digest.** An identity match does not imply reproducible numerics, and nothing
> in the record distinguishes the two.

That is the finding. It is not a GPU problem, and it exists today.

## 4. Magnitude

Between AVX2 and SSE4_2, on the `fno` backbone after the fixture's two training
steps:

| Quantity | Differing | Max absolute | Max relative |
| --- | --- | --- | --- |
| Trained parameters | 2660 of 4696 (56.6%) | `2.086e-07` | `6.105e-04` |
| Model predictions | 11 of 64 | `1.746e-10` | `1.264e-06` |

Both are reported because they answer different questions. Parameter divergence
says the training diverged. Prediction divergence is what any downstream metric
actually inherits, and it is about five hundred times smaller at this training
length - the predictions are still dominated by the shared initialisation after
two steps. Anything reasoning about score thresholds must use the second row;
using the first would overstate the effect by that factor.

**This is a floor, not a bound.** It is measured at the shortest run the fixture
permits. Divergence of this kind compounds with step count, and the authorized
envelope allows 32 steps per invocation - sixteen times longer. The magnitude at
32 steps is **not measured here**: the C-02 compile fixture pins its step count
to 2 through both its parameter domain and its static resource table, and
widening it is a fixture change that was out of scope for this measurement.
Whoever needs the number should close that gap deliberately rather than
extrapolate from this one.

## 5. What this does and does not establish

**Established.** Reduction order changes the result; the instruction set is one
live source of that change; the effect is reproducible, affects both registered
backbones, and is invisible to every identity Carbon records.

**Not established.** That two real hosts in production would differ - this
simulates a narrower feature set on one machine rather than measuring a second
machine. Nor whether a host with AVX-512 available would differ again; this host
does not have it. The magnitude at realistic step counts. Any behaviour on a GPU. Any
tolerance, for anything.

**Not concluded.** That AVX2 is safe to assume. It is near-universal on x86-64
since 2013, but D3 gives validators provider freedom explicitly, and a provider
offering ARM instances supplies no AVX at all.

## 6. Why it outranks the GPU programme

Two consequences, both independent of any device.

**Consensus.** If two validators reconstruct the same submission on hosts with
different feature levels, they compute different weights and therefore different
downstream quantities. Nothing currently detects this: `compare_r1` short-circuits
to `BACKEND_UNSUPPORTED` because no backend profile is qualified, so no comparison
runs. The divergence is latent rather than benign - it becomes live at exactly the
moment MQ-008 qualifies a profile and the comparison gate opens.

**Measurement validity.** An MQ-008 campaign that does not control the CPU feature
level of its CPU arm would observe divergence caused by the instruction set and
attribute it to the device. Four attempts cannot be un-spent. This constrains the
evidence specification directly, and is recorded there.

## 7. Reproducing it

Each configuration was trained in its own process, because JAX and the BLAS
libraries read their threading environment at import. Configurations were run
under `nice` alongside an unrelated acceptance run; that affects timing only, and
no timing claim is made here.

## 8. Maturity

`MEASURED` on one host, Ubuntu 24.04 under WSL2, CPython 3.11.16, JAX and jaxlib
0.10.2, CPU backend. Not `SCIENTIFICALLY_QUALIFIED`, not `SECURITY_QUALIFIED`,
not `PRODUCTION_QUALIFIED`.

## 9. What the owner should decide

1. **Whether cross-host reproducibility is a requirement of validator consensus.**
   If it is, this is a live defect and it is not about GPUs.
2. **Whether the recorded environment should capture what actually determines the
   numerics** - CPU feature level and XLA flags - so that two hosts which would
   diverge are distinguishable before they are compared. This document does not
   change that record; doing so alters an accepted schema and is a migration
   under an explicit decision.
3. **Whether the prescribed exam environment pins a feature level.** W4 declares
   the environment; whether it must constrain ISA is a scientific decision, and
   constraining it would interact with the provider freedom D3 grants.
