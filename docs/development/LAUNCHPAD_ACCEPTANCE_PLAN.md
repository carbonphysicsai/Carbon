# Launchpad acceptance plan (LAUNCHPAD-ACCEPT-01)

**Status:** SPECIFIED. This is a plan: nothing in it has run, spent, rented or
installed anything. Each cell below is UNRUN until its evidence file exists.

**Authority.**
- The owner wants to be "super confident" in the miner Launchpad before
  launch (2026-10-07, through the Test Lead).
- The owner, 2026-10-07, through the Test Lead: "I want our testing running
  through launchpad as soon as it can like it will on mainnet."
- Standing rules this plan keeps:
  - OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon never rents, stops or bills a
    miner's compute;
  - OWNER-MINER-SETUP-AGENT-FIRST-01: keys reach Carbon by file path only,
    and starting the signer and signing stay human;
  - OWNER-COMMITMENT-POSTER-01 D1 to D10;
  - OWNER-LAUNCHPAD-PROD-02 (the live smoke test);
  - OWNER-GRAPHITE-05: grants are proposed, then the owner approves them.

**Baseline.** An audit of origin/main `37389ea46` (2026-10-07) found:
- the fresh-machine run of `install_miner.sh` (C-MLP-04's acceptance) has never
  happened;
- local GPU, remote SSH (every provider card), Hermes and the Chutes and Engy
  keys are tested only with fakes;
- the Claude Code, Codex and Hermes MCP snippets are marked UNVERIFIED
  (`environment_setup.py`, `mcp_connect`);
- the commitment poster (#717, `carbon/chain/commitment_poster.py`) is called
  by nothing in the Launchpad or the MCP door;
- `published_endpoints.json` lists no endpoint, so no real submission has
  ever got a validator verdict through the Launchpad;
- the OWNER-LAUNCHPAD-PROD-02 live smoke test has no recorded result;
- `tests/service/test_launchpad_production_journey.py` uses fixtures
  throughout.

**What "accepted" means here.** A cell passes only on real infrastructure:
- a real machine, real keys, the real testnet 567 chain and a real validator;
- no fixture, fake transport or stand-in counts.

Passing grants engineering evidence only. Nothing here is
SCIENTIFICALLY_QUALIFIED, SECURITY_QUALIFIED or PRODUCTION_QUALIFIED. Every
score is DEVELOPMENT and labelled device class CPU (OWNER-REHEARSAL-CPU-CLASS-01).

---

## 1. Order of work

The order comes from the owner's directive: test traffic moves onto the
Launchpad as soon as each path works, mainnet-style. The option matrix (§3)
runs alongside and never blocks stage A.

### Stage A: the critical path (traffic moves here first)

| Step | What | Ticket | Unblocks |
|---|---|---|---|
| A1 | The commitment op in the Launchpad and MCP, and commit-before-submit | LAUNCHPAD-ACCEPT-02 | v2 deployments with `require_commitment: true` (rehearsal 3a's valV2) |
| A2 | The receiver-hotkey check at submit | LAUNCHPAD-ACCEPT-03 | Submitting to a named validator and only that validator |
| A3 | A submit target for the AX42 testnet validator through the tunnel (`http://127.0.0.1:18467`), with its pinned receiver | LAUNCHPAD-ACCEPT-04 | The real submit path |
| A4 | Status and verdict readback on both doors | LAUNCHPAD-ACCEPT-04 | Graphite and miners reading verdicts |
| A5 | The first real submit-to-verdict through the Launchpad (§5) | none: an evidence run | The switch of traffic (A6) |
| A6 | Switch test traffic (§6) | none | Mainnet-like testing |

- A1 and A2 are independent and build in parallel.
- A3 depends on A2, because the tunnel target is only safe with a pinned
  receiver.
- A4 is mostly verification. The battery intake client already polls to a
  verdict (`carbon/battery/campaign.py`, `submit_through_intake`), so A4
  ships with A3.
- Each ticket is one PR, sent to PR Head.
- When a path becomes usable by Graphite, the Test Lead is told once, so the
  executor can switch.

### Stage B: the fresh-machine install (§4)

This needs no code and costs nothing. It runs as soon as the owner sets aside
a clean WSL distro. It can run before stage A finishes, and its submit step
(step 10) waits for A5.

### Stage C: the option matrix (§3)

Runs in parallel with A and B. The zero-cost cells come first: local CPU,
local GPU, ssh-docker to the owner's own workstation, the MCP clients. Paid
rentals wait for the grant (§7).

### Stage D: research_share_shortfall (LAUNCHPAD-ACCEPT-05)

Off the critical path. A FULL Graphite launch whose research share cannot pay
for one model call is refused today, but only inside the driver, after
launch. LAUNCHPAD-ACCEPT-05 moves that check to the launch door and the cost
calculator.

---

## 2. Conventions for every cell

- **Evidence folder.** One folder for the whole acceptance:
  `docs/development/evidence/launchpad-acceptance-<YYYY-MM-DD>/`.
  - `cells/<cell-id>.json` per cell, with schema
    `carbon.launchpad.acceptance-cell.v1` and these fields:
    `cell`, `date`, `revision`, `machine_kind`, `result`
    (`PASS`/`FAIL`/`BLOCKED`), `refusal_code`, `evidence` (digests and
    closed codes), `within_cap` (Boolean), `actor`.
  - `FINDINGS.md`, the register of every defect a cell or Graphite hits:
    the defect, its cell, its closed code, and the slice or PR that fixes it.
  - The fresh-machine run keeps its own folder,
    `docs/development/evidence/fresh-miner-<date>/` (FRESH_MINER_JOURNEY.md),
    linked from the matrix.
- **What never goes in evidence** (public repository):
  - keys, passwords, tokens or account identifiers;
  - balances, and spend totals (record `within_cap` only);
  - remote machine addresses;
  - profile contents (record the profile digest);
  - hidden material, or any per-case or hidden score.
- **Keys** are passed by owner-only file path only (`model_key_file`, the
  signer's wallet). Nothing prints a key; an agent never opens a key file or
  password file.
- **Actors.**
  - **Owner**: keys, accounts, wallet, signer start, TTY confirmations,
    chain transactions, starting and stopping rented machines, anything on
    the AX42.
  - **Agent**: this session or the Graphite Test executor. It drives the
    Launchpad through the browser or MCP and writes evidence.
- **Validation of code changes** runs through `./scripts/dev/canonical.sh`
  on Windows; native output is a diagnostic only.
- **Negative paths are cells too.** Every flow has at least one refusal cell
  with its exact closed code and its `next_step`.

---

## 3. The acceptance matrix

### 3.1 How the cells cover the options

A full cross product (14 flows × 9 compute × 7 inference × 4 agents) has
about 3,500 cells, most of which test nothing new. The matrix is a covering
design instead:
- **The base configuration** runs every flow end to end: this machine's
  CPU, `engy-chat`, and the Graphite miner edition (§3.2).
- **Each other option** reruns only the flows it changes (§3.3 to §3.5):
  - compute changes the compute check, send-worker, practice and cleanup;
  - inference changes the quote, the check, launch validation and metered
    spend;
  - the agent changes connection and who drives launch, practice, freeze,
    commit and submit.
- **Flows no option changes** run once on the base configuration and once
  through MCP: commitment, submit, status, freeze, and the refusals. MCP
  parity is part of the test.

### 3.2 Flows on the base configuration

| Cell | Flow | Exact real test | Pass means | Evidence | Cost | Acts |
|---|---|---|---|---|---|---|
| F01 | Install | §4 step 1: `install_miner.sh` on the clean distro, then again with `--gpu` | Exit 0; the worker, analysis and GPU worker images are built and recorded; `environment_setup after-install` accepts them; the Control Center starts | Installer output (redacted of the token), image ids, revision | none | owner runs; agent records |
| F02 | Update | Install at `--ref <main commit from 2 days before>`, then `install_miner.sh --update` | Checkout moves to main; images rebuilt; the old compute check and profile are moved to `runner-profile.stale.json`; setup re-checks; the Control Center refuses a running update | Both outputs, before and after revisions, the stale file's presence | none | owner |
| F03 | Setup: signer and registration | Start `carbon-miner-signer` for a registered rehearsal hotkey; the `carbon_setup_status` loop to `begin` | Status shows the signer reachable and the hotkey registered on 567, read from the chain at a recorded block; an unregistered hotkey gets `human_action_required` with the unsigned registration | Status JSON (public hotkey only), block | none | owner starts signer; agent reads |
| F04 | Setup: inference | `quote`, then `inference` with `consent.max_cost_nano` equal to the quote and the key as `model_key_file` | Model list read and one live completion through the real provider; a bare `consent: true` refused | Quote, check result code | ≤ USD 0.10 | owner writes key file; agent calls |
| F05 | Setup: compute and review | `compute` (CPU), then `review` | Images verified against the revision; the profile is written and loaded without a restart | Profile digest | none | agent |
| F06 | Research environment and cost calculator | `carbon_challenges_v1__describe` and the Challenges page for battery, then the launch form's hunt and ceiling estimate | Provisions and named Gaps match `carbon/challenge_kit/standard.py`; the estimate's per-call reservation matches the driver's at the same model (§LAUNCHPAD-ACCEPT-05) | Both readouts, the reservation figure | none | agent |
| F07 | Launch (Graphite BUILD, 1 epoch) | **This is the OWNER-LAUNCHPAD-PROD-02 live smoke.** One campaign, `deepseek-v4-flash` on Engy, CPU practice, provider cap about USD 0.50 | The campaign runs to COMPLETED or PAUSED with every model call journalled and settled; spend within the cap; all three first-turn calls run | Campaign id, final state, `within_cap` | ≤ USD 0.50 (already approved) | owner key; agent launches |
| F08 | Practice | Within F07, or `carbon_practice` on an `own-agent` campaign | A TRAIN trial returns feedback whose backend record says `CPU` | Feedback backend record | in F07 | agent |
| F09 | Freeze | `carbon_freeze_candidate` with a bounded reason | Manifest frozen; a freeze with no practice refused | Frozen strategy hash, contract digest | none | agent |
| F10 | Commitment | `carbon_commit` (LAUNCHPAD-ACCEPT-02) for the frozen candidate | The plan shows the digest equal to `daemon.commitment_digest(...)`; the agent gets `human_action_required: confirm_commitment`; after the owner types the digest's last 8 characters on the signer's TTY, the digest is read back from the chain at finality | Digest, block, extrinsic hash | testnet fee (measured 0 rao) | owner confirms on TTY; agent requests |
| F11 | Submit | `carbon_submit` to the tunnel target (§5) | 202 with a submission id; the intake's receiver equals the profile's pinned receiver | Submission id, intake URL (loopback), receiver | none | agent |
| F12 | Status and verdict | `carbon_observe` and `carbon_campaign_view` until a verdict | A sealed DEVELOPMENT outcome labelled CPU; no hidden score, case or seed on either door | The sealed outcome's public fields | none | agent |
| F13 | Refusals (real path) | Each, on the real chain and validator: submit before commit; a second commit in the same tempo; submit with a mismatched receiver; a second scored submission in the same tempo; a freeze with no practice; launch with an unregistered hotkey; MCP `key` as a value | Exactly `commitment_required`, `ALREADY_COMMITTED_THIS_TEMPO`, `intake_receiver_mismatch` (nothing signed or sent), `hotkey_window_used`, the no-practice refusal, `registration_required`, `key_must_be_a_file_on_this_door`; each with its `next_step` | One cell file per code | none | agent; owner for signer |
| F14 | Pause, resume, restart | Close the Control Center mid-campaign, restart, resume | The campaign PAUSES on close and resumes from its journal; a paid call is never resent blind | State transitions | in F07 | agent |

### 3.3 Compute options

`REMOTE_GUIDES` offers six remote cards: runpod, lium, targon, vast, lambda
and own-server.

Each remote cell runs these flows:
- the compute check with the miner's own SSH;
- send-worker (ssh-docker only);
- two practices;
- the cleanup check: no `carbon-job-*` container or `/tmp/carbon-job-*` left;
- refusal checks: an unreachable host, and a missing worker.

| Cell | Option | Real machine | Pass means | Evidence | Cost | Acts |
|---|---|---|---|---|---|---|
| C1 | `this-machine-cpu` | The fresh distro (§4) | F05 and F08 pass | Backend `CPU` | none | agent |
| C2 | `this-machine-gpu` | The owner's WSL host, RTX 3060, fresh distro with Docker Engine and the NVIDIA Container Toolkit | nvidia-smi detected; the host device record installed (or `prepare` named); two practices record `ISOLATED_CARRIER_GPU` with the device record and what JAX observed; the same recipe frozen and accepted by the validator (C-MLP-03 slice 3) | Device record digest, the two backend records, verdict | none | owner runs `prepare` if it needs root; agent |
| C3 | own-server, `ssh-docker` | The owner's main WSL distro reached over SSH from the fresh distro (a real SSH hop, Docker and the toolkit) | Check passes; worker sent by image id; two practices `REMOTE_GPU`, verified `image-id`; cleanup confirmed | Transport, verification kind, cleanup | none | owner enables sshd and the key; agent |
| C4 | runpod, `ssh-container` | 1 RunPod pod from the pinned GPU worker (`push_worker_image.sh`), full SSH on TCP 22 | Check passes on build identity; two practices `REMOTE_GPU`; `/tmp/carbon-job-*` removed | As C3, plus pod kind | grant tier 1 | owner starts and stops the pod; agent |
| C5 | vast, `ssh-docker` (VM instance) | 1 Vast.ai VM instance | As C3. It also settles MINER_REMOTE_SETUP's UNVERIFIED note on whether Vast VM images carry the NVIDIA toolkit | As C3 | grant tier 1 | owner; agent |
| C6 | vast, `ssh-container` (standard instance) | 1 Vast.ai standard instance in SSH launch mode | As C4 | As C4 | grant tier 2 | owner; agent |
| C7 | lambda, `ssh-docker` | 1 Lambda instance; user added to `docker` | As C3 | As C3 | grant tier 2 | owner; agent |
| C8 | lium, `ssh-container` | 1 Lium pod (subnet 51) with sshd in the image's own layer | As C4. It also settles the UNVERIFIED `ssh -L` restriction note | As C4 | grant tier 2 | owner; agent |
| C9 | targon, `ssh-docker` | 1 Targon VM (subnet 4) | As C3. It also settles the UNVERIFIED note on whether Targon VM images carry Docker and the toolkit | As C3 | grant tier 2 | owner; agent |

- Every remote cell's GPU practice is speed only, never evidence of the
  exam.
- After each cell the owner stops the machine.
- The cell records the provider and machine kind, never the address.

### 3.4 Inference options (`INFERENCE_ORDER`)

Each cell runs the quote, then the live check (model list and one
completion), with the key by `model_key_file`. It also runs one refusal:
a wrong consent amount.

| Cell | Provider | Extra | Cost | Acts |
|---|---|---|---|---|
| I1 | `engy-chat` (default) | Base config; F07 is its campaign | ≤ USD 0.10 check | owner key file; agent |
| I2 | `chutes` | Also one 1-epoch Graphite BUILD campaign, cap USD 0.50 (C-MLP-03 slice 2: "a battery launch validates with each") | ≤ USD 0.60 | owner key file; agent |
| I3 | `engy-anthropic` | Check only | ≤ USD 0.10 | owner; agent |
| I4 | `openai-responses` | Check only | ≤ USD 0.10 | owner; agent |
| I5 | `anthropic` | Check only | ≤ USD 0.10 | owner; agent |
| I6 | `openai-compatible-chat` | Check only, at Chutes' or Engy's Chat Completions URL with `declared_pricing` | ≤ USD 0.10 | owner; agent |
| I7 | `openai-compatible-responses` | Check only, at a Responses-compatible URL the owner holds a key for | ≤ USD 0.10 | owner; agent |

- **Pass** means the model list was read, one completion returned, the
  booking was settled within the quote, and the key never appears in any
  log, page, MCP result or evidence.
- **Blocked:** a provider whose key the owner does not hold is recorded
  BLOCKED with that reason. It is not a pass.

### 3.5 Agents

| Cell | Agent | Exact real test | Pass means | Evidence | Cost | Acts |
|---|---|---|---|---|---|---|
| A1 | Graphite miner edition (`carbon-graphite`) | F07, then a second BUILD campaign that freezes, commits and submits to the tunnel target | Practice, freeze, commit (requested by Graphite; confirmed by the owner on the TTY, D10), submit and verdict all happen in one campaign | Campaign journal digests, verdict | in F07, plus ≤ USD 0.50 | owner key and TTY; agent |
| A2 | Hermes | Install Hermes with its own installer; setup writes `~/.hermes/profiles/carbon` with consent; run `hermes -p carbon chat`, asking it to launch, practise, freeze, commit and submit | Hermes asks before each such tool; the campaign practises, freezes, commits and submits (C-MLP-03 slice 5); files written match setup's list | Hermes version, files list, verdict | ≤ USD 0.50 model | owner key, Hermes consent, TTY; agent |
| A3 | Claude Code over MCP | Paste setup's `claude mcp add ...` snippet verbatim; `claude mcp list`; then `carbon_setup_status` → `carbon_launch` (`own-agent`) → practice → freeze → commit → submit → observe | The snippet works unedited; tools listed; a long call (practice) completes inside the client's limit; `UNVERIFIED` removed from the snippet | Client version, tool count, verdict | owner's own Claude plan; no grant | owner runs client; agent records |
| A4 | Codex over MCP | Setup's `codex mcp add ...` snippet and its `config.toml` block (`tool_timeout_sec = 1800`), then the same loop as A3 | As A3 | As A3 | owner's own Codex plan; no grant | owner; agent |
| A5 | Hermes snippet path | The `~/.hermes/config.yaml` `mcp_servers` block by itself, and whether `hermes mcp add` takes a custom command | The block works; the `hermes mcp add` question settled either way and the snippet updated | Version, outcome | none | owner; agent |

- **On a FAIL, a snippet is fixed or marked unsupported.** It is never left
  UNVERIFIED after its cell runs.
- **A2 to A4 drive the miner's own agent through the MCP door,** so they
  also check door parity. Each refusal returns the same closed code and
  `next_step` as the browser.

### 3.6 The completion predicate

The Launchpad is accepted for launch when all of these hold:
1. every flow cell F01 to F14 is PASS on the base configuration;
2. C1, C2, C3, C4 and C5 are PASS (tier 1);
3. I1 and I2 are PASS, and I3 to I7 are PASS or BLOCKED-by-key with the owner
   aware;
4. A1 to A4 are PASS;
5. no `UNVERIFIED` marker is left in `mcp_connect`;
6. every `FINDINGS.md` entry is fixed or explicitly accepted by the owner.
7. the release check (§3.7) passes: every option offered on either door is
   PASS, or hidden, or labelled "untested".

Tier-2 compute cells (C6 to C9) are launch-desirable but not launch-blocking.
They verify per-provider notes. The owner funded them
(OWNER-LAUNCHPAD-ACCEPTANCE-GRANT-01); each one runs where the owner holds
that provider's account.

### 3.7 Release check: nothing untested is offered as tested

The owner set this launch rule on 2026-10-07, through the Test Lead. At
launch, the Launchpad hides any option whose matrix cell is not PASS, or
labels it "untested". That covers:
- every compute option and remote provider card (`REMOTE_GUIDES`);
- every inference provider (`INFERENCE_ORDER`);
- every agent and MCP client snippet.

- **The check runs before every release.** It compares the options the
  Launchpad offers on both doors (setup `choices()`, `REMOTE_GUIDES`,
  `INFERENCE_ORDER`, the agent choices, `mcp_connect`'s snippets) with the
  latest cell results under `docs/development/evidence/launchpad-acceptance-*/`.
- **An option with no PASS cell** at the release's revision, or an earlier
  revision the cell names, must be:
  - hidden, or
  - shown with the "untested" label on both doors, carried as a closed field
    the MCP door returns too. Copy alone does not count.
- **A BLOCKED or FAIL cell is never shown as tested.** The release is refused
  until the option is labelled.
- **Building the check** is a slice of LAUNCHPAD-ACCEPT-01. The default it
  starts from is "untested" for every option. That is truthful for today's
  main, and passes flip options to tested one cell at a time.

### 3.8 Construction levels (LAUNCHPAD-LEVELS-01)

No level counts as passed until it passes real runs through the Launchpad
(OWNER-LADDER-THROUGH-LAUNCHPAD-01): freeze, commit, submit and verdict on
the testnet development-ladder deployment (`battery-dev-ladder`,
VALIDATOR-25), from `carbon-rehearsal-minerC` only, never minerA or minerB.
Each cell runs on both doors (browser and MCP) with the same closed codes.
Every cell is BLOCKED until VALIDATOR-25 slice 2 publishes `served_contracts`
and the ladder deployment runs on valV2.

| Cell | Level | Exact real test | Pass means | Evidence | Cost | Acts |
|---|---|---|---|---|---|---|
| L1 | 1 (and arm `signed` on the attack panel only) | `carbon_launch` `agent: none`, `construction_level: 1`; practise a recipe with `loss_expressions`; freeze; commit; submit to the ladder intake | The manifest and the frozen record name `battery-l1-loss-expressions-v1` and its digest; the commitment reads back as `{challenge, variant digest, strategy hash}`; the ladder admits and returns a DEVELOPMENT verdict; the same candidate sent to the main intake is refused `level_not_served_by_target` before signing | Variant digest, commitment digest and block, submission id, verdict's public fields, the refusal cell | testnet fee | owner TTY; agent |
| L2 | 2 | As L1 with `construction_level: 2` and `muon_spectral` or `pool_selection` | As L1 for `battery-l2-v2`; an out-of-bounds widened value refused `level_strategy_refused` at practice | As L1 | testnet fee | owner TTY; agent |
| L3 | 3 | As L1 with `construction_level: 3` and a `numerics` menu choice | As L1 for `battery-l3-numerics-v1` | As L1 | testnet fee | owner TTY; agent |
| L4 | 4 (graph only) | Lower a recipe with `python -m carbon.level4.tooling lower`, set `composition_graphs` to its digest, practise, freeze with `level4_directory` | Freeze verifies the submission (allowlist, Challenge, interface, batch, the variant's size bound) and keeps its envelope byte for byte; commit binds the L4 variant digest; submit is refused `level4_envelope_transport_unavailable` (and the ladder answers `ladder_level_4_not_open`) until the validator's upload slot and Level 4 Phase 3 open it | Submission digest, envelope digest, the refusal cells | none until opened | agent; owner TTY |

- **Refusal cells, each level:** `level_not_registered` (an unregistered
  arm), `level_not_served_by_target` (the main intake, which lists level 0
  only), and the ladder's own admission codes (`ladder_hotkey_not_listed`,
  `ladder_variant_not_accepted`, `ladder_level_not_accepted`), each with its
  `next_step`.
- **Practice is the Level 0 base.** A level campaign's practice trains the
  recipe less its widened fields and says so
  (`construction_level.widened_trained: false`); only the ladder's rebuild
  runs the level. A cell never reads a practice score as the level's.

---

## 4. The fresh-machine install run (C-MLP-04's acceptance)

**The machine.** A new WSL2 distro on the owner's PC, `carbon-fresh` (Ubuntu
24.04, imported clean). It counts as clean only if:
- **Its Docker is its own.** Docker Desktop's WSL integration is turned
  *off* for this distro, and Docker Engine and the NVIDIA Container Toolkit
  are installed inside it. With the integration on, it would share the main
  distro's images and fail "nothing Carbon-related installed".
- **It has no Carbon state:** no checkout, no `~/.carbon`, no
  `~/.hermes/profiles/carbon`, no images, no wallet. Checked and recorded
  before step 1.
- **There is disk for it.** At least 29 GiB free for the GPU worker, plus
  margin. C: holds both vhdx files: check `Get-PSDrive C` before the build,
  never only `df` (see the 2026-10-03 disk incident).

A clean cloud VM is the alternative. It would need its own grant line and
cannot run C2.

**The run** follows FRESH_MINER_JOURNEY.md steps 1 to 10 exactly:

| Step | Who | Recorded |
|---|---|---|
| 0. Clean-state check, disk check | agent proposes; owner runs | Distro release, GPU, free disk, empty-state listing |
| 1. `git clone ... && install_miner.sh --gpu` (then F02's `--update`) | owner | Installer output (token line removed) |
| 2. Signer, for a registered rehearsal hotkey | owner. Only the hotkey file and `coldkeypub.txt` are copied into the distro, never the coldkey | Public hotkey |
| 3. Control Center, registration confirmed | owner opens it; agent may drive through MCP | Status block |
| 4. Inference (Engy, then Chutes) | owner key file; agent | Quote, check result |
| 5. Compute: C1, then C2 | agent; owner for `prepare` | Images, device record digest |
| 6. Agent: Graphite, then Hermes | owner consent for Hermes | Versions, files written |
| 7. Review, naming the tunnel target as its own intake with its pinned receiver (§5) | agent | Profile digest; intake "own"; receiver |
| 8. Launch battery | agent | Campaign id |
| 9. Two GPU practices | agent | Backend records |
| 10. Freeze, commit, submit, verdict | agent; owner on the TTY | Submission id, verdict, intake URL |

- **Evidence** goes to `docs/development/evidence/fresh-miner-<date>/README.md`,
  with exactly FRESH_MINER_JOURNEY.md's Record fields, plus the F02 update
  output.
- **Step 10 waits for A5.** Steps 1 to 9 do not wait.
- **Afterwards** the distro is kept, so later `--update` runs (F02) use it.
  Removing it is the owner's choice.

---

## 5. The real submit-to-verdict path (testnet, rehearsal 3a)

**Target.** Rehearsal 3a's valV2 validator on the AX42 (the operator's
`REHEARSAL_3A_BATTERY.md`, in the shared operator folder, not in this
repository).
- Its door binds to the AX42's loopback, `127.0.0.1:8467`.
- The owner's PC reaches it through the tunnel loop, with
  `-L 18467:127.0.0.1:8467`.
- Its intake's receiver is valV2's public hotkey
  `5CtxhYH5Qqv8EcqC8ffGsUcyaQe4ojNRtsQqTbWyhbu1CMHf`.
- Its deployment sets `require_commitment: true`.

**What this plan never does:**
- touch the AX42, its accounts, its hidden material, its VM credentials, the
  tunnel account's key or `authorized_keys`;
- run any step of the rehearsal sheet;
- run any chain transaction except the miner's own commitment, and that only
  as a request: the owner signs it.

**Entry conditions.** All are the owner's or the Test Lead's, and are read,
never performed:
1. rehearsal 3a steps 1 to 4 done: `status` reports `healthy: true`;
2. step 8 done: valV2's permit reads `'permit': True`, and minerA and minerB
   are registered;
3. step 3's `answer_key sync` shows a live window `HELD`;
4. the tunnel loop is up with `-L 18467`;
5. LAUNCHPAD-ACCEPT-02, -03 and -04 are merged.

**The run (A5).**
1. The owner starts minerA's signer with `--receiver` set to valV2
   (rehearsal step 9).
2. Setup Review names the intake `http://127.0.0.1:18467` for battery, with
   receiver valV2 pinned (LAUNCHPAD-ACCEPT-03 and -04). The preflight reads
   the intake's public facts: network testnet, netuid 567, battery, receiver
   valV2.
3. Launch an `own-agent` battery campaign, driven by MCP from this session,
   or by the Graphite executor once it switches.
4. Practise once (CPU), then freeze.
5. `carbon_commit`. The owner types the last 8 characters on minerA's signer
   TTY. The digest is read back at finality.
6. `carbon_submit`, which returns 202 and a submission id.
7. `carbon_observe` until the verdict.

**Pass.**
- A sealed DEVELOPMENT outcome, device class CPU. No hidden score, case,
  seed or reference on any door.
- The commitment's block precedes the submission's receipt block (D6).
- valV2's journal names the same submission id. The owner reads that; the
  agent does not.

**One submission, two uses.** Rehearsal 3a step 5's CPU rebuild timing needs
exactly one baseline submission from minerA, with the daemon stopped. A5's
first submission can be that one, if the Test Lead and the owner sequence
it. That saves one tempo and one TTY confirmation.

**Then the negative cells on this path** (F13): submit before commit;
mismatched receiver; a second submission in the same tempo; a second
commitment in the same tempo.

**Throughput limits** (D4 and rule v2):
- one commitment and one scored submission per hotkey per tempo (360
  blocks, about 72 min);
- every commitment needs the owner at that hotkey's signer TTY;
- the rehearsal's load ceiling is 3 miner hotkeys × 20 scored submissions a
  day.

The traffic switch (§6) is planned against those limits.

---

## 6. Moving test traffic onto the Launchpad

The development door (`carbon/battery/dev_submit.py`, port 18468) stays for
candidates, tuning and attack exploration. Anything adopted runs through the
Launchpad: freeze → commit → submit → status, as on mainnet.

| Traffic | Moves when | Through | Notes |
|---|---|---|---|
| Rehearsal 3a battery submissions | A5 passes | MCP or browser, minerA and minerB | Replaces script submissions |
| Rehearsal 3b | Its Challenge's intake exists and is reachable like 3a's | The same path | The plan gains a 3b target row when the Test Lead names it |
| Graphite Level 1+ adopted candidates | A5 passes, then the Test Lead switches the executor | The Graphite executor as an `own-agent` MCP client of a Launchpad install | Graphite is the first heavy user: every gap it hits goes into `FINDINGS.md` and becomes a Launchpad fix |
| Attack runs: their adopted or final submissions | As Graphite | The same path | Exploration stays on 18468 |

- **The Test Lead is told once per path** that becomes usable by Graphite.
- **The executor's Launchpad install** is its own state directory under its
  own account, never the owner's wallet directory. Its hotkey's signer runs
  in the owner's terminal.

---

## 7. Grant

**Approved in full, USD 13.55:** OWNER-LAUNCHPAD-ACCEPTANCE-GRANT-01,
2026-10-07. Tier 2 lines run only where the owner holds the account. Nothing
spends until that record is on main. The ceilings bind per OWNER-GRAPHITE-05.

**Rates.** Rate ceilings are taken from published rates read on 2026-10-07,
rounded up:
- RunPod: community RTX 3090 about USD 0.22/h. The repo's A40 SECURE
  ceiling is USD 0.4927/h (OWNER-A40-ACCEPTANCE-GRANT-01).
- Vast.ai: RTX 3090 about USD 0.13/h.
- Lambda: A10 about USD 0.86 to 1.29/h.
- Lium and Targon: UNVERIFIED. Read them before renting.

A machine above its ceiling is not rented.

| Line | Platform, transport | Machines | Ceiling | Deadline | Worst case |
|---|---|---|---|---|---|
| T1-a | RunPod pod, ssh-container (C4) | 1 | USD 0.50/h | 2 h | USD 1.00 |
| T1-b | Vast.ai VM, ssh-docker (C5) | 1 | USD 0.40/h | 2 h | USD 0.80 |
| T1-r | One replacement each for T1-a and T1-b | ≤ 2 | as above | 2 h | USD 1.80 |
| T2-a | Vast.ai standard, ssh-container (C6) | 1 | USD 0.40/h | 2 h | USD 0.80 |
| T2-b | Lambda, ssh-docker (C7) | 1 | USD 1.50/h | 2 h | USD 3.00 |
| T2-c | Lium, ssh-container (C8) | 1 | USD 0.60/h | 2 h | USD 1.20 |
| T2-d | Targon VM, ssh-docker (C9) | 1 | USD 1.00/h | 2 h | USD 2.00 |
| CL | Cleanup allowance | | | | USD 0.25 |
| M1 | Inference checks I1 to I7 | 7 | USD 0.10 each | | USD 0.70 |
| M2 | Chutes campaign (I2) | 1 | | 1 epoch | USD 0.50 |
| M3 | Graphite commit-and-submit campaign (A1) | 1 | | 1 epoch | USD 0.50 |
| M4 | Hermes campaign (A2) | 1 | | 1 epoch | USD 0.50 |
| M5 | Retry allowance (one failed campaign) | | | | USD 0.50 |

| Total | Lines | Cap |
|---|---|---|
| **Tier 1, launch-blocking** | T1-a, T1-b, T1-r, CL, M1 to M5 | **USD 6.55** |
| Tier 2, provider notes | T2-a to T2-d | USD 7.00 |
| **Full grant** | all | **USD 13.55** |

**Not in the grant:**
- the approved PROD-02 smoke (F07, about USD 0.50);
- Claude Code and Codex: the owner's own plans;
- testnet commitment fees: measured 0 rao, test TAO.

**Accounts.** Vast.ai, Lambda, Lium and Targon each need an account the
owner holds. An agent cannot create one.

**Who acts.** The owner starts and stops every rented machine, acting as the
miner, and gives setup the SSH destination. Carbon's code never rents, and
that keeps OWNER-MINER-COMPUTE-LINK-ONLY-01. For RunPod, the operator layer
(`operator_compute`) on the operator's own account may start the pod under
this grant instead, as the A40 run did. The Launchpad still reaches it only
by SSH.

---

## 8. Owner decisions and actions this plan needs

**Decisions, answered 2026-10-07** ("grant full, AX42 stays private, approve
all"):
1. **The grant:** full, USD 13.55 (OWNER-LAUNCHPAD-ACCEPTANCE-GRANT-01).
2. **The AX42 door stays private (OWNER-AX42-DOOR-PRIVATE-01).**
   - `published_endpoints.json` stays empty.
   - The tunnel target serves the owner's own rehearsal miners only.
   - A future public testnet door goes on a separate, validator-only host,
     after a security review. The Test Lead brings it to the owner after 3a.

**Actions:**
- create the `carbon-fresh` distro, and turn off its Docker Desktop
  integration;
- copy one rehearsal hotkey into it;
- hold key files for each provider (I1 to I7);
- start the signers and confirm every commitment on their TTYs;
- start and stop every rented machine;
- run the rehearsal 3a steps.

---

## 9. Risks

- **The first real commitment on testnet 567 is untested.** The fee pin is
  0 rao, from localnet plus a read-only testnet estimate. If testnet charges
  a fee, the signer refuses `FEE_OVER_CEILING`. Recording a new ceiling is
  a D3 measurement record, not an agent's choice.
- **The tempo limits are real.** One commitment and one submission per
  hotkey per tempo makes every retry cost about 72 minutes. The negative
  cells are scheduled after the positive one.
- **The disk on C:.** A second distro with the GPU worker adds about 29 GiB
  to a drive that has run out before.
- **Shared-uid interference.** The executor's Launchpad and the owner's must
  not share a state directory or runner database. One lock holder per
  database.
