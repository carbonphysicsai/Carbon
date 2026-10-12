## 2026-10-12 — OWNER-SCORE-PROOF-PICK-01: the score proof's confirmation pick is G-FEAS+ENV/A-Q@0.01

**Authority.** The owner, verbatim, typed in the Test Lead session on 2026-10-12: "I pick G-FEAS+ENV/A-Q@0.01 for the confirmation".

**The pick.**
- **Rule:** `G-FEAS+ENV/A-Q@0.01`, from registry v8.
  - It is A-Q (accuracy with Q3 decision regret, 0.5/0.5).
  - It has two gates: per-case false feasibility, failing at or above 0.01, and the envelope gate at 1.0, failing at or above (SCORE-PROOF-01 amendment 7).
- **From:** the v8 selection rerun (`proof-v8/selection.json` on the AX42), where it is marked pickable under SCORE-PROOF-PICKABLE-02, with no failed screens.
- **What the owner saw before picking:** these aggregates for the sweep G-FEAS+ENV/A-Q@0.005–0.02, as the Test Lead relayed them:
  - τ 0.248 [−0.065, 0.388];
  - top-1 regret 0.023;
  - gate recall on the unsafe members 1.

**Frozen.** The pick is fixed by this record before the confirmation unlock (amendment 5). The confirmation (`SCORE_PROOF_TONIGHT.md` C′2, producer-code-r8.3) tests it against the rule in force, `G-FEAS/A-Q>@0.05`, as the one registered contrast.

**Not decided here.** Adoption into any deployment's scoring needs its own owner record, and only if the confirmation verdict is PROVEN.

**Maturity.** DEVELOPMENT only; no rule, gate, reward or LIVE state changed.
