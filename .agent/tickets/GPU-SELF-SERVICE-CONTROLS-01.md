# GPU self-service effective controls and task-owned cleanup

Status: working contract; Root reserved source repair 2026-10-15.
Base: c22c988be3d6663fd0fabe4737b9e05947203e74.
Primary map: SYSTEM/AGENT-EXECUTION; Hub retired by owner direction.

Authority: C-CORE-19_gpu_miner_and_validator_lanes.md,
docs/development/GPU_EXECUTION_LANES.md and the 2026-09-21 owner amendment
docs/development/GPU_VALIDATOR_ADMISSION_DECISION.md. The amendment admits
both registered roles under SELF_SERVICE_HOST_AUTHORITY, with distinct miner
and validator assurance. Admission is not backend qualification or official use.

Seam: IMPLEMENTATION_LAG in GPU execution admission and cleanup. The actual
c41 diagnostic captured CONTROLS/POLICY followed by CLEANUP/UNCERTAIN. It did
not identify the earliest individual daemon predicate. Independently, source
sends self-service profiles into strict enumeration despite the empty established
contract registry, and fixed practice omits the task-owned allocation record
that existing controller and miner-script paths create before container creation.
Preserve both failed tasks, conservative accounting and their actual limitations.

KEEP CPU containment, immutable image/device/launch/profile binding, environment
pins, resource/deadline/output controls, strict grants, local approvals, strict
observations, strict/local allocation ownership, quarantine, and history.
REPAIR verified self-service authority dispatch for both existing roles. Give
it its own host-record label and honest device-identity observation/registered
role assurance. Never enumerate foreign processes, infer exclusivity, fabricate
empty contention observations, or label it strict/local development authority.

REPAIR the fixed-practice writer using existing task-owned allocation APIs
before create, under the existing short check/create serialization. Cleanup
continues to require exact allocation ownership and dispatches by the recorded
authority. Do not universally discharge missing allocation records or infer
whole-device release. No new cleanup/watchdog authority supplied as a Boolean.

Owned manifest: this ticket/decision; reconstruction/worker/docker_runtime.py;
reconstruction/worker/accelerator_runtime.py; necessary fixed-practice plumbing
in development_session/research_carrier.py; focused regression tests. One PR.
Open PRs 1398-1401/1385/1255/1246/1222 do not overlap the reserved runtime files;
recheck the final manifest before push. Other source lanes remain single writers.

Plan: contract/decision; authority-specific observation and labels; existing
allocation-before-create plumbing; full shared control and cleanup regressions;
author static checks; Product complete independent engineering/security review;
Root combined canonical validation and CI; Root normal merge/adoption/GPU trials.
Baseline: existing unchanged core passed CI38838942191; this is not a fresh
focused baseline. Root queued focused validation after the frozen repair.

DoD: both self-service roles pass correct real control comparisons without strict
enumeration/release; all CPU controls and device/image/profile/label mismatches
still refuse; forged authority/dual labels cannot downgrade strict/local;
missing/foreign/malformed allocation records fail closed; fixed practice records
the correct owner before create, cleanup/cancel/recovery retains its accounting.
Strict/local regression controls stay intact. No author app imports/tests/host
or provider execution. Root owns canonical tests, actual CUDA and merge.

Maturity ceiling: bounded implemented/tested engineering. No production security,
backend qualification, scientific pass, LIVE or ordinary CUDA acceptance follows
from fixtures or an instrumented diagnostic. User finishline remains actual
ordinary JAX and PyTorch CUDA fit/predict with retained usable results.
