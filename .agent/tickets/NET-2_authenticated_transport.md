# NET-2 — Authenticated application transport and durable receipts

**Wave:** C0 network foundation
**Status:** `in_progress`
**Depends on:** NET-1
**Primary Hub map_ref:** `WAVE-C/NET-2`
**Evidence:** `.agent/evidence/wave_c/net-2.md`
**Authority:** OWNER-C0-REWARD-01, OWNER-C0-VALIDATION-01; DELIVERY_PROTOCOL.
**Starting main:** 6dad22db26e4b8babadf73c4de2527a17485a2b1 (PR #120).

## Owning interfaces and implementation plan

KEEP `carbon.mcp.McpService`, A7 requester/lifecycle, A6 disclosure and NET-1
snapshot types. WRAP Bittensor 11.1.0 `http_auth` in `carbon.chain.auth`;
SDK signers, auth objects and exceptions remain there. Add explicitly constructed
`carbon.transport.gateway` with canonical envelope, bounded journal and existing
MCP dispatch. No import-time client, listener, key read or database connection.
NET-3 consumes journal-resolved authenticated receipt references, not a
caller assertion of receipt order or scientific acceptance.

1. Define v1 canonical messages and SDK auth wrapper, then adversarial tests.
2. Implement atomic nonce/request receipt journal and context/snapshot checks.
3. Wrap existing MCP dispatch; test original receipt order, restart and limits.
4. Reconcile current authority/Hub, focused canonical acceptance, normal merge.

## Definition of Done

- [ ] Exact `btauth/1` signatures bind method, path, receiver, body and freshness;
      installed-SDK contract tests use disposable in-memory keys.
- [ ] Canonical UTF-8 JSON rejects duplicate keys, alternate encodings, floats
      outside finite bounds, unknown envelope fields, oversized/deep inputs.
      Envelope binds protocol, network/genesis/netuid, challenge/version,
      exact snapshot, session and request ID; tool fields cannot contradict it.
- [ ] Verify current registered hotkey and exact snapshot identity before
      dispatch; reject stale/provider/context/UID-recycling evidence.
- [ ] Durable SQLite journal atomically records nonce, request identity,
      original authenticated receipt order, provenance and time/block watermark.
      Exact duplicate and conflicting replay fail distinctly after restart;
      clock rollback, capacity and burst limits fail closed with bounded errors.
- [ ] Reuse seven-tool MCP dispatch and A7 requester identity; authentication
      never creates admission, accepted score, frontier or settlement authority.
      No generic result serialization or evaluator data in transport messages.
- [ ] Focused meaningful network, MCP, replay, installed-SDK and invariant tests
      pass in canonical acceptance; source/Hub accurately distinguish local
      tested transport from public service/scientific/security qualification.

## Development settings and limits

POST /carbon/v1/mcp; body <=65,536 bytes, headers <=4,096 bytes, depth <=16,
4,096 JSON nodes, nonce age 10s / future skew 2s, snapshot age <=60s,
32 authenticated requests per hotkey per second, journal <=100,000 receipts.
These are reversible DEVELOPMENT settings, not production SLO/security approval.
Receipt capacity fails closed; durable archival/rotation is an operator concern.
Provider-reported finality remains the NET-1 trust boundary. Service hosting,
TLS/deployment, secrets/custody and real scientific authority are later owners.

## Delivery boundary

No public endpoint or public-network transaction. No new evaluator, accepted
Boolean, hidden data projection, frontier state, reward or weight publication.
After accepted merge, NET-3 is next under standing owner authorization.
