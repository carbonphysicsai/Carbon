## 2026-10-08 — OWNER-BATTERY-SCORE-RULE-01: battery's scoring rule is A-Q with the G-FEAS@0.05 gate (rule v3, prospective)

**Authority.** The owner, 2026-10-08:
- "approve the scoring rule", relayed by the Test Lead;
- confirmed directly in the Carbon Validator session. Asked whether to
  register it as a new rule version, they answered "Yes, register it".

Adopting a score is the science owner's call (AGENTS.md §5). This record is
that call. It supplements:
- OWNER-GRAPHITE-TEST-WAVE-08 (the score-tuning loop);
- OWNER-BATTERY-SCORING-WINDOW-01 (rule v2);
- OWNER-BANK-ARCHITECTURE-01 (rule v2-bank).

**The rule**, exactly registry v4's candidate `G-FEAS/A-Q` at cutoff 0.05
(`docs/development/evidence/battery-score-tuning/registry-v4.json`, sha256
`44795679e04b62627b8ad396631eae0de8b54e97429012dcc014a29792e4f814`):
- **Score, `A-Q`:** a geometric blend of two legs, weights `{a: 0.5, q: 0.5}`:
  - `a`, accuracy (`ratios.legs`);
  - `q`, Q3 decision regret: 1 / (1 + the mean Q3 decision regret over the
    quiz's feasible decision scenarios), in units of the minimum useful
    improvement.
- **Gate, `G-FEAS@0.05`:** a submission is **ineligible** if its per-case
  false-feasible rate on the scoring set exceeds **0.05**. A gate failure is
  ineligible and is never offset by score (invariant 7.3).

**Evidence:** the sealed tuning curves.
- Inputs: `graphite-tuning-v2`'s commitment (journal sequence 7) and its quiz
  (digest `sha256:347c95…`, journal sequence 8).
- `curves.json`, sha256
  `ee0088a83e86da7758ebd5fda8c3d9a897fae2b56ddac0afbf76a2d27d6a3bfe`
  (aggregates only; the operator's shared tuning inputs).
- Against the deciding rule `CE`:
  - τ 0.227 against 0.146, with Δτ [0.085, 0.141];
  - known-bad models in the top half: 4 of 10, against 9;
  - 4 gate failures;
  - top-1 regret 0.

**How it is registered:**
- **A new, prospective battery rule version** on the main testnet
  deployment: `v3`, and `v3-bank` composed with the bank (OWNER-BANK-
  ARCHITECTURE-01).
- **Applies from rehearsal 3b.** Rehearsal 3a stays on the rule in force.
- **v2 and v2-bank history is unchanged:** nothing scored under them is
  rescored (invariant 10).
- A deployment moves to the rule by naming it.

**Not granted here:**
- any LIVE, reward, mainnet or qualification claim;
- any other cutoff or weighting (a change is a new record);
- the score-to-chain-weight mapping (stage 2 of the loop), which stays with
  the owner.
