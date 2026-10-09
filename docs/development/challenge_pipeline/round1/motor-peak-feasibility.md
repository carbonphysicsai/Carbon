# Motor peak feasibility — keep 12 N·m; search the magnetic bottleneck

**DEVELOPMENT, SPECIFIED; analysis only.** Owner request MOTOR-PEAK-FEASIBILITY-01,
2026-10-09. No reference solves or spend. This supplements [Motor v2](motor-precision-joint-v2.md)
and [#922's prospective law](https://github.com/carbonphysicsai/Carbon/pull/922),
without changing either. [Arithmetic sheet](motor-peak-feasibility.json) is
not reference truth, a score input or an execution plan.

## Conclusion and the buyer problem

**12 N·m is not analytically excluded by the current 2D grammar, but is not
demonstrated.** A high-tooth-width corner gives an optimistic saturation screen
of roughly 13.4–14.9 N·m after 4° skew. That is little margin for leakage,
armature reaction, tolerances or real end effects. The published best observed
peak is 9.8953 N·m. Do not call the screen a feasible motor or a proven maximum.
Catalogue evidence makes 12 N·m an ambitious compact direct-drive target, not
an obviously impossible buyer ask. Keep 12 until the authorized search reports.

The buyer needs **one geometry** that holds 6 N·m smoothly, accelerates at
12 N·m, and backdrives within 0.05 N·m cogging. Finding only a high mean peak
is insufficient: peak ripple must also be ≤5% **and** ≤0.60 N·m; holding ripple
≤5% **and** ≤0.30 N·m. A static magnetic curve cannot establish a 2-s rating,
continuous holding temperature, inverter capability or robot tip accuracy.

## 1. Inputs and sizing calculation

Public acquisition pin: [66ea509888e4ef0f5ac08750554db744b56b92bf](https://github.com/carbonphysicsai/Carbon/tree/66ea509888e4ef0f5ac08750554db744b56b92bf/scripts/dev/motor/feasibility02).
Its `topology.py`, `run.py`, `stages.py` are unchanged from the S3 evidence pin
`5f373b199be8f8fc12c7c3e29d345e35d1c7832a`. The registry defines 10p/12s,
double-layer tooth winding, fundamental winding factor 0.9330127; six coordinates:
magnet 1.5–4 mm, coverage 0.65–0.95, gap 0.3–1 mm, tooth fraction 0.20–0.40,
opening fraction 0.03–0.12, slot-bottom radius 34–42 mm; skew 0/2/4°.
Fixed OD 92 mm, rotor surface radius 25.6 mm, active stack 35 mm. **35 mm is
active length, not complete installed length.** Tip/wedge 0.6/0.34 mm.

No named grades exist here: magnet `Br=1.2 T, mu_r=1`, no temperature or
demagnetization law; steel is generic Brauer iron, not M19 or another product.
The [main deck](../../../../carbon/motor/getdp.py) uses
`nu_b=100+10 exp(1.8 B²)`, with vacuum permeability in parallel. Relative
permeability is about 723/228/60/14 at 1.6/1.8/2.0/2.2 T. The 1.8–2.0 T
markers below are **screening assumptions, not hard saturation or safety limits**.

Use the coil polygon's exact shoelace area, not an annular sector. For Q=12
slots, `A_slot=2 A_side`, total source area `A_total=12 A_slot`.
J=15 A/mm² is **sinusoidal peak density over each model coil region**.
`run.params` chooses one-turn equivalent current `I=J A_side`; GetDP inserts
`turns*I/A_side`, so its source equals J. No second layer/fill/current factor
belongs in that source. Physical copper fill f would give peak copper density
`J/f`, RMS `J/(sqrt(2) f)`; e.g. f=0.5 implies 30 peak/21.2 RMS A/mm².
Fill, copper heating and cooling are not modeled or approved physical ratings.

For sinusoidal fundamental loading, mean shear is `tau=B1 K1/2` and
`T=2 pi r² L tau = pi D² L B1 K1/4`, with
`K1=k_w J A_total/(pi D)`, hence `T=k_w B1 D L J A_total/4`.
Here D is **mean air-gap diameter ~51.5 mm**, not stator OD. This is the usual
electric-loading/magnetic-loading D²L sizing; see [published sizing study §3,
equation 7](https://link.springer.com/article/10.1007/s42835-022-01322-w).
Our explicit current-sheet convention fixes the coefficient; apparent-power
formula conventions must not be copied as torque constants.

No-saturation field uses the [existing analytic baseline](../../../../carbon/motor/analytic.py):
`B_g=Br h_m/(h_m+k_c gap)`, `B1=(4/pi) B_g sin(pi coverage/2)`, Carter
coefficient from slot opening. It neglects finite iron reluctance, leakage,
armature reaction, waveform harmonics and cogging. It is optimistic sizing,
**not a mathematically certified global upper bound**.

For a tooth collecting one sinusoidal slot-pitch flux interval,
`B_tooth≈B1 [Q sin(p pi/Q)/(p pi tooth_fraction)]`; coefficient is
`0.737913/tooth_fraction`. A return yoke estimate is `B_yoke≈B1 r_bore/(p h_yoke)`.
Clip B1 to those flux-capacity markers only to compare bottlenecks. This
ignores coupled field redistribution and loaded tooth-tip saturation; it is
neither a lower bound nor a guaranteed attainable torque. At 12 N·m the mean
shear requirement is ~82.3 kPa at r=25.75 mm/L=35 mm.

| Public-grammar screen, J15, gamma0 | Whole-slot area mm² | No-saturation N·m | Tooth field before clipping T | 1.8–2.0 T marker N·m, unskewed |
| --- | ---: | ---: | ---: | ---: |
| tooth .20, gap .3, magnet 4, cover .95, bottom 42 | 222.509 | 23.85 | 5.23 | 8.22–9.13 |
| same, tooth .30 | 203.253 | 21.79 | 3.48 | 11.26–12.51 |
| tooth .35, bottom 41.5, other inputs same | 185.380 | 19.87 | 2.99 | 11.98–13.31 |
| same corner, tooth .40, bottom 42 | 183.925 | 19.71 | 2.61 | 13.58–15.09 |
| published d16 geometry (not a fit) | 173.764 | 16.99 | 3.31 | 9.25–10.28 |

d16's observed standard 4°-skew peak is 9.8953 N·m; proximity to the last
screen is a sanity check, **not calibration or validation**. The high-tooth
corner requires effective B1≈0.862 T for 12 N·m, with tooth estimate≈1.59 T
and yoke≈1.12 T. It has K1≈191 kA/m at the declared source density. Hence a
search is justified; proving simultaneous ripple/cogging feasibility still
requires references. Increasing turns alone cannot increase torque at fixed J.

Three full-stack-equivalent slices are averaged once. For the fundamental,
`k_skew=[1+2 cos(p s/2)]/3`: 0.99746 at 2°, 0.98987 at 4°. A ~1% fundamental
loss cannot alone explain a 20–34% peak deficit. Actual loaded means require
the slice solves; skew mainly suppresses harmonics and may change saturation.

## 2. Manufacturer envelope check (not a matched-deck credibility result)

These are manufacturer ratings, not independent lab evidence. Sizes must be
read from drawings, not inferred from product names. None demonstrates Carbon's
5% ripple/0.05 N·m cogging requirement or the same source density/thermal duty.

| Manufacturer example | Actual envelope comparison | Published torque and interpretation |
| --- | --- | --- |
| Kollmorgen TBM2G-09426 | 94 mm OD, 26.3 mm active stack, 37.79 mm max assembly; closest nearby diameter, not an exact 92-mm fit | Peak 8.98–9.01 N·m across windings; continuous 3.67 N·m at stated high-temperature/heatsink conditions |
| TQ RoboDrive ILM85x26 | 85 mm OD; stator total length 40.3 mm, rotor length 27.2 mm; **not** a 26-mm-total-length motor | Manufacturer peak 9.37 N·m; nominal 2.9 N·m |
| Tecnotion QTR-A-105-34 | 105 mm OD, 34 mm stator height, **24 mm lamination stack**; larger diameter | Peak 6.5–6.7 N·m; 10.3–11.2 N·m “ultimate” uses a different thermal-rise definition and is not peak |
| Larger contingency: TBM2G-11526 | 115 mm OD, 26.3 mm active stack, 44.39 mm max assembly | Peak up to ~15.3 N·m, continuous 6.03 N·m under manufacturer conditions; not a Carbon qualified substitute |

Sources: [Kollmorgen selection guide pp.8, 40, 44, 46–50](https://www.kollmorgen.com/sites/default/files/TBM2G-KM_SG_00396_RevA_EN.pdf),
[TQ product specifications](https://www.tq-group.com/en/products/tq-robodrive/motors-drive-solutions/motor-kits/ilm85x26/),
[Tecnotion brochure pp.16–17](https://www.tecnotion.com/wp-content/uploads/2025/11/Torque_Brochure_EN_2.4.pdf).
This small convenience sample is **not** a market-wide typical rating. It
suggests nearby compact designs commonly quoted here are around 7–9 N·m peak,
while 12 is a stretch needing better geometry/loading, not automatic rejection.
Linear length normalization of 9.01 ×35/26.3≈12.0 is a hypothesis only: different
rotor diameter, materials, current, assembly and thermal rules prevent equivalence.

## 3. Code/config findings to compare with Data Collection

Audit [registry](https://github.com/carbonphysicsai/Carbon/blob/66ea509888e4ef0f5ac08750554db744b56b92bf/docs/development/evidence/motor-feasibility-02/registry.json),
[runner](https://github.com/carbonphysicsai/Carbon/blob/66ea509888e4ef0f5ac08750554db744b56b92bf/scripts/dev/motor/feasibility02/run.py)
and [stack analyzer](https://github.com/carbonphysicsai/Carbon/blob/66ea509888e4ef0f5ac08750554db744b56b92bf/scripts/dev/motor/feasibility02/stages.py):

- **Coverage, concrete:** S3 peak plan names d09/d12/d16/d21, while holding
  refinement also includes d01/d06/d17. Those three null peaks can be NOT_RUN;
  no numerical defect or low torque follows from null. `_stack` also returns
  null if *any* required slice is absent or non-OK; classify each separately.
- **Resume, concrete risk:** `run.main` marks every recorded case ID done,
  including failed records. Resuming the same plan does not retry it. DC must
  audit planned/attempted/OK statuses and make any authorized repair attempt
  prospectively identifiable, retaining the old failures; no deletion to fake
  continuity and no retry authority is granted here.
- Peak is J15/gamma0; 4° skew needs gamma +10/0/−10 at rotor offsets −2/0/+2°.
  `gamma−5d` maintains the same phase currents after shifting the rotor.
  `current_offset_deg` derives +15° for the new winding, versus legacy −120°.
  Check generated manifest/IA,IB,IC, source-region areas and signed curves
  against this code, not the nominal label. An RMS/peak or half-slot mapping
  mismatch could understate torque; **none is established in the reviewed code**.
- `length=35 mm` enters GetDP once as 0.035 m; stack torque is the mean of
  already full-length slices, not their sum or a second length/third factor.
  `turns=1` is an equivalent source, not an omitted 104-turn multiplier.
- Mean peak is `mean(curve)`, not its largest rotor sample. Full-period
  analysis removes the duplicate endpoint. Retain 12° coverage, its endpoint
  periodicity check, coordinate/step/rung identities and Newton outcomes.
- 2D has **no end-effect derating**. Missing end leakage normally makes the
  idealization optimistic, not an identified explanation of underprediction.
  Bias/sign depend on a matched 3D witness. Missing end effects, hot magnets,
  copper heating and demagnetization block the physical 2-s claim.
- The runner default names a mutable image tag; retain the actually used image
  digest and generated deck hashes for DC's repair/search. [Dockerfile](../../../../scripts/dev/motor/reference/Dockerfile)
  pins Gmsh 4.15.2/GetDP 3.5.0 tarballs but that alone does not prove which
  image ran. No change to the shared engine, no prune and no container runs.

## 4. Search recommendation and minimum return

First reconcile missing coverage and current identity; do not turn a setup
error into a geometry reframe. Then prioritize **tooth fraction .35–.40,
gap .3–.4 mm, bottom 41–42 mm, magnets 3–4 mm, coverage .85–.95, openings
.03–.06**, inside the registered validity grammar. These are diagnostic
search recommendations, not a new P or frozen bank. Start around the wide-tooth
corner and neighbors, not only further random points with thin saturated teeth.
Compare 2°/4° skew against an unskewed diagnostic; preserve 6/12/ripple/cogging
and J≤15. Balance tooth capacity against copper area and yoke depth. Tooth-tip
and rotor iron can still saturate even when the bulk estimate looks adequate.
Do not raise Br, J or introduce notches/chamfers without a versioned decision.

DC return: pin/source digest; actual six coordinates and validity; every
planned peak/slice ID with NOT_RUN/failed/OK reason; current convention/areas,
signed torque/angle/cogging curves; peak and holding margins/rung intervals;
peak tooth/tip/yoke flux density and convergence; total search attempts/cost;
best **jointly** feasible geometry or NO_VERIFIED_FEASIBLE_DESIGN/UNRESOLVED.
Missing flux-density output is a needed observer, not a license to guess it.
Count geometry as independent; don't count correlated slices as three designs.
No bank rental until the question law and contested-boundary evidence are ready.

## 5. Only if the search rules out the current envelope

Prefer an **owner-approved larger envelope retaining 6/12 and all safety/ripple
limits**, supported by the larger manufacturer example, over an unsourced
torque reduction. Candidate scope: ~115-mm diameter class with its real axial
allowance; the full CAD/thermal/material grammar still needs owner/science.
At the current observed best, ideal length-only scaling needs
`35×12/9.8953≈42.44 mm` active stack (21.3% longer); this is an estimate, not
a catalogue-backed guarantee or approval to change the fixed length.

| V2, original vs prospective envelope change | Before | After (if buyer accepts size) |
| --- | --- | --- |
| Job/value unit | Verified smooth 6/12-N·m direct-drive joint shortlist | Same job and torque; no inflated speed/payload benefit |
| Mock gross revision saving | 6 h ×$150/h = $900 | At most the same $900 assumption, minus redesign/integration/model costs |
| Demonstrated net savings | $0 floor; not measured | $0 floor; not measured |
| What buyer gives up | Compact 92-mm magnetic frame, 35-mm active stack | Diameter/axial space, mass/inertia and existing mechanical fit; cost and system impacts NOT_MEASURED |

The packet's $3,600 redo/$640 stoppage are assumed costs of mistakes, not
automatic extra savings. No value increase follows from making the envelope
larger. **No requirement reduction is recommended or adopted here.** A new
lower-torque buyer/duty needs sourced load/acceleration evidence and an owner
decision, not merely a neighbouring datasheet. Static/catalogue evidence
earns no Tier 2 agreement or real-world Tier 3 qualification.
