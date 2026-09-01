# Carbon Testnet-to-Mainnet Launch Path

**Executable roadmap mapped to Carbon Waves B–I**
**Status:** CURRENT OWNER-RATIFIED ROADMAP after merge; planning/governance only, not launch approval
**Version:** 1.0.4
**Date:** 1 September 2026
**Decision:** `OWNER-NET-01`
**Repository planning base:** `7161fe3c4a04821b7f676ab006bd5d313d0442d2`
**Supersedes:** v1.0.3 launch sequencing, optional direct-weight mainnet beta, and unresolved G2–G7 taxonomy

> [!IMPORTANT]
> This document specifies the post-Wave-B roadmap. It does not authorize a
> future ticket, runtime implementation, Bittensor transaction, scientific or
> security qualification, economic value, LIVE activation, deployment, or
> mainnet launch. `CONSTITUTION.md`, `.agent/WAVE.md`, the active wave board,
> ticket authority, the Build Out and constitutional overlay, Launch Bar, and
> the Master Open Design Questions remain controlling in their domains.

> [!CAUTION]
> Wave B remains exactly as governed by current main. B-04 remains selected
> `in_progress`; its runtime and B-01F completion predicate are unchanged. No
> C, H, or I ticket is selected by this roadmap.

## 1. Executive launch position

Carbon will begin real Bittensor integration after Wave B and will separate
network integration, scientific qualification, frontier promotion, and
economic settlement into distinct gates.

```text
Wave B
science-authoring and miner-research contracts
        ↓
Wave C0
Bittensor identity, chain adapter, authenticated transport, localnet
        ↓
G2 LOCALNET_READY
        ↓
Wave C1
Miner MCP transport + validator-to-exam real vertical
        ↓
Wave C2
temporary winner-triggered direct testnet weights
        ↓
G3 TESTNET_ALPHA_DIRECT_WEIGHTS
        ↓
Wave D
first scientifically qualified Challenge
        ↓
G4 QUALIFIED_TESTNET
        ↓
Wave H
frontier promotion and finality
        ↓
Wave I
treasury routing, scientific-economic ledger, per-Challenge settlement
        ↓
G6 TREASURY_SETTLEMENT_QUALIFIED
        ↓
G7 MAINNET_MECHANISM_COMPLETE
```

G5 `MAINNET_DEPLOYABLE` may be reached when infrastructure, keys, custody,
operators, and a release are ready, while economic activation remains off.
Waves E, F, and G may proceed after Wave D in parallel and do not block the
H/I launch-critical branch.

A direct score-to-weight or direct-winner mainnet beta is not part of the
current launch path. Mainnet economic activation requires treasury routing
and per-Challenge settlement.

## 2. Carbon/Bittensor authority boundary

### Bittensor owns

- hotkey/coldkey identity;
- UID registration and metagraph discovery;
- validator/miner presence and stake/network state;
- chain transactions and weight publication; and
- eventual emissions rails.

### Carbon owns

- Challenge identity and Miner MCP semantics;
- candidate commitments and the research protocol;
- official evaluation and the hidden exam;
- producer-independent reconstruction;
- reference/truth and MeasurementContracts;
- scientific score and Challenge-local leader determination;
- frontier promotion and finality;
- economic entitlement; and
- per-Challenge settlement.

Scientific/evaluation modules do not depend directly on Bittensor SDK objects
where a narrow adapter preserves testability. The only target dependency is:

```text
Carbon scientific result
        ↓
Carbon policy event
        ↓
nominal typed chain intent
        ↓
ChainAdapter / WeightPublisher
        ↓
Bittensor
```

The inverse—Bittensor object → scientific scoring authority—is forbidden.

## 3. Launch gates

| Gate | Name | Required evidence | Claim ceiling |
|---|---|---|---|
| G2 | `LOCALNET_READY` | Chain adapter, authenticated transport, candidate commitment, structural localnet weights, readback, and recovery work | Local integration only; no scientific/economic qualification |
| G3 | `TESTNET_ALPHA_DIRECT_WEIGHTS` | Real candidate → exam → score → signed receipt → temporary winner event/intent → on-chain testnet weight → readback → expiry/supersession → no-winner sink | `NON_LIVE`, `NON_SETTLING`, `NOT_FRONTIER_QUALIFIED`, `NOT_MAINNET_ELIGIBLE` |
| G4 | `QUALIFIED_TESTNET` | The exact first Challenge passes Wave D scientific, security, leakage, independent-review, and Launch-Bar evidence | Qualified testnet for the exact identities only; no frontier/settlement/mainnet implication |
| G5 | `MAINNET_DEPLOYABLE` | Infrastructure, keys, custody, operators, release, rollback, and incident state ready | Deployable; economic activation may remain off |
| G6 | `TREASURY_SETTLEMENT_QUALIFIED` | H/I frontier/finality, treasury, validator economics, migration rehearsal, and settlement soak pass | Qualified mechanism for exact evidence; still requires launch authority |
| G7 | `MAINNET_MECHANISM_COMPLETE` | Mainnet activates under explicit owner authority with treasury routing and per-Challenge settlement | Mechanism complete for exact approved network/release/Challenge set |

No earlier gate implies a later one.

## 4. Wave C decomposition

### 4.1 Wave C0 — network foundation

Preserve/reconcile the NET family as follows. Exact ticket IDs may be retained
or minimally reconciled when Wave C is later authorized; this roadmap does not
select them.

| Work | Responsibility | Acceptance boundary |
|---|---|---|
| NET-0 | topology, threat model, Carbon/chain authority, temporary testnet policy | architecture and security review; no runtime authority from this plan |
| NET-1 | pinned Bittensor `ChainAdapter`, metagraph, wallet/UID identity, classified chain errors | SDK contained behind adapter; identity/read-only state tests |
| NET-2 | hotkey-authenticated application transport and replay protection | authenticated request binding; no hidden-exam disclosure |
| NET-3 | candidate commitment, availability, and hotkey/UID binding | exact candidate bytes and producer identity remain bound through receipt |
| NET-4A | nominal localnet, testnet-winner, and treasury-routing chain intents | one intent family cannot substitute for another |
| NET-4B | weight compiler, chain constraints, no-winner sink, readback, and receipts | no arbitrary score input; exact chain-state evidence |
| NET-5 | reproducible localnet E2E harness | structural/localnet test weights and failure recovery |
| NET-6 | node/runtime/images/secrets/recovery/observability | operator and security evidence; no production claim from configuration alone |

G2 requires the complete exact localnet chain; a unit-test adapter or omitted
readback does not pass it.

### 4.2 Wave C1 — real scientific vertical

C1 preserves current real-vertical responsibilities:

- durable submission state and authenticated intake;
- real declarative producer-independent reconstruction backend;
- sandbox/resource/process/filesystem/network/wall-clock isolation;
- protected reference/truth runtime;
- MeasurementContracts, Score Pack, and exact failure separation;
- signed EvaluationReceipts and append-only commitments;
- validator orchestration;
- authenticated Miner MCP E2E;
- testnet publication integration;
- secondary execution and validator-disagreement handling; and
- validator free-riding simulation.

Miner-facing wiring is:

```text
Miner agent
→ Bittensor identity / discovery
→ hotkey-authenticated application transport
→ Carbon Miner MCP
→ practice / research / submit / result
```

Bittensor wraps the MCP; it does not become the MCP. The official exam remains
inaccessible from miner-facing interfaces.

Validator-facing wiring is:

```text
validator identity
→ authenticated submission intake
→ candidate commitment verification
→ durable queue/state
→ producer-independent reconstruction
→ protected official exam
→ MeasurementContracts
→ Score Pack
→ signed EvaluationReceipt
→ Carbon policy decision
→ typed chain intent
```

Orchestration may host the exam; it may not redefine scientific merit.

### 4.3 Wave C2 — temporary direct-weight testnet integration

| Work | Responsibility |
|---|---|
| C-W1 | define `TestnetWeightEligibilityEvent` and exact provenance admission |
| C-W2 | winner-only policy, bounded expiry, supersession, and explicit no-winner sink |
| C-W3 | chain publication, validator agreement, readback, classified recovery, and non-paying rollback |
| C-W4 | complete Testnet Alpha Report binding the proof chain, evidence, identities, failures, and maturity ceiling |

The G3 proof chain is exactly:

```text
miner hotkey
→ authenticated MCP request
→ committed candidate
→ validator orchestration
→ protected exam
→ scientific score
→ signed EvaluationReceipt
→ TestnetWeightEligibilityEvent
→ TestnetWinnerWeightIntent
→ on-chain testnet weight
→ chain readback
→ expiry/supersession
→ no-winner sink
```

## 5. Temporary winner policy

Raw score magnitude does not map to Bittensor weight magnitude. A
Challenge-local score/rank determines only whether a new eligible leader
exists.

```text
new eligible Challenge leader
→ TestnetWeightEligibilityEvent
→ bounded test reward window
→ winner receives logical participant allocation
→ event expires unless superseded by a later new leader
```

The exact reward-window duration remains human/economic-policy owned.

A `TestnetWeightEligibilityEvent` binds at minimum:

- network identity and netuid/mechanism identity;
- Challenge identity/version;
- candidate identity and method identity;
- miner hotkey/UID binding;
- source EvaluationReceipt commitment;
- test-policy version;
- previous leader identity;
- valid-from chain/tempo identity;
- valid-through chain/tempo identity or equivalent expiry; and
- `NON_LIVE`, `NON_SETTLING`, `TESTNET_ONLY` markers.

### 5.1 Exact provenance eligibility

Only the real Wave-C testnet path can originate an event. Policy rejects:

- fixture, mock, practice, estimate, PriorPack, or scaffold outputs;
- partial reconstruction;
- failed infrastructure or failed reference;
- cancelled work or deferred evidence;
- indeterminate or contested comparison;
- unbound candidate bytes;
- wrong hotkey/UID identity; and
- stale or superseded receipt identity.

### 5.2 No-winner behavior

No valid winner may silently leave a stale rewarded winner active. The
following all become non-paying: no eligible leader, expiry, contest,
indeterminacy, validator disagreement, candidate unavailability, identity
mismatch, reference failure, infrastructure failure, supersession, and
invalid chain binding.

```text
ACTIVE ELIGIBLE WINNER
  winner participant allocation = active
  other participant miners = zero

NO ACTIVE WINNER
  approved non-paying sink allocation = active
  participant miners = zero
```

The exact sink chain identity and custody remain network/economic-owner and
security-review decisions. Omitted or invalid weights are not an acceptable
substitute for the policy.

The sink must be registered against the exact network, netuid/mechanism, and
test-policy version; auditable and readback-verifiable; incapable of
conferring participant, miner, or validator benefit, scientific merit,
frontier standing, settlement entitlement, or redistribution to
participants; and fail-closed/non-paying through expiry, recovery, and
invalid-readback handling. These are required properties only; this roadmap
does not choose a chain identity or custody topology.

### 5.3 Multi-Challenge testnet

The initial direct-weight testnet defaults to one Challenge. Before multiple
Challenges share direct testnet allocation, Carbon must either use treasury
settlement or register a fixed `TESTNET_ONLY` per-Challenge allocation policy
and allocate each slice only to that Challenge's active test winner. Scores
do not set cross-Challenge slices. Production allocation belongs to
`ChallengeSetEpoch` plus treasury/economic policy.

## 6. Typed chain intents

The three nominal intent families are separate authority types:

```text
StructuralLocalnetWeightIntent
TestnetWinnerWeightIntent
TreasuryRoutingWeightIntent
```

A chain publisher accepts none of these as a generic dictionary and accepts
no raw score, raw scientific result, hidden measurement, scientific threshold,
Challenge-specific score magnitude, or payout amount. A caller-selected
Boolean such as `emission_capable=True` cannot cross the authority boundary.

## 7. Wave D and G4

Wave D remains the human/scientific qualification gate for the first exact
Challenge. Successful G3 weights do not imply Wave-D success.

G4 binds the exact Challenge, population, SamplingPlan, reference/truth,
measurements, uncertainty, Score Pack, backend profile, security controls,
leakage evidence, independent review, and Launch-Bar evidence required by
current authority. Before Wave D, C2 is not scientifically qualified
superiority. After Wave D, qualified Challenge ranking may feed the same
temporary test policy, but no C2 event becomes a `FrontierAdvanceEvent`.

## 8. Post-D launch-critical branch

### 8.1 Waves E, F, and G

Landscape/evidence memory, product qualification, and commercial/private
engagement may proceed after D in parallel. They retain their own authority
and evidence gates and do not block H/I.

### 8.2 Wave H — frontier promotion and finality

Wave H alone owns:

```text
FrontierBaseline
FrontierRecord
LeaderReplacementPolicy
FrontierPromotionExam
FrontierAdvanceEvent
ChallengeSetEpoch
appeal / finality
```

A leaderboard lead or testnet direct-weight event does not create a frontier
event. Promotion preserves `SUPERIOR`, `NOT_SUPERIOR`, and `INDETERMINATE` and
the registered one-event-per-Challenge-settlement-window direction.

### 8.3 Wave I — mainnet-critical treasury and settlement

| Work | Responsibility |
|---|---|
| I-00 | treasury receiver/custody/economic contract |
| I-01 | `SettlementObligation` plus immutable accrual/scientific-economic ledger |
| I-02 | `TreasuryRoutingWeightIntent` and treasury-routing publication |
| I-03 | exactly-once miner settlement |
| I-04 | validator execution/audit economics |
| I-05 | direct-testnet-to-treasury migration and localnet/testnet settlement soak |

Exact custody topology and payout/compensation values remain human, security,
and economic-owner decisions.

## 9. Treasury architecture

```text
validator weight publication
→ TreasuryReceiverSet
→ TreasuryVault / custody boundary
→ TreasuryAccrualLedger
→ SettlementObligation
→ per-Challenge payout
```

The production chain vector contains no raw candidate score, hidden
measurement, Challenge-specific score magnitude, scientific threshold, or
winner payout amount.

```text
qualified Challenge evidence
→ fresh frontier promotion
→ FrontierAdvanceEvent
→ SettlementObligation
→ treasury settlement
```

Treasury routing settles entitlement; it never creates scientific merit.

## 10. Validator-service economics

Treasury routing creates a free-riding risk because a validator can copy a
treasury vector without executing the scientific work. Reserve distinct:

```text
ValidatorAssignment
ValidatorExecutionReceipt
ValidatorAuditReceipt
ValidatorServiceObligation
ValidatorServiceSettlement
```

Mainnet evidence must show that independent validators have sufficient
incentive to execute or audit assigned work and that a copier cannot claim
Carbon-controlled service compensation without valid evidence. Exact quorum,
stake, assignment, audit rate, and compensation policy remain open.

## 11. Direct-testnet-to-treasury migration

The mandatory rehearsal is:

```text
stop creating new direct-winner events
→ allow active events to expire or revoke under registered migration policy
→ confirm no-winner sink state
→ activate treasury-routing weights
→ verify treasury accrual
→ exercise test FrontierAdvanceEvents
→ create SettlementObligations
→ settle and reconcile
```

Tests prove:

- no overlap between direct-winner and treasury modes;
- no double economic benefit for one event;
- treasury outage preserves scientific evidence;
- retries do not duplicate payouts;
- UID/key rotation does not corrupt accounting;
- chain failure cannot rewrite scientific merit;
- rollback returns to a non-paying state; and
- no automatic mainnet fallback to direct-winner weights.

## 12. Open evidence, security, and economic decisions

The roadmap resolves launch structure, not these values or acceptances:

| Question | Owner/status |
|---|---|
| reward-window duration | economic/protocol owner; `EVIDENCE_REQUIRED` |
| exact no-winner sink identity/custody | network/economic/security owners; `SECURITY_REVIEW_REQUIRED` |
| validator quorum and stake requirements | protocol/economics/security; `EVIDENCE_REQUIRED` |
| validator assignment/audit rate and compensation | protocol/economics; `EVIDENCE_REQUIRED` |
| treasury receiver/vault custody implementation and signers | treasury/security/governance; `SECURITY_REVIEW_REQUIRED` |
| miner and validator-service settlement amounts | economic owner; `EVIDENCE_REQUIRED` |
| operational SLOs, rollback, recovery, reorg, and incident acceptance | operations/security; `EVIDENCE_REQUIRED` / `SECURITY_REVIEW_REQUIRED` |
| Challenge scientific qualification and Launch Bar | scientific owners; Wave D evidence required |
| mainnet deployment/economic activation | owner/governance; explicit future approval required |

MQ-052 through MQ-062 and existing MQ-009 through MQ-020 carry the controlling
question/evidence record.

## 13. Stop-ship conditions

Stop the affected gate if any of the following is true:

- hidden exam or reconstruction-sensitive data reaches a miner surface;
- candidate bytes are not commitment-bound to the authenticated hotkey/UID;
- a Bittensor object enters scientific scoring authority;
- a publisher accepts raw scores/results or an authority Boolean;
- fixture/mock/practice/estimate/PriorPack/scaffold evidence reaches C2;
- reference/infrastructure failure becomes candidate scientific failure;
- no-winner behavior can retain a stale participant reward;
- a testnet event creates frontier or settlement authority;
- direct-winner and treasury modes overlap;
- retry or key rotation can duplicate/corrupt settlement;
- a copying validator can claim service compensation without evidence;
- mainnet can fall back automatically to direct-winner weights; or
- a reserved science/security/economic/launch value is missing.

## 14. Delivery and sequencing control

`GOV-NET-01` is the bounded planning/governance delivery for this version.
Current `.agent/WAVE.md` and `.agent/WAVE_B.md` remain the only active
implementation selection authority. When Wave B later closes under its own
governance, a separate prospective transition may select the first bounded
C0/NET ticket. This plan itself starts none.

## 15. Evidence and source basis

This version reconciles:

- `CONSTITUTION.md`, `AGENTS.md`, `.agent/INVARIANTS.md`, `.agent/WAVE.md`,
  `.agent/WAVE_B.md`, delivery/delegated-decision protocols, and current
  tickets/evidence;
- `Design_Specs/Build_Out.md`, constitutional overlay, protocol extension,
  Agentic Development Master Plan, Launch Bar, Miner MCP, and Evaluation
  Evidence and Validator Audit;
- the scientific canon, architecture decisions/rationale, maturity and
  defensibility ledgers, and Master Open Design Questions; and
- the current implementation/code-authority state at the planning base.

Bittensor commands, APIs, limits, costs, flags, and chain behavior are
time-sensitive. NET-0/NET-1 must re-read pinned official Bittensor authority
and live chain state when implementation is actually selected. This roadmap
does not freeze an SDK version or claim current operational behavior.

## 16. Exact maturity state

```text
SPECIFIED: YES
OWNER_DIRECTION / RATIFIED_ROADMAP: YES after merge under current governance
BITTENSOR_IMPLEMENTED: NO
TESTNET_WEIGHTS_IMPLEMENTED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
TREASURY_IMPLEMENTED: NO
ECONOMICALLY_QUALIFIED: NO
LIVE: NO
MAINNET: NO
PRODUCTION_QUALIFIED: NO
```

> **Launch rule:** transport, scientific qualification, frontier promotion,
> and settlement each earn separate evidence. Token or chain state never
> upgrades weak scientific evidence into merit.
