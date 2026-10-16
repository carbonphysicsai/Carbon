# GPU-MINER-CONTROLS-DIAGNOSTIC-02: nested policy identity

Ticket: `.agent/tickets/GPU-MINER-CONTROLS-DIAGNOSTIC-02.md`.
Status: IMPLEMENTED_WORKING_DECISION, pending tests and delivery.
Primary map: `SYSTEM/AGENT-EXECUTION` (retired Hub; no map edit).

Problem: JAX R5 and Torch R6 actual practice tasks each failed at CONTROLS
with a bare private POLICY and no predicate. The accepted inspector can let
nested host-record rechecks raise before its enum-bearing comparison refusal.
Their exact cause is unknown.

Recommended approach: only in diagnostic mode, convert a bare nested POLICY
to a fixed source-defined site enum only when its private diagnostic is empty.
Leave the original exception untouched for every other caller, preserve
non-POLICY and all nonempty private diagnostics,
and retain every check. Implement in `docker_runtime.py`, test five recheck
sites in `test_gpu_self_service_controls.py`. The carrier's existing private
allowlist and public result behavior need no change.

Alternatives rejected: raw logs or device values would widen disclosure;
blind retry loses the failed control; relaxing policy would assume security
acceptance. This is removable without changing historical results. A lead
reversal changes this wrapper, enum list, focused test, and ticket. No public
interface, later-wave authority, or human-reserved input is selected.
