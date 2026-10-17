# GPU-MINER-CONTROLS-DIAGNOSTIC-02: nested policy rechecks

Status: working contract; Root-assigned bounded source repair 2026-10-16.
Base: `c8979fe62357df1c24affd1869d9805731f37b03` (merged main at start).
Primary map: `SYSTEM/AGENT-EXECUTION`; owner-retired Hub has no changed
purpose, placement, status, dependencies, boundary, maturity, or links.

Actual JAX R5 and Torch R6 battery-practice tasks each reached `CONTROLS`,
then returned `FAILED_INFRA/INTERNAL` with a private `WorkerCode.POLICY`
sidecar and no `controls_predicate`. Both tasks were cleaned up and their
leases closed. Neither produced CUDA fit/predict evidence. The accepted
diagnostic cannot name a nested bare policy refusal raised while it rechecks
adapter, device request, create arguments, host record, or GPU environment.
The particular failed recheck is unknown; no mismatch is asserted.

Decision `GPU-MINER-CONTROLS-DIAGNOSTIC-02`: KEEP the existing controls and
carrier; WRAP only these nested policy calls at the diagnostic inspector.
For opted-in fixed battery practice, attach one closed site enum to a bare
`WorkerFailure(POLICY)` with empty private diagnostics. Other callers receive
the original exception; other codes and all nonempty diagnostics remain
unchanged. No observed
value, Docker output, environment, device UUID, path, label, or secret enters
the diagnostic. All admission checks, refusal behavior, and cleanup remain.

Owned paths: this ticket, its decision, `docker_runtime.py`, focused CPU tests.
No public API or scientific/security acceptance changes. Root owns host/GPU
actuation and one fresh TEST task after review and delivery; this source
change cannot itself establish actual CUDA fit/predict. Rejected alternatives:
retrying without a named refusal or relaxing a check. The wrapper is reversible.
No human-reserved value is selected.

Plan: focused regression for each nested recheck and default refusal; source
syntax/static checks; independent review; canonical changed-path CI and normal
one-PR OWNER-DX-03 delivery; then one task-owned diagnostic and bounded repair
or actual fit/predict as the evidence allows. Maturity ceiling: implemented
diagnostic only until exact-tree tests and GPU result prove more.
