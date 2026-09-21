# Owner decision and work package P: unblock GPU validator admission

## The decision

**Recorded 2026-09-21. Owner decision, programme #209, ticket C-CORE-19.**

`VALIDATOR_DEPLOYMENT_PATH.md` classified GPU `VALIDATOR_RECONSTRUCTION` as
`NEW_OWNER_DECISION_REQUIRED` and stated the smallest decision. It is decided:

> **GPU `VALIDATOR_RECONSTRUCTION` admits through the host record and `doctor`,
> the same path the miner lane uses. It does not require an owner-signed grant or
> an exclusive lease.**

### Why

- **Exclusivity was never the mechanism delivering reproducibility.** D3 measured
  that pinned determinism does it: three sessions, nine runs, one digest.
- **N2 is the first direct evidence on contention.** Eighteen runs across nine
  configurations, including two simultaneous runs on disjoint core sets, produced
  one weight digest. That is CPU, and GPU contention remains untested, but it
  points away from exclusivity rather than toward it.
- **The grant is self-asserted** - an unsigned file on the host it describes. It
  constrains accident, not an adversary, so requiring it buys no adversarial
  guarantee. Amendment 3 C4 established the same of the numerics record: it is
  provenance, not attestation.
- **It pre-empted a deferred question.** `GPU_EXECUTION_LANES.md` states that this
  document takes no position on validator exclusivity and that whether contention
  perturbs numerical outcomes is empirical and MQ-008 owns it. A grant asserting
  `EXCLUSIVE_SINGLE_DEVICE` answers that by decree.
- **D3 of the recovered roadmap** gives validators provider freedom explicitly. An
  owner-signed grant per validator host does not scale to that.

### What this decision does not do

**Admission is not qualification.** `compare_r1` still returns
`BACKEND_UNSUPPORTED` while the backend profile is not `SUPPORTED`, and MQ-008 at
G4 still owns that. A GPU validator run produces development evidence. Nothing
here changes what evaluation accepts, qualifies any hardware, sets any tolerance,
or authorizes any spend.

**Exclusivity stays MQ-008's empirical question.** This decision declines to
assert an answer; it does not assert the opposite one.

---

## P1. Admit `VALIDATOR_RECONSTRUCTION` on GPU through the host record

Route the role through the same host-record-plus-`doctor` admission the miner lane
uses. The strict path stays in the tree and stays unused for this role.

**Do not remove the strict host apparatus, and do not build on it.** Both remain
forbidden. This is a dispatch change, not a deletion and not an extension.

Keep `STRICT_HOST_GRANT` and `LOCAL_DEVELOPMENT_APPROVAL` the two
never-interchangeable authorities they already are. Do not widen either to cover
this; if the role needs an authority value it should be the miner lane's, not a
relaxed version of the strict one.

## P2. Record contention facts as observations

The decision declines to require exclusivity. It does not claim contention is
harmless, so make it detectable later.

Extend the numerics record with the contention-relevant facts the host can supply:
what else is resident on the device where that is observable, and the memory
pressure at admission.

**Preserve missingness honestly.** Compute-process enumeration is unavailable
under WDDM. Where it cannot be observed, record it as unavailable - never as
"nothing else running". `ESTABLISHED_OBSERVATION_CONTRACTS` stays empty; this adds
observations, not an established contract, and it is provenance rather than
attestation.

## P3. Complete the deployment path

Remove the `NEW_OWNER_DECISION_REQUIRED` block from
`VALIDATOR_DEPLOYMENT_PATH.md` and finish the GPU half of the operator sequence:
prerequisites, host check, image, run, score, recover. Cite this decision by date
and ticket.

Reconcile `VALIDATOR_GPU_DETERMINISM_POLICY.md` with it where the two meet.

## P4. Tests

The admission change needs a test that fails if the role silently reverts to
requiring a grant, and one that fails if an unobservable contention fact is ever
recorded as an observed absence.

## P5. Resolve the #249 conflicts

Every check on #249 passes, merge gate included, but it is `CONFLICTING` against
main because #247 merged underneath it. Resolve against current main, keep the
measured values and their provenance byte-identical through the merge, and re-run
`tests/cpu` on the result.

---

## Rules that do not bend

Unchanged. Exact stays exact; never choose a tolerance; never relabel B as A;
never erase device or run identities for a cross-host comparison; a mismatch is an
incident with cause unestablished; do not widen `ScoreStatus`; protected material
stays off this path; do not build on the strict apparatus; do not edit a worktree
while a suite consumes it.

No GPU run, rental or paid call follows from this package. P7 still governs
spending.
