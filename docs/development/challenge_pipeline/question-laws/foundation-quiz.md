# Quiz content for the five foundation Challenges

**CHALLENGE-QUESTION-LAWS-02 / DEVELOPMENT / SPECIFIED only.** The buyer
needs a correct admissibility and design decision, not a high average curve
score that hides a breached limit. This specifies Q2 near-limit questions,
Q3 design choices, truth refinement, behavioural controls and diagnostics
for f02, f06, f08, f13 and f17. There are no realized cases or answer keys.
Test Lead owns score use, power, thresholds and adoption. Every new quiz
selection, band, count or scientific setting is **HUMAN_INPUT with a
recommendation**; the [proposal sheet](foundation-quiz-proposals.json) is
non-runtime and keeps registered choices null. Existing mock-customer
limits retain OWNER-PORTFOLIO-DEV-ROUND-01 authority, not production authority.

## Basis and forward rule

Use [#776](https://github.com/carbonphysicsai/Carbon/pull/776) at
`63d641b65a7e54ee547c1dd7b2aafece3b4d1366`: its
[eight question laws](https://github.com/carbonphysicsai/Carbon/blob/63d641b65a7e54ee547c1dd7b2aafece3b4d1366/docs/development/challenge_pipeline/question-laws/README.md),
[law sheet](https://github.com/carbonphysicsai/Carbon/blob/63d641b65a7e54ee547c1dd7b2aafece3b4d1366/docs/development/challenge_pipeline/question-laws/proposals.json)
and [Motor and cell quiz pattern](https://github.com/carbonphysicsai/Carbon/blob/63d641b65a7e54ee547c1dd7b2aafece3b4d1366/docs/development/challenge_pipeline/question-laws/motor-cooling-quiz.md).
This exact proposal is a dependency, not evidence that it is merged or a law
adopted. PR Lead integrates it first. KEEP Battery's
[quiz](../../../../carbon/challenge_validator/battery_quiz.py),
[v8 registry](../../evidence/battery-quiz-designs/quiz-registry-v8.json) and
[diagnostics](../../evidence/battery-quiz-designs/quiz-diagnostics-v1.json)
as patterns, not copied scoring, power, sample sizes or mistake prices.

The [Test Lead's forward ruling](https://github.com/carbonphysicsai/Carbon/pull/776#issuecomment-6048654166)
applies to all eight: **NONE_FEASIBLE remains in P; no redraws**. Correct
abstention is decision value, while abstaining when a resolved feasible
alternative exists is a missed opportunity. Test Lead registers how those
outcomes enter a score; no magnitude is invented here. Power is assessed on
the **feasible-opportunity subset using diagnostic Q enrichment**, never by
conditioning or replacing P. Report the full P feasible/none/unresolved mix
and Q's separate coverage and mixture. If no feasible opportunities or bad
controls exist, separation is UNMEASURABLE, not perfect. No redraw of an
unresolved reference either. Battery's already-sealed v8 redraw is the
explicit historical exception, ending at its **next quiz version**. No v8,
EV5, journal sequence 14 or live-contract change or historical rescore.

## Common question and answer contract

Before model evaluation, freeze Challenge/decision-contract and outer
P_job/Q_job/w_job identities; variant, supported service panel and buyer
requirements; action grammar and ordered bank; optimizer/version/budget;
observer, reference and extraction pins; units, tie/refinement policy and
underlying-case exposure links. Freeze the selector, then commit its pick or
abstention and predictions digest **before answer-key access**. Candidates
cannot choose questions, starts, law, reference, query budget or truth.

Q2 asks whether **one action's stated observations** satisfy a requirement,
including the active failed constraint. A condition-level pass is not a
whole-panel pass. Q3 asks which action is best in the exact finite bank under
the complete mandatory panel, or whether none is feasible. Admissibility
precedes ranking: no weighted average compensates for one hard breach.
Finite-bank best is not a global physical optimum.

Proposed internal reporting records, not runtime fields:

- Question context, unit-bearing limits, complete panel, action/bank and
  selection pins, law variant, objective/ties and exposure linkage.
- Answer-key reference state, action verdicts and intervals, active
  constraints, resolved optimum/tie and objective, standard/refined
  identities, coverage and typed terminal failures.
- Committed pick/abstention; SELECTED_FEASIBLE/INFEASIBLE/UNRESOLVED,
  MISSED_OPPORTUNITY, CORRECT_ABSTENTION or ABSTENTION_UNRESOLVED; physical
  regret only against a resolved same-bank feasible comparator. A false-feasible
  pick is reported, not assigned an invented monetary penalty.

Reuse `carbon/design_search/tasks.py` identity/commit/judge patterns without
changing them or #779's optimizer implementation. Inner condition `strata`
are not outer P_job/Q_job/w_job. Custom p10 and curve observers need a
versioned projection: the task API's unweighted mean is not a quantile.
`bank_digest` hashes ordered IDs, not physical geometry or reference rows;
the producer manifest binds those separately. Miner-visible projections must
omit registered starts, seed, bank order and protected linkage under the
separate disclosure ticket; this specification exposes no such instances.

## Q2 selection and coverage

Recommend independent, precommitted public/retired diagnostic pilots: define
each reference-supported boundary region first, then choose cases by a
frozen panel's prediction disagreement, **not the submitted candidate's
errors**. Reuse #776's up-to-80 from up-to-320 case-requirement-pair pattern
only as a HUMAN_INPUT starting recommendation, not five filled pools or a
power calculation. Counts, per-limit allocations, control magnitudes,
near-limit distances, panel/rebuild pins and tie rules remain HUMAN_INPUT.
Missing panel prediction means unavailable, not unanimous agreement.

Include reference-settled cases on both sides of each active boundary,
intersections with competing limits, and easy interiors. Report shortages,
overlap, context/constraint coverage, eligibility and all reference failures.
If a settled feasible or infeasible side is absent, that detection measure
is UNMEASURABLE. Q2's disagreement selection is diagnostic; no invented
inverse weights turn an opaque ranking into P_job reliability.

Use signed passing margins: **cap minus observation** for upper limits and
**observation minus floor** for lower limits, in the original unit. Numerical
conservation/passivity/mesh checks establish reference eligibility, not extra
buyer constraints or a soft physics score. Their failure is not candidate
blame. No protected material is accessed by this proposal or its static tests.

## f02 Burst thermal quiz

**Buyer decision:** choose a schedule that delivers the most additional
joules above the 20-W base without exceeding the top-die thermal ceiling.
The [packet](../round1/f02-burst-thermal.md) anchors **95 °C over 120 s**.

Q2 boundary strata:

- Top-die **spatial and temporal peak** just below/above 95 °C and the drawn
  Q3 ceiling; warm initial state, weaker Robin cooling and 80:20 patch split
  distinguish a center/mean prediction from the true local maximum.
- Rectangular, ramp and two-pulse event/lag cases: a post-event peak missed
  by 0.5-s samples, or one pulse passing while the second causes a breach.
- Additional-energy floor from the drawn law: correctly integrate the
  waveform. For a ramp, extra energy is `(peak-base)*D/2`, not `(peak-base)*D`;
  the two rectangles total D and the intervening base interval adds no extra
  energy. These are waveform arithmetic, not Elmer truth.
- Crossing/recovery disagreement is observer/refinement coverage. Recovery
  uses the separately computed 20-W baseline; it is **not** a new Q3 recovery
  deadline. A fixed 95-°C crossing does not answer a different drawn ceiling.

Q3 selects one of nine schedules for **one of the 24 declared contexts**:
two Robin regimes × two initial temperatures × two source splits × three
waveform families. Require temperature and requested extra energy, maximize
extra J, then frozen action order. Regret is foregone extra J for feasible
picks. Shared-package contexts remain clustered, not independent devices.

Refinement uses the same stack, sources and waveform events with independent
mesh and time rungs and internal peak/crossing search. Packet checks include
peak shift ≤0.5 °C and crossing shift ≤0.5 s; its 1-°C decision-unresolved
band remains explicit, not a calibrated statistical interval. Applying that
band to varying ceilings is a HUMAN_INPUT recommendation. A crossing found
at only one rung, missing baseline or exhausted refinement remains unresolved
for the affected observation. An unresolved recovery alone does not erase a
separately settled temperature/energy verdict when recovery is not required.
The RC screen is not spatial transient truth. Exact runnable Elmer stack
deck, environment, source/observer and adequate bank are **NOT_DEMONSTRATED**.

## f06 Grating coupler quiz

**Buyer decision:** choose a manufacturable mask with robust fiber coupling
and acceptable guided reflection over the finite tolerance panel. The
[packet](../round1/f06-grating-coupler.md) anchors **coupling ≥0.30** and
**reflection ≤0.10 at every one of 45 vector/wavelength points**.

Q2 contrasts just-passing/failing coupling and reflection, separately and at
their intersection: wavelength endpoints, nominal/alignment offsets, paired
etch/pitch/duty perturbations and valid minimum-feature edges. Detect a mask
whose p10 or nominal center looks good but one mandatory point fails. Use
power fractions with independently normalized incident guided power, TE0
reflection and the pinned outgoing fiber overlap; near-zero reflection uses
absolute units, never an unstable relative percentage. A 180-nm post-
perturbation line/space breach is geometry invalidity, not a solved physics
failure. Invalid actions must not be silently clipped into a different mask.

Q3 keeps all nine tolerance vectors × five wavelengths, maximizes the frozen
45-point nearest-rank p10 (the fifth ordered coupling), after every mandatory
coupling/reflection check. Regret is coupled-power fraction (also report
percentage points). No process yield or continuous-band assurance follows.

Refine 30/20/10-nm spatial rungs, PML/padding, duration and normalization
independently on the same physical deck. Packet Δcoupling 0.02 and
Δreflection 0.01 absolute checks are convergence criteria, **not** certified
uncertainty bounds or quiz bands. Propagate the accepted per-point intervals
through min/max and p10 before deciding limits or winner ordering. Adding
wavelength witnesses is different from changing the five-point objective;
a changed spectral panel needs its own prospective identity and truth.

**Fine-grid memory:** the packet's bare 10-nm dimension screen is about
**573 million to 1.20 billion cells**, before substrate, air padding and PML.
This is not measured Meep RSS. The 256-GiB feasibility ceiling does not prove
fit or available capacity. Require a deck-specific cell/material/monitor/PML
memory forecast and retained measured peak RSS before claiming fine-rung
adequacy. OOM, unavailable memory or time leaves fine truth UNRESOLVED; no
silent coarse substitute, GPU grant or larger-machine purchase. The old
supermode solver is not this new 3D Meep/port/overlap route, whose exact
runnable reference and full panel remain **NOT_DEMONSTRATED**.

## f08 Resonance structure quiz

**Buyer decision:** choose a support with low worst-band motion that fits
the mass and stiffness constraints. The [packet](../round1/f08-resonance-structure.md)
anchors **mass ≤0.45 kg**, **static compliance ≤0.03 mm/N**, **dynamic peak
≤0.15 mm/N throughout 80–600 Hz**, at all three damping values.

Q2 contrasts mass, static-compliance and harmonic-peak boundaries separately
and together: light-but-flexible, stiff-but-heavy, and statically acceptable
supports with a narrow low-damping resonance between sampled frequencies.
Include resolved peak-location/phase witnesses at nonzero amplitudes and
modal-truncation failures. Frequency nodes are not independent samples.
Mass can use pinned geometry/material integration; an offline beam estimate
does not establish the ribbed/relieved support's dynamic feasibility.

Q3 keeps damping 0.005/0.01/0.02 and the complete adaptive band, minimizes
worst dynamic compliance, then mass, then bank order. Regret is mm/N of
avoidable worst response. No strength, fatigue, nonlinear clamp/joint or
machine settling-time claim is added.

Refine mesh, retained modes and resonance brackets independently. Keep the
packet's 12/24/48-mode rungs where supported, peak shift ≤5%, eigenfrequency
shift ≤1%, peak-location shift ≤min(2 Hz, 1% of peak frequency), and phase
shift ≤5° near nonzero peaks. Resolve spacing to at most one tenth of each
half-power bandwidth. These verification criteria are not calibrated quiz
bands. A coarse sample maximum is not complete-band truth; unresolved modes
or peaks block the affected verdict/optimum. Never raise damping to obtain
agreement. The exact CalculiX static/eigen/harmonic CAD deck, build, complex
extractor and adequately resolved bank are **NOT_DEMONSTRATED**.

## f13 Compressor silencer quiz

**Buyer decision:** choose a compact passive geometry with the strongest
lower-tail attenuation on the declared no-flow acoustic band. The
[packet](../round1/f13-compressor-silencer.md) anchors **band p10 TL ≥5 dB**,
**package length ≤300 mm** and **diameter ≤140 mm**, with port/neck/clearance
validity. There is no mean-flow pressure loss, source-noise or regulation gate.

Q2 tests just-below/above p10 attenuation, length and diameter; geometry near
valid neck/clearance edges; and cases where optimistic sparse sampling hides
transmission notches enough to change p10 or the best pick. Report minimum
TL and narrow failures as diagnostics, **not** an invented every-frequency
5-dB constraint. TL is `-10 log10(Ptrans/Pinc)` from acoustic power, not
`-10 log10` of a pressure-amplitude ratio. Preserve passivity/balance and
orientation checks on raw complex transfer/powers; no favorable clipping.

Q3 uses the complete 500–2500-Hz curve for each valid bank action, constrains
the drawn package and p10 requirements, maximizes interval-weighted p10 TL,
then bank order. Regret is avoidable p10 dB. Frequency interval width defines
target mass; equal weights on adaptive nodes would overweight resonances.
The port/end impedances, air and no-flow model remain fixed across questions.

Refine mesh and frequency quadrature independently, retaining every notch.
Packet checks: mesh ΔTL ≤0.5 dB, resonance shift ≤10 Hz, and full-band p10
and mean change ≤0.25 dB; energy balance ≤1%. Convergence checks are not
certified decision intervals. Quantile reconstruction/quadrature and its
uncertainty rule are HUMAN_INPUT. Near transmission zeros need a registered
absolute-power/log applicability rule; never clip dB to force agreement.
Sparse preflight values cannot certify the band quantile. The exact runnable
3D Elmer Helmholtz port/deck/extractor and full-curve route remain
**NOT_DEMONSTRATED**; a hypothetical multi-frequency deck is not implemented.

**Frequency-launch accounting:** 500–2500 Hz inclusive at 10 Hz gives
`(2500-500)/10+1 = 201` initial frequencies per curve. Under the separately
launched-frequency route, 16 bank geometries need **3,216** base launches;
the separate 30-case feasibility panel would need **6,030**. Add every
adaptive frequency, mesh rung, normalization, control and failed attempt.
The original 40-launch allowance cannot complete one 201-point curve. A
verified multi-frequency route may reduce process count, not erase frequency
work, memory or CPU cost; measure and version it first. Eight model queries
per search are not eight reference launches. A threshold-only question
reuses the same curve bank but does not renew its exposure.

## f17 Passive micromixer quiz

**Buyer decision:** choose grooves that keep outlet mixing useful without
excessive pump burden or residence. The [packet](../round1/f17-passive-micromixer.md)
anchors **M ≥0.8**, **pressure drop ≤250 Pa**, **mean hydraulic residence
≤20 s** across the complete nine flow/diffusivity conditions.

Q2 contrasts each limit and intersections: a high-M action with excess
pressure or residence, a low-pressure action with inadequate mixing, and
high-Péclet cases where numerical diffusion falsely improves M. The outlet
uses **positive axial-flux weighted** mean/variance and
`M = 1 - sqrt(variance_out/0.25)` without clamping. An area-weighted surrogate
is not this observer. Residence is actual fluid volume including grooves
divided by total flow; it is not a residence-time distribution. Backflow,
missing velocity evidence or unresolved scalar balance is reference coverage,
not invented excellent mixing.

Q3 keeps 1/3/5 µL/min × diffusivities 0.5/1/2 ×10⁻¹⁰ m²/s, maximizes worst
M after every condition meets the drawn three limits, then bank order.
Regret is avoidable mixing-index fraction (also report percentage points).
No chemistry, reaction yield, assay or clinical-performance claim is added.

Refine groove geometry/mesh, velocity convergence and scalar boundary layers
independently, especially at maximum Pe. Retain raw c, outlet flux and
variance; packet checks include balance ≤0.5%, c in [−0.001,1.001], ΔM ≤0.02
and Δpressure ≤5%. Boundedness alone cannot certify low numerical diffusion.
These are reference checks, not score thresholds or certified uncertainty.
Charge flow and scalar processes separately. Reusing an existing velocity
requires an exact identical flow/geometry pin; diffusivity reuse is not
assumed in the base count. Cooling's OpenFOAM installation does not provide
this new grooved flow/scalar/observer route, which is **NOT_DEMONSTRATED**.

## Q3 laws and answer diversity

These reproduce the #776 **recommendations**, not new registered laws.
Owner selects grid or continuous; neither is adopted here. Each P context
is its complete service panel except f02's 24 separately drawn contexts.

| Family | Grid requirement values | Continuous intervals on the same axes | Proposed bank and initial batch |
| --- | --- | --- | --- |
| f02 | T cap {90,92.5,95} °C; extra energy floor {300,600,900} J | T cap [90,95] °C; energy floor [300,900] J | 9 schedules per context; k=8; 216 raw context/grid combinations |
| f06 | Coupling floor {0.25,0.30,0.35}; reflection cap {0.05,0.10,0.15} | Coupling floor [0.25,0.35]; reflection cap [0.05,0.15] | 256 masks; k=8; 9 raw grid combinations |
| f08 | Dynamic cap {0.10,0.15,0.20} mm/N; static cap {0.02,0.03,0.04} mm/N; mass cap {0.35,0.45,0.55} kg | Dynamic [0.10,0.20]; static [0.02,0.04]; mass [0.35,0.55] | 256 geometries; k=8; 27 raw combinations |
| f13 | p10 floor {3,5,7} dB; length cap {240,270,300} mm; diameter cap {120,130,140} mm | p10 [3,7]; length [240,300]; diameter [120,140] | 16 geometries; k=8; 27 raw combinations |
| f17 | M floor {0.75,0.80,0.85}; pressure cap {200,250,300} Pa; residence cap {15,20,25} s | M [0.75,0.85]; pressure [200,300]; residence [15,25] | 45 geometries; k=8; 27 raw combinations |

Grid baseline P is uniform on the declared context/grid support. Continuous
P uses uniform supported intervals with registered dependencies, **not equal
mass on unequal-volume answer cells**. A question with requirements looser
than the original packet asks an explicitly different buyer brief; it is not
success on the original hard limits. Do not substitute it for the anchor quiz.
New service subsets, operating bands or action geometries are not included
in these laws without separate support and prospective registration.

For continuous diagnostics, reuse #776's recommended
`Q = 0.5 P + 0.5 P(. | near-limit region)`; specify density, band region,
normalizer and support before use. On a grid use the corresponding discrete
mass. An empty region falls back to P and reports no enrichment. If the
feasible-opportunity subset is empty, do not fabricate power: revise the
design space or support prospectively under the appropriate owner. Report
raw Q results and, for any adopted population estimate, actual P/Q weights.
Score use remains Test Lead-owned; no reference-conditioned redraw changes P.

Audit observed distinct resolved winners, feasible-set/verdict signatures,
concentration and feasible/none/unresolved mix. For iid draws, expected
distinct winners is `sum_a [1-(1-p_a)^k]` over **resolved design winners**,
excluding NONE_FEASIBLE and UNRESOLVED; report P and Q expectations separately.
Use the actual exposure-constrained joint draw law when not iid. Winners are
bounded by the eligible bank, not the number of continuous decimals. All
measured winner masses/expectations and close-call rates are
**NOT_DEMONSTRATED**. A batch dominated by one answer fails to demonstrate
design discrimination; report it rather than keep redrawing until it looks
diverse. Diagnostic Q can enrich without disguising the original P mix.

Report threshold-close, uncertain-ordering, refinement-requested,
reference-unavailable and residual-UNRESOLVED rates, per P/Q and context,
with all-draw and eligible denominators. More continuous thresholds cost no
new base solve on an adequate bank, but may require new edge refinement.
Threshold variation, model arms, idempotent replay and refinement never mint
new cases or reset E. Follow #756/#760 bank retirement and publication:
retired published cases never return to hidden use. Keep #776's one-question-
per-underlying-window recommendation until an explicit bundle policy exists.

## Refined edge truth and failure handling

Before sealing an answer key, identify every bank action with a required
reference interval crossing a buyer limit and every potential winner with
uncertain ordering. Selection is independent of the submitted pick. Pin the
same physical deck, standard and refined solver/extractor identities and
predeclared bounded refinement rungs. Approved packet convergence limits
are not calibrated uncertainty; acceptance and interval construction, quiz
bands, stopping rules, tie resolution, budget and allowed residual rate
remain HUMAN_INPUT. Refine under a separately authorized producer ticket or
retain UNRESOLVED; this ticket grants no execution.

For upper limits, accept only when the entire accepted interval is within
the cap; reject when wholly above. For lower limits, reverse the inequalities.
An intersecting interval stays UNRESOLVED under the registered band/equality
rule. A known independent breach can settle an action as infeasible even if
another quantity is unresolved. NONE_FEASIBLE requires **every** action to
be demonstrably infeasible; missing references cannot supply that proof.
One settled feasible action establishes FEASIBLE_EXISTS, but missing or
possibly better competitors prevent an exact optimum/regret claim. Use the
registered common resolved mask and expose its omissions, not candidate-
specific favorable subsets. No clean pass or credit for unresolved truth.

Missing/uncertain **candidate** predictions are coverage or abstention
findings; they cannot turn settled reference truth into UNRESOLVED. OOM,
nonconvergence, broken mesh, normalization failure, missing peaks or incomplete
refinement are typed reference/infrastructure findings, not candidate
scientific failures. Do not silently drop them from the headline denominator.
Validators **never solve references**: they rebuild/infer, commit and score
against the sealed producer key. New reference/observer versions revise
future batches only; already-sealed results retain their original identity.

## Behaviour defined controls

Two good baselines accompany the four requested bad behaviours: accurate
physical observations plus the frozen selector, and calibrated candidate
uncertainty without invented feasibility. Even calibrated abstention can
miss a settled feasible opportunity. A control is bad **where it actually
causes the defined decision error**; accurate edge optima and knowing a truly
discrete bank are not gaming. Magnitudes, regions, mixtures, recipes and
panel admission are HUMAN_INPUT; no controls run here.

| Family | Edge optimist | Over cautious | Localized sign error | Optimizer or lattice aware |
| --- | --- | --- | --- | --- |
| f02 | Reports a truly too-hot schedule just inside the ceiling, or inflates a ramp's extra J | Rejects a reference-feasible high-energy schedule near the ceiling | Reverses cap-minus-peak or energy-minus-floor in a declared region | Correct on ordinary samples but hides an event/second-pulse peak at search-favoured high energy; no nonexistent off-lattice schedule attack |
| f06 | Overstates near-floor coupling or understates near-cap reflection on a failing tolerance point | Rejects a feasible robust mask on one covered edge | Reverses coupling/reflection passing margins without inventing negative power | Accurate at coarse mask/spectral probes but biased at separately covered perturbation or search-favoured mask witnesses |
| f08 | Understates a true narrow resonance, stiffness burden or mass near a limit | Rejects a feasible lightweight support whose resolved peak meets limits | Reverses compliance/mass passing margin in a declared region | Accurate at coarse frequency/design nodes but hides a covered inter-node resonance or search-favoured low-response design |
| f13 | Inflates interval-weighted p10 by masking low-TL intervals, or understates package size | Rejects a reference-feasible compact attenuator near target | Reverses p10-minus-floor or cap-minus-length/diameter; no invented active acoustic gain | Fits sparse frequency/CAD nodes but hides covered notch/quadrature behaviour at a search-favoured geometry |
| f17 | Artificially smooths scalar variance to inflate M, or understates pressure/residence | Rejects a feasible useful-mixing cartridge near a limit | Reverses M/pressure/residence passing margin; no nonphysical concentration clipping | Fits coarse grooves/easy-flow nodes but mispredicts covered maximum-Pe or search-favoured grooves |

Use the same fixed selector and budgets for all models; candidates cannot
choose a more favorable optimizer. Off-bank controls require independent
covered truth or remain UNRESOLVED, never nearest-neighbour labels presented
as exact. Numeric mesh/angle/time/frequency refinement and a denser **design
action lattice** are different changes. Truth-informed synthetic controls
are operator fixtures, not public derivatives of protected cases or miner
training material. Public pilots use genuinely public/retired references.

## Diagnostics a through e

All five are **reported diagnostics only**; none becomes a gate or score
input here. Acceptance thresholds, tail definitions, power target, recipes,
k and reference/selection budgets remain HUMAN_INPUT.

| Diagnostic | Report for every family | Family specific focus and limitation |
| --- | --- | --- |
| (a) Optimizer stability | Frozen primary versus precommitted exhaustive-bank or second bounded audit: pick agreement, false-feasible/missed-opportunity spread and regret in buyer units | f02 nine-action and f17 finite exhaustive comparators; f06/f08/f13 bounded mixed/CAD search. Report seed/query-budget differences; no after-truth best-of-search |
| (b) Grid resolution | Matched standard/refined truth plus separately declared coarse/refined action witnesses: feasibility, best-pick agreement and physical regret | f02 time/events/mesh with the same nine actions; f06 spatial/PML/time and separate spectral witnesses; f08 mesh/modes/adaptive resonances; f13 mesh/frequency quadrature; f17 mesh/transport/flux. New actions require new truth, not threshold reuse |
| (c) Power by k | Exploratory k={1,2,3,4,6,8,12} as a recommendation subject to E and coverage; good versus behaviour-defined bad discrimination, AUC with mean/lower-tail uncertainty, false-infeasible and missed opportunities | Compute power on the feasible-opportunity subset under diagnostic Q; retain/report NONE_FEASIBLE in P and correct abstention. Cluster whole shared banks/contexts and recipe replicas. Absent class support is UNMEASURABLE; no k is certified |
| (d) Agreement with decision value | Compare a prospectively declared quiz-outcome/metric ordering against independent same-scope public DEVELOPMENT value using Kendall tau-b/Spearman rho, plus per-design feasibility and best-pick agreement or physical regret | Units: f02 J, f06 fraction/percentage points, f08 mm/N, f13 dB, f17 fraction/percentage points. Test Lead defines the metric; ties and missing comparators explicit. No cross-Challenge scalar comparison or invented money |
| (e) Unresolved rate | All-draw, truth-covered, action-selected, optimum-unresolved, refinement-terminal and candidate-missing rates, by constraint/context/variant/P/Q with numerator/denominator | Memory-unavailable f06, incomplete f13 curves, unresolved f08 peaks, f02 events and f17 diffusion stay visible. Raising k cannot cure a common missing reference; no unresolved clean credit |

The report carries observed/expected winner diversity, answer concentration,
feasible/none/unresolved mix, close-call demand and E use alongside diagnostics.
Reference credibility follows [the common contract](../round1/reference-credibility.md):
buyer-tool witnesses use a separate **non-hidden** draw from the same supported
distribution or legitimately retired published bank cases, enriched toward
near-limit/decision-flipping regions. Never export hidden EVAL, STRESS, quiz
or tuning witnesses across the producer custody boundary. Report pointwise
and decision agreement; neither replaces the other. A systematic tool gap is
a reference finding and prospective revision, never candidate failure or a
reason to silently rescore sealed results.

## Reference gaps and cost accounting

Every per-case solve cost, complete-bank CPU-hour cost and refinement cost
below is **UNMEASURED**, with numeric slots null. These are launch-work
formulas, not timings, machine sizing, feasibility evidence or grants.

| Family | Base reference work for #776's proposed bank | Missing demonstrated route |
| --- | --- | --- |
| f02 | 9×24=216 transient solves, plus controls, mesh/time refinement and steady recovery baselines | Exact Elmer layered-stack deck, pinned environment/source/observer and adequate spatial/time bank |
| f06 | 256×9=2,304 vector solves **only if** one verified broadband solve resolves all five wavelengths; otherwise additional spectral work | New 3D Meep normalization/TE0/fiber-overlap deck, fine-grid memory fit and adequate tolerance bank; old photonic timing is inapplicable |
| f08 | At least 256×(static+eigen+three harmonic)=1,280 process launches before controls/refinement | Exact CalculiX CAD/static/eigen/harmonic and adaptive peak/mode/extractor route |
| f13 | At least 16×201=3,216 separate-frequency launches before controls/refinement; 30 cost-panel curves separately imply 6,030 | Exact 3D Helmholtz port/energy/extractor plus full adaptive-band quadrature; no verified batched-frequency route |
| f17 | 45×9=405 condition pairs; at least 810 flow/scalar launches if both run per pair before controls/refinement | Exact grooved laminar flow/scalar deck and flux observer; velocity reuse must be demonstrated and pinned |

Complete settled banks allow requirement-only reuse at **zero additional
base solves**, not zero scoring/rebuild cost, free edge truth or new exposure.
Measure elapsed and process CPU time, allocated resource time, peak memory,
failures and cold/setup/refinement work separately in a future authorized
cost study. The existing feasibility allowances do not fill these banks.
No solver costs are borrowed from Battery, old supermode photonics or cooling.

## Adoption and handoff

Next work is to settle public/retired reference coverage and diversity, then
register law variant/support, observer projections, uncertainty/refinement,
Q2 panel, controls, exposure bundle, Q/power/score use and unresolved policy
under the responsible owners. Packaging and reference production are separate
tickets and grants. No hidden quiz or counted/fresh campaign is authorized
merely by completing these content specifications.

The shared implementation must take Challenge as a parameter; no duplicated
neutral registry, hidden-batch route, weighting, disclosure or optimizer
pipeline. The Battery-led protocol remains DEFINING, family queue unchanged,
and 45/30/25 is only a candidate. Cooling stays cell-only; no full cold plate.
Maturity is SPECIFIED, not executed/tested physics, power, earned credibility,
scientific/security/production qualification, deployment or LIVE authority.
**Codex is done; PR Lead may take over** when the complete candidate is handed off.
