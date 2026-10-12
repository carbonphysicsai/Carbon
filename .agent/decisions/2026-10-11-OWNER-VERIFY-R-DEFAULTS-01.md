## 2026-10-11 — OWNER-VERIFY-R-DEFAULTS-01: VERIFY-R's k, budget and regret unit for the score proof

**Authority.** The owner, verbatim, relayed by the Test Lead: "approve
VERIFY-R defaults". These are the Test Engineer's recommended defaults
(`~carbon/shared/evidence/verify-r/`, 2026-10-11). VERIFY-AWARE-SCORE-01
left these values HUMAN_INPUT.

**Values.**
- **k:** 1, 3 and 5 are registered as curve points; 3 is picked. k = 1 is
  Q3's single pick, so it gains nothing from verification; 3 lets a model
  recover from one or two near-limit misses; 5 is the sensitivity point.
- **Verification budget:** k complete panels, at 120 s wall each. 120 s is
  about 1.5 times the measured median solve (82 CPU-s per solve on the
  pinned truth image, B4's 210 solves).
  - **Amended 2026-10-12 (SCORE-PROOF-01 amendment 9).** As first recorded,
    a solve that ran longer used up budget and could stop the list early,
    with the stopped share reported. In the run that stopped 35-42% of
    lists. The recorded `wall_s` measures the solver host, not the model
    being judged, and slow solves cluster on near-limit, refined lattice
    points, so charging it biased against exactly the picks that matter.
    Every verified panel is now charged the registered 120 s allotment, so
    the budget is exactly k panels. Overruns are counted
    (`panels_over_allotment`) and unmeasured records are counted
    (`cost_unmeasured_panels`), but neither stops a list. The owner
    confirmed this change directly in the PR Head session; k, the 120 s
    allotment and the regret unit below are unchanged.
- **Regret unit:** 1,200 s. That is EV4's false-acceptance cost (10) times
  its minimum useful improvement (120 s), which keeps EV4's provisional cost
  ratios: finding nothing feasible costs 1.0, as a false acceptance does,
  and each 120 s of gap costs 0.1.

**Scope.**
- The values apply to VERIFY-R on the battery tuning quiz's Q3 lattices in
  the score proof (SCORE-PROOF-01 amendment 8, registry v8,
  `carbon/battery/value/verify_quiz.py`).
- No rule is adopted: the owner picks from the selection as before.
- EV4's mistake costs remain PROVISIONAL_DEVELOPMENT.

**Maturity.** DEVELOPMENT only.
