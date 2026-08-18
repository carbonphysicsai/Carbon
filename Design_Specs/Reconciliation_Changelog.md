# Design Specs Reconciliation Changelog

**Trigger:** Post-ratification note — *Documents that should be changed after ratification* (§31).

**Mode:** Focused reconciliation — not a full rewrite. Design specs remain authoritative; this pass aligns semantics.

## Summary of changes

| Document | Changes applied |
|----------|-----------------|
| **Scoring.md** | Declared sole mathematical authority. Hard gates → **binary**. Soft aggregate → **weighted geometric mean**. P0 baseline weights **45/30/25**. τ pack-bound & dossier-calibrated. Removed sigmoid-as-hard-gate as normative. |
| **SPEC.md** | Kept architectural. Pointed scoring to Scoring.md semantics. P0 launch slice vs Phase-0 expansion. Shared exam identity. Public physics vs hidden realizations. Stronger Port B invariant. |
| **Trustless_Verification.md** | Path A retained. Future beacon rule, official exam identity, validator IDs excluded, hybrid beacon direction, envelope closure for score-bearing draws. “Trusted validator realm” → validator-controlled, adversarially constrained, independently reproducible. |
| **Data_Management.md** | Aligned with Trustless addenda (exam identity, envelope, beacon). |
| **Miner_MCP.md** | Two-loop + feedback budget kept. `corr ≪ 1` → **non-oracle requirement**. Mock incompleteness = computational/evaluative, **not false physics**. |
| **Generator_Validation.md** | Example numerical criteria not globally normative; conditional on physics/evidence type. Reference caches = dossier evidence ≠ live exam. |
| **Evidence_and_Envelope_Standards.md** | Score-bearing stress inside declared envelope. Evidence ranks = provenance descriptors, not vote weights. |
| **Launch_Bar.md** | Port B: same mandatory lean pack for every scored nonzero submission; progressive depth ≠ variable grading. |
| **Specialist_Bank.md** | Winning strategy may be candidate; ban direct product promotion without fresh independent qualification. Product Battery retained. |
| **Build_Out.md** | Remains sequencing authority; must follow higher-level semantic docs; no alternate formulas. |

## Explicit non-goals of this pass

- Did not invent new challenge packs or τ values.
- Did not rewrite Build_Out wave tickets line-by-line.
- Did not change commercial GTM narrative beyond Specialist_Bank candidate rule.
- Did not push to GitHub (local reconciled copies only until review).

## Authority after reconciliation (domain-specific, not a global hierarchy)

Authority is **domain-owned**. No single doc outranks all others on every question:

| Domain | Authoritative doc(s) |
|--------|----------------------|
| Architecture / system boundaries | `SPEC.md` |
| Scoring mathematics (gates, aggregate, weights) | `Design_Specs/Scoring.md` |
| Seeds, exam identity, beacons | `Trustless_Verification.md` + `Data_Management.md` |
| Miner/agent surface (MCP, free loop) | `Design_Specs/Miner_MCP.md` |
| Launch stop-ships / Port B floor | `Design_Specs/Launch_Bar.md` |
| Generator credibility / dossiers | `Generator_Validation.md` + Evidence standards |
| Specialist productization | `Design_Specs/Specialist_Bank.md` |
| Build sequencing only | `Design_Specs/Build_Out.md` |

Conflicts inside a domain: fix the domain doc. Cross-domain conflicts: reconcile explicitly; do not invent a numbered precedence ladder that re-creates SPEC-vs-everything fights.

## Next steps

1. Human review of weighted geometric + 45/30/25 vs any challenge-specific packs already drafted.
2. Replace repo `Design_Specs/*` with these files after approval.
3. Update agent tickets only if they still mention sigmoid hard gates or corr ≪ 1.


## Review status

External review: **APPROVE WITH REQUIRED CLEANUP** (residual contradiction pass applied in-place on this bundle).
