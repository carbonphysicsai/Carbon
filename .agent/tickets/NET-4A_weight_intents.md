# NET-4A — Nominal publication intents

**Wave:** C0 network foundation
**Status:** `in_progress`
**Depends on:** C-REWARD
**Primary Hub map_ref:** `WAVE-C/NET-4A`
**Evidence:** `.agent/evidence/wave_c/net-4a.md`
**Starting main:** 505f08cde173eab197aa397a09536bb6bf576065 (PR #123).
**Authority:** OWNER-C0-REWARD-01; launch v1.0.6; current Build Out/overlay;
OWNER-DX-03 and OWNER-C0-VALIDATION-01. No public-network authority.

## Working contract and plan

KEEP C-REWARD projections, NET-2 journal and NET-1 contextual identity. Add a
nominal StructuralLocalnetWeightIntent reference and durable issuer/resolver in
carbon/rewards. The issuer resolves the existing fixture ledger; raw scores,
caller-selected stages or accepted flags cannot issue an intent. Testnet winner
and optional treasury types remain distinct, with explicit unavailable issuers
until their owning C1/C2/treasury contracts supply authority. NET-4B owns signing.

1. Implement exact local provenance, current-state/supersession and validity checks.
2. Test no winner/all-burn, shared winners, replay/restart, mutation, stage confusion,
   expiry, funding boundary, changed acceptance and quarantine.
3. Reconcile canonical delivery state and Hub; focused canonical acceptance and
   expected-head merge. NET-4B is next under standing authorization.

## Definition of Done

- [ ] Nominal localnet, testnet-winner and optional treasury-routing intent families
      are distinct; fixture references cannot construct public or LIVE authority.
- [ ] Local issuer obtains a complete stored C-REWARD projection, binding exact
      network/genesis/provider/netuid, snapshot/block/time, challenge states,
      reward policy, route, stage, provenance and validity.
- [ ] Intent identity and body digest persist in the existing journal. Exact replay
      is idempotent; conflicting replay, tampering, stale state and supersession fail.
- [ ] Validity is at most 60 finalized-chain seconds (DEVELOPMENT), cut short by
      the next registered allocation/funding boundary. Expiry does not clear chain
      weights. No-winner intent retains the complete non-paying burn target.
- [ ] Issuance requires localnet ledger provenance; raw projection dictionaries and
      authority Booleans are rejected. Missing treasury is supported. Reserved
      public families fail with precise owning-dependency reasons.
- [ ] Tests and all applicable canonical acceptance pass, preserving scientific,
      disclosure, signing and LIVE boundaries. No runtime burn or G2 claim.

## NET-4A-D1

Issue opaque nominal references backed by journal-resolved immutable records,
not self-authenticating dataclasses. Keep one active complete-vector intent per
chain context; later issuance supersedes the old intent. Fresh issuer resolution
checks record-state fingerprints and quarantines. NET-4B additionally checks
fresh snapshot identity, runtime constraints and the final integer vector during
SDK execution. Use a development 60-second maximum validity and publish every
allocation/funding boundary; these are implementation settings, not approved
production SLOs. No fixture-to-testnet conversion function exists.

Hub impact: map_structural; WAVE-C/NET-4A primary, C-REWARD, CI and maturity
affected. Lead notification is asynchronous. No new human engineering gate.
