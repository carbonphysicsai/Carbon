"""Level 4 graph-only construction (development only).

OWNER-LEVEL4-GRAPH-ONLY-01: at Level 4 Carbon accepts only the math graph a
submission produces, refused unless every operation is on the allowlist and
the graph fits the budget; no miner code runs at training, inference or
grading. Plan: `docs/development/graphite/level4/PHASE1_PLAN.md`.

Carbon side (runs on Carbon hosts):

* `graph`: the Carbon graph format (strict JSON) and its measurements;
* `params`: the parameter kinds the allowlist names;
* `allowlist`: the versioned allowlist (`allowlist_v1.json`, digest-bound);
* `named`: custom derivative kernels rebuilt with Carbon's own rules;
* `validate`: gate G4, graph validation against the allowlist, the caps and
  the Challenge's interface;
* `interpret`: rebuild a validated graph as a JAX function;
* `initializers`: Carbon-built initialization from a declared spec;
* `specimens`: known-bad programs and documents and the gate each must hit.

Miner side (Launchpad tooling; never run on Carbon hosts for a submission):
`tooling` lowers JAX (`tooling.lower_jax`) and PyTorch (`tooling.lower_torch`)
programs into the format.

Challenge-neutral: a Challenge supplies an adapter (`carbon/<challenge>/
level4.py`). Nothing here is miner-facing, nothing is in `CONTRACTS`, and every
cap is `HUMAN_INPUT` until an owner sets it.
"""
