## 2026-10-11 — OWNER-BATTERY-CHAMPIONSHIP-02: the championship's false-takeover rate stated openly, and the guard keyed to how a batch is drawn

**Authority.** The owner, 2026-10-11, verbatim in the Test Lead session: "approve". Relayed by the Test Lead to the Carbon Validator session.

This is a scientific and process value, not a security acceptance. It approved two things:
1. keeping the false-takeover target at 1 % per round, stating openly in the miner one-pager what that compounds to;
2. the Test Engineer's strengthened guard (`REV5_STRESS_NOTE.md`, MARGIN-SIZING evidence): the SE from block means, with a t-quantile on blocks − 1 df, keyed to how a batch is actually built.

**Amends** OWNER-BATTERY-CHAMPIONSHIP-01, prospectively. Nothing is built yet: the build waits for battery's finish.

**1. The false-takeover rate, stated.**
- **The target:** at most 1 % per round, unchanged.
- **Compounded over rounds in which no entrant is truly better:**
  - about 7 % a week: 1 − 0.99⁷ = 6.8 %;
  - about 26 % over 30 rounds: 1 − 0.99³⁰ = 26.0 %.
- These are upper bounds. When the king is genuinely better than the field, the rate is lower.
- The miner one-pager states the monthly figure.

**2. The guard, keyed to the draw.** An entrant must have:

`mean(d̄_b) > t(1 − 1 % ÷ K; B − 1) × sd(d̄_b) / √B`

where:
- d̄_b is the entrant's mean paired improvement over the king within draw block b;
- B is the number of blocks;
- K = 10, so the one-sided level is 0.001.

Each Challenge declares its draw unit, and the build reads it from the Challenge, never assumes it.

**Battery's draw unit: the single case.** It is confirmed against the code:
- `seeds.make_batch` draws each case independently, from its own derived seed (`draw_inputs`: uniform over `INPUT_BOUNDS`);
- no case shares an operating condition with another;
- bank tranches use the same draw.

So for battery, B = n, and the guard is the plain paired guard on t(n − 1). That gives about 3.09 at n ≈ 4,000; the earlier record's z = 3.090 was its large-n limit.

The championship batch kind is drawn with `make_batch`. Its unit stays the single case unless a later record changes how the batch is built.

**Before the mean and the SE:**
- **Hidden duplicates.** Each hidden duplicate pair (`make_batch`'s `duplicates`) is collapsed to one case. A deterministic model gives identical errors on both, so counting both would understate the SE.
- **A q leg.** If the picked rule keeps one, its part of the composite is resampled by design question: its unit is the question.

**Other Challenges** (motor, cooling and later ones) post no guard until they declare their draw unit and measure their paired noise (OWNER-BATTERY-CHAMPIONSHIP-01 item 9).

**Not decided here:** the score-proof pick, the pod spend, and mainnet values.
