# Carbon Context
**Status:** v1 — team review

## Mission
Carbon is a competitive scientific-computing system, initially a Bittensor subnet, for discovering and independently evaluating neural-operator training strategies. Miners submit methods; validators independently retrain them on hidden procedural data under a pinned challenge contract. Mandatory physics gates establish admissibility; surviving strategies are ranked on physics fidelity, robustness, and accuracy.

Carbon's durable asset is the verified record of which training methods survive difficult scientific exams. That record can improve future search and, through a separate qualification path, produce envelope-qualified engineering surrogates. The durable record is not only a leaderboard: it is an evidence chain linking strategy identity, challenge/version, qualified execution environment, scientific result, and later product qualification.

## Core loop
`miner/agent → free research loop → strategy submission → shared hidden exam → independent retraining → binary gates → weighted-geometric lean score → signed EvaluationReceipt → EvaluationCard + Model Card → Bittensor emission mapping → later Landscape → specialist candidate → fresh retrain + Product Battery → qualified artifact`

## Trust boundary
**Public:** challenge/envelope/exclusions, generator logic, scoring mathematics, gate definitions, versions/hashes, validation dossier, protocol rules, and public-safe commitments/provenance.

**Hidden/controlled:** realized official draws/seeds on miner paths, reconstruction-sensitive diagnostics, private ExecutionTranscript material, private Landscape intelligence, Product-Battery seeds, full commercial artifacts.

The declared physics is public. The answer sheet is hidden. **Commitment is not disclosure:** Carbon may publish cryptographic commitments to an exam/result without publishing the seed or reversible exam identity.

## Evaluation evidence
Every official evaluation is designed to produce a private ExecutionTranscript and a signed immutable EvaluationReceipt. The receipt commits to the strategy, challenge/generator/scoring versions, qualified backend/environment, result commitments, gate vector, score, status, and validator identity without exposing hidden exam reconstruction material.

The Internal Model Card and miner-facing EvaluationCard are projections/consumers of that evidence, not substitutes for it. EvaluationCard remains budgeted and allow-listed.

Finalized receipt hashes should enter an append-only Merkle/MMR-style evidence log with signed checkpoints. P0 does not require every receipt to be stored on-chain.

## Reproducibility
Carbon distinguishes three layers:

- **R0 exact artifact identity:** hashes, versions, pins, deterministic control state, commitment construction, and equivalent non-floating artifacts match exactly.
- **R1 numerical reproducibility:** floating outputs/metrics agree within a backend-qualified, human-approved tolerance.
- **R2 decision reproducibility:** backend noise must not unpredictably flip mandatory gates or materially reorder authoritative outcomes beyond the qualified uncertainty band.

Universal bit-for-bit equality across arbitrary heterogeneous accelerators is not a Carbon protocol requirement. P0 targets a narrow qualified hardware/software cohort and a JAX-first TrainEval backend. Other backends require separate qualification before becoming emission-capable.

A result inside the qualified uncertainty band of a mandatory threshold is contested/non-emitting pending retry; validator/backend disagreement is not silently converted into a miner physics failure.

## Scientific credibility
The operating envelope is the claim boundary. Before LIVE, a generator earns a reproducible dossier using evidence appropriate to its physics: analytic/manufactured truth, converged numerical references, multi-code agreement, industrial goldens, conservation, coverage, and model-form uncertainty as applicable.

**Strength of claim ≤ strength of evidence.** Reference disagreement is documented and resolved by better evidence, narrower envelopes, or explicit uncertainty—not by weakening gates. Reference caches qualify generators; fresh procedural draws examine miners.

Carbon should map dossier evidence onto applicable external V&V/VVUQ/context-of-use vocabulary where useful so the evidence is legible to engineering reviewers. A crosswalk is not itself a standards-compliance claim.

## Scoring
Mandatory hard gates are binary; any mandatory fail gives `S_combined = 0`. Survivors receive normalized physics, robustness, and accuracy legs combined by weighted geometric mean. P0 baseline weights are 0.45/0.30/0.25. Challenge packs may specialize weights; scientific thresholds/categories are dossier-calibrated and pack-bound.

Fees, priors, mock/light metrics, Landscape similarity, Product-Battery status, audit rate, and validator similarity are forbidden lean-score inputs.

## Data and consensus
Official `train ≠ eval ≠ stress`. Validators grading one submission use the same scientific exam identity. Validator identity is excluded from scientific seed derivation. All score-bearing draws remain inside the declared envelope; stress may concentrate on rare regimes and edges.

Randomness providers may evolve from a Phase-0 chain beacon toward stronger Drand/hybrid designs, but scientific seed semantics remain owned by the data/seeding specifications. Bittensor weight commit/reveal and Carbon exam randomness are distinct protocol concerns.

## Scientific plane and emission plane
Carbon separates the durable scientific result from Bittensor economic consensus.

**Scientific plane:** submission → qualified evaluation → signed receipt(s) → reproducibility/dispute handling → canonical scientific result.

**Emission plane:** canonical scientific scores → Carbon/Bittensor weight policy → commit/reveal as applicable → Subtensor/Yuma/YC3 → emissions.

Bittensor is Carbon's first economic network implementation. The public weight vector does not retroactively redefine historical scientific evidence.

Validator evaluation free-riding/weight copying is therefore treated as a protocol/economic sustainability threat rather than the definition of scientific truth. Weight similarity alone is telemetry, not proof of cheating. Mainnet planning requires explicit honest-evaluator economics and free-rider scenario analysis.

## Validator audits
After a primary receipt commitment is immutable, future unpredictable randomness may select a subset of evaluations for authorized qualified secondary re-execution. Audits compare R0/R1/R2 evidence. Material disagreement makes the evaluation contested/non-emitting pending retry and may quarantine a backend/challenge combination; it does not automatically assign a miner physics zero.

Audit allocation may improve validator accountability and evidence quality but never enters the miner scientific score.

## Infra ≠ science
Infrastructure/reference failures are structurally separate from scientific or strategy failures. Julia/SciML/reference exceptions, node failures, queue loss, policy OOM kills, and equivalent infra failures produce typed infra/reference statuses and retry/refund/quarantine semantics. They do not synthesize hard-gate failures.

## Miner interface
Miner MCP provides a dense free loop and a rare official submit loop. Free practice is honest but cheaper, shallower, coverage-limited, and non-authoritative. It never sees the official realized exam and never grants emissions. EvaluationCard is budgeted to support repair without becoming a grader oracle.

## Chain boundary
Scientific modules should depend on narrow chain/metagraph/weight/beacon interfaces rather than deeply embedding Bittensor SDK objects where practical. Bittensor is the first adapter. This preserves testability and Carbon's scientific provenance if network implementation details evolve.

## Landscape
Landscape is build-ordered, not assumed live at P0. It learns from verified Model Cards and later promotion outcomes, fits symbolic/causal hypotheses, improves search guidance, and ranks opportunities. It never overrides gates; causal effects are observational decision support.

## Specialist Bank
Leaderboard rank is not product qualification. A winning strategy may seed a candidate, but a commercial full surrogate requires fresh controlled retraining and the applicable Product Battery. Product evidence is decontaminated from the lean draws that justified promotion where feasible.

The same evidence spine should later support qualified strategy/model packages with operating envelope, credibility evidence, reproduction profile, known limitations, provenance lineage, and requalification triggers. This allows Carbon to serve as a neutral discovery/qualification/evidence rail rather than requiring every downstream engineering platform to be vertically replaced.

## P0
P0 proves one complete vertical through hidden evaluation, scoring/cards, signed evidence structure, and actual Bittensor testnet weights. Additional Phase-0 PDEs are independently qualified packs. Landscape, specialists, mainnet, production validator-audit economics, and ZK proofs are not implied by P0 completion.

P0 is **proof-ready but proof-free**: canonical commitments should preserve future option value for narrow proofs over committed outputs/gate verdicts, but proof-of-training/ZK is not a P0 requirement.

## Maturity vocabulary
- **SPECIFIED:** normative intended behavior exists.
- **IMPLEMENTED:** required code exists.
- **TESTED:** acceptance/invariant tests pass in the intended environment.
- **PRODUCTION-QUALIFIED:** required scientific/security/operational qualification has passed.

Never infer one from another.
