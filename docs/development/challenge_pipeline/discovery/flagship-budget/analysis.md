# Flagship bank budget: the cost-only claim and its limits

CHALLENGE-DISCOVERY-01, owner-requested research follow-up. The owner is considering whether one flagship may have a larger startup budget. **No budget is changed or granted here.** All work remains inside discovery and the existing PR #928. Source inventory and scores are pinned to [original data at 536a2716](https://github.com/carbonphysicsai/Carbon/blob/536a2716bd24a41751a1d382fca40038ff1384ae/docs/development/challenge_pipeline/discovery/data.json). This report does not rewrite or rescore that evidence.

## 1. Which candidates actually qualify for the requested description?

**Strict answer: zero.** “Failed only on startup” would require every non-cost hard gate to pass, with G6 failing. No original candidate has that evidence. Feasibility/limits, contested designs, reference applicability, matched-baseline advantage and the exact customer packet remain HOLD. “No other recorded failure” is not “all other gates passed.”

The useful diagnostic list is the three rows whose **only recorded FAIL is G6**, whose original excitement base is at least 3.5 on the defined 0–5 scale, and whose original economic chain has positive gross scenario value. The 3.5 cut is a **report classification definition** ([3.5,3.5,3.5]), not a scientific threshold or a retrospective new score. “Strong value” here means a substantial conditional labour-value scenario; all three had original V2 base score 2 and V3 base score 1. No strong observed customer-value claim is earned.

All 80 IDs were accounted for: 15 originally scored; 65 have no excitement score or complete C2 estimate. Seven scored rows have a G6 failure. Three have G6 alone; four also have a non-cost failure. This is an audit of evidence available, not a finding that the other 65 are boring or affordable.

| Candidate from the 80 | Original recorded failed gates | Original excitement L/B/H | Included? / reason |
| --- | --- | --- | --- |
| D021 Photonic ring | G5, G6 | 3.67 / 4.67 / 5.00 | Excluded: Also G5: cheap baseline defeats the plain proposed scope |
| D016 Package warpage | G6 | 3.33 / 4.33 / 5.00 | Diagnostic cost-only-code list: G6 is the sole recorded FAIL; non-cost gates remain HOLD |
| D026 RF coupled filter | G5, G6 | 3.00 / 4.00 / 5.00 | Excluded: Also G5: cheap baseline defeats the plain proposed scope |
| D041 PEM reactant header | G6 | 2.67 / 3.67 / 4.67 | Diagnostic cost-only-code list: G6 is the sole recorded FAIL; non-cost gates remain HOLD |
| D051 Wind airfoil | G5, G6 | 2.33 / 3.33 / 4.33 | Excluded: Also G5; excitement base below the report's defined high-score cut |
| D046 CO2 adsorption cycle | G6 | 3.33 / 4.33 / 5.00 | Diagnostic cost-only-code list: G6 is the sole recorded FAIL; non-cost gates remain HOLD |
| D056 LPBF scan strategy | G2, G6 | 3.33 / 4.33 / 5.00 | Excluded: Also G2: thermal reference alone lacks graded distortion |

All three included candidates have G1/G2/G3/G4/G5/G7 HOLD, not PASS. Estimated cost and a larger owner budget resolve none of those gaps. LPBF's excitement does not compensate for an absent distortion-producing reference; plain RF/photonic/wind jobs still need to beat their cheap tools.

## 2. Ranked original jobs, cost and index

All triples in this report are **ASSUMPTION low/base/high** unless stated as exact source/definition. Existing counts, source IDs and dates are descriptive; fixed scenario counts have degenerate ranges. No physical or safety limit is invented.

| Rank / candidate | Original C1 complete-case CPU-h L/B/H | C2 startup EUR L/B/H | Original index L/B/H | Rounded envelope covering the stated high (EUR) |
| --- | --- | --- | --- | --- |
| 1. Package warpage (D016) | 0.03 / 0.12 / 0.45 | 23.91 / 46.06 / 127.30 | 0.86 / 453.80 / 41902.45 | 128 |
| 2. PEM reactant header (D041) | 0.05 / 0.15 / 0.40 | 28.83 / 53.45 / 114.99 | 0.96 / 325.92 / 26059.84 | 115 |
| 3. CO2 adsorption cycle (D046) | 0.05 / 0.20 / 0.80 | 28.83 / 65.76 / 213.46 | 0.26 / 132.45 / 13029.92 | 214 |

Those rounded envelopes are ceilings of the labelled high scenarios ([128,128,128], [115,115,115], [214,214,214]); they are not safety factors, measured p95 bounds or recommended spend grants. The C1 high values are hypotheses and are not known upper bounds. Required refinement, witness licensing, convergence tails, data authoring and power-driven bank enlargement could exceed them.

**Important budget interpretation:** base C2 already fits EUR100 for every included row. Under the original conservative screen, the high scenario makes them cost-rejected. If the owner considers illustrative ceilings of EUR150 or EUR250 (unadopted bookkeeping alternatives), the stated high envelopes for package/PEM fit the former and all three fit the latter. This changes only a cost scenario test; it produces no new scientific pass.

| Candidate | Original V2 EUR/revision L/B/H | Original V3 eligible revisions/year L/B/H | Gross annual labour-value EUR L/B/H |
| --- | --- | --- | --- |
| Package warpage | 120.00 / 540.00 / 1920.00 | 20.00 / 240.00 / 1200.00 | 2400.00 / 129600.00 / 2304000.00 |
| PEM reactant header | 120.00 / 450.00 / 1440.00 | 20.00 / 240.00 / 1200.00 | 2400.00 / 108000.00 / 1728000.00 |
| CO2 adsorption cycle | 120.00 / 450.00 / 1440.00 | 10.00 / 120.00 / 600.00 | 1200.00 / 54000.00 / 864000.00 |

The original chains use hypothetical teams/cadence and avoided engineering hours at EUR60/90/120 per hour (ASSUMPTION). These are not named buyers, revenues, willingness to pay, cash savings or realised benefit. Demonstrated commercial lower bound is zero.

### Same value-per-euro definition

Use the original framework exactly: **I = V2 × V3 / (C2 + 52 × C3_weekly)**, with numerator and denominator in EUR. C3=C2×R/E, with R=[0.5,1,2] weekly windows and E=[20,10,5] windows per physical-bank refresh (ASSUMPTION, not adopted law). Thus yearly denominator factors are [2.3,6.2,21.8] (derived); 52 is a fixed accounting convention, not a scientific value.

Base sorting uses base gross/base cost. Sensitivity corners are low gross/high cost and high gross/low cost. Wide overlap is not robust order. Excitement is never the ranking criterion or a cure for a hard failure. These ratios are gross scenario ordering aids, not ROI, net economic benefit or comparable scientific scores.

For an owner focusing solely on a one-time bank, the **startup-only** annual-gross/C2 index is reported separately; it excludes recurring refresh and is not the framework index:

| Candidate | Startup-only index L/B/H | Framework C3 EUR/week L/B/H |
| --- | --- | --- |
| Package warpage | 18.85 / 2813.58 / 96375.63 | 0.60 / 4.61 / 50.92 |
| PEM reactant header | 20.87 / 2020.67 / 59937.64 | 0.72 / 5.34 / 46.00 |
| CO2 adsorption cycle | 5.62 / 821.21 / 29968.82 | 0.72 / 6.58 / 85.38 |

Under the shared base refresh assumption, startup-only ratios are 6.2 times I and preserve the order. Different real workloads/refresh rates can change it. A larger startup cap does not approve ongoing refresh or validator costs; those remain HUMAN_INPUT.

### Charged bank ledger, held constant

For each row keep the original menu and bookkeeping: designs [24,24,24], mandatory strata [3,3,3], primary cases [72,72,72], refined cases [24,24,24] at cost multiplier [2,2,2], charged failures [15,15,15] and witness pairs [8,8,8] with two tools each. Equivalent complete cases U=72+48+15+16=[151,151,151].

**C2 = 1.37 × (151 × C1 + 4) × 1.19 + 10 EUR.** EUR1.37/node-hour is the user rate; serial elapsed/CPU ratio [1,1,1], setup/idle/fit [4,4,4] node-hours, tax stress [1.19,1.19,1.19], other-charge reserve [10,10,10] EUR and zero incremental witness licence are inherited assumptions. No division by vCPU count or invented concurrency gain. Licensing or fit overhead beyond allowances must be added. Human authoring/rights costs are not priced.

The narrow-scope alternatives **do not cut menu, strata, failure, refinement or witness counts** to fit the cap. Neither this ledger nor its counts proves a qualified/powered bank. C1 quantiles, exact deck/image/extractor and full all-in bills remain NOT_MEASURED.

## 3. Minimum credible scope proposals and honest value loss

These are the smallest credible **research proposals identified**, not a proven global minimum or a qualified cheap reference. The retained exciting part is an engineering hypothesis. Narrowing changes the buyer question, so V1/V2/V3/V4/V5 must be rebuilt. No original safety or feasibility requirement is relaxed; if the buyer still needs an omitted effect, the narrower scope is inappropriate.

### 3.1 Package warpage — rank first, strongest conditional case

**Original exciting job:** a package mechanical engineer chooses underfill/solder-stack geometry using warpage and strain through a full thermal history. Advanced heterogeneous packaging gives the frontier/investor appeal; it does not establish customer value.

**Proposed minimum:** fix one package architecture and approved material family; choose a small layer/underfill geometry family using an equivalent-layer **2D thermoelastic warpage screen** at customer-approved temperature/material states. Retain thermal-expansion mismatch and layered-package geometry. The open route is a reviewed CalculiX shell/section or other approved open implementation; whether it reproduces the required reduction and outputs is HUMAN_INPUT. Do not call an arbitrary plane-strain slice a full-package reference.

**What the buyer gives up:** unrestricted chiplet placement and full 3D corner/solder-ball strain, process-induced residual stress, nonlinear creep/plastic history, assembly effects and finished-package reliability. The 2D job may only screen layer choices before a separately retained full-package verification. If original limits depend on local 3D strain or process history, they cannot be waved through using the reduced output.

**Source and incumbent check:** [Lo, Liu and Chang](https://scholars.lib.ntu.edu.tw/entities/publication/c32f1d38-1e15-4056-b256-cee403b6c61d) describe a 3D-to-2D thermo-mechanical warpage method. This supports a modelling analogue, not the availability/licence/adequacy of our proposed open implementation. [WarpagePINN](https://arxiv.org/abs/2607.00364) and [WarPGNN](https://arxiv.org/abs/2603.18581) provide additional learned-model comparators. Their published performance claims are not Carbon measurements or tolerances.

Baseline must include laminate/Suhir-style theory, the deterministic reduced warpage method, cached FE surfaces and applicable learned incumbents with acquisition/training cost counted. Inference: reducing to a linear layered family may make a deterministic matrix/response map sufficient, repeating f08's failure mode. This is a V4 risk, not a proven new failure.

**Value retained/lost:** the quantitative sensitivity below retains 40% of per-decision value and 50% of eligible revisions at base; base gross becomes EUR25,920 instead of EUR129,600. The implied 80% base loss is an ASSUMPTION, not an empirical fraction. Neither original nor narrowed job has demonstrated commercial value. Retained engineering excitement needs reassessment rather than inheriting 4.33.

### 3.2 PEM reactant header — second, a modest budget envelope

**Original exciting job:** a fuel-cell stack engineer chooses header geometry for distribution and pressure-drop limits across flow conditions. The original task was already a component-level hydraulic screen; it never established full electrochemical/thermal stack authority.

**Proposed minimum:** fixed stack architecture/port arrangement, dry single-phase flow and a **2D manifold with calibrated porous/branch resistances**; vary header-width/taper parameters for that hydraulic design step. Retain distribution and pressure constraints in the registered 2D job. OpenFOAM is the proposed open route; exact closure, boundary data and extraction require approval and pins.

**What the buyer gives up:** general 3D junction/inlet/outlet shapes, vortical jets/crossflow and local port details; wet gas, condensation, reaction/heat coupling and arbitrary stack architecture. The last effects were not qualified by the original hydraulic proposal either, so do not count them as proven value that has now been removed. New losses primarily concern geometric coverage and 3D flow validity. A 2D flow pass cannot certify starvation, power, durability or a finished fuel cell.

The published [Chen, Jung and Yen 2D manifold study](https://www.sciencedirect.com/science/article/pii/S0378775307009457) omits electrochemistry, heat and mass transport. The [turbulent-header study](https://www.sciencedirect.com/science/article/abs/pii/S036031991100348X) reports complex 3D outlet-header flow. Publisher abstracts were available in search; direct full-page retrieval returned 403. Full applicability methods remain unverified.

Baseline must include a hydraulic network/porous model and the original CFD-trained response surface. Inference: the smaller job could already be answered by that network at negligible incremental cost. Hydrogen branding alone cannot preserve investor/miner excitement or surrogate leverage.

**Value retained/lost:** base sensitivity retains 35% of V2 and 50% of V3; gross falls from EUR108,000 to EUR18,900, an assumed 82.5% loss. This is a prospective subset of hydraulic requests, not a measured adoption fraction. If the real buyer needs 3D output, the narrowed value can be zero.

### 3.3 CO2 adsorption cycle — third, preserves a more expensive full loop

**Original exciting job:** a capture process engineer chooses cycle step pressures/times using cyclic purity, recovery and energy outputs. Cyclic separation retains frontier relevance but exact sorbent, limits, dynamics, convergence and buyer demand are unresolved.

**Proposed minimum:** one fixed adsorbent, dry binary feed and registered single-bed cycle; fixed pressure/cycle architecture, with only adsorption/purge timing choices. Use an **isothermal axial mass/momentum model**, iterated to prospectively approved cyclic steady state. Retain cyclic purity/recovery screening. No fewer cycles, coarser grid or weakened steady-state criterion is assumed as a cost shortcut.

The original pyAPEP route is **already spatially 1D**: there is no honest 3D-to-2D saving to claim. [Official simsep documentation](https://nahyeonan.github.io/pyAPEP/build/html/simsep.html) separates mass/momentum from mass/momentum/energy calculations. The real reduction is thermal physics and eligible request/action coverage.

**What the buyer gives up:** thermal/heat-of-adsorption transients, coupled energy-use claims, pressure-architecture search, broad feeds/materials and integrated plant operation. Isothermal control must be an actual buyer-realistic bench/screening job; the physical cost of temperature control is not priced. If energy or temperature limits are required in the original job, switching off the energy balance is not a pass. Preserve mass conservation, purity/recovery, operating-pressure and every other limit applicable to the new job.

Baseline must include equilibrium/shortcut cycles, a fixed-feed interpolated dynamic response surface and reduced process optimisation. Inference: a fixed two-timing menu may have too little residual complexity for a valuable fast-model Challenge. Kinetics and cyclic feasibility alone do not establish advantage.

**Value retained/lost:** base sensitivity retains 30% of V2 and 50% of V3; gross falls from EUR54,000 to EUR8,100, an assumed 85% loss. Full-plant energy improvement cannot be counted in that retained value. Customer rejection or an adequate shortcut baseline can make it zero.

### Side-by-side narrowing ledger

All triples below are **ASSUMPTION low/base/high**, not measured savings. Retention factors are deliberately transparent sensitivities; they have zero lower bounds because the new job might be unacceptable. They are not sourced percentages. Costs are hypotheses for **complete outputs over the retained conditions**, not one time step or one sample. The original U=151 and all overhead assumptions are retained.

| Candidate | Narrow C1 CPU-h L/B/H | Narrow C2 EUR L/B/H | V2-retention fraction L/B/H × V3-retention fraction L/B/H | Narrow V2 EUR L/B/H | Narrow V3/year L/B/H |
| --- | --- | --- | --- | --- | --- |
| Package warpage | 0.005 / 0.02 / 0.07 | 17.75 / 21.44 / 33.75 | 0.00 / 0.40 / 0.65 × 0.00 / 0.50 / 0.80 | 0.00 / 216.00 / 1248.00 | 0.00 / 120.00 / 960.00 |
| PEM reactant header | 0.01 / 0.04 / 0.12 | 18.98 / 26.37 / 46.06 | 0.00 / 0.35 / 0.60 × 0.00 / 0.50 / 0.75 | 0.00 / 157.50 / 864.00 | 0.00 / 120.00 / 900.00 |
| CO2 adsorption cycle | 0.01 / 0.04 / 0.12 | 18.98 / 26.37 / 46.06 | 0.00 / 0.30 / 0.55 × 0.00 / 0.50 / 0.70 | 0.00 / 135.00 / 792.00 | 0.00 / 60.00 / 420.00 |

| Candidate | Narrow gross annual EUR L/B/H | Gross-value loss % L/B/H | Narrow index L/B/H | Original base index → narrow base |
| --- | --- | --- | --- | --- |
| Package warpage | 0.00 / 25920.00 / 1198080.00 | 48.00 / 80.00 / 100.00 | 0.00 / 194.95 / 29343.29 | 453.80 → 194.95 |
| PEM reactant header | 0.00 / 18900.00 / 777600.00 | 55.00 / 82.50 / 100.00 | 0.00 / 115.61 / 17810.03 | 325.92 → 115.61 |
| CO2 adsorption cycle | 0.00 / 8100.00 / 332640.00 | 61.50 / 85.00 / 100.00 | 0.00 / 49.55 / 7618.73 | 132.45 → 49.55 |

Under these declared retention scenarios, narrowing reduces value per euro for all three, despite meeting the startup estimate cap. That conclusion is conditional on the retention hypotheses. A buyer interview may change it; no fraction is selected to guarantee that an exciting narrowed job wins. None inherits an excitement score, feasibility proof, scientific gate pass or independent credibility tier.

## 4. Owner choice and smallest next evidence

**Recommendation:** package warpage first for customer/reference/baseline investigation, then PEM header, then CO2 cycle, in original-base value-per-euro order. The stronger scenario order is not enough to nominate a qualified flagship. Preserve original scope if its customer value is real; choose a cheaper narrower job only if its actual buyer acceptance and baseline residual survive.

Before deciding a larger full-bank allowance, ask for the exact customer decision/unchanged limits and material rights, a reference-output demonstration and a same-decision cheap-baseline audit. If those fail, reject rather than enlarge budget. This owner follow-up authorises none of the prospective narrow scopes and consumes no existing Challenge's reframe cycle.

An optional first triage is a separately authorised Data Collection task, not run here. Use ten draft actions across all three approved strata, with primary 30, refinements 6 at double cost, four complete-case controls, four witness equivalents and four failed-attempt equivalents: U_triage=[54,54,54]. Counts are ASSUMPTION with degenerate ranges, not proof of five feasible/five near-infeasible designs. Use exactly the full original C1 outputs and the same overhead model:

| Original job | Triage EUR L/B/H (ASSUMPTION) |
| --- | --- |
| Package warpage | 19.16 / 27.09 / 56.14 |
| PEM reactant header | 20.92 / 29.73 / 51.74 |
| CO2 adsorption cycle | 20.92 / 34.13 / 86.95 |

All stated high triage estimates fit EUR100. This is a possible early stop before a full bank, not a full-bank acceptance or p95 study. Strong baseline validation, licensing or extra truth work can exceed the allowance; reprice if so. Retain all customer/safety limits and unresolved/reference failure distinctions.

Final HUMAN_INPUT: the real customer and job, limits/strata/P/Q/w, approved reference and tolerances, power-driven menu/bank size, earned V4, actual costs and any larger grant. Raising a budget is an owner choice; scientific and security qualification remain separate.

## 5. Sources, scope, decisions and verification

The original evidence snapshot is PR #928 head 536a2716bd24a41751a1d382fca40038ff1384ae. The follow-up authority read is main 432d22b786a7341de788bc8b1206526849f3a31f; current AGENTS/Constitution/invariants, Business Canon, delivery/delegation, common packet and value-cost framework were read. Build-out, overlay, master-plan and scientific-canon files match their already-read original snapshot. The owner message is the active bounded research contract; WAVE names no active successor ticket.

Bounded working decisions: KEEP the original 80/15 scores, gates, costs and data; add a separately labelled diagnostic budget list and prospective scope/value-loss scenarios; keep bank effort counts constant; never turn HOLD into PASS or invent a sole-cost survivor. These are reversible research records, with no schema/runtime/packet/qualification change. The owner request returns this follow-up to the existing PR; no second PR or merge is created. Hub is retired/frozen. All files remain within discovery.

Primary sources were checked on 2026-10-09; no source supplies customer limits or cost timings for these scenarios:

| ID | Source | Narrow support and retrieval limitation |
| --- | --- | --- |
| PKG2D | [Lo, Liu and Chang / National Taiwan University](https://scholars.lib.ntu.edu.tw/entities/publication/c32f1d38-1e15-4056-b256-cee403b6c61d) | Author-institution abstract describes a 3D-to-2D thermo-mechanical warpage method. It is a comparator/modelling analogue, not a verified open CalculiX implementation. institutional abstract. |
| PKGPINN | [WarpagePINN authors](https://arxiv.org/abs/2607.00364) | Primary preprint of learned thermal-warpage prediction. Comparison must include acquisition/training and domain limits; no reported speedup is adopted here. primary preprint abstract. |
| PKGGNN | [WarPGNN authors](https://arxiv.org/abs/2603.18581) | Primary preprint of physics-aware parametric thermal-warpage prediction. It strengthens the incumbent screen; no general V4 conclusion follows. primary preprint abstract. |
| PEM2D | [Chen, Jung and Yen](https://www.sciencedirect.com/science/article/pii/S0378775307009457) | Published abstract describes a 2D porous-media stack/manifold model while omitting electrochemistry, heat and mass transport. This supports the narrower hydraulic modelling analogue only. publisher abstract via search; direct open 403. |
| PEM3D | [Turbulent-header study authors](https://www.sciencedirect.com/science/article/abs/pii/S036031991100348X) | Published abstract reports complex 3D outlet-header jets/crossflow, motivating applicability checks before using 2D. publisher abstract via search; direct open 403. |
| APEPDOC | [pyAPEP authors](https://nahyeonan.github.io/pyAPEP/build/html/simsep.html) | Official axial-column model documentation separates mass/momentum from mass/momentum/energy functions. Isothermal reduction changes the claim; original model is already spatially 1D. official documentation. |

The root [validator](../validate.py) checks the original inventory plus the follow-up's selection/exclusions, source IDs, unchanged cost/score evidence, literal zero-qualified claim, retained-value arithmetic, complete-cost/index/triage calculations, order, links and exact file manifest. It runs no solver, network or third-party package. Native results are drafting diagnostics; exact-head canonical CI remains PR Lead's acceptance task. No amount of static verification qualifies a customer, reference, economic benefit or scientific test.

Maturity: sourced research and prospective scenario specification only. Solver runs=0; spend=0; no hidden/AX42 data or existing Challenge packet edits. There is no dispatch readiness, approved budget, adoption, production/scientific/security claim or historical rescore.

