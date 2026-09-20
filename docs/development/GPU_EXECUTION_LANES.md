# GPU execution lanes: miner research and validator reconstruction

**Status: proposal.** It records an owner direction and an implementation
design. It does **not** qualify hardware, set a numerical tolerance, or change
what evaluation accepts. Where a decision belongs to scientific authority this
document names the owner and stops.

Owner direction, 20 September 2026: *maximum and efficient GPU execution access
on the miner side; safe and controlled GPU access on the validator side.*

---

## 1. Why this exists

Carbon's accelerator support was built as a single admission path written to
validator requirements: a host grant asserting `EXCLUSIVE_SINGLE_DEVICE` and
`DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE`. The profile shipped
`admission_enabled: False` with `allocation: EXCLUSIVE_REQUIRED_NOT_VERIFIED` -
a placeholder meaning *require the strictest thing, we have not checked it is
achievable*. Because dispatch was disabled, nobody had to find out.

When a real host appeared, it could not prove exclusivity: compute-process
enumeration is unavailable under the WDDM driver model, and NVIDIA reports
per-process memory as unavailable there. The requirement blocked the host.

Two observations make that a design error rather than bad luck.

**The CPU lane never required it.** A miner runs CPU reconstruction with no host
grant, no exclusive lease, and no proof that nothing else uses their CPU.
Containment, content binding and independent reconstruction carry the trust. The
GPU lane invented a stricter rule and applied it to both roles.

**The strict grant is self-asserted.** It is an unsigned JSON file on the host it
describes. `AcceleratorHostAdmission.load()` reads it, checks file permissions
and canonical form, and trusts it. It constrains accident, not an adversary.

---

## 2. What each role actually does

Carbon's submission is a **declarative training strategy**, not a trained
checkpoint. Validators reconstruct and train from scratch under pinned contracts.
A miner may submit without training locally at all.

That fixes the roles precisely:

| | Miner GPU | Validator GPU |
| --- | --- | --- |
| Purpose | private search for better strategies | the training that counts |
| Enters the scientific record | no | yes |
| Given protected material | no | no (see §4) |
| Failure mode that matters | miner wastes their own time | a wrong verdict enters the record |

Miner GPU output is never evidence. Nothing a miner computes locally is
submitted, verified or scored. Carbon's only interest is that **more of it
happens**, because search volume is what Carbon buys.

---

## 3. The lanes

### 3.1 Miner research lane

Requirements are the CPU lane's, plus a device:

- the pinned immutable worker image, matching its labels;
- worker containment - no network, read-only root, all capabilities dropped,
  non-root user, seccomp, cgroup CPU/memory/PID bounds, bounded scratch,
  bounded output, a deadline;
- content-bound inputs - construction plan, training archive and randomness
  identities;
- an installed `HostDeviceRecord` describing the device;
- `doctor` passing;
- effective controls resolved before the run;
- task-owned cleanup of exactly this launch's container and allocation.

**Not required:** exclusivity, compute-process enumeration, an owner-signed
grant, verified whole-device release, or global quarantine. Any NVIDIA device,
any platform - WSL2, bare metal, virtual machine, rented instance - any provider.
Admission is self-service.

The reason Carbon ships this tooling is **fidelity, not gatekeeping**: a miner
exercising a strategy in the same pinned environment a validator will use can
predict what the validator gets. Restricting it subtracts search capacity and
adds nothing, because the output is not evidence.

### 3.2 Validator reconstruction lane

Validator GPU execution is **not qualified**, and this document does not qualify
it. It integrates with the existing mechanism rather than inventing one.

`carbon/reproducibility/harness.py::compare_r1` already returns `INDETERMINATE`
unless `identity.backend_support is BackendProfileSupport.SUPPORTED`, and again
when the qualification's `backend_profile_ref` does not match. A GPU backend
profile is therefore a candidate whose support status stays unqualified until
evidence exists.

**MQ-008** - *"Qualify narrow backend/hardware profile under R0/R1/R2"* - is
`EVIDENCE_REQUIRED`, owned by SCI + SRE at gate G4. Until it resolves, validator
GPU runs are development evidence and R1 comparison is `INDETERMINATE`. That is
the correct, already-implemented behaviour, and nothing here should route around
it.

**On exclusivity for validators this document takes no position.** Whether device
contention perturbs kernel selection or allocation enough to affect numerical
outcomes is an empirical question MQ-008 owns. It should be measured, not
assumed, and not settled by an infrastructure preference.

---

## 4. What stays exact, always

The reproducibility contract separates four questions. Only one of them admits a
tolerance.

| Question | Requirement |
| --- | --- |
| Am I using the committed recipe, inputs, environment and policies? | **Exact identities.** Hashes, versions and bindings must match. |
| Is this the stored artifact the receipt identifies? | **Exact byte integrity.** A numerically similar replacement cannot satisfy the original hash. |
| Does a repeat execution reproduce the numerical results? | **The registered comparison procedure.** No default epsilon exists. |
| Does the evidence support the same scientific decision? | **The registered decision and uncertainty policy.** Numerical closeness alone establishes nothing. |

Exact integrity is not exact reproduction. A run produces checkpoint **A**; a
fresh reconstruction produces **B**. Storing, transferring or reopening **A**
must verify A's committed bytes. Whether **A** and **B** satisfy a reproducibility
requirement is a separate question under an authorized policy. **B** must never
be relabelled **A**, and matching predictions never establish the same artifact.

**No GPU concern justifies relaxing a hash.** Where a tolerance or qualification
is missing, record the result as development evidence or unresolved - never
invent an acceptance threshold to make a device pass.

---

## 5. Protected material never reaches the GPU

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

**Treat these as a named invariant with a test**, not as an accident of the
current design. GPU-accelerated evaluation against hidden cases, if ever wanted,
is a distinct lane with a real containment argument and must be designed then -
never as an extension of this one.

---

## 6. What the authorized hardware batch is for

The owner's four-attempt batch should **generate the cross-device numerical
measurements MQ-008 needs**: the same registered strategy under identical R0
identities, executed on CPU and on the GPU, with observed divergence recorded as
evidence for SCI + SRE.

Its purpose is evidence production, not demonstration. "The GPU ran something" is
not a result. A measured divergence under pinned identities is.

The batch envelope is unchanged by this document: four attached attempts total
including failures and retries, 32 training steps per invocation, 600 s
productive with a 120 s cleanup reserve, 1800 s per attempt, 3600 s per batch
from first admission with no restart reset, worker RAM at the lower registered
ceiling, 64 MiB per attempt and 256 MiB per batch of output and retained logs,
worker network disabled, zero paid spending.

---

## 7. Who decides what

| Decision | Owner |
| --- | --- |
| Backend/hardware qualification under R0/R1/R2, and any tolerance | SCI + SRE, via MQ-008 at G4 |
| Whether validator hosts must be dedicated, and who provisions them | Owner + SRE |
| Whether a telemetry observation source is ever established | Owner; `ESTABLISHED_OBSERVATION_CONTRACTS` stays empty until then |
| Miner lane admission requirements | this document |
| What a miner-lane result is worth | nothing scientifically, by construction |

---

## 8. What this does not do

It qualifies no hardware, registers no telemetry contract, creates no grant,
authorizes no attempt, sets no tolerance, and changes nothing about what
evaluation accepts. It changes which requirements apply to which role, so that a
miner is not blocked by a validator's threat model and a validator is not
qualified by an infrastructure preference.
