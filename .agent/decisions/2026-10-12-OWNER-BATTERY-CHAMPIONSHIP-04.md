## 2026-10-12 — OWNER-BATTERY-CHAMPIONSHIP-04: build miner status rows and laddered screening scores now; the grain rule

**Authority.** The owner, verbatim in the Test Lead session on 2026-10-12: "Build the miner status rows and rounded screening scores now; the grain is the Test Engineer's measured screening standard error, rounded up to the nearest 0.5% (minimum 0.5%)." The Test Lead relayed it to the Carbon Validator. The PR Head put it to the owner directly and he confirmed it in that session on 2026-10-12,
before this record was merged: a relayed decision that changes what miners are shown is not
recorded on a relay alone.

**Amends** OWNER-BATTERY-CHAMPIONSHIP-03, prospectively. For these two items only, it lifts that record's "nothing is built until battery finishes". Everything else in -03 stands: one slot per coldkey, championship ranking by the displayed score, ties to the earliest commitment, and the takeover decided only on the fresh batch.

**1. Miner status rows (public, no score).** The validator's signed score feed lists, per hotkey, counts of its submissions in the live deployment:
- received;
- scored;
- refused, broken down by closed refusal code.

It carries no score, no per-window or per-case value, no case identity, and no championship or fresh-batch material. Refusal codes are the closed codes the submitter already sees from the intake status endpoint.

**2. Laddered screening scores (-03 §1, unchanged in form).** The feed's `leaderboard.ladder` carries, per coldkey (the hotkey's owning coldkey read from the chain):
- the pooled screening score only, never per window or per case;
- updated only when a submission beats the coldkey's displayed best by more than the grain;
- rounded to the grain.

Otherwise the status is "no improvement beyond the grain".

**3. The grain rule.** The grain is the Test Engineer's measured standard error of the screening score:
- rounded up to the nearest 0.5 % relative step;
- with a 0.5 % minimum;
- posted on the rules card.

The measurement (method, scored-submission sample and result) is recorded with its evidence. Until it is recorded, `grain_pct` is null and every displayed score stays `SEALED_UNTIL_GRAIN` (fail closed). The status rows in item 1 do not wait for the grain.

**Build.** Platform Codex PLT-08, reviewed by the Carbon Validator as a disclosure path. It ships in the first release after the scheduled-rotation cutover, so it shows submissions to the new deployment only. Testnet DEVELOPMENT only. Mainnet values are not decided here.

**Not decided here:** the grain's measured value; a similarity radius or registration-cost rise (-03 residual); mainnet.
