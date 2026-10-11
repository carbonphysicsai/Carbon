# f13 — generated common packet draft

DEVELOPMENT / DRAFT_ONLY. SOURCE_EXTRACT means verified bytes, not approval.
Every unsourced field is HUMAN_INPUT. No runtime or qualification authority.

## 1. Engineering job

### buyer — HUMAN_INPUT

Compressor-skid acoustic engineer (internal mock customer)

Owner: science/product owner. Needed: Confirm applicability and authorize buyer.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### decision — HUMAN_INPUT

Choose compact silencer geometry with admissible full-band transmission loss, not installed-noise compliance

Owner: science/product owner. Needed: Confirm applicability and authorize decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### value — SOURCE_EXTRACT

Hypothetical compressor-skid acoustic engineer: select a two-chamber passive
silencer within140-mm diameter/300-mm length that maximizes band p10 transmission
loss; buyer target p10≥5 dB. Also report minimum TL and every narrow failure.
This is a packaging/attenuation decision, not compressor-source prediction,
operating pressure-drop, flow acoustics or a noise-regulation compliance claim.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize value.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### wrong_decision — SOURCE_EXTRACT

Hypothetical compressor-skid acoustic engineer: select a two-chamber passive
silencer within140-mm diameter/300-mm length that maximizes band p10 transmission
loss; buyer target p10≥5 dB. Also report minimum TL and every narrow failure.
This is a packaging/attenuation decision, not compressor-source prediction,
operating pressure-drop, flow acoustics or a noise-regulation compliance claim.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize wrong_decision.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### exclusions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize exclusions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 2. Physical system

### physics — HUMAN_INPUT

Linear acoustic frequency response; proposed coaxial reduction not yet adopted

Owner: science/product owner. Needed: Confirm applicability and authorize physics.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### geometry — SOURCE_EXTRACT

Rigid-walled 3D chambers, radii55–70 mm, lengths40–110 mm; coaxial50-mm-ID inlet
and outlet. Inter-chamber neck radius20 mm,length10–50 mm, lateral x offset
0–25 mm; require≥10-mm clearance from chamber walls. Package dimensions include
the two chambers, neck and two fixed10-mm port stubs. No shell vibration,
absorption or mean flow. Synthetic air rho1.2 kg/m³,c343 m/s. Unit incident
plane-wave acoustic power, matched outlet impedance rho*c. Frequency500–2500 Hz.
Staggering is a physical design action; coaxial geometry is a strong control.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize geometry.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### materials — SOURCE_EXTRACT

Rigid-walled 3D chambers, radii55–70 mm, lengths40–110 mm; coaxial50-mm-ID inlet
and outlet. Inter-chamber neck radius20 mm,length10–50 mm, lateral x offset
0–25 mm; require≥10-mm clearance from chamber walls. Package dimensions include
the two chambers, neck and two fixed10-mm port stubs. No shell vibration,
absorption or mean flow. Synthetic air rho1.2 kg/m³,c343 m/s. Unit incident
plane-wave acoustic power, matched outlet impedance rho*c. Frequency500–2500 Hz.
Staggering is a physical design action; coaxial geometry is a strong control.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize materials.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### conditions — SOURCE_EXTRACT

Rigid-walled 3D chambers, radii55–70 mm, lengths40–110 mm; coaxial50-mm-ID inlet
and outlet. Inter-chamber neck radius20 mm,length10–50 mm, lateral x offset
0–25 mm; require≥10-mm clearance from chamber walls. Package dimensions include
the two chambers, neck and two fixed10-mm port stubs. No shell vibration,
absorption or mean flow. Synthetic air rho1.2 kg/m³,c343 m/s. Unit incident
plane-wave acoustic power, matched outlet impedance rho*c. Frequency500–2500 Hz.
Staggering is a physical design action; coaxial geometry is a strong control.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize conditions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### omissions — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize omissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 3. Population P, Q and w

### P — SOURCE_EXTRACT

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

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize P.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### Q — SOURCE_EXTRACT

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

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize Q.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### w — SOURCE_EXTRACT

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

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize w.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### strata — SOURCE_EXTRACT

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

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize strata.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### independent_unit — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize independent_unit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 4. Case contract

### case_identity — SOURCE_EXTRACT

Validate3D geometry, neck clearance, positive volumes and total≤300-mm length.
Bind source/port planes, normals, impedance, material and extraction identity;
refuse geometries rather than clip their offsets. Retain complex transfer
orientation. Public cases are independent from later operator-side hidden draws.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize case_identity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### validity — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize validity.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### disclosure — SOURCE_EXTRACT

Validate3D geometry, neck clearance, positive volumes and total≤300-mm length.
Bind source/port planes, normals, impedance, material and extraction identity;
refuse geometries rather than clip their offsets. Retain complex transfer
orientation. Public cases are independent from later operator-side hidden draws.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize disclosure.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 5. Reference policy

### solver — SOURCE_EXTRACT

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

### Reference credibility target

**Buyer tool:** COMSOL Acoustics Module is the assumed skid designer's
linear-acoustics workflow, not an adoption finding. **Carbon reference:**
proposed Elmer 3D Helmholtz finite elements, **not the same tool**; the exact
task environment/deck/extractor remains unproven packaging. Tier 1 requires
the buyer's own tool and exact ports, impedance, mesh and power conventions.

**Target tier:** Tier 2 for offline passive-silencer simulation selection.
Tier 3 calibrated duct-rig transmission measurements would be required before
purchasing against a physical attenuation promise. Operating-flow/source-noise
or regulatory claims remain separate. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** COMSOL's published
[Absorptive Muffler](https://doc.comsol.com/6.3/doc/com.comsol.help.models.aco.absorptive_muffler/absorptive_muffler.html)
**unlined reactive variant**, plus the packet's straight-duct and coaxial
single-chamber transfer-matrix controls. Freeze medium, rigid walls, port
conditions and geometry in both tools. Do not import porous-liner absorption
into this lossless scope. Add matched offset two-chamber witnesses above the
chamber-mode cutoffs across the complete adaptive band; a three-frequency
preflight cannot establish TL p10. Perforated/shell/flow muffler examples or
their lab comparisons do not confer evidence for this different model.

**Acceptance tolerance: HUMAN_INPUT.** Recommend pointwise transmission-loss
difference ≤1.0 dB on the resolved common band, interval-weighted p10/minimum
differences ≤1.0 dB and resonance-location difference ≤10 Hz. At transmission
zeros/deep notches, a separately accepted absolute transmitted-power floor and
complex-transfer comparison are HUMAN_INPUT; retain the raw notch instead of
clipping dB to force agreement. A 1-dB error allocation is not permission to
lower the 5-dB buyer target or count non-passive solutions as credible.

**Claim boundary:** [common credibility contract](reference-credibility.md).
Accepted Tier 2 permits “matches the reference simulator” for these passive
transmission cases, never “matches reality”, compressor noise reduction,
operating pressure economics or compliance without the relevant evidence.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize solver.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### pins — SOURCE_EXTRACT

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

### Reference credibility target

**Buyer tool:** COMSOL Acoustics Module is the assumed skid designer's
linear-acoustics workflow, not an adoption finding. **Carbon reference:**
proposed Elmer 3D Helmholtz finite elements, **not the same tool**; the exact
task environment/deck/extractor remains unproven packaging. Tier 1 requires
the buyer's own tool and exact ports, impedance, mesh and power conventions.

**Target tier:** Tier 2 for offline passive-silencer simulation selection.
Tier 3 calibrated duct-rig transmission measurements would be required before
purchasing against a physical attenuation promise. Operating-flow/source-noise
or regulatory claims remain separate. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** COMSOL's published
[Absorptive Muffler](https://doc.comsol.com/6.3/doc/com.comsol.help.models.aco.absorptive_muffler/absorptive_muffler.html)
**unlined reactive variant**, plus the packet's straight-duct and coaxial
single-chamber transfer-matrix controls. Freeze medium, rigid walls, port
conditions and geometry in both tools. Do not import porous-liner absorption
into this lossless scope. Add matched offset two-chamber witnesses above the
chamber-mode cutoffs across the complete adaptive band; a three-frequency
preflight cannot establish TL p10. Perforated/shell/flow muffler examples or
their lab comparisons do not confer evidence for this different model.

**Acceptance tolerance: HUMAN_INPUT.** Recommend pointwise transmission-loss
difference ≤1.0 dB on the resolved common band, interval-weighted p10/minimum
differences ≤1.0 dB and resonance-location difference ≤10 Hz. At transmission
zeros/deep notches, a separately accepted absolute transmitted-power floor and
complex-transfer comparison are HUMAN_INPUT; retain the raw notch instead of
clipping dB to force agreement. A 1-dB error allocation is not permission to
lower the 5-dB buyer target or count non-passive solutions as credible.

**Claim boundary:** [common credibility contract](reference-credibility.md).
Accepted Tier 2 permits “matches the reference simulator” for these passive
transmission cases, never “matches reality”, compressor noise reduction,
operating pressure economics or compliance without the relevant evidence.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize pins.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### refinement — SOURCE_EXTRACT

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

### Reference credibility target

**Buyer tool:** COMSOL Acoustics Module is the assumed skid designer's
linear-acoustics workflow, not an adoption finding. **Carbon reference:**
proposed Elmer 3D Helmholtz finite elements, **not the same tool**; the exact
task environment/deck/extractor remains unproven packaging. Tier 1 requires
the buyer's own tool and exact ports, impedance, mesh and power conventions.

**Target tier:** Tier 2 for offline passive-silencer simulation selection.
Tier 3 calibrated duct-rig transmission measurements would be required before
purchasing against a physical attenuation promise. Operating-flow/source-noise
or regulatory claims remain separate. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** COMSOL's published
[Absorptive Muffler](https://doc.comsol.com/6.3/doc/com.comsol.help.models.aco.absorptive_muffler/absorptive_muffler.html)
**unlined reactive variant**, plus the packet's straight-duct and coaxial
single-chamber transfer-matrix controls. Freeze medium, rigid walls, port
conditions and geometry in both tools. Do not import porous-liner absorption
into this lossless scope. Add matched offset two-chamber witnesses above the
chamber-mode cutoffs across the complete adaptive band; a three-frequency
preflight cannot establish TL p10. Perforated/shell/flow muffler examples or
their lab comparisons do not confer evidence for this different model.

**Acceptance tolerance: HUMAN_INPUT.** Recommend pointwise transmission-loss
difference ≤1.0 dB on the resolved common band, interval-weighted p10/minimum
differences ≤1.0 dB and resonance-location difference ≤10 Hz. At transmission
zeros/deep notches, a separately accepted absolute transmitted-power floor and
complex-transfer comparison are HUMAN_INPUT; retain the raw notch instead of
clipping dB to force agreement. A 1-dB error allocation is not permission to
lower the 5-dB buyer target or count non-passive solutions as credible.

**Claim boundary:** [common credibility contract](reference-credibility.md).
Accepted Tier 2 permits “matches the reference simulator” for these passive
transmission cases, never “matches reality”, compressor noise reduction,
operating pressure economics or compliance without the relevant evidence.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize refinement.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### uncertainty — SOURCE_EXTRACT

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

### Reference credibility target

**Buyer tool:** COMSOL Acoustics Module is the assumed skid designer's
linear-acoustics workflow, not an adoption finding. **Carbon reference:**
proposed Elmer 3D Helmholtz finite elements, **not the same tool**; the exact
task environment/deck/extractor remains unproven packaging. Tier 1 requires
the buyer's own tool and exact ports, impedance, mesh and power conventions.

**Target tier:** Tier 2 for offline passive-silencer simulation selection.
Tier 3 calibrated duct-rig transmission measurements would be required before
purchasing against a physical attenuation promise. Operating-flow/source-noise
or regulatory claims remain separate. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** COMSOL's published
[Absorptive Muffler](https://doc.comsol.com/6.3/doc/com.comsol.help.models.aco.absorptive_muffler/absorptive_muffler.html)
**unlined reactive variant**, plus the packet's straight-duct and coaxial
single-chamber transfer-matrix controls. Freeze medium, rigid walls, port
conditions and geometry in both tools. Do not import porous-liner absorption
into this lossless scope. Add matched offset two-chamber witnesses above the
chamber-mode cutoffs across the complete adaptive band; a three-frequency
preflight cannot establish TL p10. Perforated/shell/flow muffler examples or
their lab comparisons do not confer evidence for this different model.

**Acceptance tolerance: HUMAN_INPUT.** Recommend pointwise transmission-loss
difference ≤1.0 dB on the resolved common band, interval-weighted p10/minimum
differences ≤1.0 dB and resonance-location difference ≤10 Hz. At transmission
zeros/deep notches, a separately accepted absolute transmitted-power floor and
complex-transfer comparison are HUMAN_INPUT; retain the raw notch instead of
clipping dB to force agreement. A 1-dB error allocation is not permission to
lower the 5-dB buyer target or count non-passive solutions as credible.

**Claim boundary:** [common credibility contract](reference-credibility.md).
Accepted Tier 2 permits “matches the reference simulator” for these passive
transmission cases, never “matches reality”, compressor noise reduction,
operating pressure economics or compliance without the relevant evidence.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize uncertainty.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### cost — SOURCE_EXTRACT

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

### Reference credibility target

**Buyer tool:** COMSOL Acoustics Module is the assumed skid designer's
linear-acoustics workflow, not an adoption finding. **Carbon reference:**
proposed Elmer 3D Helmholtz finite elements, **not the same tool**; the exact
task environment/deck/extractor remains unproven packaging. Tier 1 requires
the buyer's own tool and exact ports, impedance, mesh and power conventions.

**Target tier:** Tier 2 for offline passive-silencer simulation selection.
Tier 3 calibrated duct-rig transmission measurements would be required before
purchasing against a physical attenuation promise. Operating-flow/source-noise
or regulatory claims remain separate. **Credibility evidence: NOT_DEMONSTRATED**.

**Benchmark cases:** COMSOL's published
[Absorptive Muffler](https://doc.comsol.com/6.3/doc/com.comsol.help.models.aco.absorptive_muffler/absorptive_muffler.html)
**unlined reactive variant**, plus the packet's straight-duct and coaxial
single-chamber transfer-matrix controls. Freeze medium, rigid walls, port
conditions and geometry in both tools. Do not import porous-liner absorption
into this lossless scope. Add matched offset two-chamber witnesses above the
chamber-mode cutoffs across the complete adaptive band; a three-frequency
preflight cannot establish TL p10. Perforated/shell/flow muffler examples or
their lab comparisons do not confer evidence for this different model.

**Acceptance tolerance: HUMAN_INPUT.** Recommend pointwise transmission-loss
difference ≤1.0 dB on the resolved common band, interval-weighted p10/minimum
differences ≤1.0 dB and resonance-location difference ≤10 Hz. At transmission
zeros/deep notches, a separately accepted absolute transmitted-power floor and
complex-transfer comparison are HUMAN_INPUT; retain the raw notch instead of
clipping dB to force agreement. A 1-dB error allocation is not permission to
lower the 5-dB buyer target or count non-passive solutions as credible.

**Claim boundary:** [common credibility contract](reference-credibility.md).
Accepted Tier 2 permits “matches the reference simulator” for these passive
transmission cases, never “matches reality”, compressor noise reduction,
operating pressure economics or compliance without the relevant evidence.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize cost.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 6. Output and measurement contract

### outputs — SOURCE_EXTRACT

Complex R/T at fixed port planes; incident/reflected/transmitted acoustic
powers, residual and TL=−10 log10(Ptrans/Pinc). No pressure-amplitude ratio
masquerading as power TL. Report interval-weighted p10 (lower quantile), mean,
minimum and full refined curve. Energy outside tolerance is unresolved reference.
Target is not an adopted official score or proof that every frequency meets5 dB.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize outputs.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### hard_limits — SOURCE_EXTRACT

Complex R/T at fixed port planes; incident/reflected/transmitted acoustic
powers, residual and TL=−10 log10(Ptrans/Pinc). No pressure-amplitude ratio
masquerading as power TL. Report interval-weighted p10 (lower quantile), mean,
minimum and full refined curve. Energy outside tolerance is unresolved reference.
Target is not an adopted official score or proof that every frequency meets5 dB.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize hard_limits.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### objective — SOURCE_EXTRACT

Complex R/T at fixed port planes; incident/reflected/transmitted acoustic
powers, residual and TL=−10 log10(Ptrans/Pinc). No pressure-amplitude ratio
masquerading as power TL. Report interval-weighted p10 (lower quantile), mean,
minimum and full refined curve. Energy outside tolerance is unresolved reference.
Target is not an adopted official score or proof that every frequency meets5 dB.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize objective.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 7. Construction contract

### vocabulary — SOURCE_EXTRACT

Prepared Level-0 target: declarative geometry-to-complex-transfer model with
deterministic reconstruction; exact grammar/data permissions/runtime limits
await registration and budget study. No inference-time evaluator access.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize vocabulary.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### training — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize training.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### permissions — SOURCE_EXTRACT

Prepared Level-0 target: declarative geometry-to-complex-transfer model with
deterministic reconstruction; exact grammar/data permissions/runtime limits
await registration and budget study. No inference-time evaluator access.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: construction/security owner. Needed: Confirm applicability and authorize permissions.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 8. Research kit

### public_kit — SOURCE_EXTRACT

Own-seed geometry generator/reference, transfer-matrix and retained-mode
baselines, source/termination/normalization docs and incomplete public practice.
Reuse shared evidence/rebuild infrastructure; create acoustics-specific decks
and extraction. Never ship protected EVAL/STRESS, seeds or labels to pods.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize public_kit.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### baseline — SOURCE_EXTRACT

Own-seed geometry generator/reference, transfer-matrix and retained-mode
baselines, source/termination/normalization docs and incomplete public practice.
Reuse shared evidence/rebuild infrastructure; create acoustics-specific decks
and extraction. Never ship protected EVAL/STRESS, seeds or labels to pods.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize baseline.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### rights — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize rights.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 9. Evidence plan

### panel — SOURCE_EXTRACT

Controls before volume. Do not compare/rank full-band decisions from this
first-round sparse reference preflight. Compare equal decision/query budgets including baseline
setup and failed attempts. Park a topology that transfer/modal methods solve
adequately cheaply; do not add asymmetry solely to favor a model. Later fresh
confirmation and calibrated duct measurements require new custody/rights plans.
Operating-flow extensions are a new contract, not a first-round grant.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize panel.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### controls — SOURCE_EXTRACT

Controls before volume. Do not compare/rank full-band decisions from this
first-round sparse reference preflight. Compare equal decision/query budgets including baseline
setup and failed attempts. Park a topology that transfer/modal methods solve
adequately cheaply; do not add asymmetry solely to favor a model. Later fresh
confirmation and calibrated duct measurements require new custody/rights plans.
Operating-flow extensions are a new contract, not a first-round grant.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize controls.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### confirmation — HUMAN_INPUT

HUMAN_INPUT: no value supplied.

Owner: science/product owner. Needed: Confirm applicability and authorize confirmation.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

## 10. Readiness and claim record

### readiness — SOURCE_EXTRACT

Current prospective T2: [buyer value/cost scorecard](../value-cost/f13.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report interval-weighted full-band p10/packaging margins; sparse frequencies or
incomplete multi-frequency curves cannot establish design value.
No favorable redraw, exposure reset, solver grant or qualification follows.


Selected requirements and an analytical mode-cutoff screen only. 3D acoustic
reference adequacy is NOT_DEMONSTRATED. Next: exact impedance/power conventions,
CAD and analytic controls under stage permission. No source-noise reduction,
operating economics, compliance, physical qualification or launch claim.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize readiness.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### owners — SOURCE_EXTRACT

Current prospective T2: [buyer value/cost scorecard](../value-cost/f13.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report interval-weighted full-band p10/packaging margins; sparse frequencies or
incomplete multi-frequency curves cannot establish design value.
No favorable redraw, exposure reset, solver grant or qualification follows.


Selected requirements and an analytical mode-cutoff screen only. 3D acoustic
reference adequacy is NOT_DEMONSTRATED. Next: exact impedance/power conventions,
CAD and analytic controls under stage permission. No source-noise reduction,
operating economics, compliance, physical qualification or launch claim.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize owners.
Held closed: No runtime registration, bank draw, execution, qualification or spend.

### next_gate — SOURCE_EXTRACT

Current prospective T2: [buyer value/cost scorecard](../value-cost/f13.md)
and [owner framework](../value-cost/README.md). Require at least five feasible
and five distinct near-limit infeasible actions per mandatory stratum. Report
the overall fraction; it is not a gate. Other value checks still require
evidence. Refinement/acceptance remains HUMAN_INPUT; no new runtime authority.
The original fraction-based observations below retain their historical meaning.

**Before any new hidden bank:** the owner-selected [four-check value prerequisite](../question-laws/value-check-v1.md)
requires per-stratum discrimination and meaningful buyer-unit spread, one
complete feasible action, and changing best/equivalent answers. Numeric
thresholds remain HUMAN_INPUT recommendations; receipt **NOT_DEMONSTRATED**.
For this buyer, report interval-weighted full-band p10/packaging margins; sparse frequencies or
incomplete multi-frequency curves cannot establish design value.
No favorable redraw, exposure reset, solver grant or qualification follows.


Selected requirements and an analytical mode-cutoff screen only. 3D acoustic
reference adequacy is NOT_DEMONSTRATED. Next: exact impedance/power conventions,
CAD and analytic controls under stage permission. No source-noise reduction,
operating economics, compliance, physical qualification or launch claim.

Source: `docs/development/challenge_pipeline/round1/f13-compressor-silencer.md` sha256 `397361ad8340ccbc19f07e2a025fb9c9c29934a9b1159e0c7000fc1e061fdde0`.
Owner: science/product owner. Needed: Confirm applicability and authorize next_gate.
Held closed: No runtime registration, bank draw, execution, qualification or spend.
