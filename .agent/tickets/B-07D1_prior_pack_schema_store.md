# Ticket B-07D1 - PriorPack schema, store, index, and offline compatibility

**Wave:** B candidate
**Status:** todo
**Depends on:** B-07A, B-07B, B-07S, A6, A9, A11
**Build Out:** C10 prior contract and storage
**Master questions:** MQ-016, MQ-018, MQ-025, MQ-026, MQ-045, MQ-051
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§9.1-9.5, 9.7; `Landscape_Agent.md`; `Physics_Intelligence_System.md`

## Goal

Implement exact immutable PriorPack contracts and storage without erasing evidence authority or introducing production signing authority.

## Definition of Done

- [ ] Consume B-07A's B-07S-ratified shared wire-visible `PriorPackRef`,
      `PriorPack`, `PriorChannelRef`, `PriorIndexSnapshotRef`,
      `PriorPublicationReceiptRef`, `TestOnlyPriorApprovalReceiptRef`,
      `PriorPolicyBundleRef`, `PublicEstimandRef`, and one-lever
      `PriorGuidanceItem` without redefining them; internal store models cannot
      alter the wire contract.
- [ ] Require every actionable intervention to target one registered `ParameterCatalog.surface_id`; method artifacts remain non-executable citation/rationale/falsification resources unless catalog-registered.
- [ ] Define exact intervention anchors, scope semantics, estimands, separate evidence origin and epistemic type, the immutable origin/publication-class ceiling matrix, valid-pair/promotion rules, aggregate-only provenance, and canonical item ordering with no order signal.
- [ ] Require one or more typed `counterevidence_and_applicability` entries for material
      `NULL`, `NEGATIVE`, `MIXED`, and `OUT_OF_SCOPE` evidence. Permit
      `NONE_FOUND` only with an exact public search-scope ref and evidence
      cutoff. Bind these entries to the same estimand, scope, provenance,
      coarsening, rights, and disclosure rules as positive guidance.
- [ ] Implement canonical bytes/hash, immutable private history, exact approved-public lookup rules, publication receipts, and active/superseded/withdrawn lifecycle. Canonical `PriorPack` bytes contain neither their own hash nor `PriorPackRef`; `PriorPackRef.content_hash` is SHA-256 of those canonical bytes and is outside the preimage. Reject self-referential identities. Enforce the acyclic `previous index → receipt → new index` graph, with no receipt-to-resulting-index reference; superseded bytes remain public-exact and withdrawn bytes are no longer served but remain in the private audit store. Preserve the public tombstone/receipt and state explicitly that withdrawal cannot revoke previously retrieved copies. Keep the nominal private `TestOnlyPriorApprovalReceipt` and approval snapshot separate from public publication receipts and indexes.
- [ ] Provide only a production signer/key seam and deterministic test-only signer; add no production algorithm, key registry, rotation, revocation, or custody claim.
- [ ] Implement publication classes `TEST_ONLY`, `BOOTSTRAP_PUBLIC`, and `LEARNED_PUBLIC` with mechanical source eligibility.
- [ ] Define the exact lossy v2-to-v1 offline compatibility mapping and internal `PriorProjectionReceipt`; no production v2-backed v1 provider exists and projected bytes remain private test artifacts.
- [ ] Add canonicalization, history/index, exact/active lookup, atomicity,
      reciprocal/cyclic-ref rejection, mapping/loss, contrary-evidence
      non-suppression, false-`NONE_FOUND`, applicability, authority-erasure,
      signer-seam, malicious-ref, resource, and installed-wheel tests.

## Human input

Owners approve public vocabulary, estimands, policy bundle, release roles, rights, and any future signing/custody scheme. Missing input leaves external activation unavailable.

## Must not

Externally publish or activate any pack, install a v2-backed v1 provider, expose projected bytes publicly, imply a signature is qualified, personalize output, or let priors enter score.
