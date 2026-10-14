# INCENTIVE-OBSERVER-02: identity-bound current winner observation

Working contract and plan. Base main
`e976b36e91ef72468c27461ee15b5c05b587e3fc`; isolated branch
`codex/incentive-observer-02`. Root selected this bounded repair under the
owner's competition/payment and mainnet-behavioral-parity mandate. Current
OWNER-DX-03 controls; Hub retired. Root owns engineering delivery/merge.

## Source findings and authority

The competition plan item 2 and current INCENTIVE-CANARY-01 reader disagree
with OWNER-VALV2-WEIGHTS-01: the observer reads released leaderboard.incumbent,
but the publisher reads the live deployment's battery_promotion. Non-retiring
windows can make the former null indefinitely. VALIDATOR-33's existing king
surface reads the publisher WinnerLedger and names its latest record only
while its model matches the live deployment. Reuse that surface; no separate
winner selection, paying-feed adapter or future proven-leaderboard work.

Current signed king omits the record's registered policy digest; as_of_block
omits genesis/network/netuid. The reader authenticates bytes with a pinned
key but checks no feed schema/challenge/validator/freshness/rollback context.
Feed version excludes live chain fields, so equal versions do not prove equal
or fresh observations. Preserve signature/domain/key implementation.

Authority read: constitution/invariants/current WAVE and delivery/delegated
protocol; unchanged Build Out/overlay/master compatibility and code/legacy
authority identities; INCENTIVE-CANARY-01, VALIDATOR-29, current feed/king,
winner eligibility/publisher/policy contracts; OWNER-TESTNET-WEIGHTS-01,
OWNER-WEIGHTS-AUTHORITY-01, OWNER-WEIGHTS-HOLD-LIFT-01,
OWNER-VALV2-WEIGHTS-01, OWNER-BATTERY-CHAMPIONSHIP-04 and
OWNER-PROVEN-LEADERBOARD-01. Root's finish-line record adds parity acceptance.
No archived executable reuse. Classification: IMPLEMENTATION_LAG for the
observer; HUMAN_INPUT for unregistered freshness and production policy values.

## Bounded working decision

KEEP the registered winner/decay/projection/publication and pure diagnostic
helpers. REPAIR only observation provenance, context and refusal behavior.
Add public signed identity fields copied from the existing ledger.policy and
finalized chain context; no private recipe/window/sample/account data. Read
the full signed feed and current king, never silently fall back to released
standing. Context must bind schema, Challenge, validator/key, policy digest,
network/genesis/netuid and finalized block/holder identities. Ineligible,
missing, unauthenticated, stale, conflicting or unknown evidence stays
UNVERIFIED; no unavailable field supplies a successful empty observation.

No freshness limit is registered. Keep explicit HUMAN_INPUT/no production
default; operational verified freshness waits for owner adoption. Synthetic
fixture values exercise controls and confer no live acceptance. A persisted
observer watermark must reject version/block/time rollback and same-block
hash conflicts; equal feed versions with newer chain fields remain possible.
Do not turn public feed signature into scientific or paying authority.

Use the same context/identity guards for any registered policy network.
Current testnet policy cannot authorize finney; absent mainnet policy fails
closed. Testnet owner-coldkey allowance versus mainnet refusal is an existing
economic parity gap, not an observer decision. No recipient policy change.
Battery-only sources, multi-Challenge aggregation, future proof slots,
step pay, allocation, scoring, thresholds, signer/key handling and deployment
are outside this ticket. One Challenge observation cannot certify the whole
subnet's allocation or actual Alpha credit/amount.

## Plan and acceptance

1. Canonical existing observer/feed/winner baseline; reproduce the signed
   wrong-context and released/live mismatch with discriminating controls.
2. Bind additive king policy/chain context to actual existing producers,
   with malformed/absent bindings fail closed. Keep old feeds interpretable
   as legacy observation evidence, never upgrade them silently.
3. Version observer configuration prospectively and implement full-feed,
   current finalized observation plus freshness/watermark validation. Owner
   missing values remain explicit. Update operator docs and migration.
4. Canonical focused positive/negative controls: valid current winner while
   released leaderboard null; wrong key/schema/challenge/validator/policy/
   genesis/netuid; UID/coldkey drift, stale/future/rollback/conflict/missing
   fields; equal version/newer block; no unauthorized fallback or payout
   claim; network parity and fixture limits. Relevant regressions/invariants
   and pinned formatting/hygiene; one main-based non-draft PR.

Expected paths: this ticket and bounded decision; scripts/dev/canary observer
implementation/policy placeholder and focused tests; score_feed.py and king
feed tests for additive provenance; operator observer documentation. Fresh
open-PR scan found no observer/feed/king-test overlap. Refresh before edits.
No production provider/chain read, signing, keys, spend, host acceptance,
private ledger/bank, holdout or protected data. All execution is canonical
synthetic fixtures. Maturity ceiling: DEVELOPMENT implemented/tested only.
Human input: adopted feed freshness bounds and exact authority; actual mainnet
policy/config and economic parity rulings stay outside this bounded repair.
Completion: bounded candidate passes applicable automated acceptance and Root
delivery; owner gaps remain visibly UNVERIFIED, never counted as acceptance.
