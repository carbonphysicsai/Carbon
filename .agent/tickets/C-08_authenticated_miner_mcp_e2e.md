# C-08 — Authenticated Miner MCP end to end

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; contract materialized, unselected and unstarted
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

- [ ] NET-2 authenticates real transport requests and binds the exact caller,
  network, Challenge, session, request body and replay state.
- [ ] C-07 supplies the real source-owned submit/result path; fixture or
  practice evidence cannot enter it.
- [ ] End-to-end tests cover caller substitution, cross-network/Challenge/
  session replay, duplicate requests, ambiguous dispatch, cancellation,
  authorized retry, budget exhaustion, concurrency and bounded responses.
- [ ] Disclosure-composition tests across MCP, cards, errors, timing and
  repeated related requests prove official-exam secrecy and requester isolation.
- [ ] Durable receipts associate transport request, submission, execution,
  archive/official result and returned projection without making transport an
  authority over any of them.

## Authority ceiling

Contract materialization only. No real transport composition, public endpoint,
fee policy, scientific/security qualification, chain transaction, production or
LIVE authority exists.
