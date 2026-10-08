# COOLING-THERMAL-BUDGET-04 — temperature planes and panel hold

Ticket CHALLENGE-CUSTOMER-INPUTS-04; direct owner request for paper screening.
KEEP #804's 85-C spreader-side TIM2 interface requirement. A die-side sum
including TIM1 is a different observable, not a silent replacement junction
limit. At fixed prescribed die flux, TIM1 raises die temperature but does not
add its jump to the TIM2 interface. Missing die/package physics precludes a
physical junction qualification claim.

With the supplied 28-K bare-cell anchor, nominal uniform TIM2 interface is
83 C; nominal uniform die-side proxy is 97.96 C. The user's 25.7-K TIM1
hotspot estimate is correct. Even an optimistic redistributed-hotspot screen
gives a 115.09-C die proxy. The lowest resistance choices in #817's ranges
still miss 85 C for that proxy with this plate anchor. This is conditional
screening, not a proof that no other plate/reference route can work.

No simple stack sum rules out the current interface target: its uniform
case has 2 K of nominal headroom. A hotspot needs a much flatter post-map
(optimistic peak/mean <=1.2 at nominal TIM2 and unchanged 28-K plate rise).
Conduction/spreading, local plate response and uncertainty are not measured.
Do not release the 53-job panel on the assumption of perfect spreading.

WRAP a separate budget with reproducible arithmetic and conditional inlet,
limit, power and area levers; mark the existing recipe held. The smallest
owner decision is whether the buyer retains the 85-C interface requirement
or wants a prospective die/junction requirement and changed operating inputs.
Budget/plane release, stack adoption, supported map and package pins remain
required. There is no solver or execution grant in this ticket.

Rejected: adding coolant rise to a plate rise already measured from inlet;
counting the original TIM twice; assuming copper is isothermal; treating
conditional linear power/area extrapolations as verified feasible designs;
solving a full cold plate. Supersede this budget/hold prospectively if the
owner changes the plane or evidence supplies a better conditional model.
Existing old references and results remain unchanged; Hub is retired.
