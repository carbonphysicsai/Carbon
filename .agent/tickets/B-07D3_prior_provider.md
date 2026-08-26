# Ticket B-07D3 - Static prior provider and alignment

**Wave:** B candidate
**Status:** todo
**Depends on:** B-07D1, B-07D2, B-07S, A9
**Build Out:** C9/C10 static prior retrieval
**Master questions:** MQ-016, MQ-017, MQ-025, MQ-026
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§8-10

## Goal

Serve only prebuilt approved prior artifacts with deterministic public alignment and no request-time private analytics.

## Definition of Done

- [ ] Implement `get_prior` with exact-ref and active-channel selectors, one atomic index snapshot, publication-receipt binding, exact approved historical retrieval, and run-level pack pinning.
- [ ] Return identical canonical bytes for every requester of an exact pack and perform no server-side personalization, LLM generation, private-store query, or paid informational upgrade.
- [ ] Implement `inspect_prior_alignment` using only the public pack, public catalog, and deterministic public matching.
- [ ] Apply class, approval, and withdrawal checks to both selectors:
      active/superseded approved public bytes may serve; withdrawn returns
      hash-bound audit status only and Carbon stops newly serving the bytes,
      without pretending previously retrieved copies were revoked;
      `TEST_ONLY` and unapproved bytes remain private-test-only.
- [ ] Implement the B-07S nominal fixture-only provider path: an exact-ref
      request through `FixtureResearchContext` may return a structurally
      approved `TEST_ONLY` fixture pack only when its exact
      `TestOnlyPriorApprovalReceiptRef` resolves. Return and retain
      `TEST_ONLY / NOT_UTILITY_QUALIFIED`; external/public context structurally
      rejects that provider, receipt, and pack. Add no caller mode and no
      alternate direct API.
- [ ] Return typed unavailable for unapproved, mismatched, missing-ledger/receipt, stale-index, or unsupported public states under the v2 error contract.
- [ ] Add requester-equality, atomic snapshot, publication receipt, approved history, withdrawal-no-bytes, index race, cross-Challenge, provider failure, no-private-query, no-score-prediction, no-score-input, resource, and installed-wheel tests.

## Must not

Query Landscape or the card lake during a request, personalize remotely, reveal private records, expose an implicit mutable `latest`, or predict official outcomes.
