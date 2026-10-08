# Cooling v2 thermal budget before feasibility jobs

**DEVELOPMENT / analytic screen, not reference truth.** The 53-job
[spreader panel](cooling-spreader-panel-v2.json) is **ON HOLD**. The current
85-C requirement is the **lid-side TIM2 interface**, not the die junction.
The proposed stack does miss 85 C at the die-side proxy in this budget, but
that is not the same conclusion as failing the current interface requirement.
The owner must choose the plane before any release. Motor and other family
laws are unchanged.

## Inputs and measurement basis

Use P=1500 W, inlet=45 C, A=30x30 mm=9e-4 m2, flow=3 L/min,
R1''=5.14e-6 and R2''=6e-6 m2 K/W, copper thickness=1.5 mm and
k=391 W/(m K). Average flux is **1.667 MW/m2**; a ratio-3 raw die peak is
**5 MW/m2**. Ratio 3 is a peak/mean at the die, not an assumed post-spreader
ratio. The [arithmetic sheet](cooling-thermal-budget-v2.json) freezes inputs,
assumptions and the hold; no code consumes it as execution authority.

The owner-supplied **about 28 K bare-cell peak rise from inlet** is an
empirical planning anchor, not a physical minimum for all designs. Public
[Cooling feasibility evidence](https://github.com/carbonphysicsai/Carbon/blob/f79e7a61da10f1005e7438362ffc8baf6bf80d61/docs/development/evidence/cooling-feasibility-02/summary.json)
reports c2-warm_uniform at 81.189 C with the **old 5e-6** postprocessed TIM.
Subtract its uniform 8.333-K TIM jump and 45-C inlet: bare-face rise is
27.856 K, consistent with the rounded 28-K anchor. This case's fin is
0.35 mm, not the panel's proposed 0.3 mm; it is not a run of that panel.

At 45 C the pinned PG25 polynomials give rho=1007.21 kg/m3 and
cp=3980.70 J/(kg K). `P/(rho*flow*cp)` gives an outlet rise **7.48 K** if
the full 1500 W is absorbed. Exact periodic tiling can absorb slightly less.
The residual **20.52 K** of the 28-K anchor combines plate convection,
conduction and peak-to-bulk effects. We cannot independently identify those
components from one measured peak. **Do not add 7.48 K to 28 K**, or retain
the old TIM as well as TIM2. This is PG25, not an unversioned pure-water model.

## Resistance budget and temperature planes

Uniform flux gives the following increments:

| Contribution | Rise K | Plane affected |
| --- | ---: | --- |
| Coolant rise, full-area energy balance | 7.48 | Included in the 28-K cell anchor |
| Remaining cell convection/conduction/peak effects | 20.52 | Together with coolant gives bare plate rise 28 |
| TIM2, qbar R2'' | 10.00 | Lid-side TIM2 interface |
| Added copper lid, qbar t/k | 6.39 | Die-facing lid surface |
| TIM1, qbar R1'' | 8.57 | Die-side temperature proxy |

Thus `T_interface = 45 + 28 + 10 = 83 C`, and
`T_die_proxy = 83 + 6.39 + 8.57 = 97.96 C`. The user's estimate of roughly
90 C or more is confirmed **for the upstream die-side sum**, not the current
interface observable. This proxy omits internal die/junction resistance;
it cannot certify a physical junction temperature.

For raw ratio-3 flux, TIM1 alone adds **25.70 K** at the die hotspot. It does
not disappear when copper spreads downstream heat. Spreading is a lateral
conduction problem, not a separately known scalar resistance. Show two
conditional screens, neither a certified upper/lower bound:

- **Optimistic redistribution:** post-spreader flux becomes uniform; use
  the uniform 28-K cell anchor and 6.39-K copper drop at the source site.
  Interface=83 C; die proxy=83+6.39+25.70=**115.09 C**. The assumption of no
  extra source-site spreading drop is favorable, not demonstrated by the lid.
- **No redistribution:** retain peak/mean=3 through TIM2 and copper and,
  optimistically, still use the uniform plate rise. Interface=**103 C**;
  die proxy=45+28+30+19.18+25.70=**147.88 C**. Actual nonuniform plate response
  can be worse; this does not reconstruct the old >=117-C results.

At the nominal TIM2, an unchanged 28-K local plate rise leaves only 12 K
for contact: post-spreader peak/mean must be **<=1.2** even before an error
allowance. At R2''=4e-6 it is <=1.8; at 8e-6 it is <=0.9, so even a uniform
map fails that conditional interface screen. These are headroom targets,
not claims that a 1.5-mm lid achieves them. Correlated local fields and the
joint uncertainty from [the spreader specification](cooling-spreader-v2.md)
still govern any reference verdict.

## Sensitivity and buyer levers

Taking R1''=R2''=4e-6, t=1.5 mm and k=400 (the most favorable resistance
choices in the stated ranges), uniform die proxy is **92.58 C**; the same
optimistic redistributed hotspot proxy is **105.92 C**. **No stack in those
ranges reaches a die-side 85-C target under this 28-K-anchor screen.** It is
not valid to infer that no stack can meet the existing interface target:
the lowest-TIM2 uniform interface screen is 79.67 C.

If the buyer wants an 85-C **die-side** target, these are the conditional
single-lever break-even values for the nominal stack, with no uncertainty
reserve and favorable redistributed-hotspot assumptions:

| Buyer lever | Uniform | Raw ratio-3 hotspot, ideal redistribution |
| --- | ---: | ---: |
| Inlet maximum, keeping the 28-K rise unchanged | 32.04 C | 14.91 C |
| Die-side limit needed at inlet 45 C | 97.96 C | 115.09 C |
| Power maximum at inlet 45 C, fixed 3 L/min and linear rise scaling | 1133 W | 856 W |
| Common die/lid area minimum, keeping plate rise fixed at 28 K | 1872 mm2 (43.27-mm square) | 3157 mm2 (56.19-mm square) |

Each lever changes a reference contract. The 14.91-C inlet is **outside** the
current PG25 30-C lower applicability bound. Power values assume the same
geometry and fixed flow, with linearized properties/heat transfer; the current
2-L/min/kW law is not held simultaneously. Area values enlarge both source
and lid while holding a plate anchor that would need rechecking; they are
not permission to extend the periodic 30-mm grammar or run a full plate.
Keeping a 30-mm die with a raw hotspot, changing **lid area alone cannot**
close this screen: plate rise plus TIM1 is already 53.7 K, exceeding 40 K.
Changing only die area at the nominal 30-mm lid also cannot close it, since
plate+TIM2+copper already gives 44.39 K before TIM1. The common-area row is
therefore a coupled package change, not free die-only or lid-only headroom.

For the **existing interface** target, the owner need not adopt a junction
limit. Nominal uniform screening leaves 2 K; a retained ratio-3 interface
needs inlet<=27 C or interface limit>=103 C under the same optimistic plate
anchor. A sufficiently flattened post-map might avoid either change, but
has not been demonstrated. No inlet, limit, power, area or TIM alternative
is selected by this budget.

## Release condition and Data Collection return

**Hold all 53 jobs**, including solver verification/witness jobs. Paper
arithmetic may continue. The owner must confirm the temperature plane and
inputs; a reviewed analytical map/budget must exhibit possible feasibility
with an explicit uncertainty allowance, not merely assume uniform spreading.
Then stack/package/map support and the separately required execution authority
must be present. None of these pins or releases is supplied here.

If the owner chooses 85 C at the die/junction, request a buyer-level lever
before the panel. If the owner retains 85 C at TIM2, first supply the
candidate-specific conservative conduction calculation and a credible local
plate-response/spreading bound within its allowed uncertainty. Return the
plane, cell/TIM decomposition, raw/post fluxes, applicability and budget
receipt. A permit going live elsewhere does not automatically release this
held panel. Reference failure remains separate from candidate failure.
