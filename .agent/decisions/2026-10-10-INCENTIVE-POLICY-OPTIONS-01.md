# INCENTIVE-POLICY-OPTIONS-01-D1 — separate deduplication and target attribution

**Status:** implemented working analysis decision; no runtime policy adoption.

**Problem.** #974's four-hotkey effect is extra screening opportunity, while
the owner's canary also asks whether a duplicate rebuilt artifact can multiply
or divert a target. An artifact reward cap without pre-screen deduplication
does not answer the first question; a best-model target does not identify its
rightful recipient.

**Recommendation.** Model exact digest deduplication before score queries and
compare two target-attribution counterfactuals, equal split and authenticated
first-claimant. Model near-duplicate grouping as a separate, explicitly
unqualified similarity assumption. Retain one winner target per window from
#974, and state that simultaneous duplicate publisher claims require the live
canary. Keep actual emission and receipts outside the model.

**Location.** `scripts/dev/incentive_policy_options.py`, its manifest, curves,
tests and `docs/development/incentive-policy-options/README.md` on
`codex/incentive-policy-options-01`, initially stacked on #974 and then
reconciled to merged main for canonical CI.

**Alternatives.** Treating every hotkey as an independent artifact reproduces
the #974 vulnerability; capping targets without deduplicating screens leaves
that route open. Inferring a production near-duplicate metric from synthetic
coordinates would invent evidence. Choosing an attribution owner here would
cross the owner's economic authority.

**Affected boundaries.** No public interface or reward code changes. No hidden
data, solver, AX42, chain, or LIVE use. Scientific comparison, target-weight
accounting, and actual settlement remain separate. This is reversible by
discarding the development analysis. A future adopted rule would require a
new, versioned validator/publisher policy and ownership migration decision.

**Supersession path.** Change the manifest assumptions, `episode`/`_eligible`
and `_credit_shares`, tests, and the decision report together. The owner must
select any margin, decay, duplicate identity, attribution, or emission change.
