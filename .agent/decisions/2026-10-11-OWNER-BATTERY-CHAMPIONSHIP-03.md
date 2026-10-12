## 2026-10-11 — OWNER-BATTERY-CHAMPIONSHIP-03: screening scores published on admission, under a per-coldkey ladder, and one championship slot per coldkey

**Authority.** The owner, 2026-10-11, verbatim in the Test Lead session (relayed by the Test Lead to the Carbon Validator session):

> I like that a lot more. And I'd like to limit people to one slot if
> possible.

It approved two things:
1. publishing screening scores immediately on admission, rounded, in place of the ~18 h sealed release for screening;
2. one championship contention slot per coldkey.

**Amends** OWNER-BATTERY-CHAMPIONSHIP-01 and -02, prospectively. It also reverses, for battery's screening score only, the sealed rule that a score is public only after all its windows are released (score feed `VALUES["live"]`). Championship results remain public immediately after each round. Nothing is built until battery finishes.

**1. Immediate screening scores, released through a ladder.** On admission, a submission's pooled screening score is published at once, in rounded form. Only the pooled score is published: never a per-window score, never per case.

The displayed score follows a **ladder** (Blum and Hardt's "Ladder" leaderboard mechanism), **kept per coldkey**:
- a coldkey's displayed score changes only when one of its submissions beats the coldkey's displayed best by more than the grain;
- the new display is that score rounded to the grain;
- otherwise the display is unchanged, and the submission is shown as "no improvement beyond the grain".

**The grain** is one standard error of the screening score, measured by the Test Engineer from scored submissions and rounded up to a 0.5 % relative step, with a 0.5 % floor. It is posted on the rules card. Until it is measured it is HUMAN_INPUT, and screening scores stay sealed (fail closed).

**Championship entry ranks by the displayed (laddered) score.** A tie goes to the earliest chain commitment.

**2. One slot per coldkey.**
- At the cut-off block, each eligible model's coldkey is read from the chain: the hotkey's owning coldkey at that block.
- Of a coldkey's hotkeys and artifacts, only its best-ranked eligible model can be among the K = 10.
- The king's coldkey may still enter one other model.

**Why it is safe, and what remains:**
- **The decider is unchanged.** A takeover is decided only on the round's fresh, single-use batch, with both bars. Immediate screening scores affect who enters, never who wins. The false-takeover bound (≤ 1 % a round) holds whoever enters, including near-copies.
- **Probing the screening cases.** The bank reuses each case in up to E = 5 windows, so an immediate score on a live window can be probed by submitting variants. These bound it:
  - the per-hotkey window limit;
  - rounding;
  - the ladder, which releases nothing for a submission that does not beat the coldkey's best by the grain;
  - publishing only the pooled score.

  The worst outcome is a variant overfit to screening taking an entry slot. It cannot take the crown without winning on fresh cases.
- **Residual: multiple coldkeys cannot be fully prevented.** Hotkey registration has a cost, but coldkeys are free.
  - D6 exact-digest dedup refuses an identical recipe from a second coldkey.
  - A near-identical variant (no similarity radius, by the owner's earlier D6 choice) can still hold a second slot, and the ladder's bound is per coldkey.
  - So one actor with many coldkeys can crowd entry slots and probe more. They still cannot raise the false-takeover rate.
  - A similarity radius or a registration-cost rise would be a separate owner decision.

**Not decided here:** the grain's measured value, mainnet values and the pod spend.
