# PRACTICE-DECISION-SIGNAL-01: public practice decision prototype

**Status:** DEVELOPMENT working contract. **Authority:** owner direction,
2026-10-09. **Maturity ceiling:** specified and tested prototype; no miner
display, exam score, gate, or qualification change.

## Scope

1. Reuse the pinned `practice-decision-set-v2` (six public conditions, 35
   protocols each), its committed reference records, and the existing EV4
   selection, reference-band, tie, abstention, and Q3 aggregate definitions.
   This is a public-practice analogue of regret and false-feasible rate, not
   the hidden exam's Q3 leg or G-FEAS verdict.
2. Provide a read-only CPU prototype for Graphite run 5's first-seed panel:
   the published default MLP plus the distinct scored recipes. Rebuild from
   their registered battery implementation 1.0 and committed public TRAIN
   material; infer only on the pinned public practice
   decision inputs. Use the already committed run-5 practice accuracy and EV4
   development decision-value aggregates only for offline rank comparison.
   Never call a reference solver or load a hidden, tuning, confirmation, or
   operator-held panel. Aliased recipes are counted once.
3. Report matched-panel Kendall tau-b and Spearman rho of accuracy and public
   decision loss against committed development value, with the exact member
   and resolved-scenario counts. A missing prediction/reference yields an
   explicit unmeasured result, never a zero loss or pass. The result is a
   small retrospective diagnostic, not adoption evidence.
4. Write the proposed miner-visible aggregate projection and its withheld
   fields in a spec. Do not edit Launchpad or practice feedback runtime in
   this ticket. Owner decides whether the signal is shown. PRACTICE-QUIZ-01
   remains the broader implementation contract; this ticket supplies a
   bounded public prototype and does not supersede its Test Lead rulings.

## Decisions and boundaries

- KEEP `carbon.battery.practice_safety.load_decision_set` and
  `carbon.battery.value.decision`; WRAP the already registered Q3 aggregate
  semantics for this development tool. The EV4 provisional mistake costs are
  copied into a practice-only rule and test-bound to the public EV4 contract;
  the runtime tool never reads that contract's EV conditions.
- Report the public set's six-condition coverage: all-infeasible conditions
  are excluded by the Q3 rule; an unresolved reference never becomes a
  candidate failure. Q3's registered band-pessimistic diagnostic treatment of
  a selected unresolved candidate remains visible through its unresolved
  count. No gate cutoff or pass/fail is attached.
- Input material is public TRAIN v1 and public practice-decision-set v2 only.
  The offline comparison reads published run-5 aggregate scores and EV4
  development value, never case-level EV4 predictions or references. Its
  final report contains only aggregate model outcomes and recipe labels.
- **Primary map_ref:** `SYSTEM/AGENT-EXECUTION`. Hub impact is mapped detail
  only. The current delivery policy retires Hub maintenance; the prototype
  does not change the map's purpose, placement, authority, dependencies,
  maturity, or primary links.

## Acceptance

- Toy tests for fixed selection, feasibility/regret, unresolved and missing
  cases, allow-listed final report, and first-seed/alias matching.
- Public-only run-5 result if the local CPU model runtime can rebuild every
  member. Otherwise name the missing input or environment and leave the
  numerical claim unmeasured.
- Canonical CI through `scripts/dev/canonical.sh` or the PR's exact-head CI.
  One PR to PR Lead. No spend, solver run, hidden/AX42 material, or LIVE change.
