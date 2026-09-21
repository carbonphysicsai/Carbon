# Validator GPU reconstruction orchestration (C-CORE-20)

Ticket: C-CORE-20. Branch `agent/core-platform-20-validator-orchestration`.
Base: `dbfaec1d` on `main`.
Authority: `docs/development/C_CORE_20_VALIDATOR_ORCHESTRATION.md` on
`agent/gpu-execution-lane-design` (PR #248).

C-CORE-19 made `VALIDATOR_RECONSTRUCTION` admissible on a GPU and recorded, in
its own delivery, that nothing constructed one. This is the caller.

---

## 1. The gap, re-verified before it was closed

`repeats.py:393` calls `reconstruct()` in process. That module contains no
backend, accelerator, profile or device selection of any kind: its only
`profile_digest` is the receipt's recorded value and `as_backend_bytes()` is seed
encoding. Validator reconstruction was direct CPU with no seam through which a
validator run could reach the accelerator controller.

Also re-verified at `dbfaec1d` rather than taken from the handoff: `main` had not
advanced; `C-CORE-20` was free of any branch, ticket file or reference;
`/var/lib/carbon/accelerators` is absent so attempts consumed is genuinely 0; and
the dispatch routes both roles to `_execute_self_service_lane` with the strict
path below it.

## 2. What was built

`carbon/reconstruction/validator_launch.py`, the validator counterpart of
`miner_launch.py`, using the same controller, durable queue and launch store.

**No second orchestration system.** Cancellation and recovery are properties of
the host and its launch store rather than of a lane, so both entry points call
one implementation and differ only in the label on the record written. The two
functions in `miner_launch` gained an optional `schema` argument with their
existing values as defaults; nothing else about them changed, and the miner tests
pass unmodified.

Three properties make it a validator entry point rather than a parameterised
miner one:

**The role is fixed and is not a parameter**, exactly as the miner path fixes its
own. `test_there_is_no_parameter_that_requests_authoritative_use` asserts the
whole signature, so a future parameter named `role`, `lane`, `backend`,
`official`, `eligible` or `image` fails the suite rather than passing review.

**The execution class is Carbon's.** The image is resolved from an
operator-installed record (`validator-worker-image.json`) through the existing
`load_image_identity()` mechanism, and the manifest has **no image field at
all**. Absent rather than ignored: a manifest naming an image - even the correct
one - is refused by the closed record, so the submitted value never becomes part
of the conversation. It is resolved *before* work is claimed, so a host that is
not registered to run validator work does not take work off the queue and then
discover it.

**Identity comes from the queue.** The manifest supplies materials; plan,
reconstruction policy and resource policy digests are each checked against the
binding before anything is staged.

## 3. The connected path now available

```text
manifest + admitted queue entry
  -> ValidatorLaunchRequest (closed record, materials only)
  -> registered_image()            [host record, not the manifest]
  -> queue.claim_next()            [identity from the queue]
  -> binding cross-check           [plan / policy / resource digests]
  -> IsolatedReconstructionController.execute(
         accelerator_role=VALIDATOR_RECONSTRUCTION)   [fixed literal]
  -> _execute_self_service_lane    [host record + doctor admission]
  -> worker profile v6, lane VALIDATOR_ISOLATED,
     assurance BACKEND_QUALIFICATION_REQUIRED_MQ008
```

## 4. Tests, and exactly what they prove

`tests/cpu/test_validator_launch_orchestration.py` - **27 cases.** A synthetic
host root and a scripted container CLI throughout: no device is attached, no
container is created, **no GPU numerics are exercised**. The property under test
is orchestration - which role, which lane, which image identity and which work
binding reach the controller's launch boundary - and a scripted CLI is a faithful
fixture for that and nothing else. Several runs end in `WorkerFailure` at the
export boundary, which is a limit of the fixture rather than of the lane.

**This is not GPU acceptance and no fixture here is labelled as one.**

Positive: the launch reaches the controller carrying the validator role, the
`VALIDATOR_ISOLATED` lane, worker-profile schema v6, the
`BACKEND_QUALIFICATION_REQUIRED_MQ008` assurance with `official_eligible: false`,
the registered image identity, and the exact committed binding - with no grant
loaded and none present.

Negatives, each refusing: a miner manifest presented to validator orchestration;
a validator manifest carrying an image; a missing image record; four shapes of
mismatched image record; materials for a different execution; a changed plan; a
changed seed; a file named outside the manifest's own directory; a non-public
training archive; four malformed manifest shapes; an empty queue; and a replayed
request.

Two findings from writing them, where my expectation was wrong and the code was
right:

- **A replayed manifest is refused as `CONFLICT`, not `UNAVAILABLE`.** The
  durable launch store recognises that the execution already has a launch and
  declines the second. That is a sharper refusal than the empty-queue one I
  predicted, and the test now records the real mechanism.
- **A CPU plan presented with an accelerator role is refused at the environment
  pin, before the controller's own role check.** Both are refusals; the test
  accepts either and asserts the thing that actually matters - that **no
  container is built**, so a CPU reconstruction never proceeds under a record
  saying a GPU role was requested.

`tests/cpu/test_protected_material_isolation.py` - extended from 11 to **14
cases**: the new module imports no protected package, takes only type-enforced
public training data, and writes records containing identities and states only.

## 5. The successful result path, and the one step that needs hardware

`tests/science/test_worker_success_path.py` already carried a **genuinely
trained** artifact through the **real** validator to `ASSOCIATED` on the CPU
lane - nothing fabricated, no digest written by hand, no check relaxed. Two cases
were added beside it rather than duplicating that work:

- The same trained artifact, the same controller and the same validator, driven
  with `VALIDATOR_RECONSTRUCTION`, is **refused** and does not reach
  `ASSOCIATED`.
- The same setup with no accelerator role **does** reach `ASSOCIATED`.

The contrast is what gives the first its meaning: what the refusal isolates is
the role, not the fixture.

So the step that genuinely requires hardware is precise and small:

> **A plan pinning the GPU execution profile, trained on that device, producing
> the artifact the real validator then accepts.**

Everything before it - claiming admitted work, binding materials to committed
identities, resolving the registered execution class, reaching the controller
with the validator role and lane - is covered device-free. That one step is left
for the authorized experiment and is not approximated.

## 6. Hardware and spend

Reported in two parts, because they are two claims and only one of them is about
this ticket.

**Journal.** `/var/lib/carbon/accelerators` is absent, so **0 formal journaled
C-CORE accelerator attempts were consumed by C-CORE-20.** An absent journal
establishes that the formal journal is absent; it is not evidence that no GPU
work has ever run on this device, and must not be read as such.

**This ticket.** C-CORE-20 **attached no device, created no container and
incurred no spend.** No rental, no paid call, no grant, no lease, no quarantine.

**Earlier work, not erased by either statement.** C-CORE-19 did run GPU
determinism work on the owner's device under separate authorization - the D3
characterization, nine runs across pinned and unpinned sessions. That activity
was real and is recorded in `c-core-19-gpu-determinism.md`. It was not journaled
as a C-CORE attempt, and describing it retroactively as one would be as wrong as
pretending it never happened.

The hardware study is proposed and not started:
`docs/development/VALIDATOR_TWO_HOST_EXACT_REPLAY_PLAN.md`. It states its own
precondition - that same-device pinned determinism be re-measured at
representative scale first, because it has only ever been shown at two training
steps on 4,696 parameters, and because the CPU scale measurement showed that
scale does not behave as the earlier evidence assumed. Every cost line is
`REQUIRES_QUOTE` and no comparative cost claim is made.

## 6a. External delivery review, and what it changed

`C_CORE_20_DELIVERY_REVIEW.md` raised one genuine defect and three corrections.

**The defect: cancellation crossed lanes while a docstring implied it did not.**
`_cancel_path` is keyed by execution id alone - neither lane nor schema appears
in it - so `validator_launch.request_cancel` wrote exactly the file a miner
cancel writes, and either lane could stop the other's launch. `recover` states
its lane-independence deliberately; `request_cancel` said "Ask a running
*validator* launch to stop", implying a boundary the filesystem did not have.
Four cancel and recover tests existed and none was a cross-lane negative.

**Decided: cancellation is lane-independent, exactly as recovery is.** An
execution id already names one admitted execution, which ran in one lane, so
putting the lane in the key would disambiguate nothing - it would only create a
way for a *correct* cancel to silently miss. For a cooperative stop whose purpose
is halting spend on rented compute, a cancel that quietly fails to match is the
dangerous failure, not one that reaches across lanes. It grants nothing either
way: `state_root` is operator-private, so anyone who can write a request there
already controls the host, and the request only asks a run to stop at its own
next boundary and clean up after itself.

Both docstrings now say that, and six tests assert it: cancel in each direction,
clearing in either direction, recovery of the other lane's record, that a cancel
still names exactly one execution (lane-independent is not identity-independent),
and that the shared `schema` argument cannot select a role, convert a lane or
alter a durable identity.

**Image injection, finished.** `worker_image`, `image` and an unknown field are
each refused **while carrying the correct installed image**, so refusal comes
from the closed schema rather than a value comparison. The manifest's field set
cannot name a path or host root. `HOST_ROOT` was verified to be a fixed path in
source, not environment-configurable, and a test holds that. A symlinked image
record is now refused - `load_image_identity` followed links, while every other
operator-private input on this path refuses them, and an execution class resolved
through a link is one someone else can repoint.

**Attempt accounting, reworded.** See §6: the absent journal and this ticket's
own zero activity are two separate claims, and neither erases the GPU
determinism work C-CORE-19 genuinely ran under separate authorization.

**Two-host plan, four constraints added.** The circularity one was a real
soundness hole: δ must be derived from previously retained same-device or public
calibration evidence and fixed before the comparison, because choosing it
afterwards rigs the study in either direction. Also: calibration strategies are
selected using public or synthetic DEVELOPMENT material only, since choosing a
near-margin pair by its distance to a protected threshold would disclose that
threshold; larger-margin controls are retained beside near-margin cases; and the
report compares underlying predictions and physical measurements without implying
a production rank or gate that Carbon has qualified none of.

## 7. Untouched, deliberately

`compare_r1`, every scoring gate, `ScoreStatus`,
`ESTABLISHED_OBSERVATION_CONTRACTS`, the strict host apparatus, and the
`repeats.py` CPU path - which gained no backend parameter, because a parameter
there would be the role laundering the design forbids.

Kept separate and not repaired here: #242, #246, #248, #251, and the Workbench
successor.

## 8. Maturity, as distinct states

| State | Earned |
| --- | --- |
| `SPECIFIED` | yes |
| `IMPLEMENTED` | yes |
| `TESTED` | yes, device-free, for orchestration |
| `HARDWARE_EXERCISED` | **no** |
| `SCIENTIFICALLY_QUALIFIED` | **no** |
| `SECURITY_QUALIFIED` | **no** |
| `PRODUCTION_QUALIFIED` | **no** |

The strongest permitted statement:

> Validator GPU orchestration is implemented and engineering-tested; official
> backend qualification remains unresolved.

Not "GPU validator deployable."
