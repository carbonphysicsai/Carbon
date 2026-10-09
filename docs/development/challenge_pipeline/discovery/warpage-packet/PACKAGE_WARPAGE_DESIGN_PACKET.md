# D016 package warpage — common customer design packet

Ticket: `CHALLENGE-WARPAGE-PACKET-01`. Lineage: [#928](https://github.com/carbonphysicsai/Carbon/pull/928), D016, source head `f6e5eea975fc19bf84aa65dc6e3093624c000860`. Format: [COMMON_DESIGN_PACKET_V1](../../COMMON_DESIGN_PACKET_V1.md). Status: **research specification; customer-specific acceptance and dispatch HOLD**.

Sources S1–S12 and their exact applicability appear in [source-evidence.md](source-evidence.md). Proposed numerical counts, resources and costs are **ASSUMPTION low/base/high** in [feasibility-panel.json](feasibility-panel.json). Sourced numbers are contextual observations with degenerate low/base/high ranges; they are not uncertainty bounds. `HUMAN_INPUT` means an identified owner must supply or approve the value before the affected behaviour can proceed.

## 1. Engineering job

**Decision maker:** package mechanical/design engineer at an outsourced semiconductor assembly/test provider or advanced-package design organisation, with reliability and thermal owners approving constraints. Amkor identifies Nathan Whitchurch in this role and describes a coupled mechanical/thermal package study [S1](source-evidence.md#buyer-workflow-and-architecture). ASE independently describes customer-input stress/warpage simulation [S2](source-evidence.md#buyer-workflow-and-architecture). These independently originating customer-side sources satisfy role/workflow evidence. They establish neither a Carbon buyer nor validation of the proposed commercial savings.

**Physical decision:** select an approved underfill material and underfill/solder-stack geometry for a full three-dimensional package. Candidate actions may change supplier-approved underfill option, gap/standoff and permitted fillet/solder-stack dimensions. Other architecture/material changes require prospective scope approval. The proposed workflow is customer drawings/process conditions → qualified simulation of each action's full history → reject any action violating a mandatory limit → compare admissible actions → buyer chooses → normal customer verification and release.

**Proposed objective:** minimise the buyer-approved worst-case warpage criterion among feasible actions. Whether the real buyer instead minimises package cost, thermal penalty or risk is `HUMAN_INPUT` from the buyer design owner; no scalar preference weights are invented. Hard conditions include applicable external and internal interconnect warpage, die/interface/solder stress or strain criteria, package/process and service temperature limits, manufacturing geometry constraints and reference applicability across all required conditions.

Wrong choices can cause assembly rework or redesign. A numerical loss, frequency of decisions, engineer time saved and willingness to pay are unmeasured. No yield, safety, reliability lifetime or market-size claim is made. The scope remains the original **full 3D job over complete thermal history**; planar beam/laminate models remain baselines and controls.

`OPEN / HUMAN_INPUT`: buyer acceptance contract, geometry rights, objective, limits, real repeat cadence and present elapsed decision latency. Owner: customer packaging/reliability/thermal leads. **Held closed:** deployable advice, customer acceptance labels and value claims.

## 2. Physical system

**Architecture grammar, proposed:** multiple silicon dies/chiplets on an approved fan-out/interposer/substrate stack; Cu pillars/bumps and solder joints embedded in underfill; encapsulant and routing layers; external balls and board interface where assembly constraints require them; lid/TIM/supports where they influence package deformation or the graded temperature. Preserve full spatial asymmetry and local joint/interface regions. A quarter-symmetry model is only admissible when every geometry, load, boundary and graded observable shares that symmetry and an independent full-domain check establishes equivalence.

S1 supplies a published large-body ASIC/HBM architecture. S7 supplies a smaller, independently described fabrication-history research vehicle. They are separate geometry anchors, not endpoints of an approved interpolation family. The [material/geometry ledger](source-evidence.md#research-geometry-and-strongest-low-cost-approaches) supplies source-bound dimensions and temperature-dependent property observations. **Approved customer dimensions and material ranges are `HUMAN_INPUT`**. Independent min/max mixing of those vehicles would invent a package.

**Material contract:** named supplier/lot or independently characterised material identity; temperature-dependent anisotropic elasticity/CTE where required; thermal conductivity, heat capacity and density for thermal evolution; calibrated solder plasticity/creep and transition treatment; underfill/encapsulant cure, shrinkage and relaxation; interface/contact/cohesive laws when the buyer's grade depends on them. Supplier DMA storage modulus is a characterisation anchor, not automatically an approved static elastic modulus. Material curves, fitting protocol, uncertainty and temperature/time validity must be pinned together.

**Causal history:** manufacture/assembly steps, material activation, cure and stress-free/reference state, cooling, board attachment/reflow, subsequent cooling and any buyer-required power-on/service history. Preserve residual state between steps. Prescribed spatial temperature fields are causal inputs only when their originating model/measurement is rights-cleared and adequate; they do not constitute a solved thermal prediction. If warpage changes TIM thermal resistance enough to affect the temperature grade, the coupling iteration and stopping criterion require qualification.

**Initial/boundary conditions:** assembly support/contact, board/lid constraints, temperature field or heat/convection boundary conditions, initial residual stress and moisture conditioning. Every condition, timestamp, dwell/ramp, initial state and full horizon is `HUMAN_INPUT`. Units must be pinned coherently in the solver deck and exported in the measurement contract.

**Limits ledger:** S4 supplies conditional external BGA/FBGA warpage criteria; S5 supplies supplier reflow capability and cure guidance. Neither supplies this package's complete acceptance contract. Applicable warpage, internal-joint, stress/strain and operating temperature limits all remain `HUMAN_INPUT`. A fracture toughness is not a stress allowance. A measured temperature or material transition is not a maximum permitted operating temperature.

Omitted moisture/delamination, fracture propagation or long-term fatigue cannot be hidden if the customer's acceptance depends on them. Owner-approved evidence may establish an omission's irrelevance; otherwise the candidate remains on HOLD. This packet does not make an elastic idealisation adequate by reducing the job.

## 3. Population P, Q and w

**Intended population P:** rights-cleared customer package variants and approved underfill/solder-stack decisions under manufacturing/process/service conditions for which the complete reference and measurements are qualified. Geometry family, material/process variation law, correlations, support, prevalence and exclusions are `HUMAN_INPUT` from the science owner and customer. A source-bound material table or bounded geometry box does not define P.

**Proposal Q:** prospective public feasibility exploration may concentrate on thermal-mismatch extremes, changing support/contact regimes, hot/cold spatial gradients and actions near each approved limit. These are diagnostic proposals, not claims about deployment frequency. The assumed panel strata are distinct complete-history classes to be chosen by the owners; they are **not three temperature samples from one history**. Exact support, draws and any adaptive boundary-search rule must be precommitted before reference access.

**Evidence weighting w:** owner-approved purpose-specific weighting for independent confirmation, stratified reporting and any subsequent score. No importance correction is invented without the law and support relationship. Early diagnostics report raw counts and separate strata. They do not produce a deployment-weighted scalar.

**Independent observation:** a complete package/design-history instance, with customer variant/process batch dependencies registered. Mesh refinements, timestamps, repeated seeds and FE nodes are correlated measurements, not additional independent customers or histories. Freeze independence clusters and held-out whole variants/histories before uncertainty estimation.

`OPEN / HUMAN_INPUT`: P, Q, w, strata, sampling/independence law and data rights. Owner: scientific population owner with customer process owner. **Held closed:** representative-population claims, official evidence weighting and production scoring.

## 4. Case contract

A case contains versioned geometry and named regions; approved action; complete thermal/process history and preserved material state; material-law pins; initial/boundary conditions; measurement masks/coordinates; required limit set with applicability; reference recipe and resource allowance. The input must distinguish thermal histories from snapshots.

Valid geometry requires manufacturable positive dimensions, non-intersecting intended solids, explicit joints/interfaces/supports and consistent material assignments. Manufacturing minima/maxima and validity tolerances are `HUMAN_INPUT`. An invalid case is a case-construction failure. A valid design that violates a hard physical limit is an infeasible action; it must remain available for decision testing.

Canonical case identity should bind all causal and reference-relevant inputs plus versions. The exact serialisation/hash law is `HUMAN_INPUT`; no new runtime identity/schema is implemented. Public projections contain the released grammar, laws, approved public examples and own-seed practice inputs. Protected cases, official seeds, draw identities, private customer geometry and witness outputs remain operator-side. Public metadata must not permit reconstruction of protected instances.

`OPEN / HUMAN_INPUT`: case grammar, canonical representation, validity criteria, identities and disclosure allow-list. Owner: case-authoring/science and rights owners. **Held closed:** official case generation, protected evaluation and research-data release.

## 5. Reference policy

**Proposed open route:** reuse the inspected f08 CalculiX release 2.23 build pattern [S13](source-evidence.md#pinned-f08-package-reuse), using openly licensed dependencies and avoiding an assumed proprietary linear-solver entitlement [S10](source-evidence.md#open-reference-route-and-cost-anchor). Existing source/build pins are evidence of a reusable package recipe, not a warpage run identity. Freeze the warpage compiler/dependency manifest, built container digest, geometry/mesh/material/deck hashes and postprocessor identity; those new execution pins remain `HUMAN_INPUT`. No container or solver was built or run.

**f08 reuse map, inspected at `0f12834226f65cdb317e7407e1e83e68c135801b`:**

| Disposition | Existing artifact | What transfers / what does not |
| --- | --- | --- |
| KEEP | `scripts/dev/reference_packages/calculix/{Dockerfile,build.sh,sources.lock.json}` | ccx 2.23 source/checksum, pinned Debian snapshot and serial CPU build/environment patterns; reverify license/build and actual run digest. Not material adequacy or a warpage grant. |
| WRAP | `f08_deck.py`'s full-3D Gmsh mesh, named-region and retained-output patterns | New multilayer/asymmetric grammar, units, material regions and observers required; do not run the existing mesher here. |
| DO NOT REUSE AS TRUTH | f08's metal cantilever modal/static deck and projection observer | No package multilayer thermal expansion, calibrated underfill cure/relaxation, solder phase/joint formation or retained residual process state. Modal truncation evidence proves none of these. |
| GAP / HOLD | New process/material implementation and witnesses | Feature proofs for coupled/prescribed temperatures, orthotropic expansion, activation, cure/creep/plasticity, molten solder and state-continuous restart before full-task feasibility. |

The pinned source lock includes ccx archive SHA-256 `9c88385c10fb04f5dc6c4e98027a51bebdd8aee3920e05190d6c1dd08357d6e7` and single-thread settings. The ccx manual's expansion convention must be matched to supplied temperature-dependent material data, not inferred from a CTE scalar. Existing f08 capabilities are a KEEP/WRAP opportunity; they neither qualify this reference nor authorize package-owner changes. The planned feature proofs remain unexecuted.

The route is full-domain 3D solid thermal/structural FE with the complete ordered process history and state. Temperature-dependent thermoelasticity is an initial control. Supported time-dependent plastic/creep procedures and calibrated material implementations are necessary wherever they change the full-history grade. Cure kinetics, shrinkage, viscoelastic relaxation and molten-solder treatment are not proven merely by CalculiX's capability list. If the chosen laws cannot be represented and independently checked, the open route fails the hard filter; the reference job stays intact.

**Exact-output route, proposed:** thermal steps or approved mapped fields → structural/history steps → native nodal displacement and temperature plus integration-point coordinates, stress and strain → deterministic measurement transform in §6. Request needed history-dependent quantities from the start. Check step/time and material-state continuity, coordinate conventions and strain/stress measure for each formulation. Do not replace selected integration-point quantities with smoothed FRD nodal peaks; verify the procedure actually evolves creep [S11](source-evidence.md#open-reference-route-and-cost-anchor).

**Controls:** free thermal-expansion body, homogeneous bonded laminate, isothermal no-load case, rigid-motion/constraint checks and matched closed-form beam/laminate cases where applicable. Refine spatial mesh and history timesteps independently; check heat balance, force/moment consistency and solver convergence in appropriate units and normalisations. Mandatory tolerances, cutbacks and resource limits are `HUMAN_INPUT`, not successful-solve heuristics. An unconverged singular corner stress cannot acquire a finite admissibility limit through smoothing.

Matched buyer-tool witnesses must be generated outside the producer's custody, from separate non-hidden task draws or rights-cleared retired/public cases with verified release provenance. Selection is frozen before comparison, enriched strata are reported as Q, and all selected failures/disagreements are retained. Sealed results retain their original reference identity; any adequacy revision applies prospectively.

**Credibility:** earned `NOT_DEMONSTRATED`. Proposed target is **Tier 2** under the [reference credibility contract](../../round1/reference-credibility.md): independent published benchmark evidence **and** matched-task buyer-tool witnesses, with pointwise and decision agreement under approved unit-bearing limits. Tier 1 requires exact customer-tool/deck/settings identity; CalculiX does not earn it by resembling ANSYS. Tier 3 requires calibrated independent experiments for the claimed observables. Self-convergence cannot earn independent credibility. Hardware reliability/release claims require additional matched physical evidence.

**Failure/cost policy:** distinguish invalid case, reference inadequate/unconverged, missing witness, infrastructure failure and genuine infeasible design. Missing or failed reference evidence never becomes candidate failure or `NONE_FEASIBLE`. Charge actual setup, all attempts, refinements, independent witness generation, fitting and verification; record complete-case wall/CPU time and peak memory. No uncharged buyer licence assumption is treated as confirmed.

`OPEN / HUMAN_INPUT`: exact deck/container, calibrated laws, numerical/measurement tolerances, witness rights, resource approval and adequacy. Owner: reference/science and compute owners. **Held closed:** graded reference bank and feasibility dispatch.

## 6. Output and measurement contract

The proposed reference exports:

| Observable | Shape and units | Qualification obligation |
| --- | --- | --- |
| Displacement and package surface shape | Global vector field over named nodes and complete registered history; mm in the public export | Bind undeformed/deformed coordinates, orientation, rigid-motion treatment and surface mask |
| External package warpage | Signed scalar and magnitude by condition, plus surface/diagonal profiles; mm | Use the chosen applicable measurement definition; preserve twist/asymmetry and sign conventions |
| Stress and strain | Named material/region integration-point tensor histories; MPa and dimensionless strain | Pin Cauchy/other stress and total/mechanical/inelastic strain measures; approved aggregation, corner/interface treatment and applicability |
| Temperature | Named-region field/history and approved maxima; °C with solver conversion fixed | Distinguish supplied temperature from predicted temperature; preserve time/gradient and junction/assembly region |
| Admissibility/action outcome | Per-action typed status and individual hard-limit margins | Include reference uncertainty and missing-data status before feasible ranking |

Source standards inform the transform; they do not qualify a specific postprocessor. A buyer may require a different zone or assembly metric. Spatial registration, interpolation, temporal extremum capture, independent witness comparability and uncertainty bounds need approved evidence. Numerical-to-experiment temperature/warpage agreement does not validate local stress by implication.

Mandatory failure precedes ranking: all registered hard limits must be met in every required condition/stratum. A soft error, fast runtime or high excitement cannot compensate for failure. Normalisation, uncertainty margins, near-infeasible-band width, scoring and target accuracy are `HUMAN_INPUT` from the measurement/science owner.

**Question-law sketch.** One question consists of a buyer-supported complete package context, mandatory full histories, a requirement draw within approved support, and a finite set of approved underfill/solder-stack actions. Recommend **k = 4 / 8 / 12 questions per window** (ASSUMPTION low/base/high; base 8), subject to Test Lead power and owner law approval. k is not an action count, timestep count or number of independent physical solves. The first diagnostic pool has **M = 10 / 10 / 10 proposed actions**; the actual question menu/law remains `HUMAN_INPUT`. Choose the objective-best feasible action, or `NONE_FEASIBLE` when adequate reference evidence shows every action fails at least one mandatory limit. No redraw to remove that buyer answer. Ties and objective uncertainty require a precommitted policy. A model may abstain/request approved verification when evidence is inadequate; missing truth, unsupported inputs and uncertain frontier status are separate from `NONE_FEASIBLE`.

Keep P's requirement/context law, Q's frontier enrichment and w's buyer mix separate (§3). Continuous requirement support/distributions remain HUMAN_INPUT, not arbitrary interpolation between unrelated JEITA package classes. A small audit grid does not replace P. Report distinct winners/value-equivalent sets, feasible/NONE_FEASIBLE/UNRESOLVED mix, close-call rate and dependence by physical bank. Expected answer diversity is NOT_DEMONSTRATED. Reused threshold draws consume the same exposure E; E/B/n are HUMAN_INPUT, not fresh truth created by a new question ID.

Do not rank a failed action by averaging across thermal conditions. **T2(a), Test Lead working value relayed by the owner:** for every question family and mandatory stratum, require **at least five distinct resolved feasible and five distinct resolved infeasible actions, BOTH within two refinement bands** of the relevant limit. The band width in each observable's units is HUMAN_INPUT from verified numerical/reference uncertainty. With signed slack m and approved one-band width delta, near means `abs(m) <= 2*delta`; this is a proposed working diagnostic, not production adoption. A feasible action must satisfy all mandatory conditions for the graded question/stratum; a near-infeasible action needs a resolved violation attributed to that boundary. Distant failures of another constraint, unsupported truth and repeated timestamps do not fill frontier quotas. Report boundary/active-constraint membership and cross-stratum full-question feasibility separately.

Register both-side counts and the exact uncertainty rule before frontier inspection. Too few near designs means more frontier resolution, never a wider band or weaker limit. Overall pass rate is reported but is not the former 20–80% gate. Also require meaningful buyer-unit margin spread, a complete feasible answer across mandatory strata and answers that change across contexts/draws. All outcomes and working thresholds remain unmeasured/unapproved. Ten diagnostic slots can discover a shortage; they do not guarantee a powered batch or bank admission.

## 7. Construction contract

No construction permission, runtime Challenge or new schema is granted. Reuse the existing Level 0 capability vocabulary and current construction isolation. Actual allowed strategy vocabulary, training data, reconstruction backends, model format, CPU/GPU resources, wall/memory limits and immutable artifact identity require the construction owner's versioned grant.

Public own-seed data could become training input only if the construction contract and rights permit it. A proposal for a research generator or open solver is not permission to run participant code in the official evaluator. Protected witness/evaluation truth remains independently controlled. Reconstruction failures and official measurement failures retain separate typed semantics.

`OPEN / HUMAN_INPUT`: Level 0 bindings, data/backends, budget, reconstruction/artifact contract and security approval. Owner: construction, compute and security owners. **Held closed:** construction release and participant execution.

## 8. Research kit

Existing public material: this ten-section draft, source/applicability ledger, original D016 assumptions and the prospective panel manifest. Proposed kit after approval: rights-cleared 3D examples and region definitions; material-law provenance; grammar and own-seed generator; pinned open reference route; measurement transforms and analytic controls; strongest baseline recipes; practice-only metrics; explicit compute provisions and reproducibility/cost ledger.

Unprovided: a runnable container/deck, calibrated complete-history material models, rights-cleared meshes or training labels, approved population/generator, practice evaluator, qualified measurement implementation and construction grant. A paper's availability does not automatically authorise redistribution of customer/vendor decks or all underlying measurements. Official seeds, protected labels and sealed confirmation remain absent from the public kit.

`OPEN / HUMAN_INPUT`: kit completeness and data/licence rights. Owner: kit/construction and rights owners. **Held closed:** claiming a usable training kit or releasing reference data.

## 9. Evidence plan

**First feasibility and value-check panel — proposed, no dispatch.**

Stage zero is documentary: customer engineering owners freeze a real package/action grammar, every applicable hard limit, full process/service history, calibrated laws and witness export rights. Science owners freeze measurement/reference tolerances, independence, strata and baseline tuning limits. If any acceptance or reference input remains missing, Data Collection reports the gap and performs no substitute “feasible” calculation.

After separate owner compute approval, the priced diagnostic panel assumes **10 / 10 / 10 actions** evaluated over **3 / 3 / 3 distinct complete-history strata**, producing **30 / 30 / 30 primary cases**, plus **6 / 6 / 6 double-cost refinements**, **4 / 4 / 4 analytic/control equivalents**, **4 / 4 / 4 paired-tool witness equivalents** and **4 / 4 / 4 failed-attempt equivalents**: **54 / 54 / 54 complete-case equivalents**. Every count is ASSUMPTION, not realised evidence. The witness allocation is only an early triage allowance; it does not establish Tier 2 coverage or independent confirmation power.

**Explicit pre-registration, not runnable material.** All slots inherit one buyer-approved full-3D architecture `ARCH-A`, nominal geometry `G-NOM`, calibrated material/process set `MAT-A` and complete history definitions below. These symbolic identifiers are public drafting labels, not runtime IDs. Values/identities are HUMAN_INPUT; no property minimum/maximum is invented.

| Proposed design slot | Change from the approved nominal; freeze obligation |
| --- | --- |
| W01 | Nominal underfill UF-A and solder-stack S-A; supplier-valid full geometry |
| W02 / W03 | Buyer-approved lower / upper gap-standoff, with compatible joint geometry |
| W04 / W05 | Buyer-approved lower / upper underfill fillet extent, keep-outs preserved |
| W06 / W07 | Alternative approved UF-B / UF-C with their complete correlated material laws, not independent CTE/modulus tweaks |
| W08 / W09 | Approved solder-stack S-B / S-C, including alloy, bump shape and phase/history treatment |
| W10 | Precommitted combined underfill/stack frontier proposal; exact permitted values chosen before truth access |

| Proposed stratum | Complete history to freeze, not a temperature snapshot |
| --- | --- |
| S1 | Nominal manufacture/cure/bond/reflow/cool-down plus approved nominal spatial operating field |
| S2 | Same registered process plus a buyer-supported asymmetric operating field and complete service/cool-down sequence |
| S3 | Buyer-approved dwell/residual/process variant plus its supported operating and cool-down history |

For every W/S combination freeze CAD/mesh/regions, catalogs and law hashes, state/activation/phase history, thermal file/hash, boundaries, observers, limits/bands, solver/container and resource identities. A missing lawful supplier alternative is SLOT_UNRESOLVED, not a substitute invented material. No slot is registered until buyer/science accept applicability and DC freezes the complete manifest; hashes/status stay null/HOLD here. Distinct slots must resolve to distinct actions; aliases do not count twice.

Precommit the six refinement selections and tie rule before seeing truth: use the approved near-boundary rule, retain unresolved/failing selections and stop on shortages rather than changing limits. The four control slots are free expansion, analytic bonded bilayer, full-3D asymmetric/twist consistency, and complete-history restart/state consistency. The two paired-tool witness slots are separate non-hidden matched-task draws or provenance-verified retired published cases, outside producer custody, not quiz/tuning material. Extra feature proofs, frontier slots or witness coverage require a versioned manifest/cost extension; the failure reserve is accounting, not retry permission.

Using original complete-case C1 **ASSUMPTION 0.03 / 0.12 / 0.45 node-hours**, the panel is **ASSUMPTION €19.16 / €27.09 / €56.14**. Its detailed formula, reserves, licence assumption and exclusions are in [feasibility-panel.json](feasibility-panel.json). None of these counts weakens the full 3D/history job. Measure real complete-case latency and costs before extrapolating a bank.

Required outputs: actual feasible/near-infeasible counts for each stratum, every binding limit, reference/refinement and witness discrepancies, thermal/force balance checks, complete-case timing/memory, typed failures and the charged ledger. The early panel can discover infeasibility or reference failure; it cannot guarantee the required contested population. Fewer than the required counts, unstable maxima or incompatible limits means HOLD and owner review, not limit relaxation.

**Strongest cheap baselines and value test.**

| Arm | Why it is serious | Matched-admissibility test |
| --- | --- | --- |
| Laminate/beam/trace-homogenised model | Published research supports low-cost global curvature estimates [S7–S8](source-evidence.md#research-geometry-and-strongest-low-cost-approaches) | Include calibrated temperature dependence and the same geometry/history support; verify whether it selects the same feasible action despite lacking local detail |
| Cached buyer/reference FE | Complete repeated cases can reuse already adequate outputs | CLOSED_BANK exact cache receives its permitted complete outputs and uncertainty; do not claim model value when lookup makes the same decision |
| Reduced FE and response surface | Published 3D FE plus response-surface optimisation covers underfill decisions [S9](source-evidence.md#research-geometry-and-strongest-low-cost-approaches) | Freeze the strongest fitted response/interpolation strategy before witness access; allow honest uncertainty and verified fallback |
| Carbon candidate | Possible amortisation over new coupled 3D variants/histories | Demonstrate decision agreement at every hard limit, then lower end-to-end elapsed decision cost than the best adequate incumbent |

Run separate CLOSED_BANK and NEW_SUPPORTED studies under the [cheap-baseline contract](../../cheap-baselines/README.md). For new supported decisions, hold out whole geometry/history clusters, use identical permitted acquisition/fitting information and compute, charge reference/fitting/fallback/verification, and compare admissibility before speed. Record p50/p95 complete decision latency only after measurement; no industry runtime is inferred from an unrelated thermal service.

**Plausible Carbon advantage:** local asymmetry, spatial thermal gradients and time-dependent residual state might change a near-frontier decision that a laminate or sparse response map misses, while repeated new supported decisions amortise model construction. This is a hypothesis. Richer fields alone are not value; a response surface with honest fallback may already be best. Independent confirmation must be freshly held out and never used for tuning.

`OPEN / HUMAN_INPUT`: approved studies, sample power, thresholds, confirmation population, revision/disclosure protocol and spend. Owner: science/value and compute owners. **Held closed:** affordability proof, admission and deployment-value claim.

## 10. Readiness and claim record

| Item | State and next requirement |
| --- | --- |
| Real role/workflow | Source-confirmed by independently originating Amkor and ASE material; exact customer packet and acceptance remain HOLD |
| Architecture/material evidence | Public anchors catalogued; customer grammar, ranges and material-history law are HUMAN_INPUT |
| Hard-limit feasibility and contestability | NOT_DEMONSTRATED; source applicability and actual cases must be established |
| Open exact-output route | Proposed CalculiX route; no deck, container, output adapter or solver run |
| Earned credibility | NOT_DEMONSTRATED; target Tier 2 requires matched independent evidence |
| Baseline superiority | NOT_DEMONSTRATED; closed-bank cache may erase value |
| Startup affordability | Assumed base fits owner budget; original high scenario exceeds it; actual all-in bill unknown |
| Construction/security/rights | No grants or qualification; HUMAN_INPUT |
| Maturity | RESEARCH_SPECIFICATION_DRAFT only; no Challenge adoption, launch, LIVE status or scientific qualification |

**Original discovery comparison, preserved rather than rescored.** Every scenario value below is an **ASSUMPTION** from #928's D016/D012/D077 scored cards at the pinned source head. Index = conditional V2 × V3 / (C2 + 52 × weekly C3); low uses low benefit with high cost, base uses base benefit/cost, and high uses high benefit with low cost. It is an economic ordering hypothesis, not a cross-Challenge scientific score or net ROI. Its benefit floor is zero until measured. Excitement is a tiebreaker only.

| Candidate | Startup € low/base/high | Value-to-cost index low/base/high | Excitement low/base/high |
| --- | --- | --- | --- |
| D016 package warpage | 23.91 / 46.06 / 127.30 | 0.865 / 453.804 / 41,902.447 | 3.333 / 4.333 / 5.000 |
| D012 solenoid pole, #921 lineage | 18.98 / 26.37 / 46.06 | 5.378 / 2,113.982 / 164,907.682 | 2.333 / 3.333 / 4.333 |
| D077 seal gland, #921 lineage | 20.21 / 28.83 / 53.45 | 5.150 / 2,014.034 / 154,865.993 | 1.667 / 2.667 / 3.667 |

On the inherited base assumptions, warpage does **not** beat the solenoid or seal on value per cost. Its frontier/investor excitement does not reverse that ordering or resolve its hard-filter HOLDs. The parallel discovery search owns any revised portfolio ranking; this packet does not update its shared data.

**Explicit comparison against the eight.** Same index definition, but no invented currency conversion or missing full-bank cost. The annual gross snapshot below is in **USD**, while D016/D012/D077 above use EUR. It is labelled assumption-based decision value, not surrogate leverage, traction or earned advantage. Snapshot lineage and machine-readable null indices are in [feasibility-panel.json](feasibility-panel.json); the current discovery comparison also retains NOT_COMPUTABLE where complete C2/C3 and matched currency are missing.

| Incumbent | Conditional annual gross USD low / base / high | Full C2 / weekly C3 / same-index result | Decision-level check before comparison |
| --- | --- | --- | --- |
| Battery v3 | 1,500 / 315,000 / 19,800,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Beat the precomputed five-band charge map; sessions are not new solver decisions |
| Motor | 4,000 / 162,000 / 3,840,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Full holding/peak/cogging feasibility and signed-curve response surface |
| Cooling cell | 1,000 / 40,500 / 768,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Beat cell interpolation; no full cold plate in this comparison |
| f02 burst thermal | 4,000 / 144,000 / 1,920,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Thermal impulse-response/reduced-order decision baseline |
| f06 grating coupler | 2,000 / 72,000 / 720,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Adequate industry 2D optimizer may erase speed value |
| f08 structures | 2,000 / 54,000 / 576,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Cached modal library, not full-harmonic straw baseline |
| f13 silencers | 1,000 / 36,000 / 384,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Sound power/reference route before transfer-matrix/response comparison |
| f17 micromixer | 2,000 / 72,000 / 1,024,000 | NOT_COMPUTABLE: complete costs and currency basis missing | Periodic-cell/reduced mixing baseline with protected diffusion measure |

No per-case timing alone fills C2/C3, no assumed FX is used, and null is not zero. This packet does not rescore the eight or consume a reframe. Warpage still needs real full-history feasibility and contested boundaries, credible reference and superiority over its strongest cheap baseline. No same-index superiority over the eight is demonstrated.

Reviewers are **HUMAN_INPUT named science/reference owner, customer packaging/reliability/thermal owners, construction/compute/security/rights owners and PR Head**. The next gate is a source-complete acceptance/reference freeze, followed by an independently authorised diagnostic panel. User adoption/replacement authority remains with the owner.

The packet records research and proposed specification. No solver ran, no spend occurred and no protected or existing Challenge material was changed. Documentation checks and PR CI cannot qualify the physics.
