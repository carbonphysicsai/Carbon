# Carbon Open Questions v2 — Integrated Architecture

**Status:** owner-recommended unresolved-question ledger for tech/science/economic/security review.  
**Supersedes:** `docs/context/Open_Questions.md` for current integrated design discussion.  
**Rule:** resolved architecture belongs in design specs/decisions; only genuinely unresolved human-owned choices belong here.

## First qualified Burgers Challenge

- **OQ2-001 — Final fixed-ν Burgers population.** Ratify exact IC population, `T`, resolution, stress strata, exclusions, and SamplingPlan around the owner-recommended fixed `nu=5e-3` slice. **Owner:** Physics/SciML.
- **OQ2-002 — Cole–Hopf reference implementation qualification.** Pin numerical representation, resolution/precision, convergence evidence, uncertainty floor, and corroborating numerical-witness requirements. **Owner:** Physics/SciML.
- **OQ2-003 — Burgers MeasurementContracts.** Ratify exact definitions and numerical implementations for finite output, mean/mass conservation, energy non-increase, maximum-principle consistency, field error, and stress-stratum error. **Owner:** Physics/SciML.
- **OQ2-004 — First LIVE Score Pack.** Ratify mandatory predicates, thresholds, soft transforms, strata handling, estimands, and current P0 profile after the dossier is complete. **Owner:** Physics + protocol.
- **OQ2-005 — Reconstruction-repeat policy.** Choose repeat count / summary / admissibility probability or other method-quality policy from measured reconstruction variance. **Owner:** Physics + protocol + infra.
- **OQ2-006 — LeaderReplacementPolicy.** Set the first Challenge's scientifically meaningful superiority / indeterminate rule from promotion-exam variance. **Owner:** Physics + protocol.

## Challenge portfolio

- **OQ2-007 — Phase-0 portfolio membership.** Select the first 4–7 qualified academic Challenges and the order in which they enter reward-enabled `ChallengeSetEpoch`s. Seven PDE families remains an ambition, not an automatic activation list. **Owner:** Physics + protocol.
- **OQ2-008 — Settlement-window cadence.** Set Challenge promotion/settlement windows compatible with evaluation cost, Bittensor timing, and treasury accounting. **Owner:** Protocol/economics.
- **OQ2-009 — Frontier baseline policy.** Decide how each Challenge's initial independently reconstructed `FrontierBaseline` is selected and versioned. **Owner:** Physics + protocol.
- **OQ2-010 — Staged-disclosure mitigation.** Ratify fee/rate/cadence or other safeguards against intentionally releasing incremental improvements over many windows. **Owner:** Economics + protocol.

## Treasury / Bittensor settlement

- **OQ2-011 — Treasury contract starting point.** Decide whether Carbon forks/adapts Enigma/Church-of-Rao patterns or implements a fresh controller/vault pair. **Owner:** Protocol + security.
- **OQ2-012 — Proposal authority.** Determine launch proposer design and recovery path; minimize ability of one admin to censor a valid event indefinitely. **Owner:** Governance + security.
- **OQ2-013 — Validator governance parameters.** Quorum, success threshold, voting delay/period, timelock, expiry, cancellation, validator eligibility. **Owner:** Governance/economics/security.
- **OQ2-014 — Treasury asset/accounting policy.** Ratify Alpha/TAO handling, staking/conversion if any, period-inflow accounting, retained unused opportunity, and spending limits. **Owner:** Economics + protocol.
- **OQ2-015 — Treasury-neuron chain qualification.** Prove on localnet/testnet that the registered treasury neuron receives intended miner-side emission without unintended `MinerBurned` or other economic distortion, and that payouts work through intended precompiles. **Owner:** Protocol + infra.
- **OQ2-016 — Payout destination identity.** Decide binding between miner hotkey, coldkey/EVM recipient, strategy identity, and change/recovery procedures. **Owner:** Protocol + security.

## Scientific evidence / validator operation

- **OQ2-017 — Backend reproducibility cohort.** Ratify first supported JAX hardware/software profile and R1/R2 tolerances. **Owner:** SciML + infra.
- **OQ2-018 — Validator disagreement and promotion dispute.** Final retry/quarantine/contest semantics for ordinary ScoreResults and frontier promotion. **Owner:** Protocol + ops.
- **OQ2-019 — Evaluation disclosure budget.** Complete adaptive red-team demonstrating miner-facing feedback does not become a practical official-exam reconstruction oracle. **Owner:** Security + agent engineering.
- **OQ2-020 — Randomness/beacon production policy.** Ratify future chain-event timing / external beacon / fallback semantics for official exams and promotion exams. **Owner:** Security + protocol.

## Product and commercial layer

- **OQ2-021 — First Product Qualification Pack.** Define only when an exact target SKU/job exists; no universal product thresholds. **Owner:** Product + physics + protocol.
- **OQ2-022 — Sponsored Challenge economics.** Define sponsor-funded discovery/qualification payments without contaminating base scientific ranking or equal performance-portfolio semantics. **Owner:** Commercial + economics + protocol.
- **OQ2-023 — Information-value bounty treasury.** Decide whether/when replication, ablation, uncertainty-reduction or targeted experiments receive separate bounties and how those bounties remain distinct from frontier performance reward. **Owner:** Science governance + economics.

## Launch decision

- **OQ2-024 — vNext authority ratification.** Tech/science/economic lead accepts/modifies/rejects the integrated architecture and authorizes migration into runtime specs. **Owner:** Team leads.
- **OQ2-025 — First payout-enabled LIVE flip.** Requires qualified Challenge, validated promotion policy, treasury localnet/testnet evidence, security review, and Launch Bar v2. **Owner:** Protocol + physics + security + economics.
