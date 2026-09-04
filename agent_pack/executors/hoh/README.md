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
ephemeral invocation with user config ignored, an explicit sandbox, a fixed
working directory, and an output JSON Schema. Planner and Tester use
`read-only`; Developer uses `workspace-write` only in a sanitized disposable
Git projection. The controller validates its clean commit and imports only the
plan/run-allow-listed patch into the dedicated ticket worktree. Mandatory
protected patterns cannot be removed by a run manifest, only regular-file Git
modes are importable, and any failed import restores the exact prior candidate.
Role subprocesses receive a small allow-listed environment rather than
inheriting API keys or other ambient variables. `danger-full-access` is never
used. See the official [Codex SDK and programmatic control documentation](https://developers.openai.com/codex/sdk)
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
that command in the isolated candidate projection and matches its exit status
and stdout/stderr digest before accepting `VERIFIED`. An empty command list,
as in the pre-science B-05 navigation manifest, cannot produce `VERIFIED`.

The Codex sandbox and projection boundary are defense in depth for this
development pilot. They are not a production arbitrary-code security claim.

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
