# Ticket B-04 - ReferencePolicy, TruthAsset, and reference runners

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A
**Build Out:** C19 and truth/reference authoring
**Master questions:** MQ-004
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §9; `Evidence_and_Envelope_Standards.md`; reconciled target `Runtime_Julia_Truth_Oracle.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

## Goal

Represent how one exact case receives an uncertainty-bearing answer key without defining any solver as truth by reputation.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Reference_and_TruthAsset_Contract.md`, obtain independent
      SciML/statistics/protocol review plus methodologically independent
      reference review and explicit human ratification, and merge that contract
      normally; record the exact contract commit in the implementation plan.
- [ ] Define `ReferencePolicy`, `TruthAsset`, primary/corroborating roles, provenance, uncertainty, applicability, failure, and disagreement contracts.
- [ ] Define a closed evidence-role model capable of representing analytic or
      semi-analytic primary evidence, manufactured-solution verification
      anchors, mesh/time/tolerance-converged numerical primaries, independent
      numerical witnesses, experimental validation anchors, industrial
      goldens/customer-hosted references, qualified accelerator/surrogate
      references, and prospectively registered hybrid policies.
- [ ] Make the support boundary for every role explicit. MMS evidence normally
      supports code verification and convergence; it cannot by itself establish
      target-population relevance, model-form validity, customer context of use,
      engineering qualification, or product fitness.
- [ ] Define nominal primary and witness runner interfaces with no generic caller-selected truth mode.
- [ ] Bind exact case, reference policy, role, implementation, environment, numerical method/configuration, artifact, applicability, uncertainty representation, and qualification identities.
- [ ] Preserve primary authority, witness corroboration, generator-under-test,
      and verification-anchor roles as separate. Agreement cannot promote an
      unqualified role, and evidence authority cannot transfer across another
      PDE, envelope, geometry/BC class, implementation, environment, or hardware
      path.
- [ ] Require independence/correlation disclosures for shared equations,
      discretizations, meshes, transforms, libraries, generated code,
      calibration data, personnel, floating-point paths, and hardware where
      material.
- [ ] Return typed supported, uncertain, conditioning, unsupported/not-
      applicable, disagreement, numerical-failure, malformed/provenance, and
      infrastructure-failure outcomes.
- [ ] Ensure reference failure cannot become candidate gate failure or score zero.
- [ ] Add fixture runners and provenance/failure/cross-boundary tests, including
      evidence-role confusion, MMS-to-validation relabeling, correlated-witness
      disclosure, no authority transfer, and no silent fallback, without
      claiming Cole-Hopf or Julia qualification.

## Human input

SciML and an independent reviewer qualify the primary/witness hierarchy,
evidence roles, methods, uncertainty, failure regions, applicability,
independence, and acceptable disagreement.

## Must not

Average incompatible references into truth, let a generator certify itself,
fall back to mock or weaker unregistered truth, promote MMS into physical
validation, transfer one reference's authority to another regime or envelope,
or claim solver authority from successful execution, language, library,
reputation, cost, or nominal tolerance.
