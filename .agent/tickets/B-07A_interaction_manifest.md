# Ticket B-07A - v2 protocol core, interaction manifest, and capability discovery

**Wave:** B candidate
**Status:** done
**Depends on:** B-02A, B-02B, B-02C, B-05, B-07R, B-07S, A3, A9
**Build Out:** C9 public research discovery
**Master questions:** MQ-005, MQ-006, MQ-015, MQ-016, MQ-017, MQ-024
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§2-5

## Goal

Implement the ratified shared v2 nominal protocol primitives once, then let an autonomous miner discover every public contract and capability required to begin research without undocumented repository knowledge.

## Definition of Done

- [x] Implement, exactly once, the B-07S-ratified shared wire-visible nominal
      refs, requests, results, resource envelopes, errors, service interfaces,
      canonicalization helpers, and bounds used across v2. Downstream domain
      tickets import these primitives and cannot redefine them.
- [x] Implement the B-07S-ratified wire-visible `InteractionManifest` and exact refs; the older `ChallengeInteractionManifest` shorthand is documentation lag and creates no alias, helper, or second wire schema.
- [x] Include public physical, candidate-output, target-population, official SamplingPlan, training-support/`R_strategy` family, measurement, score/evidence-use policy, assembly, Strategy, catalog, compiler, method, practice, scaffold, prior-channel/policy, resource, disclosure, and capability reference slots.
- [x] Represent not-yet-populated practice, scaffold, prior, and forecast capabilities explicitly as unavailable; B-GATE owns later populated integration.
- [x] Support exact historical retrieval and explicit absent/unavailable capabilities.
- [x] Reject wrong-Challenge, stale, malformed, cross-bound, conflicting, and unsupported refs.
- [x] Expose no protected exam-pack identity, seed, realized case/stratum composition, private reference endpoint, validator topology, hidden policy, live candidate margin, or fee secret; registered population and score policy stay public.
- [x] Add exact-type, canonicalization, hash, availability, version, hostile-provider, resource-bound, and installed-wheel tests.
- [x] Provide a bounded local-only agent adapter for exact v2 discovery and serialization with stable errors, no network listener, no credentials, and no fixture/practice authority.

## Must not

Implement the final B-07S-ratified closed-operation dispatcher, domain providers/stores, or
task lifecycle; list hidden Challenges; infer qualification; alias fixture and
production manifests; or use the manifest as submission admission.

## Completion boundary

The implementation is bounded to the shared `carbon.research` wire vocabulary,
`ChallengeInfo`, `InteractionManifest`, immutable exact-version discovery, and
the local two-operation discovery adapter. The other ten frozen operations are
known but return `CAPABILITY_UNAVAILABLE`; their semantic owners remain later
tickets. `carbon_protocol_v1`, submission, task lifecycle, domain stores,
practice, prior publication/retrieval, resource forecasting, full dispatch,
transport, credentials, qualification, production, and LIVE are unchanged or
unearned. This `done` state becomes authoritative only when the unchanged ready
revision passes applicable automated acceptance and Merge gate and normally
merges with the expected-head guard.
