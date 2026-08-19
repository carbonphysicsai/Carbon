# Carbon Scientific Reference Canon v1

**Status:** Research/evidence map for team review  
**Purpose:** Curated external evidence base for Carbon's litepaper, whitepaper, scientific positioning, and future claim audits.  
**Authority:** This document does **not** define Carbon protocol behavior. Current code and normative Carbon specifications remain authoritative for Carbon's implementation and intended mechanics. External references support premises about scientific ML, engineering credibility, autonomous science, and incentive systems; they do not prove Carbon's protocol works.

---

## 1. Scientific thesis this canon supports

Carbon's public scientific case should be built as a chain of independently supportable premises:

1. Learned operators can provide fast surrogate mappings for families of physical systems.
2. Predictive data fit alone does not establish preservation of physical structure, robustness, or trustworthy generalization.
3. Scientific-model credibility is context-dependent and requires verification, validation, provenance, uncertainty/limitations, and evidence appropriate to the intended use.
4. Open scientific search is expensive, parallelizable, and can be independently evaluated when the evaluator controls the scientific contract.
5. Autonomous systems can increasingly generate hypotheses, run or select experiments, interpret outcomes, and iterate.
6. Active learning and autonomous experimentation show that accumulated evidence can be used to choose more informative future experiments.
7. Bittensor provides a programmable economic substrate in which subnet creators define incentive mechanisms, miners produce the target commodity, and validators score miner outputs.

Carbon's synthesis is then:

> **If trustworthy physical generalization is the unresolved commercial target, make physics-surviving generalization the target of an open intelligence market.**

And:

> **Carbon is an incentivized physics-intelligence system: distributed hypothesis generation -> independent scientific evaluation -> structured experimental memory -> controlled learning -> better search and qualification.**

This is a design thesis to be tested, not a conclusion supplied by the literature.

---

## 2. How to use this canon

Each source is tagged with:

- **Tier I — Foundational:** safe to reuse in the litepaper and whitepaper for durable premises.
- **Tier II — Deep canon:** useful for whitepaper depth, design rationale, and specific scientific claims.
- **Tier III — Frontier/watchlist:** recent or narrower evidence; useful for research direction but should not carry foundational public claims alone.

Evidence strength labels:

- **STANDARD / AUTHORITATIVE GUIDANCE** — formal engineering standard or official technical guidance.
- **FOUNDATIONAL PRIMARY** — field-defining or foundational primary research.
- **PRIMARY EMPIRICAL** — primary experimental/computational evidence.
- **REVIEW** — synthesis of a research area.
- **FRONTIER PRIMARY** — recent primary research requiring additional replication/history before foundational use.

For every citation, Carbon should distinguish:

- **Supports:** the external premise the source actually supports.
- **Does not prove:** Carbon-specific claims the source must not be used to imply.

---

# 3. Pillar A — Operator learning makes the opportunity real

### A1. Fourier Neural Operator for Parametric Partial Differential Equations
- **Citation:** Li, Z. et al. (2020), *Fourier Neural Operator for Parametric Partial Differential Equations*.
- **URL:** https://arxiv.org/abs/2010.08895
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** Neural operators can learn mappings associated with families of PDE solutions; FNO demonstrated strong performance on Burgers, Darcy, and Navier-Stokes benchmarks and large inference-speed advantages relative to conventional solvers in the reported settings.
- **Does not prove:** That neural operators are universally accurate, production-ready, or appropriate outside tested regimes; that Carbon's specific evaluation design is correct.
- **Use:** Litepaper opportunity statement; whitepaper operator-learning background.

### A2. Neural Operator: Learning Maps Between Function Spaces
- **Citation:** Kovachki, N. et al. (2021), *Neural Operator: Learning Maps Between Function Spaces*.
- **URL:** https://arxiv.org/abs/2108.08481
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** General neural-operator formulation, function-space mappings, discretization-invariant formulation, universal approximation result, and PDE surrogate use cases.
- **Does not prove:** Generalization outside the learned distribution or commercial reliability.
- **Use:** Litepaper scientific premise; whitepaper architecture context.

### A3. DeepONet
- **Citation:** Lu, L., Jin, P., Karniadakis, G. E. (2019), *DeepONet: Learning nonlinear operators for identifying differential equations based on the universal approximation theorem of operators*.
- **URL:** https://arxiv.org/abs/1910.03193
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** Operator-learning as a distinct learning problem and DeepONet as a practical operator-learning architecture.
- **Does not prove:** That operator approximation error alone is sufficient for engineering trust.
- **Use:** Whitepaper operator-learning history; optional litepaper reference.

---

# 4. Pillar B — Physics is not automatically captured by predictive loss

### B1. Physics-Informed Neural Networks
- **Citation:** Raissi, M., Perdikaris, P., Karniadakis, G. E. (2017), *Physics Informed Deep Learning (Part I): Data-driven Solutions of Nonlinear Partial Differential Equations*.
- **URL:** https://arxiv.org/abs/1711.10561
- **Tier / strength:** Tier I — FOUNDATIONAL PRIMARY.
- **Supports:** Explicit incorporation of governing PDE information into learning objectives; physical laws can be used as prior constraints rather than relying on data fit alone.
- **Does not prove:** That PINNs are always superior, that every physical invariant should be a hard gate, or Carbon's score weights.
- **Use:** Litepaper support for 'physics is a first-class objective'; whitepaper SciML background.

### B2. Physics-Informed Neural Operator
- **Citation:** Li, Z. et al. (2021), *Physics-Informed Neural Operator for Learning Partial Differential Equations*.
- **URL:** https://arxiv.org/abs/2111.03794
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL.
- **Supports:** Combining operator learning with PDE constraints; evidence that data and physics constraints can be jointly useful in operator-learning settings.
- **Does not prove:** Carbon's particular hierarchy of gates, robustness, and accuracy.
- **Use:** Litepaper/whitepaper support for physics-aware operator training.

### B3. Hamiltonian Neural Networks
- **Citation:** Greydanus, S., Dzamba, M., Yosinski, J. (2019), *Hamiltonian Neural Networks*.
- **URL:** https://arxiv.org/abs/1906.01563
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Physical inductive biases and conservation structure can materially affect learned dynamical behavior and generalization in tested systems.
- **Does not prove:** That Hamiltonian structure is appropriate for all Carbon Challenges.
- **Use:** Whitepaper structure-preserving ML section.

### B4. Lagrangian Neural Networks
- **Citation:** Cranmer, M. et al. (2020), *Lagrangian Neural Networks*.
- **URL:** https://arxiv.org/abs/2003.04630
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Encoding physical structure and symmetries/conservation can improve learned physical dynamics in relevant systems.
- **Does not prove:** Universal superiority of structured architectures.
- **Use:** Whitepaper structure-preserving ML section.

### B5. Explicit constraints in Hamiltonian/Lagrangian learning
- **Citation:** Finzi, M., Wang, K. A., Wilson, A. G. (2020), *Simplifying Hamiltonian and Lagrangian Neural Networks via Explicit Constraints*.
- **URL:** https://arxiv.org/abs/2010.13581
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Explicit constraints can materially change accuracy/data efficiency in physics-learning tasks.
- **Does not prove:** That a particular Carbon constraint or gate is scientifically justified.
- **Use:** Whitepaper evidence that structural constraints are not interchangeable with scalar fit metrics.

---

# 5. Pillar C — Generalization, robustness, and holistic evaluation remain open problems

### C1. PDEBench
- **Citation:** Takamoto, M. et al. (2022), *PDEBENCH: An Extensive Benchmark for Scientific Machine Learning*.
- **URL:** https://arxiv.org/abs/2210.07182
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL / BENCHMARK.
- **Supports:** Need for broader, standardized, multi-problem and multi-metric SciML evaluation; current methods show heterogeneous performance and challenging failure regimes.
- **Does not prove:** Carbon's exact scoring design, hidden-evaluation mechanism, or product qualification system.
- **Use:** Litepaper support for richer-than-single-error evaluation; whitepaper benchmarking section.

### C2. Approximate Bayesian Neural Operators
- **Citation:** Magnani, E. et al. (2022), *Approximate Bayesian Neural Operators: Uncertainty Quantification for Parametric PDEs*.
- **URL:** https://arxiv.org/abs/2208.01565
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Neural-operator failure can be difficult to detect and UQ is a relevant deployment problem for PDE surrogates.
- **Does not prove:** That UQ must be a universal Carbon hard gate.
- **Use:** Whitepaper UQ and deployment-risk section.

### C3. Out-of-domain learning and uncertainty for PDE operators
- **Citation:** Mouli, S. C. et al. (2024), *Using Uncertainty Quantification to Characterize and Improve Out-of-Domain Learning for PDEs*.
- **URL:** https://arxiv.org/abs/2403.10642
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Out-of-domain behavior remains nontrivial for neural operators; uncertainty methods can themselves fail under distribution shift; physical constraints and calibrated uncertainty may improve OOD behavior in tested tasks.
- **Does not prove:** That one OOD metric is sufficient or that Carbon should score outside its declared envelope.
- **Use:** Whitepaper generalization/UQ section; supports diagnostic distinction between in-envelope stress and arbitrary OOD claims.

### C4. Active operator learning with predictive UQ
- **Citation:** Winovich, N., Daneker, M., Lu, L., Lin, G. (2025), *Active operator learning with predictive uncertainty quantification for partial differential equations*.
- **URL:** https://arxiv.org/abs/2503.03178
- **Tier / strength:** Tier III — FRONTIER PRIMARY.
- **Supports:** Operator uncertainty can guide active learning and outer-loop optimization in tested systems.
- **Does not prove:** Landscape's future active-experiment design will work at protocol scale.
- **Use:** Whitepaper future research / Landscape active-learning section.

### C5. Structure-aware UQ for neural operators
- **Citation:** Song, H. et al. (2026), *Structure-Aware Epistemic Uncertainty Quantification for Neural Operator PDE Surrogates*.
- **URL:** https://arxiv.org/abs/2603.11052
- **Tier / strength:** Tier III — FRONTIER PRIMARY.
- **Supports:** Current research continues to treat distribution shift and spatially structured uncertainty as practical neural-operator deployment problems.
- **Does not prove:** Mature consensus or production qualification of the proposed method.
- **Use:** Research watchlist only; do not use as sole support for foundational claims.

---

# 6. Pillar D — Engineering credibility is bounded, evidence-backed, and context-of-use dependent

### D1. ASME VVUQ 1 — Terminology in Computational Modeling and Simulation
- **Citation:** ASME VVUQ 1-2022.
- **URL:** https://www.asme.org/codes-standards/find-codes-standards/verification-validation-and-uncertainty-quantification-terminology-in-computational-modeling-and-simulation
- **Tier / strength:** Tier I — STANDARD.
- **Supports:** VVUQ terminology and the principle that evidence should justify application of a computational model for its context of use.
- **Does not prove:** Carbon compliance with ASME standards or that Carbon's Qualification Record is an ASME certification.
- **Use:** Litepaper bounded-claim/context-of-use argument; whitepaper credibility framework.

### D2. ASME V&V 40 — Assessing credibility through V&V
- **Citation:** ASME V&V 40-2018, *Assessing Credibility of Computational Modeling through Verification and Validation: Application to Medical Devices*.
- **URL:** https://www.asme.org/codes-standards/find-codes-standards/assessing-credibility-of-computational-modeling-through-verification-and-validation-application-to-medical-devices
- **Tier / strength:** Tier I — STANDARD.
- **Supports:** Model credibility should be commensurate with reliance on the computational model and the consequences of an incorrect decision; completed V&V evidence supports decision-specific credibility.
- **Does not prove:** That Carbon products meet V&V 40 or medical-device requirements.
- **Use:** Litepaper/whitepaper support for job-shaped qualification and bounded credibility.

### D3. NASA-STD-7009B — Standard for Models and Simulations
- **Citation:** NASA-STD-7009B (2024), *Standard for Models and Simulations*.
- **URL:** https://standards.nasa.gov/standard/nasa/nasa-std-7009
- **Tier / strength:** Tier I — STANDARD / AUTHORITATIVE GUIDANCE.
- **Supports:** Formal model/simulation lifecycle practices, defined acceptance criteria, credibility products, verification/validation/uncertainty concepts, and communication of model credibility.
- **Does not prove:** NASA endorsement of Carbon, Carbon compliance, or universal applicability of NASA-specific requirements.
- **Use:** Litepaper evidence/provenance framing; whitepaper V&V and qualification section.

### D4. NASA-HDBK-7009B — Implementation Guide
- **Citation:** NASA-HDBK-7009B (2026), *NASA Handbook for Models and Simulations: An Implementation Guide for NASA-STD-7009B*.
- **URL:** https://standards.nasa.gov/standard/NASA/NASA-HDBK-7009
- **Tier / strength:** Tier I — AUTHORITATIVE GUIDANCE.
- **Supports:** Practical good practices for production, use, and consumption of modeling/simulation products and lifecycle credibility.
- **Does not prove:** Carbon's implementation satisfies NASA guidance.
- **Use:** Whitepaper credibility/evidence lifecycle; product qualification design rationale.

### D5. Applying NASA-STD-7009 to surrogate models
- **Citation:** NASA NTRS (2020), *Applying NASA-STD-7009 Standard for Models and Simulations to Surrogate and Other Statistical Models*.
- **URL:** https://ntrs.nasa.gov/citations/20200002832
- **Tier / strength:** Tier II — AUTHORITATIVE TECHNICAL APPLICATION.
- **Supports:** NASA credibility-assessment concepts can be meaningfully applied to surrogate/statistical models, including asking whether a model was designed and validated for its present use.
- **Does not prove:** Carbon-specific qualification semantics.
- **Use:** Strong whitepaper bridge from traditional M&S credibility to learned surrogates.

---

# 7. Pillar E — Autonomous and agentic science is becoming technically plausible

### E1. A-Lab autonomous laboratory
- **Citation:** Szymanski, N. J. et al. (2023), *An autonomous laboratory for the accelerated synthesis of inorganic materials*, Nature.
- **URL:** https://www.nature.com/articles/s41586-023-06734-w
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL.
- **Supports:** Closed-loop systems can combine historical data, ML, active learning, automated execution, failure analysis, and iterative experiment selection to accelerate scientific search.
- **Does not prove:** Fully autonomous general science or Carbon's MCP miner loop specifically.
- **Use:** Litepaper/whitepaper support for the broader closed-loop scientific-search paradigm.

### E2. Self-driving laboratories review
- **Citation:** Abolhasani, M., Kumacheva, E. (2023), *The rise of self-driving labs in chemical and materials sciences*, Nature Synthesis.
- **URL:** https://www.nature.com/articles/s44160-022-00231-0
- **Tier / strength:** Tier I — REVIEW.
- **Supports:** Self-driving laboratories integrate machine learning, automation, and iterative machine-selected experiments around user-defined objectives.
- **Does not prove:** Carbon's economic incentive mechanism.
- **Use:** Whitepaper autonomous-science context.

### E3. Autonomous experiments using active learning and AI
- **Citation:** Ren, Z. et al. (2023), *Autonomous experiments using active learning and AI*, Nature Reviews Materials.
- **URL:** https://www.nature.com/articles/s41578-023-00588-4
- **Tier / strength:** Tier II — REVIEW / PERSPECTIVE.
- **Supports:** Autonomous experimentation requires robust operation, reproducibility, and careful handling of epistemic/stochastic error; active learning can guide experiments.
- **Does not prove:** Carbon's Landscape architecture.
- **Use:** Whitepaper agentic science and reproducibility sections.

### E4. The AI Scientist
- **Citation:** Lu, C. et al. (2024), *The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery*.
- **URL:** https://arxiv.org/abs/2408.06292
- **Tier / strength:** Tier II — PRIMARY SYSTEM DEMONSTRATION.
- **Supports:** Frontier agents can perform substantial portions of a computational research loop including hypothesis generation, coding, experimentation, analysis, and iterative research.
- **Does not prove:** Human-equivalent scientific judgment, trustworthy autonomous science, or Carbon's miner efficacy.
- **Use:** Litepaper agentic-miner framing (sparingly); whitepaper agentic search section.

### E5. AutoSciLab
- **Citation:** Desai, S. et al. (2024), *AutoSciLab: A Self-Driving Laboratory For Interpretable Scientific Discovery*.
- **URL:** https://arxiv.org/abs/2412.12347
- **Tier / strength:** Tier III — FRONTIER PRIMARY.
- **Supports:** Automated experiment generation, active experiment selection, latent-structure discovery, and interpretable equation learning can be combined in one closed loop.
- **Does not prove:** General scientific autonomy or Carbon's future active-science layer.
- **Use:** Research frontier / Landscape inspiration.

---

# 8. Pillar F — Experimental selection can itself become an intelligence problem

### F1. A-Lab active-learning loop
- **Source:** Szymanski et al. (2023), A-Lab (E1).
- **Tier / strength:** Tier I — PRIMARY EMPIRICAL.
- **Supports:** Failed experiments can be converted into actionable information that guides subsequent experiment selection.
- **Does not prove:** Landscape causal inference or cross-Challenge transfer.
- **Use:** Litepaper future active-science paragraph; whitepaper Port C rationale.

### F2. AlphaFlow
- **Citation:** *AlphaFlow: autonomous discovery and optimization of multi-step chemistry using a self-driven fluidic lab guided by reinforcement learning* (2023), Nature Communications.
- **URL:** https://www.nature.com/articles/s41467-023-37139-y
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Closed-loop autonomous search can navigate high-dimensional multi-step experimental spaces and optimize user-defined objectives.
- **Does not prove:** Carbon's strategy search or scientific scoring design.
- **Use:** Whitepaper active search / experimental design.

### F3. Active-learning experimental design
- **Citation:** Wang, R. (2021), *Active Learning-Based Optimization of Scientific Experimental Design*.
- **URL:** https://arxiv.org/abs/2112.14811
- **Tier / strength:** Tier II — PRIMARY EMPIRICAL.
- **Supports:** Active learning can be used to prioritize informative scientific experiments rather than exhaustively sampling the experiment space.
- **Does not prove:** Carbon's future information-gain allocation mechanism.
- **Use:** Whitepaper experimental-design theory/motivation.

---

# 9. Pillar G — Bittensor provides a programmable incentive substrate

### G1. Bittensor whitepaper — A Peer-to-Peer Intelligence Market
- **Citation:** Rao, Y., *Bittensor: A Peer-to-Peer Intelligence Market*.
- **URL:** https://bittensor.com/whitepaper
- **Tier / strength:** Tier I — PRIMARY PROTOCOL SOURCE.
- **Supports:** The core idea of a decentralized intelligence market in which network measurement/ranking and incentives reward useful machine intelligence.
- **Does not prove:** Carbon's scientific evaluator, Carbon's miner strategy market, or that a given Carbon incentive design is economically stable.
- **Use:** Litepaper 'Why Bittensor' section; whitepaper economic substrate.

### G2. Incentivizing Intelligence: The Bittensor Approach
- **Citation:** Steeves, J. et al., *Incentivizing Intelligence: The Bittensor Approach*.
- **URL:** https://www.bittensor.com/academia
- **Tier / strength:** Tier I — PRIMARY PROTOCOL SOURCE.
- **Supports:** Bittensor's conceptual separation of intelligence production, peer evaluation/ranking, blockchain incentive distribution, and anti-collusion motivation.
- **Does not prove:** That Carbon's validator economics or anti-free-riding design are solved.
- **Use:** Whitepaper incentive-mechanism background.

### G3. Bittensor Documentation
- **Citation:** Bittensor official documentation.
- **URL:** https://www.bittensor.com/docs
- **Tier / strength:** Tier I — CURRENT OFFICIAL DOCUMENTATION.
- **Supports:** Current product-level role split: subnet creators define incentive mechanisms, miners produce the commodity, validators score miners, stakers back validators.
- **Does not prove:** Scientific validity of any subnet objective.
- **Use:** Litepaper current Bittensor role description; must be rechecked before publication because platform semantics can change.

---

# 10. Canonical claim map for the Carbon litepaper

The litepaper should use citations sparingly. Recommended claim-to-source mapping:

| Litepaper claim | Preferred sources |
|---|---|
| Learned operators can make repeated PDE evaluation much cheaper in demonstrated settings | A1, A2, A3 |
| Physics-aware learning is a real research direction because data fit alone need not encode governing structure | B1, B2, B3/B4 |
| Scientific ML needs broader and more holistic evaluation than one scalar field-error metric | C1 |
| Generalization/OOD/UQ remain active deployment problems for neural operators | C2, C3 |
| Model credibility should be tied to evidence and context of use | D1, D2, D3 |
| Credibility concepts apply to surrogate/statistical models | D5 |
| Closed-loop autonomous scientific search is technically plausible | E1, E2; E4 for computational agents |
| Failed experiments can improve future experiment selection | E1 / F1, F2 |
| Bittensor allows an incentive mechanism to define and reward a subnet commodity | G1, G2, G3 |

### Claims that should cite Carbon specs, not external literature

- Carbon's strategy schema.
- Hard-gate semantics and authoritative zero.
- P0 `0.45 / 0.30 / 0.25` baseline.
- Score Pack semantics.
- hidden seed/draw handling.
- EvaluationReceipt / Model Card / EvaluationCard semantics.
- Landscape four-port authority boundaries.
- Product Battery requirements.
- Qualification Record semantics.
- SPECIFIED / IMPLEMENTED / TESTED / PRODUCTION-QUALIFIED status.

External science can support why those categories matter. It cannot establish what Carbon currently specifies or implements.

---

# 11. Whitepaper scientific-case outline using the canon

A rigorous Carbon whitepaper can make the argument in this order:

1. **Opportunity:** Operator learning makes low-latency learned physics plausible. [A]
2. **Gap:** Data fit alone does not guarantee physical consistency or robust generalization. [B, C]
3. **Commercial implication:** Engineering credibility is bounded and evidence/context-of-use dependent. [D]
4. **Mechanism:** Carbon makes physics-surviving performance the economic optimization target. [Carbon specs + G]
5. **Agentic search:** Humans and autonomous agents compete to discover training strategies. [E + Carbon MCP specs]
6. **Independent evidence:** Validators execute the registered scientific contract; evidence is preserved without leaking the exam. [D + Carbon evidence specs]
7. **Compounding intelligence:** Verified experimental memory feeds controlled decision support. [E, F + Landscape spec]
8. **Active science:** Later, research allocation may target experiments with high information value. [F]
9. **Qualification:** Commercial claims require fresh evidence tied to context of use rather than leaderboard rank. [D + Carbon product specs]
10. **Falsifiability:** Carbon succeeds only if this mechanism produces measurably better robustness/reproducibility/downstream qualification behavior than plausible accuracy-first baselines.

---

# 12. Carbon-level hypotheses the literature does NOT settle

These should become explicit whitepaper research questions rather than citation-backed assertions:

1. Does physics-weighted independent evaluation cause miners to discover strategies with better downstream engineering robustness than accuracy-first competition?
2. How predictive is lean subnet rank of later Product Battery success?
3. Which physical invariants deserve hard-gate status in each Challenge family?
4. How should robustness sampling evolve without making the live exam unstable or gameable?
5. How transferable are training effects across related PDE families, geometries, and regimes?
6. How much qualified backend numerical variability can be tolerated before ranking or gate decisions become unstable?
7. Which Landscape observational effect estimates remain stable after accounting for miner selection, search-policy adaptation, and confounding?
8. Can controlled public priors materially improve miner search efficiency without collapsing exploration diversity or leaking the rank oracle?
9. Do Product Battery failure modes provide useful upstream signals for Challenge design and miner guidance?
10. Which qualification evidence is actually predictive of downstream model reliability in deployed engineering workflows?
11. Does open competition generate enough experiment diversity to outperform an equivalently funded centralized research program?
12. Can validator economics sustain genuinely independent evaluation rather than free-riding at practical scale?

Carbon should be designed to generate evidence about these questions.

---

# 13. Publication rules

1. Prefer primary papers, formal standards, and official documentation over secondary summaries.
2. Do not use a recent frontier paper as sole evidence for a foundational claim.
3. Do not cite papers to imply Carbon-specific thresholds or protocol choices are scientifically proven.
4. Never imply NASA, ASME, or another standards body endorses Carbon merely because Carbon's architecture is informed by similar credibility principles.
5. Distinguish `supports` from `proves` in internal claim audits.
6. Re-check current Bittensor documentation immediately before publication because protocol/product semantics are time-sensitive.
7. For disputed or rapidly evolving scientific claims, cite multiple independent primary sources and state uncertainty.
8. Keep Landscape causal/effect language observational unless identification assumptions and evidence justify stronger wording.
9. Tie public product claims to context of use and the actual qualification evidence, not to subnet rank.
10. Maintain a dated watchlist rather than silently promoting new research into the foundational canon.

---

# 14. Tier III watchlist priorities

Future canon expansion should prioritize primary work on:

- neural-operator OOD/generalization under geometry and parameter shift;
- long-horizon rollout stability and error accumulation;
- conservation-/structure-preserving operator learning;
- calibrated UQ for operator surrogates;
- surrogate exploitation inside inverse design/optimization;
- verification and validation of AI/ML computational models, including ASME's evolving AI/ML VVUQ work;
- reproducibility across accelerator/software backends;
- optimal experimental design and information-gain objectives;
- automated theorem/equation/physics discovery;
- agentic computational research with external evaluation;
- decentralized evaluator economics and free-riding;
- empirical relationships between benchmark performance and real downstream engineering reliability.

---

## Closing doctrine

The canon exists to keep Carbon's public scientific case rigorous:

> **The literature establishes the opportunity and the unsolved problems. Carbon specifies a mechanism intended to attack them. Carbon's own experiments must establish whether that mechanism works.**

That distinction should remain visible in every litepaper, whitepaper, partner document, and investor claim.
