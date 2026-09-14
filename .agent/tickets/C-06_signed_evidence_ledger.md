# C-06 — Signed evidence ledger

**Wave:** C1 real scientific execution foundations
**Status:** `done` in bounded non-official DEVELOPMENT scope; PR #161 accepted
exact head `bad0b05c7683af67caa5fbd9fe9a8e11fda588da` in run
`34797587027` and normally merged as
`0c00350b98b9a0062006f5bd2ce50c20aff37b3c`
**Selected slice:** signed non-official DEVELOPMENT receipt and append-only
ledger
**Selection authority:** `OWNER-C1-BURGERS-ALPHA-01`
**Plan:** `.agent/plans/C-06_signed_development_evidence.md`
**Evidence:** `.agent/evidence/wave_c/c-06.md`
**Primary Hub map_ref:** `WAVE-C/C-06`
**Depends on:** C-01, C-02, C-04, C-05

## Goal

Bind the accepted public-development execution chain into a signed, durable,
reviewer-traceable receipt without exposing protected material or creating
official result authority.

## Definition of Done

- [x] DEVELOPMENT receipts bind Challenge, submission/Strategy, generator,
      target population, SamplingPlan, TRAIN commitment, exact three-attempt
      reconstruction, inference, reference, measurement, uncertainty, Dossier,
      qualification-manifest, source, worker-image and execution-policy
      identities.
- [x] Ledger entries preserve atomic append-only provenance, exact replay,
      supersession, revocation and tamper-evident checkpoints.
- [x] Public/reviewer projections use distinct positive allow-lists and exclude
      protected cases, answer keys, seeds, thresholds and private signing keys.
- [x] Atomic append, Ed25519 verification, tamper, replay, stale/revoked key,
      missing-evidence, partial-write and invalid-transition tests fail closed.
- [x] Every receipt is structurally DEVELOPMENT-only and incapable of asserting
      official, protected, score, archive, network or reward eligibility.
- [x] Pass exact-head automated acceptance and normal merge.
- [ ] Implement the later qualified official receipt/retention/custody profile
      only after its scientific, security and external key authority exist.

## Authority ceiling

Evidence and custody engineering only. A valid receipt does not itself qualify science, security, network, production, or settlement.
