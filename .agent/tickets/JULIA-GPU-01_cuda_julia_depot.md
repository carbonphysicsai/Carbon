# JULIA-GPU-01: CUDA in the pinned Julia depot, so `run_julia` can use the GPU

Owner authority: the owner, in chat on 2026-10-03, approving the open question
from C-MLP-05 (https://github.com/carbonphysicsai/Carbon/pull/523): "I approve
all. Including security review and GPu Julia" (OWNER-EXEC-APPROVALS-01,
item 4).

**Primary Development Hub map_ref:** `SYSTEM/AGENT-EXECUTION`,
`HUB_UPDATE_REQUIRED`.

**Status:** scoped, not built (2026-10-03). Two engineering preconditions are
missing, and neither is available in a cloud session:
- a Docker host to build the depot;
- write access to the GHCR depot package to publish it.

## What is approved

The pinned Julia depot carries CUDA, so a miner's `run_julia` code cell can
use a GPU on the miner's own machine, as `run_python` can under C-MLP-05.

The approval does not change:
- **Validator and evaluation.** The validator stays on jax-cpu. Julia's
  analysis scope stays `official_eligible: False` and
  `PUBLIC_MINER_AUTHORED_JULIA_NO_EVALUATOR`
  (`carbon/development_session/julia_analysis.py`).
- **Evidence status.** GPU practice is speed only and never evidence.
- **Reference workers.** The reference-worker images
  (`Dockerfile.julia-worker`, `Dockerfile.julia-science`) and
  `reference_runtime/julia/Manifest.toml` are out of scope.
- **Security status.** The C-MLP-05 GPU code cell remains unqualified for
  security; see OWNER-EXEC-APPROVALS-01 item 3. This ticket inherits that
  review requirement (AGENTS.md §13).

## Where the image is pinned today

- **The lock.** `scripts/dev/julia_depot.lock.json` names the GHCR depot by
  digest.
- **Recipe and identity.** `carbon/development_session/julia_depot.py`
  covers:
  - the pinned ubuntu base;
  - Julia 1.13.0;
  - the offline bootstrap;
  - `fetch_recipe`, the only step with network;
  - `precompile_recipe`, which runs with network off and deletes
    `scratchspaces`.
- **Environments.** `julia_environments/{current,pde}/{Project,Manifest}.toml`.
  Neither carries CUDA. GPUCompiler and LLVM are already present through
  Enzyme.
- **Build and CI.** The build is `julia_depot_build.build_depot`, behind
  `scripts/dev/julia_depot.py` (key, adopt, build). The CI job `c03-worker`
  adopts the locked depot and has only `packages: read`.
- **Today's GPU refusal.** On C-MLP-05, `run_julia` with `device: gpu` is
  refused before dispatch with `julia_gpu_unavailable`.

## Plan

**Slice 1: the depot (can land on `main` before C-MLP-05).**
1. **Packages.** Add CUDA.jl to the `current` environment with
   `preserve=PRESERVE_ALL`, so existing pins do not move. Add cuDNN only if a
   Lux or Flux GPU convolution is wanted.
2. **Preferences.** Commit a `LocalPreferences.toml` that fixes the CUDA
   runtime version and disables the bundled compatibility driver. Without
   it, a GPU-less build host selects no CUDA artifact and the offline
   sandbox fails at run time.
3. **Artifacts.** `fetch_recipe` installs artifacts for the CUDA-tagged
   platform, not only the host platform. Everything must be inside the
   image: runs use `--network=none` and `JULIA_PKG_OFFLINE`.
4. **Runtime precompile.** Run `CUDA.precompile_runtime()` and keep the
   GPUCompiler scratchspace that `precompile_recipe` now deletes. Otherwise
   every GPU run recompiles the device runtime.
5. **Identity.** Add `LocalPreferences.toml` to the depot identity
   (`environment_files`, `depot_document`, the `fetch_recipe` COPY). Update
   `tests/cpu/test_julia_depot_identity.py`.
6. **Test.** With no network and no GPU, the depot loads CUDA, finds its
   artifacts, and reports `CUDA.functional() == false`. CPU runs are
   unchanged.
7. **Publish on a Docker host:** run `julia_depot.py build`, push to GHCR,
   read the RepoDigest, and write the lock with `julia_depot.py key`. Do this
   in the same PR, or CI rebuilds the depot cold against its 150-minute
   limit.

**Slice 2: the code cell (after C-MLP-05 merges).**
1. **Local GPU.** Remove `julia_gpu_unavailable` for local GPU runs. Add the
   accelerator to `run_julia`.
2. **Carrier.** Add a Julia GPU host check (a depot check plus an NVIDIA
   runtime check). The current check accepts only the Python GPU worker's
   lock digest. Add a Julia CUDA profile in `research_carrier._worker_profile`.
3. **Remote GPU.** Keep remote Julia GPU refused, under its own code. The
   remote route is bound to the one pinned Python GPU worker.
4. **Text and records.** Update the MCP and page text, prelaunch,
   `carbon/challenge_kit/standard.py` (invariant 16), tests, DECISIONS and a
   Hub event.

**Slice 3: GPU host only.** Run a real kernel. Record the host driver
minimum and the cost of the first GPU run.

## Open questions and blockers

- **Compatibility, unverified.** Does a CUDA.jl release resolve against
  Julia 1.13.0 and the GPUCompiler/LLVM versions Enzyme pins in `current`?
  If not, the choice is an owner decision: a separate CUDA environment, or a
  separate depot.
- **Size, estimated not measured.** The miner image grows by an estimated
  3–5 GB uncompressed. The cold CI build, already 55–85 minutes, gets longer.
- **The CUDA runtime version.** Choosing it is an engineering decision,
  recorded in `.agent/DECISIONS.md` when slice 1 lands.

## Definition of done

- **Slice 1:** the depot lock names a published depot with CUDA. Identity
  and offline-load tests pass in CI. CPU suites are unchanged.
- **Slice 2:** `run_julia` with `device: gpu` dispatches locally under the
  same isolation as `run_python`. Remote Julia GPU is refused, named.
- **Slice 3:** a recorded kernel run on a GPU host.

Maturity on completion: DEVELOPMENT; IMPLEMENTED and TESTED. Not
SECURITY_QUALIFIED.
