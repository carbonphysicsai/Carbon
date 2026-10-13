# VALUE-METRIC-V2: registered definition (rev 2)

**State:** REGISTERED_DEFINITION. DEVELOPMENT. Registered prospectively on 2026-10-13, before any V2 bank exists. **Every value is HUMAN_INPUT.** The owner sets values later, from curves on a real V2 bank. Nothing here scores, ranks or pays anything until a separate owner record adopts values and a sealed confirmation passes.

**Machine-readable form:** [`definition.v2.json`](definition.v2.json). Its canonical-JSON sha256 is the identity that a value record, a bank and a confirmation must bind. **The bank contract** is [`BANK_SPEC.md`](BANK_SPEC.md).

**Evidence trail:**
- RES-07 (#1209): the old metric rewards abstention, and a cheap baseline is strong;
- RES-08 (#1218): rev 1 stressed, with 12 definition questions;
- RES-09 (#1241): rev-2 curves, and the EV4 panel can't carry V2.

**Challenge-neutral:** one rule for every Challenge. Each Challenge supplies only its question law (§1) and its bank.

## 1. The question law (supplied per Challenge)

| Part | Meaning |
|---|---|
| Action grammar A | A finite, enumerated set of design actions, each with a stable id |
| Conditions | The operating conditions an action must hold under; one or more per question |
| Objective and unit u | The buyer's objective per action, and the benefit unit u |
| Feasibility | Constraint checks decided by the verified reference with its registered bands: FEASIBLE / INFEASIBLE / UNRESOLVED |
| Fallback b(q) | The buyer's own default action for the question |
| Population P, weights w | The question population and any weighting, kept separate (constitution §7.2) |

## 2. The estimand

For a question q in the scored bank and a model m:

`U(m, q) = G(m, q) − κ · n(m, q)`

- **`G`, the verified gain:**
  - `G = max(0, (objective(b) − objective(r)) / u)`, where r is the best reference-FEASIBLE action on the model's shortlist and the objective is the reference's, never the model's;
  - `G = 0` when no shortlisted action is reference-FEASIBLE and better than b;
  - G is never negative: the buyer keeps the better of the two.
- **`n`:** the reference **condition-solves** the shortlist consumes. One action with c conditions costs c, and every listed action is charged, including unsafe, unresolved and unavailable ones.
- **`κ`:** the charge per condition-solve, in benefit units. HUMAN_INPUT.
- **The model's score:** the w-weighted mean of U over the scored bank.
- **Abstention (an empty shortlist) scores exactly 0.**

## 3. The shortlist selector (the validator's, never the miner's)

From the model's own predictions over every action in A:
1. keep the actions the model predicts FEASIBLE;
2. keep those whose **predicted** objective beats the fallback's **reference** objective (RES-09);
3. order them by predicted objective, ties by action id;
4. take at most k (HUMAN_INPUT, registered from the buyer's workflow, never from a sweep).

The validator computes the selector and counts the solves. **Miners submit models, never lists.** Every listed action is verified and charged.

## 4. The scored bank

A question is in the **scored bank** only if its fallback is reference-FEASIBLE and it is **decision-determined**:
- every action × condition has a reference result: FEASIBLE, INFEASIBLE, or UNRESOLVED **inside the registered reference band**. A FAILED_REFERENCE or missing result is never allowed;
- **and** every UNRESOLVED action's reference objective is known and **no better** than the best reference-FEASIBLE action. So the question's best action and its gain ceiling are the same however the unresolved actions would resolve.

**An UNRESOLVED action on a model's shortlist** is charged its solves and earns **no gain**. The buyer's own reference check could not certify it either. It is counted in `unresolved_shortlisted`, which feeds the tie-break (§5).

**A fully resolved question is the special case with no UNRESOLVED actions.** Questions whose unresolved actions could beat the best stay out of U (reference-incomplete) until the reference policy resolves them (BANK_SPEC §9, REF-RESOLVE).

All other questions are excluded from U **for every member** and reported with their counts:

| Excluded class | Treatment |
|---|---|
| Reference-incomplete (a failed or missing result, or an unresolved action that could beat the best) | A reference gap, never a candidate failure (invariant 7.5). Re-admitted when completed or decision-determined |
| Fallback-infeasible (rescue) | A separate rescue leg, scored only once a rescue-benefit unit is registered (HUMAN_INPUT) |
| Settled NONE (no feasible action) | No decision value; counted |

So the scored population is **P_V2 = P | fallback feasible**, with w unchanged inside it. Accepting this restriction is an owner population decision, **HUMAN_INPUT**.

## 5. Safety and ties

- **Mandatory admissibility is unchanged:** the active registered candidate's G-FEAS gate, and every adopted physics gate (for example OWNER-PHYSICS-GATES-01 B15), applied before ranking. They are never priced into U (invariant 7.3).
- **Among exactly equal mean U, the tie-break is:**
  1. fewer reference-INFEASIBLE shortlisted actions;
  2. then fewer UNRESOLVED;
  3. then the earliest chain commitment.

## 6. Reported beside U, never folded in

- safety counts;
- missed opportunity: the best known feasible gain minus G, and the ceiling-capture fraction G / G_max on scored questions;
- coverage: verified improvements, fallback kept, abstentions, unresolved;
- the excluded-class counts (§4);
- reuse on registered independent shifted strata, each with its own P. The reuse weight in the score is ρ = 0. A non-zero ρ needs fresh, independent strata and its own confirmation;
- **the cheap-arm margin** (§7).

λ, the cost of a deployed failure, is not in U. Only verified-feasible designs return, so it cancels from rankings. It stays unmeasured, never assumed to be 0.

## 7. The cheap arm and Challenge readiness

- **The strongest cheap arm is preselected and frozen per Challenge before any sealed half is opened:** nearest, bilinear, GP or RBF maps built from public TRAIN references, with the same selector, k and κ. It's registered by the Carbon Validator.
- **A Challenge can carry V2 value evidence only if both hold** on its public development half (the BANK_SPEC winnability check):
  - the cheap arm's ceiling capture is below a threshold;
  - a development reference model shows a positive paired net margin over it.

  Both thresholds are HUMAN_INPUT.
- Whether payout requires beating the cheap arm is owner economic policy.

## 8. Confirmation and takeover statistics

- **Acceptance:** positive mean net U **and** a positive paired margin over the cheap arm, on the sealed half.
- **Takeover:** no relative margin. The rule is an absolute minimum useful gain Δ_min (benefit units), plus a paired, one-sided, question-block-level test at false-takeover budget α, as in rev 5's ≤ 1 % a round. Ties keep the king.
  - Δ_min and α are HUMAN_INPUT.
  - The sealed half must contain enough independent blocks for α to be attainable (BANK_SPEC §5).
- **Abstention, known-bad and adversarial controls** are scored alongside. Always-abstain must score 0, and the bad controls must stay out of the top half (PRIORITIES 2026-10-13, "scoring aligned").

## 9. Rules of change

- This definition is prospective. **It re-scores nothing** (invariant 10): the current registered candidate (OWNER-BATTERY-SCORE-CANDIDATE-01) and all history keep their own rule.
- **Changing u:** κ is re-registered as κ·u_old/u_new, so the preference is unchanged. Any other change of κ is an owner preference change.
- **Any change to §2–§8 is a new definition revision** with a new digest. A value record binds exactly one definition digest.

## 10. HUMAN_INPUT

- P_V2 acceptance, κ, k, u per question law, the fallback per question law;
- the rescue-benefit unit;
- Δ_min, α;
- the cheap-arm ceiling-capture and margin thresholds;
- any non-zero ρ;
- the payout condition;
- mainnet values.
