# Ticket B-04 - ReferencePolicy, TruthAsset, and reference runners

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A
**Build Out:** C19 and truth/reference authoring
**Master questions:** MQ-004
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §9; `Evidence_and_Envelope_Standards.md`; reconciled target `Runtime_Julia_Truth_Oracle.md`

## Goal

Represent how one exact case receives an uncertainty-bearing answer key without defining any solver as truth by reputation.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Reference_and_TruthAsset_Contract.md`, obtain independent
      SciML/statistics/protocol review plus methodologically independent
      reference review and explicit human ratification, and merge that contract
      normally; record the exact contract commit in the implementation plan.
- [ ] Define `ReferencePolicy`, `TruthAsset`, primary/corroborating roles, provenance, uncertainty, applicability, failure, and disagreement contracts.
- [ ] Define nominal primary and witness runner interfaces with no generic caller-selected truth mode.
- [ ] Bind exact case, reference policy, implementation, environment, numerical method, and artifact identities.
- [ ] Preserve primary authority, witness corroboration, and generator-under-test as separate roles.
- [ ] Return typed reference, conditioning, unsupported-case, disagreement, and infrastructure failures.
- [ ] Ensure reference failure cannot become candidate gate failure or score zero.
- [ ] Add fixture runners and provenance/failure/cross-boundary tests without claiming Cole-Hopf or Julia qualification.

## Human input

SciML and an independent reviewer qualify the primary/witness hierarchy, methods, uncertainty, failure regions, and acceptable disagreement.

## Must not

Average incompatible references into truth, let a generator certify itself, fall back to mock truth, or claim solver authority from successful execution.
