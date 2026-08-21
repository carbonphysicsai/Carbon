# Symbolic-Numeric Design Simulation — Gate 4: Challenge Compiler / Validation Dossier Integration

**Status:** design-forward simulation; no runtime compiler, registry, scoring, or dossier changes.  
**Objective:** Simulate converting structured physical semantics into a reviewable Challenge-authoring package and decide where the Gate-3 `MeasurementContract` belongs.

## Existing Carbon authority used

Carbon already treats the Validation Dossier as the public evidence pack demonstrating generator/reference credibility and threshold calibration before a Challenge goes LIVE. Existing doctrine also states that numerical criteria are conditional on physics/evidence type rather than universal constants.

The compiler must therefore scaffold evidence work; it cannot bypass or replace the dossier.

## Simulated workflow

```text
partner/domain scientist
        ↓
PhysicalSystemSpec
        ↓
AdapterReport (if imported)
        ↓
Challenge Compiler
        ├─ candidate generator requirements
        ├─ candidate MeasurementContracts
        ├─ required observables
        ├─ candidate stress taxonomy
        ├─ missing-evidence matrix
        ├─ disclosure classification review
        └─ dossier skeleton
        ↓
HUMAN SCIENTIFIC REVIEW
        ↓
reference/generator implementation
        ↓
validation + calibration experiments
        ↓
Validation Dossier
        ↓
registered MeasurementContract bindings
        ↓
Score Pack
        ↓
Challenge Registry / LIVE gate
```

The compiler output is a **Challenge Authoring Package**, not a Challenge certificate.

## MeasurementContract placement decision

### Option A — embed only in Validation Dossier
Rejected as the sole identity mechanism.

Reason: the same measurement definition may be referenced by candidate evaluation, generator validation, product qualification, and historical evidence. If its complete identity exists only as prose inside a dossier, cross-artifact lineage becomes fragile.

### Option B — put complete measurement semantics in Score Pack
Rejected.

Reason: Score Pack should define how registered measurements affect scoring/gates. It should not own derivative estimation, mesh sampling, normalization, uncertainty-floor evidence, implementation provenance, or non-score-bearing measurements.

### Option C — standalone versioned MeasurementContract artifact, referenced by dossier and Score Pack
**Preliminary preferred design.**

```text
MeasurementContract artifact
  exact measurement semantics
        ↑                 ↑
Validation Dossier       Score Pack
qualifies/calibrates     selects role/threshold/weight/gate
```

The dossier provides evidence that the measurement is credible for its intended role and envelope. The Score Pack binds a qualified measurement identity and defines its score-bearing use. A3 can later content-bind the measurement artifact through the existing generic artifact mechanism if/when it becomes a registered Challenge artifact.

**Discovery:** measurement definition, measurement qualification, and measurement use are three distinct authorities.

## Candidate Challenge Authoring Package

```text
ChallengeAuthoringPackage {
  physical_system_spec_ref
  adapter_report_ref?
  proposed_generator_contract
  proposed_reference_realization
  proposed_measurement_contracts[]
  required_candidate_outputs[]
  proposed_stress_categories[]
  missing_evidence[]
  disclosure_review[]
  dossier_skeleton
  unresolved_decisions[]
}
```

This object is explicitly pre-registration and cannot make a Challenge LIVE.

## Burgers simulation

Compiler reads the accepted Burgers relation and current final-state operator interface.

It proposes:

- finite-output check: observable now;
- mean-conservation candidate: observable from `u0,uT`, but needs a MeasurementContract and numerical-floor calibration;
- full PDE residual: **not observable** from final-state-only output because `u_t` is unavailable;
- current spatial-balance proxy: importable only if honestly classified as proxy;
- periodicity diagnostic: possible candidate, but no automatic hard gate;
- lower-viscosity / higher-amplitude stress categories: descriptive generator semantics, not automatic stress adequacy proof.

The compiler therefore produces a missing-evidence item rather than inventing a full residual.

**Finding:** a useful compiler must be allowed to say `NOT_MEASURABLE_WITH_CURRENT_OUTPUT_CONTRACT`.

## Poisson simulation

Compiler sees two noncanonical source variants and refuses to choose one automatically.

Expected output:

```text
BLOCKING_SCIENTIFIC_DECISION:
  choose canonical Poisson physical model before generator/dossier generation
```

After a scientist chooses a model, the compiler can propose:

- Dirichlet boundary measurement contract;
- PDE residual candidate with explicit strong/weak/discrete-method choice unresolved;
- manufactured-solution checks for generator/reference validation only;
- coefficient/source-field coverage requirements where applicable.

**Finding:** compiler must distinguish **blocking scientific decisions** from **missing evidence**. They are not the same thing.

## Adversarial simulations

### A. Compiler generates many plausible diagnostics
More diagnostics can create false confidence and larger Goodhart surfaces.

**Decision:** compiler ranks/proposes diagnostics by scientific purpose and observability, but cannot maximize count or automatically elevate all to score-bearing status.

### B. Dossier evidence qualifies one measurement version, implementation changes later
A numerically changed measurement implementation can alter values even if the symbolic property is unchanged.

**Decision:** qualification binds exact MeasurementContract version + implementation identity. Material changes require requalification/recalibration.

### C. Score Pack threshold copied across Challenges
Same measurement name exists under different physical systems/envelopes.

**Decision:** thresholds bind `(physical_system_spec, measurement_contract, envelope/dossier qualification)`, not generic metric names.

### D. Partner-private model with public subnet competition
The compiler cannot simply publish the PhysicalSystemSpec if it contains proprietary equations/parameters.

**Decision:** authoring package needs a disclosure plan that can separate public competition semantics from controlled scientific semantics. However, hidden semantics must not make the public score scientifically unauditable; such Challenge modes require explicit governance and may be unsuitable for open subnet use.

### E. Compiler generated dossier language becomes mistaken for evidence
A generated report skeleton says a convergence study is required; no study has run.

**Decision:** generated dossier sections must carry `PLANNED/UNRUN` state. Templates cannot render as completed evidence.

### F. Existing Validation Dossier examples contain universal-looking thresholds
Current appendix includes illustrative-looking numerical criteria while its reconciliation header says such criteria are conditional.

**Discovery:** future compiler/schema should force threshold basis/provenance so examples cannot accidentally become inherited defaults.

## Earned object: EvidenceRequirement

Gate 4 reveals another useful pre-evidence object:

```text
EvidenceRequirement {
  requirement_id
  subject_ref
  purpose
  required_experiment_or_analysis
  acceptance_basis_owner
  status: PLANNED | RUNNING | SATISFIED | FAILED | WAIVED_WITH_RATIONALE
  evidence_refs[]
}
```

This is not scientific evidence. It is the typed statement of what evidence is missing or required.

Why it matters:

- separates 'we know what must be tested' from 'we have tested it';
- prevents generated dossier scaffolding from masquerading as evidence;
- allows Challenge onboarding progress to be auditable;
- can later support partner project management and cost estimation.

## New architecture discoveries

### D-028 — Measurement definition, qualification, and score use are separate authorities
**Class:** EXTEND/HARDEN.

Preferred chain:

```text
MeasurementContract
  -> Validation Dossier qualification/calibration
  -> Score Pack role/threshold/weight
```

Do not duplicate full measurement semantics in Score Pack or bury identity only in dossier prose.

### D-029 — Challenge Compiler output is an authoring package, not a Challenge
**Class:** HARDEN.

The compiler proposes and tracks work; human scientific review + evidence + existing registry gates remain authoritative.

### D-030 — Blocking scientific decisions differ from missing evidence
**Class:** EXTEND.

`UNRESOLVED_MODEL_CHOICE` cannot be fixed by running more validation. The authoring system should distinguish decisions that define the scientific object from evidence needed to support an already-defined object.

### D-031 — EvidenceRequirement should be a typed pre-evidence object
**Class:** EXTEND.

This prevents plans/templates from being confused with results and creates an auditable onboarding workflow.

### D-032 — Qualification binds exact measurement implementation identity
**Class:** HARDEN.

Changing numerical measurement semantics can invalidate calibration even if the physical relation is unchanged.

### D-033 — Threshold portability is constrained by physical system + measurement + envelope
**Class:** HARDEN.

Never inherit thresholds by metric name alone.

### D-034 — Controlled partner semantics create a transparency compatibility test
**Class:** HARDEN/DEFER.

Private scientific models may be commercially important, but open competition requires enough public semantics to make evaluation legitimate. Carbon may need distinct Challenge modes rather than pretending every partner problem fits the same disclosure model.

### D-035 — Generated scientific documentation requires explicit evidence-state labeling
**Class:** HARDEN.

`PLANNED`/`UNRUN`/`SATISFIED` etc. should be machine-visible, not prose-only.

## Commercial/economic implication

The Challenge Compiler now looks more credible as a future partner product:

> **Bring Carbon a scientific model; receive an auditable plan for turning it into an incentivized model-discovery program.**

Its deliverables are not 'automatic verification'. They are:

- semantic import/coverage report;
- unresolved scientific-decision list;
- candidate evaluation plan;
- required model outputs;
- evidence requirements;
- dossier scaffolding;
- disclosure analysis;
- onboarding progress state.

This could reduce the cost and ambiguity of converting existing simulation/model assets into Carbon Challenges even before the subnet produces a winning model.

## Gate verdict

**PASS WITH TWO MAJOR DESIGN ADDITIONS: standalone MeasurementContract identity + typed EvidenceRequirement.**

Carry both into Gate 5. Landscape should learn only from completed evidence objects and exact measurement identities; it must not confuse planned requirements, generated hypotheses, or dossier templates with observations.
