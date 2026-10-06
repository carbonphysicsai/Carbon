# SCORE-TUNE-B1: the battery score-tuning loop (harness)

**Authority.** OWNER-GRAPHITE-TEST-WAVE-08 (#647), as the Test Lead assigned it to Data Collection on 2026-10-05.

**Scope (this PR).** The fixture-tested harness `carbon/battery/value/score_tuning.py`. It computes nothing on real data.

**The loop.**
1. **Panel.** Graphite L0 constructions from the R3 runs, EV4's 100 recipes and the constructed controls. Each member's stored predictions are on the tuning set (`graphite-tuning-v1`), which the Validator's tooling scores operator-side once sealed. `member_legs` gives each member's legs (a, r, g, m, n, p) and gate measures (near, envelope).
2. **Candidates.** Each is registered before computing, in a committed registry file that is clean in git (`load_registry` refuses otherwise). The diagnosis and the near-limit legs seed them. Results record the registry's commit and sha256. An unregistered id is refused.
3. **Evaluation.** Stored predictions are re-scored, with no retraining, against development decision value: EV4's dev conditions with refined references, on the common resolved mask. The measures are:
   - τ-b and ρ, with the seed band;
   - paired Δτ against the deciding rule;
   - regret;
   - the top choice's false-feasible rate;
   - divergences;
   - the unsafe-winner check.

   A gate failure ranks strictly last (the EV5 ruling).
4. **Survivors** go to the Validator's development score variants, for a Graphite pressure run and Attacker Mode X.
5. **Stage 2.** `chain_mappings`: what winner-take-all, top-k-equal and top-k-rank payouts would pay in decision value, and the weight they put on unsafe members.

**Folded in.** The decision-sensitivity diagnosis (`diagnosis`): sensitive scenarios, mask coverage, and each leg's alignment with decision value.

**Not done here.** The panel's real data, the registry's real candidates, refined references (the separate DEVELOPMENT-only policy). Nothing is adopted. No rule, gate or reward changes.
