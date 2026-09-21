# GPU determinism under pinned settings (D3)

Recorded 2026-09-20 under programme #209, ticket C-CORE-19.
Measurement evidence, produced on the owner's device under the owner's explicit
authorization to spend GPU attempts on Carbon development testing.

**It qualifies nothing.** It is a determinism check - whether the settings
function - not MQ-008 qualification evidence. MQ-008 qualifies a narrow backend
profile on the hardware validators will actually use; this is a laptop GPU under
WSL2 and it qualifies that hardware no more than the W6 withdrawal said it would.
No tolerance is set. Raw per-session records are in
`c-core-19-gpu-determinism/`.

## 1. The result

| Condition | Sessions | Within a session | Across sessions |
| --- | --- | --- | --- |
| **Unpinned** | 4 | bit-identical, 3 of 3 every time | **4 distinct weight digests** |
| **Pinned** (D2 configuration) | 3 | bit-identical, 3 of 3 every time | **1 digest, `beffb28947778594…`** |

> **An unpinned GPU reconstruction does not reproduce across processes.** Every
> session computed a self-consistent answer and a different one from every other
> session. That is exactly the question R1 asks - does a repeat execution
> reproduce the numerical results - and unpinned, on this device, the answer is
> no.

> **Pinned, it does reproduce.** Three independent sessions, nine runs, one
> digest.

Observed unpinned digests: `1b50674aa7dfba36…`, `8c876ef4a9a69dfc…`,
`7efe63f71b8532e3…`, `59dcb8d72da8e358…`. The last three are retained as files;
the first came from a session whose record was overwritten by a re-run and
survives only in the transcript, so four were observed and three are retained.

## 2. What this establishes, and what it does not

**Establishes.** The determinism configuration functions: it turns
cross-process divergence into cross-process reproducibility on this device, for
this workload, reproducibly. And `--xla_gpu_exclude_nondeterministic_ops=true`
did **not** refuse this workload - a real risk, since that flag makes an op with
no deterministic implementation a hard failure rather than a silent result.

**Does not establish.** That any *other* device reproduces, that two *different*
devices agree with each other, or that any of this is qualified. It also does not
establish behaviour at realistic workload size: the fixture trains two steps on
a 4,696-parameter model, so the reduction sizes and op mix that make atomics and
split-reduction order matter are barely exercised. A larger workload could
diverge in ways this one cannot show.

**A caution about the within-session result.** Unpinned runs were bit-identical
*inside* a process. Anyone measuring determinism by repeating a run in one
process would have concluded the problem does not exist. It takes separate
processes to see it, which is worth stating because it is an easy measurement to
get wrong.

## 3. Pinning changes the numbers

`beffb28947778594…` is not any of the unpinned digests. The configuration does
not merely stabilise the result - it produces a **different** result.

That matters for adoption. Artifacts produced under the pinned configuration
differ from artifacts produced without it, so this is a change of behaviour and
not a free improvement. Nothing existing is retroactively wrong; it is that the
two are not interchangeable.

## 4. The throughput cost, measured

D2 asks for the number rather than an assurance that it is small.

| | Unpinned (median) | Pinned (median) | Difference |
| --- | --- | --- | --- |
| Compile | 1.55 - 1.61 s | 2.44 - 2.56 s | **about +1.0 s, +63%** |
| Train execution | 0.040 s | 0.041 s | +0.001 s, +2.6% |

The compile cost is where disabling autotuning lands, and it is substantial in
relative terms. It is also a fixed per-run overhead: at a realistic training
length it amortises, while the execution overhead is the one that scales. The
+2.6% execution figure is measured on a two-step run and is **not** a reliable
estimate of the cost at a real workload size. SCI should treat the compile number
as solid and the execution number as indicative only.

## 5. It confirms D1 was necessary

The pinned and unpinned runs computed different weights. Their recorded
environments now differ too, in exactly the three keys responsible:
`xla_flags`, `nvidia_tf32_override`, `cublas_workspace_config`.

Before D1, both would have recorded a byte-identical `observed_environment` while
producing different numbers - the same failure the CPU instruction-set finding
exposed, reproduced on a GPU. D1 closes it, and this is the direct verification
on runs that genuinely diverged.

## 6. Method

Materials were staged on the host as the worker stages them - a GPU-profiled
construction plan, a public TRAIN archive, and the derived seed - and the real
`reconstruct()` ran inside the pinned worker image with the device attached.
Admission was the real one: the miner-lane check ran, and earlier attempts were
correctly refused when the device kind was not stated and when the environment
was ineligible.

Repeats were run **inside** one container rather than one admission per repeat,
which is what made three repeats per session affordable. That tests the numerics
rather than the orchestration; reaching `ASSOCIATED` through the controller is a
separate question and is not claimed here.

Two setup defects were found and fixed before any measurement, which is the
"free crash discovery" a local run was expected to buy: the worker scratch had no
`TMPDIR` directory for `ptxas` intermediates, and a results path was not writable
by the container's non-root user.

## 7. Maturity

`MEASURED` on one device: NVIDIA GeForce RTX 3060 Laptop GPU, driver 581.95,
CUDA 13, under WSL2, `jax`/`jaxlib` 0.10.2 with the CUDA 13 plugin, inside worker
image `sha256:e4a2014daa9abc4e…`.

Not `SCIENTIFICALLY_QUALIFIED`, not `SECURITY_QUALIFIED`, not
`PRODUCTION_QUALIFIED`. `ESTABLISHED_OBSERVATION_CONTRACTS` remains empty and no
observation source was registered.
