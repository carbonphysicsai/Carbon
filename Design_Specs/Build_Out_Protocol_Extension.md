# Carbon Build-Out Protocol Extension

**Status:** Ratified sequencing extension incorporated into `Build_Out.md` v1.5
**Purpose:** Preserve the detailed `Evaluation_Evidence_and_Validator_Audit.md` integration contract without reordering or invalidating the current Wave B board.
**Rule:** `Build_Out.md` remains the sequencing authority. Version 1.5 incorporates this extension's post-Wave-B sequencing; this file remains additive design detail. If this file conflicts with a current domain owner, the domain owner governs semantics.

---

## 1. Sequencing principle

The completed A0 → A12 order remains historical implementation evidence;
do not reinterpret or reorder it. Do **not** interrupt or reorder the current
Wave-B board. Promote real execution/audit and Bittensor work only through a
separately selected post-Wave-B C0/C1/C2 ticket.

No P0 implementation may use this extension to:

- expose official seeds/draw IDs;
- weaken mock isolation;
- replace weighted-geometric scoring;
- turn infrastructure failure into scientific failure;
- let stubs emit;
- invent scientific thresholds or reproducibility tolerances;
- require ZK/proof-of-training.

---

## 2. Wave A integration

### A0 — package layout

Add clean package boundaries sufficient for later implementation:

```text
carbon/
  evaluation/
  audit/
  chain/
  qualification/
```

Exact module names may differ, but scientific/evaluation code must not be coupled directly to Bittensor SDK objects if a narrow adapter can preserve testability.

### A1 — CI skeleton

CI must be capable of running a future invariant suite that includes receipt/hash stability, infra/science separation, disclosure controls, and mock isolation. Do not require real GPU/backend execution in A1.

### A3 — challenge registry / LIVE gate

Registry schema should reserve bindings for:

- `receipt_schema_version`;
- required/allowed `backend_profile_id` values;
- exact environment/backend qualification references;
- evidence/qualification artifact hashes.

LIVE remains blocked until exact-version qualification artifacts match.

### A4 — seeding domains / leakage

Add a non-reversible `exam_commitment` projection interface. Tests must prove that miner/public surfaces cannot recover or receive raw official seed material from the commitment.

`BeaconProvider` may be introduced as an interface, but A4 does not independently choose scientific seed timing beyond the ratified data/seeding specs.

### A5 — scoring engine

No mathematical change. `Scoring.md` remains sole authority. Add a stable score-result representation suitable for commitment into an EvaluationReceipt.

### A6 — card store / disclosure

The future evidence architecture continues to distinguish:

```text
Private ExecutionTranscript
Signed EvaluationReceipt
Internal Model Card
Miner EvaluationCard
```

For bounded Wave-A A6, implement only a private record containing the exact A5
`InternalResult` plus its opaque lookup/authorization binding, and the
allow-listed miner `EvaluationCard`. Private ExecutionTranscript, signed or
fixture EvaluationReceipt, rich Internal Model Card, signing/commitment, and
evidence persistence remain later-owned; A6 does not implement them. Raw
hidden exam material is never copied into `EvaluationCard`.

### A8 — TrainEvalAPI stub

The stub should return a structurally valid, mechanically
**non-production-authoritative** execution result. A later receipt/evidence owner may
consume that result to create an unmistakably fixture/mock/stub receipt; A8
does not implement or own the receipt. Stub results and any later stub receipt
must be mechanically rejected by LIVE/emission paths.

### A10 — leaderboard

Leaderboard entries reference public-safe receipt identity/commitment only if useful. No hidden exam data is added to public fields.

### A11 — logging / metrics

Add receipt/evidence lifecycle observability:

- receipt finalized / signature failed;
- evidence-store write failure;
- transcript retention status;
- infra/science status class;
- public-projection redaction failures.

Logs never contain raw official seeds/draw IDs.

### A12 — invariant suite

Add or reserve tests for:

- receipt canonicalization/hash/signature stability;
- stub/mock receipt cannot emit;
- infra result cannot enter ScoreEngine;
- EvaluationCard cannot contain hidden transcript fields;
- exam commitment is non-disclosing by interface;
- LIVE requires qualified backend profile when the registry enables that requirement.

---

## 3. Wave B additions

Wave B science-ready skeleton work adds:

### B-E1 — reproducibility harness skeleton

Implement the framework for R0/R1/R2 comparison without inventing numerical tolerances.

Outputs:

- repeated-run capture;
- exact artifact comparison;
- numerical delta report;
- gate/score decision-stability report;
- `HUMAN_INPUT` tolerance slots;
- backend-profile qualification artifact schema.

### B-E2 — Julia/reference failure contract

Wrap the Julia/SciML verification path so service failures return typed reference/infra statuses rather than synthetic gate failures.

### B-E3 — Credibility Dossier crosswalk schema

Extend dossier artifact layout with optional mappings for context of use, verification, validation, uncertainty, configuration/provenance, limitations, and requalification triggers. This is a vocabulary/evidence mapping only, not a standards-compliance claim.

---

## 4. Wave C additions

Wave C begins only after Wave B and is split into C0 network foundation, C1
real scientific vertical, and C2 temporary direct-weight testnet integration.
This plan does not authorize any of them.

### C0 — network foundation

Reconcile the NET family around:

```text
NET-0  topology / threat model / chain boundary / temporary test policy
NET-1  pinned ChainAdapter / metagraph / wallet / UID / chain errors
NET-2  hotkey-authenticated application transport / replay protection
NET-3  candidate commitment / availability / hotkey binding
NET-4A nominal localnet / testnet-winner / treasury-routing intents
NET-4B compiler / chain constraints / no-winner sink / readback / receipts
NET-5  reproducible localnet E2E harness
NET-6  node / runtime / images / secrets / recovery / observability
```

G2 `LOCALNET_READY` requires the structural/localnet chain and readback. It
confers no scientific, security, network-economic, LIVE, or production
qualification.

### C1 — real scientific vertical

### C-E1 — real signed EvaluationReceipts

Official TrainEval execution produces finalized signed receipts bound to exact pins/backend profile and stored in the evidence ledger.

### C-E2 — append-only receipt commitment log

Implement durable receipt storage plus Merkle/MMR-style append-only commitment checkpoints. On-chain anchoring is optional and not required for P0 acceptance unless separately ratified.

### C-E3 — chain adapter

Implement Bittensor behind narrow protocol interfaces such as:

```text
ChainAdapter
MetagraphSnapshot
WeightPublisher
CommitRevealAdapter
ChainEventRecorder
```

Bittensor identity/discovery and hotkey-authenticated application transport
wrap the Carbon Miner MCP; they do not become the MCP. Official exam material
remains inaccessible from miner-facing interfaces.

### C-E4 — scientific vs policy and chain-intent plane integration

The scientific result is recorded before any network decision. Dependency is
one way:

```text
Carbon scientific result
→ Carbon policy event
→ nominal typed chain intent
→ ChainAdapter / WeightPublisher
→ Bittensor
```

The nominal intents are `StructuralLocalnetWeightIntent`,
`TestnetWinnerWeightIntent`, and `TreasuryRoutingWeightIntent`. A publisher
must reject arbitrary score dictionaries, raw scientific result objects,
hidden measurements, scientific thresholds, payout amounts, and a
caller-selected authority Boolean. A Bittensor weight vector cannot overwrite
historical scientific evidence.

### C-E5 — validator free-riding simulator

Before mainnet planning, add a reproducible simulator/notebook/tool that models evaluator cost, validator stake distribution, copier/free-rider scenarios, audit rate, and honest-evaluator sustainability. Outputs are protocol/economic evidence, not score inputs. Reserve distinct `ValidatorAssignment`, `ValidatorExecutionReceipt`, `ValidatorAuditReceipt`, `ValidatorServiceObligation`, and `ValidatorServiceSettlement` so a copier cannot claim Carbon-controlled service compensation without valid evidence. Exact rates and policy remain human/evidence owned.

### C-E6 — probabilistic audit prototype

After receipt commitment, use future unpredictable randomness to select a subset of testnet evaluations for authorized secondary re-execution. Compare under R0/R1/R2. A disagreement is `CONTESTED` and non-paying pending policy, not a miner physics zero; it routes C2 to the explicit no-winner state.

The audit rate, quorum, and stake policy remain human/protocol-owned.

### C2 — temporary direct-weight testnet integration

C2 adds:

```text
C-W1 TestnetWeightEligibilityEvent
C-W2 winner-only expiry / supersession / explicit non-paying sink
C-W3 publication / validator agreement / readback / recovery
C-W4 complete Testnet Alpha Report
```

Raw score magnitude never maps to weight magnitude. A Challenge-local
scientific result determines only whether a new eligible leader exists. Only
exact real C2 provenance may create an expiring `TESTNET_ONLY`, `NON_LIVE`,
`NON_SETTLING` event and `TestnetWinnerWeightIntent`. Fixture, mock, practice,
estimate, PriorPack, scaffold, partial, failed, cancelled, deferred,
indeterminate, contested, identity-unbound, or stale evidence is ineligible.

With an active eligible winner, only the winner participant allocation is
active and other participants are zero. Without one, an approved non-paying
sink is active and every participant is zero. The exact window duration and
sink identity/custody remain owner-owned. G3 remains `NON_LIVE`,
`NON_SETTLING`, `NOT_FRONTIER_QUALIFIED`, and `NOT_MAINNET_ELIGIBLE`.

---

## 5. Wave D / LIVE additions

LIVE qualification must include, where applicable:

- approved P0 backend profile;
- measured reproducibility evidence and approved R1/R2 tolerances;
- evidence retention policy;
- EvaluationReceipt schema/signing readiness;
- infra/reference failure-path verification;
- disclosure review proving receipts/cards/logs do not leak hidden exam material.

A successful G3 test weight is not Wave-D evidence. Mainnet-readiness review
additionally requires Wave-H frontier/finality evidence and Wave-I treasury,
validator-economics, migration, and settlement evidence.

### 5.1 Post-D launch-critical H/I additions

Wave H alone owns frontier baseline/record, replacement policy, promotion
exam, `FrontierAdvanceEvent`, `ChallengeSetEpoch`, appeal, and finality. A
leaderboard lead or C2 event does not create a frontier event.

Wave I is mainnet-critical:

```text
I-00 treasury receiver / custody / economic contract
I-01 SettlementObligation + immutable accrual/scientific-economic ledger
I-02 TreasuryRoutingWeightIntent + treasury publication
I-03 exactly-once miner settlement
I-04 validator execution / audit economics
I-05 direct-testnet-to-treasury migration + settlement soak
```

G6 requires a rehearsal that stops new direct-winner events, expires/revokes
existing events under registered policy, confirms the non-paying sink,
activates treasury routing, verifies accrual, exercises test frontier events
and obligations, and settles/reconciles without overlap, duplicate benefit,
science mutation, accounting loss on key rotation, or direct-winner mainnet
fallback. Waves E/F/G may proceed after D but do not block H/I.

---

## 6. Backend implementation direction

For P0 implementation planning:

- JAX is the first backend targeted for full qualification;
- PyTorch or other backends remain possible later through `TrainEvalAPI` backend adapters;
- multiple backends do not become production-authoritative merely because adapters exist;
- each production-authoritative backend profile requires its own qualification evidence.

---

## 7. Non-goals

This extension does not add to P0:

- proof of training;
- mandatory zero-knowledge proofs;
- arbitrary miner code execution;
- public raw transcripts;
- per-receipt on-chain storage;
- standards-compliance marketing claims;
- automatic punishment based solely on validator weight similarity.
