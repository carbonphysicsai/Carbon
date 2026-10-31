# OWNER-CROWN-MARGIN-2SD-01: the testnet crown margin's seed-spread term is 2 × the control's seed standard deviation, for now

Date: 2026-10-31 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "I guess c for now" (earlier "C", then "So maybe d?", answered by the Lead's lottery-tweak explanation).

## Context

Under the registered statistic (the largest seed-to-seed swing of the control's total, under OWNER-KOTH-MARGIN-SEED-SPREAD-01), the Burst Thermal 2.5 margin came out at 0.064, about 17% of the baseline. The control's 10 seed totals split into two groups (~0.45 and ~0.49–0.51), with no clear outlier. The four options offered were: (a) max swing; (b) max swing with one outlier dropped; (c) 2 × the seed SD; (d) the mean pairwise difference. (d) was set aside because public catalog recipes with trivial tweaks act like seed re-rolls, which makes crowns a lottery.

## Decided

- On the testnet launch versions, the KOTH margin's seed-spread term is 2 × the standard deviation of the control model's per-seed totals, in place of the largest swing. One rule across all launch Challenges (Burst Thermal, Motor, Ribbed Bracket, and Cooling when measured).
- The rest of OWNER-KOTH-MARGIN-SEED-SPREAD-01 stands: the margin is at least the larger of the same-recipe rebuild noise and this term, and values are used as measured. The Validator computes and receipts them. The 10-31 estimates are Burst Thermal ≈ 0.047, Motor ≈ 0.0079, Ribbed Bracket ≈ 0.0061.
- "For now": revisit on week-1 crown-turnover data.

## Bounds

- Testnet only. No rescoring of anything already graded.
