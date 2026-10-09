# CHALLENGE-BASELINE-SPECS-01 — cheap buyer methods to beat

**DEVELOPMENT / SPECIFIED, 2026-10-08.** These are strong, inexpensive
comparison workflows, not measured winners, adopted scientific models, or
qualification evidence. They implement the current or expressly proposed
buyer job in the linked [value dossiers](README.md). The named sources show
that each *method class* is used in an engineering workflow; none establishes
that a particular Carbon buyer uses it, that its accuracy is sufficient for
our packet, or that it beats Carbon. Cost and latency remain **UNMEASURED**
until Data Collection runs matched receipts. No source's tutorial run time is
transferred to Carbon hardware.

## Common V4 measurement contract

Data Collection registers the exact packet version, action grammar, hard
limits, objective, tie/value-equivalence rule, condition strata, P, Q and buyer
weights separately. It builds each baseline from public/own-seed or otherwise
permitted **training** panels, with reference-bank clusters kept intact across
fit/validation/evaluation splits. A baseline may tune its architecture and
safety guard band on that public validation split, then freezes code, fitted
parameters, data identities and optimizer before the sealed evaluation panel
is read. No evaluation reference, protected ID or digest pre-image enters
fitting or method choice. Inputs outside fitted support produce an explicit
abstention, not an extrapolated pass.

Each baseline commits its predicted quantities, feasibility verdicts and
pick/abstention before the common settled reference is consulted. The same
registered action set and complete condition panel are used for Carbon and
baseline. Data Collection reports **per stratum** and, for indexed decisions,
**per index and full map**: feasible-existence agreement, hard-limit confusion
by quantity, selected action or registered value-equivalent set agreement,
false-feasible picks, abstentions, objective-unit regret, and unresolved/infra
exclusions under one common resolved mask. Mandatory failures are never
offset by a better objective. P, Q and within-map buyer weights are separate
views. Show the cost/latency versus agreement frontier at **matched
admissibility** (including false-feasible and abstention rates); do not select
a favorable baseline operating point using the sealed panel. The owner/Test
Lead decides comparison thresholds and V4, not this document.

The cost ledger counts input acquisition, reference/experimental training
evaluations, fitting/optimization, failed attempts, memory, licenses where
applicable, and retained final independent verification. Report cold build
CPU-h/wall time and amortized cost per buyer revision separately from p50/p95
per-question and per-action latency on the same registered hardware. Symbols
below identify the work to meter; they are **not measured cost estimates**.

## Battery v3 — cached/interpolated charge map

- **Build inputs and cost.** Fit a table or POD map from permitted complete
  charge programmes indexed by protocol, cooling level, the five ambient
  bands, starting SOC and other registered state/requirements. Retain session
  minutes and every hard-limit observable (plating, charge temperature,
  voltage, capacity/retention), rather than fitting time alone. Meter
  `N_programmes × C_complete_programme + C_fit + C_validation`; the same cell
  characterization and 30-cycle reference cost cannot be treated as free.
- **Answer and latency.** Interpolate each candidate's outputs, enforce all
  limits **in every band**, choose one protocol/cooling action per band and
  buyer-weight the five admissible times. Refuse extrapolation or a cell/state
  outside fitted support. Query latency is five sets of table/POD evaluations
  plus a finite action scan; p50/p95 and cold-load time are unmeasured.
- **Existing use.** A [Romeo Power engineering account published by MathWorks](https://www.mathworks.com/company/technical-articles/modeling-and-simulating-battery-performance-for-design-optimization.html)
  describes SOC/temperature lookup tables fitted for battery design and charge
  method exploration; the [table-based battery block](https://www.mathworks.com/help/simscape-electrical/ref/batterytablebased.html)
  specifies interpolation and ageing/charge dynamics. This supports the method
  class, not accuracy for plating or Carbon's v3 map.
- **Decision agreement.** Compare all five per-band admissibility and action
  picks, full-map feasible existence, equivalent-minute sets and weighted
  minute regret on the registered SOC/ambient/requirements panel. A single
  false pass on a mandatory band is a false-feasible map; a missing band is
  unresolved. Charge-integral and phase-extremum reference checks remain.

## Motor — cached harmonic response surface

- **Build inputs and cost.** Use a public design-of-experiments set of the
  registered geometry, winding/skew and holding/peak commands. Cache solved
  magnetic harmonics or fit a response surface for torque, ripple and cogging
  with the exact current-angle and saturation conditions. Meter
  `N_complete_curves × C_magnetic_curve + C_fit + C_validation`, including
  each geometry's setup and failed evaluations.
- **Answer and latency.** Evaluate the surface over the registered geometry /
  command bank, enforce the torque/ripple/cogging limits and return the
  registered shortlist pick. Latency is surface evaluation plus the fixed
  search, unmeasured p50/p95; a new topology outside training support
  abstains.
- **Existing use.** [Ansys Maxwell's DesignXplorer integration](https://ansyshelp.ansys.com/public/views/secured/electronics/v242/en/subsystems/maxwell/content/LinktoDesignXplorer.htm)
  exposes magnetic simulation variables and outputs for design of experiments
  and optimization; [DesignXplorer](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/pdf/DesignXplorer_Users_Guide.pdf)
  includes response-surface optimization. This is a tool workflow, not a
  measured motor-buyer query count.
- **Decision agreement.** On the registered S3-like panel, compare the same
  torque floor, ripple and near-zero cogging verdicts for every command,
  then geometry/command pick and regret in its registered objective unit.
  Stratify by holding, peak and saturation; no motor-system thermal or
  controller claim follows.

## Cooling cell — fitted thermal/hydraulic response surface

- **Build inputs and cost.** Fit a response surface or thermal-resistance
  table on permitted periodic-cell conjugate-flow solves over geometry,
  coolant state, flow and the registered lid-side interface map. Charge the
  vapour-chamber/lid pre-solve separately. Meter
  `N_cell_panels × C_conjugate_cell + C_interface + C_fit + C_validation`.
- **Answer and latency.** Predict case-plane temperature and pressure drop /
  hydraulic objective on each condition, apply all registered limits, then
  select the cell. Latency is lookup/surface evaluation over the candidate
  bank, p50/p95 unmeasured. Interface maps outside support abstain.
- **Existing use.** [Ansys's Icepak–optiSLang thermal-design workflow](https://www.ansys.com/it-it/webinars/optimizing-thermal-designs-with-ansys-optislang-and-aedt-icepak)
  explicitly uses design of experiments and response-surface metamodels to
  pre-optimize electronics cooling without a solver call at each iteration.
- **Decision agreement.** Compare lid-side case-plane temperature and
  hydraulic limit verdicts, feasible existence, selected cell and objective
  regret by heat-load/interface stratum. This is a cell comparison; die
  temperature and complete cold-plate performance remain outside scope.

## f02 burst thermal — compact transient RC network

- **Build inputs and cost.** Calibrate a one-/three-node RC network from
  permitted package step/transient responses at each registered cooling
  boundary, plus source waveform and steady recovery baseline. Meter
  `N_transients × C_transient + C_RC_fit + C_recovery + C_validation`; do not
  make the shared steady baselines free.
- **Answer and latency.** Integrate the exact 120-s candidate waveform,
  search the spatial/time peak temperature and report recovery, then maximize admissible
  input joules. Latency is a small ODE/network transient per schedule and
  condition plus peak search, p50/p95 unmeasured; an unsupported cooling or
  initial-temperature state abstains.
- **Existing use.** [Ansys Icepak's IC-package documentation](https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/ice_ug/ice_ug_sec_network_ic_ss.html)
  gives RC transient package networks; its [surrogate thermal network builder](https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v261/en/Subsystems/Icepak/Content/Variables/ToolkitIcepakSTNB.htm)
  constructs faster networks from detailed-model trials.
- **Decision agreement.** Compare the spatial peak ≤95 °C verdict across the
  full event, then selected schedule and extra-J-per-burst regret for each
  cooling/initial/split/waveform stratum. Report recovery diagnostics
  separately. Endpoint-only temperatures cannot count as agreement.

## f06 grating coupler — direct 2D optimizer workflow

This is the proposed early-screening f06-v2 job in the
[value dossier](f06.md). The original full-3D robust packet is a separate,
unchanged job. A 2D pass alone is not a final 3D acceptance verdict.

- **Build inputs and cost.** Set up the registered 2D stack, source/mode,
  wavelength and offset deck and a constrained pitch/duty/etch search. There
  is no fitted training model; meter setup plus **every** 2D forward/adjoint
  solve, failed search step and retained 3D witness as
  `N_2D_solves × C_2D + C_setup + C_3D_witness`.
- **Answer and latency.** Return an in-plane shortlist from direct 2D
  optimization under the registered line-normalized screening requirements,
  with retained 3D spot checks for transfer to final use. Latency is an entire
  2D optimization per new screening question, plus the charged spot checks,
  not a neural inference; measure p50/p95 and solver calls. The 2D stage
  cannot certify finite-width 3D fibre coupling.
- **Existing use.** [Ansys Optics' 2D grating-coupler inverse-design workflow](https://optics.ansys.com/hc/en-us/articles/360042800573-Inverse-Design-of-Grating-Coupler-2D)
  optimizes a 2D FDTD design with manufacturing constraints and exports a 3D
  design for subsequent checking.
- **Decision agreement.** For the proposed f06-v2 job, compare the same 2D
  spectral/in-plane hard-limit verdicts and chosen screening mask against the
  registered 2D reference. Report 3D witness disagreement and final-use
  acceptance separately. If the original full-3D job is tested, require its
  complete 3D tolerance panel and charge it in the ledger. Do not compare 2D
  line power to 3D fibre efficiency as though they were one quantity.

## f08 resonant support — cached modal library

- **Build inputs and cost.** For each registered geometry, compute static
  stiffness/mass, a converged eigenbasis and residual-flexibility correction;
  cache the modal load/probe projection. Meter
  `N_geometries × (C_static + C_eigen + C_projection) + C_validation`.
  Reuse a basis across damping/frequency/load questions for that **same**
  geometry, never across changed geometry without rebuilding it.
- **Answer and latency.** Sweep the registered 80–600 Hz band and damping
  conditions from the cached modes, bracket narrow peaks and minimize
  worst-band tip motion per unit load subject to mass and compliance limits.
  Latency per new damping/force question is a
  modal projection/frequency sweep; new geometry also pays the build cost.
  Both p50/p95 are unmeasured.
- **Existing use.** [Ansys Mechanical's mode-superposition documentation](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/ans_str/Hlp_G_STR_SMSUP.html)
  explicitly stores and reuses eigenmodes for later harmonic analyses.
- **Decision agreement.** Compare mass, static compliance and **worst
  continuous-band** dynamic compliance at every damping level, then chosen
  support and mm/N regret. The 12/24/48-mode and adaptive-peak witnesses
  determine whether this already is a sufficient cheap buyer method.

## f13 silencer — transfer/retained-mode calculation

- **Build inputs and cost.** For the proposed coaxial no-flow packet, assemble
  chamber/duct transfer matrices and retain radial modes or junction
  corrections wherever a plane-wave-only approximation fails. Meter geometry
  setup, mode extraction, frequency products and validation, including
  rejected out-of-domain cases; no 3D Helmholtz solve is charged as free
  baseline input.
- **Answer and latency.** Predict the transmission-loss curve and choose
  chamber lengths/radii to maximize band p10 transmission loss under the
  registered band and packaging limits.
  Latency is one matrix/mode sweep per geometry, p50/p95 unmeasured. Offset,
  flow-acoustic or higher-mode unsupported cases abstain.
- **Existing use.** An [industrial silencer design account hosted by COMSOL](https://www.comsol.com/paper/duct-silencer-modeling-with-comsol-multiphysics-94641)
  says it starts with 1D transfer-matrix optimization; a [Dinex-authored
  transfer-matrix/FE study](https://www.comsol.com/paper/analyzing-muffler-performance-using-the-transfer-matrix-method-5079)
  applies the method to muffler design and checks simulations against a rig.
- **Decision agreement.** Compare full-band transmission-loss and packaging
  verdicts, especially narrow dips and mode cutoffs, then chosen silencer and
  dB regret on the same frequency law. A plane-wave agreement below cutoff
  cannot establish an all-band decision.

## f17 micromixer — CFD-trained response surface

- **Build inputs and cost.** Fit a validated response surface from permitted
  finite scalar/flow panels over the registered repeated-groove geometry,
  flow and diffusivity conditions. Fit both flux-weighted mixing index and
  pressure drop; meter `N_flow + N_scalar` complete CFD jobs, sampling,
  fitting, holdout and failed attempts. Velocity reuse is credited only when
  actually measured.
- **Answer and latency.** Evaluate each groove candidate at all mandatory
  conditions, enforce pressure, residence and mixing limits and maximize
  worst-condition outlet uniformity under the registered
  design. Latency is surface evaluation and a finite scan, p50/p95 unmeasured;
  outside fitted Reynolds/Péclet and geometry support it abstains.
- **Existing use.** The [original micromixer design study in *Scientific
  Reports*](https://pmc.ncbi.nlm.nih.gov/articles/PMC8907327/) uses Latin
  hypercube CFD samples, response-surface proxies and a genetic search for
  mixing index and pressure drop. It shows the method class, not its adequacy
  for Carbon's finite inlet/diffusion observer.
- **Decision agreement.** Compare mixing, pressure and residence hard-limit
  verdicts over all flow/diffusivity strata, then selected groove and
  mixing-index regret. Recompute
  the finite scalar reference and flux-weighted outlet measure; numerical
  diffusion or a periodic-velocity shortcut cannot become agreement by
  relabeling the observer.
