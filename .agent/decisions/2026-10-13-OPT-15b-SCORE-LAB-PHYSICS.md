# OPT-15b Score Lab physics diagnostics (2026-10-13)

**Scope:** DEVELOPMENT diagnostic only. Authority: OPT-15b in the local
Optimizer queue, the Validator's read-only `with_physics` contract, and the
owner's task-neighbourhood direction. No score, gate, Challenge law or
qualification threshold is adopted.

**Engineering decisions:** The synthetic traits are generated and observed
by construction. Law-violation rate and size remain separate config knobs;
their product is the one `law_violations` badness field expected by the
Validator wrapper. Target, shifted and extrapolated true values use disjoint
analytic toy questions. Shifted tasks alter objective weighting, one hard
margin, operating context or action boundary. Their oracle is exact over the
offered action set. FLOOR retains the candidate's raw score and ranks by
fewer breaches before score. An OFF switch is required as a control.

**Real-data boundary:** PLT-01's public calibrated paired readings supply
B15/B16 for 142 members. The separately committed public physics-consistency
measurements supply B9 for those same IDs. The compact public EV4 replay has
100 members and no off-distribution reference value. Missing traits or rule
legs produce `INSUFFICIENT_EVIDENCE`; no proxy is substituted for an exact
public registry score. All example limits and weights are labelled
ASSUMPTION. B9 remains diagnostic only.

**Follow-up:** Test Lead and owner choose any scientific use or limits only
after independent, qualified evidence. OPT-15c may broaden the sweep with an
independent holdout; this ticket does not run or see that holdout.
