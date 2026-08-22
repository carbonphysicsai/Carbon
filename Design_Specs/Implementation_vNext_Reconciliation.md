# Carbon Implementation vNext Reconciliation

**Status:** OWNER-RECOMMENDED implementation overlay; current `Implementation.md` remains historical/current implementation guidance until matching tickets are approved.  
**Purpose:** Prevent code work from extending stale score→weights, universal-truth, or old Burgers assumptions while vNext is reviewed.

## 1. Implementation boundary

Code should increasingly reflect this domain separation:

```text
Challenge authoring / registry
      ↓
case generation / reference realization
      ↓
independent reconstruction
      ↓
official measurement + ScoreResult
      ↓
frontier promotion
      ↓
FrontierAdvanceEvent
      ↓
treasury settlement
```

No one runtime module should silently own multiple scientific/economic authorities simply for convenience.

## 2. Challenge objects

Future implementation should preserve distinct identities for:

- PhysicalSystemSpec;
- CandidateOutputContract;
- InstanceDistributionContract;
- SamplingPlan;
- ChallengeInstanceGenerator;
- ReferencePolicy;
- MeasurementContracts;
- Validation Dossier;
- Score Pack;
- LeaderReplacementPolicy;
- ChallengeSetEpoch;
- FrontierBaseline / frontier state.

These may compile to compact runtime artifacts, but their semantic identities must remain auditable.

## 3. Reference backends

Replace assumptions of one hard-coded `GroundTruthOracle` with a registry/interface for Challenge-qualified reference backends. Julia/SciML is one adapter. Analytic, dataset, experimental, partner-service, or other solver adapters must be possible without changing the scientific control plane.

Reference responses carry status/provenance; backend failure is never automatically candidate scientific failure.

## 4. ScoreEngine

Keep ScoreEngine small and deterministic. Future engine code consumes authorized evidence and exact Score Pack. It does not:

- sample populations;
- generate reference truth;
- invent measurements;
- choose thresholds/weights;
- determine cross-Challenge economics;
- decide frontier entitlement;
- execute treasury transfer.

## 5. Promotion engine

Introduce a separate promotion component that:

- snapshots opening frontier/baseline;
- collects eligible contenders for the window;
- requests common fresh promotion evidence when required;
- enforces reconstruction-repeat policy;
- applies exact `LeaderReplacementPolicy`;
- returns `SUPERIOR`, `NOT_SUPERIOR`, `INDETERMINATE`;
- emits signed/content-addressed `FrontierAdvanceEvent` only for valid superior outcome.

## 6. Challenge portfolio accounting

Introduce a deterministic `ChallengeSetEpoch` artifact with exact active Challenge versions and `1/N` notional performance opportunity. Do not infer `N` dynamically mid-period from whatever registry entries happen to be reachable.

## 7. Treasury integration

Treasury adapter consumes finalized frontier events and period accounting, not raw ScoreResults.

Required guards:

- event ID replay protection;
- event digest verification;
- recipient binding;
- exact entitlement calculation;
- no amount mutation by proposer;
- governance/timelock state tracking;
- idempotent execution/reconciliation;
- payout failure separate from frontier state.

## 8. Historical P0 compatibility

Current `poc/` and existing A-stage runtime tests remain valuable. Do not mutate historical fixtures so they appear compliant with new science. Add new Challenge IDs/versions/configs for repaired Burgers and new settlement architecture.

## 9. Burgers implementation direction

New authoritative candidate should implement:

- fixed `nu=5e-3` Challenge identity unless Physics lead modifies it;
- `u0 -> u(T)` candidate contract;
- high-resolution periodic Cole–Hopf reference backend;
- qualified final-state measurements;
- new stress definition within registered IC family;
- no mandatory use of old final-time spatial-balance proxy as a full residual;
- reconstruction-repeat experiment harness;
- promotion-exam harness.

## 10. CI invariants

Add tests that fail if:

- a causal Challenge variable changes the target but is absent from candidate input/fixed semantics;
- generator distribution drifts from registered contract;
- reference failure maps to candidate physics failure;
- diagnostic measurement becomes score-bearing without a binding;
- inadmissible evidence reaches promotion;
- historical score and challenger score from unrelated draws are compared when the policy requires common promotion;
- inactive Challenge opportunity is reallocated to another Challenge winner;
- a frontier event can be paid twice;
- payout failure mutates scientific result;
- Landscape changes the current epoch's base `1/N` opportunity.

## 11. Final rule

> **Implementation should make the authority boundaries hard to violate accidentally: challenge science, score use, frontier selection, and treasury settlement are separate typed stages.**
