# Carbon Build Out — Integrated vNext Sequencing

**Status:** OWNER-RECOMMENDED implementation sequence for tech lead review.  
**Purpose:** Turn the integrated architecture into bounded implementation waves without broadening execution freedom before the judge is proven.

---

# Wave 0 — Freeze authority and migration plan

- tech/science/economic review Canon v4 + integrated vNext spec;
- reconcile current `SPEC.md`, `Scoring.md`, Data/Generator/Validation/Operations docs;
- mark stale direct-score-emissions language;
- preserve current runtime until migration tickets are approved;
- define exact first authoritative Burgers Challenge identity.

Exit: no contradictory source-of-truth claims.

---

# Wave 1 — Qualify first Burgers judge

- fixed `nu=5e-3` task contract `u0 -> u(T)`;
- pin candidate I/O contract;
- implement/pin Cole-Hopf reference backend;
- qualify numerical corroboration only in supported regimes;
- rewrite stress suite to fixed-viscosity registered semantics;
- qualify final-state measurements (finite, mean/mass, energy, maximum principle, field error, stress error);
- demote old final-time spatial balance proxy to diagnostic-only unless separately qualified;
- build InstanceDistributionContract + SamplingPlan;
- complete Validation Dossier;
- compile Burgers Score Pack from qualified measurement uses.

Exit: Challenge can be marked CHALLENGE-QUALIFIED for stated P0 claim.

---

# Wave 2 — Prove non-degenerate miner science

Run strategy x reconstruction-seed x evaluation-seed matrix:

- gold / data-only / physics-informed / undertrained / deliberately adversarial strategies;
- multiple reconstruction seeds;
- multiple fresh evaluation/stress draws;
- rank reversal analysis;
- admissibility probability;
- score dispersion;
- truth-dominance stop-ship;
- validator evidence reproducibility.

Exit: at least two realistic admissible methods with scientifically meaningful, sufficiently stable separation; weak/adversarial methods fail as intended.

---

# Wave 3 — Implement frontier promotion

- FrontierBaseline registry;
- settlement windows;
- contender collection;
- common promotion exam;
- LeaderReplacementPolicy state machine;
- `FrontierAdvanceEvent` identity/digest;
- one-event-per-Challenge-window default settlement;
- Challenge defect freeze;
- version incompatibility handling.

Exit: synthetic/local event ledger proves no false leader from unrelated random draws.

---

# Wave 4 — Treasury localnet prototype

Use Enigma-style controller/vault as a reference pattern, not a dependency.

- deploy treasury neuron;
- deploy TreasuryController + TreasuryVault prototype;
- direct miner-side subnet emission to treasury neuron;
- implement event-bound payout proposal;
- active-validator governance;
- quorum/success/timelock/cancel/expiry;
- rate limits;
- duplicate-event payout prevention;
- Alpha transfer integration;
- operator/admin censorship observability;
- emergency freeze/recovery.

Test `N=7`, event counts `k=0,1,2,7`.

Exit: chain accounting matches logical Challenge accounting with no unintended redistribution/burn effect.

---

# Wave 5 — End-to-end one-Challenge settlement dry run

```text
submission
-> reconstruction
-> qualified exam
-> ScoreResult
-> common promotion exam
-> FrontierAdvanceEvent
-> treasury entitlement
-> validator governance
-> timelock
-> payout
```

Inject failures at every boundary.

Exit: science survives treasury/chain outages; no duplicate payout; no payout without valid event.

---

# Wave 6 — Phase-0 Challenge portfolio

Add 3-6 additional qualified academic Challenges, aiming for total 4-7 / original seven-PDE breadth where feasible.

For each:

- explicit CandidateOutputContract;
- target population + SamplingPlan;
- Challenge-specific truth hierarchy;
- MeasurementContracts;
- Validation Dossier;
- Score Pack;
- FrontierBaseline;
- LeaderReplacementPolicy.

Freeze active set per ChallengeSetEpoch.

Exit: equal notional opportunity without cross-Challenge score pooling; treasury accounting remains correct.

---

# Wave 7 — Network adversarial campaign

- sybil/duplicate submissions;
- staged disclosure behavior;
- simultaneous contenders;
- validator disagreement;
- malicious/slow treasury proposer;
- validator collusion thresholds;
- chain/RPC outage;
- Challenge freeze mid-period;
- Challenge add/retire at boundary;
- payout recipient change attacks;
- information leakage across repeated promotion exams.

Exit: Launch Bar updated with frontier/treasury stop-ship conditions.

---

# Wave 8 — Broaden physics, then model freedom

Only after Waves 1-7 are green:

- harder regimes / geometry / coupled physics;
- conditioned task inputs;
- multiple neural architectures;
- ROM/hybrid/classical candidates;
- registered ReconstructionProtocols;
- later sandboxed ConstructionPrograms.

Do not expand physics depth, model freedom, and commercial realism simultaneously without explicit experimental justification.

---

# Wave 9 — Partner Challenge and product path

In parallel with scientific build-out:

- partner interviews;
- workload/population definition;
- truth-source audit;
- pilot Challenge authoring;
- sponsored Challenge economics if appropriate;
- separate product qualification path.

Frontier reward remains search reward; product/commercial payment remains separate.

---

# Launch gates added by integrated architecture

Before production frontier payouts:

1. qualified first Challenge;
2. truth-dominance test green;
3. non-degenerate admissible miner population;
4. reconstruction/evaluation rank stability acceptable under registered policy;
5. independent validators reproduce authoritative evidence;
6. common promotion exam prevents false leader replacement;
7. treasury neuron receives intended emissions without unintended burn/redistribution effect;
8. event-bound settlement cannot double-pay or modify entitlement;
9. chain outage preserves scientific frontier state;
10. Challenge freeze stops payout;
11. active Challenge portfolio and equal opportunity are prospectively pinned;
12. public claims match actual maturity.
