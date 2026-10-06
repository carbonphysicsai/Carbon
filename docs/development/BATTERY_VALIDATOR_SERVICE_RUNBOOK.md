# Battery validator service: runbook

**Authority.** OWNER-LAUNCHPAD-PROD-01 (2026-10-03): a real submission
endpoint and validation service on the validator-pinned images. Engineering
decisions: LP-PROD-G (`.agent/decisions/2026-10-03-LP-PROD-G.md`). Exposure:
OWNER-INTAKE-EXPOSURE-01 (2026-10-02), testnet 567 only.

**Status.** Implemented and tested on loopback with throwaway deployments
(`tests/cpu/test_battery_validator_service.py`,
`tests/cpu/test_battery_intake_service_e2e.py`). It has **not** been started
against the operator's deployment, and no host is exposed. The intake is not
SECURITY_QUALIFIED: tests hold the gates, they are not a security audit
(AGENTS.md §13). Scores are DEVELOPMENT evidence. Nothing here sets weights
(OD-4b) or writes to a chain.

This document never contains a secret, an account identifier or a host's
private path. Keys and files are named by role; the owner's private host
brief names each instance.

## 1. What runs

One deployment, two processes, one writer lock (`deployment.writer`):

| Process | Command | Does |
|---|---|---|
| intake | `python -m carbon.battery.intake serve --config <intake.json>` | The submission endpoint (OD-7(b)). Authenticates each signed `battery_submit` (`btauth/1`, NET-2), records it in its inbox, answers `202` with the submission id, and its worker admits and advances it through the daemon. Answers `battery_status` to the submitting hotkey only. Holds `<inbox>.serve.lock` while it runs. |
| validator daemon | `python -m carbon.battery.operate run --config <deployment.json> --every 60 --heartbeat <service dir>/daemon-heartbeat.json` | One `run` per minute: advances whatever is queued, including submissions that reached the deployment another way, and opens finalist comparisons. Keeps an owner-only heartbeat (pid, passes, how the last pass ended) and holds its `.lock` while it runs. |

Both log one JSON line per event (to stderr and stdout respectively): times,
counts and exception types only, never a peer address, hotkey, path,
request, case or seed. A configuration refusal exits `2`, which is never
restarted; any other exit is restarted with backoff. A deployment the host
cannot serve yet (`evaluation_host_unavailable`: Docker down, or still
starting after a reboot) is not a refusal: the intake waits for it before it
listens (`waiting_for_host`), and the daemon retries it each period
(`pass_unavailable`). Neither exits for it.

`status` and `restore` see each process by its lock, however it was started
(systemd units or `supervise`): the supervisor's `supervisor.lock`, the
intake's serving lock and the daemon's heartbeat lock.

The service tooling is `python -m scripts.dev.battery_validator_service`,
run from the repository root:

| Command | What it does |
|---|---|
| `preflight --config S [--wait-for-host SECONDS]` | Every check a start needs, all at once (§3). With `--wait-for-host`, re-checks every 5 s for up to SECONDS while the only refusal is a Docker that is not answering yet. Exit 0 ready, 2 not. |
| `parity --config S` | The image and contract parity check alone (§3, `parity`): miners practise on the validator's own pinned images, the standard. |
| `status --config S` | The intake (its serving lock and its own public answer read over its bound address), the daemon (its lock and heartbeat), the supervisor's children if it runs, inbox and pool counts, the latest backup. Healthy only when every part is seen running. Exit 0 healthy, 3 not. |
| `backup --config S` | Root, journal and state together, under the writer lock, with the intake's inbox and transport journal (§6). |
| `restore --config S --from DIR` | Restore one backup into absent paths only, all or nothing (§6). |
| `supervise --config S` | Run both processes with restart-on-failure (§4.2). |
| `units --config S --out DIR` | Write `systemd --user` units for both processes (§4.1). Writes files only. |

## 2. Hard rules

- Never print, copy, log or commit a key, password, token or wallet file.
  Carbon holds no hotkey: miners sign in their own tooling.
- Work in a clean worktree at the merged `main` commit. Run every command
  with `uv run --locked --group science-jax --group chain --group archive`.
- Keep every existing configuration file, key, root and journal. Never
  edit the seed journal: it is append-only commitment evidence, and it holds
  EV5's sealed confirmation batch, which nothing here reads or reveals.
- Back up before any change to the deployment (§6), and stop at the first
  failing step. Never work around a refusal.
- No chain transaction, no weights, no paid compute. Ask the owner to run any
  `sudo` command.

## 3. Bring the service up from the existing v1 deployment

`C` below is the existing deployment file the private host brief names
(`carbon.battery.validator-deployment.v1`, mode `0600`). Every file you write
here is mode `0600`, in a `0700` directory under the operator's private data
directory, outside every checkout.

1. **Intake configuration** (`carbon.battery.intake.v1`):
   ```json
   {
     "schema": "carbon.battery.intake.v1",
     "deployment": "<C>",
     "transport_journal": "<intake dir>/transport.sqlite3",
     "inbox": "<intake dir>/inbox.sqlite3",
     "receiver": "<the validator hotkey's public SS58 address>",
     "host": "127.0.0.1",
     "port": 8467
   }
   ```
   `receiver` is the hotkey a miner signs its requests for; it is public. The
   default bind is loopback. Do not add `exposure_record`, `tls_cert` or
   `tls_key` until §5.
2. **Service configuration** (`carbon.battery.validator-service.v1`):
   ```json
   {
     "schema": "carbon.battery.validator-service.v1",
     "intake": "<intake.json>",
     "state_dir": "<service dir>",
     "backups": "<backup dir>",
     "practice_images": {"image_manifest": "<the validator's worker manifest, as published for practice>"},
     "run_every_s": 60
   }
   ```
   `practice_images` names the manifests of the images miners practise
   against, under the deployment's own keys: `image_manifest`, and
   `torch_image_manifest` when the deployment serves PyTorch. Miners
   practise on the validator's own pinned images (OWNER-LAUNCHPAD-PROD-02,
   answer 10), so each must be the validator's image. On the testnet host
   that is the Launchpad runner profile's `image_manifest`.
   `allow_direct_backend` exists for local development only; leave it out.
3. **Back up** before anything else changes the deployment:
   `backup --config S` (§6). Keep the printed `root_commitment`.
4. **Preflight:** `preflight --config S`. Each check reports `ok`, `refused`
   (with a code and the next step) or `skipped` (it needs a refused one):

   | Check | Refusal codes | What to do |
   |---|---|---|
   | `service` | `service_config_missing`, `_not_regular`, `_not_owner_only`, `_schema`, `_fields`, `service_directory_not_owner_only` | Fix the file or directory named. |
   | `intake` | `intake_config_*`, `intake_exposure_unrecorded`, `intake_exposure_needs_tls` | Fix the intake configuration (§5 for a public bind). |
   | `deployment_config`, `deployment` | `evaluation_*` (the deployment's own codes), `deployment_backend_direct` | The service serves through the isolated carrier only. |
   | `exposure` | `intake_tls_cert_missing`, `intake_tls_key_missing`, `intake_tls_key_not_regular`, `intake_tls_key_not_owner_only`, `intake_tls_unreadable`, `intake_exposure_needs_carrier` | Only for a non-loopback bind (§5). The key must be a regular owner-only file, not a symlink (§5, TLS). |
   | `images` | `image_manifest_unreadable`, `image_not_eligible` (with the doctor's code), `torch_image_not_built_on_worker` | Load or rebuild the pinned image the manifest names; rerun the doctor. `worker.doctor.docker_unavailable` is Docker not answering: start it, or rerun with `--wait-for-host`. |
   | `upgraded` | `deployment_not_upgraded` (with the fields), `deployment_identities_not_carryable` | Run `python -m carbon.battery.operate upgrade --config $C` (OWNER-BATTERY-CARRYOVER-01), then preflight again. A changed rule, material or seed pin needs a new deployment. |
   | `parity` | `practice_image_unnamed`, `practice_manifest_unreadable`, `practice_image_differs` (with the fields, the validator's image as `standard`), `parity_contract_differs` | Stop. Miners practise on the validator's own pinned images and contract (§3.5). |

   An `upgrade` run before LP-PROD-G bound a carrier deployment to the
   read-only (in-process) backend's identity, after which every start
   refused `identities_changed`. `upgrade` from this commit binds the pinned
   images; if the preflight shows `deployment_not_upgraded` with
   `["backend"]`, that is this repair. Back up first.
5. **Parity.** The validator's pinned images are the standard miners
   practise against (OWNER-LAUNCHPAD-PROD-02, answer 10).
   `parity --config S` holds each practice manifest to the image the
   deployment scores with, field by field (`image_id` and every build digest), and the contract the
   deployment is bound to against this checkout's registered battery
   contract, which every miner campaign on this checkout freezes. An image
   difference is resolved by publishing the validator's image for practice;
   the validator's image is never changed to match practice. Then rerun.
   Practice reaches the image's public build identity only, never the hidden
   test conditions: no private case, seed, root, reference or per-case
   result.
6. **Start** (§4), then **verify**:
   - `status --config S` shows `healthy: true`, `intake.serving: true` and
     `intake.answer: ok` with a fresh `snapshot_age_s` (under 60 s), and
     `daemon.state: running` with `daemon.last_pass: ok`;
   - `curl -s http://127.0.0.1:8467/carbon/v1/battery/intake` returns the
     public facts: network, genesis, netuid 567, the battery Challenge,
     `receiver`, the snapshot, `qualification: false`, `reward: false`;
   - the logs show `listening` and, from the daemon, one `pass` per minute.

## 4. Keep it running

### 4.1 With systemd (`systemd --user`)

```bash
python -m scripts.dev.battery_validator_service units --config S --out <units dir>
cp <units dir>/carbon-battery-*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now carbon-battery-intake.service carbon-battery-validator.service
loginctl enable-linger "$USER"   # the owner runs this with sudo if required
```

`units` also makes `<service dir>` owner-only, where the daemon keeps its
heartbeat. Each unit runs `preflight --wait-for-host 300` before it starts
(`TimeoutStartSec=360`), so a Docker still starting after a reboot is waited
out; restarts on failure after 5 s; never restarts the main process's exit 2
(a refused configuration); and gives up after 5 starts in 10 minutes.
`RestartPreventExitStatus` applies to the main process only: a preflight that
refuses its configuration is retried, read-only, until that start limit
stops the unit (`systemctl --user status` shows it failed). Logs:
`journalctl --user -u carbon-battery-intake`.

### 4.2 Without systemd (`supervise`)

On a host without systemd (a WSL distribution without it enabled), run the
supervisor in a session that survives your terminal (`tmux`, or a boot task
the owner sets up):

```bash
python -m scripts.dev.battery_validator_service supervise --config S
```

It holds the service's lock (a second one is refused,
`supervisor_already_running`), refuses to start unless the preflight is
ready (`preflight_not_ready`; it waits up to 5 minutes while Docker is not
answering yet), and restarts a failed child after a backoff doubling from
1 s to 60 s. A child exiting 2 stops both (exit 2); more than 5 restarts of
one child in 10 minutes stops both (exit 1). SIGTERM or Ctrl-C stops both,
SIGKILL after 45 s. Logs and state are under `<service dir>`:
`logs/supervisor.jsonl`, `logs/intake.log`, `logs/daemon.log`,
`supervisor-state.json`, `daemon-heartbeat.json`. The logs are not rotated:
rotate them with `logrotate` (`copytruncate`) or restart the supervisor
after moving them.

**Stopping during a pass.** Both the supervisor and the units give a
stopping process 45 s (`STOP_GRACE_S`, `TimeoutStopSec`). A pass still
running then - a carrier rebuild may take up to the deployment's `seconds`,
600 by default - is killed. Nothing is lost or judged: the run is recovered
as infrastructure at the next start and retried, never scored against the
miner. Stop between passes (the daemon logs one `pass` line each) when you
can.

### 4.3 After a code or image update

1. Stop the service (`systemctl --user stop ...`, or SIGTERM the supervisor).
2. `backup --config S`.
3. `python -m carbon.battery.operate upgrade --config $C`.
4. `preflight --config S` until ready (parity included), then start.

### 4.4 Switching testnet from v1 to v2 (OWNER-TESTNET-V2-SWITCH-01)

Ryan runs these on the testnet host. They use the same 567 identities: the
same validator hotkey as `receiver`, and the same publisher wallet. Names:
- `C1` is the v1 deployment file, which becomes EV5's frozen archive;
- `C2` is the v2 deployment file (`battery-validator-v2`, rule v2);
- `I` is the intake configuration, and `S` the service configuration.

1. **Stop the service:** `systemctl --user stop carbon-battery-intake.service
   carbon-battery-validator.service` (or SIGTERM the supervisor).
2. **Back up v1 one last time** (`backup --config S`), then **archive it.**
   Add `"archived": "OWNER-TESTNET-V2-SWITCH-01"` to `C1`, keeping it mode
   `0600`. From then on:
   - a writable start, `operate upgrade` and the weights publisher refuse
     it;
   - EV5 still reads it.
3. **Point the intake at v2.** In `I`, set `"deployment": "<C2>"`. Nothing
   else in `I` or `S` changes: the transport journal, inbox, receiver,
   host, port and TLS all stay. The daemon unit takes its deployment from
   `I`, so regenerate the units and reload them:

   ```bash
   python -m scripts.dev.battery_validator_service units --config S --out <units dir>
   cp <units dir>/carbon-battery-*.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   ```

4. **Pull the release and upgrade v2.** Wait until #684 and the
   TORCH-GPU-01 work have merged.
   - Pull the released images by digest (the release's pull script), and
     set `C2`'s `image_manifest` (and `torch_image_manifest`, if it serves
     PyTorch) to the released manifests.
   - Set `S`'s `practice_images` to the same manifests.
   - Back up v2 (`backup --config S`, which now backs up v2), then run:

   ```bash
   python -m carbon.battery.operate upgrade --config <C2>
   ```

   This adopts implementation 2.0 under OWNER-BATTERY-CARRYOVER-01. A
   changed rule, material or seed pin needs a new deployment instead.
5. **Preflight and parity:** `preflight --config S` until it is ready, and
   `parity --config S`. Both must pass. Then start:
   `systemctl --user start carbon-battery-intake.service
   carbon-battery-validator.service`.
6. **Status:** `status --config S` shows `healthy: true`. Also check
   `python -m carbon.battery.operate status --config <C2>`: the pool is
   `rule v2` and its batches are complete.
7. **Weights.** From now on, pass v2 to the publisher. Its other arguments
   are unchanged:

   ```bash
   python -m carbon.rewards.testnet_winner_publication run --config <testnet config> \
     --standing <standing> --journal <journal> --ledger <ledger> --battery-deployment <C2>
   ```

   Pointing it at `C1` now refuses with `WEIGHT_SOURCE_ARCHIVED`.

## 5. Publishing the endpoint (owner-reserved steps first)

OWNER-INTAKE-EXPOSURE-01 permits a public bind for testnet 567, the
battery Challenge and today's routes and limits. Exposing a host is still an
operator action, and these choices are the owner's. Nothing below is decided
by this runbook.

**Owner decisions (reserved):**

1. **Public host.** One of:
   - *This WSL host behind NAT*, reached by a TCP port-forward (router to
     Windows, Windows `netsh interface portproxy` to WSL) or by a tunnel that
     passes TCP through. The intake must terminate TLS itself: a tunnel or
     proxy that terminates TLS makes every request one peer, so the per-peer
     limits stop working. The host sleeps and reboots with the workstation,
     and the listener runs beside the validator's private root, journal,
     state and service key (an item on file in OWNER-INTAKE-EXPOSURE-01).
   - *A dedicated always-on server*: restore the deployment there from a
     backup (§6), load the pinned images by digest, and run the same
     service. A backup holds the deployment's state only: the deployment,
     intake and service configurations and the deployment's `service_key`
     (when it has one; signed outcomes need the same key) are carried
     separately, owner-only, and placed before the restore. It separates
     the listener from the workstation, and it is a host Carbon does not yet
     operate.
2. **DNS name** for the endpoint, pointing at that host's public address.
3. **TLS certificate** for that name (for example ACME). The key the intake
   reads must be a regular `0600` file outside every checkout: the preflight
   refuses a symlink (`intake_tls_key_not_regular`), and ACME clients such as
   certbot keep symlinks under `live/`. Copy the key and the full chain to
   the configured paths (owner-only) after each renewal - a deploy hook can
   do it - and restart the intake, which loads them at start.
4. **Firewall**: inbound TCP to the intake's port only, from anywhere (or
   the ranges the owner chooses); nothing else on the host reachable.

*2026-10-03: decided by OWNER-LAUNCHPAD-PROD-02 (decisions 7 and 8).* A
dedicated, always-on server operated by Carbon; a DNS-only (unproxied) name
under the owner's domain; an ACME certificate renewed automatically, whose
deploy hook copies the key to its owner-only file and restarts the intake;
inbound HTTPS to the intake only and SSH by key only; automatic security
updates. They are applied at the server bring-up, by the steps below.

**Then the operator:**

1. Change the intake configuration: `"host": "0.0.0.0"` (or the one
   interface), `"exposure_record": "OWNER-INTAKE-EXPOSURE-01"`,
   `"tls_cert"` and `"tls_key"`. The deployment must be the isolated
   carrier: a `direct` deployment is never exposed
   (`intake_exposure_needs_carrier`).
2. `preflight --config S` until ready, then restart the intake.
3. From another machine:
   `curl -s https://<dns name>:<port>/carbon/v1/battery/intake`.
4. `status --config S`: the probe reads the listener over TLS, verifies it
   against the configured certificate file, and checks the leaf it presents
   is that file's first certificate, byte for byte
   (`intake_certificate_differs` otherwise, for example a certificate the
   intake has not reloaded since a renewal).
5. **Publish** through a pull request that adds the endpoint to
   `scripts/dev/miner_launchpad/published_endpoints.json` (the Launchpad's
   published-endpoints file), in that file's own schema: the battery
   Challenge `battery-fastcharge-ageing-development-v1` and the URL
   `https://<dns name>:<port>`. A miner's Launchpad setup then checks the
   intake serves its chain and Challenge before it is used.

The commitment reader (OD-7(a)) is still missing; keep
`require_commitment: false` until it exists.

## 6. Backup and restore

**Backup** (`backup --config S`) writes one owner-only directory
`<backups>/battery-validator-<UTC time>` holding:

| File | What |
|---|---|
| `root.bin` | the private root (32 bytes) |
| `journal.jsonl` | the seed journal (append-only commitments) |
| `state.sqlite3` | the daemon state (a consistent SQLite snapshot) |
| `inbox.sqlite3`, `transport.sqlite3` | the intake's inbox and receipt journal, when they exist |
| `manifest.json` | each file's SHA-256 and size, the root's public commitment, the journal's entry count. Never the root. |

The first three are copied under the deployment's writer lock, so no
admission, run, batch commitment or upgrade lands half inside the backup. It
is written under a hidden name and renamed when complete; a backup that
fails removes its hidden copy. The work directory is not copied: a run whose
staged output is missing after a restore is retried as infrastructure, never
held against a miner. Configurations, TLS material and the `service_key` are
not in a backup (§5). Keep backups owner-only and off the repository; a lost
root cannot be replaced without a new journal.

**Restore** (`restore --config S --from <backup dir>`) is all or nothing:

- refuses while any part of the service runs, however it was started
  (`restore_service_running`, naming `supervisor`, `intake` or `daemon`):
  stop the units or the supervisor first;
- verifies every file against the manifest first (`backup_corrupt`);
- refuses if any destination, or a SQLite side file (`-wal`, `-shm`,
  `-journal`) beside one, exists (`restore_target_exists`). It never
  overwrites a root, journal or state, live or not. A `.restoring` file an
  interrupted restore left is named too (`restore_leftover_exists`);
- makes every destination directory owner-only before it writes a byte
  (`service_directory_not_owner_only`), writes each file under a temporary
  name and links it into place, then checks the deployment loads with the
  backup's root commitment (`restore_root_differs`). If any step fails it
  removes every file it wrote, so a rerun starts from the same state.

Then `preflight`, then start. A submission a miner sent after the backup is
unknown to the restored intake; the Launchpad resends the same frozen
candidate (the same submission id) when its status answers `not_found`.

## 7. What a miner sees

The Launchpad's intake path (`carbon.battery.campaign`,
`submit_through_intake`) consumes an epoch only with a verdict: `SCORED`,
`INVALID_CONSTRUCTION` or `RECONSTRUCTION_FAILED`. Anything else is a closed
code (`campaign.intake_outcome`), and the frozen candidate stays for a later
submit, which is always the same submission:

| Status | Codes (examples) |
|---|---|
| `QUEUED` | `evaluation_queued` |
| `UNAVAILABLE` (the validator's side) | `intake_unreachable`, `snapshot_unavailable`, `rate`, `capacity`, `inbox_full`, `backend_not_served`, `commitment_reader_unavailable`, `evaluation_failed_infra`, `intake_answer_unrecognised` |
| `REFUSED` (the miner acts) | `hotkey_window_used`, `commitment_required`, `TRANSPORT_IDENTITY`, `AUTH_*`, `snapshot_unknown`, `intake_changed_since_submission`, `intake_signer_changed`, `intake_mismatch`, `signer_unavailable`; the neutral door's codes (`contract_not_served`, `challenge_mismatch`, `non_finite_value`, `duplicate_key` and the rest of `challenge_validator.dispatch.SCREEN_REFUSALS`) |

**The neutral door** (VALIDATOR-01 VAL-D3). Every authenticated
`battery_submit` passes Carbon's challenge-neutral checks before the inbox
sees it (`challenge_validator.Validator.screen`).
- **A refusal** is answered at once (400, its closed code) and is never
  queued, evaluated or counted against the hotkey's window.
- **One behaviour change.** A stale or unknown contract digest, a non-object
  strategy or a cross-Challenge strategy is refused at the door. Before, it
  was admitted and recorded `INVALID_CONSTRUCTION`.
- **The attempt ledger.** Every attempt is recorded in the operator's attempt
  ledger: refused, received, refused for the window, or refused for a full
  inbox. It sits at `<inbox>.attempts.sqlite3`, or wherever the intake
  configuration's optional `attempt_ledger` points, in an owner-only directory.
  A ledger in a shared directory refuses the start, exit 2. The ledger keeps
  each submission's hash, never its strategy. `status` reports its counts by
  kind, and `backup` copies it as `attempts.sqlite3`.

`intake_client.explain(code)` gives each code's plain explanation. A
refusal at admission that is not a verdict (`intake.RECEIVED_AGAIN`) is
received again when the same candidate is resent; a window refusal is resent
only once the window has opened. A resend is sent only when the connected
signer's hotkey names the epoch's own submission: after a signer change the
campaign sends nothing (`intake_signer_changed`), never the candidate a
second time under another hotkey. Every way the trip itself can fail - a
signer that does not sign, a proxy's error page, a connection that breaks,
an intake for another chain - is one of these codes, so the campaign keeps
its frozen candidate instead of ending on an exception.

## 8. Not done here

- No host is exposed, no service was started against the operator's
  deployment, and no endpoint is published: those are §5's steps.
- No security review of the service tooling; the intake's known items stay
  on file (`BATTERY_MINER_SUBMISSION_PATHS.md`). *2026-10-03: the owner has
  since accepted the security review of the service tooling and the intake
  changes (LP-PROD-G) as presented on 2026-10-03 (OWNER-LAUNCHPAD-PROD-02,
  decision 11). Tests are not a security audit, and the acceptance is the
  owner's.*
- The commitment reader (OD-7(a)) and any weights (OD-4b) are out of scope.
