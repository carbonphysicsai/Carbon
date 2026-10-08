# Battery v3 optimizer for a five band charge map

**DEVELOPMENT / SPECIFIED; prospective #759 amendment.** Supersede
[optimizer v2](battery-ev-fast-charge-v2.md)'s shared-protocol decision with
the owner-selected [ambient map](../round1/battery-ambient-map-v3.md).
Earlier drafts and evidence remain unchanged. Runtime, reference, task and
score integration are separate tickets.

## Actions admissibility and objective

An action per band is `(c1,c2,switch_voltage,cooling_level)`; the committed
answer is all five entries, not a universal tuple. Recommend h multipliers
{1,2,4} under the study's whole-programme cooling convention. Freeze each
band's finite candidate bank, switches, C rates/order, nominal h and area,
initial state, SOC, cycle programme and reference/observer pins. The public
study's c2=1.25 and varying switch voltages are not supported by the existing
runtime `BatteryCase`; accepted bank/feature receipts remain absent.

At every band enforce all-charge thermal/plating limits, 4.2-V programme
voltage and Q30/Q1>=0.99 before ranking. Test discharge/rest temperatures
remain diagnostics. Start-SOC-to80 minutes include the 120-s initial rest;
SOC0.1 retains the 10-80 anchor. Missing crossing/support stays UNRESOLVED.
Arbitrary initial aged states require an owning restart contract, not a
cycle checkpoint mislabeled as a free initial condition.

Select each band's minimum session time. Owner-selected map value is
`sum_b buyer_mix_b * t_b`, without a worst-warm primary objective. Report
worst-warm as a diagnostic if useful. All mandatory band gates apply even
at zero weight. Report hA(T-Tamb), heat-removal energy and missing hardware/
electricity costs; time-only ranking is not a net cooling-economics claim.

Recommend best-anchored delta=0.5 min (HUMAN_INPUT) for value-equivalent
feasible choices. With `d=t_pick-t_best`, recommend #820's proposed rule:
regret is zero when `d<=delta`, otherwise the full `d` minutes. Weight it with
the same buyer mix only after map admissibility. Report raw minutes/regret
and `max(0,d-delta)` excess minutes as a separate diagnostic, not a silently
different scored regret. Test Lead registers score use. Ties need a frozen
order, not pairwise chaining.
Interval uncertainty in feasibility, best or equivalence requires refinement
or UNRESOLVED; safety has no 0.5-min slack.

## Search budget and commitment

KEEP/WRAP Challenge-neutral freeze/commit and finite-bank task machinery.
For exhaustive finite banks, budget `B_model=sum_b N_b` at the drawn SOC.
Optimizing bands separately avoids enumerating `product_b N_b` full maps;
there is no shared cooling-resource constraint in this job. Any future
global constraint needs a new optimizer/version, not this factorization.
With positive weights, changing mix changes value, not independent argmins.

Register lattice spacing, all per-band inventories, model call/cache rules,
objective/phase projection, limits/margins, value resolution and action-order
ties in an immutable map contract. Commit all choices or a typed abstention
before producer truth. The model uses no protected references to search.
Existing single-task mean/strata.w alone does not define buyer mixture or a
multi-entry map. #820 at `e1d0fdbec3a77f464e936d2750b55a78dfb5d2a8` owns
the indexed-task proposal; do not duplicate it. Battery-specific action/observer
projection and an accepted integration remain MIGRATION_REQUIRED.

## Reference judgment and controls

A feasible observed action establishes existence at that band; unresolved
competitors do not establish an exact optimum. A fully settled no-feasible
band yields NONE_FEASIBLE for a complete map, with band reasons retained.
Incomplete truth stays UNRESOLVED, never a least-unsafe best or favorable
zero. No reference failures are attributed to the candidate.

Refine cold-band plating near the 2-mV diagnostic band, all drawn thermal/
plating boundaries, session crossings and time/value orderings. Source
`ambient-indexed.json` shows complete feasible-map existence with cooling,
but historical best-pick ordering is unresolved in four of five bands.
The new value-equivalence proposal does not rescore those historical flags.

Controls: edge-optimist ignores a local charging/plating breach; over-cautious
abstains despite a resolved safe option; sign-error reverses plating polarity;
optimizer/lattice-aware fits registered picks but fails off-lattice or
near-equivalent alternatives under independently covered truth. Report
diagnostics (a)-(e), per-band diversity/feasible mix and complete-map value.
Test Lead owns score use, power, uncertainty and thresholds.

## Cost maturity and handoff

Public inventories total 414 band/action contexts; rebuilding the same
inventory at three SOCs would scope 1242 base programmes plus refinement.
V3 costs, cold cooling extensions, new SOC observer coverage and full bank
adequacy are UNMEASURED/NOT_DEMONSTRATED. The old 2684x90-CPU-s figure is
not a quote here. Each underlying case retains its exposure E.

No solver runs, spend, hidden material, EV5/journal14/live-contract changes
or valV2 permit activation. Motor and five-family optimizers/laws unchanged.
Data Collection supplies immutable action/reference/observer/bank evidence;
Validator owns runtime projection and score registration. PR Lead owns
delivery after handoff; science coordinates on #42 and team on #643.
