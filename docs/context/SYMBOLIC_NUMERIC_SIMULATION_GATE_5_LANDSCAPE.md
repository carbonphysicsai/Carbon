# Symbolic-Numeric Design Simulation — Gate 5: Landscape Physical-Context Integration

**Status:** design-forward simulation; no Landscape implementation or epistemic promotion.  
**Objective:** Test whether structured physical semantics can improve Carbon's scientific learning without turning similarity, metadata, or model output into causal authority.

## Existing Carbon doctrine preserved

Carbon already defines the intervention-outcome record as the scientific object, requires failure retention, separates performance from information value, and gives Landscape explicit epistemic states (`observed`, `predictive`, `causal_candidate`, `experimentally_supported`). The current intervention-outcome graph includes strategy intervention, physical regime, execution environment, hidden outcome, reproducibility, qualification, and optional lifecycle evidence.

Gate 5 asks what symbolic-numeric structure adds to that graph and what new failure modes it creates.

## Proposed evidence row

A future Landscape observation should be conceptually closer to:

```text
ExperimentObservation {
  experiment_id
  intervention_ref
  challenge_version
  physical_system_spec_ref
  physical_context_features_ref?
  measurement_contract_refs[]
  measurement_results[]
  execution_provenance
  reproducibility_evidence
  outcome/status
  evidence_quality
  selection_provenance
  disclosure_policy_ref
}
```

Only completed, execution-valid evidence enters the observation corpus. `EvidenceRequirement`, compiler proposals, unresolved decisions, and generated dossier templates are not observations.

## Core hypothesis

### H16 — Structured physical context improves prospective transfer prediction

Compare:

```text
baseline:
P(Y_future | intervention, Challenge ID, ordinary metadata)

vs

physical-context model:
P(Y_future | intervention, structured physical context, measurement identity, ordinary metadata)
```

The test must be prospective/held-out across Challenge versions or systems. Retrospective clustering is insufficient.

Success means better calibrated prediction or better downstream experiment/search decisions, not prettier explanations.

## Physical context representation

Do not initially feed raw equation ASTs into an opaque learner and call the embedding physics intelligence.

Start with qualified, provenance-bearing features such as:

- physical-system semantic identity;
- system class;
- spatial dimension;
- state/field structure;
- boundary/initial-condition classes;
- known process tags only where scientifically authored;
- qualified regime features / dimensionless groups only with scale provenance;
- measurement identity and evidence role;
- model output/observability contract.

Raw symbolic representations may later be studied as an additional representation if they improve prospective performance.

## Simulated transfer examples

### A. Burgers intervention transfers to another advection-diffusion Challenge
Suppose a curriculum oversampling sharp-gradient states improves robustness on Burgers.

A physical-context model might predict transfer to another nonlinear transport system with similar regime structure.

**Correct epistemic status:** predictive if it improves held-out prediction. It is not causal merely because the physical story sounds plausible.

### B. Same physics family, different MeasurementContract
Two Challenge versions both report `residual`, but one uses a final-state proxy and another a full spacetime residual.

If Landscape treats the metric name as identical, it may infer a false outcome shift.

**Discovery:** measurement identity is required for longitudinal comparability. Metric labels are not stable scientific variables.

### C. Symbolically similar, numerically different regimes
Two PDEs have similar relation structure but one operates in a smooth regime and the other develops shocks/fronts.

**Discovery:** equation structure alone is insufficient transfer context. Regime/evidence metadata must be learned/qualified separately.

### D. Different equations, similar effective regime
Two systems from different families may share a dimensionless/dominant-process regime relevant to a training intervention.

**Discovery:** physical similarity should be empirical and multi-view, not a fixed ontology tree. Carbon should test whether authored regime features improve transfer rather than declaring a universal taxonomy.

## Adversarial simulations

### E. Selection bias from performance market
Miners adaptively choose strategies they believe will score well. Observed strategy/outcome relationships are therefore confounded by search policy, budget, prior feedback, and participant skill.

**Decision:** every observation should preserve **selection provenance** where possible: ordinary performance search, reproduction experiment, Port C targeted experiment, sponsored intervention, etc. Landscape must not interpret observational frequency as intervention effect.

### F. Survivorship / missing failures
Only successful training runs are persisted.

Existing Carbon doctrine already rejects this. Gate 5 strengthens the requirement: failure and censoring state must be explicit because missingness can be intervention-dependent.

**Discovery:** distinguish scientific negative outcome from censored/no-result/infrastructure failure. Censoring itself may be informative but is not equivalent to poor model performance.

### G. Measurement version change
A measurement implementation changes and scores shift.

**Decision:** historical results remain bound to exact MeasurementContract. Cross-version normalization, if attempted, is a separate analysis with uncertainty/provenance, never silent rewriting.

### H. Challenge refresh / evaluation exhaustion
A new Challenge version changes protected exam construction.

**Decision:** Challenge version and evaluation-information policy are covariates/provenance. Landscape may model version effects but cannot merge versions as identical experimental environments by default.

### I. Physical feature leakage
Landscape-derived miner-facing advice says a particular regime feature predicts official stress failure and thereby leaks protected exam information.

**Decision:** structured physical intelligence does not bypass the Evaluation Information Budget. Public/Port-A outputs require disclosure analysis just like score diagnostics.

### J. Ontology-induced confirmation bias
Carbon authors label systems with expected dominant processes; Landscape then 'discovers' relationships driven by those labels.

**Decision:** preserve feature provenance (`authored`, `derived`, `learned`) and compare against baselines. A human-authored ontology is a hypothesis-bearing representation, not ground truth.

### K. Post-treatment leakage
A physical-context feature is derived from candidate outcomes after evaluation and then used as though it were pre-experiment context.

**Discovery:** Landscape features need temporal/causal role typing: pre-intervention context, intervention descriptor, post-intervention measurement, downstream qualification outcome. Otherwise prediction can accidentally leak outcomes into inputs.

### L. Multiple measurements of one latent property
Several qualified measurements target related physical behavior.

**Decision:** do not collapse them automatically. Landscape may learn relationships among measurements, but exact measurement identity and evidence role remain available.

## Earned object: ContextFeatureSet

Gate 5 suggests a versioned derived feature object rather than bloating PhysicalSystemSpec:

```text
ContextFeatureSet {
  feature_set_id
  version
  physical_system_spec_ref
  feature_time_role
  features[] {
    feature_id
    value
    semantic_type
    provenance_type: authored | derived | learned
    derivation_ref?
    applicability
    uncertainty?
  }
}
```

This keeps `PhysicalSystemSpec` descriptive/minimal while allowing Landscape experiments with richer representations.

A ContextFeatureSet is not a scientific certificate and cannot alter Challenge scoring.

## Earned provenance: selection + censoring

Landscape's intervention-outcome graph should preserve, where available:

```text
selection_provenance:
  performance_market | port_c_registered_experiment | reproduction | sponsored | other

result_state:
  completed_valid | scientific_failure | training_failure | censored | infrastructure_failure
```

Exact enums remain design candidates, but the distinction is now important for causal/predictive interpretation.

## Prospective decision-lift requirement

Physics intelligence should be earned through downstream decisions.

Possible tests:

1. transfer prediction calibration on held-out Challenges;
2. rank candidate interventions before a new Challenge is run;
3. choose between reproduction/transfer experiments under a fixed budget;
4. predict Product Battery failure modes prospectively;
5. reduce regret or cost-to-qualified-model versus a baseline experiment policy.

A model that only reconstructs historical clusters or produces plausible narratives has not demonstrated physics intelligence.

## New architecture discoveries

### D-036 — Physical context must be prospective-role typed
**Class:** EXTEND/HARDEN.

Distinguish pre-intervention context, intervention descriptors, post-intervention measurements, and downstream outcomes to prevent post-treatment leakage.

### D-037 — Selection provenance is required for serious causal interpretation
**Class:** EXTEND/HARDEN.

Performance-market observations, Port C experiments, reproductions, and sponsored studies are generated by different selection mechanisms. Preserve that distinction.

### D-038 — Censoring/missingness is a first-class evidence state
**Class:** EXTEND/HARDEN.

Scientific failure, training failure, no-result/censored, and infrastructure failure cannot be collapsed.

### D-039 — Measurement identity is part of the experimental variable space
**Class:** HARDEN.

Landscape must not compare generic metric labels across versions as though measurement semantics were unchanged.

### D-040 — Physical similarity must be empirically useful, not ontologically declared
**Class:** HARDEN.

Equation family/tags may help, but Carbon should test whether a representation improves prospective transfer. No universal similarity metric is ratified.

### D-041 — Introduce ContextFeatureSet as a derived, versioned Landscape representation
**Class:** EXTEND.

Keep PhysicalSystemSpec minimal; derive richer physical/regime features separately with provenance and uncertainty.

### D-042 — Feature provenance type matters
**Class:** EXTEND/HARDEN.

Authored, derived, and learned physical features have different epistemic status and failure modes.

### D-043 — Physics intelligence should be defined by prospective decision lift
**Class:** KEEP/HARDEN.

A Landscape model earns the term only if it improves future search, experiment allocation, qualification prediction, or decision economics relative to baselines.

### D-044 — Structured intelligence is itself subject to evaluation-information governance
**Class:** HARDEN.

Miner/public advice derived from official evidence can leak protected evaluation information even when the underlying PhysicalSystemSpec is public.

## Scientific implication

The intervention-outcome graph should evolve conceptually from:

```text
strategy × Challenge × outcome
```

toward:

```text
intervention
× pre-intervention physical context
× selection mechanism
× exact measurement semantics
× execution environment
→ outcome / censoring state
→ reproducibility
→ qualification
```

This is substantially richer, but each added dimension exists to prevent a concrete inference error rather than to create ontology complexity for its own sake.

## Commercial/economic implication

If H16 succeeds, Carbon's compounding asset becomes more defensible: not merely a history of leaderboard outcomes, but evidence about which model-construction interventions transfer across identifiable physical contexts.

If H16 fails, Carbon should still retain the semantic/provenance benefits of PhysicalSystemSpec, MeasurementContract, and Challenge authoring; it should **not** market physical-context Landscape as a moat merely because the representation exists.

## Gate verdict

**PASS AS A TESTABLE INTELLIGENCE ARCHITECTURE, NOT AS A CLAIM OF ACHIEVED INTELLIGENCE.**

The structured-physics integration strengthens Landscape only if prospective decision lift is demonstrated. Carry `ContextFeatureSet`, selection provenance, censoring state, temporal feature roles, and exact measurement identity into Gate 6 hybrid model-construction search.
