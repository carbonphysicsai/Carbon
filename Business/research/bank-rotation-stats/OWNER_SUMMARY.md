# Owner summary â€” bank reuse, information and refill

**Research recommendation only.** E should follow each Challenge's measured
cost, information requirement and feedback-release target. Physics class alone
is insufficient. Keep the owner's current testnet battery E=1; the requested
5/10/20 values are historical development options, not current mainnet policy.

A frozen deterministic member gives the same per-case result on every repeat.
For independent-case evidence, 1000 equally repeated appearances therefore
carry at most 200/100/50 unique cases for E=5/10/20. Repetition helps
validator agreement, comparisons on a common bank and temporal monitoring;
it does not add new physical coverage. Counting appearances independently can
understate standard errors by sqrt(E): 2.24/3.16/4.47 in that frozen limit.
These are mathematical consequences, not measured live-bank correlations.

For a declared random-effects sensitivity rho low/base/high 0.25/0.75/1
(ASSUMPTION), effective sample sizes per 1000 appearances are:

| Requested class | B/n, E | ESS low-rho / base / high-rho | Refill CPU-h per 100 appearances, low/base/high |
| --- | --- | --- | --- |
| Battery pool | 20, 5 | 500 / 250 / 200 | 0.417 / 0.506 / 0.667 |
| Motor-like | 10, 10 | 308 / 129 / 100 | 6 / 8 / 10 |
| CFD-class | 5, 20 | 174 / 66 / 50 | 10 / 30 / 100 |

Cost inputs: battery 75/91/120 CPU-s (91 from public planning, ends
ASSUMPTION); motor 0.6/0.8/1 core-h (source endpoints, assumed midpoint);
CFD 2/6/20 core-h is **ASSUMPTION illustration**, actual cost HUMAN_INPUT.
All rows assume one already-admissible reference case; expensive design
questions need a full-lattice/refinement and admission-yield cost instead.

Literal repeat draws in consecutive **overlapping active windows** violate
the owner bank's active-disjoint rule. Schedule consecutive *eligible* draws
after prior holders end, or interleave disjoint cohorts; no such runtime
change is implemented here. This can bound retirement lag, but may slow
fresh-case information. With assumed spacing/duration 3 windows, E=5/10/20
gives 15/30/60 windows from first draw to release eligibility, plus timers.
Case membership stays sealed; aggregate feedback can still enable adaptive
overfitting. Retire and clear every dependent window before publication,
and never redraw published cases or claim Merkle integrity proves secrecy.

Recommended cost rule: sum each bank/stratum's draw rate Ã— offered-reference
CPU cost / (E Ã— valid admission yield), add fresh canaries and overhead;
choose E prospectively inside an owner-set refill budget **and** a minimum
unique-case information rate and maximum release lag. If those bounds
conflict, slow cadence or increase budget/reserveâ€”do not invent extra power
from reuse. [ANALYSIS.md](ANALYSIS.md) supplies formulas, source seams and
selection criteria; [cost-rule.json](cost-rule.json) is the handoff specification.
