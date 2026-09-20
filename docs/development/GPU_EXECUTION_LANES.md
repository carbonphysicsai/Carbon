# GPU execution: scope, lanes and what is deliberately out

**Status: proposal.** It qualifies no hardware, sets no tolerance, creates no
grant and changes nothing about what evaluation accepts. Where a decision belongs
to scientific authority it names the owner and stops.

---

## 1. Scope

Carbon needs GPU execution for exactly two things:

1. **Enable the miner launchpad.** A visitor chooses a challenge, an agent, a
   reasoning provider and *experiment compute*, approves a budget, and runs a
   research campaign. The compute is rented from a third-party provider. Carbon's
   worker must start reliably on hardware nobody chose in advance.
2. **Let validators use GPUs for reconstruction.** Validators train from scratch
   under pinned contracts. GPU execution is a backend they may use, subject to
   the qualification that already governs backends.

**Everything else is out of scope.** Section 5 names what was built beyond this
and must not be rebuilt.

---

## 2. Goal 1: the launchpad

The launchpad's compute is **rented, arbitrary and unknown in advance**. That
single fact determines the requirements, and it is why portability was the
load-bearing work rather than a convenience.

Required:

| Requirement | Why |
| --- | --- |
| No device identity in source | Every rented instance is different hardware. A pinned UUID makes the launchpad impossible. |
| Installed `HostDeviceRecord` + `doctor` | The worker must discover and verify whatever it landed on. |
| The pinned immutable image | Reproducibility, and so a miner's run reflects what a validator would do. |
| Worker containment, as the CPU lane has it | Unchanged from the accepted CPU model. |
| Effective limits from the approved budget | **Cost control.** The miner is billed by the hour; a run that ignores its ceilings spends their money. |
| Task-owned cleanup and attempt settlement | A leaked container on a laptop wastes nothing. On a rented instance it bills until someone notices. |
| `run` / `cancel` / `recover` | The launchpad must start, stop and recover work on a remote box it provisioned. Without these there is no product. |

**Not required:** exclusivity, compute-process enumeration, an owner-signed
grant, verified whole-device release, global quarantine. None of them is
satisfiable on arbitrary rented hardware, and none of them protects anything
here - miner output is not evidence. Carbon's submission is a declarative
training strategy; validators train from scratch, and a miner need not train
locally at all.

---

## 3. Goal 2: validator reconstruction

**This needs nothing new from engineering.** It needs the existing worker, the
existing backend profile, and the qualification path that already exists.

`carbon/reproducibility/harness.py::compare_r1` returns `BACKEND_UNSUPPORTED`
while `identity.backend_support` is not `SUPPORTED`, and `INDETERMINATE` when a
comparison procedure is absent or its qualification does not match. The backend
check runs first, and returns no deltas - so an unqualified backend produces no
measurements at all. A GPU backend profile is
therefore a candidate whose support status stays unqualified until evidence
exists.

**MQ-008** - *"Qualify narrow backend/hardware profile under R0/R1/R2"* - is
`EVIDENCE_REQUIRED`, owned by SCI + SRE at gate G4. Until it resolves, validator
GPU runs are development evidence and R1 comparison is `BACKEND_UNSUPPORTED`.
That gate does not self-resolve: it computes nothing, so waiting produces no
evidence. Only a deliberate measurement campaign can resolve MQ-008 - see
`GPU_INITIAL_POLICY.md`. That is
correct, already implemented, and must not be routed around.

The only engineering requirement is **to stop blocking it**: a validator may run
GPU reconstruction and have the result report honestly as unqualified.

This document **takes no position on validator exclusivity.** Whether device
contention perturbs numerical outcomes is empirical and MQ-008 owns it.

---

## 4. What stays exact, always

The reproducibility contract separates four questions. Only one admits a
tolerance.

| Question | Requirement |
| --- | --- |
| Am I using the committed recipe, inputs, environment and policies? | **Exact identities.** Hashes, versions and bindings must match. |
| Is this the stored artifact the receipt identifies? | **Exact byte integrity.** A numerically similar replacement cannot satisfy the original hash. |
| Does a repeat execution reproduce the numerical results? | **The registered comparison procedure.** No default epsilon exists. |
| Does the evidence support the same scientific decision? | **The registered decision and uncertainty policy.** Numerical closeness alone establishes nothing. |

Exact integrity is not exact reproduction. A run produces checkpoint **A**; a
fresh reconstruction produces **B**. Storing, transferring or reopening **A** must
verify A's committed bytes. Whether **A** and **B** satisfy a reproducibility
requirement is a separate question under an authorized policy. **B** must never be
relabelled **A**, and matching predictions never establish the same artifact.

**No GPU concern justifies relaxing a hash.** Where a tolerance or qualification
is missing, record the result as development evidence or unresolved - never
invent an acceptance threshold to make a device pass.

---

## 5. Out of scope, and why it must not be rebuilt

These were built for neither goal. They are recorded here so nobody reintroduces
them believing they were required.

**The strict host apparatus** - exclusivity, the host grant asserting
`EXCLUSIVE_SINGLE_DEVICE` and `DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE`,
compute-process enumeration, verified whole-device release, global quarantine.
The profile shipped `admission_enabled: False` beside
`allocation: EXCLUSIVE_REQUIRED_NOT_VERIFIED` - *require the strictest thing, we
have not checked it is achievable* - and because dispatch was disabled nobody
found out. Two facts make it a design error rather than bad luck: the CPU lane
never required exclusivity, and the grant is an unsigned file on the host it
describes, so it constrains accident rather than an adversary.

**Telemetry capability work** was load-bearing only because strict demanded
enumeration. The honest reporting it produced remains correct;
`ESTABLISHED_OBSERVATION_CONTRACTS` stays empty and nothing here is a reason to
add an entry. Its priority was manufactured by a requirement that should not have
existed.

**The local development approval lane** - owner-signed, 24-hour expiry, fixed
attempt budget - is a diagnostic harness for one machine. It is neither goal. The
miner lane subsumes it.

---

## 6. Protected material never reaches the GPU

Three structural facts keep it out, and they should be maintained deliberately:

1. `carbon/reconstruction/accelerators` is imported only by
   `carbon/reconstruction`, `carbon/reconstruction/worker` and
   `carbon/development_session`. Not by evaluation, evaluation_packs, scoring,
   qualification or gauntlet.
2. The staged worker request has a **closed field set** with no slot for
   protected or held-out material.
3. The single data input is type-enforced public: `PublicTrainingArchive` rejects
   any role other than `TRAIN` and any format other than
   `carbon.public-trajectories.v1`, at construction.

**Treat these as a named invariant with a test.** GPU-accelerated evaluation
against hidden cases, if ever wanted, is a distinct lane with a real containment
argument and must be designed then - never as an extension of this one.

---

## 7. The authorized hardware batch

The owner's four-attempt batch serves **goal 2 only**: it produces the
cross-device numerical measurements MQ-008 needs - the same registered strategy
under identical R0 identities, on CPU and on GPU, with observed divergence
recorded for SCI + SRE. Evidence production, not demonstration.

Goal 1 does not depend on it. The launchpad needs the worker to start on rented
hardware, which is verified by starting it on rented hardware.

Envelope unchanged: four attached attempts total including failures and retries,
32 training steps per invocation, 600 s productive with a 120 s cleanup reserve,
1800 s per attempt, 3600 s per batch from first admission with no restart reset,
worker RAM at the lower registered ceiling, 64 MiB per attempt and 256 MiB per
batch, worker network disabled, zero paid spending within this programme.

**Open question for the owner:** four attempts including failures may be too few
to separate run-to-run variation from device-to-device variation. Size it before
spending, because attempts do not come back.

---

## 8. Who decides what

| Decision | Owner |
| --- | --- |
| Backend qualification under R0/R1/R2, and any tolerance | SCI + SRE, via MQ-008 at G4 |
| Whether validator hosts must be dedicated | Owner + SRE |
| Whether a telemetry observation source is ever established | Owner; the registry stays empty until then |
| Where paid provider spend sits - launchpad product vs this programme | Owner |
| Miner lane admission requirements | this document |
| What a miner-lane result is worth | nothing scientifically, by construction |

---

## 9. What this does not do

It qualifies no hardware, registers no telemetry contract, creates no grant,
authorizes no attempt, sets no tolerance, and changes nothing about what
evaluation accepts. It narrows GPU execution to the two things Carbon needs and
records what was built beyond them, so the scope does not drift again.
