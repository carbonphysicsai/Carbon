# Battery Level 4 capabilities: draft proposal

**Author:** the Level 4 engineer, 2026-10-08, on the Test Lead's ruling for PR 8
**Status:** PROPOSED. A draft for the owner's acceptance, which the Test Lead
brings to them. Nothing here opens to miners.
**Authority:** OWNER-LEVEL4-GRAPH-ONLY-01 (D1). D2–D6 remain open, and every
cap stays `HUMAN_INPUT`.

## Why this is a draft and not `level-4.json`

`carbon/challenge_pipeline/proposals/<challenge>/level-<n>.json` accepts only
a proposal whose `proposed_by.agent` is `graphite` (`proposals.validate`,
OWNER-CHALLENGE-ROADMAP-03: "Graphite proposes every level's capabilities").
The Test Lead ruled that for Level 4 this engineer drafts the capability,
because the capability is the surface itself. That ruling is not an
amendment to the owner's decision, so writing this draft under Graphite's
name would misstate who wrote it.

The capability objects below use the proposal schema's own keys (`id`,
`adds`, `bounds`, `rationale`, `sources`, `reconstruction`,
`attack_surface`), so `level-4.json` can take them verbatim. Two ways to
file them:
- a Graphite planner session transcribes the draft, naming this file as its
  source;
- the owner amends OWNER-CHALLENGE-ROADMAP-03 to let the Level 4 engineer
  propose Level 4.

The construction contract owner accepts either way.

The development-only variant (`battery-l4-graph-v1`, LEVEL4-DEV-VARIANT-01)
already widens the drafted surface for internal use. OWNER-GRAPHITE-DEV-LEVELS-01
F1 allows that for a surface Carbon drafts and the Test Lead reviews.

## The surface, at maximum freedom

The Test Lead's ruling sets the stance: the whole allowlist, with nothing
pre-trimmed. The attack finds the limits, and protection follows.

```json
[
 {
  "id": "hybrid.composition_graphs",
  "adds": "A new model architecture as a graph: the math graph a miner's JAX or PyTorch model lowers to (carbon.level4 format, schema carbon.development.level4-graph.v0), with an init graph or an init spec. Any composition of the allowlist's operations: the whole of allowlist v1, with nothing pre-trimmed (72 allowed and 8 review ops, 9 allowed and 5 review named functions, and 44 allowed and 2 review PyTorch Core ATen ops).",
  "bounds": "Graph-only admission through gates G0-G7 (carbon.level4): G0 intake with HUMAN_INPUT size bounds; G3 strict parse in an isolated process; G4 allowlist v1 (version level4-allowlist-v1, digest sha256:3b2371ffb02275a1dc2dbbe8e8a97eb180b9c673c9149cc38d05ae99557971f7), with roles, parameter kinds, named functions, init data flow, interface and batch; G5 compile in isolation, fail-closed until the security owner accepts it (D3); G6 Carbon trains it with Carbon's key, battery's own loop and optimizer menu, TRAIN v1 only, steps within the TRAINING-BUDGET-01 compute budget; G7 grading through battery's exam, unchanged. Caps on constant bytes (counted after pruning), nodes, call depth, document bytes and largest intermediate are HUMAN_INPUT on battery's sheet (D6). No pretrained weights: the constant cap enforces that (D4). The interface in development is battery's Level 0 network boundary (features in, normalized outputs out).",
  "rationale": "Levels 0-3 vary only the families Carbon ships. Published progress is structural: new layers, new encoders and new couplings of physics and learning (proposal section 1: CANTO, NOIR). Graph-only admission widens the architecture freely while no miner code runs at training, inference or grading (D1).",
  "sources": [
   "docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md",
   "docs/development/graphite/level4/PHASE0_SPIKE_REPORT.md",
   "docs/development/graphite/level4/PHASE1_PLAN.md",
   "docs/development/graphite/level4/phase1_e1_results.json"
  ],
  "reconstruction": "carbon.level4 (G0-G7) with the battery adapter carbon.battery.level4. Battery's Level 0 MLPs and DeepONet, lowered to graphs and run through verify, G4 and G6, reproduce the declarative path's parameters and predictions bit for bit on CPU, and G7 gives the declarative path's exact exam verdict. Until D3, every rebuild of a submitted graph fails closed as Carbon's environment (battery.level4_worker).",
  "attack_surface": "The proposal's section 8 suite, with one specimen per row (carbon.level4.specimens.attack_suite): callbacks and escapes, unbounded loops, keyed RNG outside init, constant smuggling and splitting, compile bombs, initializer abuse, interface abuse, forged custom derivative rules and tampered documents. Open: procedural tables, which no graph check can block (D4, Track B); compute under-counting (Phase 4 R6/R7); compiler exploits (G5, D3); and GPU nondeterminism of review ops (the A40 R1 leg)."
 },
 {
  "id": "objective.loss_graphs",
  "adds": "A miner loss as a graph (role loss) over the model's outputs and TRAIN targets, admitted where battery's Level 1 permits a loss, through the same gates as the forward graph.",
  "bounds": "Allowlist v1 in the loss role. No RNG. Named functions allowed. The same HUMAN_INPUT caps apply. G6 does not consume a loss graph yet: it trains with battery's loss until the Phase 1 follow-up wires one in.",
  "rationale": "The proposal (section 3.4) gives the miner the architecture and, where Level 1 permits, the loss. NOIR's independence penalty is a loss term that only helps on top of a new layer.",
  "sources": [
   "docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md",
   "carbon/battery/loss_terms.py"
  ],
  "reconstruction": "carbon.level4.validate in the loss role. Battery's Level 1 loss terms already lower and rebuild bit for bit (Phase 0 and Q1 records). Training with a loss graph in G6 is still to build.",
  "attack_surface": "Score gaming through the training objective is owned by the exam. A loss graph can't reach grading, because G7 uses battery's exam, unchanged."
 }
]
```

## Left out, with reasons

- Custom derivative rules that aren't registered kernels (`custom_jvp_call`,
  `custom_vjp_call`). They are refused because a graph cannot carry a Python
  rule. Registered kernels keep Carbon's rule (Q1).
- Unbounded loops (`while`), host callbacks, foreign calls and collectives
  are refused (allowlist v1).
- Named functions whose rules close over constants (`dawsn`, `erfcx`,
  `fresnel`, `owens_t`), and `frexp`, are refused in v1.
- Carbon's solver as a graph operation is left to D5, as a later rung.
- Level 5, custom inference that isn't pure math, stays behind the security
  owner's full sequence.
