# C-08 — Authenticated Miner MCP end to end

**Wave:** C1 real scientific execution foundations
**Status:** `in_progress`
**Status scope:** bounded non-official DEVELOPMENT composition
**Selected slice:** authenticated NET-2 + A9 + real-path C-07 association,
without a public listener or official result authority
**Selection authority:** `OWNER-C1-BURGERS-ALPHA-01`, implemented by `C-08-D1`
**Plan:** `.agent/plans/C-08_authenticated_miner_mcp_e2e.md`
**Evidence:** `.agent/evidence/wave_c/c-08.md`
**Primary Hub map_ref:** `WAVE-C/C-08`
**Depends on:** NET-2, C-07; current A9 Miner MCP disclosure contract
**Owner:** Codex + API/protocol engineering
**Accountable reviewer:** Protocol + security + scientific integration
**Authority:** retained C-08 identity from launch v1.0.3 §6.3; current C1
miner-facing wiring in launch v1.0.4 §4.2; `Design_Specs/Miner_MCP.md`;
`Design_Specs/Build_Out.md` §3

## Goal

Bind the current Miner MCP service to NET-2's authenticated application
transport and the real C-07 validator orchestration path so submit/result
operations preserve exact caller, network, Challenge, session, request,
execution and receipt identities without exposing the official exam.

## Boundary and dependencies

A9's seven-tool in-process service, schemas, budgets and disclosure allow-lists
remain the MCP owner. NET-2 owns authenticated hotkey/application transport,
replay protection and transport receipts. C-07 owns the real official
orchestration result. C-08 composes those owners; it does not add a scorer,
execution engine, scientific result, payment rule, chain intent or publication
authority.

Every request must bind authenticated caller identity, network/netuid where
applicable, Challenge/version, transport session, request/idempotency identity
and the exact source submission. Caller-controlled fields cannot override
authenticated identity or select protected exam material. Practice, fixture and
research paths remain nominally distinct and cannot satisfy a real result.

## Resource, cancellation and disclosure contract

- Enforce registered request/response size, concurrency, query/disclosure,
  rate, execution-resource and spend/budget controls before downstream work.
  Missing real policy values reject or remain unavailable; no fee or quota is
  invented by this ticket.
- Cancellation and retry delegate to C-01/C-07 lifecycle owners. Ambiguous
  dispatch blocks duplicate submission until reconciled; retries create exact
  linked attempts and do not change cases, seeds or scientific meaning.
- Return only the A9/A6 authorized projection for the authenticated requester.
  Official seeds, cases, reference values, fine margins, private transcripts,
  other requesters' state and reconstruction-sensitive diagnostics remain
  unavailable across success, error, timing and pagination surfaces.
- Authentication, authorization, replay, budget, provider and infrastructure
  failures remain typed operational outcomes, not candidate scientific failure.

## Definition of Done

- [x] NET-2 authenticates transport requests and binds the exact caller,
  network, Challenge, session, request body and replay state.
- [x] C-07 supplies the exact source-owned non-LIVE orchestration path; fixture or
  practice evidence cannot enter it.
- [x] End-to-end tests cover caller substitution, cross-network/Challenge/
  session replay, duplicate requests, ambiguous dispatch, cancellation,
  authorized retry, budget exhaustion, concurrency and bounded responses.
- [x] Disclosure-composition tests across MCP, cards, errors, timing and
  repeated related requests prove official-exam secrecy and requester isolation.
- [x] In this bounded slice, durable receipts associate transport request,
  source submission, C-01 attempt and returned C-07 DEVELOPMENT projection
  without making transport an authority over any of them. Official result and
  archive association remain structurally unavailable.
- [ ] Pass the exact-head automated acceptance, including the mandatory Linux
  installed-SDK/service-backed lane, and normally merge.

## Authority ceiling

Selected bounded public/synthetic DEVELOPMENT composition only. No public
listener, protected data, official result, real archive acknowledgement, fee
policy, scientific/security qualification, chain transaction, production or
LIVE authority exists.

## Candidate implementation

`carbon.miner_mcp` adds no listener. It composes the exact NET-2 gateway and A9
service, records submit intent before A9 mutation, records C-07 bind intent
before the source-owned operation, and retains source terminal accounts. A9
results remain exact A9 objects; C-08 adds only a canonicalized copy-on-read
C-07 public projection. The lookup binds requester, submission and Challenge
through the original transport receipt.

Focused CPU/invariant/classifier tests pass locally. The installed Bittensor SDK
test is registered in the existing C-03/C-04/C-05/C-07 Linux service lane and
must execute in exact-head acceptance; the native Mac JAX environment does not
carry that chain dependency and supplies no substitute result.
