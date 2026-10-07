## 2026-10-07 — OWNER-LEVEL4-GRAPH-ONLY-01: Level 4 admission is graph-only

**Authority.** The owner, 2026-10-07: "approve D1". The Test Lead session
relayed it, answering decision D1 of
`docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md` (§11): "Adopt
'graph-only' as the meaning of Level 4 admission, and the roadmap wording in
§7". Recorded by the Level 4 engineer session.

1. **Graph-only Level 4.** At Level 4 Carbon accepts only a pure math graph.
   Every operation must be on the Challenge's allowlist, and the graph must fit
   the budget. No miner code runs at training, inference or grading. Carbon
   initializes, trains and grades the graph itself.
2. **Roadmap wording.** `Design_Specs/Challenge_Roadmap.md` takes the
   proposal's §7 wording as revision 2.3, in two places: "Construction and
   solver access", and Track A admission item 1.
3. **Phase 1 is go.** It is development-only, with nothing miner-facing. The
   Test Lead's direction sets the order:
   - the Q1 named-function fix;
   - gates G0–G7 as Challenge-neutral code;
   - the equivalence suite;
   - the known-bad specimens.

   The plan is `docs/development/graphite/level4/PHASE1_PLAN.md`.

**Not decided here.** D2–D6 stay the Test Lead's recommendations until the
owner rules:
- D2: Level 4 v1 on B′, Carbon's own graph format;
- D3: security-owner acceptance, narrowed under B′ to G5 compile isolation and
  Carbon's own parser;
- D4: pretrained assets, priors and hybrids;
- D5: solver as an operation;
- D6: per-Challenge caps. Every cap stays `HUMAN_INPUT`.

**Unchanged.**
- No live contract changes. Level 4 opens to miners only through a locked,
  released contract the owners choose (OWNER-GRAPHITE-TEST-WAVE-03). The
  miner-facing registry exclusions (`loss_expressions`, `composition_graphs`
  under `EXECUTABLE_SUBMISSION`) stay. Only a development-only Level 4 variant
  may admit allowlisted graphs.
- The Level 3 rule: no participant code until the security owner accepts
  isolation.
- No result here earns SPECIFIED, IMPLEMENTED, TESTED or SECURITY_QUALIFIED
  for Level 4 on any Challenge.
