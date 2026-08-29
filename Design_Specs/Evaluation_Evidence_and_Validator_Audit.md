# Carbon Evaluation Evidence & Validator Audit Specification

**Revision:** 1.1 candidate amendment (2026-08-26)
**Status:** OWNER-RATIFICATION PROPOSAL — the previously ratified architecture remains authoritative; revision 1.1's scientific-repeat and dependence rules require explicit Physics/SciML, statistics, and protocol-owner acceptance.
**Scope:** P0 evidence spine, backend qualification, validator accountability, testnet auditability, future proof-readiness  
**Authority:** This document owns execution evidence, evaluation receipts, reproducibility qualification, validator audit/re-execution, and scientific-vs-emission consensus separation. It does **not** override `Scoring.md`, `Data_Management.md`, `Trustless_Verification.md`, `Miner_MCP.md`, generator qualification specs, or `Launch_Bar.md` in their owned domains.

---

## 1. Objective

Carbon must preserve a durable, independently auditable record of **what scientific evaluation actually occurred** without exposing the hidden exam. The evidence system must support:

- reproducibility and backend qualification;
- miner-result provenance;
- validator accountability and dispute handling;
- Bittensor testnet/mainnet weight publication;
- later customer/product credibility dossiers;
- future cryptographic proof systems without requiring ZK in P0.

The evidence spine is intentionally separate from the miner-facing disclosure surface. **Commitment is not disclosure.** Official seeds, derived seeds, draw IDs, reversible identifiers, and reconstruction-sensitive diagnostics remain controlled.

---

## 2. Evidence object model

Every official evaluation produces four conceptually distinct artifacts.

```text
Official execution
   ↓
Private ExecutionTranscript
   ↓ canonical commitments
Signed EvaluationReceipt
   ├─ Internal Model Card
   ├─ Miner EvaluationCard projection
   ├─ Audit / re-execution input
   ├─ Scientific evidence ledger
   └─ Emission-plane score input
```

### 2.1 Private `ExecutionTranscript`

Validator-controlled, non-public evidence sufficient for authorized reproduction and incident investigation. It may contain hidden exam reconstruction material, detailed logs, fine-grained metrics, tensor identifiers, and other controlled data.

Requirements:

- encrypted at rest or held inside an access-controlled validator evidence store;
- never returned through MCP, leaderboard, public API, or miner-visible logs;
- versioned schema;
- immutable after finalization except for append-only incident annotations;
- retention policy is operationally configurable but LIVE qualification must define the minimum evidence-retention window.

### 2.2 Signed `EvaluationReceipt`

A compact, stable, cryptographically signed commitment to an evaluation. The receipt is the durable protocol evidence object.

Minimum fields:

```text
receipt_schema_version
receipt_id
submission_id
strategy_hash

challenge_id
challenge_version
generator_version
generator_hash
scoring_version
scoring_pack_hash

backend_id
backend_profile_id
env_digest
limits_hash

exam_commitment
prediction_root
reference_root
metrics_root
gate_vector_commitment

run_status
S_phys
S_rob
S_acc
S_combined

started_at
finished_at
validator_hotkey
validator_signature
```

Rules:

1. `exam_commitment` commits to the authorized hidden exam identity/material but MUST NOT expose raw or derived official seeds, draw IDs, or reversible identifiers.
2. Score fields are only authoritative when produced by the challenge-bound current `Scoring.md` path and a valid receipt status.
3. `FAILED_INFRA`, incomplete, stub, mock, or non-LIVE receipts are mechanically non-emission-capable.
4. A receipt is immutable after signing. Corrections create a new receipt linked by `supersedes_receipt_id`; historical receipts remain preserved.
5. Receipt signing does not imply scientific qualification. It proves provenance of an execution claim, not that the challenge/backend is production-qualified.

### 2.3 Internal Model Card

The Model Card remains the rich internal scientific/operational record. It references the receipt and may include full allowed internal diagnostics. It MUST NOT be treated as equivalent to the miner/public EvaluationCard.

### 2.4 EvaluationCard

The EvaluationCard is an allow-listed miner-facing projection derived from the receipt + Model Card. Existing disclosure-budget and no-seed-leakage rules remain controlling.

---

## 3. Append-only evidence ledger

Carbon SHOULD maintain an append-only commitment log of finalized EvaluationReceipts.

Preferred design:

- receipts stored in durable object/database storage;
- canonical receipt hash inserted into an append-only Merkle structure or Merkle Mountain Range;
- periodic signed checkpoint root published by Carbon validators/operators;
- optional future on-chain anchoring of checkpoint roots when cost/benefit justifies it.

P0 does **not** require every receipt or tensor hash to be written on-chain.

The evidence ledger exists to provide tamper evidence and cross-system provenance, not to expose the exam.

---

## 4. Reproducibility contract

Carbon does not require universal cross-hardware bitwise equality for floating-point training. Reproducibility is qualified in three layers.

### R0 — exact artifact identity

The following MUST match exactly for a repeated identical official evaluation:

- canonical strategy representation/hash;
- challenge/generator/scoring versions and content hashes;
- execution limits/configuration;
- seed derivation inputs and role structure inside authorized validator scope;
- procedural sample identity/metadata where represented deterministically;
- environment/container digest;
- deterministic non-floating control-plane state;
- receipt commitment construction.

### R1 — numerical reproducibility

Floating numerical outputs, references, metrics, and training outcomes must agree within a **backend-qualified tolerance** established by repeated execution on the supported hardware/software profile.

No agent may invent this tolerance. It is human SciML/infra approved and bound to `backend_profile_id`.

### R2 — decision reproducibility

Repeated honest evaluation must be stable enough that backend noise does not unpredictably:

- flip mandatory gate status;
- convert an admissible result to scientific failure;
- materially reorder rankings beyond the qualified uncertainty band.

A result inside the qualified uncertainty band of a mandatory threshold is **CONTESTED / NON-EMITTING pending retry**, not automatically a physics failure.

For ranking or promotion, R2 is evaluated over separately realized,
producer-independent reconstruction replicates and common whole physical cases
or trajectories stratified by the registered stress design. Registered paired
seeds or common random numbers are permitted, but shared data, backbone,
seed-role, hardware, implementation, reference, representation, and execution
dependence remains in the model. The procedure must diagnose reconstruction-by-
case interaction and propagate joint reference uncertainty. A Challenge
Dossier qualifies the interval procedure and its applicability test; the exact
incumbent-challenger evidence must also satisfy that test before a zero-
covariance or quadrature shortcut is allowed.

### 4.1 Scientific stability repeats are not validator-integrity audits

Carbon uses two different repeat mechanisms:

- a **scientific reconstruction-stability repeat** samples the registered
  construction process to estimate failure probability, variability, tails,
  and reconstruction-by-case interaction. It is governed by the
  `ReconstructionEvidencePolicy` and may enter the paired scientific decision
  interval; and
- a **validator-integrity re-execution audit** under §9 tests whether an
  evaluator honestly executed and reported a committed contract. Its audit
  selection, disagreement, and quarantine evidence does not substitute for
  the scientific replicate design and does not directly change candidate
  score.

One execution may serve both roles only when the Challenge prospectively binds
both roles, preserves the required provenance and sampling design, and prevents
double-counting it as two independent units. Receipts and Dossiers label the
role explicitly as `SCIENTIFIC_STABILITY_REPEAT`, `VALIDATOR_INTEGRITY_AUDIT`,
or a prospectively authorized dual role.

---

## 5. Backend qualification

### 5.1 P0 backend decision

**P0 qualified training/evaluation backend: JAX-first.**

This is a qualification and implementation-scope decision, not a permanent ban on PyTorch or other frameworks.

`TrainEvalAPI` remains backend-oriented:

```text
TrainEvalAPI
  ├─ JaxBackend       # P0 target for qualification
  ├─ TorchBackend     # later, only after independent qualification
  └─ FutureBackend
```

Strategies describe approved training semantics; miners do not obtain arbitrary framework-code execution rights merely because multiple backends exist.

### 5.2 `backend_profile_id`

A qualified backend profile binds at least:

- backend implementation version;
- Python/runtime dependency lock;
- JAX/XLA/compiler version for the P0 JAX backend;
- accelerator class and supported driver/runtime cohort;
- numerical precision policy;
- deterministic-kernel/configuration policy;
- container/environment digest;
- measured R1/R2 reproducibility evidence.

LIVE evaluation must reject an unqualified backend profile.

### 5.3 Narrow P0 hardware cohort

P0 SHOULD qualify a narrow supported hardware/runtime cohort rather than weakening reproducibility requirements to support arbitrary heterogeneous accelerators.

Broader hardware cohorts are separate qualification events.

---

## 6. Infra/science type boundary

`infra ≠ science` must be enforced structurally, not only by convention.

Execution results SHOULD use a discriminated status model such as:

```text
Success
InvalidStrategy
StrategyNumericalFailure
StrategyTrainingFailure

InfraTimeout
InfraResourceViolation
InfraNodeFailure
ReferenceBackendFailure

IncompleteMetrics
```

Rules:

- only valid scientific/strategy results can construct authoritative `ScoreInput`;
- `Infra*` statuses cannot enter the physics-gate/scientific-failure path;
- Julia/SciML/reference-solver exceptions produce `ReferenceBackendFailure` or another explicit infra/reference status;
- infra failure produces retry/refund/quarantine semantics, never an invented hard-gate FAIL;
- partial metrics from failed infrastructure are non-authoritative and non-emission-capable.

---

## 7. Scientific plane vs emission plane

Carbon separates the durable scientific record from Bittensor economic consensus.

### 7.1 Scientific plane

```text
submission
 → qualified evaluator execution
 → signed EvaluationReceipt(s)
 → reproducibility / dispute logic
 → canonical scientific result
```

The scientific result is defined by Carbon's challenge contract, qualified execution evidence, and dispute policy — not merely by the public Bittensor weight vector.

### 7.2 Emission plane

```text
canonical scientific scores
 → Carbon/Bittensor weight policy
 → commit/reveal where applicable
 → Subtensor/Yuma/YC3
 → emissions
```

Bittensor determines network economic distribution. It does not retroactively redefine the scientific evidence stored for a submission.

### 7.3 P0 compatibility

This separation does not require a new blockchain or external consensus system in P0. A P0 implementation may use Carbon-operated/qualified validators as the scientific evaluators while still publishing Bittensor testnet weights exactly as Build Out requires.

The architectural separation exists so that later validator free-riding, network-mechanism changes, or commercial audit requirements do not destroy the underlying scientific provenance.

---

## 8. Validator free-riding / weight-copying threat

Carbon treats validator evaluation free-riding as an explicit economic/protocol threat.

The problem is not defined as "similar weights are malicious." Honest validators grading the same exam are expected to correlate strongly.

The relevant question is whether Carbon can sustain enough **actual scientific execution** when copying/consensus-following is cheaper than retraining.

Required pre-mainnet analysis:

- evaluator compute/reference/ops cost;
- submission rate and queue cost;
- validator stake distribution;
- copier/free-rider fraction scenarios;
- Bittensor validator incentive parameters then in force;
- audit/re-execution rate;
- honest evaluator operating margin;
- probability that sufficient independent scientific evidence exists;
- failure cases where economic consensus diverges from Carbon's canonical scientific result.

Similarity metrics may be used for telemetry and audit prioritization, never as sole proof of cheating.

---

## 9. Probabilistic re-execution audits

Carbon SHOULD add randomized secondary evaluation audits once real backend execution exists.

These are validator-integrity audits, not the scientific reconstruction-
stability repeats defined in §4.1. A high integrity-audit rate cannot repair an
underpowered scientific repeat design, and scientific repeat evidence cannot
excuse a dishonest or irreproducible evaluator.

Lifecycle:

1. primary evaluator finalizes and signs an EvaluationReceipt;
2. receipt commitment becomes immutable;
3. later public unpredictable randomness selects receipts/evaluators for audit;
4. an authorized qualified secondary evaluator receives the controlled reconstruction material;
5. secondary execution is compared under R0/R1/R2;
6. matching audit strengthens evidence; disagreement enters dispute handling.

Disagreement policy:

```text
first material disagreement
 → CONTESTED / NON-EMITTING
 → retry on qualified infrastructure

persistent disagreement
 → quarantine affected backend/challenge/profile
 → incident + human review
```

A miner is not assigned scientific zero merely because validators or infrastructure disagree about the experiment.

Audit rates may later be risk-based, but audit allocation MUST NOT modify the miner's scientific score.

---

## 10. Chain abstraction

Scientific modules must not depend directly on Bittensor SDK objects where an adapter boundary can preserve portability and testability.

Recommended protocol interfaces:

```text
ChainAdapter
BeaconProvider
MetagraphSnapshot
WeightPublisher
CommitRevealAdapter
ChainEventRecorder
```

Bittensor is the first implementation, not the scientific ontology.

Randomness should similarly use a provider abstraction:

```text
BeaconProvider
  ├─ Phase0ChainBeacon
  ├─ DrandBeacon
  └─ HybridBeacon
```

Do not conflate Bittensor weight commit/reveal with Carbon scientific exam randomness. They solve different protocol problems.

`Data_Management.md` + `Trustless_Verification.md` continue to own the actual scientific seed derivation rules.

---

## 11. CI as constitutional enforcement

Carbon's invariant suite should be treated as a trust-boundary enforcement layer, especially because implementation is agent-assisted.

Required invariant-test families include:

```text
no official seed/draw leakage
mock cannot access official material
weighted-geometric scoring only
binary hard-gate zeroing
forbidden score-input rejection
stub never emits
infra never becomes physics failure
LIVE requires exact qualification manifest
EvaluationPin/Receipt completeness
public EvaluationCard allow-list
receipt signature/hash stability
```

Tests must be written so that the easiest way for a coding agent to make CI green is to preserve the architecture rather than weaken an invariant.

---

## 12. Credibility Dossier crosswalk

Carbon's scientific qualification remains evidence-driven and challenge-specific, but dossier artifacts SHOULD be legible to established engineering V&V/VVUQ reviewers.

The qualification system should support a machine-readable crosswalk between Carbon evidence and external credibility concepts such as:

- context of use / claimed operating envelope;
- code verification;
- solution verification;
- generator/reference validation;
- uncertainty characterization;
- robustness/sensitivity evidence;
- configuration management;
- reproducibility evidence;
- provenance/evidence lineage;
- known limitations and requalification triggers.

Target vocabulary should draw from applicable ASME VVUQ and NASA modeling/simulation credibility frameworks where useful.

**Important:** a crosswalk is not a claim of standards compliance. Carbon may claim compliance only after the applicable requirements are explicitly reviewed and satisfied.

---

## 13. Proof-ready, proof-free P0

P0 does not require zero-knowledge proof of training or proof of evaluation.

However, receipt construction should preserve future option value through:

- canonical tensor serialization/order where practical;
- versioned domain-separated commitments;
- deterministic gate/scoring operator identifiers;
- committed prediction/reference/metric roots;
- stable receipt schemas.

A future proof system may prove narrow statements such as gate/scoring correctness over committed outputs without proving the entire training process.

No ZK mechanism may weaken hidden-evaluation controls or materially increase P0 honest-validator cost without a separately ratified decision.

---

## 14. Product and strategic use

The same evidence spine should later support a **Qualified Strategy Package** or qualified surrogate artifact containing, as applicable:

- strategy/recipe identity;
- challenge/version;
- operating envelope;
- qualification evidence and credibility crosswalk;
- backend/reproduction profile;
- performance distributions;
- known limitations;
- provenance/receipt lineage;
- requalification triggers.

This enables Carbon to act as a neutral discovery/qualification/evidence rail. External engineering-AI platforms may be competitors, miners, customers, integrators, or consumers of qualified Carbon evidence depending on the commercial relationship.

---

## 15. Maturity and launch rules

Nothing in this specification is automatically PRODUCTION-QUALIFIED because it is specified or implemented.

- EvaluationReceipt schema can be SPECIFIED/IMPLEMENTED before validator audit policy is scientifically/economically qualified.
- Backend profiles must be TESTED and human-approved before LIVE.
- Validator audit economics must be measured before mainnet claims.
- Credibility crosswalks do not create standards compliance by documentation alone.
- Future proof-readiness does not imply a ZK system exists.

Existing Carbon maturity vocabulary remains mandatory: **SPECIFIED / IMPLEMENTED / TESTED / PRODUCTION-QUALIFIED**.
