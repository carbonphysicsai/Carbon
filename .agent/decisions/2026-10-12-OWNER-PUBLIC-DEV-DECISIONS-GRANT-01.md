## 2026-10-12 — OWNER-PUBLIC-DEV-DECISIONS-GRANT-01: USD 8 for the public-dev-decisions RunPod run

**Authority.** The owner, 2026-10-12, confirmed directly in the PR Head
session. He was asked to confirm the cap because the Test Lead's relay
reported "Yes for all 3 #1s" and flagged the figure as eight dollars "not 6",
so the number had been ambiguous somewhere. Asked which it was, he chose:

> Yes — eight US dollars

He had earlier been relayed as approving "PUBLIC-DEV-DECISIONS-01, USD 8,
RunPod, public data only". This record rests on his own word, not the relay,
as `RUN_SHEET.md` requires: "Spend only under
OWNER-PUBLIC-DEV-DECISIONS-GRANT-01, once the owner has confirmed it in PR
Head's session and it is merged."

**The grant.**
- **Cap: USD 8**, all in. This is a ceiling, not a target.
- **Platform:** one RunPod Secure Cloud CPU pod, 32 vCPU / 256 GB, at
  USD 1.76/h, from the truth image by digest.
- **What that buys, as the run sheet projects it:** about 4.5 pod-hours, a
  14,400 s solve budget, about 110 questions fitted, and about 64 resolved at
  EV4's 58% mask rate. The USD 6 alternative projected about 90 questions and
  about 52 resolved, short of the 64 target. The mask rate comes from EV4's
  7 of 12; refinement should raise it, but that is not measured.
- **Public data only.** No sealed, hidden, tuning or bank material. The code,
  the seed, the questions, the references and the results are all public, so
  the run needs no custody record.

**Not authorized by this.**
- No further pod, no second run, and no overrun past USD 8. An overrun needs
  its own owner acceptance, as the score-proof pod's did
  (`OWNER-SCORE-PROOF-RUNPOD-OVERRUN-01`).
- No agent holds a RunPod key or touches the pod. The owner creates it, waits,
  and fetches; Data Collection only prepares the spec, into a private file on
  the operator host and never the repository.
- Nothing scientific. No qualification, score, ranking, frontier or product
  claim follows from the run.

**The lesson that applies.** `OWNER-SCORE-PROOF-RUNPOD-OVERRUN-01` recorded
that a pod under a capped grant needs a termination that does not depend on
the owner being at the PC, and that the next RunPod grant should name a hard
stop. This grant's run sheet sets `PROBE_DEADLINE` to creation plus the
grant's pod-hours minus 0.1 h, which is that hard stop in the pod's own
environment rather than a human watching a clock.

**Spend figures.** The pod's actual hours and charge go in the operator's
private ledger, not here. The public repository holds caps and rates, never
spend totals.

**Maturity.** DEVELOPMENT spending authority only.
