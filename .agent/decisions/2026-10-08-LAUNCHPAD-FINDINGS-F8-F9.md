## 2026-10-08 — LAUNCHPAD-FINDINGS-F8-F9: serve Graphite its public practice results, and say the input window before a Graphite launch spends

**Authority.** The Launchpad smoke run of 2026-10-08 on `carbon-fresh`
(campaign `14d573bb4c425ecf12c185dd223f7ece`) found LA-F8 and LA-F9
(`docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md`).
The choices below are engineering choices delegated to the Launchpad
acceptance work. No scientific value, threshold, gate, tolerance, price,
budget or model capacity changes. No default changes, no closed code is
renamed, and every interface change is an addition.

**Decisions.**

1. **LA-F9: the public practice paths are exempt from the checkout deny rule,
   exactly and only.**
   - All five withheld results matched one rule: the checkout deny prefix
     `docs/development/evidence/`, on the public PRACTICE set's own path at
     `safety.material.path`. No Graphite marker matched. The file is
     committed in the public repository and is practice, not the exam.
   - `graphite.protected_material.PUBLIC_PRACTICE_PATHS` names the battery,
     motor and cold-plate practice paths, written out so the leaf module
     imports no Challenge. A test holds each to its Challenge's constant.
   - The exemption applies only when a whole string equals one of those
     paths, case and all. It lifts only the checkout deny rule: every
     Graphite marker still applies to the same string, and every other path,
     prefix and fragment is still refused. Requests, results, literature
     cards and `marker_classes` share the one check, so the internal and
     miner editions cannot diverge.
   - Not done here: a result refusal still says `dispatched: false`,
     although the call ran. The attack analysis reads that field as
     Graphite's own refusal, so it needs its own change and review.
   - Review: this narrows a disclosure filter, so it needs security review
     before merge.

2. **LA-F8: one context record, and an advisory before launch; the default
   window is left to the owner.**
   - The cause is Carbon's default `max_input_tokens` (65,536) under the
     sound one-token-per-byte admission bound. The model's published window
     is not the cause: Engy lists 1,048,576 tokens. This is GRAPHITE-D34's
     defect in the miner edition, which runs on the miner's own selection.
   - `model_provider.ENGY_CONTEXT_TOKENS`, `ENGY_CONTEXT_OBSERVED`,
     `PUBLISHED_CONTEXT_TOKENS` and `published_context()` now hold the
     published context. `graphite.roles` re-exports the table with D34's
     values unchanged. `INPUT_TOKEN_BOUNDS` names `select`'s existing input
     bounds.
   - The capability document's model block gains `input_window`, and the
     launch options' `graphite` block gains `input_window`. Each carries the
     closed advisory code `graphite_input_window_too_small` and its next
     step from the refusal catalog. The catalog also gains `context_ceiling`.
   - **Not decided here (owner):** whether a Graphite launch gets a larger
     window by default. The options and their costs are in LA-F8. Raising
     the default changes what each call reserves from the miner's own
     ceilings, and it changes when a FULL launch is refused, so it is a
     product decision, not an engineering one. A launch refusal would need a
     floor nobody has set, and a compaction rule v2 would change a frozen
     rule. Until the owner decides, the advisory and the miner's own
     `model_settings.max_input_tokens` are the path.

**Tests.** `tests/cpu/test_launchpad_findings_f8_f9.py`. Also re-run: the
Graphite miner mutation, boundary, import-order and GPU-probe tests, the
attack analysis and verification tests, the Launchpad page usability,
supervisor, model selection and Control Center Graphite tests.
