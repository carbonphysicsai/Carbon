# Carbon contributor and agent tools

This folder contains executor-independent entry points for repository work. Start with [AGENTS.md](../AGENTS.md), the relevant ticket, and the current [delivery protocol](../.agent/DELIVERY_PROTOCOL.md). For a project overview, read the [root README](../README.md); for implementation evidence, read [Project status](../docs/publications/PROJECT_STATUS.md).

## Entry points

| Document | Role |
|---|---|
| [Constitution](../CONSTITUTION.md) | Scientific, business, and implementation responsibilities |
| [Wave status](../.agent/WAVE.md) | Controlling engineering board and links to track records |
| [Wave C](../.agent/WAVE_C.md) | Current wave register |
| [Delivery protocol](../.agent/DELIVERY_PROTOCOL.md) | Implementation, checks, and merge requirements |
| [Decision protocol](../.agent/DELEGATED_DECISION_PROTOCOL.md) | Delegated engineering and human-reserved decisions |
| [Invariants](../.agent/INVARIANTS.md) | Scientific and security constraints |
| [Ticket launcher](CODEX_TICKET_LAUNCHER.md) | Short executor startup guide |
| [Environment](../docs/development/ENVIRONMENT.md) | Canonical setup and validation |
| [Development Hub](../docs/development/carbon_hub/orientation/START_HERE.md) | Implementation map and navigation |

## Delivery

Use one branch and pull request per bounded task by default. Read the relevant authority, implement coherent changes, run focused checks, and complete the scope-required automated acceptance. Merge the tested revision with the expected-head guard after `Merge gate` passes and any applicable owner block or conflict is resolved.

`OWNER-DX-03` supersedes older mandatory human-review, GPT-receipt, review-quota, and post-merge full-CI requirements in historical templates. Use a normal merge commit; do not squash, rebase-merge, or enable auto-merge. Confirm the merge and record the bounded result. Avoid empty or evidence-only commits.

Scientific qualification, security acceptance, legal rights, live economics, deployment, and launch remain separate decisions. Passing software checks does not grant them. Material decisions follow the current decision protocol within the work's authorization.

## Status and optional executors

Wave A and Wave B have closed in their recorded engineering scopes. The repository now includes Wave C work and parallel battery, research-tooling, and Control Center tracks. Consult each track's current record rather than inferring all activity from an older wave snapshot.

Executor integrations live under [executors/](executors/). They cannot override repository instructions. The retired `agent_pack/.agent/` path is not an entry point.
