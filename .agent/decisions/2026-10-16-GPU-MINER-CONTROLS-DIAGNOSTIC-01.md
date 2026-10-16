# GPU-MINER-CONTROLS-DIAGNOSTIC-01: private failed-control identity

Ticket: `.agent/tickets/GPU-MINER-CONTROLS-DIAGNOSTIC-01.md`.
Status: IMPLEMENTED_WORKING_DECISION on branch
`codex/gpu-miner-controls-diagnostic-01`; Root owns validation and delivery.
Primary map: `SYSTEM/AGENT-EXECUTION` (retired Hub; no map edit).

The actual JAX practice task failed `CONTROLS`/`WorkerCode.POLICY` before
fit/predict, but its private record did not identify which comparison refused.
Recommend a fixed source-defined first-predicate enum only when the trusted
battery-practice carrier opts in. The inspector retains all comparisons and
refusals, and other callers default to empty policy diagnostics. The carrier
copies the exact enum only to its owner-only task failure record for
`BATTERY_PUBLIC_PRACTICE` + `CONTROLS` + `WorkerCode.POLICY`.

Implemented in `carbon/reconstruction/worker/docker_runtime.py` and
`carbon/development_session/research_carrier.py`; tests are
`tests/cpu/test_gpu_self_service_controls.py` and
`tests/cpu/test_fixed_practice_failure_diagnostics.py`. No public API, score,
scientific or security acceptance, authority, or cleanup policy changes.
Graphite and every other existing caller retain the default empty diagnostic.

Rejected alternatives: a blind retry cannot distinguish controls; Docker
event polling races immediate cleanup; retaining raw inspect, environment,
labels, values, or GPU output risks disclosure; weakening a failed control
would invent security acceptance. The enum field can be removed prospectively
without reinterpreting existing outcomes. A lead change would supersede this
decision in this file, adjust the two runtime files and focused tests, and
review the complete resulting diff. No human-reserved input is selected;
Root's future TEST dispatch remains separately gated.
