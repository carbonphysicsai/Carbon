# INCENTIVE-OBSERVER-02: current, identity-bound public observation

This is a passive DEVELOPMENT observer. A matching weight/incentive observation
does not establish an Alpha amount, balance credit, settlement, scientific
qualification or security acceptance. It cannot select a winner, change a
policy, set weights or sign a transaction.

The paying source is the live deployment's promotion and the publisher's
WinnerLedger. Released `leaderboard.incumbent` and `standing` remain display
history; neither is a payment source. The observer uses the existing signed
`king`, which the producer names only while its model matches the live
deployment. A missing ledger/current match stays unknown.

## Prospective public contract additions

The score-feed v1 schema/signature domain and old fields retain their meaning.
Readers already drop unknown keys. These additive identity fields disclose no
case, window, seed, raw score, private ledger path or credential:

| Field | Exact source and meaning |
|---|---|
| `king.policy_digest` | The current WinnerLedger record's public registered policy digest. Missing legacy values remain unbound. |
| `network.{name,netuid,genesis_hash}` | The finalized chain reader's configured context, using the existing network-snapshot public field shape. No endpoint is disclosed. Null when unavailable. |
| `winner_observation.schema` | `carbon.validator.winner-observation.v1`; prospective block contract. |
| `winner_observation.source` | Closed `WINNER_LEDGER_AND_LIVE_DEPLOYMENT` producer identity. |
| `winner_observation.policy_digest` | Current matching ledger policy, or explicitly supplied registered `--weight-policy`. No implicit current-policy guess. |
| `winner_observation.state` | `CURRENT`, `NO_PAYABLE_WINNER`, or `UNAVAILABLE`. These are observation states, not scientific grades. |

`NO_PAYABLE_WINNER` requires an actually read ledger and a live deployment
without an incumbent, a matching ineligible record, or a matching registered
canary record (whose hotkey remains suppressed). An empty read without policy
binding is unknown. A missing ledger, wrong Challenge, old deployment's winner,
or missing current match is `UNAVAILABLE`. An unregistered current holder is
observed against the finalized participant map and contributes no target,
matching the existing publisher. Nothing changes eligibility or payment.

The producer's optional `--weight-policy` names a registry-pinned policy and
must match chain network/netuid and Challenge membership. It only supplies
public observation identity, particularly for an empty no-incumbent ledger.
Existing feed building without this option remains possible but cannot turn
unknown values into a verified incentive observation.

## Observer config v2 and migration

`carbon.incentive-canary.config.v2` requires the old public validator/key/URL/
policy fields plus `challenge` (`id`, `version`, `rule_digest`), `network`
(`name`, `netuid`, `genesis_hash`), `chain_endpoint` and an absolute `cursor`
path. `additional_challenges` optionally lists other exact Challenge bindings
served by the same configured validator/feed key. Duplicate/unknown bindings
refuse. A complete registered policy vector is needed to verify aggregation;
missing sources stay `UNVERIFIED`, never implicitly all-burn.

The feed key, validator and exact deployed Challenge/rule identities are pinned
out of band. The observer builds an explicit ChainContext, checks policy network
and netuid, and captures row/incentives/participants at one finalized snapshot.
Feed block/hash/time must match that snapshot or a read-back finalized anchor.
UID/coldkey/registration drift, foreign context, altered signature and malformed
or unavailable data refuse without echoing source payloads or exceptions.

Old v1 configurations and scalar incumbent/leaderboard readers cannot qualify a
current observation. Use a new scoped cursor when migrating configuration,
policy, validator or Challenge context; do not relabel old journal lines.
The owner-only append-only cursor is a local observation watermark, not the
winner/payment ledger. One OS lock fences validation of its complete history
and append. Version/block/time rollback, equal-block hash conflict, equal-version
winner conflict and same-hotkey registration change remain `UNVERIFIED`.
Equal feed versions with newer chain fields are allowed because feed versioning
deliberately excludes those live fields.

## Freshness and remaining owner gates

No feed freshness limit is adopted. `incentive_observation.FRESHNESS` contains
`authority: HUMAN_INPUT`, `max_feed_age_ms: None`, `max_block_lag: None`.
Neither feed nor config may supply its own replacement. Operational checks stay
`UNVERIFIED/feed_freshness_human_input` until the owner adopts a record and
values. Synthetic tests explicitly replace these with fixture values only.
The age bound covers signed generation time and the independently read chain
time; future timestamps refuse. The block-lag bound covers finalized feed
anchors, whose hash and timestamp are independently read back when older.

For a complete, bound roster, the observer reuses pure `Winner` and
`epoch_targets`: aggregate a shared hotkey before UID mapping, preserve registered
decay and exact Q12 remainder/burn. The existing integer observation tolerance
is unchanged. Different current versus stored targets are observation drift;
epoch publication lag is not automatically a payment-policy violation.
The reader independently obtains the validator row's `LastUpdate` at the same
finalized head and reads that publication block/hash/time. Missing context stays
UNVERIFIED; a winner clock after publication cannot prove a defect in that older
row. The complete pure-vector comparator may BLOCKER an exact wrong fixture
vector; operational current-target drift is ATTENTION. Known canary violations
are retained. A sybil pair also winning other Challenges is not a primary-
Challenge split measurement; its aggregate attribution stays UNVERIFIED and
does not enter the per-Challenge sybil summary.
The pure diagnostic `verify_epoch` accepts optional `expected_targets` for
this vector. A shared holder without bound aggregate targets stays UNVERIFIED;
the observer does not guess mixed clocks from counts or normalize earned shares.

Mainnet uses the same identity/context/freshness code and needs its own registered
policy and operator context. The current testnet policy is not mainnet evidence.
Testnet owner-coldkey allowance versus mainnet refusal is an existing economic
parity gap, left for owner reconciliation. Mainnet policy/configuration,
publication capabilities/security acceptance, actual multi-Challenge winner
adapters, the future proven-leaderboard lifecycle and measured payment receipts
remain separate gates. No default, recipient exception, allocation, score,
threshold, clock-reset, signer or economic policy is changed here.

## Parity inventory

| Seam | Classification and disposition |
|---|---|
| Released versus live winner; absent context/rollback checks | Engineering defect repaired here using the existing paying source. |
| Shared-hotkey aggregate compared to one Challenge share | Engineering defect repaired observationally; paying Q12 math unchanged. |
| Genesis/netuid/endpoints and validator/feed-key identities | Necessary environment differences, explicitly pinned and checked. Endpoint is never disclosed in a receipt/feed. |
| Mainnet policy/membership/configuration and baseline | Reserved owner/qualification input. Testnet's null-baseline first-incumbent exception does not demonstrate launch behavior. |
| Testnet owner-coldkey allowance versus mainnet refusal | Reserved economic parity gap; this observer does not reconcile it. |
| Battery-only operator source and missing other feeds | Separate engineering follow-up; incomplete public observation stays UNVERIFIED. |
| Runtime/authorization/reveal/publication capabilities | Separate exact-network acceptance evidence; this passive allocation check does not certify those guards. |
| Future proven-leaderboard promotion/step lifecycle | Prospective migration, outside this repair. Existing finals remain the built paying source. |
| Freshness bounds and operational payment receipts | Owner inputs/evidence still required. No fixture or nonzero incentive supplies production acceptance or an Alpha amount. |
