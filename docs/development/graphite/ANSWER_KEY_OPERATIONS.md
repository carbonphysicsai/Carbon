# The shared answer key: running it (VALIDATOR-19 slices 2-3)

Three roles, each on its own machine:
- **The producer host** draws, solves, seals, schedules and signs. It is
  private and SSH-only.
- **The distribution host** serves sealed, active packages to permit holders.
  It is small and public.
- **Validators** fetch, verify and import.

Nothing with the producer's root or solver is ever internet-facing, and the
distribution host cannot reach the producer (VALIDATOR-18, the two-host
design). Ryan runs every step below; agents hold no credential for either
host. All of this is DEVELOPMENT: no qualification, settlement or LIVE
authority, and not a security audit (AGENTS.md §13).

## 1. The producer (on the producer host, as `carbon-producer`)

1. **Its signing key**, once:

   ```bash
   python -m carbon.challenge_validator.answer_key keygen --out /var/lib/carbon-producer/etc/producer.key
   ```

   This prints the public key and its id. The public key is the one
   validators and the distribution host pin.
2. **Its configuration**, `/var/lib/carbon-producer/etc/producer.json`
   (mode 0600):

   ```json
   {
     "schema": "carbon.challenge-validator.producer-config.v1",
     "service_account": "carbon-producer",
     "producer_dir": "/var/lib/carbon-producer/producer",
     "signing_key": "/var/lib/carbon-producer/etc/producer.key",
     "chain": {"network": "test", "endpoint": "wss://…", "provider": "…", "genesis_hash": "0x…", "netuid": 567},
     "sources": {
       "battery-fastcharge-ageing-development-v1": {
         "deployment": "/var/lib/carbon-producer/etc/<the producer's battery deployment>.json",
         "overlay": "/var/lib/carbon-producer/etc/battery-truth-overlay",
         "approval": {"record": "OWNER-…", "file": "<its file under .agent/decisions/>", "sha256": "<sha256 of that file>"}
       }
     }
   }
   ```

   **`approval`** is the owner's record authorizing this Challenge's answer
   key. The producer refuses a Challenge whose record file is not in the
   checkout it runs, byte for byte (`producer_challenge_not_approved`).
   Launching a new Challenge is adding its source with its own record.
3. **The rotation tick** runs every few minutes from a `systemd` timer. Its
   only input is the finalized block it reads from `chain`:

   ```bash
   python -m carbon.challenge_validator.producer tick --config /var/lib/carbon-producer/etc/producer.json
   ```

   - **Cadence.** Each Challenge's cadence comes from its own registered rule.
     Battery rule v2 gives one batch per 1,080 blocks, three live at once,
     so the window of slot `s` is blocks `[1080 s, 1080 (s + 3))`. A
     Challenge whose rule names no block cadence gets no scheduled batch.
   - **Filling slots.** A tick fills the next slot ahead of its window: it
     draws, solves in the pinned truth image, seals, schedules and publishes
     into `producer/outbox/<challenge>/`. A slot it cannot fill in time is
     journaled `slot_unfilled`. It is never filled late, and validators keep
     scoring on their current batches meanwhile.
   - **Retiring.** A tick retires every batch whose window has ended: the
     package moves to `producer/retired/<challenge>/`.
     - **A batch drawn from a bank** (rule `v2-bank` and later) releases
       itself: the journal records `release: AUTO_PUBLISH_RETIRED`, and the
       same tick reveals each ended window and publishes its retired cases,
       signed, into `outbox/<challenge>/training/<challenge>/`
       (OWNER-AUTO-PUBLISH-RETIRED-01). The push below carries them to the
       host's training pool. They stay in the outbox, so `--delete` never
       removes them.
     - **Any other batch** records `release: HUMAN_INPUT`: releasing it is
       the owner's decision and never automatic
       (OWNER-BATTERY-3B-AND-EXPOSURE-01).
   - **Status:** `producer status --config …` prints counts only.

## 2. The push (producer to distribution, outbound only)

The producer pushes; the distribution host never connects back.

1. **On the distribution host,** create an account that can only receive
   files into the inbox: OpenSSH's `rrsync`, restricted to one directory.

   ```bash
   sudo useradd --system --create-home --home-dir /var/lib/carbon-dist --shell /bin/sh carbon-dist
   sudo install -d -m 0700 -o carbon-dist -g carbon-dist /var/lib/carbon-dist/inbox
   ```

   `carbon-dist` needs a real shell (`/bin/sh`): sshd runs even the forced
   `rrsync` command through the account's login shell, and `nologin` would
   refuse it (rsync then fails with "protocol version mismatch"). It stays
   confined: its one key is `restrict`ed to the forced `rrsync -wo` into the
   inbox, the sshd `Match User carbon-dist` block allows no TTY and no
   forwarding, and it has no password.

2. **Authorize the producer's key.** In
   `/var/lib/carbon-dist/.ssh/authorized_keys`, add one line for the
   producer's push key:

   ```text
   restrict,command="/usr/bin/rrsync -wo /var/lib/carbon-dist/inbox" ssh-ed25519 AAAA… carbon-producer-push
   ```

3. **Push from the producer** after every tick (the same timer):

   ```bash
   rsync -a --delete --chmod=F600 /var/lib/carbon-producer/producer/outbox/battery-fastcharge-ageing-development-v1/ carbon-dist@<dist host>:
   ```

   `--delete` removes retired packages from the distribution inbox. The
   distribution host also refuses to serve any package whose window ended
   at the finalized block it reads, so a missed push never serves a retired
   batch.

## 3. The distribution host (public, as `carbon-dist`)

The configuration `/var/lib/carbon-dist/etc/dist.json` (mode 0600) holds:
- the inbox, fetch log and nonce store paths;
- `receiver`, the hotkey validators sign their requests for;
- `producer_public_key`;
- the `chain` context for the permit read;
- `host` and `port`.

A public bind needs the owner's exposure record and TLS (`exposure_record`,
`tls_cert`, `tls_key`, as for the intake). Then:

```bash
python -m carbon.challenge_validator.distribution serve --config /var/lib/carbon-dist/etc/dist.json
```

The fetch log (`fetch_log`) is the per-hotkey record of every request and
verdict.

## 4. A validator

- The deployment config sets `"batch_source": "answer_key"`. It then never
  draws, and its pool rotates only by the packages' windows.
- **The fetch configuration** (`carbon.challenge-validator.answer-key-fetch-config.v1`)
  names the distribution URL, `receiver`, the validator's own `hotkey` and
  signer socket, the pinned `producer_public_key`, the deployment and the
  Challenge.
- **The validator's signer** is `carbon-miner-signer`, started for this
  fetch only: `--request answer-key --receiver <receiver>`. A signer
  started as a miner's (the default, MCP only) refuses the fetch as
  `signer_refused:NOT_A_CARBON_REQUEST`.
- **Run on a timer:**

  ```bash
  python -m carbon.challenge_validator.answer_key sync --config <fetch.json>
  ```

- A refusal imports nothing and prints `FAILED_INFRA` with its code. The
  validator never draws or solves a replacement.
