# V3-RULE-ROBUSTNESS-01

**Status:** DEVELOPMENT stress test. Owner request 2026-10-10. The adopted
battery v3 rule remains `G-FEAS/A-Q@0.05`; this ticket does not change it.

## Working contract

- Use the public registry-v4 candidate and its actual `score_tuning` scorer on
  synthetic member legs. Never treat invented cases as measured power or
  evidence of a real miner exploit.
- Compare each constructed attack with a declared baseline using raw score,
  gate verdict, synthetic decision loss, and the attack's changed quantity.
- Exercise regret normalization/tails, unnecessary abstention, a concentrated
  feasibility edge error, and an accuracy/regret trade-off.
- Recommend prospective, separately versioned rule probes only. The Test Lead
  owns analysis and the science owner owns any scoring-rule change.

**Primary map_ref:** `WAVE-A/V3-RULE-ROBUSTNESS-01` (historical map only;
Development Hub retired under OWNER-WORKFLOW-SPEED-01). Maturity ceiling:
TESTED synthetic diagnosis. No solver, spend, hidden data, or LIVE use.

## Decision

KEEP the existing `score_tuning` implementation as the single source of v3
arithmetic. WRAP it with an isolated synthetic adversarial panel. This avoids
re-implementing the rule and makes any apparent gain reproducible. Alternative
hard limits and weights stay recommendations, not runtime behavior. No human
input is needed to run the diagnostic; adoption remains reserved.
