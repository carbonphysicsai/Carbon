# Validator policy: the most deterministic GPU reconstruction achievable

Owner direction, 20 September 2026: *test and solve for the most deterministic
way possible to run fair training (reconstruction) runs on GPUs, and make that
the validator policy.*

**Status: declared, not qualified.** This states the configuration a validator
runs GPU reconstruction under. Declaring a configuration is not qualifying it,
and nothing here sets a tolerance or admits a backend. Qualification remains
MQ-008's, under R0/R1/R2 at gate G4, owned by SCI + SRE.

## 1. Why a policy is needed rather than a recommendation

An unpinned GPU reconstruction **does not reproduce across processes**. This was
measured, not assumed: four sessions of the same registered strategy under
identical R0 identities produced four different sets of trained weights, each
session internally consistent and each disagreeing with the others.

R1 asks whether a repeat execution reproduces the numerical results. Unpinned,
the answer is no - and no tolerance rescues that, because choosing one to make a
device pass is precisely what MQ-008 rejects. So the configuration is not a
performance preference to settle later. **It is a precondition for a GPU profile
ever qualifying.**

## 2. The configuration

Pinned in `worker_environment()` for the GPU profile, applied by the controller
to every accelerator launch.

### XLA

| Setting | Purpose |
| --- | --- |
| `--xla_gpu_deterministic_ops=true` | Orders reductions and selects kernels deterministically rather than by whatever the scheduler did. |
| `--xla_gpu_exclude_nondeterministic_ops=true` | **Refuses** an op with no deterministic implementation instead of silently using one. |
| `--xla_gpu_autotune_level=0` | Stops kernel choice depending on timing measurements taken per device and sometimes per run. |

Each was verified against the pinned build rather than recalled: an invented flag
is refused with `Unknown flag in XLA_FLAGS`, and each of these was accepted by
`jaxlib` 0.10.2 inside the pinned worker image. `--help` on this build lists only
flags marked stable, so absence from that list is not evidence a flag is missing.

The second one deserves its own note. It can make a workload **fail** that would
otherwise have produced a number. That is intended. A result nobody can reproduce
is not evidence, and failing loudly is worth more than a number that cannot be
defended. Measured: it did not refuse the reference workload.

### Library and precision

| Setting | Purpose |
| --- | --- |
| `JAX_DEFAULT_MATMUL_PRECISION=highest` | Full float32 matmuls. Already pinned before this policy. |
| `NVIDIA_TF32_OVERRIDE=0` | TF32 silently drops mantissa bits from Ampere onward. This covers paths not routed through JAX's precision setting, including cuDNN convolutions. |
| `CUBLAS_WORKSPACE_CONFIG=:4096:8` | cuBLAS requires a fixed workspace before it guarantees deterministic results across runs. |

Considered and deliberately **not** pinned: `--xla_gpu_enable_cublaslt` and
`--xla_gpu_triton_gemm_any`, both accepted by this build. They select which GEMM
implementation runs rather than whether it is deterministic, so pinning them
would freeze a performance decision under the name of determinism.

## 3. What it delivers

**Same-device reproducibility across processes.** Three independent sessions,
nine runs, one weight digest. Measured on one device; see §5.

## 4. What it does not deliver

**Cross-device agreement is not established, in either direction.** These
settings fix the order of operations within one device. Whether two devices with
different streaming-multiprocessor counts, memory hierarchies or instruction sets
compute the same floating-point result under this configuration is
**unmeasured**, and it is exactly what a matched two-host test would determine.

Two things follow. This policy is not a guarantee of cross-device agreement, and
nothing here is proof that agreement is unachievable - JAX declining to
*guarantee* cross-platform numerics is not proof that no configuration delivers
them. Until that test runs, plan for divergence without asserting it.

**It also changes the numbers.** The pinned configuration produced a different
result from every unpinned run. Artifacts produced under it are not
interchangeable with artifacts produced without it.

**And the underlying problem is not GPU-specific.** The same divergence was
measured on CPU across instruction-set levels. A GPU adds to it; it did not
create it.

## 5. What it costs

| | Unpinned | Pinned | Difference |
| --- | --- | --- | --- |
| Compile, median of 9 runs | 1.610 s | 2.536 s | **+0.93 s, +58%** |
| Compile, mean of 9 runs | 1.860 s | 2.504 s | +0.65 s, +35% |
| Train execution, median | 0.0451 s | 0.0412 s | **not resolvable** |
| Train execution, mean | 0.1358 s | 0.1368 s | **not resolvable** |

Measured on a two-step reference workload, nine runs per condition.

The compile figure is a fixed per-run overhead and amortises over a real training
length. The execution overhead is the one that scales, and at this sample size it
is **not resolvable**: median and mean disagree in sign, both dominated by
per-session warm-up. No execution figure is given, because the measurement does
not support one. Experiment 2 of `GPU_NEXT_EXPERIMENTS_SPECIFICATION.md` is where
it should be measured at a scale that can resolve it.

## 6. What it means for fairness

Two validators on different devices may compute different weights; §4 records
that this remains unmeasured. Where they do, the continuous score legs absorb the
difference smoothly - a small numeric difference moves a score by a small amount.
How small is a property of each metric, and is not a fixed ratio carried over
from any earlier measurement.

**A mandatory hard gate does not.** It is a step function: a value on one side
passes and on the other the submission is rejected entirely with
`MANDATORY_GATE_FAILED`, not deducted. So residual cross-device divergence does
not degrade a score smoothly near a gate threshold - it flips the outcome.

That is where divergence stops being noise and becomes unfairness, and it is a
protocol and scientific question rather than an engineering one. The options are
written up in `.agent/evidence/wave_c/c-core-19-gate-robustness-options.md` and
none is implemented.

## 7. Provider freedom is preserved

This policy constrains the **configuration**, not where it runs. Per D3 of the
owner's recorded decisions, a validator may use whatever provider they choose,
and qualification attaches to a backend profile rather than to a provider or a
host. Nothing here prescribes a machine, a datacenter or an ownership model.

## 8. Scope of the measurement behind it

One device: NVIDIA GeForce RTX 3060 Laptop GPU, driver 581.95, CUDA 13, under
WSL2, `jax`/`jaxlib` 0.10.2, inside the pinned worker image. A laptop GPU
qualifies nothing, and this measurement was never intended to. It establishes
that the settings function **on this configuration** - this device, this driver,
this build, this workload. Whether the result holds on another device, driver or
jaxlib build is untested: a one-device experiment establishes a result for that
configuration only.

The reference workload is small: two training steps on a 4,696-parameter model. A
larger workload exercises reduction sizes and op mixes this one does not, and
could behave differently.

## 9. What would change this policy

A measurement showing the configuration fails to hold on a datacenter GPU, or
that it refuses a workload Carbon needs, or that its cost at realistic scale is
prohibitive. Any of those is a finding to act on. None of them is a reason to
relax a hash or choose a tolerance.
