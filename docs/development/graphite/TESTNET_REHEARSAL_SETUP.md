# Testnet as a dress rehearsal: one pass (OWNER-REHEARSAL-AND-RELEASE-01)

Testnet 567 runs exactly as mainnet will:
- **the hidden VM** draws and solves every batch;
- **a small public distribution host** serves the batches to validator-permit
  holders;
- **testnet's validators** run import-only and score miners who commit on
  chain and submit through the real, signed miner door.

Ryan runs every step. Agents hold no credential for the VM or the
distribution host (`HIDDEN_HOST_SETUP.md`, Credential custody).

The prerequisites have all merged to `main`:
- VALIDATOR-19 S1–S4 (#688, #690, #708);
- the finalist batches (#709);
- the testnet v2 switch (#691);
- the worker image release (#684).

Every host runs the same release tag (§2 of the record).

## Part 1. The VM: Carbon's producer (after `HIDDEN_HOST_SETUP.md` §1–5)

1. **The producer's own battery deployment.** It is separate from the
   Graphite development pool: its root draws testnet's batches.
   - Write `/var/lib/carbon-producer/etc/testnet-producer-battery.json`
     (mode 0600), as `HIDDEN_HOST_SETUP.md` §4, with:
     - `state`, `private_root`, `journal` and `work` under
       `/var/lib/carbon-producer/testnet/`;
     - `"rule": "v2"`, `"backend": "direct"` (it only draws and ingests;
       solves run in the pinned truth image);
     - `"require_commitment": false`;
     - `"service_account": "carbon-producer"`.
   - Leave out `development_only`.
   - Then:
     `sudo -u carbon-producer python -m carbon.battery.operate init --config <that file>`.
2. **The producer key and configuration:** `ANSWER_KEY_OPERATIONS.md` §1.
   - The source's `approval` is this record. On the VM's checkout run:
     `sha256sum /opt/carbon/.agent/decisions/2026-10-06-OWNER-REHEARSAL-AND-RELEASE-01.md`.
     It becomes `{"record": "OWNER-REHEARSAL-AND-RELEASE-01", "file": "2026-10-06-OWNER-REHEARSAL-AND-RELEASE-01.md", "sha256": "<that>"}`.
   - `chain` is testnet 567's context: the same as the testnet config's
     `network`, `endpoint`, `provider`, `genesis_hash` and `netuid`.
3. **The tick and the push timer** (`ANSWER_KEY_OPERATIONS.md` §1.3 and §2):
   a `systemd` timer every 5 minutes runs `producer tick`, then the `rsync`
   push. The first tick fills the next slot (screening plus finalist). That
   takes the truth solves' time, about 100 solves per batch.

## Part 2. The distribution host (Hetzner Cloud CX23, the owner's spend)

1. **Create the server:** Ubuntu 24.04 with only Ryan's own SSH key
   (FIDO2), plus `ufw` (allow OpenSSH and 443) and `fail2ban`, as
   `HIDDEN_HOST_SETUP.md` §1.
2. **Accounts:** `carbon-dist` and its `rrsync` inbox
   (`ANSWER_KEY_OPERATIONS.md` §2), plus the producer's push key.
3. **A real TLS certificate,** so any validator can verify it without
   pinning:
   - point `answers.carbonphysics.ai` at it (the owner's name);
   - run `sudo certbot certonly --standalone -d answers.carbonphysics.ai`;
   - copy the certificate and key into `/var/lib/carbon-dist/etc/`, owned by
     `carbon-dist`, mode 0600;
   - add a renewal hook that copies them again and restarts the service.
4. **The owner's exposure record:** `OWNER-ANSWER-KEY-INTAKE-EXPOSURE-01`
   (approved 2026-10-06, `.agent/decisions/`). It must be in the release
   tag the host runs.
5. **`dist.json`** (`ANSWER_KEY_OPERATIONS.md` §3):
   - `"host": "0.0.0.0"`, `"port": 443`;
   - `exposure_record`, `tls_cert` and `tls_key`;
   - `receiver`: the hotkey validators sign their fetches for (the subnet
     owner's public SS58 is fine);
   - `producer_public_key`: from Part 1.2;
   - `chain`: testnet 567.

   Run `distribution serve` as a service under `carbon-dist`.

## Part 3. The PC: testnet v2 as an import-only validator

This replaces steps 4–7 of the v2 switch (`BATTERY_VALIDATOR_SERVICE_RUNBOOK.md`
§4.4, steps 1–3 done: v1 archived, the intake pointing at v2).

1. **Edit v2's deployment `C2`** (mode 0600):
   - `"batch_source": "answer_key"`: it never draws again, and its
     earlier, self-drawn batches (V00–V03, F00) stay unused;
   - `"require_commitment": true`, with `"commitment_reader"` set to testnet
     567's chain context (`network`, `endpoint`, `provider`,
     `genesis_hash`, `netuid`);
   - the released `image_manifest` (and `torch_image_manifest`, if
     served).
2. **Back up and upgrade:**
   `backup --config S`, then
   `python -m carbon.battery.operate upgrade --config <C2>`, then
   `python -m carbon.battery.operate open --config <C2>`.
   It opens empty (`ROTATION_PENDING`); the first imported window
   activates it.
3. **The fetch configuration and timer** (`ANSWER_KEY_OPERATIONS.md` §4):
   - `url`: `https://answers.carbonphysics.ai`;
   - `receiver`: from Part 2.5;
   - `hotkey`: the validator hotkey, through its signer (`signer_socket`);
   - the pinned `producer_public_key`;
   - `deployment`: `C2`;
   - the battery Challenge.

   A `systemd --user` timer runs `answer_key sync` every 5 minutes. The
   validator hotkey must hold a validator permit on 567.
4. **Preflight, parity and status,** as §4.4 steps 5–6, then start the
   intake and the daemon.
5. **The public miner door:** the intake's public bind under
   OWNER-INTAKE-EXPOSURE-01 (§5 of the service runbook). Ask the session
   that runs this before binding publicly.
6. **Weights:** §4.4 step 7, unchanged (`--battery-deployment <C2>`).

## Part 4. The rehearsal check

- **A permitted validator holds the live windows.** `answer_key sync`
  prints `IMPORTED` and then `HELD` for each.
- **The pool rotates.** `operate status --config <C2>` shows the pool
  rotating at the producer's 1,080-block windows.
- **A real submission scores.** A miner (Graphite's construction, under a
  miner hotkey) commits its strategy digest on chain, then submits through
  the intake (`remote_submission`). It gets a sealed outcome, never a hidden
  score.
- **More validators** (when the owner names their hotkeys, VALIDATOR-19
  S4): each runs Part 3 under its own OS account. `acceptance.parity` and
  `score_parity` must show identical batches, seeds and scores.
