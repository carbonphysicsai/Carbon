# Carbon Harness-of-Harness controller

This directory contains optional, bounded development tooling for B-01H. It is
not Carbon runtime authority and is not included in the `carbon` wheel.

```text
authority + ticket + requirements
→ fresh read-only Planner projection
→ strict IterationPlan
→ workspace-write Developer in a sanitized projection
→ controller-validated patch import into one dedicated ticket worktree
→ exact clean candidate head/tree freeze
→ fresh read-only Tester projection
→ strict IterationEvidence
→ deterministic replan / pause / final-candidate handoff
```

The controller owns advancement. A model cannot promote a requirement, clear a
human block, approve a pull request, satisfy the final GPT review gate, merge,
qualify science/security/production, activate `LIVE`, or create network,
economic, or rights authority.

## Supported executor surface

`CodexExecAdapter` probes the installed CLI before use and invokes only the
supported non-interactive `codex exec` surface. Each role starts in a fresh
ephemeral invocation with user config ignored, a fixed working directory, and
an output JSON Schema. A custom Codex permission profile denies the filesystem
root, restores only Codex's minimal tool runtime, denies ambient temporary
directories, grants the disposable projection read-only for Planner/Tester or
writable for Developer, grants one fresh invocation-private temporary
directory, disables command network access and host-skill discovery, uses that
private directory as `HOME`, and sets approval policy to `never`. Authentication
may use the explicit `CODEX_HOME`, but sandboxed commands cannot read it. The
adapter never passes the legacy `--sandbox` flag because it would replace this
narrower permission profile. Before accepting the installed CLI, an adversarial
startup probe proves projection reads, read-only enforcement, Developer
projection writes, and denial of a sibling sentinel for both profiles. A
generic no-context `codex exec` preflight then independently uses both exact
read-only and workspace-write role configuration paths. Each must report
`custom permissions` on trusted stderr before any private role context is sent;
inability to enforce or select either boundary fails closed.

The controller validates the Developer's clean commit and imports only the
plan/run-allow-listed patch into the dedicated ticket worktree. Mandatory
protected patterns cannot be removed by a run manifest, only regular-file Git
modes are importable, and rollback is permitted only while the repository still
has the exact controller-attributable identity/content. Concurrent external
work is preserved and causes a closed identity failure. Both controller-owned
Git commit sites force a fresh empty hooks directory, and projection cleanup
never follows role-created symlinks.
Role subprocesses receive a small allow-listed environment rather than
inheriting API keys or other ambient variables. `danger-full-access` is never
used. See the official [Codex permission-profile documentation](https://learn.chatgpt.com/docs/permissions),
[Codex SDK and programmatic control documentation](https://developers.openai.com/codex/sdk),
and [non-interactive mode documentation](https://developers.openai.com/codex/noninteractive).

The adapter is executor-agnostic at the controller boundary. `ScriptedExecutor`
provides deterministic synthetic runs, and `ManualExecutor` explicitly pauses
for an externally supplied packet or consumes one supplied packet exactly once.

## Run state and resume

By default `StateStore.for_repository()` writes atomic mode-0600 JSON under:

```text
$(git rev-parse --git-common-dir)/.carbon-hoh/runs/<run-id>/
```

This state is outside tracked content. Resume revalidates the exact run
manifest digest, authority ref/commit/tree, ticket bytes, requirements bytes,
role profiles, clean candidate head/tree, and protected-context boundary.
`resume` also proves authority ancestry, recomputes and reauthorizes the exact
Git changed-path manifest and regular-file modes, rejects lifecycle-incoherent
phase/plan/requirement/regression state, reauthorizes every persisted Tester
disclosure, and independently replays every final accepted evidence command
before accepting a persisted `FINAL_CANDIDATE_READY` state. `retry` rechecks
identities before returning a `PAUSED_HUMAN` or `PAUSED_INFRA` run to the exact
coherent active phase that paused; Tester-originated pauses retain their plan.
Failure reason and evidence plus complete open-regression records remain
structured inputs to later roles.
Every initialize/resume/step/retry transaction holds a mode-0600 per-run lock,
and step/retry compare the persisted state digest with the version loaded by
that controller before writing. A stale controller therefore cannot overwrite
a newer transition. Executor unavailability, startup failure, and timeout enter
the typed `PAUSED_INFRA` state at the originating phase and remain eligible for
the same identity-checked retry path.

## Progressive disclosure

Each role starts with exact `initial_context` paths. A role can return
`context_requests`; the controller expands only tracked regular files matching
that role's `context_allow_paths`, rejects protected/out-of-authority requests,
records every disclosed path and SHA-256, and re-invokes the role. Every role
receives a disposable Git projection containing only granted paths; the
Developer projection is writable, while Planner and Tester projections are
read-only.

A requirements manifest also binds an exact closed command allow-list for each
requirement. Tester evidence must name a disclosed verifier artifact, its
digest, and one exact allow-listed argv. The controller independently reruns
that command through the executor evidence seam. The Codex adapter uses the
same verified read-only, root-denying, network-disabled profile with only the
candidate projection and a private runtime exposed; manual replay fails
unavailable, while direct subprocess replay exists only in the explicitly
synthetic test executor. The controller matches exit status and stdout/stderr
digest before accepting `VERIFIED`. An empty command list, as in the
pre-science B-05 navigation manifest, cannot produce `VERIFIED`.

The Codex permission-profile sandbox and projection boundary are defense in
depth for this development pilot. They are not a production arbitrary-code
security claim.

## CLI

From the repository root:

```bash
python scripts/dev/hoh.py probe-codex
python scripts/dev/hoh.py validate requirements agent_pack/executors/hoh/manifests/b05.requirements.v1.json
python scripts/dev/hoh.py init /absolute/path/to/run-manifest.json
python scripts/dev/hoh.py step /absolute/path/to/run-manifest.json
python scripts/dev/hoh.py retry /absolute/path/to/run-manifest.json
python scripts/dev/hoh.py retry /absolute/path/to/run-manifest.json --manual --packet /absolute/path/to/role-packet.json
python scripts/dev/hoh.py run /absolute/path/to/run-manifest.json
python scripts/dev/hoh.py status /absolute/path/to/run-manifest.json
```

`init`, `step`, and `run` use the Codex adapter unless `--manual` is supplied.
The run manifest must bind the executor/profile digests reported by the chosen
adapter. `run` stops at `PAUSED_HUMAN`, `PAUSED_INFRA`, or
`FINAL_CANDIDATE_READY`; the last state is only a handoff to
`.agent/DELIVERY_PROTOCOL.md`.

## B-05 pilot manifest

`manifests/b05.requirements.v1.json` maps `B05-D01` through `B05-D11` to the
unchanged B-05 Definition of Done and binds the exact ticket Git blob and
SHA-256 after OWNER-DX-02's status-only sequencing interposition. It contains no
measurement, threshold, weighting, uncertainty, reconstruction, stopping,
qualification, physical, or production value. Its verification-command lists
are intentionally empty until B-05 authority supplies real requirement-owned
verification; model prose cannot fill that gap.
