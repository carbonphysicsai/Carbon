## 2026-10-05 — OWNER-GRAPHITE-TEST-WAVE-04: count constructions by what they build, not how they are written; the frozen rule's tail coverage accepted for testing

**Authority.** The owner, 2026-10-05, in the Test Lead session, answering the
two owner questions from the battery Level 1 loss-expression review packet
(`docs/development/graphite/L1_LOSS_EXPRESSIONS_REVIEW_PACKET.md`, Q7 and Q8).

**Supplements** OWNER-GRAPHITE-TEST-WAVE-01, -02 and -03.

1. **Identity for counting and rewarding is the rebuilt artifact (Q7).**
   - **The owner's answer.** Asked whether every mechanism that counts,
     limits, deduplicates or rewards *distinct constructions* should identify
     a construction by its rebuilt artifact, never by its recipe or
     expression text, the owner answered "yes".
   - **Why.** Many textually different recipes build the same model. Under
     Level 1 loss expressions:
     - `E` and `scale(1, E)` are the same loss;
     - `cap(E, 1e4)` is the same loss when E stays below 1e4;
     - non-canonical reorderings are the same loss.

     A digest of the recipe or expression therefore cannot tell them apart
     (packet U3, "identity aliasing"). Counting by that digest could be farmed
     by trivial rewrites. A copied leader's recipe, reworded, would look new.
   - **What the identity is.** The rebuilt artifact's identity: the trained
     parameters' digest, or the built artifact digest the reconstruction rule
     already binds. Same loss, same seed and same pinned trainer give the same
     artifact.
   - **Where it applies:**
     - leaderboard or nomination entries;
     - per-construction attempt and rate limits;
     - duplicate-submission checks;
     - novelty or exploration counts, including Graphite's own session
       metrics and the attack benchmark's (B2) distinct-attempt counts;
     - any future reward that depends on distinctness.
   - **Where it does not apply.** Per-hotkey and per-campaign limits keyed on
     the participant, not the construction, are unaffected.
   - **Current state.** On main at the time of this decision, no mechanism
     counts or rewards by recipe or expression identity. Incumbent comparison
     and nomination are score-based. The rule binds every mechanism built from
     here on.

2. **The frozen rule's tail coverage is accepted for testing (Q8).**
   - **The owner's answer.** Asked whether the frozen rule's gates and tail
     metrics are adequate to catch metric-aimed training (U1) and tail
     sacrifice (U2) at Level 1, the owner answered "yes ... for testing".
   - **What that means.** For the Graphite test wave, the frozen rule's tail
     coverage is the instrument that detects U1 and U2. Results remain
     alignment findings, measured and reported as τ/ρ, regret, false-feasible
     rate and tail metrics.
   - **What it does not mean.** It is a testing acceptance only. It is not a
     scientific qualification of the frozen rule and supports no claim
     outside the wave.

**No execution.** This record dispatches, provisions and spends nothing.
