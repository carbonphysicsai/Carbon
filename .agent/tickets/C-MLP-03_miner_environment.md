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

**Status:** slices 1 and 2 implemented (engineering evidence only). Slice 2's
live acceptance (completions with miner-held Chutes and Engy keys, and a
battery autonomous launch with each) is pending the miner's keys.
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

- **Which Mira?** Answered 2026-10-01: autoscience.io/Mira, not Mira
  Network's Flows (OWNER-BATTERY-CARRYOVER-01).
