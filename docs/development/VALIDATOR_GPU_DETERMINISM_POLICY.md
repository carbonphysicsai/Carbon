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

**Different GPU models will still produce different weights, and no setting
changes that.** Determinism settings fix the *order* of operations on one device.
They do not make two devices with different streaming-multiprocessor counts,
different memory hierarchies or different instruction sets compute the same
floating-point result. Anyone reading this policy as a guarantee of cross-device
agreement has read it wrong.

**It also changes the numbers.** The pinned configuration produced a different
result from every unpinned run. Artifacts produced under it are not
interchangeable with artifacts produced without it.

**And the underlying problem is not GPU-specific.** The same divergence was
measured on CPU across instruction-set levels. A GPU adds to it; it did not
create it.

## 5. What it costs

| | Unpinned | Pinned | Difference |
| --- | --- | --- | --- |
| Compile | 1.55 - 1.61 s | 2.44 - 2.56 s | **+1.0 s, +63%** |
| Train execution | 0.040 s | 0.041 s | +0.001 s, +2.6% |

Measured on a two-step reference workload. The compile figure is a fixed per-run
overhead and amortises over a real training length; the execution figure is the
one that scales and is **indicative only** at this size. The number is given
rather than an assurance that the cost is small.

## 6. What it means for fairness

Two validators on different devices compute different weights. The continuous
score legs absorb that proportionally - a small numeric difference moves a score
by a small amount.

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
qualifies nothing, and this measurement was never intended to - it establishes
that the settings *function*, which is a claim about the settings and transfers,
rather than a claim about the device, which would not.

The reference workload is small: two training steps on a 4,696-parameter model. A
larger workload exercises reduction sizes and op mixes this one does not, and
could behave differently.

## 9. What would change this policy

A measurement showing the configuration fails to hold on a datacenter GPU, or
that it refuses a workload Carbon needs, or that its cost at realistic scale is
prohibitive. Any of those is a finding to act on. None of them is a reason to
relax a hash or choose a tolerance.
