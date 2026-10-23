# OWNER-DESIGN-DECISION-FIDELITY-01: more decision questions per batch in the design half

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Carbon Validator's session ("yes I like this add"), answering the Validator's proposal. The owner's motivation: "there just needs to be more fidelity in the score. Actual formulas that measure the quality of the design impact".
Builds on: OWNER-EVALUATION-FOCUS-AND-DATA-CYCLE-01 (Design = min(verified achieved-value credit, decision-critical prediction credit)) and OWNER-DESIGN-VALUE-01 ("changing best answers across strata or question draws").
Scope: DEVELOPMENT / testnet. These are new sealed evaluation versions for F08, Motor and Cooling, built in the min(V, C) move (VALIDATOR_D_AUDIT_20261023.md). No LIVE or mainnet authority.

## Decided

**Achieved-value credit V is the equal-weight mean of three continuous decision measures, in each Challenge's buyer units, from the existing references:** no new solves.

1. **Pairwise ordering (V_pair).** For every pair of candidates, the model's predicted objective orders them, and the order is checked against the reference.
   - A misordered pair costs its true objective gap.
   - V_pair = 1 − (sum of the misordered gaps) / (sum of all the gaps).
   - Pairs whose true gap is within the reference resolution are excluded.
2. **Accept/reject (V_feas).** For each candidate, the model's feasible/infeasible call is checked against the reference.
   - A wrong accept costs the true limit violation, divided by the registered critical scale.
   - A wrong reject costs the true margin given up, divided by the same scale.
   - V_feas = 1/(1 + the mean cost).
3. **Nearby variants (V_var).** The pick question is re-asked with each Challenge's main limit shifted by **±5%** (the proposal, adopted as the starting value). V_var = the mean of the existing V = 1/(1 + regret/D_scale) over the base question and the variants.

**C is unchanged from the plan:** the worst normalised signed-margin error over every candidate, including unselected ones. **D = min(V, C).**

## Not decided here

- The ±5% shift and the equal weights are **starting values**. The owner sees the proof-run results (VALIDATOR_RECAL_SEED_SPREAD_SPEC_20261023.md) before they are final.
- The scales are the existing registered dev1 §7 values; no new scale is chosen here.
