# EV5: results

This is public synthetic DEVELOPMENT evidence:
- no chain action, reward or weight change;
- the testnet rule stays deciding;
- no qualification claim;
- no level above 0 is opened.

A rung pass needs all three verdicts **and** the owner's signed lock (OWNER-TRACK-A-L0-02).

**Run.** The run used the code frozen at `c9c27a63` (EV5-RUN-01, #631). `ev5_run verify` passed on all 1017 files before every step. Every output records `checkout_head`.
- **Authority:** OWNER-EV5-GO-01, under OWNER-EV5-CAP-01 as amended by OWNER-EV5-GPU-01.
- **Interpretation choices:** all 13 were ruled by the Test Lead before any data. See `.agent/tickets/EV5-RUN-01_analysis_and_confirmation.md`.
- **Deviations:** six, listed in `run-record.json` under `deviations`.

## Verdicts (never blended)

| Verdict | Result |
|---|---|
| Value (reported, not graded) | **H1** DECIDING_CONFIRMED · **H2** DOES_NOT_HOLD · **H3** separation HOLDS |
| Adversarial score | **FAIL** |
| Construction integrity | **PASS** |

**H1.** Δτ = τ(`sr2-a0-r0.3-g0.6-m0.1`) − τ(`control-exam-v1`) = 0.373 − 0.402 = **−0.029**. The 95 % paired-bootstrap interval is [−0.132, +0.074] (99 eligible real members, 12 verification conditions, B = 10000, seed 20261001).
- **Promotion conditions:**
  - the interval's lower bound is not > 0;
  - Δτ does not exceed the τ noise band (0.100);
  - across-family divergence is 12 for the candidate against 10 for the deciding rule.
- **None of the three holds**, so the deciding rule is confirmed for ranking.
- The secondary gated pair, reported only: Δτ −0.022, [−0.096, +0.054].

**H2.** At 2.0 bands:
- **Controls:** the boundary optimist FAILs; oracle, conservative and rank-preserving delay PASS.
- **Real members:** 20 of 99 fail, which is not more than half.
- **Difference:** the mean verification-loss difference, FAIL minus PASS, is **+0.80**, but its 95 % interval [−0.79, +2.33] includes 0. So H2 does not hold.

**H3.**
- The sign-error control's near-limit false-acceptance rate is 0.946, above every eligible real member's (all are measured), so separation **holds**.
- No rule ranks the control last, and the gate passes it.
- Only the descriptive measurement catches it.

**Adversarial score: FAIL.**
- **Track A:** 8 of the 10 Track A rebuild-identity constructions select a protocol the reference verifies infeasible in some EV5 scenario, and rank in the top half under the deciding rule plus the gate. Ranks run from 6 to 47 of 100.
- **Mode X:** reference-verified violations for best_deciding (`mlp_t6000_w256_d3_ens2-s0`, rank 1) and best_proposed (`mlp_t6000_w512_d3-s1`, rank 23). Both pass the gate. There are 25 in-band and 21 out-of-band findings in total.
- The literal-0 sensitivity line, which enters no verdict, is in `analysis.json`.

**Construction integrity: PASS.**
- Track A families are all IN_PROGRESS with 0 findings.
- The 21 frozen typed refusals still hold.
- 110 of 110 rebuilds match the frozen panel.
- **Worker-boundary scan.** CI's service lane was skipped at `c9c27a63` (run 37328226257). Under the Test Lead's ruling (option d, decided before the result), the scan ran at that exact checkout on the operator host, with CI's own lane scripts: 2 passed. The record is `worker-boundary-scan.json`: worker image `sha256:427997a0…`, output sha256 `d5709d56…`.

## Confirmation batch (sealed; descriptive; enters no verdict)

- **Batch.** Regenerated from the deployment's committed root and recalled against fingerprint `sha256:0add08ed…` at journal sequence 14 (recall never commits).
- **Solves.** 120 of 120 distinct cases were solved OK on the operator host in the pinned truth image. The 4 hidden duplicates reuse their originals' solves.
- **Predictions.** All 110 models were rebuilt on host CPU.
- **Report.** Owner-only and **not published here** (ruling 12). Nothing private is in this directory.

## Files

| File | What |
|---|---|
| `results.json`, `report.md` | The engineering-value results (`python -m carbon.battery.value evaluate`) |
| `analysis.json` | H1–H3 and the three verdicts (`ev5_run analyse`) |
| `gate.json` | Gate verdicts and candidate scores (`ev5_run gate`) |
| `optimizer/` | Selection, report, findings, verification references |
| `decision-references.jsonl.gz`, `references.sha256`, `predictions.sha256` | The 840 decision references and the digests of every reference and prediction bundle (bundles stay on the operator host) |
| `plans/optimizer-*` | The post-selection verification plans (commit `94211d1d`) |
| `worker-boundary-scan.json` | The scan at the exact checkout |
| `run-record.json` | The pinned digests and the six deviations |
| `accounting/ledger.jsonl` | The public projection of the pod ledger (no balance, spend, cap or rate) |
