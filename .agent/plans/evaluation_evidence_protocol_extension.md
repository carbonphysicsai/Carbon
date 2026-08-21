# Plan — Evaluation Evidence & Validator Audit Extension

**Scope:** implementation guidance only; no ticket status changes.  
**Normative design:** `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md`  
**Sequencing:** `Design_Specs/Build_Out.md` v1.4 + `Design_Specs/Build_Out_Protocol_Extension.md`

## Rules

1. Do not reorder A0–A12.
2. Do not implement Wave B/C real-backend/audit work during a Wave A ticket unless the board is explicitly expanded.
3. Preserve no-seed-leakage, mock isolation, weighted-geometric scoring, stub non-emission, and infra≠science.
4. Receipt commitments must not expose raw official seeds/draw IDs/reversible exam identifiers.
5. Scientific thresholds and reproducibility tolerances remain human-owned.
6. JAX is the first backend targeted for P0 qualification; do not make other adapters emission-capable by default.
7. No ZK/proof-of-training scope in P0.

## Ticket hooks

| Ticket | Extension hook |
|---|---|
| A0 | Reserve clean `evaluation`, `audit`, `chain`, `qualification` boundaries in canonical `carbon/`; no deep Bittensor coupling in scientific modules. |
| A1 | CI structure must support invariant tests; no GPU requirement yet. |
| A3 | Registry reserves receipt schema/backend-profile/evidence qualification bindings. |
| A4 | Add safe `exam_commitment` interface and leakage tests; do not change ratified seed semantics. |
| A5 | Stable current-spec score result suitable for receipt commitment; no scoring redesign. |
| A6 | Store the exact private A5 result behind its opaque authorization binding and project the miner EvaluationCard. Transcript, receipt, rich Internal Model Card, signing, and evidence persistence remain later-owned. |
| A8 | Produce a deterministic mechanically non-emitting stub result. A later evidence owner may consume it for a fixture receipt; A8 does not create or own that receipt. |
| A10 | Public-safe receipt reference only; no extra hidden detail. |
| A11 | Receipt/evidence lifecycle metrics + redaction; no hidden seeds in logs. |
| A12 | Constitutional tests for receipt/public projection, infra/science, stub emission and qualification boundaries. |

## Wave B after authorization

- reproducibility harness skeleton: R0/R1/R2;
- backend profile artifact schema;
- Julia/reference exception → typed infra/reference status;
- credibility dossier crosswalk structure.

## Wave C after authorization

- real signed EvaluationReceipts;
- append-only receipt commitment log;
- Bittensor chain adapter and real testnet weights;
- canonical scientific-result record before weight transformation;
- validator free-rider economics simulator;
- controlled probabilistic re-execution audit prototype.

## Review checklist for any implementation PR

- Does it make the hidden exam more reconstructable? If yes, reject or redesign.
- Can an infra/reference error reach the ScoreEngine? If yes, reject.
- Can mock/stub evidence reach emissions? If yes, reject.
- Does Bittensor SDK state leak into scientific logic without need? Prefer adapter.
- Does the change claim backend qualification without measured evidence? Reject.
- Does the change invent a reproducibility tolerance? Block for human input.
- Does it preserve immutable version/hash binding and historical evidence? Required.
