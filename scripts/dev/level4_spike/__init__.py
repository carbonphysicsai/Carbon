"""Level 4 Phase 0 spike: graph-only construction (development only).

LEVEL4-PHASE0 spike for `docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md`
§10 Phase 0 and Appendix B (B'). CPU only. No pods, no hidden data, no miner
code, no chain, nothing in `CONTRACTS`, no miner-facing surface.

Shared, Challenge-neutral modules:

* `graph`: the Carbon graph format v0 (strict JSON) and its measurements;
* `allowlist`: allowlist v0, loaded from
  `docs/development/graphite/level4/allowlist_v0.json`;
* `params`: per-parameter codecs the allowlist names;
* `lower_jax`: jaxpr -> Carbon graph;
* `lower_torch`: `torch.export` Core ATen -> Carbon graph;
* `interpret`: Carbon graph -> a JAX function Carbon differentiates itself;
* `probes`: primitive inventories, D6 measurements, serialization probes.

A Challenge supplies only an adapter (`adapters/<challenge>.py`). A Challenge
literal in a shared module is a defect (tested).

No cap or limit is chosen anywhere here: every value the proposal reserves
(§6.2, §6.3, D6) stays `HUMAN_INPUT`.
"""
