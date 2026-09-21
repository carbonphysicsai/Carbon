# C-CORE-20 — validator GPU reconstruction orchestration

Owner-directed continuation from merged C-CORE-19. Close the integration gap
between an admissible `VALIDATOR_RECONSTRUCTION` role and a shipped path that
constructs and drives one.

---

## Verified before writing. Do not redo this

Checked against `origin/main` on 2026-09-21:

- **`origin/main` is `dbfaec1d`** - the handoff's expected head, and main has not
  advanced past it.
- **`C-CORE-20` is free.** No remote branch, no ticket file, no reference anywhere
  on main. The highest existing is `C-CORE-19`, so `C-CORE-20` is the correct
  successor. Claim it.
- **`/var/lib/carbon/accelerators` is absent** - attempts consumed is genuinely 0.
- **The dispatch change is real.** `controller.py` routes both
  `MINER_RESEARCH` and `VALIDATOR_RECONSTRUCTION` to
  `_execute_self_service_lane`; the strict path sits below it, in the tree and
  unreachable, with no fallback in either direction. `lane_for_role` still maps
  the roles to `MINER_CONTAINED` and `VALIDATOR_ISOLATED` respectively.

Re-verify anything you are about to depend on. Everything else in the handoff is
unverified by me.

## The call path, traced

**The gap, precisely.** `carbon/reconstruction/repeats.py:393` calls
`reconstruct()` **in process**, and that module contains **no backend,
accelerator, profile or device selection of any kind** - its only `profile_digest`
is the receipt's recorded value and `as_backend_bytes()` is seed encoding. So
validator reconstruction today is direct CPU with no seam through which a
validator run could reach the accelerator controller.

**The template already exists.** `carbon/reconstruction/miner_launch.py` is the
working orchestration for the other role: `launch()` at :267, `request_cancel`,
`cancel_requested`, `clear_cancel`, and `recover()` at :384. Its docstring at :286
states the exact property this ticket needs:

> The role is fixed to `MINER_RESEARCH` and is not a parameter, because a caller
> that could choose it could choose the lane.

And at :278 it states the identity rule this ticket needs:

> they already exist in the durable queue, put there by whoever admitted the
> work, and this claims one rather than inventing a second, weaker identity
> beside it.

`ASSOCIATED` is `WorkerLaunchState.ASSOCIATED` in `carbon/execution/worker.py`.

---

## Design

**KEEP then WRAP. Do not build a second orchestration system, and do not add a
backend parameter to the `repeats.py` path** - a parameter there would be exactly
the role laundering the design forbids.

Build the validator counterpart of `miner_launch.py`, with the role **fixed to
`VALIDATOR_RECONSTRUCTION` and not a parameter**, claiming work from the existing
durable queue rather than constructing a parallel identity. Mirror its surface:
launch, cancel request and clear, recover.

### Binding

Carry the identities the queue already committed to - compiled plan, challenge and
case identities, seed and randomness commitments, policy and resource identities,
worker profile, image and runtime and environment identities, numerical execution
configuration, and the protected input binding where applicable. Refuse a manifest
naming different work than the queue admitted, the way the miner path already
does. Invent no weaker identity beside it.

### No fallback, in any direction

A validator GPU rejection must not retry through the miner lane, a miner rejection
must not retry through the validator lane, and **CPU must not silently substitute
when GPU was the declared validator backend.** Where policy selects CPU, CPU stays
CPU. A role reaches exactly one path, chosen before admission is attempted - the
property `controller.py` already states and must keep.

### Validator execution class is Carbon-owned

Resolve a registered, pinned validator GPU worker image through the existing image
mechanisms. A miner submission must not be able to choose the device UUID,
provider, driver, image, execution flags or numerical environment. Keep class
identity distinct from individual host and device identity, and **do not erase
host differences to make a reproducibility comparison pass.**

### MQ-008 gating is untouched

Do not modify `compare_r1` to return supported, do not add a default tolerance,
do not round or quantize, do not change scoring gates, do not build a median or
consensus evaluator. Any path treating a GPU reconstruction as authoritative must
still meet the existing backend qualification decision.

---

## Acceptance, device-free first

**Positive.** A legitimate validator reconstruction reaches the real controller
launch boundary carrying `VALIDATOR_RECONSTRUCTION`, the validator lane label,
exact worker/profile/image identities, and the exact committed work binding.

**Negative - each must refuse.** Miner role presented to validator orchestration;
validator request bearing miner authority; missing or mismatched image; mismatched
profile; changed plan or recipe; changed seed or binding; changed protected input
identity; missing backend eligibility where authoritative use is requested;
malformed or unsupported lane; replayed request whose identities differ; and any
attempted fallback to another lane.

**Where a test mocks execution, state exactly what it proves.** Do not claim
controller acceptance from a helper-only test, and **do not label a CPU-backed
fixture "GPU acceptance."** A fixture may use CPU or synthetic execution only
where the property under test is orchestration rather than GPU numerics, and must
say so.

**Successful result path.** Carry a legitimate reconstruction through request to
controller to worker result to validation to associated result, without
fabricating a checkpoint or bypassing the real validator. C-CORE-19 already did
this for the CPU lane with a genuinely trained artifact and two negative
counterparts - reuse that approach. If one final step genuinely requires GPU
hardware, isolate exactly that step and leave it for the authorized experiment.

**Protected material.** Retain and extend the negative tests showing no path from
protected evaluator inputs into Launchpad, research MCP, miner GPU service, public
capability or exam-environment disclosure, or research export. Do not log
protected values into new orchestration or performance evidence.

---

## Boundaries

**Hardware.** Do nothing that needs a device beyond what current authority already
covers. If no authority covers a GPU invocation, **stop only the hardware
operation and finish everything device-free**, then produce a finite proposed
test rather than assuming permission. Do not rent matched hosts and do not start
MQ-008 qualification because orchestration is ready.

**Keep separate, do not repair here.** #242 archive/tamper defect, #246 Linux
workspace delivery, #248 GPU design documents, #251 Launchpad product integration,
and the Workbench successor's repairs. Coordinate shared Hub writes and preserve
other workstreams' events; do not overwrite generated Hub files from another
workstream or hand-merge generated pages instead of reconciling.

**Delivery.** Source records first, preserve immutable change events, reconcile
the authority snapshot, regenerate Hub projections from source, validate in the
real PR and diff environment. Do not weaken the classifier, invariant suite or
merge gate, and do not weaken tests to make this work.

---

## Report these as distinct states. Do not collapse them

`SPECIFIED`, `IMPLEMENTED`, `TESTED`, `HARDWARE_EXERCISED`,
`SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`, `PRODUCTION_QUALIFIED`.

Until MQ-008 is satisfied, the strongest permitted statement is:

> Validator GPU orchestration is implemented and engineering-tested; official
> backend qualification remains unresolved.

**Do not say "GPU validator deployable."**

Report starting and final head identities, files and contracts changed, the exact
connected path now available, tests and the revisions they ran against, what
remains untested, hardware attempts and spend actually used, issues kept separate,
and the PR, accepted CI and merge identity.

## After delivery, propose but do not start

A two-same-class-host exact-replay plan through the orchestration delivered here:
execution-class definition, provider and host requirements, host count,
repetitions and sessions, workload set, fresh-process and compile requirements,
numerical values and digests to compare, scientific outputs to compare, wall and
runtime bounds, cost from real quotes where available or marked `REQUIRES_QUOTE`,
retained evidence, cleanup, and stop conditions. That becomes the MQ-008 basis.

Continue through ordinary implementation and test failures. Do not return after
each helper commit. Stop only where a genuine permission, resource or scientific
decision blocks the affected operation.
