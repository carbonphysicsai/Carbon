# Ticket B-07D3 - Static prior provider and alignment

**Wave:** B candidate
**Status:** `done` in bounded merged static-provider scope
**Depends on:** B-07D1, B-07D2, B-07S, A9
**Build Out:** C9/C10 static prior retrieval
**Master questions:** MQ-016, MQ-017, MQ-025, MQ-026
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§8-10

## Goal

Serve only prebuilt artifacts authorized for their publication class with
deterministic public alignment and no request-time private analytics.

## Definition of Done

- [x] Implement the B-07S-ratified prior-retrieval capability with exact-ref
      and active-channel selectors, one atomic index snapshot, publication-
      receipt binding, exact authorized historical retrieval, and run-level
      pack pinning.
- [x] Return identical canonical bytes for every requester of an exact pack and perform no server-side personalization, LLM generation, private-store query, or paid informational upgrade.
- [x] Implement the B-07S-ratified prior-alignment capability using only the public pack, public catalog, and deterministic public matching.
- [x] Apply class, approval, and withdrawal checks to both selectors:
      active/superseded approved public bytes may serve; withdrawn returns
      hash-bound audit status only and Carbon stops newly serving the bytes,
      without pretending previously retrieved copies were revoked;
      `TEST_ONLY` and unapproved bytes remain private-test-only.
- [x] Implement the B-07S-ratified nominal fixture-only provider path: an
      exact-ref request through its private fixture context may return a
      structurally authorized `TEST_ONLY` pack only when the exact private
      test-only authorization receipt resolves. Return and retain
      `TEST_ONLY / NOT_UTILITY_QUALIFIED`; external/public context structurally
      rejects that provider, receipt, and pack. Add no caller mode and no
      alternate direct API.
- [x] Return typed unavailable for unapproved, mismatched, missing-ledger/receipt, stale-index, or unsupported public states under the v2 error contract.
- [x] Add requester-equality, atomic snapshot, publication receipt, approved history, withdrawal-no-bytes, index race, cross-Challenge, provider failure, no-private-query, no-score-prediction, no-score-input, resource, and installed-wheel tests.

## Must not

Query Landscape or the card lake during a request, personalize remotely, reveal private records, expose an implicit mutable `latest`, or predict official outcomes.

**Delivery record:** `OWNER-B07D123-01` groups delivery without merging ticket
identity or maturity. Plan: `.agent/plans/B-07D1_D2_D3_prior_delivery.md`.
Evidence: `.agent/evidence/wave_b/b-07d3.md`.

All engineering criteria were implemented and focused-tested in the grouped
candidate. PR #95 accepted head `0b5e62728cd922e494116aaf9b3096346e1b7bb2`
and normally merged it as `258a35d91f45a1125879123bddccc52428d003b2`
after run `34078606840` passed applicable acceptance and Merge gate. B-07E was
then selected as the next eligible ticket.
