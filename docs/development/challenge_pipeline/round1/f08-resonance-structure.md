# f08 — resonance-resistant stage support, customer round 1

Authority and numeric source: [index](README.md), [sheet](requirements.json).

## 1. Engineering job

Hypothetical precision-stage engineer: select a light ribbed support minimizing
worst-band tip motion per unit load. Buyer constraints: mass≤0.45 kg, static
tip compliance≤0.03 mm/N, and dynamic peak≤0.15 mm/N throughout 80–600 Hz for
all declared damping conditions. A missed peak causes positioning error.
No full-machine settling time, throughput, fatigue, strength or joint certification.

## 2. Physical system

Cantilever rectangular plate: length180–260, width60–100, thickness4–8 mm. Two
longitudinal upper ribs, height8–16/thickness3–5 mm, at y=±width/4. Centered
through-plate cable relief: length20–60 mm in x and width20 mm; rounded 3-mm
corners, no rib intersection, ligament≥6 mm. Synthetic isotropic Al-like law:
E70 GPa, nu0.33, rho2700 kg/m³. Root x=0 fully clamped. Unit z-directed force
uniform on the last 5 mm×central10 mm tip pad, retaining resultant1 N.
Constant modal damping ratio0.005,0.01 or0.02 (not an inferred real joint law).

## 3. Population P, Q and w

Geometry is a design action. Reference-input geometry law: independent uniform
grammar parameters conditioned on valid shape. Exogenous `P_dev` is uniform
over three modal damping ratios; frequency is an adversarial peak search, not
a random customer state. Later decision comparisons weight damping1/3 and
report worst condition separately. Q feasibility uses three fixed geometries
(low/nominal/high rib at length220,width80,thickness6,relief40 mm) at damping
0.005 and0.02. No population estimate from six diagnostic cases.

## 4. Case contract

Bind complete CAD, material, clamp/load pad, damping, extraction coordinates
and units; refuse intersecting ribs/relief, invalid mesh or insufficient
ligaments. Reject rather than silently repair geometry. Canonical case/solver/
deck/extractor identities remain separate. Public cases never reveal hidden IDs.

## 5. Reference policy

CalculiX static, eigen and harmonic reference with independent mesh/mode/grid
checks; its [official capability list](https://www.dhondt.de/ov_calcu.htm) and
[manual](https://www.dhondt.de/ccx_2.20.pdf) support the candidate route.
Pin build, license, CAD/mesher, element order, mass representation, modal
damping and complex-output conventions before any reference dispatch.

Analytical oscillator and unrelieved beam controls; three mesh levels and
12/24/48 retained modes where supported. Require eigenfrequency change≤1%,
peak amplitude change≤5%, peak location change≤min(2 Hz,1% of peak frequency),
phase change≤5° near nonzero peaks. Adaptively bracket each resonance; refine
frequency spacing to≤one tenth of its half-power bandwidth before a peak claim.
Check modal truncation independently of mesh. All static/eigen/harmonic process
launches count separately within36 attempts/12 node-hours/$30; six diagnostic
cases need18 launches, leaving controls/refinements finite. Missing rungs mean
unresolved reference, not a claimed adequate grid or silently higher damping.

## 6. Output and measurement contract

Complex z displacement / N at tip-pad centroid and midspan reference point;
mass, static compliance, modal frequencies, full adaptive frequency grid and
band maximum/location. Declare harmonic exp(+i omega t) convention; convert
solver phase consistently. Retain the curve and peaks, not a scalar-only grade.
Every damping condition must meet constraints; good nonresonant values cannot
offset a missed peak. Reference failure is missing evidence, not candidate failure.

## 7. Construction contract

Prepared Level-0 target: deterministic geometry-to-response ROM/interpolation
with declarative recipes; no runtime ID/recipe permission change. Exact TRAIN
provenance, retained-mode and resource vocabulary waits for its ticket and
training-budget study. No evaluator code or protected data in reconstruction.

## 8. Research kit

Public CAD/mesh/response docs, own-seed generation/reference and incomplete
practice; Euler–Bernoulli beam, 6/12-mode reduction and reused-factorization
baselines. Charge their factorization/setup/search costs. Reuse authoring,
custody and reconstruction; create the structural domain adapter, not a new judge.

## 9. Evidence plan

First demonstrate peak resolution. Later preregister designs, search budgets
and decision measures before solves; hold out whole geometries, not frequencies
on the same curve. Fresh confirmation and physical modal tests are independent
later evidence. If modal reduction already solves this job cheaply, park it
instead of selecting a grid to manufacture a learned advantage.

## 10. Readiness and claim record

Selected requirements, offline beam/mass screen only. New modal/harmonic
reference, numerical adequacy, kit and reconstruction are NOT_DEMONSTRATED.
Next: exact CAD/support/damping deck and analytic controls under stage permission.
No machine performance, physical damping, qualification or launch claim.
