# C-04 — Protected Burgers reference runtime

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; unselected and unstarted
**Depends on:** B-04, B-E2, C-03

## Goal

Implement the protected Burgers primary-reference adapter and an independent witness without leaking truth assets or inventing fallback authority.

## Definition of Done

- [ ] Run the qualified primary reference and independent witness on the exact canonical case behind the protected boundary.
- [ ] Emit typed `ReferenceRunOutcome` records with policy, case, implementation, environment, applicability, uncertainty-evidence, and artifact identities.
- [ ] Key caches by every qualified identity and reject stale, partial, cross-case, cross-policy, or cross-environment reuse.
- [ ] Keep unsupported, uncertain, disagreement, not-applicable, numerical-failure, and infrastructure-failure outcomes distinct and non-candidate.
- [ ] Provide no mock, weaker solver, averaging, majority-vote, or convenience fallback; common-case campaign utilities may reuse the same types without broadening authority.

## Authority ceiling

Burgers-v1 runtime engineering only. Human scientific qualification and truth admission remain separate and fail closed.
