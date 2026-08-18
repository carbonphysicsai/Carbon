# Carbon Context
**Status:** v1 — team review

## Mission
Carbon is a competitive scientific-computing system, initially a Bittensor subnet, for discovering and independently evaluating neural-operator training strategies. Miners submit methods; validators independently retrain them on hidden procedural data under a pinned challenge contract. Mandatory physics gates establish admissibility; surviving strategies are ranked on physics fidelity, robustness, and accuracy.

Carbon's durable asset is the verified record of which training methods survive difficult scientific exams. That record can improve future search and, through a separate qualification path, produce envelope-qualified engineering surrogates.

## Core loop
`miner/agent → free research loop → strategy submission → shared hidden exam → independent retraining → binary gates → weighted-geometric lean score → EvaluationCard + Model Card → later Landscape → specialist candidate → fresh retrain + Product Battery → qualified artifact`

## Trust boundary
**Public:** challenge/envelope/exclusions, generator logic, scoring mathematics, gate definitions, versions/hashes, validation dossier, protocol rules.

**Hidden/controlled:** realized official draws/seeds on miner paths, reconstruction-sensitive diagnostics, private Landscape intelligence, Product-Battery seeds, full commercial artifacts.

The declared physics is public. The answer sheet is hidden.

## Scientific credibility
The operating envelope is the claim boundary. Before LIVE, a generator earns a reproducible dossier using evidence appropriate to its physics: analytic/manufactured truth, converged numerical references, multi-code agreement, industrial goldens, conservation, coverage, and model-form uncertainty as applicable.

**Strength of claim ≤ strength of evidence.** Reference disagreement is documented and resolved by better evidence, narrower envelopes, or explicit uncertainty—not by weakening gates. Reference caches qualify generators; fresh procedural draws examine miners.

## Scoring
Mandatory hard gates are binary; any mandatory fail gives `S_combined = 0`. Survivors receive normalized physics, robustness, and accuracy legs combined by weighted geometric mean. P0 baseline weights are 0.45/0.30/0.25. Challenge packs may specialize weights; scientific thresholds/categories are dossier-calibrated and pack-bound.

Fees, priors, mock/light metrics, Landscape similarity, and Product-Battery status are forbidden lean-score inputs.

## Data and consensus
Official `train ≠ eval ≠ stress`. Validators grading one submission use the same scientific exam identity. Validator identity is excluded from scientific seed derivation. All score-bearing draws remain inside the declared envelope; stress may concentrate on rare regimes and edges.

## Miner interface
Miner MCP provides a dense free loop and a rare official submit loop. Free practice is honest but cheaper, shallower, coverage-limited, and non-authoritative. It never sees the official realized exam and never grants emissions. EvaluationCard is budgeted to support repair without becoming a grader oracle.

## Landscape
Landscape is build-ordered, not assumed live at P0. It learns from verified Model Cards and later promotion outcomes, fits symbolic/causal hypotheses, improves search guidance, and ranks opportunities. It never overrides gates; causal effects are observational decision support.

## Specialist Bank
Leaderboard rank is not product qualification. A winning strategy may seed a candidate, but a commercial full surrogate requires fresh controlled retraining and the applicable Product Battery. Product evidence is decontaminated from the lean draws that justified promotion where feasible.

## P0
P0 proves one complete vertical through hidden evaluation, scoring/cards, and actual Bittensor testnet weights. Additional Phase-0 PDEs are independently qualified packs. Landscape, specialists, and mainnet are not implied by P0 completion.

## Maturity vocabulary
- **SPECIFIED:** normative intended behavior exists.
- **IMPLEMENTED:** required code exists.
- **TESTED:** acceptance/invariant tests pass in the intended environment.
- **PRODUCTION-QUALIFIED:** required scientific/security/operational qualification has passed.

Never infer one from another.
