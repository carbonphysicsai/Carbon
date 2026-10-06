# CHALLENGE-AI-COOLING-12: registered Graphite-wave practice comparison

**State:** working contract; DEVELOPMENT testing only.
**Authority:** OWNER-GRAPHITE-TEST-WAVE-06 §1; Test Lead's delegated
selection in `docs/development/evidence/cold-plate-equivalence-margin-v1/README.md`.
**Starting base:** `c690f6f702dc91f9237b9853c9e6205cd7841f38`.

## Scope

Wire Cooling's existing public PRACTICE adapter to the accepted, measured
relative margin `0.13157222884271824` and the approved unit-free OD-2
settings (`n_min=30`, `n_boot=4000`, `alpha=0.05`,
`important_min=10`). Keep the existing 100 cases, 30 important cases,
prediction gates, score, baseline and construction contract unchanged.
Version the practice rule identity prospectively as v2, and pin the evidence
record in the comparison identity. A deterministic bootstrap
seed is an implementation choice, not a new scientific threshold.

This is Graphite-wave public adaptive feedback. A `promotable` result here is
only a testing comparison disposition. It is not an official, fresh-case,
scientifically qualified or network winner. Protected cases, seeds and labels
never enter this route. The future 45/30/25 Score Pack and [0,1] score variant
remain separate, unadopted work.

## Evidence and failure policy

- Use the same-case error differences and the same overall, important-region,
  and component trade-off dispositions as OD-2, with Cooling's own three
  components. Positive differences mean the challenger is worse.
- Missing candidate predictions fail the existing schema gate through the
  challenge-neutral coverage rule. A gate failure cannot be compensated by a
  lower soft error.
- Require the complete registered case set with unique case IDs and usable
  reference evidence before a positive testing comparison. Missing or invalid
  reference/infrastructure evidence yields nonnumeric
  `INSUFFICIENT_EVIDENCE`, while known candidate gate failure stays visible.
- Report bootstrap intervals as *descriptive over the fixed, adaptively seen
  public PRACTICE set*, not population confidence or hidden confirmation.
- Historical comparisons remain under their original rule identity; this is
  a prospective policy identity, with no silent rescore.

## Definition of done

1. Cooling-only comparison identity binds the accepted margin record and
   settings; no Battery runtime file or neutral variant registry is changed.
2. Adapter applies the registered rule and refuses incomplete evidence.
3. Focused tests cover exact equality, improvement, important-region trade-off,
   mandatory gate failure, missing/invalid evidence, missing prediction
   coverage, determinism and record pinning.
4. Canonical affected tests and automated acceptance pass; add one lessons
   entry, one PR, and hand it to PR Lead with Codex done.

**Maturity ceiling:** IMPLEMENTED/TESTED for the Graphite DEVELOPMENT wave.
Scientific qualification, fresh confirmation, official scoring, customer
acceptance, LIVE and winner weights remain unavailable.
