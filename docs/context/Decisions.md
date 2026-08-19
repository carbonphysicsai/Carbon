# Carbon Decisions
**Status:** v1 — team review

This ledger records reconciled architectural decisions. Detailed semantics remain in the domain specifications.

## Authority
Authority is domain-owned: `SPEC.md` owns architecture; `Scoring.md` scoring mathematics; `Data_Management.md` + `Trustless_Verification.md` official data/seeding; `Miner_MCP.md` miner behavior/disclosure; generator/evidence specs scientific qualification; `Evaluation_Evidence_and_Validator_Audit.md` execution evidence, reproducibility qualification, validator audit and scientific-vs-emission separation; `Launch_Bar.md` stop-ships; `Landscape_Agent.md` knowledge-layer behavior; `Specialist_Bank.md` candidate selection, Product Battery execution, banking and commercial egress; `Product_Qualification_Evidence.md` product-plane evidence objects, bounded qualification claims, disclosure tiers and requalification lifecycle; `Build_Out.md` sequencing, with `Build_Out_Protocol_Extension.md` as the ratified additive extension pending fold-in to the next Build Out revision.

## Decisions
- **D-001 Strategy competition:** miners submit schema-versioned training strategies; validators independently retrain/evaluate them.
- **D-002 P0 vertical first:** prove one complete LIVE challenge loop before Phase-0 breadth; additional PDEs are independently qualified packs.
- **D-003 Shared exam identity:** validators grading one submission use the same challenge-bound scientific exam; validator identity is excluded from seed derivation.
- **D-004 Public unpredictable randomness:** Phase 0 uses blockchain-derived public unpredictable randomness; production randomness is strengthened before production-grade claims.
- **D-005 Public physics, hidden realization:** envelope, generator logic, scoring, gates, versions, and dossier are auditable; realized official draws and reconstruction-sensitive diagnostics are hidden.
- **D-006 Envelope closure:** all score-bearing draws stay inside the declared challenge envelope; outside-envelope probes are diagnostic unless a new version expands the contract.
- **D-007 Train ≠ eval ≠ stress:** official roles are separately seeded; miners never control official eval/stress draws, thresholds, or eval configuration.
- **D-008 Binary hard gates:** any mandatory FAIL forces authoritative score zero; smooth surrogates are non-authoritative only.
- **D-009 Gates vs margins:** gates determine admissibility; continuous physics margins rank survivors.
- **D-010 Weighted geometric score:** `S = S_phys^w_p × S_rob^w_r × S_acc^w_a`; P0 baseline is 0.45/0.30/0.25, applied once.
- **D-011 Pack-bound science:** LIVE thresholds, envelopes, categories, and tolerances are dossier-calibrated and versioned; generic numbers are illustrative.
- **D-012 UQ is claim-dependent:** no universal P0 UQ hard gate.
- **D-013 Evidence-appropriate dossiers:** generator qualification validates the actual physics claim rather than enforcing one ceremonial checklist.
- **D-014 Reference caches qualify generators:** they are not the normal live miner benchmark.
- **D-015 No silent rescore:** historical results remain bound to their original versions.
- **D-016 Honest non-oracle free loop:** mock/light physics is honest but computationally/evaluatively incomplete, never official, and never emission-capable.
- **D-017 Budgeted disclosure:** EvaluationCard is an allow-listed projection of the richer Model Card.
- **D-018 Economic separation:** fees, priors, mock/light metrics, Landscape similarity, and Product-Battery status never enter lean scientific score/emissions.
- **D-019 Infra ≠ science:** infrastructure failure is separate from scientific/strategy failure.
- **D-020 Same mandatory lean exam:** Port B may schedule/prefilter/supplement but may not vary the mandatory score-bearing exam per miner.
- **D-021 Versioned adaptive stress:** new failure modes affect future validated pack versions, not a live version silently.
- **D-022 Landscape is decision support:** causal/symbolic outputs guide search but cannot satisfy gates or independently qualify products.
- **D-023 Competition ≠ product qualification:** commercial full surrogates require fresh retraining and the applicable Product Battery.
- **D-024 Winner may seed candidate:** a winning strategy is a valid specialist candidate; rank/checkpoint is not qualification.
- **D-025 Product decontamination:** opportunity, bank-verification, and Product-Battery draws use separate seed material where feasible.
- **D-026 LIVE is qualification:** exact-version scientific, scoring, backend, disclosure, security/operational, and Launch-Bar evidence is required.
- **D-027 Explicit maturity states:** use SPECIFIED / IMPLEMENTED / TESTED / PRODUCTION-QUALIFIED; no state implies the next.
- **D-028 KEEP → WRAP → REPAIR → REPLACE:** reconciled specs govern design; historical code is retained only where useful and compliant.
- **D-029 EvaluationReceipt evidence spine:** every official evaluation is designed to yield a signed, immutable EvaluationReceipt committing to execution identity/results without exposing hidden exam reconstruction material. Private ExecutionTranscript, EvaluationReceipt, Internal Model Card, and miner EvaluationCard are distinct artifacts.
- **D-030 Commitment ≠ disclosure:** exam/result commitments may be auditable while raw official seeds, derived seeds, draw IDs, reversible identifiers, and reconstruction-sensitive diagnostics remain hidden under existing disclosure rules.
- **D-031 Three-layer reproducibility:** Carbon distinguishes R0 exact artifact identity, R1 backend-qualified numerical reproducibility, and R2 gate/ranking decision reproducibility. Universal arbitrary-hardware floating-point bit identity is not a protocol requirement.
- **D-032 Contested uncertainty band:** a result whose qualified backend uncertainty can materially flip a mandatory threshold is CONTESTED/NON-EMITTING pending retry; validator/backend disagreement is not converted into a miner physics zero.
- **D-033 JAX-first P0 backend:** JAX is the first backend targeted for full P0 TrainEval qualification. Other backends may be added through adapters only after separate qualification; adapter existence does not make a backend emission-capable.
- **D-034 Narrow qualified hardware cohort:** P0 prefers a narrow measured hardware/software cohort bound by `backend_profile_id` over weakening reproducibility requirements for arbitrary heterogeneous accelerators.
- **D-035 Type-safe infra/science boundary:** infra/reference failures must be structurally unable to enter authoritative physics scoring. Julia/SciML/reference exceptions produce explicit infra/reference statuses, retry/refund/quarantine semantics, and no invented gate failure.
- **D-036 Scientific plane ≠ emission plane:** Carbon's durable scientific result is defined by qualified evaluation evidence and dispute policy; Bittensor transforms canonical scientific scores into economic weights/emissions but does not retroactively redefine the scientific record.
- **D-037 Validator free-riding is explicit threat:** copied/consensus-following validator weights are treated as a protocol/economic sustainability threat. Weight similarity alone is telemetry, not proof of cheating. Mainnet planning requires honest-evaluator economics/free-rider scenario analysis.
- **D-038 Probabilistic re-execution audits:** after a receipt commitment is immutable, future unpredictable randomness may select evaluations for qualified secondary re-execution under R0/R1/R2. Audit allocation never changes the miner's scientific score.
- **D-039 Chain adapter boundary:** scientific modules should interact with Bittensor through narrow chain/metagraph/weight/commit-reveal adapters where practical. Bittensor is Carbon's first economic network implementation, not the scientific ontology. Scientific beacon semantics remain owned by data/seeding specs.
- **D-040 Append-only evidence ledger:** finalized receipt hashes should be stored in an append-only Merkle/MMR-style evidence log with signed checkpoints; per-receipt on-chain storage is not a P0 requirement.
- **D-041 CI is constitutional enforcement:** Wave A invariant CI must make hidden-evaluation leakage, mock/official crossing, stale scoring semantics, stub emission, infra→science conversion, qualification bypass, and receipt/public-projection violations mechanically difficult to regress.
- **D-042 Credibility crosswalk:** Carbon qualification evidence should be machine-readable against applicable external V&V/VVUQ/context-of-use terminology where useful. A crosswalk is not itself a standards-compliance claim.
- **D-043 Proof-ready, proof-free P0:** P0 does not require ZK/proof-of-training. Canonical commitments and stable receipt schemas should preserve future option value for narrow proofs over committed outputs/gate verdicts without raising P0 validator cost.
- **D-044 Neutral evidence rail:** Carbon's durable strategic asset includes qualified strategy/model provenance and credibility evidence, allowing external engineering-AI platforms to be competitors, miners, customers, integrators, or evidence consumers rather than forcing Carbon into a single vertically integrated CAE-platform position.
- **D-045 Model Card immutability across promotion:** a fresh product retrain creates a new product-candidate Model Card linked to prior strategy/evidence lineage; competition Model Cards are never mutated into product certificates.
- **D-046 Product Battery Record:** every product qualification attempt, including failures, produces an immutable version-bound Product Battery Record. Failed attempts remain evidence and may inform future search/product decisions without altering historical subnet scores.
- **D-047 Qualification Record:** the canonical product-plane claim object is a signed, immutable Qualification Record binding one exact model artifact to one context of use, qualification-policy/Product-Battery version, evidence set, limitations, escalation conditions, and requalification triggers. It is an evidence-backed bounded claim, not a generic safety or regulatory certificate.
- **D-048 Qualification lifecycle is append-only:** qualification may later be superseded or require requalification, but historical Model Cards, Product Battery Records, and Qualification Records are not rewritten. Current-state changes create linked records/events with explicit semantics.
- **D-049 Product transparency is tiered:** Carbon opens the claim and provenance while disclosure remains allow-listed by audience. Public/catalog, buyer/diligence, and private/audit surfaces may expose different evidence; hidden exam reconstruction material and proprietary recipes remain controlled.
- **D-050 Qualified Specialist is a package:** a commercial full specialist is the deployable artifact plus its product-candidate Model Card, Product Battery Record, Qualification Record, supporting evidence references, deployment identity, and commercial controls. Rank/checkpoint alone is never the product claim.
