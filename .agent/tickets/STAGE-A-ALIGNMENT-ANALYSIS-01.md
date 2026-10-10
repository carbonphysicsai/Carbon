# STAGE-A-ALIGNMENT-ANALYSIS-01: prospective Graphite score/value analysis

**Status:** DEVELOPMENT working contract. **Authority:** owner direction,
2026-10-09; SCORE-VALUE-ALIGNMENT-01, V3-SCORE-INPUTS-01, and the registered
battery v2/v3 rules. **Maturity ceiling:** tested analysis tooling, not a
score-rule change or scientific qualification.

## Contract and decisions

1. Analyze a closed, digest-bound `carbon.battery.stage-a-alignment-input.v1`
   summary. It contains only opaque member/recipe labels, seed, confirmed
   development practice and v2 exam aggregate scores, decision loss on one
   registered development panel, and references to V3-SCORE-INPUTS-01 reports.
   The analyzer never opens an operator record, prediction, case, hidden bank,
   or solver output. Unknown fields and invalid identities are refused.
2. A comparison cohort has one Challenge, level, v2 rule digest, pool version,
   rebuild device class, decision measure/panel, and v3 panel identity. Scores
   from distinct cohorts are never pooled. A nonterminal, unresolved, missing,
   or reference/infra-failed member makes the affected planned comparison
   unmeasured; it is listed with cause rather than silently dropped. If all
   v2 scores and values exist but v3 reports do not, report the complete v2
   cohort and practice/exam relationship as `V2_ONLY`, with v3 unmeasured.
3. V2 and v3 Kendall tau-b/Spearman rho use the same planned member list and
   decision loss (lower is better). The v3 ordering is reproduced with the
   registered `G-FEAS/A-Q@0.05` candidate and its gate, with the leg identity
   checked against the V3-SCORE-INPUTS-01 report. The historical v2 exam score
   is read as recorded; no old score is rewritten.
4. Recipe-cluster bootstrap resamples recipes, retaining every recorded seed.
   It is descriptive. Report defined draws and unavailable bands honestly.
   Practice versus exam is shown per recipe, with score directions made explicit;
   a rank association is reported only inside a comparable cohort.
5. Per-term log contributions (`0.5 log a`, `0.5 log q`) and the G-FEAS gate
   are reported separately. Divergence is pairwise ranking disagreement with
   decision loss. Contributions describe the observed ordering; they are not
   causal attributions or a scoring-rule recommendation.

**Implementation:** a read-only analyzer, synthetic stage-A-shaped fixtures,
and a one-page owner summary template. No spend, solver runs, hidden material,
AX42, LIVE change, or owner-reserved threshold decision. One PR to PR Lead.

**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`. Hub impact: mapped detail;
the retired Hub's orientation purpose, placement, status, dependencies,
boundaries, maturity and primary links remain accurate, so no generated Hub
update is needed under current `.agent/DELIVERY_PROTOCOL.md`.
