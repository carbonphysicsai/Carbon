# Symbolic-Numeric Design Discovery Ledger

**Branch:** `design/symbolic-numeric-integration`  
**Status:** active design-forward simulation ledger; non-runtime and non-scoring.  
**Purpose:** Capture architecture discoveries surfaced by implementation pressure before updating Carbon's canon, papers, or Summit deck.

## Classification

- **KEEP** — confirms current design.
- **HARDEN** — current concept is right but needs another invariant/boundary.
- **EXTEND** — a new capability has been earned by a concrete design need.
- **REVISE** — an existing design is materially suboptimal.
- **DEFER** — plausible but not yet justified.
- **REJECT** — tempting idea that would weaken Carbon.

## Ledger

| ID | Discovery | Source gate | Class | Design consequence | Canon/paper/pitch consequence | Confidence |
|---|---|---|---|---|---|---|
| D-001 | Executable Challenge semantics can drift from explanatory scientific metadata. | Burgers reconciliation | HARDEN | PhysicalSystemSpec preserves conflicts and follows versioned executable semantics until science owner changes them. | Supports provenance/traceability case; not stage-pitch material. | High |
| D-002 | A governing physical relation is not itself a score-bearing metric. | Burgers traceability | KEEP | Relation IR remains descriptive; diagnostics require separate numerical definition, dossier evidence, calibration, and Score Pack registration. | Strengthens 'symbolic model does not certify physics' doctrine. | Very high |
| D-003 | The current Burgers `residual_diagnostic` omits `d_t(u)` and is therefore a final-state spatial-balance proxy, not a full PDE residual. | Burgers traceability | REVISE | Preserve metric utility if desired, but classify/name it accurately; future full residual is a distinct qualified primitive. | Scientific-credibility improvement; no need to teach on stage. | Very high |
| D-004 | A physics-family label such as 'Poisson' is insufficient physical identity: repository sources can encode materially different model variants. | Poisson generality | HARDEN | PhysicalSystemSpec identity binds explicit relations/fields/conditions, not family label alone. | Strengthens structured-physical-context argument in whitepaper. | Very high |
| D-005 | Field-valued scientific quantities are a genuine core semantic class distinct from scalar parameters. | Poisson generality | EXTEND | Add `field(name, role)` to v0.1 relation IR and field declarations to PhysicalSystemSpec. | Minor canon/whitepaper detail; not pitch material. | High |
| D-006 | Manufactured/reference cases must be separated from the general physical-system definition. | Poisson generality | HARDEN | Reference cases live in provenance/numerical realization, not governing model identity. | Supports evidence hierarchy. | Very high |
| D-007 | Pre-designing all future physics variables would overfit imagined systems; no extension path would create repeated schema migrations. | v0.1 minimization | HARDEN | Small demonstrated core plus namespaced, non-authoritative extensions. Promotion requires repeated real use. | Supports disciplined extensibility; not pitch material. | High |
| D-008 | Structural machine validation is useful only if explicitly denied scientific authority. | Validator design | KEEP | Validator checks references/shape/forbidden content, never scientific correctness or numerical adequacy. | Reinforces no-layer-certifies-itself doctrine. | Very high |
| D-009 | Semantic authoring readiness is not binary. | Validator simulation | EXTEND/HARDEN | Distinguish structurally invalid, structurally valid-with-gaps, reviewable, and externally scientifically qualified states. Validator owns only structural boundary. | Useful whitepaper epistemic/maturity detail; probably not litepaper/pitch. | High |
| D-010 | Coupled systems will likely require scoped symbol namespaces. | Validator simulation | DEFER | Keep global uniqueness in v0.1; revisit during multiphysics crash test. | None yet. | Medium-high |
| D-011 | Units/dimensional analysis are promising authoring/evaluation primitives but current Carbon sources do not justify core unit semantics. | Validator simulation | DEFER | Keep as extension/research candidate until a real Challenge requires it. | Possible future scientific-method contribution; not yet integrate. | High |
| D-012 | Structural validity cannot establish mathematical well-posedness. | Validator simulation | HARDEN | Any future model linter is advisory; scientific qualification remains external. | Strengthens bounded-automation doctrine. | Very high |
| D-013 | Opaque extensions still need global secrecy invariants. | Validator simulation | HARDEN | Scan full artifact for forbidden protected-material classes; do not treat extension validation as public-safety proof. | Internal architecture only. | Very high |
| D-014 | Authored physical semantics, transformed symbolic semantics, and numerical-realization semantics are distinct evidence layers. | MTK adapter simulation | EXTEND/HARDEN | Preserve source/pre-transformation physical model separately from simplification/discretization provenance. | Strong whitepaper/canon addition: scientific identity must survive computational transformation. | Very high |
| D-015 | Scoped symbol identity is required for compositional scientific models. | MTK adapter simulation | EXTEND (future v0.2) | Add stable subsystem scopes/namespaces when composition is introduced; do not retrofit v0.1. | Supports long-term multiphysics story; not Summit-stage detail. | High |
| D-016 | Shared/aliased quantities across component scopes require explicit identity semantics, not string flattening. | MTK adapter simulation | DEFER/EXTEND | Define minimum alias/shared-identity contract during coupled-system gate. | None yet. | High |
| D-017 | Framework defaults are not Carbon scientific envelopes. | MTK adapter simulation | HARDEN | Defaults may be provenance only; never infer ranges, priors, stress domains, or qualification from them. | Reinforces evidence-bounded design. | Very high |
| D-018 | Adapter conversion quality must be explicit and measurable. | MTK adapter simulation | EXTEND | Every conversion returns an AdapterReport with mapped/unsupported/dropped/transformed constructs. | Potential partner-value story: auditable model onboarding. | Very high |
| D-019 | Representation level is first-class provenance. | MTK adapter simulation | EXTEND/HARDEN | Tag whether evidence describes authored physical model, transformed symbolic model, discretized system, or numerical realization. | Important canon/whitepaper concept. | Very high |
| D-020 | Observed variables can preserve engineering meaning even when numerical transformations eliminate them as states. | MTK adapter simulation | KEEP/HARDEN | Retain observed-variable class and lineage through transformations. | Supports qualification/engineering interpretation. | High |
| D-021 | A physically meaningful diagnostic may be unobservable from the candidate model's output contract. | Evaluation primitive simulation | EXTEND/HARDEN | Bind each candidate measurement to required observables; do not infer full residuals from insufficient outputs. | Strong scientific-design insight for whitepaper/canon. | Very high |
| D-022 | Measurement identity includes numerical method, not just symbolic relation. | Evaluation primitive simulation | EXTEND | Define discretization/sampling, normalization, aggregation, precision and implementation version. | Important scientific credibility addition. | Very high |
| D-023 | Carbon needs a MeasurementContract concept between physical semantics and score authority. | Evaluation primitive simulation | EXTEND | Trace relation/condition -> MeasurementContract -> dossier calibration -> Score Pack. | Major canon/whitepaper architecture contribution. | High |
| D-024 | Evidence role must be typed. | Evaluation primitive simulation | HARDEN/EXTEND | Distinguish generator validation, candidate evaluation, product qualification and Landscape descriptive measurements. | Strengthens evidence architecture. | Very high |
| D-025 | Measurement applicability binds to assumptions + exact physical-system version. | Evaluation primitive simulation | HARDEN | No generic family-level conservation/residual metric without BC/source/regime assumptions. | Whitepaper/canon detail. | Very high |
| D-026 | Machine-readable/generated diagnostics create a new Goodhart surface. | Evaluation primitive simulation | HARDEN | Preserve protected exams, stress diversity and independent evaluation; generated primitives never become the whole objective by default. | Strong reason Carbon's evaluation-information doctrine remains necessary. | Very high |
| D-027 | Dimensionless features require characteristic-scale provenance. | Evaluation primitive simulation | DEFER/HARDEN | Do not auto-generate regime groups from names/units alone; qualify characteristic scales. | Future Landscape/canon research note. | High |
| D-028 | Measurement definition, qualification, and score use are separate authorities. | Challenge Compiler simulation | EXTEND/HARDEN | Prefer standalone versioned MeasurementContract referenced by dossier and Score Pack. | Major architecture clarification for canon/whitepaper. | Very high |
| D-029 | Challenge Compiler output is an authoring package, not a Challenge/certificate. | Challenge Compiler simulation | HARDEN | Generated plans cannot bypass scientific review, dossier evidence, registry, or scoring authority. | Important positioning guardrail if Challenge Compiler becomes commercial story. | Very high |
| D-030 | Blocking scientific decisions differ from missing evidence. | Challenge Compiler simulation | EXTEND | Authoring workflow distinguishes unresolved definition choices from evidence work supporting a defined model. | Strong scientific workflow concept; whitepaper candidate. | High |
| D-031 | EvidenceRequirement is a useful typed pre-evidence object. | Challenge Compiler simulation | EXTEND | Track required experiment/analysis separately from completed evidence; explicit lifecycle states. | Could strengthen evidence-system thesis and partner workflow. | High |
| D-032 | Measurement qualification binds exact numerical implementation identity. | Challenge Compiler simulation | HARDEN | Material measurement implementation changes trigger recalibration/requalification. | Scientific credibility detail. | Very high |
| D-033 | Thresholds are not portable by metric name alone. | Challenge Compiler simulation | HARDEN | Bind threshold basis to physical-system version + MeasurementContract + qualified envelope/dossier evidence. | Reinforces physics > arbitrary score framing. | Very high |
| D-034 | Controlled partner semantics create a transparency compatibility test. | Challenge Compiler simulation | HARDEN/DEFER | Some proprietary problems may require distinct Challenge modes; open competition still needs enough auditable semantics. | Commercial/partner positioning issue worth preserving for final review. | High |
| D-035 | Generated scientific documentation needs machine-visible evidence states. | Challenge Compiler simulation | HARDEN | Mark planned/unrun/satisfied/failed/waived explicitly so scaffolding cannot masquerade as evidence. | Strengthens transparent-evidence framing. | Very high |
| D-036 | Physical-context features need temporal/causal role typing. | Landscape simulation | EXTEND/HARDEN | Distinguish pre-intervention context, intervention descriptors, post-intervention measurements, and downstream outcomes to prevent leakage. | Strong whitepaper/canon methodological addition. | Very high |
| D-037 | Selection provenance is required for serious causal interpretation. | Landscape simulation | EXTEND/HARDEN | Preserve whether observations came from performance search, Port C experiment, reproduction, sponsored study, etc. | Major strengthening of Landscape causal discipline. | Very high |
| D-038 | Censoring/missingness is a first-class evidence state. | Landscape simulation | EXTEND/HARDEN | Distinguish scientific failure, training failure, censored/no-result, and infrastructure failure. | Important evidence-system addition. | Very high |
| D-039 | Exact MeasurementContract identity belongs in Landscape's experimental variable space. | Landscape simulation | HARDEN | Never compare generic metric labels across versions as unchanged measurements. | Strengthens longitudinal evidence integrity. | Very high |
| D-040 | Physical similarity must earn value prospectively rather than be declared by ontology. | Landscape simulation | HARDEN | Test equation/regime/feature representations against held-out transfer and decision baselines. | Central scientific case for structured physical intelligence. | Very high |
| D-041 | Rich physical/regime features should live in a derived ContextFeatureSet, not bloat PhysicalSystemSpec. | Landscape simulation | EXTEND | Add versioned derived feature object with physical-system reference, provenance, applicability and uncertainty. | Important architecture/canon addition. | High |
| D-042 | Authored, derived and learned physical features have different epistemic status. | Landscape simulation | EXTEND/HARDEN | Preserve feature provenance type and avoid treating authored ontology labels as truth. | Strengthens epistemic hierarchy. | Very high |
| D-043 | Physics intelligence is earned through prospective decision lift. | Landscape simulation | KEEP/HARDEN | Require improved future search, experiment allocation, qualification prediction, or decision economics relative to baselines. | Core whitepaper/canon thesis; potentially useful simple investor language later. | Very high |
| D-044 | Structured intelligence is itself governed evaluation information. | Landscape simulation | HARDEN | Miner/public Landscape outputs remain subject to disclosure policy/Evaluation Information Budget. | Strengthens existing adaptive-evaluation argument. | Very high |

## Gate template

For each remaining simulated implementation gate, record:

1. intended component;
2. happy-path simulation;
3. adversarial/failure simulations;
4. newly required semantics;
5. authority-boundary pressure;
6. implementation/economic consequences;
7. discoveries using the classification above;
8. impact on canon, whitepaper, litepaper, Summit deck;
9. whether the discovery is mature enough to integrate now.

## Remaining simulated gates

1. ~~Structural validator execution/hardening.~~ **PASS**
2. ~~ModelingToolkit adapter.~~ **PASS WITH ARCHITECTURE EXTENSIONS**
3. ~~Physics Evaluation Primitive Library.~~ **PASS — MEASUREMENT CONTRACT DISCOVERED**
4. ~~Challenge Compiler / dossier authoring integration.~~ **PASS — MEASUREMENT IDENTITY + EVIDENCE REQUIREMENT**
5. ~~Landscape physical-context integration.~~ **PASS AS TESTABLE INTELLIGENCE ARCHITECTURE**
6. Hybrid model-construction search.
7. Coupled/multiphysics crash test.
8. Carbon-without-neural-networks test.
9. Final system-level design review.

**Publication rule:** do not edit the canon/papers/deck from individual speculative findings. Complete the discovery simulation first, then integrate the stable findings in one reconciled pass.
