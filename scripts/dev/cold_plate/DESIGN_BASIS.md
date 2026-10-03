# Cold plate (#342): provisional design basis

**Authority.** The owner delegated three choices to the executor on 2026-09-29
(`.agent/DECISIONS.md`, OWNER-BATTERY-V2-DISCLOSURE-01, items 10-12):
- material and coolant: "you pick a group and optimize";
- flow and heat-load ranges: "you pick whats most valuable";
- the thermal-interface assumption: "you pick what's optimal".

These are the choices, with their sources and reasons.

**What this is not.**
- It is a **provisional development design basis** for #342's proposed
  scope.
- It is not a qualified Challenge population or sampling law, not a
  tolerance, and not a production or customer claim.
- It grants no scientific qualification. The exam population, its sampling
  law and every gate remain separate decisions, made before they are used.

## 1. Material and coolant: a copper plate cooled by PG25

| | Choice | Why |
|---|---|---|
| Plate | **Copper, C11000 (ETP)** | It is the standard material for AI-accelerator cold plates. Its conductivity is the highest of the practical, machinable options, so the channel design, not the metal, decides performance. |
| Coolant | **PG25**: 25 % propylene glycol in water | It is the coolant the Open Compute Project specifies for single-phase cold plates ([OCP PG25 guidelines](https://www.opencompute.org/documents/ocp-pg25-guidelines-v1-0-0-pdf); [OCP PG25 cold-plate base specification](https://www.opencompute.org/documents/ocp-base-specification-pg25-v1-0-0-final-pdf)). Its viscosity is about twice water's, which makes pressure drop matter more. |

**Copper properties.** At steady state only the conductivity enters.

| Property | Value | Source |
|---|---|---|
| k | 391 W/m·K at 20 °C | Copper Development Association, C11000 data sheet |
| ρ | 8,890 kg/m³ | Copper Development Association, C11000 data sheet |
| c_p | 385 J/kg·K | Copper Development Association, C11000 data sheet |

Conductivity varies by about 1 % over 20-80 °C, so it is held constant.

**PG25 properties.** These come from CoolProp 6.8.0, incompressible fluid
`INCOMP::MPG[0.25]`. That is the Melinder (2010, IIR) propylene glycol-water
data, at mass fraction 0.25, evaluated at 2 bar:

| T | ρ (kg/m³) | c_p (J/kg·K) | k (W/m·K) | μ (mPa·s) | Pr |
|---|---|---|---|---|---|
| 30 °C | 1014.90 | 3944.6 | 0.4769 | 1.7761 | 14.69 |
| 35 °C | 1012.48 | 3956.7 | 0.4814 | 1.5417 | 12.67 |
| 40 °C | 1009.91 | 3968.6 | 0.4858 | 1.3530 | 11.05 |
| 45 °C | 1007.21 | 3980.6 | 0.4903 | 1.1993 | 9.74 |
| 50 °C | 1004.38 | 3992.4 | 0.4946 | 1.0726 | 8.66 |

- **Mass fraction versus volume.** OCP's PG25 is 25 % by volume. That is
  close to 0.25 by mass, and within the spread of the correlation. The
  difference is recorded here, not hidden.
- **Constant or temperature-dependent.** The verification rungs use
  constant properties at 40 °C. Viscosity falls about 40 % from 30 to 50 °C,
  so whether a production reference needs temperature-dependent viscosity is
  a reference-qualification question for later. It is not settled here.

**Temperature-dependent viscosity (rung 6d).** For runs that let viscosity
vary, μ(T) is a degree-4 polynomial in T (kelvin), μ = Σ cᵢ Tⁱ in Pa·s,
fitted by least squares to the same pinned model at 1 K steps over **30-50 °C
only**:

| i | cᵢ |
|---|---|
| 0 | 2.2138268571145154 |
| 1 | −0.026510771069392616 |
| 2 | 1.196248034665941e-04 |
| 3 | −2.408213659063999e-07 |
| 4 | 1.823829766797535e-10 |

- **Fit residual:** at most **1.6 × 10⁻⁵ relative** anywhere in 30-50 °C
  (checked on a 0.05 K grid; largest at 50 °C).
- **Degree:** of degrees 2, 3 and 4, degree 4 has the smallest residual in
  range (3.7e-3, 2.7e-4, 1.6e-5) and the smallest extrapolation error above
  it. It stays positive to at least 227 °C (500 K, the end of the check),
  where degree 3 reaches zero at 88 °C.
- **Outside 30-50 °C it is an extrapolation.** Against the same model it
  reads +0.1 % at 55 °C, +0.5 % at 60 °C, +5 % at 70 °C and +25 % at 80 °C:
  it overstates viscosity there. Fluid near a heated wall can be hotter than
  50 °C, so every run reports how much of its fluid is above the fitted range.
- **Only viscosity varies.** Conductivity is held at its value at the inlet
  temperature, and ρ and c_p stay constant, so the rung changes one thing.

The fitted points (μ in mPa·s):

| T (°C) | CoolProp μ | polynomial μ | relative residual |
|---|---|---|---|
| 30 | 1.77611 | 1.77610 | -1.1e-05 |
| 31 | 1.72496 | 1.72497 | +5.9e-06 |
| 32 | 1.67606 | 1.67608 | +1.0e-05 |
| 33 | 1.62930 | 1.62932 | +7.6e-06 |
| 34 | 1.58457 | 1.58457 | +1.9e-06 |
| 35 | 1.54174 | 1.54174 | -3.8e-06 |
| 36 | 1.50073 | 1.50072 | -7.8e-06 |
| 37 | 1.46144 | 1.46143 | -9.2e-06 |
| 38 | 1.42378 | 1.42377 | -7.8e-06 |
| 39 | 1.38766 | 1.38766 | -4.2e-06 |
| 40 | 1.35301 | 1.35301 | +6.0e-07 |
| 41 | 1.31975 | 1.31976 | +5.4e-06 |
| 42 | 1.28781 | 1.28782 | +9.0e-06 |
| 43 | 1.25713 | 1.25714 | +1.0e-05 |
| 44 | 1.22763 | 1.22764 | +8.4e-06 |
| 45 | 1.19927 | 1.19928 | +3.5e-06 |
| 46 | 1.17199 | 1.17198 | -3.6e-06 |
| 47 | 1.14573 | 1.14572 | -1.1e-05 |
| 48 | 1.12044 | 1.12043 | -1.4e-05 |
| 49 | 1.09608 | 1.09607 | -7.4e-06 |
| 50 | 1.07260 | 1.07262 | +1.6e-05 |

**Rung 6e: fits over the fluid's whole range.** Rung 6d's fluid reached
79 °C, so its 30-50 °C fit was extrapolated where up to half the fluid sat.
`plate_channel/fit_viscosity.py` refits the same model under a selection rule
stated in the script before it is applied (lowest degree positive over
250-500 K with a written residual within 1e-4; else the smallest residual):

| Fit | Degree | Largest relative residual, as written | c₀ … c₆ |
|---|---|---|---|
| 30-80 °C | 6 | 2.3e-5 | 17.849881432792948, −0.30849429267675, 2.229195303851334e-03, −8.615712938028535e-06, 1.877630788396675e-08, −2.186903343496054e-11, 1.063194651727941e-14 |
| 30-99 °C | 6 | 1.7e-4 | 11.809225533760118, −0.19835015412139706, 1.3929060738771873e-03, −5.23132660955004e-06, 1.1076921123177383e-08, −1.2533006110289745e-11, 5.917954657407082e-15 |

- Both stay positive over 250-500 K. The odd degrees go negative between
  112 and 140 °C and were rejected.
- 99 °C is the top because the model ends at 100 °C: CoolProp refuses it.
- At the nominal geometry the two fits give the same peak to 1e-4 K and the
  same Δp to 0.003 Pa (rung 6e). Within its range, the fit is no longer a
  source of error.

The command that produced the table:

```bash
python3 -m venv env && env/bin/pip install CoolProp==6.8.0
env/bin/python -c "import CoolProp.CoolProp as C; print([C.PropsSI(p,'T',313.15,'P',2e5,'INCOMP::MPG[0.25]') for p in 'DCLV'])"
```

## 2. Flow and heat load: the 1 kW accelerator class

The most valuable envelope is the one being built now: single accelerators
around 1 kW, where cold-plate design limits the power.

| Parameter | Range | Nominal | Basis |
|---|---|---|---|
| Heat load per plate | 500-1,500 W | 1,000 W | The current accelerator class (about 700 W to over 1 kW) |
| Heated footprint | 30 × 30 mm | same | About one large die. Average flux is 56-167 W/cm². |
| Heat map | uniform, or hot-spot maps up to 3× the average | uniform first | A family parameter. The frozen maps are a later, recorded choice. |
| Flow | 1.25-2.0 L/min per kW | 1.5 L/min per kW | OCP's PG25 guidance: 1.5 L/min per kW is about a 10 °C rise, and 1.25-2.0 is the recommended band |
| Inlet temperature | 30-45 °C | 40 °C | OCP's group-2 supply band (30-37 °C), extended to 45 °C for warm-water operation |
| Straight channels | width 0.2-0.5 mm, fin 0.2-0.5 mm, depth 1-3 mm | 0.3 / 0.3 / 2 mm | The microchannel range for skived or machined copper |

**Is it laminar?** #342 asks for this to be confirmed first. It was computed
over the full factorial of the ranges above: 324 combinations, with channels
spanning the 30 mm footprint and PG25 viscosity at the inlet temperature.
- **Re runs from 50 to 1,931. None exceeds 2,000.**
- The top corner is 1,500 W, 2.0 L/min per kW, a 45 °C inlet and 1 mm
  channel depth. It comes within about 20 % of the usual transition near
  2,300 in straight ducts.
- **Laminar solver assumptions are supported for straight channels.** That
  corner, and any serpentine bends (which can trip earlier), are flagged for
  checking before cases there are generated.

## 3. The thermal interface: a uniform resistance, applied after the solve

The choice is to **model the thermal interface material (TIM) between die and
plate as a uniform areal resistance R″, and add it after the solve**:
T_die = T_base + q″·R″.

The reason: the plate takes a prescribed heat flux (a "flux-mode" boundary),
and the TIM is a thin layer.
- In that case the TIM changes the die temperature and nothing inside the
  plate. The plate's temperature field is identical for every R″.
- So adding q″·R″ afterwards is exact to first order. It costs nothing, and
  one plate solution serves every TIM.
- Treating it as a parameter keeps TIM quality from being confounded with
  channel design, which is what the Challenge is about.

The nominal value is **R″ = 0.05 cm²·K/W (5 × 10⁻⁶ m²·K/W)**. That is a good
paste or phase-change TIM. Liquid metal is about 0.01-0.02 and ordinary
grease 0.1 or more. It is reported alongside every result, never folded into
the plate score.

**Where this stops holding.** The TIM would need to be meshed only if it were
thick or conductive enough to spread heat sideways. At a 50 µm thickness it is
not.

## 4. What still needs a decision before a dataset exists

This design basis sets the physics and the ranges. **None of these follow
from it:**
- the Challenge's population and its sampling law;
- the gates and tolerances;
- the frozen heat maps;
- the pilot cost proposal (8 ordinary and 4 difficult cases with paired
  refinement), which goes to the owner priced, before it runs.

Those are made, and recorded, when the pilot is proposed.

## 5. Decided on 2026-10-01, for the DEVELOPMENT exam

The owner delegated the design flow (OWNER-CHALLENGE-DESIGN-01): "No
blockers. Just follow the correct design flow." Section 4's open items are
decided as follows. The full record, with each choice's basis, is
`.agent/tickets/CHALLENGE-COLD-PLATE-01_development_exam.md`, D1-D8. Every
value is a provisional DEVELOPMENT value, not a qualified one.

- **The frozen heat maps are a family, not a list.**
  - The family is an axial hot band: a Gaussian on a uniform floor,
    normalized to the heat load.
  - Its parameters are a peak-to-average ratio of 1-3, a centre of 3-27 mm
    and a width of 1.5-3.5 mm.
  - 3.5 mm is the widest band that still reaches 3x on a 30 mm die.
  - The reason for a hot spot at all: with a uniform map, the textbook
    closed-form model is within 0.1-0.35 K of the reference peak. That would
    leave a learned model nothing to add.
- **The population and its sampling law.**
  - Draws are uniform over the nine-input box.
  - A draw is admitted when the closed-form model (with axial spreading)
    predicts a hottest wall of at most 95 °C and Re of at most 2,000.
  - The coolant model ends at 100 °C; the reference checks its own fluid
    against 99 °C.
- **Gates, feasibility and scores are kept apart.**
  - Gates are physical laws only.
  - Feasibility (die temperature through the TIM, and hydraulic power) is a
    decision property, never a gate.
  - The score is TRAIN-normalized peak, profile and pressure-drop error.
- **The pilot** ran in #342's shape on the owner's host, at no marginal
  spend: 16 of 16 OK (`reference/README.md`).
