# Battery screening grain (SCREENING-GRAIN-01)

**The grain** is the ladder step for battery's immediately published screening scores (OWNER-BATTERY-CHAMPIONSHIP-03 §1). The owner's rule (CHAMPIONSHIP-04 §3): the Test Engineer's measured screening standard error, rounded up to the nearest 0.5 %, with a 0.5 % floor.

**`screening-grain-v1.json` has one entry per rule.** PLT-08 uses the one entry that matches the deployment; with no match it stays SEALED_UNTIL_GRAIN.

| Rule | Score (sense) | Measured SE | Grain | Evidence |
|---|---|---|---|---|
| `v2-bank-sched` | accuracy: pooled mean error (lower is better) | 3.04 % | **3.5 %** | 126 public members × 1,588 cases |
| `v3-bank-sched` | registered `G-FEAS/A-Q>@0.05`: a^0.5 q^0.5 (higher is better) | 2.46 % | **2.5 %** | **thin:** 10 members × 9 public scenarios for q |

**The display convention** is the same for both. It is geometric, rounded toward the worse side, and changes only by at least one step. It is a convention under the owner's decision, not a threshold.

**The methods** use public data only; each is a bootstrap over the pooled screening set.
- `measure.py` (v2): analytic and bootstrap estimates; the larger median is used.
- `measure_v3.py` (v3): 294 cases plus 24 design questions, resampled per member.

**Remeasure** each entry as a new file version when:
- its pooled size changes;
- live scored submissions exist;
- for v3, the PUBLIC-DEV-DECISIONS-01 public run lands, which has far more members and questions.

**A newly adopted rule or candidate** (a v9 or v10 pick) gets its own measured entry before it goes live.
