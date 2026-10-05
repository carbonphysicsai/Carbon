# SR-M1: motor score candidates, v1

This is **descriptive DEVELOPMENT evidence; nothing is adopted.** Adopting a rule stays with the science owner. The frozen motor rule (`carbon/motor/exam.py`) is unchanged.

**Registration.** The candidates, panels and statistics were committed and pushed in `.agent/tickets/SR-M1_motor_score_candidates.md` (commit `00962445`, 11:31Z) before anything was computed.

**Reproduce.** Run `python -m scripts.dev.motor.score_candidates --out result.json`, which takes about 30 s on CPU. It uses public PRACTICE and TRAIN plus the counted motor replay; nothing is spent. Precheck: the frozen rule F0 reproduces the registered practice scores exactly (textbook 0.5002, KRR 0.1730).

## Widened development panel (16 members): the fairer check

The 16 members are:
- the fixture 5;
- KRR ripple scaled by α ∈ {0.5, 1.5, 2.0};
- KRR mean shifted by δ ∈ {±0.05, ±0.10};
- KRR at 4 other registered-grid settings.

| Candidate | τ-b | ρ | Divergences | τ − F0, paired 95% (2000 case bootstraps) | Beyond band? |
| --- | --- | --- | --- | --- | --- |
| F0 (frozen) | 0.369 | 0.522 | 12 | n/a | n/a |
| A1 (amplitude) | 0.314 | 0.396 | 9 | [−0.169, 0.096] | no |
| **A2 (phase-invariant shape)** | **0.409** | 0.561 | 9 | **[0.002, 0.153]** | **yes, barely** |
| B (frozen + optimism bias) | 0.388 | 0.533 | 9 | [−0.076, 0.095] | no |
| C (decision-aware) | 0.314 | 0.426 | 10 | [−0.169, 0.211] | no |
| A1B | 0.390 | 0.468 | 7 | [−0.112, 0.135] | no |
| A1C | 0.295 | 0.375 | 9 | [−0.170, 0.116] | no |
| A1BC | 0.371 | 0.448 | 7 | [−0.112, 0.154] | no |
| A2B | 0.428 | 0.572 | 8 | [−0.037, 0.154] | no |

## Fixture panel (5 members): circular, reported for completeness

These are the 5 members that motivated the study, so a fix "working" here proves little.
- F0: τ = 0.0, with 3 divergences.
- A1, A2, C and every combination except B: τ = 0.82, with 0 divergences.
- B: τ = 0.26.

## Reading

- **Only A2 clears the registered band, and only just.** A2 replaces the pointwise ripple-shape error with its minimum over circular shifts. That removes the phase penalty that made F0 rank the phase-shifted control last. Every other candidate's paired interval includes 0.
- **The decision-aware term C and the amplitude term A1 do not beat F0 on the widened panel.** Fixing the fixture panel did not generalise to them.
- **Decisions ignore a ±10% mean bias.** All four bias members keep KRR's choice (d06), so any score term on mean bias is decision-irrelevant on this set.
- **Side finding:** KRR at (length 8, ridge 1e-4) and at (4, 1e-2) select the true best design, d04, with regret 0. The selected (4, 1e-4) selects d06, with regret 0.0192. That is a finding about the hyperparameter selection, not a scoring claim.
- **Limits.** n ≤ 16; the members are not independent (11 derive from KRR); the controls were constructed by us; the band covers case sampling only. **Not promotable.** Confirmation needs Graphite's motor constructions and motor-graphite-confirmation-v1, under a frozen analysis.
