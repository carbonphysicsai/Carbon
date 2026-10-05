# CHALLENGE-AI-COOLING-CANDIDATE-FAULT-10 — version the existing failure policy

**Ticket:** `CHALLENGE-AI-COOLING-10_candidate_fault_policy.md`

## Problem

Cooling Interface v1 currently lets neutral dispatch catch rebuild, prediction
and non-finite-output faults as an undifferentiated exception. The resulting
`FAILED_INFRA / adapter_failure` is constitutionally safe, but its retry/refund
meaning is not a registered input. A construction that selectively triggers
that path could therefore target an implicit rule that the Track A attacker
cannot bind to a version and digest.

## Agent-recommended working decision

Keep the existing DEVELOPMENT disposition, register it as
`cooling-candidate-fault-v1`, and separate its data from its hard invariants.
The data names the three faults, `FAILED_INFRA / adapter_failure`, the ordinary
A7 retry/refund interpretation and the components that own those lifecycle
actions. The loader pins the document through the existing attribution-policy
registry and refuses a scientific score, candidate success, local retry or
local fee mutation.

Cooling wraps only the registered rebuild, predict and aggregate-score sites
in a typed `CandidateFault`. Neutral dispatch uses the adapter-provided policy
record, preserves the existing ledger classification, and returns no exception
text. The attack adapter reads the same registered policy; it does not copy the
classification into attack code.

After this ticket began, #602 merged the real-path `selective_fault` family.
That family is retained. Its Interface-v1 result now carries the same policy
record, so its evidence digest binds the policy version, digest and actual
`predict_exception` or `non_finite_score` classification. The small
resource-accounting probes continue to cover the registered policy's complete
fault inventory, including `rebuild_exception`, without duplicating #602's
real construction probe.

## Implementation location

- `carbon/agent_campaign/graphite/attribution_policies/`
- `carbon/challenge_validator/candidate_fault.py`
- `carbon/challenge_validator/interface.py`
- `carbon/challenge_validator/dispatch.py`
- `carbon/challenge_validator/cooling.py`
- `carbon/agent_campaign/attack/adapters/cooling.py`
- focused CPU tests and the Cooling DEVELOPMENT design packet

Branch: `codex/cooling-candidate-fault-policy`; one PR to `main`.

## Alternatives considered

1. **Leave the behavior as an unversioned catch-all.** Rejected: Track A
   cannot distinguish a deliberate rule from implementation drift.
2. **Change the fault to candidate failure now.** Rejected: the Test Lead
   explicitly accepted the current classification as the policy to register;
   changing it would be a new owner decision.
3. **Implement a validator retry/refund engine.** Rejected: Interface v1 owns
   neither A7 scheduling nor fee mutation, and a broad recovery subsystem is
   outside this ticket.
4. **Put constants only in the Cooling attacker.** Rejected: the attack must
   test the execution policy, not a duplicate test oracle.
5. **Generalize every Challenge immediately.** Rejected: the loader and
   dispatch seam are Challenge-neutral, but only Cooling has an authorized
   candidate-fault policy in this ticket. Other Challenges remain unchanged.

## Reversibility and supersession

The implementation is additive. A successor ships a new JSON document, adds
its digest to the registry and moves Cooling's current pointer. Editing the V1
document without updating its pin is refused; overwriting V1's meaning is not
an allowed migration.

## Human-reserved input

None for V1. A different classification or retry/refund policy is reserved to
the applicable owner and must arrive as a new registered version.
