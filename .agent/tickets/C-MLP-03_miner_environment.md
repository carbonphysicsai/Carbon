# C-MLP-03: a registered miner's environment comes with GPU, model and agent connected

Owner authority: the owner (Fitz), in chat on 2026-09-30:

> This environment is supposed to be fully loaded with GPU + Model + Agent set
> up immediately after miner registration. Offering Engy/chutes inference
> targon/Lium compute Hermes/mira agents.

and, on scope:

> We are just facilitating a miner to set those things up on their own machine!
> We aren't hosting anything except for the environment.

Recorded as `OWNER-MINER-ENVIRONMENT-01` in `.agent/DECISIONS.md` (slice 1).

**Primary Development Hub map_ref:** `SYSTEM/AGENT-EXECUTION`,
`HUB_UPDATE_REQUIRED`.

**Status:** slices 1 to 5 implemented, and slice 6's engineering seam
(engineering evidence only), Targon and Mira excepted (below). Slice 6's run
itself is a person's, on a clean machine
(`docs/development/FRESH_MINER_JOURNEY.md`). Slice 2's live acceptance (completions with miner-held
Chutes and Engy keys, and a battery autonomous launch with each) is pending
the miner's keys. Slice 3's (a real battery practice on a local GPU, and the
same recipe accepted by the validator) is pending a GPU host. Slice 4's (one
real battery practice each on RunPod and Lium from a miner account, teardown
verified and charges reconciled) is pending the miner's accounts. Slice 5's
(a Hermes-driven battery campaign that practices, freezes and submits) is
pending Hermes and the miner's keys.
- Setup: `scripts/dev/miner_launchpad/environment_setup.py`, with routes
  `/api/v1/setup` in the controller and the "Set up your environment" view.
- Tests: `tests/cpu/test_miner_launchpad_environment_setup.py` and
  `setup_journey` in the Launchpad browser smoke.
- **Recorded engineering decisions (slice 1):**
  - *Images are verified, not pulled.* Carbon publishes no image registry,
    and the worker is built from the miner's exact clean checkout. Setup
    verifies the locally built worker and analysis images against that
    revision. A missing one is refused by field with its build command.
    Pulling a pinned image stays open until a registry exists.
  - *Consent is to a quoted amount (2026-10-01).* A check that spends runs
    only when its `consent` names the maximum cost the controller quoted for
    that provider and model (`/api/v1/setup/quote`): Carbon's reservation
    bound for the check's own settings, or the stated absence of one when no
    price is known. A bare `true` is refused, so a client that defaults
    consent on spends nothing. The page's agreement box is unticked by
    default and clears on any change of provider or model.
  - *The agent step must not take the miner's password (2026-10-01).* As
    first written, it opened the hotkey with the miner's password through
    `open_external_hotkey`, stored the password owner-only and wrote
    `miner_password_file` into the profile. That is the defect #445 removes,
    and it contradicts the external signing this ticket's decision keeps. The
    step is rebuilt on #445's signer: it checks the registered hotkey through
    `connect_signer`, takes no key file and no password, and the profile names
    neither. #445 merged on 2026-10-01 and this branch merged main after it.
    The Agent step now asks the miner's running `carbon-miner-signer` which
    hotkey it holds (an optional `signer_socket` names a non-default socket).
    A refusal names the field `signer`, carries the signer's closed code, and
    gives the next step "start `carbon-miner-signer` for your registered
    hotkey". `miner-public.json` holds only the netuid and hotkey. A password
    stored by the earlier version of the page is deleted. Provider API key
    paths are named `credential_file`, so the product's no-key invariant
    (`tests/invariants/test_product_process_holds_no_key.py`) passes with no
    exception. The MCP handshake for an external agent is slice 5.
  - *Own machine is every miner's default (owner, 2026-10-01).* "ALL Miners
    in launchpad should default to their own machines and can set up
    sandboxes themselves if they want." Setup offers the miner's own machine
    as the compute default. A sandbox or rented GPU is something a miner may
    set up for themselves; Carbon never chooses one for them, and slices 3
    and 4 keep that default.
  - *The key belongs to one provider.* The profile records the setup's
    `model_selection`. An autonomous launch that names no model runs with
    it. A key file named in `provider_credentials` is never used for the
    pinned default provider.
  - *The operator config is supplied, not generated.* The miner supplies its
    path, and setup validates it for subnet 567. Its content is deployment
    identity and never enters the repository.
- **Slice 2 (inference):** `model_provider.py` adds the `chutes` adapter and
  `published_pricing`; setup offers every adapter, Engy Chat Completions
  first; `tests/cpu/test_miner_inference_providers.py` and the setup browser
  smoke cover it.
- **Recorded engineering decisions (slice 2, 2026-10-02):**
  - *Chutes settles on metered usage.* Whether Chutes reports a charge, and
    its rate limits, are unverified. Until they are, no charge report is
    read: spend is the returned usage at the published price, within the
    reservation rule.
  - *A live price is recorded with its list and time.* Chutes' per-token
    prices are read from `GET /v1/models` when the miner quotes. The record
    keeps the list URL and the UTC time read (`provider_published`), and a
    launch reuses that record rather than re-reading. USD per million tokens
    becomes integer nanodollars per token (×1000, rounded). A model the list
    does not price is refused at setup, not launched at unknown spend.
  - *Chutes and the generic adapters take a typed model id.* They have no
    fixed list, so any id the provider serves is accepted; Chutes must price
    it.
  - *A generic endpoint is configured only in setup.* An OpenAI-compatible
    adapter launches only as the setup's own choice, with the endpoint and
    optional declared price recorded in the profile. Choosing another
    generic adapter at launch is refused (`model_provider_endpoint_not_configured`),
    so no launch request can point Carbon at a new URL.
  - *Chutes OAuth is not built.* Its scopes, billing and revocation are
    unverified; a key is the only credential.
- **Slice 3 (the miner's own GPU):** `carbon/development_session/battery_gpu.py` (battery's
  GPU practice scope and program), the carrier's GPU branch in
  `research_carrier.py`, `BatteryPractice(gpu_image=...)`, the registry's
  battery `gpu_research` profile, and setup's "This machine (your GPU)"
  compute choice; `tests/cpu/test_battery_gpu_practice.py` and the setup
  browser smoke cover it.
- **Recorded engineering decisions (slice 3, 2026-10-02):**
  - *The GPU path is the carrier, not the C03 reconstruction controller.*
    Battery practice is Carbon's fixed program in the isolated carrier. On a
    GPU it runs the same way with the miner lane's GPU worker profile:
    `MINER_HOST_SELF_SERVICE`, role `MINER_RESEARCH`, the device from the
    installed host device record, `JAX_PLATFORMS=cuda`, the doctor's
    miner-lane checks, the miner device lease and Carbon's own
    retained-container check. No grant is needed. Only Carbon's fixed
    practice program may ask for the GPU; a miner-authored script cannot.
  - *The worker image is the existing GPU worker.*
    `scripts/dev/accelerator_worker_image.sh` builds the C03 worker with the
    CUDA JAX plugin. The battery files are staged byte-identical on every
    run, so the image needs no battery build of its own. It serves JAX
    recipes only, and a PyTorch recipe is refused before anything runs.
  - *The backend is recorded as observed.* The GPU program is the CPU program
    plus a `runtime.json` the worker writes (`JAX_PLATFORMS`, JAX's default
    backend, device kinds and count). The feedback carries that, the device
    record digest and the speed-only note. The CPU program is unchanged, so
    no existing practice identity moves.
  - *The device is bound into the request.* A GPU request names the
    installed device record's digest, so a replaced or withdrawn record is a
    different request. A CPU request is exactly what it was.
  - *Setup installs the host record when it can.* It detects the GPU with
    nvidia-smi and writes `/var/lib/carbon/accelerators/host-device.json`
    (`this-machine`, `own-machine`) when the controller may. Otherwise it
    names the `carbon_accelerator.py prepare` command. Several GPUs, or an
    unknown platform or container runtime, are the miner's to name; setup
    does not pick for them.
  - *CPU stays the default.* The GPU is offered beside it, never chosen for
    the miner (owner, 2026-10-01).
  - *GPU knowledge stays on the execution side.* Only the execution packages
    may import the accelerator profile (`test_protected_material_isolation`),
    and `carbon.battery` holds protected material (exam pools, seeds, truth).
    So battery's GPU practice code lives in `carbon.development_session`,
    beside Burgers' GPU lane, and the boundary is not widened.
- **Slice 4 (rented GPUs):** `carbon/compute/job_server.py` (the one-job
  server a rented pod runs), `remote_job.py` (its client),
  `rented_runner.py` (the carrier-compatible runner over `ComputeService`),
  `lium.py` (Lium adapter), `providers.py`, the RunPod adapter fixes, the
  battery `rented_gpu` scope, and setup's "A GPU rented on your own provider
  account". `tests/cpu/test_rented_job.py`, `test_rented_runner.py` and
  `test_lium_adapter.py` cover it.
- **Recorded engineering decisions (slice 4, 2026-10-02):**
  - *A rented pod runs one job, served by Carbon's own fixed server.* The
    pinned GPU worker's wheel includes `carbon.compute.job_server`; it is the
    pod's start command. The controller stages the job's public inputs, runs
    them and fetches the output over HTTP, with a per-job random token. The
    pod gets the pinned worker, the public inputs and that token. No provider
    key, hotkey or signer leaves the miner's machine. Runs start
    asynchronously and are polled, because provider proxies close long
    requests (RunPod's Cloudflare proxy: 100 s).
  - *The pinned worker reaches the pod through the miner's own registry.*
    Carbon publishes no registry. The miner pushes the GPU worker and names
    it by `repository@sha256` digest. Setup checks that digest is one of the
    local pinned image's RepoDigests.
  - *Spend follows the compute layer's existing rules.* A balance is observed
    and recorded first, the hourly ceiling and deadline bound each pod, and
    the miner's budget applies. Each trial rents one pod, which is terminated
    and verified gone whether the job succeeds or not. The provider's own
    charge is recorded when it reports one; otherwise the record says it is
    unresolved, never an estimate. A durable job record (owner-only) fixes the
    request, token and deadline before any provider call, so a restart never
    sends a different request.
  - *Provider facts, read 2026-10-02.* RunPod REST v1 (`dockerEntrypoint` /
    `dockerStartCmd`; billing needs `grouping=podId`, which the adapter now
    sends) and GraphQL for balance and price. Lium's OpenAPI (`X-API-Key`,
    executors, one-time templates by digest, rent with an idempotency key and
    a termination time, per-pod statements).
  - *Lium jobs travel over plain HTTP.* Lium documents no HTTPS proxy, so the
    job is reached on the node's IP. The token and public inputs cross
    unencrypted, and the backend record states `job_transport: http-direct`.
    Nothing secret is on the pod, and nothing measured there is evidence.
  - *Targon is not built.* Its current API runs no container image (the
    rental type answers 410; VM, bare metal and sandbox take no OCI image),
    and it reports no per-workload charge. A VM-and-SSH design would be
    needed; that is an owner decision. Targon stays an unavailable
    integration with that cause.
- **Slice 5 (agents):** `scripts/dev/miner_launchpad/hermes_setup.py` and
  setup's Hermes choice; `tests/cpu/test_hermes_setup.py` and the setup
  browser smoke cover it.
- **Recorded engineering decisions (slice 5, 2026-10-02):**
  - *Hermes gets a dedicated profile.* Setup writes
    `<HERMES_HOME>/profiles/carbon/config.yaml` and `.env`, so the miner's own
    Hermes configuration is never touched. The miner starts it with
    `hermes -p carbon chat`. Facts read 2026-10-02 from the Hermes Agent docs
    and repository (v0.21.5).
  - *Consent is to the exact files.* The Agent step names the files it would
    write and writes nothing unless the request's consent lists exactly those.
    The box is unticked by default. The files are written only after the
    signer has answered, so a refused step leaves Hermes untouched.
  - *The model is the setup's inference choice.* It is a custom
    OpenAI-compatible provider whose key is read from the profile's owner-only
    `.env` (`key_env`), never from the config. Hermes speaks Chat Completions,
    so the Anthropic-shaped routes are refused by name.
  - *Carbon's server asks first.* The `mcp_servers.carbon` stdio entry runs
    `carbon.miner_mcp.standard_cli --configuration <runner profile>` with this
    checkout's interpreter. `trust: untrusted` makes Hermes ask the miner
    before every tool that can change anything (launch, practice, freeze,
    submit).
  - *Mira is recorded and stopped.* autoscience.ai/mira (read 2026-10-02) is
    reached through a sales form and documents no tool connection, MCP or
    otherwise. Per this ticket the slice records that and stops: a network
    door into a miner's machine is an owner decision. Mira stays an
    unavailable integration, and the agent provision closes without it.
- **Slice 6 (the fresh-miner journey):** `carbon/battery/remote_submission.py`,
  the campaign's intake path, the profile's `battery_intake`, setup's
  intake check, and the runbook `docs/development/FRESH_MINER_JOURNEY.md`;
  `tests/cpu/test_battery_remote_submission.py` covers it.
- **Recorded engineering decisions (slice 6, 2026-10-02):**
  - *A campaign submits through the validator's intake when the validator
    runs elsewhere.* The frozen candidate is built by `intake_client`, signed
    by the miner's own signer (`btauth/1`), and posted to the intake named in
    the profile. Its status is then asked until there is a verdict. One
    submission per epoch: its id is recorded (owner-only) the moment the
    intake answers, so a later attempt only asks its status. A refusal or a
    wait that runs out is not a verdict and consumes no epoch.
  - *An intake is https, or loopback.* The intake binds loopback until the
    owner's exposure record exists (`OWNER-…INTAKE-EXPOSURE-NN`, the §4
    security review). This slice reaches an exposed intake when there is one;
    it does not expose one.
  - *The run is a person's.* The journey needs a clean machine, a registered
    hotkey, the miner's keys and accounts and a reachable validator, none of
    which this repository holds. The runbook says what to do and what to
    record, and closes no Gap.
- One pull request per slice, each based on main.
- Written against main `af5b8ac0`.
- The owner authorized per-slice branches `claude/c-mlp-03-slice-N` on
  2026-09-30.

**Supersedes:**
- the unticketed "C-MLP-03: Hermes, Chutes and Lium" plan in
  `docs/development/MINER_LAUNCHPAD_HANDOFF.md`;
- the compute, model and agent scope of the first release in
  `docs/development/CONTROL_CENTER_PROGRAMME.md`.

The programme's other owner decisions stand: validator hosting, the reused
UID, external signing and battery first. Its decision 3, "the model provider
is the miner's choice", also stands. This ticket delivers it.

## Why

- **2026-09-17.** The Launchpad handoff named Hermes + Chutes inference +
  Lium GPU workers as the first combination, with Engy after it and Mira once
  verified. It was sequenced after a first end-to-end run and never ticketed.
- **2026-09-26.** The Control Center programme replaced that plan with RunPod
  as the one cloud path, the miner's own model key file and stdio MCP.
  Hermes, Chutes and Lium were not carried over. Targon was never in any plan.
- **What shipped stops at generic seams.** A miner hand-writes a runner
  profile with key-file paths, attaches "a host you control" and brings their
  own MCP client. Everything else is listed as unavailable.
- **Battery has no GPU research path.** Battery is the only launchable
  Challenge.
  - The GPU lane binds Burgers material
    (`carbon/development_session/gpu_research.py`).
  - Battery refuses a GPU runtime (`carbon/battery/campaign.py`,
    `RUNTIME_KEYS`).
  - The RunPod adapter in `carbon/compute/` has no launch path.
- **No gate required any of it.** `test_unavailable_reasons_have_causes`
  keeps each "unavailable" reason true, which is correct. But a true reason is
  not a plan. This ticket turns each one into a slice with an acceptance.

## Target

Once the onboarding door confirms registration, the Launchpad on the miner's
own machine takes them through one setup: inference, compute, agent. It
writes their configuration itself. Their first battery campaign then launches
on a GPU, with a model and an agent, with no terminal and no hand-edited file.

Carbon hosts nothing new. Every account, key and bill is the miner's, and no
key ever reaches Carbon.

## Slices

Slices 2 to 5 can be accepted on the validator's own host. Slice 6 is the
journey from a different machine.

### 1. Setup after registration, and the gate

- **Record the decision.** Record `OWNER-MINER-ENVIRONMENT-01`.
- **Gate first.** Add the `compute`, `model` and `agent` provisions to the
  research environment standard (`carbon/challenge_kit/standard.py`).
  - Battery starts with three named Gaps, each naming the slice that closes
    it: `model` slice 2, `compute` slices 3 and 4, `agent` slice 5 (Hermes;
    Mira joins once verified and does not hold the Gap open). Each closing
    slice replaces its Gap with `Provided` evidence.
  - The standard's test already fails on a silent gap.
- **The setup view.** When `confirm` reports the hotkey registered, the
  Control Center opens "Set up your environment". Its steps are Inference,
  Compute, Agent and Review. Each step shows only choices that work, each
  with its cost basis.
- **The profile writes itself.** Setup produces every field
  `carbon.launchpad.runner-profile.v2` requires, including pulling and
  verifying the pinned images. The controller then loads that profile without
  a terminal restart. `--research-profile` stays for operators.
- **Keys stay on the machine.** A key is entered once on the loopback page.
  The controller writes it to an owner-only file in an owner-only directory,
  and the profile references it by path. It is never logged, never shown
  again, and sent only to its own provider.
- **Every connection is checked live.** The checks use the miner's key and
  run at their cost, and setup says so first.
  - Inference: list the models and run one short completion.
  - Compute: read the balance and the inventory.
  - Agent: complete a handshake.
- **Refusals name the field** they are about (#419).

### 2. Inference: Chutes and Engy

- **Add a Chutes adapter** to `model_provider.ADAPTERS`.
  - Transport: Chat Completions at `https://llm.chutes.ai/v1`, with a bearer
    key.
  - Models and per-token prices come from the public `GET /v1/models`,
    recorded with source and time.
  - Settlement: from a provider charge report if Chutes returns one;
    otherwise the reservation rule applies.
- **Engy joins setup.** Default to its Chat Completions route.
- **Make the generic adapters launchable.** Carry `endpoint` and
  `declared_pricing`, validated.
- **Accept a free-text model id** for adapters with no fixed list.
- **Optional:** "Sign in with Chutes" (OAuth), after verifying its scopes,
  billing and revocation.
- **Keep the unavailable list true.** Update `INTEGRATIONS` and
  `test_unavailable_reasons_have_causes` in the same PR.
- **Acceptance:**
  - a live completion through Chutes and one through Engy, each with a
    miner-held key;
  - a battery autonomous launch validates with each.

### 3. GPU for battery research: the miner's own GPU

- **A battery GPU practice path:**
  - a battery-bound `gpu_research` scope;
  - a pinned GPU worker image carrying the battery training code;
  - `JAX_PLATFORMS` set and recorded;
  - the backend recorded in practice feedback.
- **Setup detects the GPU** and installs the host device record. The miner
  lane keeps its own requirements (C-CORE-19).
- **Say it plainly in the UI.** GPU practice is for speed only. The validator
  rebuilds on its own pinned backend and resources.
- **Acceptance:** a real battery practice on a local GPU with the backend
  recorded, and the same recipe accepted by the validator.

### 4. Rented GPU: Lium, Targon and RunPod on the miner's account

- **`ComputeProvider` adapters** for Lium and Targon; RunPod wired the same
  way.
- **`ComputeService` wired into launch**, with a durable intent, the pinned
  worker, and verified teardown.
- **Keep the trust boundary.**
  - The controller, keys and signing stay on the miner's machine.
  - A rented box receives the pinned worker and one job's public inputs only.
- **Spend stays the miner's.**
- **Acceptance:** one real battery practice each on Lium, Targon and RunPod
  from a miner account, with teardown verified and charges reconciled.

### 5. Agents: Hermes and Mira

- **Hermes** is configured locally with consent: an `mcp_servers` stdio entry
  running `carbon-mcp --configuration <profile>`, and a custom
  OpenAI-compatible model.
- **Mira** is Mira at autoscience.io (autoscience.io/Mira; owner,
  2026-10-01, OWNER-BATTERY-CARRYOVER-01). It is verified first: read its
  current documentation for how it connects to tools. If a cloud agent cannot reach a local tool
  server, record the Gap and stop: a network door into a miner's machine is
  an owner decision.
- **Acceptance:** a Hermes-driven battery campaign that practices, freezes and
  submits.

### 6. The fresh-miner journey

On a clean machine: register, set up, launch battery, practice on GPU, freeze
and submit, then verify teardown and cost. This confirms, from a different
machine, the three provisions slices 2 to 5 closed; it closes no Gap itself.

**Dependency.** A submission from a machine other than the validator's host
needs the battery intake (OD-7(b)) merged and exposed under its own record.

## Boundaries

- Carbon hosts nothing new, and no key reaches Carbon.
- No choice that spends is made for the miner. The existing finite ceilings
  for Carbon's autonomous battery agent still apply.
- The exam is unchanged. GPU practice is research only.
- Testnet 567 only. This ticket makes no chain write.
- Engineering evidence only; nothing here is qualified.
- Provider facts were read on 2026-09-30. Re-verify each before building on
  it.

## Owner input

- **Targon:** build a VM-and-SSH route (the pinned worker run with Docker
  inside a Targon VM, reached over SSH), or leave Targon out until its API
  runs container images again?

- **Which Mira?** Answered 2026-10-01: autoscience.io/Mira, not Mira
  Network's Flows (OWNER-BATTERY-CARRYOVER-01).
- **Mira's connection:** it documents none publicly (2026-10-02). Ask
  Autoscience how Mira reaches a tool server; if only over the network, decide
  whether a door into the miner's machine is acceptable.
