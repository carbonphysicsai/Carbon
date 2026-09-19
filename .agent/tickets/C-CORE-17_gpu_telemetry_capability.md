# C-CORE-17: unestablished GPU telemetry must not certify exclusivity

Status: implemented candidate under programme #209; canonical and delivery gates pending.
Base: `ab3e922e09b942c84018416688f89b9493474b85`.
Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Dependencies: C-CORE-03 accelerator reconstruction controller and its prospective
grant/role contract. Successor to the local, paused C-CORE-15 GPU engineering
workflow; that ticket's authoring is untouched by this one.
Integration owner maintains programme/Hub and downstream delivery.

## Authority

Owner's continuation of the local RTX 3060 diagnostic assignment authorizes
bounded supporting code, tests, documentation and normal PR delivery. Current
Constitution, invariants, delivery/delegation, Hub maintenance, Build Out and
constitutional overlay apply. Domain owners are Research Resource Policy and
Isolated Reconstruction Worker.

No qualification, host maintenance, new grant, campaign, GPU/TPU execution,
image build or network deployment is authorized by this ticket. The controlling
programme pause remains in force and is recorded in the evidence packet.

## Problem

`inspect_gpu_device()` and `verify_device_release()` both read an empty
`--query-compute-apps` result as positive evidence: the first records
`"other_compute_processes": []` and admits, the second concludes the device was
released. An unsupported query and a genuinely idle device return the same empty
output, so emptiness alone cannot carry the exclusivity the strict host contract
requires.

This was observed live, not inferred. Querying one GPU UUID from two sources
seconds apart returned a compute process from one and nothing from the other,
while per-process memory was reported unavailable rather than zero. The
observation establishes inconsistent visibility. It does not measure hidden
allocated bytes and does not prove concurrent numerical execution.

## Scope

KEEP the existing controller, grant, journal, lease, quarantine and cleanup
authorities, the CPU contract, TPU rejection, and every existing direct-call,
role, grant and expiry boundary. Introduce no second controller or ledger.

REPAIR the two observation sites so an observing source whose compute-process
enumeration is not established cannot pass the strict contract:

- `enumeration_capability()` returns `UNSUPPORTED`, `UNESTABLISHED` or
  `ESTABLISHED`, never a Boolean. `WDDM` is `UNSUPPORTED` before any contract is
  consulted, because NVIDIA documents WSL NVML process enumeration as incomplete
  and reports per-process memory as unavailable under that driver model. Every
  other reading is `UNESTABLISHED` by default.
- `ESTABLISHED` requires a contract registered in
  `ESTABLISHED_OBSERVATION_CONTRACTS`, which ships **empty**. A grant field or
  caller argument names which contract is claimed; registration in reviewed code
  is what certifies it, so an operator assertion still cannot.
- Strict admission refuses instead of recording an empty foreign-process list.
- Device release stays unreconciled and keeps the existing quarantine behaviour
  instead of reporting a verified whole-device release.

A driver-model reading is explicitly **not** capability evidence. An earlier
revision of this ticket allowlisted `N/A` and `TCC`; that was withdrawn before
merge because it substituted one unsupported positive assumption for another.
`N/A` reports only that a Windows-only field does not apply, and is also used
for unavailable information.

## Explicitly out of scope

Because the registry is empty, strict admission and verified device release are
currently unavailable on **every** host. That is the intended fail-closed state.
Registering the first observation contract is a separate owner decision needing
its own evidence about that source's visibility and the controls around it; this
ticket proposes none and establishes no WSL profile or exception.

Whether an already-admitted engineering run on an unestablished source should
quarantine on cleanup, rather than never being admitted, is a security-contract
decision returned to the owner rather than decided here.

## Acceptance

Focused regressions in `tests/cpu/test_accelerator_telemetry_capability.py`
cover unestablished and malformed capability readings, empty process output with
plausible zero memory and a disabled display, established sources continuing
through the existing valid path, a reported foreign process still rejected,
capability-query failure, and repeated uncertain cleanup preserving exactly one
quarantine marker. All fixtures are synthetic; no accelerator is initialized and
no host process list is captured.

Fixture success is not hardware acceptance.
