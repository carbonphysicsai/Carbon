# f13 — compact passive silencer, customer round 1

Authority and numeric source: [index](README.md), [sheet](requirements.json).

## 1. Engineering job

Hypothetical compressor-skid acoustic engineer: select a two-chamber passive
silencer within140-mm diameter/300-mm length that maximizes band p10 transmission
loss; buyer target p10≥5 dB. Also report minimum TL and every narrow failure.
This is a packaging/attenuation decision, not compressor-source prediction,
operating pressure-drop, flow acoustics or a noise-regulation compliance claim.

## 2. Physical system

Rigid-walled 3D chambers, radii55–70 mm, lengths40–110 mm; coaxial50-mm-ID inlet
and outlet. Inter-chamber neck radius20 mm,length10–50 mm, lateral x offset
0–25 mm; require≥10-mm clearance from chamber walls. Package dimensions include
the two chambers, neck and two fixed10-mm port stubs. No shell vibration,
absorption or mean flow. Synthetic air rho1.2 kg/m³,c343 m/s. Unit incident
plane-wave acoustic power, matched outlet impedance rho*c. Frequency500–2500 Hz.
Staggering is a physical design action; coaxial geometry is a strong control.

## 3. Population P, Q and w

Actions: valid geometry; reference-input geometry law is uniform independent
parameters conditioned on packaging/clearance. Exogenous `P_dev` is uniform
frequency on the declared band, approximated by an explicitly converged
frequency integration. Q first-round **reference preflight only**: straight
duct and coaxial single-chamber limiting controls plus low/nominal/high
two-chamber geometries at selected500/1500/2500-Hz diagnostic points. A complete
curve begins with a10-Hz grid (201 frequencies), then adapts around resonances;
it is not promised by40 launches. Grid density is Q, not
extra target weight; w is frequency interval width /2000 Hz. Do not overweight
an adaptively refined resonance by counting its nodes equally. No random-trial
reliability interpretation for a frequency curve.

The three diagnostic geometries use both chamber radii55/62.5/70 mm and
lengths40/75/110 mm, neck lengths10/30/50 mm and offsets0/12.5/25 mm respectively;
neck radius remains20 mm. Controls are outside that design-input law. The
runner must publish its exact sparse panel/control allocation before reference
access; missing full-band evidence remains explicit, not a reconstructed p10.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The 500–2500-Hz curve and its refined nodes belong to one compressor/duct
bank. A future `P_job` can vary the buyer's permitted attenuation target,
minimum narrow-band loss, or supported operating band while asking for a
different silencer from the **same complete curve bank**. A compressor OEM
recognizes the question from its source spectrum, duct drawing and acoustic
acceptance sheet. Re-evaluating stored curves needs no new solver launch if
the whole requested band and valid geometry are covered, and the best design
must demonstrably change. New duct terminations or media are optional axes
requiring new acoustics truth. Pressure drop is not measured by the present
reference and cannot become a mandatory limit through this variation.

**Size recommendation, not a selected law:** catalogue four distinct
condition/requirement questions first, then expand after a full-curve cost
study. `HUMAN_INPUT`: eligible requirements, `P_job`, protected `Q_job`,
weights, answer diversity, shared-bank clustering, exposure and powered
hidden `n`. Frequency nodes are within-question evidence. The 16-design
complete bank still implies at least 3,216 solver launches once; asking more
questions of it does not reset its exposure limit.

## 4. Case contract

Validate3D geometry, neck clearance, positive volumes and total≤300-mm length.
Bind source/port planes, normals, impedance, material and extraction identity;
refuse geometries rather than clip their offsets. Retain complex transfer
orientation. Public cases are independent from later operator-side hidden draws.

## 5. Reference policy

Elmer Helmholtz finite elements, pinned build/image/license, CAD/mesh order,
impedance boundary/source and complex-power extraction. The
[official model manual](https://www.nic.funet.fi/index/elmer/doc/ElmerModelsManual.pdf)
is the capability source, not Carbon's adequacy receipt. Straight duct and
single-chamber transfer-matrix controls, energy/passivity, mesh and independent
frequency refinement are mandatory. Duct's first transverse mode is outside
this band, but chamber modes need3D resolution.

Straight-duct |TL|≤0.25 dB, power balance≤1%, mesh-halving ΔTL≤0.5 dB at resolved
frequencies, resonance-location change≤10 Hz. For a later complete-curve claim,
retain transmission notches; refine frequency quadrature and mesh until both
p10 and mean change≤0.25 dB. Sparse preflight points cannot yield a band p10.
40 process launches/8 node-hours/$25 caps include controls and every separately
launched frequency solve. Without a verified multi-frequency deck this grant
cannot finish even one full201-point curve; complete-band/p10 adequacy is
explicitly deferred to a separately costed stage. Stop and
report exactly which checks/cases are unresolved, never skip tough resonances.

## 6. Output and measurement contract

Complex R/T at fixed port planes; incident/reflected/transmitted acoustic
powers, residual and TL=−10 log10(Ptrans/Pinc). No pressure-amplitude ratio
masquerading as power TL. Report interval-weighted p10 (lower quantile), mean,
minimum and full refined curve. Energy outside tolerance is unresolved reference.
Target is not an adopted official score or proof that every frequency meets5 dB.

## 7. Construction contract

Prepared Level-0 target: declarative geometry-to-complex-transfer model with
deterministic reconstruction; exact grammar/data permissions/runtime limits
await registration and budget study. No inference-time evaluator access.

## 8. Research kit

Own-seed geometry generator/reference, transfer-matrix and retained-mode
baselines, source/termination/normalization docs and incomplete public practice.
Reuse shared evidence/rebuild infrastructure; create acoustics-specific decks
and extraction. Never ship protected EVAL/STRESS, seeds or labels to pods.

## 9. Evidence plan

Controls before volume. Do not compare/rank full-band decisions from this
first-round sparse reference preflight. Compare equal decision/query budgets including baseline
setup and failed attempts. Park a topology that transfer/modal methods solve
adequately cheaply; do not add asymmetry solely to favor a model. Later fresh
confirmation and calibrated duct measurements require new custody/rights plans.
Operating-flow extensions are a new contract, not a first-round grant.

## 10. Readiness and claim record

Selected requirements and an analytical mode-cutoff screen only. 3D acoustic
reference adequacy is NOT_DEMONSTRATED. Next: exact impedance/power conventions,
CAD and analytic controls under stage permission. No source-noise reduction,
operating economics, compliance, physical qualification or launch claim.
