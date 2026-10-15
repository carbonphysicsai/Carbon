# PLT-14: Graphite tool argument and session identity events

Active authority: the owner's Platform2 queue item, 2026-10-13.
Reviewer: Graphite Testing Manager, with Carbon Validator for disclosure.
Starting main: e9a28008b3975c3aaa93b710b6f623221241c2eb.
Historical map_ref: SYSTEM/AGENT-EXECUTION; Hub maintenance is retired.

Record an argument snapshot for every model tool call, including engine-local,
rejected, truncated, parallel-not-run and exception paths. Freeze a prospective
logging-policy identity and derived agent/role/model identity in new sessions.
Existing sessions and their immutable journals are not rewritten or backfilled.

The snapshot is a positive projection of public tool fields. Public action/kind
selectors, bounded numeric settings and Booleans may be retained. Free text,
code, strategies, identifiers, files/paths, unknown fields and malformed JSON
are redacted. Unknown tool names are replaced with a fixed label. Digests bind
the redacted snapshot, never raw secrets or denied arguments. Plain-text
forecasts may remain redacted; their presence is not numerical evidence.

KEEP the existing loop's dispatch/replay identities and canary matching policy.
WRAP tool observations with a Graphite-only optional, read-only loop observer.
REPAIR raw refusal arguments. The controller's existing exact configured-canary
match may inspect the already-retained private call intent through a Boolean
provider seam; no canary token or new private archive enters events. This keeps
the canary halt/finding without broadening matching or introducing token hashes.

Target files: Graphite provider/tools and a new projection leaf; shared research
loop and controller; focused synthetic tests; this contract/decision and docs.
Do not touch experiment.py or miner_mcp/standard.py, owned by open PR #1290.
Other open PRs have no overlap with these targets at ticket start.

Validation: scripted harness and canary baseline; coverage/redaction mutations,
identity pinning, replay/crash and private-intent failures; relevant loop,
Graphite and controller regressions; canonical exact-head CI and Merge gate;
Black/Ruff, UTF-8/diff checks and pre-push delivery hygiene.
No real hidden/sealed data, model calls, hosts, probes, spend or LIVE operation.
Completion earns implemented/tested development telemetry, not security or
scientific qualification. One PR to main, exact-head Ready handoff, <=15-line
local queue report, then stop.
