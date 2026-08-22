# Runtime Documentation Migration Plan — Integrated vNext

**Status:** OWNER-RECOMMENDED migration plan; no runtime semantic change occurs merely because this plan exists.

## Goal

Move the accepted integrated architecture into domain-owned runtime documents without mixing scientific, economic, product, and implementation authority.

## 1. `SPEC.md`

After ratification:

- change system description from terminal neural-operator verification to durable fast-physical-model institution while clearly retaining narrow P0 implementation;
- insert qualified-Challenge chain and exam-qualification prerequisite;
- insert target population / SamplingPlan / truth / MeasurementContract authority boundaries;
- replace direct “score → emissions/weights” terminal flow with `ScoreResult → LeaderReplacementPolicy → FrontierAdvanceEvent → treasury settlement`;
- add frozen `ChallengeSetEpoch` and equal notional `1/N` performance opportunity;
- remove winner-heavy decay as base future doctrine;
- constrain Landscape Port C to proposals/portfolio governance and separate bounties;
- replace universal Julia oracle language with Challenge-specific ReferencePolicy;
- preserve product-qualification separation.

## 2. `Design_Specs/Scoring.md`

Do not change current score outputs until a new scoring schema/version is intentionally introduced. In the next version:

- scoring domain ends at `ScoreResult`;
- remove `emissions: lean_score_decay` and direct Yuma mapping from Score Pack schema;
- define evidence eligibility and explicit scientific result states;
- make admissibility-before-ranking first-class;
- bind explicit estimands and `P/Q/w`;
- support stratum and uncertainty policy;
- retain current P0 weighted-geometric / 45-30-25 profile as a compatibility profile where desired;
- ensure exact current schema remains executable until migrated.

## 3. `Design_Specs/Build_Out.md`

Next revision should absorb `Build_Out_vNext_Integrated.md`:

- qualified Burgers;
- strategy × reconstruction × eval-seed campaign;
- frontier-promotion engine;
- treasury localnet;
- one-Challenge end-to-end settlement;
- 4–7 Challenge portfolio;
- adversarial/economic validation.

Retire direct “scores→weights visible = P0 done” as the terminal acceptance criterion.

## 4. `Data_Management.md` / `Trustless_Verification.md` / `Generator_Creation.md`

Add explicit ownership boundaries:

- `InstanceDistributionContract` owns target population;
- `SamplingPlan` owns finite draw design;
- generator implements, does not invent, those objects;
- train/eval/stress roles remain but are not universal semantic categories for all future construction families;
- reference/truth policy is separate from generator;
- intended vs realized evidence population and censoring are recorded;
- semantic decontamination may require more than seed separation.

## 5. `Launch_Bar.md`

Create v2 with two levels:

- **Scientific Challenge LIVE bar:** population, sampling, generator, truth, measurements, dossier, Score Pack, backend/reproducibility, disclosure.
- **Payout-enabled bar:** non-degenerate admissible strategy population, truth-dominance, rank stability, LeaderReplacementPolicy, treasury/localnet evidence, settlement security.

Landscape publish remains downstream of an honest scientific bar.

## 6. `Landscape_Agent.md`

Port C migration:

- remove base performance Challenge weighting/decay tuning;
- allow evidence-based proposals for Challenge creation, retirement, requalification, stress/version changes, and separate research bounties;
- preserve “Landscape proposes; registered contracts decide.”

## 7. `Runtime_Julia_Truth_Oracle.md`

Rename/reframe to `Julia_Reference_Backend.md` or equivalent:

- service can provide qualified reference solves/adjoints/symbolic helpers;
- no generic endpoint may assert `passes` based on a hard-coded universal tolerance;
- ReferencePolicy/MeasurementContract own applicability and thresholds;
- service failure returns reference/infra states, not candidate scientific failure.

## 8. `Operations.md`

Add job classes / health state for:

- official evaluation;
- promotion exam;
- treasury governance/settlement;
- product qualification.

Add treasury-neuron/vault/controller monitoring, event-to-payout reconciliation, governance/timelock incidents, and payout-pending infra states.

## 9. `README.md` / `AGENTS.md`

README should describe integrated architecture and link `DOCUMENTATION_STATUS.md`.

AGENTS should keep current-runtime implementation discipline but require agents to consult `DOCUMENTATION_STATUS.md` before interpreting overlapping docs.

## 10. `docs/context`

- Canon v4 = current integrated canon; v3 = bibliographic annex.
- `Decisions_v2.md` continues the decision ledger.
- `Open_Questions_v2.md` replaces stale unresolved questions.
- `Architecture_Rationale.md` should receive v2 once domain migrations are accepted.

## Compatibility principle

> **Do not change a scientific or economic meaning in-place when historical records depend on the old meaning. New meaning gets a new version/identity and applies prospectively.**
