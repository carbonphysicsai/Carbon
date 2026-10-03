## 2026-10-03 — OWNER-GATE-CUTOFF-01: the near-limit optimism gate's cutoff is 2.0 bands

**Authority.** The owner, 2026-10-03, reported that the SciML/technical lead
deferred the cutoff to the lead session, and approved that ("Harsh deferred
that decision to you and I approve that"). The owner then approved applying
it in code ("permission granted", "try again").

1. **Value.** `carbon/battery/value/admissibility.py`
   `THRESHOLD_BANDS = 2.0`. A model whose mean near-limit optimism is at or
   above 2.0 bands is inadmissible and scores 0 under every rule.
2. **Why 2.0.**
   - It is a round, interpretable value: the model overstates its margins
     near the limits by twice the contract's own uncertainty band, on average.
   - It is not fitted to the boundary optimist's 2.41, and it still fails
     that control.
   - On EV4 it fails 20 of 99 real members, whose mean verification decision
     loss is 1.68 against 0.51 for the rest. On EV2 it fails 2 of 14 (1.38
     against 0.34).
3. **Scope.** A provisional DEVELOPMENT value for value-study results only,
   confirmed once in EV5 (H2). Putting the gate into the testnet rule is a
   separate approval. No historical result is rescored.
4. **Known limit.** The gate does not catch the localized sign-error control
   (mean optimism 0.46, below every real member). That needs its own
   measurement, which is a science decision; recorded, not suppressed
   (OWNER-CHALLENGE-ADMISSION-01 §6.2).
5. **Supersedes** OWNER-EV5-CAP-01 item 3's "the value stays None": the
   cutoff is now applied.
