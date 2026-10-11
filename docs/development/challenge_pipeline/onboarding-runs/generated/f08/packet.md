# f08 — generated common packet draft

DEVELOPMENT / DRAFT_ONLY. SOURCE_EXTRACT means verified bytes, not approval.
Every unsourced field is HUMAN_INPUT. No runtime or qualification authority.

## 1. Engineering job

### buyer — HUMAN_INPUT

Precision-equipment structural engineer (internal mock customer)

Owner: science/product owner. Needed: Confirm applicability and authorize buyer.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### decision — HUMAN_INPUT

Choose a linear resonance-resistant structure with admissible response across the service envelope

Owner: science/product owner. Needed: Confirm applicability and authorize decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### value — SOURCE_EXTRACT

Hypothetical precision-stage engineer: select a light ribbed support minimizing
worst-band tip motion per unit load. Buyer constraints: mass≤0.45 kg, static
tip compliance≤0.03 mm/N, and dynamic peak≤0.15 mm/N throughout 80–600 Hz for
all declared damping conditions. A missed peak causes positioning error.
No full-machine settling time, throughput, fatigue, strength or joint certification.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize value.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### wrong_decision — SOURCE_EXTRACT

Hypothetical precision-stage engineer: select a light ribbed support minimizing
worst-band tip motion per unit load. Buyer constraints: mass≤0.45 kg, static
tip compliance≤0.03 mm/N, and dynamic peak≤0.15 mm/N throughout 80–600 Hz for
all declared damping conditions. A missed peak causes positioning error.
No full-machine settling time, throughput, fatigue, strength or joint certification.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize wrong_decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### exclusions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize exclusions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 2. Physical system

### physics — HUMAN_INPUT

Linear elasticity, modes and damped frequency response

Owner: science/product owner. Needed: Confirm applicability and authorize physics.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### geometry — SOURCE_EXTRACT

Cantilever rectangular plate: length180–260, width60–100, thickness4–8 mm. Two
longitudinal upper ribs, height8–16/thickness3–5 mm, at y=±width/4. Centered
through-plate cable relief centered at x=L/2,y=0: length20–60 mm in x and width20 mm; rounded 3-mm
corners, no rib intersection, ligament≥6 mm. Synthetic isotropic Al-like law:
E70 GPa, nu0.33, rho2700 kg/m³. Root x=0 fully clamped. Unit z-directed force
uniform on the last 5 mm×central10 mm tip pad, retaining resultant1 N.
Constant modal damping ratio0.005,0.01 or0.02 (not an inferred real joint law).

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize geometry.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### materials — SOURCE_EXTRACT

Cantilever rectangular plate: length180–260, width60–100, thickness4–8 mm. Two
longitudinal upper ribs, height8–16/thickness3–5 mm, at y=±width/4. Centered
through-plate cable relief centered at x=L/2,y=0: length20–60 mm in x and width20 mm; rounded 3-mm
corners, no rib intersection, ligament≥6 mm. Synthetic isotropic Al-like law:
E70 GPa, nu0.33, rho2700 kg/m³. Root x=0 fully clamped. Unit z-directed force
uniform on the last 5 mm×central10 mm tip pad, retaining resultant1 N.
Constant modal damping ratio0.005,0.01 or0.02 (not an inferred real joint law).

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize materials.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### conditions — SOURCE_EXTRACT

Cantilever rectangular plate: length180–260, width60–100, thickness4–8 mm. Two
longitudinal upper ribs, height8–16/thickness3–5 mm, at y=±width/4. Centered
through-plate cable relief centered at x=L/2,y=0: length20–60 mm in x and width20 mm; rounded 3-mm
corners, no rib intersection, ligament≥6 mm. Synthetic isotropic Al-like law:
E70 GPa, nu0.33, rho2700 kg/m³. Root x=0 fully clamped. Unit z-directed force
uniform on the last 5 mm×central10 mm tip pad, retaining resultant1 N.
Constant modal damping ratio0.005,0.01 or0.02 (not an inferred real joint law).

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize conditions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### omissions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize omissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 3. Population P, Q and w

### P — SOURCE_EXTRACT

Geometry is a design action. Reference-input geometry law: independent uniform
grammar parameters conditioned on valid shape. Exogenous `P_dev` is uniform
over three modal damping ratios; frequency is an adversarial peak search, not
a random customer state. Later decision comparisons weight damping1/3 and
report worst condition separately. Q feasibility uses three fixed geometries
(rib heights8/12/16 mm, rib thickness4 mm, length220,width80,thickness6,
relief40 mm) at damping
0.005 and0.02. No population estimate from six diagnostic cases.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The three damping values and 80–600-Hz search belong to one support bank.
A future `P_job` can vary supported peak-motion, stiffness or mass limits and
the required excitation/damping service panel if the solved bank covers it.
An automation buyer recognizes the question from its stage acceptance sheet,
payload schedule and vibration specification. Reapplying different limits to
stored peak, stiffness and mass outputs needs no new solve, but the
reference-best support must demonstrably change. New payloads, clamp
boundaries, contact or damping laws are optional axes requiring new qualified
reference work. Modes, frequency samples and optimizer starts are not fresh
buyer questions.

**Size recommendation, not a selected law:** catalogue eight distinct
condition/requirement questions for a development scoping pilot on a
complete-band bank. `HUMAN_INPUT`: eligible limits and panels, `P_job`,
protected `Q_job`, weights, answer diversity, shared-frame clustering,
exposure and hidden `n` from power and measured reference cost.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize P.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### Q — SOURCE_EXTRACT

Geometry is a design action. Reference-input geometry law: independent uniform
grammar parameters conditioned on valid shape. Exogenous `P_dev` is uniform
over three modal damping ratios; frequency is an adversarial peak search, not
a random customer state. Later decision comparisons weight damping1/3 and
report worst condition separately. Q feasibility uses three fixed geometries
(rib heights8/12/16 mm, rib thickness4 mm, length220,width80,thickness6,
relief40 mm) at damping
0.005 and0.02. No population estimate from six diagnostic cases.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The three damping values and 80–600-Hz search belong to one support bank.
A future `P_job` can vary supported peak-motion, stiffness or mass limits and
the required excitation/damping service panel if the solved bank covers it.
An automation buyer recognizes the question from its stage acceptance sheet,
payload schedule and vibration specification. Reapplying different limits to
stored peak, stiffness and mass outputs needs no new solve, but the
reference-best support must demonstrably change. New payloads, clamp
boundaries, contact or damping laws are optional axes requiring new qualified
reference work. Modes, frequency samples and optimizer starts are not fresh
buyer questions.

**Size recommendation, not a selected law:** catalogue eight distinct
condition/requirement questions for a development scoping pilot on a
complete-band bank. `HUMAN_INPUT`: eligible limits and panels, `P_job`,
protected `Q_job`, weights, answer diversity, shared-frame clustering,
exposure and hidden `n` from power and measured reference cost.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize Q.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### w — SOURCE_EXTRACT

Geometry is a design action. Reference-input geometry law: independent uniform
grammar parameters conditioned on valid shape. Exogenous `P_dev` is uniform
over three modal damping ratios; frequency is an adversarial peak search, not
a random customer state. Later decision comparisons weight damping1/3 and
report worst condition separately. Q feasibility uses three fixed geometries
(rib heights8/12/16 mm, rib thickness4 mm, length220,width80,thickness6,
relief40 mm) at damping
0.005 and0.02. No population estimate from six diagnostic cases.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The three damping values and 80–600-Hz search belong to one support bank.
A future `P_job` can vary supported peak-motion, stiffness or mass limits and
the required excitation/damping service panel if the solved bank covers it.
An automation buyer recognizes the question from its stage acceptance sheet,
payload schedule and vibration specification. Reapplying different limits to
stored peak, stiffness and mass outputs needs no new solve, but the
reference-best support must demonstrably change. New payloads, clamp
boundaries, contact or damping laws are optional axes requiring new qualified
reference work. Modes, frequency samples and optimizer starts are not fresh
buyer questions.

**Size recommendation, not a selected law:** catalogue eight distinct
condition/requirement questions for a development scoping pilot on a
complete-band bank. `HUMAN_INPUT`: eligible limits and panels, `P_job`,
protected `Q_job`, weights, answer diversity, shared-frame clustering,
exposure and hidden `n` from power and measured reference cost.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize w.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### strata — SOURCE_EXTRACT

Geometry is a design action. Reference-input geometry law: independent uniform
grammar parameters conditioned on valid shape. Exogenous `P_dev` is uniform
over three modal damping ratios; frequency is an adversarial peak search, not
a random customer state. Later decision comparisons weight damping1/3 and
report worst condition separately. Q feasibility uses three fixed geometries
(rib heights8/12/16 mm, rib thickness4 mm, length220,width80,thickness6,
relief40 mm) at damping
0.005 and0.02. No population estimate from six diagnostic cases.

### Prospective population of buyer design questions — `HUMAN_INPUT`

The three damping values and 80–600-Hz search belong to one support bank.
A future `P_job` can vary supported peak-motion, stiffness or mass limits and
the required excitation/damping service panel if the solved bank covers it.
An automation buyer recognizes the question from its stage acceptance sheet,
payload schedule and vibration specification. Reapplying different limits to
stored peak, stiffness and mass outputs needs no new solve, but the
reference-best support must demonstrably change. New payloads, clamp
boundaries, contact or damping laws are optional axes requiring new qualified
reference work. Modes, frequency samples and optimizer starts are not fresh
buyer questions.

**Size recommendation, not a selected law:** catalogue eight distinct
condition/requirement questions for a development scoping pilot on a
complete-band bank. `HUMAN_INPUT`: eligible limits and panels, `P_job`,
protected `Q_job`, weights, answer diversity, shared-frame clustering,
exposure and hidden `n` from power and measured reference cost.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize strata.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### independent_unit — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize independent_unit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 4. Case contract

### case_identity — SOURCE_EXTRACT

Bind complete CAD, material, clamp/load pad, damping, extraction coordinates
and units; refuse intersecting ribs/relief, invalid mesh or insufficient
ligaments. Reject rather than silently repair geometry. Canonical case/solver/
deck/extractor identities remain separate. Public cases never reveal hidden IDs.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize case_identity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### validity — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize validity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### disclosure — SOURCE_EXTRACT

Bind complete CAD, material, clamp/load pad, damping, extraction coordinates
and units; refuse intersecting ribs/relief, invalid mesh or insufficient
ligaments. Reject rather than silently repair geometry. Canonical case/solver/
deck/extractor identities remain separate. Public cases never reveal hidden IDs.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize disclosure.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 5. Reference policy

### solver — SOURCE_EXTRACT

CalculiX static, eigen and harmonic reference with independent mesh/mode/grid
checks; its [official capability list](https://www.dhondt.de/ov_calcu.htm) and
[manual](https://www.dhondt.de/ccx_2.20.pdf) support the candidate route.
Pin build, license, CAD/mesher, element order, mass representation, modal
damping and complex-output conventions before any reference dispatch.

Analytical oscillator and unrelieved beam controls; three mesh levels and
12/24/48 retained modes where supported. Apply full convergence rungs only to
the nominal geometry at both damping extremes; the four other cases are coarse
diagnostics and cannot establish reference adequacy. Require eigenfrequency change≤1%,
peak amplitude change≤5%, peak location change≤min(2 Hz,1% of peak frequency),
phase change≤5° near nonzero peaks. Adaptively bracket each resonance; refine
frequency spacing to≤one tenth of its half-power bandwidth before a peak claim.
Check modal truncation independently of mesh. All static/eigen/harmonic process
launches count separately within36 attempts/12 node-hours/$30: six coarse cases
need18; oscillator/beam controls use4; two finer nominal meshes share static/
eigen solves between damping settings and use8; four additional modal-retention
and two frequency-refinement harmonic launches use6. Missing rungs mean
unresolved reference, not a claimed adequate grid or silently higher damping.

### Reference credibility target

**Buyer tool:** Ansys Mechanical modal/harmonic analysis is the assumed stage
designer's workflow, not a verified adoption claim. **Carbon reference:**
proposed CalculiX static/eigen/harmonic solves, **not the same tool**; exact
task build/decks remain packaging work. Tier 1 requires the buyer's actual
model, materials, supports, damping, mesh and extraction settings.

**Target tier:** Tier 2 for linear structural-design shortlisting. Tier 3
measured modal frequencies and force/response curves are required before
assembled-support precision reliance; full-machine settling, joints and
nonlinear dynamics remain excluded. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** published NAFEMS **P18.FV4** (cantilever with off-centre
point masses), **P18.FV73** (cantilevered thin square plate) and **R0016.5H**
(deep simply supported beam, harmonic forced response), identified in
[NAFEMS's code-verification catalogue](https://www.nafems.org/publications/code-verification/nastran-code-verification/).
Run the same benchmark definitions in CalculiX and Mechanical and compare
published reference quantities; the catalogue is not a Carbon/tool pass.
Add matched ribbed/relieved-plate static and harmonic witnesses at both damping
extremes, with identical force normalization/probes and adaptive resonance
resolution. Eigenfrequency agreement alone cannot establish FRF peak accuracy.

**Acceptance tolerance: HUMAN_INPUT.** Recommend eigen/peak frequency difference
≤1%, static-compliance difference ≤2%, mass difference ≤0.5%, and
peak-location difference ≤min(2 Hz, 1% of peak frequency), peak
displacement-per-force difference ≤5%, and wrapped phase difference ≤5° at
resolved nonzero peaks. An absolute response floor for phase/relative error
away from peaks remains HUMAN_INPUT. Resolve the same resonance and output
convention; do not increase damping or smooth away a missed peak to pass.
These bound simulator decision error, not unknown physical joint damping.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted evidence, “matches the reference simulator” for this linear
support/forcing scope, not “matches reality” or full-machine positioning.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize solver.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### pins — SOURCE_EXTRACT

CalculiX static, eigen and harmonic reference with independent mesh/mode/grid
checks; its [official capability list](https://www.dhondt.de/ov_calcu.htm) and
[manual](https://www.dhondt.de/ccx_2.20.pdf) support the candidate route.
Pin build, license, CAD/mesher, element order, mass representation, modal
damping and complex-output conventions before any reference dispatch.

Analytical oscillator and unrelieved beam controls; three mesh levels and
12/24/48 retained modes where supported. Apply full convergence rungs only to
the nominal geometry at both damping extremes; the four other cases are coarse
diagnostics and cannot establish reference adequacy. Require eigenfrequency change≤1%,
peak amplitude change≤5%, peak location change≤min(2 Hz,1% of peak frequency),
phase change≤5° near nonzero peaks. Adaptively bracket each resonance; refine
frequency spacing to≤one tenth of its half-power bandwidth before a peak claim.
Check modal truncation independently of mesh. All static/eigen/harmonic process
launches count separately within36 attempts/12 node-hours/$30: six coarse cases
need18; oscillator/beam controls use4; two finer nominal meshes share static/
eigen solves between damping settings and use8; four additional modal-retention
and two frequency-refinement harmonic launches use6. Missing rungs mean
unresolved reference, not a claimed adequate grid or silently higher damping.

### Reference credibility target

**Buyer tool:** Ansys Mechanical modal/harmonic analysis is the assumed stage
designer's workflow, not a verified adoption claim. **Carbon reference:**
proposed CalculiX static/eigen/harmonic solves, **not the same tool**; exact
task build/decks remain packaging work. Tier 1 requires the buyer's actual
model, materials, supports, damping, mesh and extraction settings.

**Target tier:** Tier 2 for linear structural-design shortlisting. Tier 3
measured modal frequencies and force/response curves are required before
assembled-support precision reliance; full-machine settling, joints and
nonlinear dynamics remain excluded. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** published NAFEMS **P18.FV4** (cantilever with off-centre
point masses), **P18.FV73** (cantilevered thin square plate) and **R0016.5H**
(deep simply supported beam, harmonic forced response), identified in
[NAFEMS's code-verification catalogue](https://www.nafems.org/publications/code-verification/nastran-code-verification/).
Run the same benchmark definitions in CalculiX and Mechanical and compare
published reference quantities; the catalogue is not a Carbon/tool pass.
Add matched ribbed/relieved-plate static and harmonic witnesses at both damping
extremes, with identical force normalization/probes and adaptive resonance
resolution. Eigenfrequency agreement alone cannot establish FRF peak accuracy.

**Acceptance tolerance: HUMAN_INPUT.** Recommend eigen/peak frequency difference
≤1%, static-compliance difference ≤2%, mass difference ≤0.5%, and
peak-location difference ≤min(2 Hz, 1% of peak frequency), peak
displacement-per-force difference ≤5%, and wrapped phase difference ≤5° at
resolved nonzero peaks. An absolute response floor for phase/relative error
away from peaks remains HUMAN_INPUT. Resolve the same resonance and output
convention; do not increase damping or smooth away a missed peak to pass.
These bound simulator decision error, not unknown physical joint damping.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted evidence, “matches the reference simulator” for this linear
support/forcing scope, not “matches reality” or full-machine positioning.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize pins.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### refinement — SOURCE_EXTRACT

CalculiX static, eigen and harmonic reference with independent mesh/mode/grid
checks; its [official capability list](https://www.dhondt.de/ov_calcu.htm) and
[manual](https://www.dhondt.de/ccx_2.20.pdf) support the candidate route.
Pin build, license, CAD/mesher, element order, mass representation, modal
damping and complex-output conventions before any reference dispatch.

Analytical oscillator and unrelieved beam controls; three mesh levels and
12/24/48 retained modes where supported. Apply full convergence rungs only to
the nominal geometry at both damping extremes; the four other cases are coarse
diagnostics and cannot establish reference adequacy. Require eigenfrequency change≤1%,
peak amplitude change≤5%, peak location change≤min(2 Hz,1% of peak frequency),
phase change≤5° near nonzero peaks. Adaptively bracket each resonance; refine
frequency spacing to≤one tenth of its half-power bandwidth before a peak claim.
Check modal truncation independently of mesh. All static/eigen/harmonic process
launches count separately within36 attempts/12 node-hours/$30: six coarse cases
need18; oscillator/beam controls use4; two finer nominal meshes share static/
eigen solves between damping settings and use8; four additional modal-retention
and two frequency-refinement harmonic launches use6. Missing rungs mean
unresolved reference, not a claimed adequate grid or silently higher damping.

### Reference credibility target

**Buyer tool:** Ansys Mechanical modal/harmonic analysis is the assumed stage
designer's workflow, not a verified adoption claim. **Carbon reference:**
proposed CalculiX static/eigen/harmonic solves, **not the same tool**; exact
task build/decks remain packaging work. Tier 1 requires the buyer's actual
model, materials, supports, damping, mesh and extraction settings.

**Target tier:** Tier 2 for linear structural-design shortlisting. Tier 3
measured modal frequencies and force/response curves are required before
assembled-support precision reliance; full-machine settling, joints and
nonlinear dynamics remain excluded. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** published NAFEMS **P18.FV4** (cantilever with off-centre
point masses), **P18.FV73** (cantilevered thin square plate) and **R0016.5H**
(deep simply supported beam, harmonic forced response), identified in
[NAFEMS's code-verification catalogue](https://www.nafems.org/publications/code-verification/nastran-code-verification/).
Run the same benchmark definitions in CalculiX and Mechanical and compare
published reference quantities; the catalogue is not a Carbon/tool pass.
Add matched ribbed/relieved-plate static and harmonic witnesses at both damping
extremes, with identical force normalization/probes and adaptive resonance
resolution. Eigenfrequency agreement alone cannot establish FRF peak accuracy.

**Acceptance tolerance: HUMAN_INPUT.** Recommend eigen/peak frequency difference
≤1%, static-compliance difference ≤2%, mass difference ≤0.5%, and
peak-location difference ≤min(2 Hz, 1% of peak frequency), peak
displacement-per-force difference ≤5%, and wrapped phase difference ≤5° at
resolved nonzero peaks. An absolute response floor for phase/relative error
away from peaks remains HUMAN_INPUT. Resolve the same resonance and output
convention; do not increase damping or smooth away a missed peak to pass.
These bound simulator decision error, not unknown physical joint damping.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted evidence, “matches the reference simulator” for this linear
support/forcing scope, not “matches reality” or full-machine positioning.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize refinement.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### uncertainty — SOURCE_EXTRACT

CalculiX static, eigen and harmonic reference with independent mesh/mode/grid
checks; its [official capability list](https://www.dhondt.de/ov_calcu.htm) and
[manual](https://www.dhondt.de/ccx_2.20.pdf) support the candidate route.
Pin build, license, CAD/mesher, element order, mass representation, modal
damping and complex-output conventions before any reference dispatch.

Analytical oscillator and unrelieved beam controls; three mesh levels and
12/24/48 retained modes where supported. Apply full convergence rungs only to
the nominal geometry at both damping extremes; the four other cases are coarse
diagnostics and cannot establish reference adequacy. Require eigenfrequency change≤1%,
peak amplitude change≤5%, peak location change≤min(2 Hz,1% of peak frequency),
phase change≤5° near nonzero peaks. Adaptively bracket each resonance; refine
frequency spacing to≤one tenth of its half-power bandwidth before a peak claim.
Check modal truncation independently of mesh. All static/eigen/harmonic process
launches count separately within36 attempts/12 node-hours/$30: six coarse cases
need18; oscillator/beam controls use4; two finer nominal meshes share static/
eigen solves between damping settings and use8; four additional modal-retention
and two frequency-refinement harmonic launches use6. Missing rungs mean
unresolved reference, not a claimed adequate grid or silently higher damping.

### Reference credibility target

**Buyer tool:** Ansys Mechanical modal/harmonic analysis is the assumed stage
designer's workflow, not a verified adoption claim. **Carbon reference:**
proposed CalculiX static/eigen/harmonic solves, **not the same tool**; exact
task build/decks remain packaging work. Tier 1 requires the buyer's actual
model, materials, supports, damping, mesh and extraction settings.

**Target tier:** Tier 2 for linear structural-design shortlisting. Tier 3
measured modal frequencies and force/response curves are required before
assembled-support precision reliance; full-machine settling, joints and
nonlinear dynamics remain excluded. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** published NAFEMS **P18.FV4** (cantilever with off-centre
point masses), **P18.FV73** (cantilevered thin square plate) and **R0016.5H**
(deep simply supported beam, harmonic forced response), identified in
[NAFEMS's code-verification catalogue](https://www.nafems.org/publications/code-verification/nastran-code-verification/).
Run the same benchmark definitions in CalculiX and Mechanical and compare
published reference quantities; the catalogue is not a Carbon/tool pass.
Add matched ribbed/relieved-plate static and harmonic witnesses at both damping
extremes, with identical force normalization/probes and adaptive resonance
resolution. Eigenfrequency agreement alone cannot establish FRF peak accuracy.

**Acceptance tolerance: HUMAN_INPUT.** Recommend eigen/peak frequency difference
≤1%, static-compliance difference ≤2%, mass difference ≤0.5%, and
peak-location difference ≤min(2 Hz, 1% of peak frequency), peak
displacement-per-force difference ≤5%, and wrapped phase difference ≤5° at
resolved nonzero peaks. An absolute response floor for phase/relative error
away from peaks remains HUMAN_INPUT. Resolve the same resonance and output
convention; do not increase damping or smooth away a missed peak to pass.
These bound simulator decision error, not unknown physical joint damping.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted evidence, “matches the reference simulator” for this linear
support/forcing scope, not “matches reality” or full-machine positioning.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize uncertainty.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### cost — SOURCE_EXTRACT

CalculiX static, eigen and harmonic reference with independent mesh/mode/grid
checks; its [official capability list](https://www.dhondt.de/ov_calcu.htm) and
[manual](https://www.dhondt.de/ccx_2.20.pdf) support the candidate route.
Pin build, license, CAD/mesher, element order, mass representation, modal
damping and complex-output conventions before any reference dispatch.

Analytical oscillator and unrelieved beam controls; three mesh levels and
12/24/48 retained modes where supported. Apply full convergence rungs only to
the nominal geometry at both damping extremes; the four other cases are coarse
diagnostics and cannot establish reference adequacy. Require eigenfrequency change≤1%,
peak amplitude change≤5%, peak location change≤min(2 Hz,1% of peak frequency),
phase change≤5° near nonzero peaks. Adaptively bracket each resonance; refine
frequency spacing to≤one tenth of its half-power bandwidth before a peak claim.
Check modal truncation independently of mesh. All static/eigen/harmonic process
launches count separately within36 attempts/12 node-hours/$30: six coarse cases
need18; oscillator/beam controls use4; two finer nominal meshes share static/
eigen solves between damping settings and use8; four additional modal-retention
and two frequency-refinement harmonic launches use6. Missing rungs mean
unresolved reference, not a claimed adequate grid or silently higher damping.

### Reference credibility target

**Buyer tool:** Ansys Mechanical modal/harmonic analysis is the assumed stage
designer's workflow, not a verified adoption claim. **Carbon reference:**
proposed CalculiX static/eigen/harmonic solves, **not the same tool**; exact
task build/decks remain packaging work. Tier 1 requires the buyer's actual
model, materials, supports, damping, mesh and extraction settings.

**Target tier:** Tier 2 for linear structural-design shortlisting. Tier 3
measured modal frequencies and force/response curves are required before
assembled-support precision reliance; full-machine settling, joints and
nonlinear dynamics remain excluded. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** published NAFEMS **P18.FV4** (cantilever with off-centre
point masses), **P18.FV73** (cantilevered thin square plate) and **R0016.5H**
(deep simply supported beam, harmonic forced response), identified in
[NAFEMS's code-verification catalogue](https://www.nafems.org/publications/code-verification/nastran-code-verification/).
Run the same benchmark definitions in CalculiX and Mechanical and compare
published reference quantities; the catalogue is not a Carbon/tool pass.
Add matched ribbed/relieved-plate static and harmonic witnesses at both damping
extremes, with identical force normalization/probes and adaptive resonance
resolution. Eigenfrequency agreement alone cannot establish FRF peak accuracy.

**Acceptance tolerance: HUMAN_INPUT.** Recommend eigen/peak frequency difference
≤1%, static-compliance difference ≤2%, mass difference ≤0.5%, and
peak-location difference ≤min(2 Hz, 1% of peak frequency), peak
displacement-per-force difference ≤5%, and wrapped phase difference ≤5° at
resolved nonzero peaks. An absolute response floor for phase/relative error
away from peaks remains HUMAN_INPUT. Resolve the same resonance and output
convention; do not increase damping or smooth away a missed peak to pass.
These bound simulator decision error, not unknown physical joint damping.

**Claim boundary:** [common credibility contract](reference-credibility.md).
After accepted evidence, “matches the reference simulator” for this linear
support/forcing scope, not “matches reality” or full-machine positioning.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize cost.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 6. Output and measurement contract

### outputs — SOURCE_EXTRACT

Complex z displacement / N at tip-pad centroid and on a2×2-mm solid top-surface
probe centered at x=L/2,y=W/2−8 mm,z=plate top (outside relief/ribs);
mass, static compliance, modal frequencies, full adaptive frequency grid and
band maximum/location. Declare harmonic exp(+i omega t) convention; convert
solver phase consistently. Retain the curve and peaks, not a scalar-only grade.
Every damping condition must meet constraints; good nonresonant values cannot
offset a missed peak. Reference failure is missing evidence, not candidate failure.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize outputs.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### hard_limits — SOURCE_EXTRACT

Complex z displacement / N at tip-pad centroid and on a2×2-mm solid top-surface
probe centered at x=L/2,y=W/2−8 mm,z=plate top (outside relief/ribs);
mass, static compliance, modal frequencies, full adaptive frequency grid and
band maximum/location. Declare harmonic exp(+i omega t) convention; convert
solver phase consistently. Retain the curve and peaks, not a scalar-only grade.
Every damping condition must meet constraints; good nonresonant values cannot
offset a missed peak. Reference failure is missing evidence, not candidate failure.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize hard_limits.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### objective — SOURCE_EXTRACT

Complex z displacement / N at tip-pad centroid and on a2×2-mm solid top-surface
probe centered at x=L/2,y=W/2−8 mm,z=plate top (outside relief/ribs);
mass, static compliance, modal frequencies, full adaptive frequency grid and
band maximum/location. Declare harmonic exp(+i omega t) convention; convert
solver phase consistently. Retain the curve and peaks, not a scalar-only grade.
Every damping condition must meet constraints; good nonresonant values cannot
offset a missed peak. Reference failure is missing evidence, not candidate failure.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize objective.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 7. Construction contract

### vocabulary — SOURCE_EXTRACT

Prepared Level-0 target: deterministic geometry-to-response ROM/interpolation
with declarative recipes; no runtime ID/recipe permission change. Exact TRAIN
provenance, retained-mode and resource vocabulary waits for its ticket and
training-budget study. No evaluator code or protected data in reconstruction.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize vocabulary.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### training — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize training.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### permissions — SOURCE_EXTRACT

Prepared Level-0 target: deterministic geometry-to-response ROM/interpolation
with declarative recipes; no runtime ID/recipe permission change. Exact TRAIN
provenance, retained-mode and resource vocabulary waits for its ticket and
training-budget study. No evaluator code or protected data in reconstruction.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: construction/security owner. Needed: Confirm applicability and authorize permissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 8. Research kit

### public_kit — SOURCE_EXTRACT

Public CAD/mesh/response docs, own-seed generation/reference and incomplete
practice; Euler–Bernoulli beam, 6/12-mode reduction and reused-factorization
baselines. Charge their factorization/setup/search costs. Reuse authoring,
custody and reconstruction; create the structural domain adapter, not a new judge.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize public_kit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### baseline — SOURCE_EXTRACT

Public CAD/mesh/response docs, own-seed generation/reference and incomplete
practice; Euler–Bernoulli beam, 6/12-mode reduction and reused-factorization
baselines. Charge their factorization/setup/search costs. Reuse authoring,
custody and reconstruction; create the structural domain adapter, not a new judge.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize baseline.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### rights — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize rights.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 9. Evidence plan

### panel — SOURCE_EXTRACT

First demonstrate peak resolution. Later preregister designs, search budgets
and decision measures before solves; hold out whole geometries, not frequencies
on the same curve. Fresh confirmation and physical modal tests are independent
later evidence. If modal reduction already solves this job cheaply, park it
instead of selecting a grid to manufacture a learned advantage.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize panel.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### controls — SOURCE_EXTRACT

First demonstrate peak resolution. Later preregister designs, search budgets
and decision measures before solves; hold out whole geometries, not frequencies
on the same curve. Fresh confirmation and physical modal tests are independent
later evidence. If modal reduction already solves this job cheaply, park it
instead of selecting a grid to manufacture a learned advantage.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize controls.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### confirmation — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize confirmation.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 10. Readiness and claim record

### readiness — SOURCE_EXTRACT

Current prospective T2: [buyer value/cost scorecard](../value-cost/f08.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report resolved worst-band compliance and stiffness/mass margins across the mandatory
damping panel, not an eigenfrequency-only or coarse-grid pass.
No favorable redraw, exposure reset, solver grant or qualification follows.


Selected requirements, offline beam/mass screen only. New modal/harmonic
reference, numerical adequacy, kit and reconstruction are NOT_DEMONSTRATED.
Next: exact CAD/support/damping deck and analytic controls under stage permission.
No machine performance, physical damping, qualification or launch claim.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize readiness.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### owners — SOURCE_EXTRACT

Current prospective T2: [buyer value/cost scorecard](../value-cost/f08.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report resolved worst-band compliance and stiffness/mass margins across the mandatory
damping panel, not an eigenfrequency-only or coarse-grid pass.
No favorable redraw, exposure reset, solver grant or qualification follows.


Selected requirements, offline beam/mass screen only. New modal/harmonic
reference, numerical adequacy, kit and reconstruction are NOT_DEMONSTRATED.
Next: exact CAD/support/damping deck and analytic controls under stage permission.
No machine performance, physical damping, qualification or launch claim.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize owners.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### next_gate — SOURCE_EXTRACT

Current prospective T2: [buyer value/cost scorecard](../value-cost/f08.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report resolved worst-band compliance and stiffness/mass margins across the mandatory
damping panel, not an eigenfrequency-only or coarse-grid pass.
No favorable redraw, exposure reset, solver grant or qualification follows.


Selected requirements, offline beam/mass screen only. New modal/harmonic
reference, numerical adequacy, kit and reconstruction are NOT_DEMONSTRATED.
Next: exact CAD/support/damping deck and analytic controls under stage permission.
No machine performance, physical damping, qualification or launch claim.

Source: `docs/development/challenge_pipeline/round1/f08-resonance-structure.md` sha256 `5387772c58e963c8cfa50bcb09529a0299fd7e12a4266953b2ecae76aecb7404`.
Owner: science/product owner. Needed: Confirm applicability and authorize next_gate.
Held closed: No runtime registration, bank draw, execution, qualification or spend.
