# The validator exam environment

**Status: declared, not qualified.** This document states what a validator runs
reconstruction under. It does not establish that the environment is
scientifically qualified, and declaring an environment is not qualifying it. The
backend profile's support status is governed by MQ-008 under R0/R1/R2 at gate
G4, owned by SCI + SRE, and is unresolved.

## Why this exists

A miner submits a **declarative training strategy**, not a trained checkpoint.
The validator reconstructs it and trains from scratch. So the miner's own
hardware is unconstrained — it does not matter what they used to arrive at the
design — but the miner is entitled to know what the design will be *run on* when
it is graded.

That is the obligation this document discharges: not a constraint on miners, but
a disclosure by Carbon. Miner hardware stays free; the exam environment is
published so a miner can consult it before submitting.

**No provider is prescribed.** A validator may run this environment with any
provider, on any host they choose. Qualification attaches to the backend profile,
not to a provider or a machine.

## The environment

### Backend profile

| | |
| --- | --- |
| Profile | `carbon.c03.linux-x86_64-cpu.development.v1`, version `1.0` |
| Scope | `UNQUALIFIED_PUBLIC_DEVELOPMENT` |
| Backend | JAX CPU |
| Support status | **unresolved** — `compare_r1` returns `BACKEND_UNSUPPORTED` until MQ-008 qualifies a profile |

A GPU backend profile is a separate profile and a separate qualification. It is
not covered by this declaration, and running on a GPU does not inherit this one.

### Pinned versions

The environment lock is the authority; these are its principal entries, as
recorded in a reconstruction's `observed_environment`:

| | |
| --- | --- |
| Python | 3.11.16 |
| `jax` / `jaxlib` | 0.10.2 / 0.10.2 |
| `numpy` | 2.4.6 |
| `scipy` | 1.17.1 |
| `equinox` / `optax` / `chex` | 0.13.8 / 0.2.8 / 0.1.92 |
| `foundax` | 0.2.0 |
| Platform | Linux, `x86_64` |

### Precision and numerics

| | |
| --- | --- |
| Parameter dtype | `float32` |
| Complex dtype | `complex64` |
| 64-bit mode (`x64`) | disabled |
| Matmul precision | `highest` |

### Resource envelope

| | |
| --- | --- |
| Concurrency | 1 per launch; concurrent launches now possible (see below) |
| CPU | 2 (quota); cpuset resolved from the host |
| Memory | 4 GiB, swap 0 |
| PIDs | 256 |
| Scratch | 512 MiB, 8192 inodes |
| Output | 128 MiB, 1024 members |
| Productive deadline | 600 s |
| Graceful cancellation | 5 s |
| Cleanup confirmation | 30 s |

Until C-CORE-19 the cpuset was required to be exactly cores `0,1`, which made
two concurrent reconstructions impossible on any host - both demanded the same
two cores. The cpuset is now resolved from the host, so a validator scoring a
queue is no longer serialised by a string literal. The per-launch quota is
unchanged at 2 CPUs and 4 GiB.

Measured under N2: usable core count (1, 2, 4, 8), memory ceiling (2, 4, 8 GiB)
and two simultaneous runs on disjoint cpusets produced byte-identical weights
across eighteen runs. Sizing is therefore a cost and throughput question on this
evidence, not a reproducibility one - on one host, one backbone, at two steps.

### Containment

Network `none`; read-only root; all capabilities dropped; non-root `65532:65532`;
`no_new_privileges`; `docker-default` seccomp; no restart. The worker image is
pinned and immutable, and its identity is bound into every launch.

### Allocator

No allocator policy is pinned for the CPU backend beyond the memory ceiling
above. The GPU overlay pins its own allocator settings and is not part of this
declaration.

## A known limitation, disclosed rather than omitted

The pinned set above does **not** determine the numerical result on its own.

Measured under W3: the same registered strategy, under identical R0 identities
and an identical `observed_environment`, produces **different weights** depending
on the CPU instruction-set level the backend compiles to. AVX2, AVX and SSE4_2
gave three distinct results, and every identity Carbon records was the same
across all three.

So two validators could both run exactly this declared environment, on different
machines, and compute different weights — and nothing in the record would
distinguish them.

This document does not resolve that. It discloses it, because a miner reading an
exam environment is entitled to know what it does and does not fix. Whether the
exam environment should additionally pin a CPU feature level is a scientific
decision that interacts with validator provider freedom, and it is recorded as an
open owner question in the W3 evidence packet rather than settled here.

## What this document is not

It is not a qualification, a tolerance, an acceptance, or a claim that
reconstruction on this environment is reproducible across hosts. It is a
statement of what a validator runs, published so that miners can see it.
