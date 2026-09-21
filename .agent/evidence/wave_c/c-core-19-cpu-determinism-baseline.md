# CPU determinism baseline (P8)

Recorded 2026-09-20 under programme #209, ticket C-CORE-19.
Measurement evidence. This is not a qualification, an acceptance record, or
authorization to attach a device. It sets no tolerance and qualifies no backend.

Answers the prerequisite question P8 poses in
`docs/development/GPU_INITIAL_POLICY.md`: **is this workload deterministic at all
under fixed identities?** Establishing it before any GPU attempt costs nothing —
no device, no hardware authority, no spend — and it changes what the four
authorized attempts would be able to conclude.

## 1. What was measured

The same registered strategy, trained repeatedly on CPU under **identical R0
identities**: the same compiled construction plan, the same public TRAIN archive,
the same derived seed, the same execution reference. Nothing was varied between
runs except the directory the artifact was written to.

That last point is the whole method. `reconstruct()` returns
`_validate_existing()` when its `artifact_path` already exists, so repeating a
call against one path measures cache reuse rather than determinism. Each repeat
here trains independently into its own path.

Three repeats for each of the two registered backbones, on the Linux host
described in §4.

## 2. Result

| Property | Result |
| --- | --- |
| `checkpoint/state.npz` — the trained weights | **BIT-IDENTICAL** across all repeats, both backbones |
| `checkpoint/manifest.json` | **BIT-IDENTICAL** across all repeats, both backbones |
| Top-level `manifest.json` | **DIFFERS** every run |
| `ReconstructionReceipt.artifact_digest` | **DIFFERS** every run — 3 distinct digests from 3 repeats |

Distinct weight digests observed, from three repeats each:

| Backbone | Distinct weight digests | `sha256` |
| --- | --- | --- |
| `fno` | 1 of 3 | `41b15c91a82214a629fa11b9d05dee4b748fff4c200c6b3e6854cf9939a7ccbc` |
| `deeponet` | 1 of 3 | `e26457408144f579ca7d457fd384d7c0357d98fd8ecc9ccf863dd7b57d381a48` |

**The workload is deterministic on CPU under fixed identities.** Every numerical
output was byte-for-byte identical across independent trainings.

## 3. The finding that matters for MQ-008

The artifact digest is **not** a usable determinism signal, and this is
structural rather than incidental.

`artifact_digest` is `_tree_digest(path)` over the whole artifact directory. That
tree includes the top-level `manifest.json`, which records `compile_seconds` and
`train_execution_seconds` — two wall-clock measurements. 25 of the manifest's 27
keys were identical across runs; those two were the only differences found
anywhere in the artifact.

So the artifact digest varies between two runs that produced identical weights,
and it would vary between a CPU run and a GPU run whatever the device did.

> **An evidence specification that compares artifact digests would report
> nondeterminism in every case, and would be measuring a clock.**

Stated plainly because the four-attempt batch cannot be un-spent: a comparison
designed around `artifact_digest` would consume attempts and conclude nothing.
Comparisons belong on `checkpoint/state.npz`, or on quantities the evidence
specification names explicitly.

No change was made to the manifest to "fix" this. Removing the timings would
change the digest of every artifact ever produced, which is a migration under an
explicit decision, not a repair to make a measurement convenient. The timings are
also genuinely useful. What is recorded here is which digest answers which
question.

## 4. Scope and limits

Measured on one host: Ubuntu 24.04 under WSL2, kernel
`6.18.33.2-microsoft-standard-WSL2`, CPython 3.11.16, JAX CPU backend
(`jaxlib` without CUDA; the run log records the CPU fallback explicitly).

This establishes determinism **for this workload, on this host, within a single
environment**. It does not establish:

- determinism across hosts, CPU architectures, or JAX/`jaxlib` versions;
- determinism on any GPU, which is exactly what remains unmeasured;
- any tolerance, for any comparison, on any backend.

It does **not** remove the need for repeats on GPU. Separating GPU run-to-run
variation from device attribution still requires at least two GPU runs of an
identical configuration, which is the batch-sizing question §6 of the policy
leaves open.

What it does establish is the attribution rule: because CPU repeats are
bit-identical, a GPU divergence observed under the same identities is
attributable to the device and its kernels rather than to the workload. That is
what P8 said it would narrow, and it does.

## 5. Reproducing it

`tests/science/test_cpu_determinism_baseline.py` performs the same measurement as
a regression: two independent trainings into distinct paths, weights compared
byte-for-byte. It also pins the artifact-digest instability, so that if either
property changes the change is visible rather than silent.

## 6. Maturity

`MEASURED` on the host in §4. Not `SCIENTIFICALLY_QUALIFIED`, not
`SECURITY_QUALIFIED`, not `PRODUCTION_QUALIFIED`. No hardware is qualified, no
attempt was spent, no device was attached, and `ESTABLISHED_OBSERVATION_CONTRACTS`
remains empty.
