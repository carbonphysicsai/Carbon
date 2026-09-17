# C-CORE-01: core JAX backend observation and coordinated delivery

Programme: issue #209; owner instruction on 2026-09-17 to integrate JAX,
GPU, TPU, Julia investigation and standard MCP with one execution strategy.
Status: draft implementation; native diagnostics passed; canonical acceptance
and Hub integration outstanding. No existing scientific selector is replaced.
Starting main: bf21d2e58544701d45cd5c25033097ea10bc9d7c.

## Bounded first change

Add a lazy explicit JAX local-backend observation primitive in canonical worker
code. It accepts only cpu/cuda/tpu, checks exact local device count/platform,
optional JAX/jaxlib version pins and bounded typed metadata, and returns closed
redacted errors. It never retries a different backend or mutates configuration.

This helper is not integrated into admission or GPU/TPU worker launch yet. It
changes no existing runtime, numerical, scientific, provider, CI or active WAVE
behavior. It has no cloud, wallet, signing or public listener capability.

Backend initialization can acquire hardware resources and lacks its own watchdog.
Future callers must invoke it inside an admitted, deadline-supervised process.
A device observation is not hardware attestation, computation verification,
precision support, security acceptance, a resource grant or scientific evidence.
The x64 field records JAX configuration only, not a claim of TPU FP64 support.

## Working decision C-CORE-01-D1

Select one integration owner and shared existing domain services. Reuse current
profiles, tasks and accounting. The external MCP server and Launchpad wrap those
services; neither defines another evaluator. Deliver a GPU numerical vertical and
an MCP vertical in parallel where executors permit it, then complete the TPU
miner/validator vertical. Prepare TPU access early. Julia remains a finite,
non-blocking optional-worker investigation.

Alternatives rejected: separate provider-specific research stacks, TPU-only
miner support, a handwritten MCP protocol engine, and a second Julia core runtime.
These add divergence or fail the owner's requirements. This initial probe is
reversible and has no automatic runtime consumer. Supersede the implementation
here and the sequencing in the plan if the lead requests a change.

Locations:
- carbon/reconstruction/worker/backend_probe.py
- tests/cpu/test_jax_backend_probe.py
- .agent/plans/CARBON_CORE_PLATFORM_EXECUTION.md

## Diagnostics performed

53 native pytest tests passed under Python 3.13.5 / pytest 9.0.2. Actual installed
JAX/jaxlib 0.9.0.1 CPU observation passed with one local CPU device. Explicit CUDA
and TPU observations returned backend_probe.backend_unavailable without CPU
fallback. No training or benchmark ran. No GPU/TPU device is available here.

The execution environment could not resolve github.com for git clone and has no
Docker executable. A minimal new-file working tree supplied local diagnostics;
it is not a full canonical checkout. The GitHub connector publishes the draft.
No environment/network restriction was bypassed or claimed resolved.

## Finish before delivery

Read the complete current mandatory repository authority, inspect this helper in
the full package and reconcile against concurrent work. Run pinned formatting,
quality, package/import, applicable CPU/invariants and worker regression under
canonical Python 3.11.16; resolve defects without weakening existing checks.

Reconcile Hub source via its maintenance contract, mapping issue #209/core worker
and external-interface work under the current appropriate nodes. Do not overwrite
PR #207's admission work or D5 scientific state. This draft marks HUB_UPDATE_REQUIRED
and does not claim generated navigation is current.

After required acceptance, use the existing Merge gate and expected-head normal
merge. Complete the rest of the platform via the consolidated plan; do not treat
this probe as a complete accelerator profile or close issue #209.
