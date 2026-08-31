# Ticket B-07A - v2 protocol core, interaction manifest, and capability discovery

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A, B-02B, B-02C, B-05, B-07R, B-07S, A3, A9
**Build Out:** C9 public research discovery
**Master questions:** MQ-005, MQ-006, MQ-015, MQ-016, MQ-017, MQ-024
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§2-5

## Goal

Implement the ratified shared v2 nominal protocol primitives once, then let an autonomous miner discover every public contract and capability required to begin research without undocumented repository knowledge.

## Definition of Done

- [ ] Implement, exactly once, the B-07S-ratified shared wire-visible nominal
      refs, requests, results, resource envelopes, errors, service interfaces,
      canonicalization helpers, and bounds used across v2. Downstream domain
      tickets import these primitives and cannot redefine them.
- [ ] Implement the B-07S-ratified wire-visible `ChallengeInteractionManifest` and exact refs; any internal domain helper remains non-wire and cannot change its meaning.
- [ ] Include public physical, candidate-output, target-population, official SamplingPlan, training-support/`R_strategy` family, measurement, score/evidence-use policy, assembly, Strategy, catalog, compiler, method, practice, scaffold, prior-channel/policy, resource, disclosure, and capability reference slots.
- [ ] Represent not-yet-populated practice, scaffold, prior, and forecast capabilities explicitly as unavailable; B-GATE owns later populated integration.
- [ ] Support exact historical retrieval and explicit absent/unavailable capabilities.
- [ ] Reject wrong-Challenge, stale, malformed, cross-bound, conflicting, and unsupported refs.
- [ ] Expose no protected exam-pack identity, seed, realized case/stratum composition, private reference endpoint, validator topology, hidden policy, live candidate margin, or fee secret; registered population and score policy stay public.
- [ ] Add exact-type, canonicalization, hash, availability, version, hostile-provider, resource-bound, and installed-wheel tests.
- [ ] Provide a bounded local-only agent adapter for exact v2 discovery and serialization with stable errors, no network listener, no credentials, and fixture/practice authority only.

## Must not

Implement the final B-07S-ratified closed-operation dispatcher, domain providers/stores, or
task lifecycle; list hidden Challenges; infer qualification; alias fixture and
production manifests; or use the manifest as submission admission.
