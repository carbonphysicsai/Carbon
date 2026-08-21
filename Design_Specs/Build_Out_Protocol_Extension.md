# Carbon Build-Out Protocol Extension

**Status:** Ratified sequencing extension to `Build_Out.md` v1.4  
**Purpose:** Integrate `Evaluation_Evidence_and_Validator_Audit.md` without reordering or invalidating the current Wave A board.  
**Rule:** `Build_Out.md` remains the sequencing authority. This extension is additive and should be folded into the next Build Out revision. If this file conflicts with a current domain owner, the domain owner governs semantics.

---

## 1. Sequencing principle

Do **not** interrupt the current A0 → A12 order. Add the evidence/audit architecture through the existing tickets where natural, then promote real execution/audit work in Waves B/C.

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
**non-emission-capable** execution result. A later receipt/evidence owner may
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

Wave C real vertical integration adds:

### C-E1 — real signed EvaluationReceipts

Official TrainEval execution produces finalized signed receipts bound to exact pins/backend profile and stored in the evidence ledger.

### C-E2 — append-only receipt commitment log

Implement durable receipt storage plus Merkle/MMR-style append-only commitment checkpoints. On-chain anchoring is optional and not required for P0 acceptance unless separately ratified.

### C-E3 — chain adapter

Implement Bittensor behind protocol interfaces such as:

```text
ChainAdapter
MetagraphSnapshot
WeightPublisher
CommitRevealAdapter
ChainEventRecorder
```

C15 testnet acceptance remains mandatory: real lean scores must become observable Bittensor testnet weights.

### C-E4 — scientific vs emission plane integration

The canonical scientific result is recorded from qualified evaluation evidence before it is transformed into Bittensor weight publication. The Bittensor weight vector does not overwrite historical scientific evidence.

### C-E5 — validator free-riding simulator

Before mainnet planning, add a reproducible simulator/notebook/tool that models evaluator cost, validator stake distribution, copier/free-rider scenarios, audit rate, and honest-evaluator sustainability. Outputs are protocol/economic evidence, not score inputs.

### C-E6 — probabilistic audit prototype

After receipt commitment, use future unpredictable randomness to select a subset of testnet evaluations for authorized secondary re-execution. Compare under R0/R1/R2. A disagreement is CONTESTED/NON-EMITTING pending retry, not a miner physics zero.

P0 acceptance may initially exercise this with a small controlled audit rate; the final production rate remains human/protocol-owned.

---

## 5. Wave D / LIVE additions

LIVE qualification must include, where applicable:

- approved P0 backend profile;
- measured reproducibility evidence and approved R1/R2 tolerances;
- evidence retention policy;
- EvaluationReceipt schema/signing readiness;
- infra/reference failure-path verification;
- disclosure review proving receipts/cards/logs do not leak hidden exam material.

Mainnet-readiness review additionally requires validator-economics/free-riding analysis and an explicit audit strategy.

---

## 6. Backend implementation direction

For P0 implementation planning:

- JAX is the first backend targeted for full qualification;
- PyTorch or other backends remain possible later through `TrainEvalAPI` backend adapters;
- multiple backends do not become emission-capable merely because adapters exist;
- each emission-capable backend profile requires its own qualification evidence.

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
