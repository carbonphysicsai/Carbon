# Carbon Scientific Reference Canon v3 — Unified Master

**Status:** Research/evidence map + scientific exploration framework for team review  
**Purpose:** Unified evidence base, argument map, claim-control instrument, and bounded agentic exploration substrate for Carbon.  
**Supersedes for scientific framing:** `SCIENTIFIC_REFERENCE_CANON.md` v2 + the v3 symbolic-numeric addendum/publication integration notes.  
**Does not supersede:** normative protocol specifications, current code, scoring authority, Challenge Registry, Product Battery rules, or qualification artifacts.  
**Scope rule:** Long-term scientific ontology does not broaden P0 implementation scope.

---

# 1. Canon charter

The Carbon Scientific Reference Canon has **four roles**.

## 1.1 Evidence base

The canon records the strongest scientific, engineering, statistical, and mechanism-design evidence relevant to Carbon's thesis.

It answers:

> What does established or frontier literature actually support about the problem Carbon is trying to solve?

## 1.2 Argument map

The canon structures the scientific case Carbon can responsibly make in public.

It distinguishes:

```text
external premise
      !=
Carbon design
      !=
Carbon implementation
      !=
Carbon evidence
      !=
production qualification
```

## 1.3 Design and claim-control instrument

The canon is used to audit new protocol, product, Landscape, measurement, and qualification ideas against scientific precedent and Carbon's epistemic constitution.

It exists partly to prevent three common failures:

1. citation -> unjustified protocol authority;
2. implementation -> unjustified scientific claim;
3. attractive narrative -> unjustified causal or qualification claim.

## 1.4 Agentic Exploration Zone

The canon is now also a **bounded scientific exploration substrate for research agents and miners**.

Agents may use the canon together with Challenge semantics and permitted Landscape evidence to generate hypotheses about:

- training and fitting strategies;
- architectures and representations;
- model decomposition;
- hybrid mechanistic/learned constructions;
- reduced-order and symbolic-numeric methods;
- numerical methods and coupling strategies;
- truth/data-acquisition policies;
- measurements and information-value experiments;
- eventually, new model-construction algorithms.

The exploration zone is **generative, not authoritative**.

A canon-supported method is not thereby preferred. A cited mechanism is not thereby correct. An agent-generated method is not thereby safe. A proposed measurement is not thereby score-bearing.

> **Canon informs hypotheses. Carbon experiments adjudicate them.**

The canon is part of the explorer, never part of the scientific judge.

---

# 2. Carbon's scientific case

The whitepaper and other public materials should present Carbon as a chain of independently supportable premises.

## 2.1 Premise chain

1. **Fast physical models create real economic leverage.** Learned operators, reduced models, hybrid models, symbolic/numerical reductions, and other approximations can reduce repeated-query cost in suitable regimes.
2. **Low predictive loss is incomplete evidence.** Fit alone does not establish physical admissibility, robustness, uncertainty behavior, rollout stability, answerability, or context-of-use credibility.
3. **Physics can be evaluated separately from fit.** Conservation, constraints, admissibility, residual behavior, boundary behavior, and other physical properties can be explicit scientific dimensions.
4. **Credibility is bounded.** Engineering V&V/VVUQ ties credibility to use context, evidence, uncertainty, reliance, and lifecycle state.
5. **Adaptive search can overfit evaluation.** Repeated feedback can consume holdout independence even when examples remain hidden.
6. **Open competition can be useful under uncertain search.** Diverse independent solvers can find strong or complementary hypotheses when the target is externally measurable.
7. **Agentic research increases hypothesis throughput.** Autonomous research systems make machine-generated search and experiment loops plausible.
8. **Producer independence requires reproducibility and provenance.** Scientific claims depend on how an artifact was constructed, executed, measured, and reproduced.
9. **Failures are scientific data.** Weak, unstable, irreproducible, or gate-failing strategies can identify dead regions and failure mechanisms.
10. **Experimental memory can improve future search.** Active learning and closed-loop experimentation motivate learning from prior outcomes.
11. **Observational memory is not causal knowledge.** Search history is selected and confounded; deliberate intervention is required for stronger causal claims.
12. **Fast models inside optimizers need trust boundaries.** Downstream optimizers can exploit surrogate error; truth calls, trust regions, answerability, and escalation matter.
13. **Qualification is a lifecycle.** Model, measurement, runtime, context, and system changes can invalidate prior evidence.
14. **Physical AI is not one model family.** Neural, symbolic-numeric, reduced, classical, hybrid, and composed models are all legitimate scientific candidates.
15. **Measurement is its own scientific object.** A governing law does not uniquely determine a numerical metric, discretization, normalization, aggregation, uncertainty floor, or threshold.
16. **Component credibility does not automatically compose.** Couplings, interfaces, joint envelopes, numerical integration, and assembled behavior require separate evidence.
17. **Agentic exploration can extend to algorithm discovery.** A mature Carbon can allow agents to propose construction methods Carbon developers did not preimplement while keeping construction separate from official evaluation.
18. **Bittensor supplies economic selection pressure, not physical truth.** Carbon defines the scientific contract; independent evidence determines outcomes.
19. **Carbon's synthesis is falsifiable.** The system must demonstrate better scientific and engineering decisions than credible alternatives.

## 2.2 Core synthesis

> **If credible physical generalization is the unresolved commercial target, make physics-surviving generalization the target of an open intelligence market.**

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

The literature motivates the architecture. Carbon's own experiments must establish whether the mechanism actually works.

---

# 3. Canon discipline

## 3.1 Evidence tiers

- **Tier I - Foundational:** durable sources appropriate for public scientific claims.
- **Tier II - Deep canon:** narrower whitepaper/design rationale.
- **Tier III - Frontier / Exploration Zone:** recent or hypothesis-generating work that should not carry foundational claims alone.

## 3.2 Evidence-strength labels

- STANDARD / AUTHORITATIVE GUIDANCE
- FOUNDATIONAL PRIMARY
- PRIMARY EMPIRICAL
- BENCHMARK / DATASET
- REVIEW
- THEORETICAL PRIMARY
- PRIMARY SYSTEMS / SCIENTIFIC-COMPUTING WORK
- FRONTIER PRIMARY

## 3.3 Public citation semantics

Every public use of a source should distinguish:

- **Supports** - the premise supported by the source.
- **Does not prove** - Carbon-specific conclusions the source cannot establish.
- **Use** - litepaper, whitepaper, design rationale, or watchlist.

> **External literature supports premises. Carbon specifications define the mechanism. Carbon experiments determine whether the mechanism works.**

## 3.4 Exploration-zone semantics

For agentic use, a source should eventually expose or be annotatable with:

- **Search affordance** - hypotheses it can motivate.
- **Applicability conditions** - physical/numerical assumptions and regimes.
- **Failure/limitation cues** - reasons it may not transfer.
- **Evidence maturity** - foundational, replicated, benchmarked, or frontier.
- **Prohibited inference** - what the agent must not promote to truth or protocol authority.

The exploration zone should prefer explicit uncertainty and unresolved state over fabricated completeness.

---

# 4. Pillar A - Learned operators make fast learned physics possible

## Core sources

- Li et al., *Fourier Neural Operator for Parametric Partial Differential Equations* (ICLR 2021), https://arxiv.org/abs/2010.08895
- Kovachki et al., *Neural Operator: Learning Maps Between Function Spaces* (JMLR 2023), https://arxiv.org/abs/2108.08481
- Lu et al., *Learning nonlinear operators via DeepONet based on the universal approximation theorem of operators* (Nature Machine Intelligence 2021), https://arxiv.org/abs/1910.03193

**Supports:** operator learning as a practical class of fast physical models and a strong first Carbon search space.

**Does not prove:** production credibility, OOD reliability, or Carbon's protocol hypothesis.

**Exploration affordance:** operator representations, discretization behavior, architecture variants, spectral/graph/function-space approximations, transfer across PDE families.

---

# 5. Pillar B - Predictive fit does not automatically preserve physics

## Core sources

- Karniadakis et al., *Physics-informed machine learning* (Nature Reviews Physics 2021), https://www.nature.com/articles/s42254-021-00314-5
- Raissi et al., *Physics-informed neural networks* (JCP 2019), https://arxiv.org/abs/1711.10561
- Li et al., *Physics-Informed Neural Operator* (2021), https://arxiv.org/abs/2111.03794
- Hernandez et al., *Structure-preserving neural networks* (JCP 2021), https://doi.org/10.1016/j.jcp.2020.109950
- Hansen et al., *Learning physical models that can respect conservation laws* (Physica D 2024), https://doi.org/10.1016/j.physd.2023.133970
- Greydanus et al., *Hamiltonian Neural Networks* (2019), https://arxiv.org/abs/1906.01563

**Supports:** physical laws, structure, and invariants can be distinct modeling objectives rather than left to scalar fit alone.

**Canon law:**

> **Physics > loss means mandatory physical failure cannot be compensated by predictive fit. It does not mean explicit symbolic physics must exist inside the candidate.**

No symbolic, mechanistic, or hybrid method receives an ideological score advantage.

---

# 6. Pillar C - Generalization, robustness, uncertainty, and rollout remain open

## Core sources

- Takamoto et al., *PDEBench* (2022), https://arxiv.org/abs/2210.07182
- Psaros et al., *Uncertainty quantification in scientific machine learning* (JCP 2023), https://doi.org/10.1016/j.jcp.2022.111902
- Magnani et al., *Approximate Bayesian Neural Operators* (2022), https://arxiv.org/abs/2208.01565
- Mouli et al., *Using UQ to Characterize and Improve Out-of-Domain Learning for PDEs* (2024), https://arxiv.org/abs/2403.10642
- Winovich et al., *Active operator learning with predictive uncertainty quantification* (2025), https://arxiv.org/abs/2503.03178

Carbon should distinguish four levels of generalization:

1. **candidate generalization** - hidden draws/regimes;
2. **intervention transfer** - whether a construction method transfers across physical contexts;
3. **measurement/evidence portability** - whether the same measurement/threshold can transfer under aligned assumptions;
4. **qualification generalization** - whether a bounded product claim remains valid under the intended use.

The commercial gap is therefore not simply whether a fast model generalizes. It is whether Carbon can produce **credible, evidence-bounded claims about where it generalizes and where it should refuse or escalate**.

---

# 7. Pillar D - Engineering credibility is bounded by context of use

## Core sources

- ASME VVUQ 1-2022, terminology for verification, validation, and UQ.
- ASME V&V 40-2018, risk-informed credibility for a stated context of use.
- NASA-STD-7009B (2024), Standard for Models and Simulations.
- NASA-HDBK-7009B (2026), implementation guidance for model/simulation credibility.
- Johnson, *Applying NASA-STD-7009 to Surrogate and Other Statistical Models* (NASA NTRS 20200002832).

**Supports:** bounded context-of-use claims, evidence-linked credibility, acceptance criteria, lifecycle reasoning, and explicit limitations.

**Canon extension:** qualification can apply to one artifact or an assembled physical-decision system. Component qualification does not automatically compose.

---

# 8. Pillar E - Adaptive evaluation requires protected information boundaries

## Core sources

- Dwork et al., *The reusable holdout* (Science 2015).
- Blum & Hardt, *The Ladder* (ICML 2015).
- Nakkiran & Blasiok, *The Generic Holdout* (2018).

**Supports:** repeated adaptive interaction with evaluation information can damage nominal holdout validity.

Symbolic-numeric and agentic discovery strengthen this pillar because machine-readable physics and generated diagnostics create additional Goodhart surfaces.

> **Public scientific semantics do not imply public official realizations, and structured intelligence does not bypass the Evaluation Information Budget.**

---

# 9. Pillar F - Open competition can be useful under uncertain search

## Core sources

- Saez-Rodriguez et al., *Crowdsourcing biomedical research* (Nature Reviews Genetics 2016).
- Boudreau, Lacetera & Lakhani, *Incentives and Problem Uncertainty in Innovation Contests* (Management Science 2011).
- Eduati et al., collaborative competition work in Nature Biotechnology (2015).

**Supports:** diverse independent competitors can produce strong/complementary hypotheses under uncertainty when results can be externally evaluated.

**Does not prove:** Carbon's emissions or economic design is optimal.

**Canon law:** novelty is not a primary performance-score term. Demonstrated evidence earns performance reward; uncertain information value can be purchased separately.

---

# 10. Pillar G - Agentic science makes closed-loop research plausible

## Core sources

- Szymanski et al., *An autonomous laboratory for the accelerated synthesis of inorganic materials* (Nature 2023).
- Abolhasani & Kumacheva, *The rise of self-driving labs in chemical and materials sciences* (Nature Synthesis 2023).
- Ren et al., *Autonomous experiments using active learning and AI* (Nature Reviews Materials 2023).
- Canty et al., *Science acceleration and accessibility with self-driving labs* (Nature Communications 2025).

The canon distinguishes:

### G-A. Registered-method agentic search

Agents search known parameters, recipes, architectures, curricula, compositions, or registered construction methods.

### G-B. Agentic construction-method discovery

Future agents may propose the construction algorithm itself, subject to independent sandboxed reconstruction and protected evaluation.

> **Agent autonomy expands hypothesis generation, not scientific authority.**

---

# 11. Pillar H - Reproducibility and provenance are first-class

## Core sources

- Heil et al., *Reproducibility standards for machine learning in the life sciences* (Nature Methods 2021).
- Mitchell et al., *Model Cards for Model Reporting* (FAccT 2019).

Carbon's generalized principle is:

> **Producer-independent reconstruction is the invariant; fresh retraining is its learned-model subtype.**

Depending on construction family, reconstruction may mean fresh training, basis construction, symbolic reduction, solver configuration, component assembly, or another registered/sandboxed build.

P0 Model Cards remain correct. Long-term experimental memory should support a technology-neutral `ExperimentRecord` superclass.

---

# 12. Pillar I - Experimental memory can improve future search

Retain active-learning and autonomous-experimentation evidence from Pillars C/G.

The richer Carbon experimental object should preserve, where applicable:

```text
construction intervention
x pre-intervention physical context
x selection mechanism
x construction/truth-access policy
x exact measurement identity
x execution/reconstruction provenance
-> outcome / censoring
-> reproducibility
-> qualification / lifecycle evidence
```

Failures are evidence. Censoring, scientific failure, construction/training failure, and infrastructure failure are not equivalent states.

---

# 13. Pillar J - Observational memory is not causal knowledge

## Core sources

- Pearl, *Causality* (2nd ed., 2009).
- Hernan & Robins, *Causal Inference: What If* (2020).

New Carbon requirements:

- preserve selection provenance;
- type pre/post-intervention features;
- distinguish authored, derived, and learned physical features;
- preserve exact measurement-version identity;
- use registered experiments where stronger causal claims matter.

> **Landscape may predict before it explains, and it may explain association before it claims causation.**

---

# 14. Pillar K - Fast physical models inside optimizers need truth boundaries

## Core sources

- Alexandrov et al., trust-region model management (2000).
- Forrester & Keane, *Recent advances in surrogate-based optimization* (Progress in Aerospace Sciences 2009).
- Liang et al., trust-region filter survey (2024).

Answerability must be prospective:

- universal response may be required;
- bounded abstention may be allowed;
- routing among qualified models may be allowed;
- high-fidelity escalation may be required.

A candidate cannot selectively decline difficult official cases unless the registered task permits it.

---

# 15. Pillar L - Qualification is a lifecycle

Retain ASME/NASA lifecycle evidence and selective-risk/calibration literature.

Qualification identity may bind:

- assembled artifact/component graph;
- physical-system/context identity;
- measurement contracts;
- runtime realization where relevant;
- answerability/coverage semantics;
- context of use.

> **Qualified components plus a coupling do not automatically equal a qualified system.**

---

# 16. Pillar M - Bittensor is the incentive substrate, not scientific authority

Retain official Bittensor documentation for neurons, emissions, and Yuma Consensus.

Bittensor coordinates search and reward. Carbon defines the registered scientific target and independent evidence process.

Consensus does not determine physical truth.

---

# 17. Pillar N - Carbon's thesis must remain falsifiable

Carbon-specific claims should carry maturity labels:

- MOTIVATED
- SPECIFIED
- IMPLEMENTED
- TESTED
- REPLICATED
- PRODUCTION-QUALIFIED

No external paper can move a Carbon claim from MOTIVATED to TESTED.

H1-H27 are listed in Section 25.

---

# 18. Pillar O - Symbolic-numeric models separate physical semantics from numerical realization

## Core sources

- Ma et al., *ModelingToolkit: A Composable Graph Transformation System For Equation-Based Modeling* (2021), https://arxiv.org/abs/2103.05244
- Foundational Modelica equation-based/acausal modeling literature, https://modelica.org/papers/1998-06-fritzson-para98LNCS1541-equationbasedmodelingandHighPerformance.pdf

**Supports:** equation-based symbolic representation, composition, structural transformation, and conversion to numerical implementation.

**Does not prove:** symbolic correctness, numerical adequacy, operational equivalence, or automatic Carbon gate generation.

> **Authored physical semantics, transformed symbolic semantics, and numerical realization are related but distinct evidence layers.**

> **Symbolic equivalence does not automatically imply numerical or operational equivalence.**

---

# 19. Pillar P - Hybrid mechanistic/data-driven models make model construction a search space

## Core sources

- Rackauckas et al., *Universal Differential Equations for Scientific Machine Learning* (2020), https://arxiv.org/abs/2001.04385
- Ghattas & Willcox, *Learning physics-based models from data: perspectives from inverse problems and model reduction* (Acta Numerica 2021), https://doi.org/10.1017/S0962492921000064

**Supports:** known physics and learned/data-driven components can coexist; model construction is broader than monolithic neural surrogacy.

**Does not prove:** hybrid superiority or mechanistic truth of learned internal terms.

> **Which permitted model-construction intervention produces the strongest evidence-bounded fast physical model for the registered task?**

That is Carbon's durable search question.

---

# 20. Pillar Q - Reduced-order modeling establishes a mature non-neural fast-model tradition

- Benner, Gugercin & Willcox, *A Survey of Projection-Based Model Reduction Methods for Parametric Dynamical Systems* (SIAM Review 2015), https://doi.org/10.1137/130932715

**Supports:** reduced models as cheaper physical representations for repeated simulation, design, control, optimization, and UQ.

> **The protocol should reward evidence-bounded physical utility, not the presence of machine learning.**

---

# 21. Pillar R - Measurement is distinct from the property being measured

## Core sources

- Oberkampf & Roy, *Verification and Validation in Scientific Computing* (2010).
- Oberkampf & Barone, *Measures of agreement between computation and experiment: Validation metrics* (JCP 2006), https://doi.org/10.1016/j.jcp.2006.03.037

**Supports:** explicit quantitative measurement definitions and separation of mathematical model, numerical implementation, error, observation, and predictive claim.

Reconciled Carbon chain:

```text
physical relation / property
        ↓
MeasurementContract
        ↓
reference + calibration evidence
        ↓
Validation Dossier
        ↓
Score Pack use
```

> **Measurement definition != measurement qualification != measurement use.**

A physical equation does not determine derivative estimation, discretization, normalization, aggregation, uncertainty floor, or threshold.

---

# 22. Pillar S - Composition creates interface evidence and non-compositional qualification

Equation-based modeling supports compositional physical systems. Engineering credibility remains bounded.

Carbon should distinguish:

- component physical semantics;
- coupling/interface semantics;
- numerical coupling realization;
- component measurements;
- interface measurements;
- assembled-system measurements;
- product-context measurements.

> **Independently qualified components still require evidence about interfaces, joint envelope, numerical coupling, and assembled behavior.**

This motivates future scoped identities, `CouplingContract`, units/nondimensionalization, geometry references, and system-level qualification without ratifying final schemas prematurely.

---

# 23. Pillar T - Physics intelligence must demonstrate prospective decision value

Recommended definition:

> **Physics intelligence is provenance-bearing knowledge about how model-construction interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by improved prospective decisions rather than retrospective narrative alone.**

A knowledge graph, embedding, ontology, or large model is not a moat merely because it exists.

Strong claims require measurable decision lift such as:

- better held-out intervention-transfer prediction;
- better experiment selection under fixed budget;
- better qualification-outcome prediction;
- lower regret/cost to reach qualified models;
- better engineering decision economics.

---

# 24. Pillar U - Agentic Exploration Zone and construction-algorithm discovery

## 24.1 Exploration hierarchy

```text
parameter search
  ↓
recipe / strategy search
  ↓
architecture / composition search
  ↓
construction-algorithm discovery
```

Carbon should begin with bounded registered strategy spaces. Later maturity may permit executable construction hypotheses that Carbon developers did not preimplement.

## 24.2 Exploration inputs

A research agent may reason over:

```text
Scientific Canon
+ Challenge / PhysicalSystem semantics
+ registered construction methods
+ permitted Landscape evidence
+ resource and truth-access constraints
```

and propose architectures, decompositions, fitting procedures, symbolic/reduced methods, hybrid closures, truth-acquisition policies, measurements, experiments, or new construction algorithms.

## 24.3 Authority boundary

```text
agent hypothesis
      ↓
registered or sandboxed independent reconstruction
      ↓
protected official evaluation
      ↓
ExperimentRecord
      ↓
reproduction / Landscape evidence
      ↓
possible method registration
```

> **The construction-method producer cannot define the official measurement that proves its own success.**

> **Construction and official evaluation are separate security domains.**

## 24.4 Construction Method Library

Successful novel algorithms may eventually graduate into reusable evidence-bearing method identities with:

- registered reconstruction protocol;
- supported physical/construction scopes;
- dependency/environment identity;
- evidence summary;
- reproducibility state;
- known failure regimes;
- maturity/epistemic state.

This creates three potential compounding assets:

1. **qualified fast physical models/systems**;
2. **physics intelligence from experimental evidence**;
3. **reusable construction methods with evidence and known limits**.

Novelty itself remains outside the primary performance score. Port C/information-value experiments may fund reproduction or ablation of uncertain methods separately.

---

# 25. Carbon research hypotheses H1-H27

The hypotheses below are Carbon research questions, not established results.

## Discovery and incentive mechanism

**H1 - Physics-weighted objective.** Does physics-weighted competition produce methods with better robustness and downstream engineering behavior than plausible accuracy-first baselines under matched resources?

**H2 - Open search.** Under matched budget, does open competition discover stronger or more diverse methods than credible centralized search?

**H3 - Incentive persistence.** Does persistent economic selection improve verified progress per compute/time/cost relative to comparable non-incentivized search?

**H4 - Producer independence.** Does validator-controlled reconstruction reduce irreproducible or artifact-specific performance claims relative to producer-supplied artifacts?

**H5 - Protected evaluation.** Does hidden procedural evaluation plus constrained feedback reduce adaptive overfitting compared with more exposed designs?

**H6 - Guidance utility.** Does controlled/noisy search guidance improve sample efficiency without becoming a rank oracle or collapsing exploration?

## Evidence and product predictiveness

**H7 - Lean-to-product predictiveness.** How predictive is lean scientific evidence of Product Battery/qualification success?

**H8 - Reproducibility value.** Does reconstruction/replication evidence improve prediction of downstream reliability beyond single-run score?

## Physics intelligence and experiment allocation

**H9 - Landscape prediction.** Can experimental memory prospectively predict outcomes better than simple priors?

**H10 - Information-value experiments.** Can Landscape-proposed experiments reduce uncertainty or improve decisions faster than random/performance-only/expert baselines?

**H11 - Product reliability.** Do qualification outcomes predict severe failures/reliability in job-shaped workloads better than rank or accuracy alone?

**H12 - Answerability/economics.** Do bounded answerability and escalation improve decision economics versus solver-only or unrestricted-surrogate use?

**H13 - Lifecycle validity.** Which material changes invalidate prior qualification evidence and require requalification?

**H14 - Full-stack economics.** Does Carbon produce better engineering decision economics than credible alternative workflows?

**H15 - Governance/security.** Do Carbon's governance and trustless-verification controls resist leakage, manipulation, and selective interpretation sufficiently for the intended claims?

**H16 - Structured physical context.** Does provenance-bearing physical context improve prospective intervention-transfer prediction relative to Challenge identity and ordinary metadata alone?

**H17 - Physical similarity representations.** Which physical-context representations (authored features, dimensionless groups, symbolic structure, learned representations) actually improve held-out transfer or decision quality?

**H18 - Experimental-memory moat.** Does accumulated intervention/outcome/qualification history measurably improve future search and product-selection performance over simpler/public alternatives?

## Symbolic-numeric and authoring hypotheses

**H19 - Scientific authoring efficiency.** Does structured physical representation reduce Challenge-authoring time, semantic drift, or scientific-definition errors without weakening human review?

**H20 - Measurement-contract integrity.** Does explicit versioned measurement identity reduce metric/threshold drift and improve reproducibility across implementations/Challenge versions?

**H21 - Hybrid model-construction search.** For appropriate Challenges, does competition across learned, hybrid, reduced, and other allowed families produce better evidence-bounded outcomes than one-family search under matched constraints?

**H22 - Producer-independent reconstruction across families.** Does family-appropriate independent reconstruction preserve or improve reproducibility/gaming resistance across heterogeneous model classes?

**H23 - Context-aware portfolio value.** Can a qualified portfolio/router/escalation system improve engineering decision economics over a single universal fast model while preserving bounded answerability?

**H24 - Challenge-authoring product value.** Can evidence-aware Challenge authoring convert partner/domain models into reviewable experimental programs faster or with fewer defects than bespoke unstructured workflows?

**H25 - Composition qualification.** Does explicit coupling/joint-envelope evidence predict assembled-system reliability better than composing independently qualified subsystem claims?

## Agentic exploration hypotheses

**H26 - Open construction discovery.** Under matched scientific and resource constraints, does allowing sandboxed agent-proposed construction algorithms discover stronger or more diverse methods than restricting search to a registered method catalog?

**H27 - Method-library compounding.** Does an evidence-bearing Construction Method Library improve future search efficiency, method transfer, or scientific decision quality?

For high-value hypotheses, Carbon should precommit comparator, resource budget, primary outcome, and rejection criterion before observing decisive evidence where practical.

---

# 26. Agentic Exploration Zone operating doctrine

The exploration zone should become progressively more capable without collapsing the distinction between ideation and evidence.

## 26.1 Maturity ladder

### E0 - Retrieval

Agent retrieves relevant canon sources, Challenge semantics, known methods, and limitations.

### E1 - Registered strategy synthesis

Agent proposes combinations of known knobs/methods inside current ConstructionPolicy.

### E2 - Architecture/composition synthesis

Agent proposes new arrangements of registered components and model families.

### E3 - Experimental-method proposal

Agent proposes novel construction algorithms, truth-use policies, or measurement hypotheses for controlled review/sandboxing.

### E4 - Evidence-linked method discovery

Agent proposes methods based on canon + Landscape evidence, Carbon executes registered experiments, and successful methods can graduate to reusable method records.

No maturity level grants the agent authority over official scoring, Challenge registration, measurement qualification, or product qualification.

## 26.2 Exploration outputs must be typed

Examples:

- `literature_supported_hypothesis`
- `landscape_predictive_hypothesis`
- `construction_program_candidate`
- `measurement_hypothesis`
- `port_c_experiment_proposal`
- `method_registration_candidate`

Typed outputs reduce the risk that an attractive generated explanation is mistaken for evidence.

## 26.3 Exploration and proprietary science

Private partner semantics require explicit access controls. Canon retrieval, agent context, generated outputs, and Landscape feedback must respect disclosure classification. Public wrapper semantics cannot be assumed to prevent leakage from controlled subsystems.

---

# 27. Constitutional scientific invariants

The following should be treated as Carbon's scientific constitution alongside existing protocol separations:

1. **The producer never controls the official grade.**
2. **The physical representation does not certify the physics.**
3. **Structural validation does not establish scientific validity.**
4. **Measurement definition, qualification, and score use are separate authorities.**
5. **Producer-independent reconstruction is required; retraining is one subtype.**
6. **Mechanistic/symbolic structure receives no automatic score privilege.**
7. **Scientific performance, information value, resource efficiency, and commercial utility are distinct values.**
8. **End-to-end success does not validate an internal learned physical relation.**
9. **Component qualification does not automatically compose into system qualification.**
10. **Physical similarity and physics intelligence must earn value prospectively.**
11. **Generated diagnostics and structured intelligence remain Goodhart/leakage surfaces.**
12. **Answerability, abstention, routing, and escalation are prospective task/product semantics.**
13. **The protocol should not require learning when a non-learned method wins.**
14. **Construction and official evaluation are separate security domains.**
15. **The construction-method producer cannot define the official measurement that proves its own success.**
16. **Novelty is not a primary score term.**
17. **Canon informs hypotheses; experiments adjudicate them.**

---

# 28. Whitepaper argument map

## Part I - Why physics intelligence is needed

- fast-physical-model opportunity;
- credible generalization gap;
- loss is incomplete;
- context-of-use credibility.

## Part II - Why Carbon is an incentivized scientific system

- physics > loss as a falsifiable objective hypothesis;
- open competition;
- Bittensor as incentive substrate;
- protected evaluation and adaptive information governance;
- agentic hypothesis generation.

## Part III - From competition to scientific evidence

- model-construction interventions;
- producer-independent reconstruction;
- PhysicalSystemSpec/structured physical context;
- MeasurementContract distinction;
- ExperimentRecord/provenance/failure/censoring;
- Landscape epistemic hierarchy;
- performance and information markets.

## Part IV - Agentic exploration and scientific-computing discovery

- Canon as Agentic Exploration Zone;
- registered strategy search -> architecture search -> algorithm discovery;
- Construction Program / method graduation as future architecture;
- no novelty reward;
- method library as compounding scientific asset.

## Part V - From physics intelligence to engineering value

- fresh product reconstruction/build;
- Product Battery and qualification;
- answerability/escalation;
- portfolio/routing;
- non-compositional qualification;
- lifecycle evidence.

## Part VI - Falsifiability and research program

- H1-H27;
- comparators, rejection criteria, maturity labels;
- threats to validity and economic premise.

---

# 29. Litepaper subset

The litepaper should remain compact.

Use only the concepts that improve the simple thesis:

- neural operators are the **starting model class**;
- Carbon searches for better ways to build fast physics models;
- physics > loss;
- producer-independent exam/reconstruction (say retraining for current neural implementation);
- evidence and failure memory;
- physics intelligence as learning what works across regimes;
- bounded qualification.

Do **not** explain PhysicalSystemSpec, MeasurementContract, CouplingContract, ConstructionProgram, namespaces, symbolic ASTs, or method-library internals.

---

# 30. Summit-stage subset

The stage version should remain simpler still:

> **Carbon pays people and agents to find better ways to build fast physics models - starting with neural operators - and independently tests what survives.**

Preferred stack/category:

> **Discovery + Evidence for Physics AI**

The Agentic Exploration Zone can appear verbally as:

> "Today agents search a bounded strategy space. Longer term the same system can let them discover new ways of constructing the models themselves - while the independent exam stays outside their control."

Only use that line if the room is following the simpler mechanism first.

---

# 31. Publication rules

1. Prefer primary papers, formal standards, and official protocol documentation.
2. Use reviews for synthesis, not to replace precise primary evidence.
3. Never use a citation to imply Carbon implementation exists.
4. Never use physics-informed literature to establish Carbon's exact scoring weights.
5. Never call Carbon qualification a regulatory certificate unless an authority actually certifies it.
6. Scope standards to their real domain/history.
7. Label hypothetical examples as illustrative until Carbon has corresponding evidence.
8. Distinguish observed, predictive, causal-candidate, experimentally supported, and mechanistically supported claims.
9. Treat adaptive feedback as statistical-validity and information-governance risk.
10. Treat high-fidelity simulation/experiment as truth/escalation sources where context requires.
11. Do not equate physical representation with physical truth.
12. Do not equate a physical property with its numerical measurement.
13. Do not port thresholds by metric name alone.
14. Use producer-independent reconstruction as the general principle; retain fresh retraining for learned models.
15. Do not imply mechanistic/hybrid models are inherently superior.
16. Do not infer internal mechanistic truth from end-to-end predictive success.
17. Do not imply subsystem qualification composes automatically.
18. Do not call structured physical context "physics intelligence" solely because it is structured; require prospective decision lift.
19. Do not describe Challenge Compiler concepts as automatic verification.
20. Do not broaden P0 claims from the long-term ontology.
21. Do not claim arbitrary-program agentic discovery exists before the execution/security architecture is implemented and tested.
22. Do not use frontier/exploration-zone sources as sole foundations for major public claims.

---

# 32. Research watchlist / Exploration Zone

Maintain active watch areas including:

- neural-operator OOD and long-horizon stability;
- physics-aware UQ;
- active operator learning and information-gain acquisition;
- symbolic-numeric equation-based modeling;
- compositional/acausal systems;
- hybrid mechanistic/data-driven models;
- reduced-order and projection methods;
- model discrepancy and learned closures;
- spectral/random-feature/direct-fitting scientific models;
- numerical measurement/validation metrics;
- dimensional analysis/nondimensionalization;
- autonomous scientific agents;
- algorithm/architecture discovery;
- sandboxed scientific-computing code generation;
- causal inference under adaptive selection;
- system-level qualification of composed models;
- routing among fast models with high-fidelity escalation;
- mechanism design and adversarial robustness for decentralized evaluation markets.

Frontier work should enter the exploration zone quickly but move into foundational public claims slowly.

---

# 33. Scientific identity

> **Carbon is an incentivized physics-intelligence system for discovering better ways to construct fast physical models.** Carbon begins with neural-operator training strategies, but its deeper scientific loop is technology-neutral: people and agents propose model-construction interventions; validators independently reconstruct and evaluate them under protected, registered scientific contracts; exact measurements and provenance-rich successes and failures become experimental memory; Landscape is intended to learn which interventions transfer across physical structures and regimes while preserving the distinction between prediction and causation; and selected artifacts move through a separate context-of-use qualification path with explicit answerability and escalation boundaries. The Scientific Canon provides the evidence base and, increasingly, an Agentic Exploration Zone for generating grounded hypotheses - but never the authority to certify them. Bittensor supplies competitive economic pressure; physics and qualified evidence remain the external constraint. Carbon's own experiments must establish whether this loop actually improves future search, scientific evidence, reusable construction methods, qualification, and engineering decisions.

## Short-form thesis hierarchy

**Scientific / whitepaper:**

> Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.

**Litepaper:**

> Carbon turns open competition into evidence about how to build fast, trustworthy physics models.

**Summit stage:**

> Carbon pays people and agents to find better ways to build fast physics models - starting with neural operators - and independently tests what survives.

---

# 34. Bottom line

The canon is no longer only a bibliography or publication support file.

It is:

```text
EVIDENCE BASE
    +
ARGUMENT MAP
    +
CLAIM / DESIGN CONTROL
    +
AGENTIC EXPLORATION ZONE
```

while the experimental system remains the judge.

> **Scientific literature gives Carbon a prior. Competition generates hypotheses. Independent experiments generate evidence. Landscape turns evidence into testable intelligence. The method library preserves reusable discoveries. Qualification determines what engineering claims may be made.**
