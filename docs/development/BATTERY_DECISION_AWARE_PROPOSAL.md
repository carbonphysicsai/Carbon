# Battery: the decision-aware exam rule, proposed prospectively

**Status.** PROPOSED, NOT DECIDING. Registered as
`carbon.battery.exam.decision-aware.proposed`, version 1
(`carbon/battery/value/proposal.py`), under
OWNER-BATTERY-DECISION-AWARE-PROPOSAL-01 (`.agent/DECISIONS.md`, 2026-10-01).

- **The deciding rule is unchanged.** It stays the frozen
  `carbon.battery.exam.v1` (OD-2) until the proposal's own approval changes
  that. The proposal is not in `exam.RULES`, so no deployment can select it,
  and a test holds that.
- **Prospective only.** Every past result keeps the meaning of the rule it was
  scored with (invariant 10). Nothing is rescored or reinterpreted.
- **Not exam qualification.** This is exploratory engineering evidence feeding
  qualification. MQ-008 is untouched, and whether the exam is adequate stays
  open.

## What is proposed

The score is EV2's development-chosen profile `dar-p0-r100-a0`, a decision
agreement score. Every scoring case is checked against every contract
constraint. The model's PASS/FAIL call, made from its own predictions, is
compared with the reference's call within the contract's uncertainty bands,
and unresolved reference calls are excluded. A false acceptance costs 10 and a
missed opportunity costs 1. The score is `1/(1 + mean cost per resolved
call)`. Gates stay mandatory.

No number is new here. The constraints, bands and costs are those of the frozen
EV2 contract, pinned by digest
`sha256:18770910…ce743`. The costs are `PROVISIONAL_DEVELOPMENT`.

## Both rankings, side by side

From EV2 (`docs/development/evidence/ev2-2026-10-01/results.json`). Each row
carries both questions, and neither leads.

| Rule | Ranks real models (τ with decision loss, verification) | Catches the boundary-optimist control |
|---|---|---|
| deciding `carbon.battery.exam.v1` | **0.298** | **no**: the control scores at or above all 14 eligible members |
| proposed `dar-p0-r100-a0` | **0.202** | **yes**: the control scores below all 14 |

Basis: `comparison.<rule>.tau_verification` and
`summary.boundary_optimist_check`.

**What the evidence says.**
- **The proposed rule closes a blind spot.** The deciding rule ranks a model
  that is accurate almost everywhere, but optimistic at the plating and
  temperature limits, above every real model. EV1 found the same.
- **The proposed rule costs ranking quality on this panel.** It ranked real
  models less well than the deciding rule (0.202 against 0.298).
- **One panel does not show that the trade is right.**
  - With 14 members, a τ difference of 0.1 is within noise. Under
    independence, the standard error of one τ is about 0.20 at n = 14.
  - 9 of the 14 members lose less than 0.2 on verification, so the
    decision-loss ranking is close to ties.

**From here on, every engineering-value report shows both rankings this
way.** `carbon/battery/value/report.py` (`two_rankings`) puts the table near
the top of each report, whenever a run carries both rules.

## What would settle it (not run; needs approval)

The open question is whether the proposed rule's lower τ is real, or an
artefact of a panel whose members barely differ. A second question follows:
does the blind spot it closes matter for real models, not only for a
constructed control? One pre-registered experiment answers both.

**EV4: a panel built to separate decision quality.**
1. **A larger, deliberately diverse panel of real models.** About 60 eligible
   members across the registered families (MLP, DeepONet and kNN variants),
   with training budgets and widths varied on purpose, so that decision losses
   spread instead of tying. The independence approximation puts the standard
   error of τ at about 0.09 at n = 60 and about 0.07 at n = 100, against 0.20
   at n = 14.
2. **Fresh verification conditions,** none from EV1 or EV2. Each condition
   should have feasible protocols near the limits, where optimism costs most.
3. **A paired comparison,** fixed before any solve: the difference in τ
   between the two rules, with a bootstrap interval over members and
   conditions. A difference whose interval excludes zero decides H1. One that
   does not is reported as unresolved.
4. **The real-model blind spot:** count the real members that make
   false acceptances near the limits, and report how each rule ranks them.
   This tests whether the blind spot bites outside the constructed control.

**What it would cost.**
- **References:** EV2 used 560 PyBaMM solves (16 conditions × 35
  candidates). EV4 at 16 fresh conditions is the same 560. At 24 it is 840.
- **Reconstructions:** about 60 members instead of 15, on public TRAIN v1.
- **Money:** EV2 ran on local CPU at USD 0 (EV2 doc §5), and EV4 can too.
  OD-5's ceiling is untouched.
- **Time:** EV2's 560 solves and 15 members ran from 2026-09-30 to
  2026-10-01, with interruptions. EV4 is roughly four times the
  reconstruction work, so expect several days of host time on this machine,
  shared with the other sessions.
- **Not started.** It needs its own pre-registration and the owner's
  approval, and its panel size and conditions are proposals for that
  approval.

## What does not change

- No exam rule, deployment, reward, weight or chain action.
- No threshold, tolerance, cost or population is chosen here. Every value
  above is the frozen EV2 contract's, or an EV2 measurement with its basis.
