# Measured offline Launchpad construction coverage (PLT-29)

This replaces the handoff survey's predictions for the bounded offline probes
below. [MEASURED.json](MEASURED.json) records the actual 55 observations, their
commands, 11 declared public strategy fixtures, source commit and file hashes.
The source snapshot is `31c6fc76a6f2555183d9f9d7915a1f641ea14415`, based on main
`679b37a05b3120e627a92c4db4d7811ada43ce5d`. No training, reference solve, model,
provider, signer, submit or live-host trial ran. All execution callbacks refuse,
and every local toolbox call records zero execution allowance consumed.

There are two measured routes: the actual
`python -m carbon.reconstruction.development_composition` CLI with its cost
check enabled, and the current local battery research service's four toolbox
operations. The audit does not substitute the composed compiler into that
service. It does not exercise Launchpad's live page/MCP transport or a served
development-level binding; those are host-side acceptance.

| Case | Declared change | Construction CLI | Local dry_validate | Local compile_strategy | Local inspect / forecast |
|---|---|---|---|---|---|
| C0 | Base Muon MLP recipe | ACCEPTED, exit 0 | ACCEPTED | ACCEPTED | RETURNED static / unresolved |
| C1 | Registered robust-L2 expression | ACCEPTED, exit 0 | REFUSED `parameter.not_rebuildable` | REFUSED `strategy.parameter_shape_invalid` | ERROR |
| C2a | SpecMuon spectral option | ACCEPTED, exit 0 | REFUSED `parameter.unknown` | REFUSED `parameter.unknown` | ERROR |
| C2b | Registered public pool selection | ACCEPTED, exit 0 | REFUSED `parameter.unknown` | REFUSED `strategy.parameter_shape_invalid` | ERROR |
| C3a | BFGS routine | ACCEPTED, exit 0 | REFUSED `parameter.unknown` | REFUSED `parameter.unknown` | ERROR |
| C3b | BFGS plus backtracking search | ACCEPTED, exit 0 | REFUSED `parameter.unknown` | REFUSED `parameter.unknown` | ERROR |
| C4 | Unverified placeholder graph digest | ACCEPTED metadata, exit 0 | REFUSED `parameter.not_rebuildable` | REFUSED `parameter.unknown` | ERROR |
| X1_pool | SpecMuon plus pool (same level) | ACCEPTED, exit 0 | REFUSED `parameter.unknown` | REFUSED `strategy.parameter_shape_invalid` | ERROR |
| X1_search | BFGS plus backtracking (same level) | ACCEPTED, exit 0 | REFUSED `parameter.unknown` | REFUSED `parameter.unknown` | ERROR |
| X2 | Loss expression plus SpecMuon (across levels) | ACCEPTED, exit 0 | REFUSED development fields | REFUSED `strategy.parameter_shape_invalid` | ERROR |
| X3 | Loss, spectral, pool, routine, search and placeholder graph | REFUSED `construction_rebuild_unavailable`, exit 2 | REFUSED development fields | REFUSED `strategy.parameter_shape_invalid` | ERROR |

**The survey's blanket X1/X2 compiler failure prediction is stale.** S1 compiles
the measured same-level and cross-level combinations. The current local base
toolbox still refuses them; prepared construction capability has not made that
route a composed service. The survey's prior C0-C3 live results used their lane
bindings, so these base-service refusals are not evidence that those historical
runs failed. Serving and wiring remain distinct from compiler capability.

**C4's accepted placeholder is not a verified graph or successful rebuild.**
It shows metadata routing only. No envelope, G0-G7 gate, isolated compilation
or training was exercised. X3 names its missing composed graph rebuild before
those stages. Both graph cases are explicitly scoped
`UNVERIFIED_GRAPH_METADATA_ONLY`; valid C4/X3 acceptance remains unrun here.
The separate S2 PR #1329 is not substituted into this main-based snapshot.

The C0 forecast's `[0, 0]` seconds is explicitly
`ZERO_BAND_IS_UNRESOLVED_PLACEHOLDER`, `NO_RESOURCE_PREDICTION` and
`SUPPORT:UNRESOLVED`. Its successful protocol reply is not zero runtime,
budget admission, a quote or observed resource evidence. Resource failures for
other strategies remain errors; no rejected strategy receives a runtime claim.

Each individual observation has an executable command, for example:

```bash
CARBON_UV_GROUPS='science-jax mcp archive' ./scripts/dev/canonical.sh python -m scripts.dev.launchpad_offline_coverage --case X2 --operation construction
CARBON_UV_GROUPS='science-jax mcp archive' ./scripts/dev/canonical.sh python -m scripts.dev.launchpad_offline_coverage --case C1 --operation compile_strategy
CARBON_UV_GROUPS='science-jax mcp archive' ./scripts/dev/canonical.sh python -m scripts.dev.launchpad_offline_coverage
```

The first command materializes the declared strategy and invokes the actual
construction CLI as a child process, retaining its exit code and typed answer.
The last command reproduces all 55 measurements. No `--no-budget` override is
used. These are representative recipes, not exhaustive vocabulary coverage or
proof that every possible combination trains correctly.

The full 10-change by 25-capability matrix is retained in the measured artifact:
B11 has the local probes above; its real-door acceptance stays unproven. All
other **240 cells are `ran: false`, `HOST_BOUND`**, rather than FAIL. They require
the actual Launchpad/host path and were not dispatched by this audit. The graph
subscope within B11 remains metadata-only as described above.

For **B18**, source inspection confirms that intake public facts report
`door.served_contracts()`, and a level-bound compile requires the target's
exact served digest before spawning. The local service's default is the base
compiler. This cannot confirm what testnet-sched currently serves: the handoff's
"L0 only" statement remains an attributed deployment observation requiring a
fresh host check. Launchpad should read the configured target's
`/carbon/v1/battery/intake` public facts and record `served_contracts` at the
actual deployed revision. No key or submit is needed for that facts read, but
this audit performs no target request. Compiler capability already exists for
the measured L0-L3 cases; a missing serving/wiring path is a deployment or
integration gap, not evidence that S1 cannot compile those combinations.

Maturity is DEVELOPMENT static engineering evidence only. Live page/MCP,
practice/smoke, GPU, signer, chain, submit, outcome and external-path acceptance,
scientific/security qualification and deployment remain with their owners.
