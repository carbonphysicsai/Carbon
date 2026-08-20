# Carbon Scientific Reference Canon v2

**Status:** Research/evidence map for team review  
**Purpose:** Evidence base and argument outline for Carbon's litepaper, whitepaper, scientific positioning, claim audits, and research program.  
**Authority:** This document does **not** define Carbon protocol behavior. Current code and normative Carbon specifications remain authoritative for implementation and intended mechanics. External references support scientific premises; they do not prove Carbon's protocol works.

---

# 1. The scientific case for Carbon

Carbon's whitepaper should read as a chain of independently supportable premises rather than as a list of features.

## 1.1 Case outline

1. **Learned operators create a real opportunity.** Neural operators and related surrogates can approximate families of physical-system mappings and make repeated inference dramatically faster in suitable regimes.
2. **Benchmark fit does not establish engineering credibility.** Low predictive loss does not by itself establish physical consistency, robustness, uncertainty behavior, rollout stability, or fitness for a specific context of use.
3. **Physics can be a distinct modeling objective.** Physics-informed, structure-preserving, and conservation-aware methods show that physical laws and invariants can be incorporated explicitly rather than left for scalar data loss to rediscover.
4. **Engineering credibility is bounded and evidence-backed.** V&V/VVUQ practice treats credibility as dependent on context of use, model reliance, evidence, uncertainty, limitations, and lifecycle state.
5. **Adaptive search can overfit an exposed exam.** Repeated interaction with evaluation data or leaderboards can invalidate naive holdout guarantees; protected evaluation and controlled feedback are scientifically justified.
6. **Open competition can be useful for uncertain search.** Scientific Challenges and innovation contests show that diverse independent solvers can uncover strong or complementary solutions when problems are uncertain and outputs can be evaluated independently.
7. **Agentic science makes machine-driven search plausible.** Autonomous laboratories and research-agent systems demonstrate closed loops of hypothesis or experiment generation, execution, analysis, and iteration.
8. **Independent retraining needs reproducibility and provenance.** Randomness, software/hardware state, datasets, execution identity, and reporting quality materially affect computational reproducibility; evidence artifacts should therefore be first-class objects.
9. **Experimental memory can improve future search.** Active learning and autonomous experimentation show that accumulated outcomes can be used to select more informative subsequent experiments.
10. **Observational memory is not automatically causal knowledge.** Correlation between strategy choices and outcomes can be confounded by miner selection, architecture, budget, regime, and other factors; causal claims require stronger assumptions or deliberate intervention.
11. **Surrogates inside optimizers need trust boundaries.** Surrogate-based optimization literature uses trust regions, truth-model calls, and model-management strategies because optimizing an imperfect surrogate can compromise the final design.
12. **Qualification is a lifecycle, not a one-time benchmark.** Engineering model credibility is maintained across requirements, development, deployment, use, change, and retirement; material changes can require renewed evidence.
13. **Bittensor supplies a programmable incentive substrate.** Carbon can define the validator-side scientific objective while Bittensor supplies open miner/validator competition and emissions mechanics.
14. **Carbon's synthesis is a falsifiable systems hypothesis.** Carbon proposes that an open, protected, physics-weighted, agentic search market can produce better training strategies and more useful evidence than accuracy-first or less structured alternatives. That must be demonstrated by Carbon's own experiments.

## 1.2 Carbon synthesis

> **If credible physical generalization is the unresolved commercial target, make physics-surviving generalization the target of an open intelligence market.**

> **Carbon is an incentivized physics-intelligence system: distributed hypothesis generation -> protected independent scientific evaluation -> structured experimental memory -> controlled learning -> better search -> evidence-bounded qualification.**

The literature establishes the opportunity, known failure modes, and relevant scientific/engineering disciplines. It does **not** establish that Carbon's exact scoring weights, gates, four-port Landscape, economic design, qualification semantics, or product outcomes are optimal.

---

# 2. Canon discipline

## 2.1 Evidence tiers

- **Tier I — Foundational:** durable sources appropriate for the litepaper and whitepaper.
- **Tier II — Deep canon:** whitepaper depth, design rationale, and narrower claims.
- **Tier III — Frontier/watchlist:** recent or developing work that should not carry foundational claims alone.

## 2.2 Evidence-strength labels

- **STANDARD / AUTHORITATIVE GUIDANCE** — formal engineering standard or official technical guidance.
- **FOUNDATIONAL PRIMARY** — field-defining primary work.
- **PRIMARY EMPIRICAL** — direct experimental or computational evidence.
- **BENCHMARK / DATASET** — systematic empirical benchmark.
- **REVIEW** — synthesis of a research area.
- **THEORETICAL PRIMARY** — formal result directly relevant to mechanism design.
- **FRONTIER PRIMARY** — recent primary research requiring more replication/history.

## 2.3 Required citation semantics

For every source used publicly, Carbon should distinguish:

- **Supports:** the external premise actually supported.
- **Does not prove:** Carbon-specific claims the source must not be used to imply.
- **Use:** where the source belongs in the litepaper, whitepaper, specification rationale, or research watchlist.

Publication rule:

> **External literature supports premises. Carbon specifications define the mechanism. Carbon experiments determine whether the mechanism works.**

---

# 3. Pillar A — Learned operators make fast learned physics possible

### A1. Fourier Neural Operator for Parametric Partial Differential Equations
- **Citation:** Li, Z. et al. (2020/2021), *Fourier Neural Operator for Parametric Partial Differential Equations*.
- **URL:** https://arxiv.org/abs/2010.08895
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** Operator learning across families of PDE solutions; strong results on Burgers, Darcy, and Navier-Stokes benchmarks; large inference-speed advantages in reported settings.
- **Does not prove:** Universal accuracy, production readiness, robustness outside tested regimes, or Carbon's evaluation design.
- **Use:** Litepaper opportunity statement; whitepaper operator-learning foundation.

### A2. Neural Operator: Learning Maps Between Function Spaces
- **Citation:** Kovachki, N. et al. (2021/2023), *Neural Operator: Learning Maps Between Function Spaces*.
- **URL:** https://arxiv.org/abs/2108.08481
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** General neural-operator formulation, function-space mappings, discretization-invariant construction, and PDE surrogate use.
- **Does not prove:** Engineering credibility or generalization outside the learned distribution.
- **Use:** Litepaper and whitepaper.

### A3. DeepONet
- **Citation:** Lu, L., Jin, P., Karniadakis, G. E. (2019/2021), *Learning nonlinear operators via DeepONet based on the universal approximation theorem of operators*.
- **URL:** https://arxiv.org/abs/1910.03193
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** Operator learning as a distinct approximation problem and a practical neural architecture for learning operators.
- **Does not prove:** That operator approximation error alone is adequate evidence for deployment.
- **Use:** Whitepaper history; optional litepaper citation.

---

# 4. Pillar B — Predictive fit does not automatically preserve physics

### B1. Physics-informed machine learning
- **Citation:** Karniadakis, G. E. et al. (2021), *Physics-informed machine learning*, Nature Reviews Physics 3, 422-440.
- **URL:** https://www.nature.com/articles/s42254-021-00314-5
- **Tier / strength:** Tier I — REVIEW.
- **Supports:** Integration of data and physical laws; physical inductive structure, invariants, hybrid modeling, and the need for robust benchmarking.
- **Does not prove:** That physics-informed approaches are always superior or that Carbon's hard-gate semantics are optimal.
- **Use:** Litepaper umbrella source; whitepaper physics-vs-loss argument.

### B2. Physics-Informed Neural Networks
- **Citation:** Raissi, M., Perdikaris, P., Karniadakis, G. E. (2017/2019), *Physics-informed neural networks*.
- **URL:** https://arxiv.org/abs/1711.10561
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** Explicit incorporation of governing PDE information into learning objectives.
- **Does not prove:** Universal superiority, hard-gate thresholds, or Carbon's score weights.
- **Use:** Whitepaper SciML background.

### B3. Physics-Informed Neural Operator
- **Citation:** Li, Z. et al. (2021), *Physics-Informed Neural Operator for Learning Partial Differential Equations*.
- **URL:** https://arxiv.org/abs/2111.03794
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL.
- **Supports:** Joint use of operator learning and PDE constraints.
- **Does not prove:** Carbon's hierarchy of physics, robustness, and accuracy.
- **Use:** Litepaper and whitepaper.

### B4. Structure-preserving neural networks
- **Citation:** Hernandez, Q. et al. (2021), *Structure-preserving neural networks*, Journal of Computational Physics 426, 109950.
- **URL:** https://doi.org/10.1016/j.jcp.2020.109950
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Learned models can be constructed to respect thermodynamic/geometric structure rather than relying on unconstrained fit.
- **Does not prove:** That the same structure applies to every Carbon Challenge.
- **Use:** Whitepaper physical-structure section.

### B5. Learning physical models that can respect conservation laws
- **Citation:** Hansen, D. et al. (2024), *Learning physical models that can respect conservation laws*, Physica D 457, 133970.
- **URL:** https://doi.org/10.1016/j.physd.2023.133970
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL.
- **Supports:** Conservation can be enforced as a distinct modeling objective and can materially change physical behavior in tested systems.
- **Does not prove:** That conservation is always the correct hard gate or that a specific Carbon tolerance is scientifically justified.
- **Use:** Litepaper/whitepaper support for physical admissibility as distinct from average error.

### B6. Hamiltonian Neural Networks
- **Citation:** Greydanus, S., Dzamba, M., Yosinski, J. (2019), *Hamiltonian Neural Networks*.
- **URL:** https://arxiv.org/abs/1906.01563
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Physical inductive bias and conserved structure can change learned dynamical behavior.
- **Does not prove:** Applicability to arbitrary PDE families.
- **Use:** Whitepaper structure-preserving examples.

---

# 5. Pillar C — Generalization, robustness, uncertainty, and rollout remain open problems

### C1. PDEBench
- **Citation:** Takamoto, M. et al. (2022), *PDEBench: An Extensive Benchmark for Scientific Machine Learning*.
- **URL:** https://arxiv.org/abs/2210.07182
- **Tier / strength:** Tier I — BENCHMARK / PRIMARY EMPIRICAL.
- **Supports:** Need for multi-problem, multi-regime, multi-metric evaluation; heterogeneous performance and difficult failure regimes across SciML methods.
- **Does not prove:** Carbon's exact scoring, hidden-evaluation, or qualification system.
- **Use:** Litepaper and whitepaper.

### C2. Uncertainty quantification in scientific machine learning
- **Citation:** Psaros, A. F. et al. (2023), *Uncertainty quantification in scientific machine learning: Methods, metrics, and comparisons*, Journal of Computational Physics 477, 111902.
- **URL:** https://doi.org/10.1016/j.jcp.2022.111902
- **Tier / strength:** Tier I — REVIEW / EMPIRICAL COMPARISON.
- **Supports:** UQ is a first-class SciML problem; multiple uncertainty methods and metrics have different behavior and limitations.
- **Does not prove:** UQ should be a universal Carbon gate.
- **Use:** Litepaper credibility/generalization argument; whitepaper UQ section.

### C3. Approximate Bayesian Neural Operators
- **Citation:** Magnani, E. et al. (2022), *Approximate Bayesian Neural Operators: Uncertainty Quantification for Parametric PDEs*.
- **URL:** https://arxiv.org/abs/2208.01565
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Neural-operator uncertainty and failure detection are practical deployment concerns.
- **Does not prove:** One uncertainty method is sufficient.
- **Use:** Whitepaper.

### C4. Out-of-domain learning and UQ for PDEs
- **Citation:** Mouli, S. C. et al. (2024), *Using Uncertainty Quantification to Characterize and Improve Out-of-Domain Learning for PDEs*.
- **URL:** https://arxiv.org/abs/2403.10642
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** OOD behavior remains nontrivial for PDE-learning systems; UQ can itself degrade under shift.
- **Does not prove:** Carbon should score arbitrary out-of-envelope cases as in-envelope failures.
- **Use:** Whitepaper generalization and envelope discussion.

### C5. Active operator learning with predictive UQ
- **Citation:** Winovich, N. et al. (2025), *Active operator learning with predictive uncertainty quantification for partial differential equations*.
- **URL:** https://arxiv.org/abs/2503.03178
- **Tier / strength:** Tier III — FRONTIER PRIMARY.
- **Supports:** Predictive uncertainty can guide active sampling and outer-loop optimization in tested operator-learning systems.
- **Does not prove:** Landscape active experiment design at protocol scale.
- **Use:** Landscape research frontier.

---

# 6. Pillar D — Engineering credibility is bounded by context of use

### D1. ASME VVUQ 1-2022
- **Citation:** *Verification, Validation, and Uncertainty Quantification Terminology in Computational Modeling and Simulation*.
- **URL:** https://www.asme.org/codes-standards/find-codes-standards/verification-validation-and-uncertainty-quantification-terminology-in-computational-modeling-and-simulation
- **Tier / strength:** Tier I — STANDARD.
- **Supports:** Formal VVUQ terminology and the principle that evidence should justify model application for a context of use.
- **Does not prove:** Carbon compliance or ASME certification.
- **Use:** Litepaper and whitepaper qualification foundation.

### D2. ASME V&V 40-2018
- **Citation:** *Assessing Credibility of Computational Modeling through Verification and Validation: Application to Medical Devices*.
- **URL:** https://www.asme.org/codes-standards/find-codes-standards/assessing-credibility-of-computational-modeling-through-verification-and-validation-application-to-medical-devices
- **Tier / strength:** Tier I — STANDARD.
- **Supports:** Risk-based credibility tied to model reliance and consequences of incorrect decisions.
- **Does not prove:** Applicability of all medical-device requirements to Carbon products or Carbon compliance.
- **Use:** Whitepaper bounded-credibility logic; cite scope explicitly.

### D3. NASA-STD-7009B
- **Citation:** NASA (2024), *Standard for Models and Simulations*.
- **URL:** https://standards.nasa.gov/standard/nasa/nasa-std-7009
- **Tier / strength:** Tier I — STANDARD / AUTHORITATIVE GUIDANCE.
- **Supports:** Uniform M&S lifecycle practices, defined acceptance criteria, credibility products, V&V/UQ concepts, and communication of model credibility.
- **Does not prove:** NASA endorsement or Carbon compliance.
- **Use:** Litepaper/whitepaper evidence and lifecycle framing.

### D4. NASA-HDBK-7009B
- **Citation:** NASA (2026), *NASA Handbook for Models and Simulations: An Implementation Guide for NASA-STD-7009B*.
- **URL:** https://standards.nasa.gov/standard/NASA/NASA-HDBK-7009
- **Tier / strength:** Tier I — AUTHORITATIVE GUIDANCE.
- **Supports:** Practical guidance for production, use, consumption, and lifecycle credibility of M&S products.
- **Does not prove:** Carbon implementation satisfies NASA guidance.
- **Use:** Whitepaper evidence lifecycle.

### D5. NASA-STD-7009 applied to surrogate/statistical models
- **Citation:** Johnson, K. L. (2020), *Applying NASA-STD-7009 Standard for Models and Simulations to Surrogate and Other Statistical Models*.
- **URL:** https://ntrs.nasa.gov/citations/20200002832
- **Tier / strength:** Tier II — AUTHORITATIVE TECHNICAL APPLICATION.
- **Supports:** NASA credibility-assessment concepts can be meaningfully applied to surrogate/statistical models; intended use and validation domain matter for high-impact surrogate use.
- **Does not prove:** Carbon-specific qualification semantics.
- **Use:** Strong whitepaper bridge from conventional V&V to learned surrogates.

---

# 7. Pillar E — Protected evaluation is necessary under adaptive search

### E1. The reusable holdout
- **Citation:** Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., Roth, A. (2015), *The reusable holdout: Preserving validity in adaptive data analysis*, Science 349(6248), 636-638.
- **URL:** https://pubmed.ncbi.nlm.nih.gov/26250683/
- **Tier / strength:** Tier I — THEORETICAL PRIMARY.
- **Supports:** Naive reuse of evaluation data under adaptive analysis can produce invalid inference; special mechanisms can preserve holdout validity under repeated adaptive interaction.
- **Does not prove:** Carbon's specific hidden-seed or feedback policy is optimal.
- **Use:** Whitepaper justification for protected official evaluation and constrained feedback.

### E2. The Ladder: A Reliable Leaderboard for Machine Learning Competitions
- **Citation:** Blum, A., Hardt, M. (2015), ICML / PMLR 37, 1006-1014.
- **URL:** https://proceedings.mlr.press/v37/blum15.html
- **Tier / strength:** Tier I — THEORETICAL PRIMARY / EMPIRICAL DEMONSTRATION.
- **Supports:** Repeated adaptive leaderboard submissions can overfit a holdout; information-limited leaderboard mechanisms can improve reliability.
- **Does not prove:** Carbon should implement the Ladder algorithm or that a leaderboard alone captures Carbon's scientific problem.
- **Use:** Whitepaper hidden evaluation, feedback throttling, mock/official separation.

### E3. The Generic Holdout
- **Citation:** Nakkiran, P., Blasiok, J. (2018), *The Generic Holdout: Preventing False-Discoveries in Adaptive Data Science*.
- **URL:** https://arxiv.org/abs/1809.05596
- **Tier / strength:** Tier II — THEORETICAL PRIMARY.
- **Supports:** Exploration/test separation plus limited exposure can support adaptive discovery while reducing false discoveries.
- **Does not prove:** Carbon's exact miner feedback schema.
- **Use:** Whitepaper deeper information-control rationale.

**Carbon design connection:** These sources provide direct scientific justification for hiding official realized cases, limiting feedback, structurally separating mock and authoritative paths, and preventing Port A from becoming a high-bandwidth rank oracle.

---

# 8. Pillar F — Open competition can be a scientific search mechanism

### F1. Crowdsourcing biomedical research: leveraging communities as innovation engines
- **Citation:** Saez-Rodriguez, J. et al. (2016), Nature Reviews Genetics 17, 470-486.
- **URL:** https://www.nature.com/articles/nrg.2016.69
- **Tier / strength:** Tier I — REVIEW / CHALLENGE EVIDENCE.
- **Supports:** Scientific Challenges can rigorously compare methods, promote reproducibility, mobilize many independent groups, and create useful community-level knowledge.
- **Does not prove:** Token incentives are necessary or that Carbon's competition will outperform centralized research.
- **Use:** Whitepaper rationale for open scientific search.

### F2. Incentives and Problem Uncertainty in Innovation Contests
- **Citation:** Boudreau, K. J., Lacetera, N., Lakhani, K. R. (2011), Management Science 57(5), 843-863.
- **URL:** https://doi.org/10.1287/mnsc.1110.1322
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL.
- **Supports:** Across 9,661 software contests, adding competitors improved aggregate contest performance for sufficiently uncertain problems because the probability of an extreme-value solution could outweigh rivalry-related effort reduction.
- **Does not prove:** Carbon's optimal miner count, emission curve, or superiority over centralized labs.
- **Use:** Whitepaper economic/scientific search rationale.

### F3. Collaborative DREAM challenge evaluation against blinded experimental data
- **Citation:** Eduati, F. et al. / DREAM community (2015), *Prediction of human population responses to toxic compounds by a collaborative competition*, Nature Biotechnology.
- **URL:** https://www.nature.com/articles/nbt.3299
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Large community competitions can evaluate many submitted methods against experimental data hidden from participants.
- **Does not prove:** General transfer to physics-model training strategies.
- **Use:** Whitepaper example of protected scientific competition.

### F4. Collaboration through competition
- **Citation:** Nature Methods editorial (2014), *Collaboration through competition*.
- **URL:** https://www.nature.com/articles/nmeth.3026
- **Tier / strength:** Tier II — EDITORIAL / SYNTHESIS.
- **Supports:** Competition can generate complementary methods that become more useful when recombined or collaboratively analyzed after evaluation.
- **Does not prove:** Landscape will successfully recombine Carbon strategy intelligence.
- **Use:** Whitepaper discussion of experimental memory and post-competition learning.

**Carbon design connection:** Open competition is most scientifically defensible when the problem is uncertain, the quality of outputs can be evaluated independently, and the system preserves diversity rather than collapsing immediately to one public recipe.

---

# 9. Pillar G — Agentic and autonomous science makes machine-driven search plausible

### G1. An autonomous laboratory for accelerated synthesis
- **Citation:** Szymanski, N. J. et al. (2023), *An autonomous laboratory for the accelerated synthesis of inorganic materials*, Nature 624, 86-91.
- **URL:** https://www.nature.com/articles/s41586-023-06734-w
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL.
- **Supports:** Closed-loop systems can combine prior data, ML, active learning, automated execution, failure analysis, and iterative experiment selection.
- **Does not prove:** Fully autonomous general science or Carbon's MCP miner loop.
- **Use:** Litepaper and whitepaper.

### G2. The rise of self-driving labs
- **Citation:** Abolhasani, M., Kumacheva, E. (2023), *The rise of self-driving labs in chemical and materials sciences*, Nature Synthesis.
- **URL:** https://www.nature.com/articles/s44160-022-00231-0
- **Tier / strength:** Tier I — REVIEW.
- **Supports:** Self-driving laboratories integrate ML, automation, and iterative machine-selected experiments around human-defined objectives.
- **Does not prove:** Carbon's economic mechanism.
- **Use:** Whitepaper autonomous-science context.

### G3. Autonomous experiments using active learning and AI
- **Citation:** Ren, Z. et al. (2023), *Autonomous experiments using active learning and AI*, Nature Reviews Materials.
- **URL:** https://www.nature.com/articles/s41578-023-00588-4
- **Tier / strength:** Tier II — REVIEW.
- **Supports:** Active learning and closed-loop experiment selection can accelerate search, while reproducibility and epistemic/stochastic error remain important.
- **Does not prove:** Carbon's agent loop is mature or production-qualified.
- **Use:** Whitepaper.

### G4. Science acceleration and accessibility with self-driving labs
- **Citation:** Canty, R. B. et al. (2025), Nature Communications 16, 3856.
- **URL:** https://www.nature.com/articles/s41467-025-59231-1
- **Tier / strength:** Tier II — PERSPECTIVE / SYNTHESIS.
- **Supports:** Experiment selection, belief updating, and human-defined objectives as components of self-driving scientific systems.
- **Does not prove:** Carbon's future active-science layer.
- **Use:** Landscape future direction.

---

# 10. Pillar H — Reproducibility and provenance are first-class evidence requirements

### H1. Reproducibility standards for machine learning in the life sciences
- **Citation:** Heil, B. J. et al. (2021), Nature Methods 18, 1132-1135.
- **URL:** https://www.nature.com/articles/s41592-021-01256-7
- **Tier / strength:** Tier I — AUTHORITATIVE COMMUNITY GUIDANCE.
- **Supports:** Reproducibility depends on data, code, dependencies, OS/resource details, random seeds, determinism controls, and awareness that GPU/hardware differences can prevent bit-for-bit identity.
- **Does not prove:** Carbon's execution stack is reproducible or that one deterministic backend is sufficient.
- **Use:** Whitepaper independent retraining, execution identity, and reproducibility section.

### H2. Moving towards reproducible machine learning
- **Citation:** Nature Computational Science editorial (2021), *Moving towards reproducible machine learning*.
- **URL:** https://www.nature.com/articles/s43588-021-00152-6
- **Tier / strength:** Tier II — EDITORIAL / GUIDANCE.
- **Supports:** Reporting of datasets, model choices, training time, randomness, hardware, software versions, code, and model artifacts is important for reproducibility and interpretation beyond accuracy numbers.
- **Does not prove:** Carbon's evidence artifacts are complete.
- **Use:** Whitepaper provenance rationale.

### H3. Model Cards for Model Reporting
- **Citation:** Mitchell, M. et al. (2019), *Model Cards for Model Reporting*, FAT* / ACM.
- **URL:** https://research.google/pubs/model-cards-for-model-reporting/
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY / REPORTING FRAMEWORK.
- **Supports:** Models should be accompanied by structured documentation of intended use, evaluation procedures, performance characteristics, and limitations.
- **Does not prove:** Carbon's Model Card is equivalent to the original framework or is a qualification certificate.
- **Use:** Whitepaper evidence-object lineage; public documentation rationale.

**Carbon design connection:** A validator-retrained strategy is scientifically more valuable when the execution environment, version identities, seeds, resource bounds, model artifact, and evaluation record can be reconstructed or audited to the degree required by the claim.

---

# 11. Pillar I — Experimental memory can guide future experiment selection

### I1. A-Lab / autonomous laboratory evidence
- **See G1.**
- **Supports:** Outcomes from previous experiments can inform subsequent automated choices.

### I2. Self-driving-lab active learning literature
- **See G3-G4.**
- **Supports:** Active learning can select informative subsequent experiments rather than sampling blindly.

### I3. Active operator learning with UQ
- **See C5.**
- **Supports:** In operator-learning settings, predictive uncertainty can guide where additional expensive evaluations are valuable.

**Carbon design connection:** These sources support the *plausibility* of Port C evolving from passive reporting toward experiment-value estimation. They do not prove that Landscape's observational memory is causal or that its proposed experiments will maximize scientific information at protocol scale.

---

# 12. Pillar J — Observational experimental memory is not automatically causal knowledge

### J1. Causality: Models, Reasoning, and Inference
- **Citation:** Pearl, J. (2000/2009), *Causality: Models, Reasoning, and Inference*.
- **URL:** https://bayes.cs.ucla.edu/BOOK-2K/book-toc.html
- **Tier / strength:** Tier I — FOUNDATIONAL THEORY.
- **Supports:** Formal distinction among statistical association, intervention, and causal effects; causal claims require structural assumptions beyond observed correlation.
- **Does not prove:** Which causal graph applies to Carbon's strategy landscape.
- **Use:** Whitepaper Landscape epistemology and causal-claim discipline.

### J2. Causal Inference: What If
- **Citation:** Hernan, M. A., Robins, J. M. (2020), *Causal Inference: What If*.
- **URL:** https://www.hsph.harvard.edu/miguel-hernan/causal-inference-book/
- **Tier / strength:** Tier I — AUTHORITATIVE TEXT / METHODS SYNTHESIS.
- **Supports:** Observational causal inference requires explicit treatment of confounding, treatment assignment, identifiability, and assumptions; randomized interventions provide stronger identification when feasible.
- **Does not prove:** Carbon can identify causal strategy effects from miner-selected data without additional design.
- **Use:** Whitepaper causal intelligence section.

**Required Carbon terminology:**

- **Descriptive intelligence:** what happened.
- **Predictive intelligence:** what is likely under observed data-generating patterns.
- **Causal intelligence:** what would change under intervention.

Landscape may produce the first two without claiming the third. Port C can eventually propose discriminating experiments that convert ambiguous observational relationships into stronger interventional evidence.

---

# 13. Pillar K — Surrogates inside optimization require trust boundaries and truth-model escalation

### K1. Trust region model management in multidisciplinary design optimization
- **Citation:** Alexandrov, N. M. et al. (2000), *Trust region model management in multidisciplinary design optimization*, Journal of Computational and Applied Mathematics 124, 139-154.
- **URL:** https://doi.org/10.1016/S0377-0427(00)00424-6
- **Tier / strength:** Tier I — REVIEW / METHODS SYNTHESIS.
- **Supports:** Approximation models can reduce expensive simulation calls, but optimization requires model-management or trust-region strategies restricting use to regions where approximations are meaningful and coordinating higher-fidelity evaluations.
- **Does not prove:** Carbon's escalation conditions or Product Battery design.
- **Use:** Whitepaper engineering optimization and context-of-use section.

### K2. Recent advances in surrogate-based optimization
- **Citation:** Forrester, A. I. J., Keane, A. J. (2009), *Recent advances in surrogate-based optimization*, Progress in Aerospace Sciences 45, 50-79.
- **URL:** https://doi.org/10.1016/j.paerosci.2008.11.001
- **Tier / strength:** Tier I — REVIEW.
- **Supports:** Surrogate-based aerospace optimization requires validation/refinement against true function evaluations; surrogate optima should not automatically be treated as truth-model optima.
- **Does not prove:** Neural surrogates behave identically to classical response surfaces or that all Carbon products need the same escalation policy.
- **Use:** Litepaper/whitepaper engineering-buyer logic.

### K3. Trust region filter strategy for surrogate optimization
- **Citation:** Liang, L. et al. (2024), *The trust region filter strategy: Survey of a rigorous approach for optimization with surrogate models*, Digital Chemical Engineering 13, 100197.
- **URL:** https://doi.org/10.1016/j.dche.2024.100197
- **Tier / strength:** Tier II — REVIEW.
- **Supports:** Combining efficient surrogate optimization with intermittent truth-model sampling can preserve convergence to the truth-model optimum in the reviewed framework.
- **Does not prove:** Carbon's product path has equivalent mathematical convergence guarantees.
- **Use:** Whitepaper escalation/truth-source analogy.

**Carbon design connection:** This literature gives a direct engineering precedent for Carbon's doctrine: use the fast learned model inside its evidenced context; retain the high-fidelity solver or experiment as truth source and escalation path.

---

# 14. Pillar L — Qualification is a model lifecycle, not a one-time benchmark

### L1. ASME VVUQ 50.1-2025
- **Citation:** *Guide to a Model Life Cycle Approach That Incorporates Verification, Validation, and Uncertainty Quantification*.
- **URL:** https://www.asme.org/codes-standards/find-codes-standards/vvuq501-vvuq-50-1-guide-to-a-model-life-cycle-approach-that-incorporates-verification-validation-and-uncertainty-quantification
- **Tier / strength:** Tier I — STANDARD / GUIDANCE.
- **Supports:** Engineering computational models have iterative lifecycle stages including requirements, development, deployment, use/maintenance, and retirement; V&V activities interact with those stages.
- **Does not prove:** Carbon's requalification triggers or lifecycle policy.
- **Use:** Whitepaper product lifecycle and requalification rationale.

### L2. NASA-STD-7009B / NASA-HDBK-7009B
- **See D3-D4.**
- **Supports:** M&S credibility is maintained and communicated across development and use, not inferred once from a benchmark.

### L3. Applying NASA-STD-7009 to surrogate models
- **See D5.**
- **Supports:** Surrogate/statistical models used in consequential engineering decisions require credibility treatment appropriate to their present use.

### L4. ASME VVUQ 70 — Verification and Validation of Machine Learning Algorithms
- **Status:** Standards activity / watchlist; verify current publication status before citation.
- **URL:** https://www.asme.org/codes-standards/publications-information/verification-validation-uncertainty
- **Tier / strength:** Tier III — STANDARDS WATCHLIST.
- **Supports:** The engineering standards community is explicitly developing ML-specific V&V work.
- **Does not prove:** Carbon compliance with a standard that is not yet final or applicable.
- **Use:** Whitepaper strategic context only, with status caveat.

---

# 15. Pillar M — Bittensor supplies the programmable incentive substrate

### M1. Bittensor building blocks / neurons
- **Citation:** Bittensor official documentation, *Understanding Neurons / Bittensor Building Blocks*.
- **URL:** https://docs.learnbittensor.org/learn/bittensor-building-blocks/
- **Tier / strength:** Tier I — OFFICIAL PROTOCOL DOCUMENTATION.
- **Supports:** Miners produce subnet-specific commodities/services and validators evaluate miner outputs according to subnet-defined logic.
- **Does not prove:** Carbon's scientific scoring is correct or that Bittensor guarantees scientific truth.
- **Use:** Litepaper/whitepaper Bittensor mechanism.

### M2. Yuma Consensus documentation
- **Citation:** Bittensor official documentation, Yuma Consensus.
- **URL:** https://docs.learnbittensor.org/yc3-blog
- **Tier / strength:** Tier I — OFFICIAL PROTOCOL DOCUMENTATION.
- **Supports:** Validator evaluations participate in the consensus/emissions mechanism through which miner performance affects rewards.
- **Does not prove:** Carbon's validator set will be reproducible, collusion-resistant, or economically optimal.
- **Use:** Whitepaper incentive substrate.

**Carbon design connection:** Bittensor supplies competitive selection pressure. Carbon defines the scientific commodity and validator-side measurement. The evaluation contract, not token consensus, remains the source of scientific semantics.

---

# 16. Pillar N — Carbon's system-level thesis must remain falsifiable

The external canon deliberately stops before claiming the Carbon mechanism works.

## 16.1 Core Carbon hypotheses

Carbon should treat the following as research questions with preregistered or otherwise auditable evidence plans where practical:

1. **Physics-weighted objective:** Does physics-weighted competition produce strategies with better robustness and downstream engineering behavior than plausible accuracy-first baselines under matched compute?
2. **Hard-gate value:** Do Challenge-specific binary physics gates remove scientifically unacceptable strategies that would otherwise rank highly on aggregate error?
3. **Independent retraining:** Does validator-controlled retraining reduce irreproducible performance claims relative to checkpoint-submission baselines?
4. **Protected evaluation:** Does hidden procedural evaluation plus constrained feedback reduce adaptive overfitting compared with more exposed leaderboard designs?
5. **Agentic search:** Do autonomous MCP miners discover competitive strategies with less human intervention or greater experimental throughput than manual search?
6. **Open-vs-centralized search:** Under matched budget, does open competition discover stronger or more diverse strategies than a centralized research program?
7. **Diversity:** Does the incentive system preserve enough strategy diversity to avoid premature convergence on locally attractive recipes?
8. **Port A value:** Does noisy/lagged search guidance improve miner sample efficiency without functioning as a rank oracle or collapsing exploration?
9. **Lean-to-product predictiveness:** How predictive are subnet physics/robustness metrics of Product Battery success?
10. **Landscape prediction:** Can experimental memory predict strategy outcomes across nearby physical regimes better than simple leaderboard priors?
11. **Causal strategy intelligence:** Which apparent strategy effects survive deliberate intervention, matching, or other causal-identification procedures?
12. **Port C information gain:** Can Landscape-proposed experiments reduce uncertainty faster than unguided or heuristic experiment allocation?
13. **Product escalation:** Do qualification envelopes and escalation rules reduce surrogate-induced engineering error without destroying the economic value of fast inference?
14. **Qualification validity:** Do Product Battery outcomes predict downstream reliability in actual job-shaped workloads?
15. **Lifecycle:** Which artifact or context changes materially invalidate prior qualification evidence and require requalification?
16. **Economics:** Does the full Carbon workflow produce better decision economics than high-fidelity-only workflows in targeted applications?
17. **Security:** Can miners or validators obtain reward through shortcuts that do not correspond to real scientific improvement?
18. **Experimental memory moat:** Does the accumulated strategy/outcome/qualification history create measurably better search and product-selection performance over time?

## 16.2 Evidence levels Carbon should report

For each major Carbon claim, use explicit maturity labels:

- **MOTIVATED:** supported as a plausible direction by external literature.
- **SPECIFIED:** defined in Carbon's normative design.
- **IMPLEMENTED:** exists in current code.
- **TESTED:** demonstrated by controlled Carbon evidence.
- **REPLICATED:** reproduced independently or across evaluator environments.
- **PRODUCTION-QUALIFIED:** sufficient evidence exists for the stated operational context.

No external paper can move a Carbon-specific claim from MOTIVATED to TESTED.

---

# 17. Whitepaper argument map

The canon should be consumed in this order when drafting the whitepaper.

## Part I — Why the problem exists

### Chapter 1: The learned-physics opportunity
- Pillar A.
- Establish speed and operator-learning potential without overselling reliability.

### Chapter 2: The commercial gap is credible generalization
- Pillars B, C, D.
- Show why predictive fit alone is incomplete and why context-of-use credibility matters.

## Part II — Why Carbon uses an incentivized scientific system

### Chapter 3: Change the optimization target
- Pillars B, C, N.
- Scientific motivation for physics/robustness dimensions; explicit statement that Carbon's exact objective is a protocol hypothesis.

### Chapter 4: Why open competition
- Pillars F and M.
- Scientific-contest evidence plus Bittensor substrate; distinguish evidence for competition from proof of Carbon economics.

### Chapter 5: Why the official exam must remain protected
- Pillar E.
- Adaptive overfitting, hidden realization, constrained feedback, mock/official separation.

### Chapter 6: Agentic mining as automated scientific research
- Pillar G.
- Human-defined objective, machine-driven hypothesis search, independent judge.

## Part III — How competition becomes intelligence

### Chapter 7: Independent retraining and evidence objects
- Pillar H plus D.
- Reproducibility, execution identity, receipts, Model Cards, provenance.

### Chapter 8: Experimental memory and Landscape
- Pillars I and J.
- Descriptive/predictive intelligence first; causal claims only under stronger evidence.

### Chapter 9: From passive learning to active experiment design
- Pillars I, J, G.
- Port C as a mechanism for turning uncertainty into designed experiments.

## Part IV — How intelligence becomes engineering value

### Chapter 10: Surrogates inside engineering workflows
- Pillar K.
- Trust regions, truth-model escalation, optimizer exploitation risk.

### Chapter 11: Qualification and lifecycle credibility
- Pillars D and L.
- Product Candidate Model Card -> Product Battery -> Qualification Record -> requalification lifecycle.

### Chapter 12: Transparency, moat, and evidence boundaries
- Pillars H, J, N.
- Open claims and provenance; protected answer key, recipes, private Landscape state; evidence maturity labels.

## Part V — The scientific research program

### Chapter 13: What Carbon must prove
- Pillar N.
- State falsifiable hypotheses, baselines, ablations, and evidence standards.

### Chapter 14: What success would mean
- Synthesis across all pillars.
- Carbon succeeds only if the incentive/evaluation/evidence loop produces better scientific and engineering decisions than credible alternatives.

---

# 18. Litepaper subset

The litepaper should cite selectively. Recommended Tier-I subset:

1. FNO / Neural Operator / DeepONet — opportunity.
2. Physics-informed ML review + PINO + conservation-aware learning — physics beyond scalar fit.
3. PDEBench + SciML UQ — broader evaluation/generalization.
4. ASME VVUQ 1 + NASA-STD-7009B — context-of-use credibility.
5. Reusable Holdout / Ladder — protected adaptive evaluation, if space allows.
6. DREAM/open-Challenge review — open scientific search, if space allows.
7. A-Lab / self-driving labs — agentic closed-loop science.
8. Bittensor official docs — incentive substrate.
9. Surrogate-based optimization review — truth-model escalation, if product section needs external support.

The litepaper should **not** cite every pillar. The whitepaper is where the full scientific case belongs.

---

# 19. Research watchlist

Maintain a separate Tier-III watchlist for rapidly moving areas:

- Neural-operator OOD and long-horizon rollout stability.
- Physics-aware uncertainty quantification.
- Active operator learning / information-gain acquisition.
- ML-specific engineering V&V standards, especially ASME VVUQ 70.
- Autonomous research agents and closed-loop computational science.
- Mechanism design and adversarial robustness for decentralized evaluation markets.
- Causal discovery from heterogeneous, adaptively selected experimental histories.
- Qualification and monitoring of ML surrogates in safety- or mission-critical engineering.

Frontier sources should not become foundational merely because they are recent.

---

# 20. Publication rules

1. Prefer primary papers, formal standards, and official protocol documentation.
2. Use reviews for synthesis, not to replace the strongest primary source for a precise claim.
3. Never use a citation to imply Carbon's implementation exists because the mechanism is specified.
4. Never use physics-informed literature to imply Carbon's exact 45/30/25 baseline is scientifically established.
5. Never call Model Cards, Product Batteries, or Qualification Records regulatory certificates unless a relevant authority explicitly certifies them.
6. Scope ASME V&V 40 to its medical-device origin when cited.
7. Distinguish current standards from standards activities/watchlists.
8. Label hypothetical examples as illustrative until Carbon has corresponding test evidence.
9. Distinguish descriptive, predictive, and causal Landscape claims.
10. Treat adaptive feedback as an information-security/statistical-validity problem, not merely a product-design choice.
11. Treat high-fidelity solvers/experiments as truth sources or escalation paths where the product context requires them; do not imply a surrogate replaces them universally.
12. Update this canon when a source is superseded, retracted, materially contradicted, or promoted/demoted in evidence tier.

---

# 21. One-paragraph scientific identity

> **Carbon is an incentivized physics-intelligence system.** Open competition generates diverse hypotheses about how physics models should be trained. Protected, validator-controlled evaluation converts those hypotheses into evidence rather than self-reported claims. Structured provenance and Model Cards turn evaluations into experimental memory. Landscape is intended to learn from that history while respecting the distinction between association and causation, and eventually to help allocate experiments where they are most informative. Selected candidates move through a separate, context-of-use qualification path that retains high-fidelity truth sources and escalation boundaries. Bittensor supplies the competitive economic substrate; physics supplies the external constraint; Carbon's own experiments must establish whether the full loop actually produces better methods, better evidence, and better engineering decisions.
