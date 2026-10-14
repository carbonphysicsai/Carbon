# OPT-14 — Level 2 attack shape and recorded-finding reader

**Status:** working contract; DEVELOPMENT repair only. **Authority:** optimizer queue OPT-14, GRAPHITE-01 phase 4, `docs/development/graphite/PHASE4_ATTACKER.md`. **Base:** main `f664977d91cd0b6149dd7db5e3f01cb14eae2448`. **Reviewer:** Graphite Testing Manager.

## Problem and bounded decision

Battery Level 2's accepted-result predicates currently call an ordinary accepted compile a BREACHED attack, even where the construction lacks that family's attack shape. The pool family must require an actually pool-rule-violating selection; the off-family, cross-level and slot-ablation families also need their own shape guards. Determinism already judges a difference, not mere acceptance. Keep the variant and miner-contract gates unchanged. For session attempts with no family attack shape, return a typed NOT_RUN/NOT_APPLICABLE oracle reading; for shaped attempts, judge the real gate and the unchecked specimen as before. The same shape predicate binds baseline family results so a future wrongly listed honest input cannot be called a breach. Version the affected Level 2 adapter, leaving historical v1 findings uninterpreted.

The OPT-13 re-mint reader handles `carbon.attack.finding.v1` session verdict evidence but conflates older named baseline/control evidence without a `verdict` with malformed verdicts. Distinguish a named non-session finding from a redacted verdict and from malformed evidence. Validate the schema, condition and digest for all formats, exclude a named non-session finding from session-verdict lookup, and preserve the strict refusal for an unknown or inconsistent body. Re-mint must still refuse missing or changed session provenance; it must never claim a specimen was redacted merely because a different finding lacks a verdict.

## Scope, tests and boundaries

Target `battery_level2.py`, the shared declarative adapter only for optional shape handling, `phase4_remint.py`, focused tests, and operator docs. Test an honest PyTorch+Muon MLP without `pool_selection`, a truly pool-violating selection accepted by a toy weakened gate, each other acceptance-based L2 family, and a toy multi-finding session with a named older finding before the matching session verdict. Preserve all three malformed-evidence checks: schema, condition and verdict conditions. No gate relaxation, no live attempt or re-mint, no hidden material, no spend, no breach re-triage.

**Invariants:** no false security finding from a valid construction; no hidden-material disclosure; typed infra/provenance failures; immutable historical evidence; fixture evidence grants no security qualification. **Hub map_ref:** `WAVE-C/GRAPHITE-01`; no Hub edit because the Hub is retired by current delivery authority and the purpose/placement/status do not change.

**Completion predicate:** focused regressions and canonical exact-head CI/Merge gate pass, one PR to main receives exact-head Ready handoff, and Graphite Testing Manager owns interpretation of the original finding and any executor rerun. No LIVE or qualification claim.
