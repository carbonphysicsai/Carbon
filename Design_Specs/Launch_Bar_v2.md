# Carbon Launch Bar v2 — Qualified Challenge, Frontier, and Settlement Stop-Ships

**Status:** OWNER-RECOMMENDED v2 for review; does not replace current `Launch_Bar.md` until ratified.  
**Purpose:** Define what must be green before Carbon calls a Challenge scientifically LIVE and what additional evidence is required before that Challenge is payout-enabled.

## 1. Two bars, not one

```text
SCIENTIFIC_CHALLENGE_LIVE
        ↓
PAYOUT_ENABLED
```

A Challenge may be scientifically executable before the frontier/treasury economy is production-qualified.

## 2. Scientific Challenge LIVE bar

### Task and authority
- [ ] PhysicalSystemSpec reviewed and exact identity pinned.
- [ ] CandidateOutputContract contains every causal input required to define the target, or the variable is fixed by the Challenge.
- [ ] Claim / operating envelope is explicit, bounded, and evidence-supported.

### Population and finite evidence
- [ ] `InstanceDistributionContract` defines the target population.
- [ ] `SamplingPlan` defines `Q(x)`, sample budget, strata/tails, repeats, stopping/extension, and censoring behavior.
- [ ] `P(x)`, `Q(x)`, and score/evidence weighting are not silently conflated.
- [ ] Generator distribution conformance is demonstrated.
- [ ] Intended and realized evidence populations are compared where censoring can matter.

### Truth / reference
- [ ] Challenge-specific ReferencePolicy is pinned.
- [ ] Analytic/numerical/experimental truth path is verified for the claimed regime.
- [ ] Reference uncertainty/failure/disagreement states are explicit.
- [ ] Independent corroboration is used where scientifically useful; a second solver is not assumed correct merely because it is independent.
- [ ] Truth-dominance test demonstrates official evidence does not reward generator-specific numerical error over qualified physical truth within claimed resolution.

### Measurements
- [ ] Every mandatory or score-bearing measurement has a qualified MeasurementContract.
- [ ] Applicability, numerical implementation, normalization, precision/reference floor, aggregation, and uncertainty are pinned.
- [ ] Diagnostic-only measurements cannot silently enter admissibility/ranking.

### Validation Dossier
- [ ] Required D1–D12 evidence classes are PASS / PASS_WITH_LIMITATIONS / N/A with justified bounded claim.
- [ ] No required evidence class is FAIL/BLOCKED.
- [ ] Dossier binds exact upstream versions/digests.

### Score Pack
- [ ] Exact Score Pack identity/hash pinned.
- [ ] Evidence eligibility states are handled fail-closed/prospectively.
- [ ] Mandatory admissibility precedes soft ranking.
- [ ] Explicit estimands identify their populations and MeasurementContracts.
- [ ] Required strata cannot be averaged away.
- [ ] Uncertainty/indeterminate semantics are registered where required.
- [ ] Current numerical execution profile is reproducible on the qualified validator cohort.

### Security and disclosure
- [ ] Official randomness unavailable to producer at commitment time under registered policy.
- [ ] construction/eval/stress or equivalent roles are decontaminated sufficiently for the claim.
- [ ] producer cannot control official population, truth path, measurement, or threshold.
- [ ] EvaluationCard/disclosure red-team passes the registered information-budget criteria.

## 3. Candidate-market discrimination bar

Before claiming the Challenge creates a useful ranking market:

- [ ] realistic strategy population contains scientifically admissible and inadmissible candidates;
- [ ] deliberate pathological candidates fail for the intended reasons;
- [ ] expected scientific ordering survives adversarial metric tests;
- [ ] reconstruction variance measured across independent builds;
- [ ] evaluation-draw variance measured;
- [ ] validator implementation agreement demonstrated;
- [ ] rank-reversal/indeterminate rates are acceptable for the intended use.

If all realistic strategies fail, the judge may be scientifically valid but there is not yet a useful miner market.

## 4. Frontier promotion bar

Before performance payouts:

- [ ] Challenge has a registered `FrontierBaseline` / incumbent identity.
- [ ] `LeaderReplacementPolicy` is versioned and Challenge-specific.
- [ ] common fresh promotion experiment is implemented where independent historical scores are not sufficiently comparable.
- [ ] promotion outputs `SUPERIOR`, `NOT_SUPERIOR`, or `INDETERMINATE` rather than raw floating-point comparison only.
- [ ] at most one paid frontier event per Challenge/window under default batched policy.
- [ ] `FrontierAdvanceEvent` binds Challenge, prior frontier, winning method, promotion evidence, Score Pack/Dossier, recipient, and entitlement.
- [ ] duplicate / replay / stale-version frontier events fail closed.

## 5. Challenge portfolio bar

Before multi-Challenge performance settlement:

- [ ] `ChallengeSetEpoch` freezes exact reward-enabled Challenge IDs/versions for the period.
- [ ] `N` and equal notional `1/N` opportunity are deterministic and auditable.
- [ ] raw scores across Challenges are never used as a shared scientific unit.
- [ ] adding/freezing/retiring/versioning a Challenge applies prospectively to the next epoch.
- [ ] no-event Challenge opportunity is not silently redistributed to other Challenge winners.

## 6. Treasury / payout-enabled bar

Before calling performance settlement production-ready:

- [ ] registered treasury neuron receives intended miner-side subnet emission on localnet/testnet.
- [ ] no unintended `MinerBurned` / normalization / cross-subnet penalty invalidates intended economics.
- [ ] TreasuryVault custody and transfer path tested with real Bittensor precompiles used by target deployment.
- [ ] TreasuryController or equivalent verifies exact `FrontierAdvanceEvent` binding.
- [ ] proposer cannot alter recipient/amount/ChallengeSetEpoch entitlement.
- [ ] one frontier event cannot be paid twice.
- [ ] active-validator governance / quorum / success / timelock / expiry / cancellation behavior is adversarially tested.
- [ ] spending/rate limits constrain governance compromise.
- [ ] admin/proposer censorship is observable and has a recovery/minimization path.
- [ ] chain/RPC/gas-estimation failure yields payout-pending state, not scientific failure.
- [ ] Challenge freeze blocks settlement without mutating prior scientific evidence.
- [ ] event ledger ↔ treasury ledger ↔ executed transfer reconcile exactly.

## 7. Burgers-specific bar

For the first owner-recommended authoritative Burgers slice:

- [ ] fixed `nu=5e-3` task is ratified or explicitly modified by Physics/SciML lead.
- [ ] Cole–Hopf implementation qualified and exact reference floor documented.
- [ ] old variable-hidden-viscosity task is not treated as authoritative under the same Challenge identity.
- [ ] old final-time `|u u_x - nu u_xx|` spatial-balance proxy is diagnostic-only unless separately requalified; it is not represented as a full PDE residual.
- [ ] finite / mass / energy / maximum-principle / field-error / stress-stratum MeasurementContracts are ratified as applicable.
- [ ] reconstruction-repeat policy selected from measured variance.

## 8. Landscape publish bar

Landscape remains downstream of the scientific Challenge bar.

- [ ] no public physics-intelligence/causal claims before qualified evidence volume and prospective validation justify them.
- [ ] Port B cannot change the mandatory registered grade per miner.
- [ ] Port C cannot change equal base performance opportunity inside an active `ChallengeSetEpoch`.
- [ ] separate information-value bounties, if introduced, are explicitly distinct from frontier performance reward.

## 9. Stop-ship summary

```text
PAYOUT_ENABLED =
    SCIENTIFIC_CHALLENGE_LIVE
    AND candidate_market_discriminates
    AND frontier_promotion_qualified
    AND challenge_portfolio_accounting_valid
    AND treasury_chain_path_qualified
```

> **First prove the exam. Then prove the frontier decision. Then prove the settlement path. Only then pay for the advance.**
