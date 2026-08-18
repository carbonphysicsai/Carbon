# Carbon Open Questions
**Status:** v1 — team review

Only unresolved human-owned questions belong here. Resolved architecture belongs in `DECISIONS.md`.

## P0 science
- **OQ-001 — First LIVE challenge envelope.** Exact parameters, BC/IC classes, exclusions, and stress taxonomy. **Owner:** Physics/SciML lead.
- **OQ-002 — First LIVE generator dossier.** Exact reference evidence and coverage required to qualify that envelope. **Owner:** Physics/SciML lead.
- **OQ-003 — First LIVE Score Pack.** Exact hard gates, thresholds, within-leg weights, robustness categories, and approved deviations from the 45/30/25 P0 baseline. **Owner:** Physics + protocol.
- **OQ-004 — Backend reproducibility tolerance.** Acceptable numerical tolerance for repeated official training/evaluation on the qualified stack. **Owner:** SciML + infra.

## Randomness / protocol
- **OQ-005 — Phase-0 seed timing.** Exact chain event/block timing and nonce lifecycle that makes randomness unavailable when a miner commits while preserving reproducibility. **Owner:** Protocol/Bittensor.
- **OQ-006 — Production beacon qualification.** Select and security-review the production strengthening path and fallback policy. **Owner:** Security + protocol.
- **OQ-007 — Validator disagreement procedure.** Retry/contested-result behavior when outputs exceed qualified reproducibility tolerance. **Owner:** Protocol + ops.

## Security / execution
- **OQ-008 — P0 strategy execution threat model.** Confirm the permitted submission capability surface and isolation controls for hostile miner-controlled input. **Owner:** Security + protocol.
- **OQ-009 — Disclosure budget validation.** Demonstrate that EvaluationCard plus repeated querying does not create a practical exam-reconstruction oracle. **Owner:** Security + agent engineering.

## Economics / operations
- **OQ-010 — Exam fee.** Set P0 fee policy; fee remains forbidden from scientific score. **Owner:** Protocol/economics.
- **OQ-011 — Submission/rate limits.** Set P0 rate limits/resource classes from measured validator cost and queue behavior. **Owner:** Ops/economics.
- **OQ-012 — Validator operating envelope.** Supported hardware, resource limits, retry policy, and minimum reliability for testnet/LIVE qualification. **Owner:** Infra/protocol.

## Qualification / ownership
- **OQ-013 — Sign-off owners.** Name authorized approvers for envelope, dossier, Score Pack, backend, security review, MCP readiness, and Launch Bar. **Owner:** Team.
- **OQ-014 — First LIVE flip.** Select the exact challenge/version once all qualification evidence is complete. **Owner:** Protocol + physics lead.
- **OQ-015 — Product Qualification Pack v1.** Before the first commercial SKU, define product-specific PB thresholds, hardware profile, operating certificate, and requalification triggers. **Owner:** Product + physics + protocol.

Carbon Open Questions — Architect Recommendations

Status: v1 — proposed answers for team review
Purpose: Provide a concrete architect recommendation for every item in OPEN_QUESTIONS.md. These are proposals, not ratified scientific, security, economic, or production decisions.

Decision rule

Where the current specs already constrain the architecture, this file recommends the narrowest compatible choice. Where a numerical scientific threshold, security acceptance criterion, economic value, or production qualification requires evidence that does not yet exist, this file recommends how to decide it rather than inventing a number.

P0 science

OQ-001 — First LIVE challenge envelope

Recommendation: Make the first LIVE challenge 1D viscous Burgers with a deliberately narrow, analytically/numerically defensible envelope.

Use:

● periodic 1D spatial domain;

● fixed, versioned spatial and temporal discretization for the challenge;

● smooth bounded initial-condition families capable of developing steep gradients under the declared viscosity range;

● strictly positive viscosity bounded away from the inviscid limit;

● no forcing in the first LIVE version unless the generator dossier separately validates it;

● no multidimensional Burgers, discontinuous imposed ICs, moving boundaries, or out-of-envelope shock regimes in the first version.

The exact viscosity interval, IC amplitude/frequency bounds, rollout horizon, resolution, and stress-category frequencies should not be chosen from generic examples. They should be frozen only after the generator dossier demonstrates reference accuracy and coverage across the proposed envelope.

Stress taxonomy recommendation: low-viscosity edge, high-amplitude IC, high-frequency/steep-gradient IC, long-horizon rollout, and combinations of these that remain inside the declared envelope.

Why: Burgers gives Carbon nonlinear transport, dissipation, steep-gradient formation, rollout behavior, conservation/residual checks, and neural-operator relevance without making the first trust proof depend on turbulence, complex geometry, mesh generation, or model-form uncertainty.

Proposed disposition: Architecture answer accepted; numerical envelope remains a dossier output.

OQ-002 — First LIVE generator dossier

Recommendation: Use the strongest available reference path for Burgers and require evidence across the whole claimed envelope, not a ceremonial generic CFD checklist.

Minimum dossier:

1. analytic/manufactured checks where available;

2. an independently implemented high-resolution numerical reference with a documented convergence study;

3. generator-vs-reference agreement across stratified audit seeds spanning interior, edges, and declared stress categories;

4. conservation/residual and energy/dissipation behavior appropriate to viscous Burgers;

5. draw-distribution coverage evidence showing the generator actually reaches the declared envelope and stress categories;

6. degeneracy/entropy checks preventing collapsed or trivial sampling;

7. numerical uncertainty/residual floors used to calibrate Score Pack thresholds;

8. exact generator, solver, environment, and artifact hashes.

Do not require mesh/temporal tests merely because an old template says so; require the convergence/evidence tests that actually establish the Burgers claim.

LIVE rule: any unexplained systematic disagreement between credible references, or inadequate coverage near a claimed boundary, shrinks the envelope or blocks LIVE.

OQ-003 — First LIVE Score Pack

Recommendation: Keep the reconciled 45/30/25 weighted-geometric architecture, but derive all scientific thresholds from the Burgers dossier.

For P0 Burgers, I recommend the mandatory gate families be:

● finite / no NaN/Inf;

● challenge-appropriate PDE residual or equation consistency;

● boundary-condition satisfaction;

● conservation / physically appropriate integral-balance check;

● short rollout stability / no numerical blow-up.

Use shock/steep-gradient behavior primarily in robustness and accuracy unless the dossier supports a clearly defined mandatory physical admissibility gate.

Do not make UQ, adjoint consistency, turbulence, chemistry, or product-shaped inverse-design checks mandatory in the first lean pack.

Within the physics leg, normalize qualified gate margins and weight them inside the leg; do not reuse the global 0.45 factor inside the component.

Robustness should emphasize the weakest declared stress categories and tail behavior, not only mean error. Accuracy should combine ordinary held-out draws with difficult in-envelope edge/rare-regime draws.

Threshold rule: tau values come from reference uncertainty + engineering/scientific relevance demonstrated in the dossier. No generic number in the design docs becomes LIVE merely by being written there.

OQ-004 — Backend reproducibility tolerance

Recommendation: Do not define one universal epsilon. Qualify reproducibility at three layers:

1. Exact deterministic artifacts: seeds, draw metadata, pack hashes, strategy canonicalization, sample generation and non-floating control flow should match exactly.

2. Reference/scoring operators: deterministic numerical metrics should meet a tight backend-qualified tolerance established from repeated runs.

3. Training outcome: require score/gate reproducibility tight enough that repeated honest runs do not change gate status or materially change ranking.

Qualification procedure:

● run repeated identical evaluations on each supported hardware/software profile;

● estimate within-profile and cross-profile score distributions;

● set tolerances from measured numerical variation, with margin below the smallest scientifically meaningful score/gate separation;

● if a strategy sits inside the reproducibility uncertainty band of a hard threshold, treat the evaluation as contested/retry rather than letting hardware noise decide a physics failure.

Recommendation for P0: initially support a narrow hardware/backend profile rather than weakening reproducibility to accommodate heterogeneous accelerators.

Randomness / protocol

OQ-005 — Phase-0 seed timing

Recommendation: Bind each submission to a future chain event that is unknowable at commitment time.

Proposed lifecycle:

1. miner submits strategy;

2. submission becomes immutable at accepted block h;

3. protocol records a challenge-configured seed_delay_blocks = d;

4. official beacon is taken from a canonical finalized block at/after h + d;

5. derive one submission-specific exam_id from the pinned challenge/generator/scoring versions, submission identifier/hash, future beacon, and a protocol run nonce/domain separator;

6. derive official_train, official_eval, and official_stress role seeds from that exam_id;

7. all validators evaluating that submission use the same derivation.

The value of d must be selected from Bittensor/Subtensor finality and reorg behavior, not guessed in this document.

Do not use validator hotkey in the scientific seed.

OQ-006 — Production beacon qualification

Recommendation: Target a hybrid public beacon for production:

beacon = H(chain randomness || independently operated distributed public randomness)

with a drand-class verifiable distributed beacon as the preferred external component.

Qualification requirements:

● public verifiability;

● deterministic retrieval by all validators;

● defined behavior for delayed/missing external rounds;

● domain separation;

● replay/reorg handling;

● evidence that no single miner, validator, Carbon operator, or chain block producer can cheaply choose the final exam;

● explicit fallback that fails closed or uses a previously specified safe source rather than silently changing randomness semantics.

I would not make validator commit-reveal the primary production mechanism unless security review shows the hybrid beacon is infeasible; validator commit-reveal adds withholding and liveness complexity inside the consensus population.

OQ-007 — Validator disagreement procedure

Recommendation: Median aggregation should handle isolated faulty/outlier validators, not hide under-specified experiments.

Proposed policy:

1. validators attest the same exam pin and return score + reproducibility metadata;

2. discard objectively invalid/infra-failed attestations;

3. compare remaining honest-looking results against the challenge/backend reproducibility tolerance;

4. if a quorum agrees within tolerance, aggregate using the protocol’s robust statistic;

5. if the honest-looking quorum exceeds tolerance, mark the submission CONTESTED / NON-EMITTING, automatically retry on qualified infrastructure;

6. if retry still disagrees, quarantine the challenge/backend combination and open an incident; do not award a median-derived scientific rank until resolved.

No strategy should receive a physics zero because validators disagree about the experiment.

Security / execution

OQ-008 — P0 strategy execution threat model

Recommendation: Make P0 declarative and bounded. Do not accept arbitrary miner Python/JAX/PyTorch code for execution on validators.

Allow strategy fields only from versioned schemas and registries, such as:

● approved backbone family and bounded architecture parameters;

● approved optimizer and training parameters;

● approved loss modules and weights;

● approved curricula;

● approved training-data sampling controls inside the challenge contract;

● approved augmentations.

Deny:

● arbitrary imports/code;

● network access;

● filesystem paths;

● subprocesses;

● custom executables;

● user-controlled seeds for official roles;

● gate/scorer overrides;

● arbitrary deserialization payloads.

Even declarative strategies run in a sandbox with:

● no network;

● scratch-only filesystem;

● CPU/GPU/RAM/VRAM/wall-clock/step limits;

● immutable base image and dependency set;

● canonical schema validation before queueing;

● output-size limits;

● process isolation and kill policy;

● audit logs that do not leak official seed material.

Later richer extension mechanisms should require a separate threat model and sandbox qualification.

OQ-009 — Disclosure budget validation

Recommendation: Treat disclosure as an adversarial information-budget problem.

For P0 EvaluationCard, expose:

● final overall score;

● coarse physics/robustness/accuracy component values or bands;

● mandatory gate pass/fail;

● controlled failure-mode tags;

● short safe diagnostics;

● challenge/scoring version hashes.

Withhold:

● official seeds/draw IDs;

● per-draw values;

● fine distance-to-threshold margins;

● per-stress numeric breakdowns;

● exact worst-case sample identity;

● reference fields.

Validation method:

1. build an internal red-team agent that adaptively submits strategies and attempts to infer hidden category mix/draws;

2. measure whether repeated EvaluationCards materially outperform legitimate free-loop information at predicting exact official hidden outcomes;

3. test differencing/near-duplicate strategy attacks;

4. impose submission/rate budgets and coarsen fields that become reconstruction channels;

5. version disclosure policy when granularity changes.

The goal is not zero correlation with quality; it is preventing reliable exam reconstruction or rank substitution.

Economics / operations

OQ-010 — Exam fee

Recommendation: Do not set a permanent token amount before measured P0 cost exists.

Use:
exam_fee = transparent expected validator resource cost + anti-spam/congestion margin

subject to:

● fee never enters scientific score;

● rejected-before-exam submissions are not charged/refunded;

● Carbon/validator infrastructure failure gets retry credit/refund;

● delivered exams and miner-attributable strategy failures consume the fee;

● identical open submissions are idempotent;

● fee schedule is published and versioned;

● no payment tier buys a better exam or scientific ranking.

For early testnet, use zero or nominal economic value while measuring actual GPU time, queue occupancy, and abuse patterns. Ratify a real fee only from those measurements.

OQ-011 — Submission/rate limits

Recommendation: Start conservative and cost-based, with per-hotkey concurrency plus rolling-window quotas, then tune from telemetry.

Policy shape:

● one active official exam per hotkey per challenge by default;

● duplicate strategy/challenge submissions while open return the existing submission ID;

● a rolling submission quota sized so a single miner cannot monopolize validator capacity;

● separate free-loop limits from paid official exams;

● challenge-specific resource classes;

● emergency global backpressure when validator utilization/queue latency crosses operational limits.

Do not encode permanent numeric quotas until P0 measurements exist.

The optimization target is enough iteration for competition while preventing one participant from consuming disproportionate validator compute.

OQ-012 — Validator operating envelope

Recommendation: P0 should qualify a small homogeneous reference execution profile first.

The profile should pin:

● OS/container digest;

● Python/JAX/CUDA/cuDNN or equivalent versions;

● approved GPU class(es);

● CPU/RAM/VRAM minimums;

● precision policy;

● resource limits;

● deterministic settings;

● network/filesystem isolation;

● reference solver environment.

Qualification requires:

● repeated-run reproducibility;

● sustained-load soak testing;

● OOM/timeout/kill behavior;

● queue recovery;

● node-loss retry;

● storage/card durability;

● score agreement across every supported hardware profile.

Add hardware profiles only after each one independently passes the same qualification suite. Do not broaden hardware support by loosening scientific tolerances.

Qualification / ownership

OQ-013 — Sign-off owners

Recommendation: Use named roles with separation of duties, then bind actual people/keys in the qualification manifest.

Minimum sign-offs:

● Physics/SciML Approver: envelope, generator dossier, scientific thresholds;

● Protocol Approver: challenge/Score Pack binding, seed semantics, emissions rules;

● Security Approver: execution isolation, disclosure, randomness threat model;

● Infrastructure Approver: backend digest, reproducibility, resource/ops qualification;

● Product Approver: Product Qualification Pack for commercial SKUs;

● Launch Approver: confirms Launch Bar completeness and authorizes LIVE transition.

For P0, one person may temporarily hold multiple roles if team size requires it, but the manifest must state that explicitly. No coding agent is an approver.

OQ-014 — First LIVE flip

Recommendation: Make 1D viscous Burgers the first LIVE challenge/version, but only after the complete qualification bundle is green.

Required before flip:

● approved envelope/exclusions;

● generator dossier;

● approved Score Pack;

● qualified backend/reproducibility tolerance;

● seed/randomness implementation and leakage tests;

● mock/official isolation;

● budgeted EvaluationCard;

● infra/science failure separation;

● actual Bittensor testnet scores → weights path;

● security review for the P0 execution surface;

● signed Launch Bar / qualification manifest.

Do not couple first LIVE to completion of Landscape, Specialist Bank, all seven academic PDEs, or mainnet.

OQ-015 — Product Qualification Pack v1

Recommendation: Do not freeze one universal commercial threshold set before Carbon has a concrete SKU and customer job.

Freeze the structure now:

● PB-PHYS — fresh controlled retrain + physics/stress;

● PB-ROLL — product-depth rollout/plant behavior where relevant;

● PB-INV — inverse-design task where relevant;

● PB-ADV — directed adversarial search inside the certified envelope;

● PB-LAT — latency class on named hardware;

● PB-ART — deployable artifact parity;

● PB-ESC — explicit escalation/failure-envelope guidance.

For the first full-surrogate catalog SKU, require all applicable mandatory PB gates, a versioned operating certificate, fresh/decontaminated seeds, exact artifact/recipe hashes, hardware profile, and requalification after any material model, recipe, envelope, backend, or customer adaptation change.

The first Product Qualification Pack should be written for the first actual product job, not retrofitted from the lean Burgers leaderboard.

Recommended closure summary

I recommend the team treat the following as the proposed closure:

|Question|Proposed answer                                                                |
|--------|-------------------------------------------------------------------------------|
|OQ-001  |Narrow 1D viscous Burgers envelope; exact numeric bounds come from dossier     |
|OQ-002  |Evidence-appropriate Burgers dossier with strong reference + coverage          |
|OQ-003  |Binary Burgers gates + 45/30/25 weighted-geometric baseline; tau from dossier  |
|OQ-004  |Measured backend-specific reproducibility tolerances; narrow P0 hardware       |
|OQ-005  |Submission commit → delayed future finalized block → shared exam identity      |
|OQ-006  |Hybrid chain + distributed public randomness production target                 |
|OQ-007  |Out-of-tolerance validator disagreement → contested/non-emitting + retry       |
|OQ-008  |Declarative bounded P0 strategies; no arbitrary miner code                     |
|OQ-009  |Coarse EvaluationCard + adversarial reconstruction testing                     |
|OQ-010  |Cost-based published fee after testnet measurements                            |
|OQ-011  |Per-hotkey concurrency + rolling quota, tuned from telemetry                   |
|OQ-012  |Small homogeneous qualified validator profile first                            |
|OQ-013  |Explicit role-based sign-offs in qualification manifest                        |
|OQ-014  |1D viscous Burgers first LIVE after full qualification                         |
|OQ-015  |Product-Battery structure now; numeric product thresholds only for concrete SKU|

What still requires evidence rather than opinion

Even if the architecture recommendations above are accepted, the following should not be ratified from this document alone:

● exact Burgers viscosity/IC/domain/resolution/horizon values;

● exact gate thresholds;

● exact reproducibility epsilon;

● exact seed-delay block count;

● exact exam fee;

● exact rate-limit numbers;

● exact supported GPU models;

● exact Product-Battery thresholds.

Those are qualification outputs and should be backed by measurements, scientific evidence, security review, or economics—not architectural preference.
## Explicitly not open
Shared-vs-per-validator exam identity, binary hard gates, weighted-geometric aggregation, P0 45/30/25 baseline, universal-P0-UQ, public-physics/hidden-realization, reference-cache role, Port-B variable grading, winning-strategy candidacy, and P0-one-vertical-first are resolved by the reconciled specs.
