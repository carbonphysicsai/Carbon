# Battery screening grain (SCREENING-GRAIN-01)

**The grain** is the ladder step for battery's immediately published screening scores (OWNER-BATTERY-CHAMPIONSHIP-03 §1). The owner's rule, 2026-10-12: the Test Engineer's measured screening standard error, rounded up to the nearest 0.5 %, with a 0.5 % floor.

**The value:** `screening-grain-v1.json` gives a grain of **3.5 %**, from a measured SE of 3.04 %. PLT-08 reads this file; without it, screening scores stay sealed (SEALED_UNTIL_GRAIN).

**The method** (`measure.py`, public data only):
- **The data:** the EV4 public scoring set (1,588 common scorable cases) and 126 eligible public members (srb1-ev4, graphite-run5-q1).
- **The score:** the pooled screening score is a member's mean per-case error over **294 cases**: 3 active batches × 98 scored cases, from `carbon/battery/exam.py`'s rule v2.
- **Two estimators of its relative SE:**
  - analytic: sd/mean/√294, median 3.04 % (P10 2.25 %, P90 3.47 %);
  - bootstrap: 294 cases drawn without replacement, 4,000 times; median 2.77 % (P10 2.04 %, P90 3.17 %).
- **The measured SE** is the median member under the larger estimator: **3.04 %**, which rounds up to **3.5 %**.
- **Robustness:** the P90 member also rounds to 3.5 %. PROVEN-LEADERBOARD-01's earlier measurement on the same data also gave 3.5 %.

**Remeasure** when the pooled screening size changes, or once scored live submissions exist (the owner's record says "from scored submissions"; this is the public-data stand-in). A new value is a new version of this file, never an edit.
