# Carbon Full Documentation Reconciliation Audit — 2026-08-22

**Branch:** `design/symbolic-numeric-integration`  
**Purpose:** Identify stale or conflicting documentation after the qualified-Challenge, Score Pack, Burgers, frontier-economics, Bittensor-adapter, treasury, roadmap, and publication integration campaign.

## Executive conclusion

The repository contains the new integrated architecture, but several high-traffic/runtime documents still describe the previous score→weights economy and pre-qualified-exam model. The conflict is **documentation migration debt**, not a need for another system redesign.

The migration must preserve two truths at once:

1. **Current runtime authority stays explicit until implementation changes are reviewed.**
2. **Future design authority must be clear enough that engineers do not accidentally extend stale semantics.**

## A. Critical conflicts — reconcile before vNext implementation tickets

### A1. `SPEC.md`

**Keep:** current implementation architecture, interfaces, P0 constraints, dual-threshold product separation.  
**Repair:** durable identity; qualified-Challenge chain; `P/Q/w`; Score Pack as Evidence Use Contract; frontier promotion; equal Challenge portfolio; treasury settlement.  
**Remove from future doctrine:** “emissions follow score,” `winner-heavy decay`, Landscape dynamically aiming base emissions, universal Julia truth framing.  
**Migration target:** `SPEC_VNEXT_INTEGRATED.md`.

### A2. `Design_Specs/Scoring.md`

**Keep as current runtime mathematical authority until migration.**  
**Keep mathematically:** binary hard gates, deterministic execution, pack binding, P0 45/30/25 profile where the current pack requires it.  
**Repair in next version:** scoring ends at `ScoreResult`; remove `emissions: lean_score_decay`, historical winner decay, and language that makes ScoreEngine the economic allocator.  
**Add:** evidence eligibility, explicit estimands, `P/Q/w`, uncertainty/strata semantics, result states, Challenge-bound score identity.  
**Future architecture:** `Score_Pack_Architecture_v1.md` plus an intentionally versioned runtime migration.

### A3. `Design_Specs/Build_Out.md`

**Keep:** existing ticket history and sequencing evidence.  
**Repair:** Wave C/C15 and acceptance criteria currently end at scores→weights. Future flow must be ScoreResult → promotion → FrontierAdvanceEvent → treasury settlement.  
**Migration target:** `Build_Out_vNext_Integrated.md`.

### A4. `Design_Specs/Launch_Bar.md`

Current bar is too narrow for the now-defined scientific institution. A v2 bar should require:

- target-population and SamplingPlan qualification;
- generator conformance;
- truth/reference adequacy;
- measurement qualification;
- truth-dominance stop-ship;
- non-degenerate admissible strategy population;
- reconstruction/rank stability;
- common promotion-exam validation;
- treasury/localnet qualification before payout-enabled production use.

The old generic Burgers `residual ceiling` example must not remain authoritative for the repaired final-state Challenge.

### A5. `Design_Specs/Landscape_Agent.md`

Port C is stale. Replace “challenge weights / more emissions to unsaturated boards / decay tuning” with:

- Challenge activation/retirement proposals;
- separate information-value/reproduction bounty proposals;
- evidence for Challenge design/versioning;
- portfolio-health analytics.

**Forbidden:** Landscape dynamically changing the base equal `1/N` performance opportunity inside a frozen `ChallengeSetEpoch`.

### A6. `Design_Specs/Runtime_Julia_Truth_Oracle.md`

Reframe as **Julia Reference Backend / Service**. Julia/SciML can be an excellent reference implementation, adjoint provider, or corroborating witness, but truth authority is Challenge-specific. The Burgers case demonstrates why analytic Cole–Hopf can outrank a generic numerical service.

### A7. `Design_Specs/Operations.md`

Add operational separation for:

- evaluation jobs;
- frontier-promotion jobs;
- treasury governance / payout jobs;
- `PAYOUT_PENDING_INFRA`;
- Challenge freeze;
- treasury-neuron health;
- event/payout reconciliation.

Remove assumptions that every `lean_eval` directly creates emissions. Reference services should be Challenge-specific dependencies, not one universal “Ground Truth Oracle.”

## B. Important narrative/context conflicts

### B1. `README.md`

Current identity is strong, but it still says emissions follow the independent score and its roadmap/docs map predates frontier/treasury integration. Update now because it is the repository's highest-traffic narrative.

### B2. `docs/context/Architecture_Rationale.md`

Most rationale survives. Update in v2:

- envelope vs population;
- why SamplingPlan is separate;
- why exam qualification precedes grading;
- why Score Pack is Evidence Use Contract;
- why frontier reward replaces score-proportional/incumbent reward;
- why treasury separates Bittensor transport from scientific settlement;
- why truth backends are Challenge-specific.

### B3. `docs/context/Decisions.md`

D1–D50 remain useful provenance unless specifically superseded. D-036 (“Bittensor transforms canonical scientific scores into weights/emissions”) is no longer the terminal future architecture. Continue the integrated ledger in `Decisions_v2.md`.

### B4. `docs/context/Open_Questions.md`

Stale answers include variable-`nu` Burgers, residual-gate assumptions, and testnet scores→weights as the final economic path. Use `Open_Questions_v2.md` for current unresolved decisions.

### B5. old Canon and Roadmap

- Canon v3 remains the bibliographic annex, but Canon v4 controls the integrated scientific constitution.
- `System_Identity_and_Roadmap.md` is superseded for narrative architecture by `System_Identity_and_Roadmap_v2.md`.

## C. Challenge-specific documents

### `POC_Burgers_FNO.md`

Preserve as historical PoC. It should not be read as first-LIVE Challenge science because:

- it states `u0 -> u(T)` while the old generator varied hidden `nu`;
- it uses the final-time spatial balance proxy as a residual gate;
- it predates Cole–Hopf truth qualification and fixed-`nu` repair.

Current scientific target is `Burgers_Challenge_Qualification_v1.md`.

### `poc/*` configs and code

These are implementation reality / fixtures, not current scientific authority. Do not “correct” historical results by relabeling them. Future qualified Burgers work gets new Challenge/generator/measurement/Score Pack identities.

## D. Documents that are substantially current

- `Challenge_Instance_Distribution.md`
- `Generator_Validation.md`
- `Score_Pack_Architecture_v1.md`
- `Challenge_Portfolio_and_Frontier_Economics_v1.md`
- `Treasury_Settlement_Architecture_v1.md`
- `Emissions_Mapping_v3.md`
- `Burgers_Challenge_Qualification_v1.md`
- `System_Identity_and_Roadmap_v2.md`
- `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`
- `SPEC_VNEXT_INTEGRATED.md`
- `Build_Out_vNext_Integrated.md`
- product-qualification separation documents, subject to terminology cleanup from generic “winner” to “frontier-selected candidate” where useful.

## E. Historical designs that should remain, but must not be mistaken for authority

- distribution / Score Pack / integrated-incentive gauntlets;
- Burgers truth pilot;
- Bittensor adapter gauntlet;
- Frontier Leader Settlement gauntlet;
- old emissions v1/v2;
- `zDesign Archive/*`;
- `zBuild Appendices/*`.

They are valuable because they preserve why the current architecture exists. Status labeling is preferable to deletion.

## F. Cross-document terminology to standardize

Use consistently:

- **qualified Challenge**, not merely “procedural benchmark”;
- **target population `P`**, **SamplingPlan / `Q`**, **weighting `w`**;
- **reference / truth policy**, not universal “oracle”;
- **MeasurementContract** for score-eligible measurement identity;
- **Score Pack = Evidence Use Contract**;
- **admissibility precedes ranking**;
- **FrontierAdvanceEvent** for normal performance entitlement;
- **equal Challenge opportunity `1/N`** within frozen `ChallengeSetEpoch`;
- **treasury settlement** separate from scientific frontier decision;
- **rank nominates; evidence qualifies** for product path.

Avoid as terminal architecture:

- “score drives weights”;
- “current leader earns emissions”;
- “winner-heavy decay”;
- “Landscape aims emissions”;
- “Julia is the truth oracle”;
- “45/30/25 means physics > loss”;
- “procedural generator output is truth”;
- “highest raw score across Challenges wins”;
- “subnet winner is a product.”

## G. Migration order

1. Establish `DOCUMENTATION_STATUS.md` and this audit.
2. Update README and developer orientation to point at the authority index.
3. Tech/science/economic review of integrated vNext.
4. Migrate `SPEC.md`.
5. Migrate `Scoring.md` while preserving current schema compatibility until explicit version change.
6. Migrate Build Out / Launch Bar.
7. Migrate Data / Trustless Verification / Generator Creation.
8. Migrate Landscape / Operations / Julia reference service.
9. Issue new Burgers Challenge identities and implementation tickets; do not mutate old PoC evidence.
10. Run a final phrase/authority audit before merge to `main`.

## H. Merge-to-main rule

Do not wholesale merge the design branch merely because the documentation is internally coherent. Move reviewed domain-owned changes to `main` intentionally, preserving current implementation behavior until the matching code/schema migration is ready.
