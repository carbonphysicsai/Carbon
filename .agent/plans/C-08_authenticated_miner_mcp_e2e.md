# C-08 bounded authenticated DEVELOPMENT composition

**Decision:** `OWNER-C1-BURGERS-ALPHA-01`, implemented by `C-08-D1`
**Status:** selected implementation plan
**Base:** C-07 PR #163 merge
`44511ac0e18c1f3b66227e1e46a986074d16ee0c`
**Primary Hub map_ref:** `WAVE-C/C-08`

## Scope and ownership

KEEP NET-2's authenticated envelope, btauth verifier and durable receipt order;
KEEP A9's exact seven operations, resource/query gates and result disclosure;
KEEP C-07/C-01 as the only attempt, retry, cancellation, stage and result
owners. Add one composition package and journal extension. It never listens on
a socket, chooses a scientific plan, executes a callback supplied by a miner,
creates a fee/quota, serializes private evidence, or publishes a result.

## Fixed flow

1. NET-2 authenticates and journals the exact network, Challenge, session,
   request and body before C-08 sees a call.
2. For `submit`, C-08 durably records dispatch intent before invoking A9.
   Successful A9 mutation is then associated with the exact source submission.
   Loss between those operations remains `RECONCILIATION_REQUIRED`; replay may
   reconcile exact known output but can never invoke A9 a second time.
3. Trusted controller code binds only an exact C-07 request whose authenticated
   requester, Challenge, submission and `REAL_PATH_NON_LIVE` execution match the
   submit association. Intent is durable before C-07 `begin`, and recovery uses
   only C-07's explicit start/resume/attach modes with the same worker/claim.
4. C-08 records only an exact source-owned C-07 operational account. The account
   may be complete, failed, cancelled, contested or indeterminate. Retry attempts
   are admitted only through C-01's existing predecessor continuity rule.
5. Authenticated `get_submission_result` still consumes A9's query budget and
   returns its exact result plus a fixed positive C-07 public projection when
   available. Every output is bounded by NET-2 canonical response limits.

## Acceptance and authority ceiling

Focused tests cover caller/context/session replay, duplicate and ambiguous
submit, exact reconciliation, real-path-only binding, C-01 retry continuity,
cancellation and terminal projections, query/concurrency/budget enforcement,
cross-request isolation, response bounds, restart and changed-byte rejection.
One Linux service test composes the actual authenticated gateway, A9 service and
C-07 orchestration with public synthetic inputs. The result stays non-official,
unscored, unarchived, non-network and non-reward eligible.

No public listener, production auth deployment, protected data, official result,
real archive acknowledgement, fee, scientific/security qualification, chain
transaction, production or LIVE authority is added.
