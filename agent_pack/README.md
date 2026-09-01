# Carbon agent pack

Executor-agnostic entry points for Carbon ticket delivery. Live authority and
tickets live at repository root under `.agent/`; historical completion detail
lives in the ticket evidence records and external receipts, not this README.

```text
current authority and selected ticket
→ working contract and durable decisions
→ coherent vertical implementation/test slices
→ canonical validation
→ exact-head Merge gate and Greptile
→ normal reviewed-tree-preserving merge
→ exact-main verification and bounded closeout
→ next ready ticket
```

## Entry points

| Path | Role |
|---|---|
| `CONSTITUTION.md` | Repository-wide authority boundaries |
| `AGENTS.md` | Default agent/human engineering behavior |
| `.agent/WAVE.md` | Active wave and selected-ticket authority |
| `.agent/WAVE_B.md` | Current Wave B board, dependencies, and maturity |
| `.agent/DELIVERY_PROTOCOL.md` | One-PR lifecycle, exact merge predicate, and evidence classes |
| `.agent/DELEGATED_DECISION_PROTOCOL.md` | Engineering decision and human-reserved routing |
| `.agent/INVARIANTS.md` | Always-on invariants |
| `agent_pack/EXECUTION_PROTOCOL.md` | Full ticket execution loop |
| `agent_pack/CODEX_TICKET_LAUNCHER.md` | Short Codex launcher |
| `agent_pack/PLANS.md` | Complex-ticket plan template |
| `docs/development/ENVIRONMENT.md` | Canonical environment guidance |
| `docs/development/carbon_hub/` | Derived orientation/navigation only |

Do not use `agent_pack/.agent/`; that path is retired.

## Current Wave B position

The B-04 bounded engineering contract is ratified; B-04 runtime remains
unimplemented and unqualified. Owner decision `OWNER-DX-01` inserts B-01F,
Development Throughput Hardening, before runtime and queues B-01G as future
non-blocking `todo`.

The B-01F candidate prepares a conditional transition: B-01F becomes `done`
and B-04 runtime becomes selected only after the exact final B-01F head/tree
passes scope-required exact-head checks and `Merge gate`, exact-head Greptile
with every valid finding repaired and zero unresolved threads, normal exact-
expected-head merge with reviewed-tree preservation, and exact-main
`Merge gate`. Before that predicate, B-04 runtime stays paused.

This sequencing changes development delivery only. It does not amend the B-04
contract or grant scientific truth, security acceptance, rights, economics,
qualification, `LIVE`, launch, deployment, or production authority.

## Delivery rules

- Use a dedicated branch/worktree and one pull request per ticket by default.
- Put the working contract, decisions, plan, and start state first; add
  coherent vertical implementation/test slices; review the final tree
  together.
- Use a separate contract PR only for a contract-only ticket, a real concurrent
  downstream immutable-contract need, an established cross-domain public-
  interface freeze, or another concrete current sequencing reason. Ticket size
  alone is not one.
- On macOS, Windows, or noncanonical Linux, run commands through
  `./scripts/dev/canonical.sh`. Native-host output is not canonical.
- Greptile is the routine correctness review Carbon waits for. Human/domain
  review remains asynchronous unless a decision or acceptance is explicitly
  human-reserved; human silence is not a gate.
- Require exact-head scope checks and `Merge gate`, exact-head Greptile, valid-
  finding repair, zero unresolved threads, and no applicable block.
- Unless owner direction explicitly says to stop before merge, normally merge
  the unchanged clean candidate with an exact expected-head guard, verify
  ordered parents/reviewed-tree/exact-main `Merge gate`, close the bounded
  ticket, and continue to the next ready ticket without another prompt solely
  for merge.
- Use normal merge commits only. Do not squash, rebase-merge, enable auto-
  merge, or grant routine bypasses.
- Track stable scope/authority/base/decisions/contracts/manifest/commands/
  invariants/maturity/predicate. Put final head/check/review/merge/exact-main
  identities in the external completion receipt.
- Never create an empty or evidence-only commit to retrigger PR validation or
  store external completion facts.
- Notify issue #42 for material lead-lane decisions; route an explicit
  `DEFER_TO_OWNER` package to issue #41. Neither routing nor silence substitutes
  for a reserved human decision.

## Optional executors

Harness-specific configuration lives under `agent_pack/executors/` only. It is
optional tooling and cannot override repository authority.
