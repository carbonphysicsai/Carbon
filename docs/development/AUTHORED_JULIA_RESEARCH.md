# Authored Julia research (prospective DEVELOPMENT scope)

C-CORE-07 extends the existing admitted workspace with `run_julia`. Python
remains the controller and JAX reconstruction remains independent. The authored
Julia image has no evaluator modules and never replaces the registered C-04
Julia methods. Every result is `MINER_SELF_REPORTED`, `STRUCTURAL_ONLY`, and
ineligible for official evaluation or automatic training-support promotion.

## Operator preparation

Build from an existing exact Julia worker manifest on an eligible Linux host:

```sh
python scripts/dev/build_julia_analysis_image.py \
  --parent-manifest .carbon-artifacts/julia-worker-image.json \
  --root .carbon-artifacts/authored-julia
```

This build reuses the checksum-pinned Julia 1.13.0 binary already in its parent.
Both analysis layers build with network disabled. It prints an image manifest
and the `runtime_authored_research` scope to declare; building grants no
execution authority by itself.
The build pins the parent image, Julia archive, empty external-package manifest,
project, source and bootstrap. The closed environment contains Base and the
standard libraries shipped in that exact distribution. The controller performs
no request-time package resolution or installation; package addition is unavailable.

No grant is needed (C-MLP-02-D11). Put the printed `runtime_authored_research`
list in your runner profile's `runtime.authored_research`, and the printed
manifest path in the profile's `authored_julia_image`. The two are required
together. When you launch, after registration is read, the runner installs the
record into the new campaign's root; a resumed campaign must still hold the same
record, and a different one is refused rather than swapped under it. The same
pattern applies to GPU research through `gpu_image`.

The MCP command attaches to one of your campaigns:

```sh
carbon-mcp --configuration /private/runner-profile.json --campaign <campaign id>
```

It checks the exact private image record against the admitted analysis parent
and runtime scope. Client discovery offers `run_julia` only when the campaign's
frozen runtime declares it. Every direct start and reconnect rechecks
authorization; discovery is not authorization. Existing domain task, transport
identity, campaign ownership, lease, watchdog, cancellation, artifact and
accounting services remain shared.

The Launchpad research runner freezes a copied tool schema that includes
`run_julia` for such a campaign. Its stopping rules and provider accounting are
unchanged, and any budget is the miner's own. An existing Python-only frozen
campaign cannot be upgraded in place: declare Julia in a new campaign.

## Client request

Call `carbon_research_v2__start_research_task` with a real JSON object:

```json
{
  "operation_id": "authored-julia-example-0001",
  "kind": "workspace",
  "strategy": null,
  "action": "run_julia",
  "arguments": {
    "source": "write(\"/scratch/output/squares.f64le\",Float64[i^2 for i in 1:8])",
    "files": [],
    "seconds": 90,
    "hypothesis": "Check a small public numerical construction",
    "expected_effect": "Retain eight finite squared values"
  },
  "hypothesis": "Check a small public numerical construction",
  "expected_effect": "Retain eight finite squared values"
}
```

The adapter encodes this action as `DevelopmentWorkspaceTaskSpecV2`; V1 accepts
the same historical actions and has unchanged wire tags. Source plus arguments
fit the existing bounded workspace request; callers cannot supply an executable,
shell command, image, package URL, environment override, grader or host mount.
Only explicitly named own/public workspace files enter the worker. Its working
directory is `/scratch/workspace`; write exports beneath `/scratch/output`.

Export types are `.json` with finite numbers and unique keys, `.f64le` with
finite little-endian binary64 values, and UTF-8 `.txt` notes. Each member is at
most 8 MiB, with existing aggregate output and member limits. Array shapes,
units and axis meanings should be saved in companion JSON. These declarations
remain self-report and do not certify physical meaning. Malformed, nonfinite,
undeclared-precision or escaping exports fail before result association.

Keep the same `operation_id` and payload across retries/reconnects. Status,
result and cancel use the returned existing task identity. A changed payload
with the same operation identity conflicts. A new output directory grants no
extra allowance. Script execution, compilation and failed work count within
the existing numerical allowance; uncertain work retains its reservation until
the existing controller observes cleanup and reconciles it. No process exit,
disconnect, small tolerance or solver agreement implies a refund or scientific
success. Retain unsupported package/method requests through `capability_request`.

## Boundaries and acceptance

Startup/history hooks are disabled on the registered Julia invocation; load
path, project and depot are fixed. The image and inputs are read-only, scratch
is ephemeral, networking is disabled and credentials/controller state/sockets
are absent. Arbitrary research source remains hostile within those worker
controls. Environment variables alone are not a sandbox. Validator workers
never load miner-writable compiled caches or this research image.

Run focused contract tests and actual isolation tests with the exact worker:

```sh
python -m pytest tests/cpu/test_authored_julia.py -q
CARBON_JULIA_WORKER_MANIFEST=.carbon-artifacts/julia-worker-image.json \
  python -m pytest tests/service/test_authored_julia_service.py -q
```

The service cases use registration-admitted fixture campaigns, actual Julia and
Docker, and an external stdio client with fixture signing/registration. They do
not establish paid-agent usefulness, production authentication/security
qualification, physical reference qualification, accelerator Julia support,
public deployment, or admission to existing exhausted campaigns.

Julia invocation and environment semantics follow the upstream
[command-line interface](https://docs.julialang.org/en/v1/manual/command-line-interface/)
and [environment documentation](https://docs.julialang.org/en/v1/manual/environment-variables/).
Offline package behavior is distinct from containment, as described by
[Pkg.offline](https://pkgdocs.julialang.org/v1/api/#Pkg.offline).
