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

**Status:** slices 1 to 3 and 5 implemented, and slice 6's engineering seam
(engineering evidence only), Mira excepted (below). Slices 4 and 4b (a GPU
rented with the miner's provider key on RunPod, Lium or Targon) were built and
are **retired** by OWNER-MINER-COMPUTE-LINK-ONLY-01 (2026-10-02): Carbon rents
no compute, and old profiles, setup requests and frozen campaigns are refused
with `rented_gpu_retired_connect_your_machine`. Slice 4 is now the miner's own
remote setup, connected over SSH (LINKONLY-D4 to D9): a machine with Docker
(`ssh-docker`) or a container started from the pinned worker (`ssh-container`).
Its library, setup choice, profile scope, campaign doors and Control Center
wiring are built and tested; the `endpoint` transport is designed and not
built (LINKONLY-D7).
Slice 6's run itself is a person's, on a clean machine
(`docs/development/FRESH_MINER_JOURNEY.md`). Slice 2's live acceptance (completions with miner-held
Chutes and Engy keys, and a battery autonomous launch with each) is pending
the miner's keys. Slice 3's (a real battery practice on a local GPU, and the
same recipe accepted by the validator) is pending a GPU host. Slice 4's (one
real battery practice on a GPU machine or container the miner runs, with its
job container or process cleaned up) is pending a miner's machine. Slice 5's
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
- **Retired 2026-10-02 (OWNER-MINER-COMPUTE-LINK-ONLY-01):** slices 4 and 4b
  below are kept as the record of what was built. Their provider-API modules,
  setup choice, battery `rented_gpu` scope and campaign hooks were removed;
  `job_server.py` and `remote_job.py` stay for the remote-machine route. What
  a miner may still hold from them is refused by name
  (`carbon/compute/retired.py`, `tests/cpu/test_rented_compute_retired.py`),
  and setup deletes Carbon's stored copy of the provider key.
- **Slice 4 (rented GPUs, retired):** `carbon/compute/job_server.py` (the one-job
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
  - *Targon was not built in slice 4.* Its current API runs no container
    image (the rental type answers 410; VM, bare metal and sandbox take no
    OCI image), and it reports no per-workload charge. The owner chose the
    VM-and-SSH route on 2026-10-02 (OWNER-C-MLP-03-ANSWERS-01); slice 4b
    builds it.
- **Slice 4b (Targon, a VM over SSH, retired):** `carbon/compute/targon.py`, the
  `targon` provider with `vm_image` in the rented choice, and setup's VM
  image field and check; `tests/cpu/test_targon_adapter.py`, the rented
  runner and setup tests, and the setup browser smoke cover it.
- **Recorded engineering decisions (slice 4b, 2026-10-02):**
  - *Provider facts, read 2026-10-02.* Targon Hub API v3.7.0
    (`https://api.targon.com/tha/v3`, `Authorization: Bearer`), from
    docs.targon.com and the API's own version endpoint:
    - org-scoped paths;
    - VM types and prices from the public inventory (`name`,
      `cost_per_hour`, `available`);
    - credits for the balance;
    - an SSH key registered first, then a VM workload registered with it, a
      VM image and a sudo password, then deployed;
    - `public_ip` and `ssh_port` from the workload's state; the user is
      always `ubuntu`;
    - deletion by `DELETE`.

    None was run live. Unverified: whether any VM image ships Docker and the
    NVIDIA Container Toolkit, and the exact JSON on a real account.
  - *One SSH key per VM, made on the miner's machine.* The private key and
    the sudo password are written owner-only under the campaign root
    (`compute/vm-keys/<ownership name>/`) and removed at teardown. The key is
    deleted at Targon too. Host keys are accepted on first use into a
    per-VM known-hosts file.
  - *The worker runs on the VM's loopback and is reached through SSH.* Over
    SSH, a fixed script starts the pinned worker once with Docker
    (`--gpus all`, `-p 127.0.0.1:8000:8000`, the job's environment in an
    owner-only file). The controller reaches it through an SSH local port
    forward, so the token and public inputs travel inside SSH, and no port is
    opened on the VM. The backend record says `job_transport: ssh-tunnel`.
  - *A VM image without Docker or the NVIDIA Container Toolkit is refused
    by name.* The script exits 90 or 91, the trial fails as infrastructure,
    and the VM is deleted. Nothing is installed on the miner's behalf; the
    miner chooses an image that has both, and setup checks the name is one
    their account may start.
  - *No idempotency key, no end time, no charge.* Targon documents none for
    a VM, so:
    - a lost register answer is ambiguous, and is reconciled by the
      workload's name, the ownership tag;
    - a refused deploy deletes the registration;
    - the trial's teardown is the VM's only end;
    - the charge stays unresolved, never rate x time. The miner's Targon
      console is the record.
- **Slice 4 (the miner's own GPU machine over SSH, OWNER-MINER-COMPUTE-LINK-ONLY-01):**
  `carbon/compute/remote_machine.py` (the SSH client, the fixed start and
  remove scripts, and streaming the worker image),
  `carbon/compute/remote_runner.py` (the carrier-compatible runner),
  `BatteryPractice(remote=...)` and the `REMOTE_GPU` backend record;
  `tests/cpu/test_remote_machine.py` and `test_remote_runner.py` cover it.
  Setup and launch offer it since the remote-setup slice below.
- **Recorded engineering decisions (slice 4, the remote machine, 2026-10-02):**
  - *The miner's own SSH decides how the machine is reached.* Carbon passes
    no `-i`, no `IdentitiesOnly`, no known-hosts file of its own and no
    `accept-new`, so the miner's agent, `~/.ssh/config` and known hosts apply
    and their key never leaves their machine. `BatchMode=yes`, so nothing
    prompts. The destination is `[user@]host` or an ssh-config alias and can
    never be read as an option; the port is passed only when named, so an
    alias keeps its own.
  - *One container per trial, by image ID.* A fixed script, run with
    `bash -s`, starts `carbon-job-<24 hex from the operation>` with `--rm`,
    `--gpus all` and `-p 127.0.0.1::8000`; the job's environment goes through
    an owner-only `mktemp` file deleted at once, and `docker port` tells
    Carbon the host port. An SSH local forward reaches it, so the token and
    inputs travel inside SSH. The job server ends itself after the job's
    lifetime and `--rm` removes the container, even if the controller never
    returns.
  - *Refused by code, nothing installed.* No Docker 90, no NVIDIA Container
    Toolkit 91, Docker not usable without sudo 92 (Carbon never holds a sudo
    password), the worker image not present by ID 93.
  - *The container is Carbon's to remove; the machine is not.* Removal runs
    whether the job succeeded or not, only for a name matching
    `^carbon-job-[0-9a-f]{24}$`, and the record says whether the machine
    confirmed it.
  - *The worker is streamed, not pulled.* `docker save <image id> | ssh
    <destination> docker load`, then the image ID is checked on the machine.
- **Slice 4, remote setup (any setup the miner runs, OWNER-MINER-COMPUTE-LINK-ONLY-01
  amendment):**
  - `carbon/compute/remote_transport.py`: the one interface and record, and
    the `ssh-docker` and `ssh-container` transports.
  - `carbon/compute/remote_container.py`: the container's fixed scripts.
  - `carbon/compute/remote_route.py`: the Challenge-neutral `remote_gpu`
    scope and runner.
  - `ChallengeCampaign.remote_worker` and `remote_runner`.
  - `scripts/dev/push_worker_image.sh`, and
    `docs/development/MINER_REMOTE_SETUP.md` (the wiring guide).
  - Setup's "Your own remote machine or container" choice, its live check
    and "Send your worker" step; the profile's `remote_machine`; the
    `remote_gpu` runtime scope at both campaign doors; and the Control
    Center.

  `tests/cpu/test_remote_transport.py`, `test_remote_route.py`,
  `test_push_worker_image.py`, the setup tests and the setup browser smoke
  cover it.
- **Recorded engineering decisions (slice 4, remote setup, 2026-10-02):**
  - *Container-only rentals are supported (owner).* The miner chooses any
    setup; Carbon wires it (LINKONLY-D5).
  - *A container reports its build identity* (LINKONLY-D6). The pinned worker
    image already carries `/opt/carbon/worker-image-build.json`, so the image
    build is unchanged. What changed inside the image is only the job server
    in its wheel:
    - it can bind the container's loopback (`CARBON_JOB_BIND`);
    - it can take a free port and write it to a file (`CARBON_JOB_PORT=0`,
      `CARBON_JOB_PORT_FILE`);
    - it keeps its scratch under a directory Carbon names (`CARBON_JOB_ROOT`).
  - *A container job is a process Carbon can find again.* One trial runs as:
    1. `mkdir -m 700 /tmp/carbon-job-<24 hex>`;
    2. the environment through an owner-only file the starting shell deletes;
    3. `setsid` so the server outlives the SSH session, its pid recorded;
    4. its port read back from the file.

    Cleanup stops only a process group whose environment names that
    directory, then removes the directory. The record says whether the
    container confirmed both.
  - *The endpoint transport is not built* (LINKONLY-D7). It is refused by
    name, and its design waits for the owner's security acceptance.
  - *The address is the profile's, the transport is the campaign's*
    (LINKONLY-D9). A pod's address may change when the miner restarts it, so
    the destination stays in the profile. A frozen campaign declares
    `remote_gpu` with the transport and the pinned GPU worker. A profile whose
    transport differs from the campaign's is refused before anything is
    reached.
  - *The live check runs nothing billable.* It uses only the miner's own SSH:
    - reach;
    - for `ssh-docker`, Docker, the toolkit and Docker without sudo, then the
      image by ID;
    - for `ssh-container`, the worker runtime and its build identity.

    It starts no job, opens no forward and installs nothing.
  - *Sending the worker is its own step, with consent.* For `ssh-docker`
    only, the miner agrees to send the pinned worker by image ID to the
    destination they named. The request must name both, so a page that
    changed either sends nothing. The transfer runs in the request and may
    take minutes.
  - *The image push is the miner's.* `push_worker_image.sh` uses the miner's
    own `docker login`, pushes only the pinned worker it built (or a manifest
    the miner names), and prints `repository@sha256` (LINKONLY-D8).
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
    MIRA-ADMISSION-01 (#475) holds the same finding:
    `docs/development/mira/CAPABILITY_REPORT.md` plans an artifact handoff and
    keeps live Mira BLOCKED. OWNER-GRAPHITE-01 (2026-10-02) then chose to
    build Carbon's own agent (Graphite) instead; the Mira adapter keeps
    refusing every call until a vendor contract exists.
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
  - *An intake is https, or loopback.* The intake binds loopback unless it
    names the owner's exposure record, OWNER-INTAKE-EXPOSURE-01 (recorded
    2026-10-02), and terminates TLS. This slice reaches an exposed intake;
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
  - Compute: verify the worker images and, for a GPU, the device. No
    provider balance or inventory is read (OWNER-MINER-COMPUTE-LINK-ONLY-01).
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

### 4. Remote GPU: the miner's own machine, connected over SSH

OWNER-MINER-COMPUTE-LINK-ONLY-01 (2026-10-02) replaced this slice's first
form, a GPU rented on Lium, Targon or RunPod with the miner's provider key.
Carbon rents no compute: the miner starts and stops their own machine, on any
provider, and Carbon only connects to it.

- **The miner's own GPU machine over SSH,** with Docker and the NVIDIA
  Container Toolkit (LINKONLY-D4). The miner's own SSH agent, configuration
  and known hosts reach it; no key of theirs reaches Carbon or the machine.
- **The pinned worker is streamed and checked by image ID.** Each trial runs
  one job container from it and removes that container; Carbon never starts,
  stops or bills the machine.
- **Keep the trust boundary.**
  - The controller, keys and signing stay on the miner's machine.
  - A remote machine receives the pinned worker and one job's public inputs
    only.
- **Container-only rentals** (for example RunPod or Lium pods, with no Docker
  daemon) are supported (owner, 2026-10-02: "miners should be able to use
  whatever they want to run their setup"). The miner starts a container from
  the pinned worker image. Carbon runs one job process per trial in it over
  SSH, checks the worker's build identity, and stops and cleans that process;
  it never touches the container's lifecycle.
- **Remote setup.** The miner chooses a transport (`ssh-docker`,
  `ssh-container`; `endpoint` is designed, not built). Setup checks it live
  with the miner's own SSH and runs nothing billable. Tooling covers the
  rest: a "send your worker" step, an image push to the miner's own registry,
  and a provider-neutral wiring guide with per-provider notes.
- **Acceptance:** one real battery practice on a GPU machine or container
  the miner runs, with its job container or process cleaned up.

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
and submit. Carbon rents nothing, so there is no Carbon-made resource to tear
down or charge to reconcile; a remote machine is the miner's to stop. This
confirms, from a different machine, the three provisions slices 2 to 5
closed; it closes no Gap itself.

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

- **Targon:** answered 2026-10-02 (OWNER-C-MLP-03-ANSWERS-01): build the
  VM-and-SSH route, the pinned worker run with Docker inside a Targon VM on
  the miner's own account, reached over SSH (slice 4b). Superseded the same
  day by OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon rents no compute, and a
  Targon VM the miner runs is reached like any other machine of theirs.
- **Container-only rentals:** answered 2026-10-02 (OWNER-MINER-COMPUTE-LINK-ONLY-01,
  amendment): "miners should be able to use whatever they want to run their
  setup. We are just facilitating and providing wiring and tooling." Built
  as the `ssh-container` transport.
- **A job endpoint reached through a provider's public proxy (open):**
  whether Carbon may run a long-lived job server the miner starts once,
  holding a standing secret and reachable from the internet (LINKONLY-D7).
  That is a security acceptance; `endpoint` stays refused by name until the
  owner decides.

- **Which Mira?** Answered 2026-10-01: autoscience.io/Mira, not Mira
  Network's Flows (OWNER-BATTERY-CARRYOVER-01).
- **Mira's connection:** answered 2026-10-02 (OWNER-GRAPHITE-01, recorded
  for this ticket by OWNER-C-MLP-03-ANSWERS-01). Carbon builds Graphite
  instead of buying Mira, and the Mira adapter refuses every call until a
  vendor contract exists (`docs/development/mira/CAPABILITY_REPORT.md`,
  MIRA-ADMISSION-01, #475). A paid Mira comparison needs its own owner
  decision.
