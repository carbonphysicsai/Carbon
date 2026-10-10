# Public anchors, novel exams and contamination audits

Status: **PROPOSED RESEARCH POLICY / NOT IMPLEMENTED / NOT RUN**. Ticket: BENCHMARK-CONTAMINATION-POLICY-01. Authority read at Carbon main **5fbac3099eaae368b23d266cce31ed7409685722**. The active scope is the owner's chat instruction, not a new executable campaign. This document changes no existing Challenge file, scientific contract, custody boundary, score or economic rule.

## Evidence and the problem being controlled

Published reference answers can appear in a miner's datasets or an LLM construction agent's pretraining. Answer exposure is different from protected-exam leakage. The former motivates excluding published instances and testing transfer; the latter remains forbidden. Learning governing equations, published numerical methods, correlations and the declared generator is legitimate. The complete public research environment remains required by [invariant 33](../../../.agent/INVARIANTS.md).

The ML literature supplies useful methods with limited transfer to physics:

| Method and primary source | What the research establishes | Proposed Carbon use and limitation |
|---|---|---|
| Generated variants — [GSM-Symbolic](https://arxiv.org/abs/2410.05229v2) | Symbolic templates enable controlled changes; performance varies between instantiations | Change decision-relevant physical inputs, with equivalence checks. Text renaming or a new seed is insufficient. Mathematical reasoning findings do not quantify physical-model contamination. |
| Fresh, objectively graded questions — [LiveBench, revised version](https://arxiv.org/abs/2406.19314v2) | Recent sources, generated tasks and updates reduce exposure risk; the revised title says contamination-limited | Freeze prospective exam versions and use independent reference measurements. Publication date or unknown model cutoff never proves an unseen case. Do not adopt live post-result redraws. |
| Dynamic challenge collection — [Dynabench](https://aclanthology.org/2021.naacl-main.324/) | Human/model-in-the-loop examples expose weaknesses missed by static tests | Use development/Attacker findings to propose the next version. A model-specific adversarial set cannot secretly replace the common registered exam or establish target prevalence. |
| Planted canary exposure — [Carlini et al.](https://www.usenix.org/conference/usenixsecurity19/presentation/carlini) | Controlled rare strings measure sequence-model memorization and extraction | Optional authorized synthetic text controls for a construction-agent audit. Never plant protected identifiers, corrupt physics labels, or add text-dependent scientific score terms. Absence of a canary does not prove clean data. |
| Ordered-dataset test — [Oren et al.](https://arxiv.org/abs/2310.17623) | A likelihood/permutation procedure can test contamination under exchangeability and model-access assumptions | An auxiliary test only where the interface supplies the required likelihoods and assumptions hold. A deterministic physical predictor normally lacks that interface; numerical closeness is not the theorem's test. |
| Membership detection — [Shi et al.](https://arxiv.org/abs/2310.16789v3) and [Duan et al.](https://arxiv.org/abs/2402.07841) | Text probability methods can indicate exposure; membership tests are sensitive to distribution mismatch | Useful optional provenance clues, with matched controls. Do not infer recipe misconduct from a text detector or equate low error with memorization. |
| Matched new test sets — [Recht et al.](https://arxiv.org/abs/1902.10811v2) | New samples can reduce accuracy through difficulty changes rather than adaptive overfitting | Benchmark-to-variant gaps require difficulty, numerical and model-form controls. A gap alone is not a contamination finding with established cause. |
| Simulation generation and multiple error measures — [PDEBench](https://arxiv.org/abs/2210.07182v7) | Public simulation code/data allow comparison across physical tasks and error diagnostics | Reuse reproducible generation and observable-specific diagnostics. A public simulation dataset is not hidden evidence or customer physical validation. |

The recommendations below are Carbon inferences from those methods and its scientific authority, not measured contamination rates. No universal novelty percentage or performance-drop threshold is supported by these papers.

## A — Anchor use and complete exclusion

Maintain a **versioned catalogue of known published cases**: source URL and revision, case deck, geometry/material/BC/IC/excitation definitions, output convention, rights evidence and known equivalent copies. Include the original benchmark, all published designs in its family, publicly released training examples and discovered derivative decks where legally usable. Track inaccessible or incompletely specified cases as coverage gaps. A finite literature search cannot certify distance from every unknown published instance or every pretraining corpus.

For each registered version, every scored case must be checked against **every complete catalogue entry**, not just the headline benchmark. The literal aspiration “every published case” is enforceable only against this declared, audited catalogue. If an identified source cannot be reconstructed for comparison, the affected support remains unresolved; publication or silence is not a clean-distance receipt.

The anchor's only roles are public reference verification/validation, reproducibility demonstration and separate diagnostic control. It is never a scored hidden question, EVAL/STRESS action or hidden panel component. Changing file names, mesh, units, coordinate origin or seed does not evade exclusion. Public training may include anchor examples with explicit labels and rights; those examples remain excluded from scored questions. Explicitly catalogued anchor controls in an audit stay non-scoring.

Recommended fail-closed generator behavior: if a case is equivalent to a catalogue entry, has incomplete required descriptors, cannot be compared under a pinned extractor, or lacks an approved distance contract, it cannot become score-bearing evidence. No runtime change implements this recommendation in this PR.

## B — Novelty is a physics and decision contract

Use a canonical descriptor extracted from the **physical case**, not a filename, random seed, embedding of its prose or mesh node ordering. Freeze units, coordinate gauges, nondimensionalization, equivalent transformations, descriptor extraction, integration domain and numerical extraction error. Compare two meshes by the represented geometry, not discretization identity.

Retain a vector of distances; a scalar summary alone can hide a copied geometry behind a changed nuisance variable. Proposed general form:

- geometry distance: norm of normalized physical geometry difference, minimized over registered equivalences;
- condition distance: normalized differences of material/excitation/operating descriptors, after similarity reductions;
- nearest-source distance: the component distances and the jointly defined distance to **each** catalogue entry, with the minimum retained internally;
- diagnostic response transfer: error and decision agreement of public-answer retrieval, correlations and interpolators on independent public development variants.

Weights, normalizers, exact equivalence group and “far enough” acceptance predicate are **HUMAN_INPUT**, scientifically reviewed per family. Mathematical constants in definitions are definitions, not measured costs or adopted scientific thresholds. No distance value in this document is a production limit.

### Backward-facing step

Use step height H only as the coordinate gauge. Proposed geometry descriptor is the normalized upper/lower wall contour in x/H and y/H on a fixed physical comparison window, plus expansion ratio, ramp length/H, edge radius/H and any allowed insert profile. A normalized integral of absolute wall-profile differences gives a computable geometry distance; its integration window, handling of discontinuities and normalization are HUMAN_INPUT. A changed mesh of the same contour has zero physical distance by definition.

Condition descriptor: the explicitly named Reynolds number, Mach number, inlet displacement/momentum thickness relative to H, normalized velocity/turbulence profiles, wall condition and source/observation conventions. Use log ratios for positive scalar similarity parameters and normalized profile norms; scales and floors remain HUMAN_INPUT. Store Reynolds-number definitions separately: identical numbers under different reference velocities are not automatically identical cases.

Canonicalize dimensional scaling at constant geometry ratios, Reynolds/Mach and normalized inlet/material conditions. A physically equivalent scale change cannot count as novelty. Do not treat a change of turbulence closure as a novel physical input: it changes reference policy. The catalogue includes experimental, tutorial and derivative numerical versions with their actual BC differences. The [NASA/TMBWG deck](https://github.com/tmbwg/turbmodels/blob/20a39f549dbff988a6accc421ac84dafc4487695/backstep_val.html) explicitly warns about Reynolds conventions and pressure-coefficient shifts.

Require geometry novelty for the proposed **geometry-design** family; changing only speed while keeping the published wall contour is insufficient for that family. Condition novelty may also be needed if anchor-answer transfer remains strong. Only a public development panel can support that acceptance rule. Distance must stay inside the reference's justified envelope: novelty is not permission to jump into unsupported compressibility, transition or arbitrary three-dimensional physics.

### Original 3D periodic metagrating

Represent the silicon mask as a periodic occupancy field chi(u,v) in normalized cell coordinates, with periods Px/lambda and Py/lambda, thickness t/lambda, substrate/device permittivities, incident wavevector, polarization and output-order convention. Use an integrated absolute mask difference minimized over physically equivalent periodic translations and **only** validated polarization/coordinate symmetries. Keep the material and condition distances separate. A reflection that exchanges the desired diffraction order is not automatically an equivalence.

Exclude the [testbed's entire published device family](https://github.com/NanoComp/photonics-opt-testbed/blob/a06518872de6ec82bb4511190e544211539f55f1/Metagrating3D/README.md), including interpolated masks and stripe encodings, not just one device. Resampling a mask produces no novelty. Uniformly scaling geometry and wavelength in a nondispersive model preserves dimensionless Maxwell inputs and is excluded. Numerical rounding differences below extractor uncertainty cannot make a new case.

For a **pattern-design** Challenge require mask novelty, even if angle or thickness changed. Preserve the full periodic x/y, finite-thickness 3D electromagnetic job. A one-dimensional stripe restriction or effective-index model is a competitor/narrower scope, not an implicit replacement. Phase-gauge changes must transform outputs correctly and cannot masquerade as different efficiencies.

### Distance is necessary; useful transfer is tested separately

A large input distance can leave the same action optimal; a small change near a boundary can flip feasibility. A distance threshold therefore cannot by itself prove that remembering an answer is useless.

Before exam qualification, run an **independent public development** novelty/shortcut panel. Include catalogue-answer retrieval, nearest-neighbor response transfer, applicable published correlations, a cached response surface and the realistic solver-alone competitor. Match action sets, mandatory limits, output extraction and budgets. Report feasibility disagreements, best verified feasible picks, buyer-unit opportunity loss where defined, unresolved references and failures. Hold out complete designs/panels rather than random rows from the same design.

The acceptance question is whether benchmark-answer recall alone can reliably satisfy the decision contract over the proposed strata. It is **not** whether every conceivable formula fails: useful physics and a fast accurate formula should be allowed to win. Minimum decision diversity, sample adequacy, accepted shortcut agreement and uncertainty remain HUMAN_INPUT. A shortcut that makes the same admissible choices defeats the incremental-value hypothesis; it does not disqualify its miner.

No newly generated hidden cases are read by this research. Future authorized operators perform protected prequalification under custody, retain internal evidence and release only allow-listed summaries.

## P, Q and w; registration and refresh

State the target P explicitly, including any approved benchmark-neighborhood exclusion. If the intended population contains those neighborhoods but Q rejects them, restrict the claim or provide a valid sampling/weighting treatment; zero sampling support cannot be repaired by an arbitrary weight. Sampling feasibility and rejection rates belong in adequacy, not a favorable unreported selection step. Statistical weights w are separately registered and cannot be inferred from source popularity or distance.

Exclusions and distance checks act on exam **construction**, never on miner identity or observed performance. Freeze the catalogue version, descriptor/extractor, exclusion predicate, generator, P/Q/w, reference and measurement identities before candidate outcomes. No retry-until-the-model-wins and no removal of hard/reference-failed cases without typed accounting. Dynamic refresh is a prospectively qualified new version; preserve historical results and exposure history. New discoveries of source overlap trigger review of the affected version and explicit remediation, not silent rescore.

A continuous generator may make accidental exact overlap unlikely. That is not evidence of a passed distance, bounded equivalence or semantic decontamination test.

## C — Published science is the cheap competition

Treat anchor constants, published formulas, similarity laws, cached simulations, response surfaces, coarse solvers and direct solver-based optimizers as admitted competitors where the output and action contracts allow them. Include their validity domains and uncertainty; do not make them look weak by omitting their calibration data or giving Carbon free construction. Charge new bank generation, training/tuning, screening, retries and final verification, with a separately disclosed amortized scenario.

For step flow, include loss/reattachment correlations only within their sourced domains, NASA-answer retrieval, response maps and coarse RANS/adjoint routes. For the metagrating, include the analytic grating relation, existing mask libraries, converged RCWA and direct gradient/adjoint search. A constant published efficiency is not a general predictor, while RCWA can be an excellent legitimate full predictor. Follow [equal-budget realism](../equal-budget-realism/SPECIFICATION.md); do not equate lower inference error with greater design gain.

## D — Claims bounded to actual evidence

| Evidence state | Claim permitted after that evidence exists | Claim not established |
|---|---|---|
| This research and published source reports | “An open published anchor and a proposed variant family have been identified; Carbon reproduction and novelty qualification are NOT_RUN.” | “Carbon validated the solver”, “contamination-free”, “launch-ready”, or a measured gain |
| Carbon reproduces numerical anchor observables under accepted limits | Named numerical code agreement, with exact settings, discrepancy and known limits | Physical validation, formal reference tier earned, or agreement for all variants |
| Carbon agrees with independent published experimental measurements | Agreement for those measured observables, case, conditions and uncertainty; distinguish calibration from held-out evidence | “Validated for your design”, unmeasured stress/flux quantities, or broad population reliability |
| Variant reference/measurement adequacy established | Reference-relative accuracy and decisions for the exact qualified family and evidence contract | Hardware validity for a customer geometry or higher credibility tier without its separate witnesses |
| Novelty and audit controls implemented and evaluated | The controls applied to the versioned catalogue and evidence described | Proof of absence of all pretraining exposure, all memorization or all unknown published duplicates |

Use [reference credibility](../../../docs/development/challenge_pipeline/round1/reference-credibility.md) and [deliverable framework](../deliverable-framework/FRAMEWORK.md). The formal buyer-tool Tier 2 additionally requires matched task witnesses; the source search alone earns none. Include adverse outcomes in the dossier rather than reporting only a passed anchor.

## E — A diagnostic audit, with controlled interpretation

Proposed authorized audit sequence, **not executed here**:

1. Freeze the candidate artifact, interface, reference identities, public control set, variant strata, resource limits, error scales, statistics and disclosure class. Maintain separate non-scoring anchor controls and variant evidence. Supplemental audits do not change the common mandatory official pack.
2. Establish reference and measurement adequacy before interpreting a predictor. Check grid/time or harmonic convergence, boundary/domain sensitivity, observable normalization and reference uncertainty. A disputed reference produces UNRESOLVED, not a candidate failure.
3. Evaluate errors separately on anchors, aligned-equivalent controls, novel public variants and independent design-held-out panels. Use accepted physical scales, not a division by near-zero error. Compute an anchor advantage and variation-response consistency, with sample sizes, denominators and uncertainty. A corrected unit/phase/coordinate transformation should preserve the appropriate prediction.
4. Include positive controls (explicit anchor lookup or synthetic authorized memorizer) and negative controls (a numerical physics route with no answer table, plus ordinary approximations). Match variant difficulty/parameter coverage where possible. Test baseline behavior and model-form discrepancy as alternative explanations. Positive controls are diagnostics, never LIVE scientific evidence.
5. An anomalously sharp anchor advantage, repeated anchor values despite materially changed inputs, or improper coordinate responses prompts investigation. Declare test multiplicity and a prospectively accepted false-alarm treatment; thresholds and power requirements are HUMAN_INPUT. Failure to detect an anomaly is not proof of clean training.
6. If the submitted interface exposes language probabilities or authorized recipe provenance, optional likelihood/canary tests can supplement the physical audit. If unavailable, record NOT_APPLICABLE rather than fabricate token evidence. Authorized custodians, not this research agent, investigate protected leakage.
7. Record outcome as insufficient evidence, shortcut/transfer finding, reference failure, or independently corroborated exposure finding, with confounders and human disposition. A scientifically useful published method is not misconduct. Existing scoring gates still govern physical failures; no unregistered suspicion penalty, candidate-specific redraw or retroactive change.
8. Retain adverse results, exact artifact/reference provenance and permitted aggregates in the dossier. Protected seeds, case IDs, nearest-source fingerprints, detailed hidden distance vectors and reconstruction-sensitive reference outputs stay internal; release only reviewed, allow-listed summaries.

Public policy and metric definitions can be transparent. The realized hidden cases and their distances cannot. An auditor report must distinguish method design, implementation, test controls and actual protected evidence.

## Existing authority crosswalk and gaps

| Proposed point | Existing authority | Reuse and remaining gap |
|---|---|---|
| A: no published scored anchors | [INVARIANTS](../../../.agent/INVARIANTS.md) 16, 17; [Instance Distribution](../../../Design_Specs/Challenge_Instance_Distribution.md) §§5, 11 | Semantic decontamination and duplicate policy already required. A benchmark catalogue, physical-equivalence extractor and explicit anchor exclusion need registration/implementation; not shown implemented by this research. |
| B: private variants and distance | Invariants 1–4, 8, 16–17, 24; [Data Management](../../../Design_Specs/Data_Management.md) §§2, 5–7 | Keep existing entropy/custody/version separation. Seed separation is explicitly insufficient. Family metric, supported envelope, thresholds, P/Q/w and sampling-bias evidence are gaps. |
| C: fair cheap baselines | Invariants 18, 25, 29, 33; [equal-budget specification](../equal-budget-realism/SPECIFICATION.md) | Preserve full miner kit and equal admissibility/budget accounting. Correlation applicability, comparator adapter and prospective novelty/value evidence need work. |
| D: limited validation claims | Invariants 19–20, 26–27, 31–32; reference-credibility tiers and deliverable framework | Reference-relative versus physical claims remain separate. No new buyer/physical qualification or paid traction is demonstrated. |
| E: audit without score invention | Invariants 7, 10–12, 19–20, 24–25; Data Management §5 | Supplemental audits are separately identified and cannot alter historical scores. Statistical controls, access-dependent methods, audit implementation and lawful human disposition are missing. |
| Dossier evidence | [Generator Validation](../../../Design_Specs/Generator_Validation.md) D7, D11 and stop-ship discussion | The document identifies truth/secrecy/decontamination requirements; its v2.1 dependence amendment is a ratification proposal. Do not treat that proposal or this policy as a new runtime gate. |

KEEP existing custody, independent grade and immutable contract rules; propose WRAP with benchmark-specific evidence. **NEW_OWNER_DECISION_REQUIRED** for policy adoption and scientific thresholds; catalogue/extractor/audit tooling remains unimplemented. Research is complete as a recommendation while those values remain explicit and fail closed. Packets owns the population, question law and panel specification; Data Collection owns future authorized public measurements. No hidden data, solver execution, spend, launch or commercial commitments are part of this work.
