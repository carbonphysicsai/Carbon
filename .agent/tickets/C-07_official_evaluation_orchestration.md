# C-07 — Official evaluation orchestration

**Wave:** C1 real scientific execution foundations
**Status:** `done` for the bounded non-official DEVELOPMENT orchestration slice;
broader official/protected scope remains open
**Selection authority:** `OWNER-C1-BURGERS-ALPHA-01`, implemented by `C-07-D1`
**Plan:** `.agent/plans/C-07_development_orchestration.md`
**Evidence:** `.agent/evidence/wave_c/c-07.md`
**Primary Hub map_ref:** `WAVE-C/C-07`
**Depends on:** C-01, C-02, C-03, C-04, C-05, C-06

## Goal

Orchestrate the exact generator, reconstruction, reference, measurement, scoring, receipt, and card owners without implementing shadow semantics or chain science.

## Definition of Done

- [x] One durable state machine associates submission, resolved plan,
      three-replica reconstruction, exact case/request manifests, prediction,
      reference, measurement, unresolved score disposition, receipt and opaque
      card/transcript owner references.
- [x] Delegate each operation to its named domain owner; the orchestrator
      accepts exact source-owned result types and contains no compiler,
      generator, numerical evaluator, scorer or publication logic.
- [x] Preserve typed generator, reconstruction, reference, measurement,
      infrastructure, cancellation, contested and indeterminate outcomes.
- [x] Reference, generator or infrastructure failure produces a retained
      operational account without a signed completion receipt, invented zero,
      score eligibility, archive acknowledgement or payable outcome.
- [x] Crash/replay/idempotency tests cover all terminal dispositions and the
      receipt-append/result-association seam; no direct chain/weight operation
      exists.
- [x] Pass the required Linux/Docker service-backed exact-head acceptance and
      normal merge.
- [ ] Implement official/protected orchestration only after scientific,
      security, signer/custody and real archive authorities exist.

## Authority ceiling

Official-path engineering only. This selected slice is public/synthetic
DEVELOPMENT evidence. Chain submission, protected admission, independent
security review, scientific qualification, real archive acknowledgement,
settlement and LIVE remain separate later gates.

## Accepted delivery

PR #163 accepted exact head
`c8990ddc44b57afd15847fe527c1da7ccecb7f18` in run `34807243278` and
normally merged the bounded slice as
`44511ac0e18c1f3b66227e1e46a986074d16ee0c`. The required Linux service lane
passed 15 tests using image/config
`sha256:03d1407e284908193694a83bbc72ed458843f0fcf88060df2e14197b25cb2a3b`.
This closes only the checked DEVELOPMENT slice above; the remaining unchecked
official/protected item and every qualification ceiling stay open.
