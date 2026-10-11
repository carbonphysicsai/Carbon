# ADAPTIVE-SOLVER-ARM-01-D1 — prospective adaptive trace, shared cost

**Status:** working DEVELOPMENT engineering decision. **Problem:** #998's
registered full solver order is honest for fixed replay but cannot encode a
proposal that depends on earlier settled observations, as #1014 identifies.

**Recommended implementation:** keep #998's fixed replay intact and add a
separate closed adaptive-panel/policy schema. The policy sees only actions and
the observed prefix. It writes an internal trace and an aggregate public-safe
report. Use #1047's validated cap and ledger unchanged for both direct and
ordinary surrogate arms. Register action bounds, branch labels, warm-start
IDs, exact-cache identity and cost, full mandatory margin names, and all
policy/cost parameters before replay. A prior common cache is paid equally by
both arms; acquisition for any private cache must be charged to its arm.

The direct arm offers exact finite enumeration for adopted f02 and a
branch-aware pattern/multistart policy for larger lattices. The surrogate arm
offers exact lookup plus a branch-aware radial-basis response surface of the
objective and mandatory margins, with a charged acquisition step and final
reference verification. Neither treats a predicted margin as truth. Both are
candidate policies to calibrate on separate development jobs; this ticket
does not select a real Challenge's strongest industry competitor.

**Alternatives rejected:** relabeling a frozen order as adaptive; selecting the
best direct/surrogate policy separately for each held-out question; ignoring
fit, screening or cache acquisition cost; giving one arm a private public bank
for free; smoothing a motor signed curve down to unregistered mean torque; and
declaring continuous regret against an unproven global optimum.

**Implementation location:** `carbon/design_search/adaptive_arms.py`, toy tests,
and a development runbook. **Dependencies:** #1014 research and #1047 budget
contract. **Invariant:** admissibility before ranking; reference and infra
failures separate; no hidden disclosure; proposal-before-reference.
**Reversibility:** remove the new replay module/registration with no migration
of existing #998 or VALUE-BAR-V1 records. **Human-reserved inputs:** real
Challenge policy selection, physical margins, method calibration, cache rights,
measured costs and qualification remain with the registered owners. A future
policy version supersedes this record rather than rewriting old traces.
