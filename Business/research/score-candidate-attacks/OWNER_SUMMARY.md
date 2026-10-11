# Owner summary — SCORE-CANDIDATE-ATTACKS-01

**Research recommendation, public DEVELOPMENT data only.** Keep VERIFY-R in
the prospective proof, but do not call any candidate ungameable. Its verifier
can prevent an unsafe delivery within the registered reference contract; its
development score can still overfit the decision distribution.

Measured on EV5's 99 real members and 12 verification questions, with
ASSUMPTION service-regret normalization low/base/high 60/120/240 seconds:

| Measured control / construction | A rank, among real members plus that control | VERIFY-R k=1 rank | Unsafe verification picks |
| --- | --- | --- | --- |
| Boundary optimist | 1 | 96–97 | 8 |
| Local sign error | 1 | 94–95 | 4 |
| Width-b construction | 13–14 | 6–10 | 1 |
| Steps-b construction | 8–9 | 44–54 | 1 |

These are observed tie ranges, not confidence intervals; no new attack was
trained. The sign-error control has E=0.007715, yet the published near-plating
measurement is 70/74 false accepts. Whole-field accuracy strongly rewards it.
VERIFY-R demotes it, but width-b still outranks or ties four real members
with better verification service value (maximum regret gap 0.08333).

A fixed-list, aggregate error-halving counterfactual raises A for all 99 real
members while decisions stay unchanged: gain min/median/max
0.02359/0.03066/0.08682. It raises no pure VERIFY-R score. The same mechanism
affects the A component of all A-Q blends while a gate's predictions and q
are frozen. This is an algebraic vulnerability, not measured retraining.

The actual Q3 q and joint scoring-set G-FEAS are absent from the public
exports. Exact A-Q+G-FEAS, tighter G-FEAS/A-Q and G-PLATE/A-Q attack ranks
are **NOT_IDENTIFIABLE**; using a decision-grid substitute would mislabel
the evidence. Published per-constraint measurements still support testing
boundary optimism and the gap in a plating-only gate.

Recommend three cheap, preregistered checks: (1) fixed-decision error changes
must not improve the decision-primary score; (2) unique committed top-k and
attempt/core/wall caps must survive padding, duplicated actions and selective
failure; (3) report worst-stratum false-feasible and paired value degradation
on untouched variants, retaining known-bad and benign controls. Copy
fingerprinting is an investigation signal, not proof or a scientific penalty.
Thresholds, budget and adoption remain **HUMAN_INPUT**. Hand-off details and
missing export fields are in [ATTACKS.md](ATTACKS.md) and [handoff.json](handoff.json).
