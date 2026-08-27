# Ticket B-E2 - Julia and reference failure boundary

**Wave:** B candidate
**Status:** todo
**Depends on:** B-04
**Build Out:** reference-service failure evidence
**Master questions:** MQ-004
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§6-7; `Runtime_Julia_Truth_Oracle.md`; B-04 reference contract
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

## Goal

Prove that a Julia/SciML or other reference-service failure remains a typed reference/infrastructure event and can never become synthetic candidate evidence.

## Definition of Done

- [ ] Audit Julia/reference service interfaces and classify reuse without assuming correctness.
- [ ] Implement fixture outcomes that distinguish at least reference supported,
      reference uncertain, reference disagreement, reference not applicable or
      unsupported, reference numerical/conditioning failure, malformed or
      provenance failure, and reference infrastructure failure. Exact runtime
      names must follow the ratified B-04 contract.
- [ ] Define typed timeout, unavailable, malformed, conditioning, unsupported-case, version mismatch, and disagreement results.
- [ ] Bind every response to exact case, role, policy, implementation,
      environment, numerical configuration, applicability, uncertainty, and
      request identity.
- [ ] Reject partial, stale, substituted, cross-case, cross-role, or unpinned responses.
- [ ] Test process/service loss, timeout, malformed payload, retry, duplicate response, wrong case, wrong role, wrong version, uncertainty, disagreement, non-applicability, numerical failure, and no-candidate-score behavior.
- [ ] Add fixtures proving that a manufactured-solution verification anchor
      cannot be relabeled as a production primary, physical-validation anchor,
      or target-population answer key.
- [ ] Prove that no unregistered analytic fixture, mock, weaker solver, stale
      cache entry, or candidate result can serve as fallback when the registered
      reference path fails.
- [ ] Record Julia runtime, MMS/analytic implementation, and scientific
      qualification gaps separately from Python contract evidence.

## Human input

SciML owners repair and qualify the Julia environment, reference methods,
evidence roles, applicability, uncertainty, and fallback policy. Contract tests
do not establish numerical authority.

## Must not

Return a fake truth asset, average a disagreement into truth, convert reference
failure to mandatory-gate failure, relabel an MMS fixture as validated physics,
fall back silently, or claim Julia inclusion equals validation.
