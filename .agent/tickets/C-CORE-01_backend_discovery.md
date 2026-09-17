# C-CORE-01: core JAX backend observation and coordinated delivery

Programme: issue #209; MCP workstream #210.
Status: draft implementation; original native diagnostics passed; canonical
acceptance and Hub integration outstanding. No scientific selector is replaced.
Starting main: bf21d2e58544701d45cd5c25033097ea10bc9d7c.

## Current scope amendment: C-CORE-01-D2 (2026-09-17)

The owner now requires Julia as a Carbon-native capability for miner research,
validator physics/reference checks through a Python bridge, and Workbench
challenge design. This supersedes C-CORE-01-D1's optional/research-only Julia
restriction. It is an implementation mandate, not scientific qualification,
new spending, protected-data processing or deployment authority.

JAX remains the GPU/TPU model training, prediction and independent reconstruction
framework for both miners and validators. Julia provides scientific analysis,
reference and design services through a stable Python-facing API. Python remains
the control plane. No PyTorch shortcut or Julia ML migration is requested.

The complete replacement execution prompt is:
`.agent/plans/CARBON_CORE_PLATFORM_EXECUTION.md` (v2).

Use one integration owner and existing domain services. Complete a JAX accelerator
track, a native Julia track with actual validator and Workbench consumers, and a
standard MCP track. Neither GPU/TPU nor Julia is a reason to block unrelated work;
all remain required programme deliverables. Preserve accepted #207 and the
separately owned #206/#208 campaigns and grants.

The Python bridge invokes pinned Julia functions/scripts and converts typed data;
it does not transpile arbitrary code or inject an interpreter into the trusted
controller. A dedicated supervised worker may use JuliaCall/PythonCall or a typed
Julia subprocess. Validate physical units, coordinates, axes, dtypes and artifact
identity. Disable request-time installs and untrusted startup/project hooks.

Read current ReferencePolicy/TruthAsset/measurement contracts and
`Design_Specs/Runtime_Julia_Truth_Oracle.md`. Its historical name grants no truth
authority. Implement validator-side Julia checks and their verification harness;
score-affecting/protected use still follows the actual qualified policy. Do not
request the same architecture approval again. Reference failure is not candidate
failure, and two languages agreeing is not independent proof.

Read Business/Workbench authority and integrate draft checks, actual solves,
parameter/sensitivity evidence, persisted artifacts and handoff. Results bind the
exact draft revision; edits invalidate dependent evidence or require explicit
valid reuse. Preserve rights and existing UNASSESSED/NOT_QUALIFIED/request-only
semantics. Protected validator results cannot enter Workbench or public MCP.

Native Julia adoption is selected. Benchmarks choose useful methods and defaults;
they must not silently defer the entire capability. Individual unsupported tasks
remain explicit with a concrete implementation or validation next step.

Alternatives rejected: unrestricted Julia eval in validator processes; automatic
Julia-to-Python source translation; a second grading/ledger system; restoring
archived services wholesale; treating Julia as a drop-in source of physical truth.

Change path: supersede D2 and the v2 plan, then reconcile issue #209 and #210 and
actual consumer tickets. Old scientific evidence and numerical policies remain
unchanged. Notify the technical lead under DELEGATED_DECISION_PROTOCOL.

## Bounded first code change

The existing code in this PR is still a lazy explicit JAX local-backend observation
primitive in canonical worker code. It accepts only cpu/cuda/tpu, checks exact
local device count/platform, optional JAX/jaxlib pins and bounded typed metadata,
and returns closed redacted errors. It never retries another backend.

This helper has no runtime admission or accelerator-launch consumer. It changes no
existing numerical/scientific/provider behavior. Backend initialization can acquire
resources and lacks its own watchdog; invoke inside an admitted supervised process.
An observation is not attestation, computation verification, precision support,
a resource grant or qualification. The x64 field is a configuration observation.

Locations:
- carbon/reconstruction/worker/backend_probe.py
- tests/cpu/test_jax_backend_probe.py
- .agent/plans/CARBON_CORE_PLATFORM_EXECUTION.md

## Historical C-CORE-01-D1 scope

D1 selected one integration owner, shared services, GPU research/reconstruction and
MCP implementation with TPU preparation. Its Julia-only-investigation clause is
superseded by D2. No previous test or scientific result is relabelled.

## Diagnostics previously recorded

53 native pytest tests passed under Python 3.13.5 / pytest 9.0.2. Actual installed
JAX/jaxlib 0.9.0.1 CPU observation passed with one local device. Explicit CUDA and
TPU observations returned backend_probe.backend_unavailable without CPU fallback.
No training or benchmark ran. The original environment had no GPU/TPU or Docker;
Git clone could not resolve github.com. A minimal working tree supplied native
diagnostics, not full-package/canonical acceptance.

The D2/v2 amendment changes planning and scope only. It adds no Julia runtime code
or new runtime-test evidence. No worker, allocation or background coding agent
started through this amendment.

## Finish before delivery

Review the helper in the current full package. Run pinned formatting, quality,
package/import, applicable CPU/invariant and worker tests under the canonical
environment. Do not weaken checks. Reconcile Hub sources under their maintenance
contract and preserve concurrent ownership. HUB_UPDATE_REQUIRED remains open.

Use the existing Merge gate and expected-head normal merge after acceptance.
Continue the integrated programme; do not close #209/#210 on this probe or a plan.
Real Julia consumer, GPU/TPU numerical, Workbench and external-client acceptance
remain required. Execute only within matching resource and data authority.
