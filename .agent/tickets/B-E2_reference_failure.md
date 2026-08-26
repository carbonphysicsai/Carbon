# Ticket B-E2 - Julia and reference failure boundary

**Wave:** B candidate
**Status:** todo
**Depends on:** B-04
**Build Out:** reference-service failure evidence
**Master questions:** MQ-004
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§6-7; `Runtime_Julia_Truth_Oracle.md`; B-04 reference contract

## Goal

Prove that a Julia/SciML or other reference-service failure remains a typed reference/infrastructure event and can never become synthetic candidate evidence.

## Definition of Done

- [ ] Audit Julia/reference service interfaces and classify reuse without assuming correctness.
- [ ] Define typed timeout, unavailable, malformed, conditioning, unsupported-case, version mismatch, and disagreement results.
- [ ] Bind every response to exact case, policy, implementation, environment, and request identity.
- [ ] Reject partial, stale, substituted, cross-case, or unpinned responses.
- [ ] Test process/service loss, timeout, malformed payload, retry, duplicate response, wrong case, wrong version, and no-candidate-score behavior.
- [ ] Record Julia runtime and scientific test gaps separately from Python contract evidence.

## Human input

SciML owners repair/qualify the Julia environment and reference methods. Contract tests do not establish numerical authority.

## Must not

Return a fake truth asset, convert reference failure to mandatory-gate failure, or claim Julia inclusion equals validation.
