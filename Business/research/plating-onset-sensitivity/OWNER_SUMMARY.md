# Does near-onset reference noise explain the unsafe picks?

**DEVELOPMENT sensitivity; no historical relabeling or qualification.**
The requested **2 mV plating-only censor changes no action label, decision
loss, member rank or score/value tau** on the public EV4 evidence. It does
not explain away the unsafe-pick result. The old contract already treats
plating inside 1.97 mV as unresolved; near-onset actions still fail when
another hard constraint fails. Sources: [report](REPORT.md),
[measurements](results.json), [pinned evidence](README.md).

Keep the two model cohorts separate:

| Verification cohort | Unsafe events | Within 2 mV | 2-4 mV | Above 4 mV |
| --- | ---: | ---: | ---: | ---: |
| Original 99 eligible EV4 members | 69 | 0 | 48 (69.6%) | 21 |
| RES-07/08's 100 public CPU rebuilds | 72 | 0 | 50 (69.4%) | 22 |

These are measured counts, low=base=high, rather than population estimates.
Each event costs the historical 10 loss units, so raw penalty shares match
event shares. The member-normalized 2-4 mV shares are 68.75% / 68.71%.
All the 2-4 mV events fail only plating. The CPU cohort's 50 such
events reuse **four physical action/condition pairs**, with 48 events at
9 C / initial SOC 0.06. Those four pairs are the useful next public reference
checks, not 50 independent measurements. [REPORT.md](REPORT.md) lists them.

Across development and verification, 42 of 835 available actions lie within
2 mV: 27 are already UNRESOLVED and 15 INFEASIBLE because they fail CV reach.
The historical cohort selects one such reach-failing action 52 times; the CPU
cohort selects it 50 times. These are **reach failures**, not definite plating
failures. None becomes safe when plating uncertainty is acknowledged.

Blindly censoring the whole action status would erase those independent
reach failures and also censor settled-NONE abstentions. It moves pooled
historical ranks to tau=0.787 and CPU ranks to tau=0.793; on a common question
mask both remain tau=1. This illustrates censoring and denominator effects,
not repaired models or confirmed reference errors.

The owner-reported mesh-convergence concern remains material: most unsafe
verification picks sit just outside the existing band. This audit measures
distance, not a calibrated error distribution. It applies no uniform 1.8 mV
correction and cannot say those four plating labels are wrong. Recommend
checking their convergence before drawing stronger physical conclusions;
any band or label policy is **HUMAN_INPUT** for the Validator and owner.
No sealed score-proof or PICK-01 data was inspected. No new solves or spend.
