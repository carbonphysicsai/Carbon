# Battery v3 continuous law for ambient indexed decisions

**DEVELOPMENT / SPECIFIED.** The owner selects an ambient-indexed map and
buyer-mix-weighted band value; the [numeric law sheet](battery-ambient-indexed-v3.json)
is not runtime registration. Supersede #817's single-protocol law prospectively;
retain that sheet and the v2 four-vector grid as history. The
[packet](../round1/battery-ambient-map-v3.md) owns the buyer job.

## P Q and weight identities

Proposed P draws a buyer mix over 5/15/25/35/40-C anchors, one start SOC and
two continuous requirement margins for the whole map. Port the recommended
Dirichlet(2,3,8,5,2), SOC {0.1,0.2,0.3} masses {0.5,0.3,0.2}, thermal margin
U[0,2.5] K and plating margin U[0,0.002] V. The resulting hard constraints are
T_charge<=45-mT and eta_charge>=mEta, plus 4.2 V and Q30/Q1>=0.99. These
probability/margin distributions remain HUMAN_INPUT; the owner selects the
10/20/30% support and start-SOC observable. A synthetic mix is not an observed
fleet distribution. Fresh initial state is a point mass; arbitrary initial
age/SOH remains unsupported, and 30-cycle degradation remains part of truth.

Q stays separate: proposed 20% interior, 50% safety-edge and 30% per-band
pick/value-edge questions, with bands chosen by Test Lead from separate
public/retired diagnostics. No redraws of NONE_FEASIBLE or unresolved truth.
Refine near the **drawn** limit, not only the 45-C/0-V anchor. At 5 C the
reported best's 1.906-mV plating minimum is within the 2-mV diagnostic band;
it does not cover the continuous law up to 2 mV without refinement.

Owner-selected `w_band=buyer_mix` weights band minutes and value-equivalent regret
within the map. It is not Q's enrichment mass or automatic weighting of
outer questions. Proposed outer-question evidence weights remain unit P
weights with bank clustering and separate Q reporting. Test Lead registers
score use/power; #815's sealed/frozen score identity is not modified here.

## Per band best picks and value resolution

For each b, choose a_b minimizing session minutes among actions satisfying
that band's complete hard limits. There is **no shared protocol** constraint.
A complete map requires a feasible action in every mandatory band, even if
its buyer weight is zero. Unsafe time cannot be averaged away.

For an all-feasible eligible map, expected minutes is
`V=sum_b mix_b * t_b(a_b)`. Recommendation: delta_b=0.5 min, registered value
still null. The value-equivalent set is feasible actions whose excess above
the **same band's resolved best** is <=delta_b. Recommend alignment with
#820's proposed indexed-task rule: for `d_b=t_b(pick)-t_b(best)`,
`r_b=0 if d_b<=delta_b else d_b`; aggregate `sum_b mix_b*r_b`.
Report raw minutes/regret and `max(0,d_b-delta_b)` as a separate excess-minutes
diagnostic. The latter is not the proposed scored-regret rule; Test Lead
registers score use. Do not chain pairwise ties into one large
equivalence class, round an uncertain pick into a pass, or use delta on safety.
Refine intervals that cannot settle best, equivalence or hard admissibility.

Changing mix alone does **not change band argmins** when band actions are
independent and weights positive: it changes fleet value and the relative
score impact of a mistake. No shared cooling-resource allocation or global
energy trade is adopted. SOC/margins may change band answers; their actual
answer-changing regions must be measured. This limits, rather than guarantees,
the learning diversity contributed by mixture variation.

## Diversity and exposure

For each band, estimate p_bj, the P mass with resolved best action j on an
eligible bank. Conditional iid questions give
`E[D_b,k]=sum_j (1-(1-p_bj)^k)`. Report value-equivalent sets as well as exact
best identities so tie/order artifacts do not manufacture diversity. For
dependent Q batches use the actual sampling design, not this iid formula.
At proposed k=8, each band has 0..min(8,N_b) winners; no measured expectation
is available. Mix-only replays have zero new per-band pick changes.

Report distinct picks, feasible/none/unresolved fractions and edge/refinement
rates **per band**, then complete/none/unresolved-map fractions and distinct
map vectors separately. Pooling five different fixed band picks does not
prove five answer-changing questions. No forced winner quota or redraw.
Every reused case consumes the same E under #756/#760; new mix, margins,
question labels or map identities do not renew exposure. Retired publication
occurs only after all drawing windows end.

## Audit cost and downstream quiz impact

Keep a four-vector **v3 map audit**: T_charge {42.5,45} x Q30/Q1
{0.99,0.995}, plating>=0, SOC0.1 and a fixed explicitly documented buyer mix.
It is not the primary law; the preserved v2 audit instead asked a shared
protocol/worst-warm question. Never mix the two evidence identities.

The public with-cooling inventory has 42/42/147/147/36 action-context entries
at the five bands, totaling 414. Covering those same inventories at three
SOCs would require 1242 base programmes plus refinement if rebuilt; the
current observations do not establish that coverage. This is a scoping count,
not an adopted bank, execution request or CPU-hour quote. Costs are UNMEASURED
for v3. Search calls per map are `sum_b N_b`, not the Cartesian product of
five action sets. Requirement/mix-only draws add zero reference solves only
on an identical complete covered bank. Coolant/action/SOC/history changes do not.

Q2 ports full-charge thermal/plating margins to each band; Q3 commits a full
map, judges per-band safety/value and aggregates buyer value after all gates.
Version the switch/cooling/session-start-SOC observer and map projection first.
#820 at `e1d0fdbec3a77f464e936d2750b55a78dfb5d2a8` owns the indexed-task
implementation proposal; this packet neither duplicates nor adopts its runtime.
Diagnostics (a) optimizer stability, (b) lattice resolution,
(c) power by k, (d) decision-value agreement and (e) unresolved rate remain.
Retain edge-optimist, over-cautious, sign-error and optimizer/lattice-aware
controls. No hidden material, sampler, quiz runtime or solver run here.
