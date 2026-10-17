# Carbon execution protocol

This is an executor-independent entry point, not a second policy stack.
[AGENTS.md](../AGENTS.md) contains engineering instructions;
[the delivery protocol](../.agent/DELIVERY_PROTOCOL.md) contains delivery rules;
[the decision protocol](../.agent/DELEGATED_DECISION_PROTOCOL.md) separates
delegated work from reserved human decisions. Use their current versions and
current direct human directions. Executor/vendor settings do not override them.

## Work the current task

Use the current owner-authorized task and relevant domain authority. A stale
board, historical orientation, future plan or OPEN/EMPTY queue cannot replace a
new direct assignment. Do not restart cancelled runtime jobs or recurring work.
A new development task does not extend an old budget or schedule.

Inspect the existing callers and tests, choose the smallest complete useful
change, and implement it on an appropriate isolated branch. Use a suitable
approved base; refreshing main solely for distance is not a prerequisite.
Preserve others' work. For explicit parallel work, agree disjoint ownership and
one integration owner rather than duplicating implementations or reviews.

Complete coherent vertical behavior and remove the obsolete active callers it
replaces. Validate the actual normal path; do not substitute a new screen,
parser, direct component probe or catalogue entry for integration. A dependency
or receiver acknowledgement blocks only the action that actually consumes it.

Record material choices once, run focused tests and the applicable canonical/CI
acceptance, and follow the delivery policy. Report changed behavior, deletions,
actual checks, limitations and earned maturity. Do not repeat green checks or
manufacture status reports. A blocked action names its actual source and scope.

## Boundaries remain

Keep hidden evaluation material out of construction; do not import arbitrary
participant code into the judge, controller or model-bank host. Keep hostile
execution isolated with actual resource limits, finite deadlines and owned
cleanup. Keep native model/fixture/prediction bytes and lineage in the existing
ScoreLab bank. Preserve Bittensor identity and transport safeguards.

Science, security acceptance, economics, rights, deployment and qualification
retain their human owners. Reference/infra failure is not candidate failure;
fixtures are not LIVE evidence; historical scores keep their old meaning.

The Development Hub and `.agent/DECISIONS.md` are frozen history. Do not select
map references, regenerate Hub pages, repin snapshots or append historical
ledgers. `agent_pack/.agent/` is retired. Optional harness-specific setup lives
under `agent_pack/executors/`; it cannot add product or delivery authority.
